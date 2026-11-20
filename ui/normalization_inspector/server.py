"""Before/after inspector for Hebrew TTS text normalization.

Samples transcripts from a JSONL file, runs them through normalize_tts_words (the context-aware
word-list entry point that pocket-tts's build_official_manifest.py uses), and serves a small Alpine.js page that highlights the word-level
differences computed with jiwer.

    python ui/normalization_inspector/server.py
    python ui/normalization_inspector/server.py --data tmp-sample-normalized.jsonl --field text
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jiwer
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "normalizer"))

from hebrew_tts_normalizer import (  # noqa: E402
    TTSNormalizeOptions,
    load_word_replacements,
    normalize_tts_words,
)

DEFAULT_DATA = ROOT / "tmp-sample-normalized.jsonl"
DEFAULT_CONFIG = ROOT / "configs" / "prepare_pocket_tts_hebrew.yaml"

# Mirrors `cleanup_options` in data_prep/prepare_ivritai.py. The YAML profile does not expose
# these, they are hardcoded there, so keep the two in sync.
CLEANUP_OPTIONS = TTSNormalizeOptions(
    apply_word_replacements=True,
    expand_numbers=True,
    keep_punctuations=True,
    attach_punctuations_to_token=True,
    remove_parentheses=False,
)

WIKI_MARKUP_RE = re.compile(r"={2,}")
DIGIT_RE = re.compile(r"\d")
PUNCT_GAP_RE = re.compile(r"\s+([.,?!])")

FILTERS = {
    "digits": lambda text: bool(DIGIT_RE.search(text)),
    "all": lambda text: True,
}


def strip_wiki_markup(text: str) -> str:
    # Same as data_prep/prepare_ivritai.py::strip_wiki_markup.
    if "=" not in text:
        return text
    return re.sub(r"\s{2,}", " ", WIKI_MARKUP_RE.sub(" ", text)).strip()


class Inspector:
    def __init__(self, data_path: Path, config_path: Path, field: str = "text", stored_field: str = "normalized"):
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        self.strip_markup = bool(cfg.get("prepare_ivritai", {}).get("strip_markup", False))
        self.config_path = config_path
        self.replacements = load_word_replacements()

        self.transcripts: list[str] = []
        self.stored: list[str | None] = []
        with data_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                text = row.get(field)
                if isinstance(text, str) and text.strip():
                    self.transcripts.append(text)
                    stored = row.get(stored_field)
                    self.stored.append(stored if isinstance(stored, str) else None)

        self._lock = threading.Lock()
        self._queues: dict[str, list[int]] = {}
        self._totals: dict[str, int] = {}

    def normalize(self, text: str) -> str:
        if self.strip_markup:
            text = strip_wiki_markup(text)
        # The manifest builder feeds the normalizer a list of words, so do the same here.
        results = normalize_tts_words(text.split(), options=CLEANUP_OPTIONS, word_replacements=self.replacements)
        return PUNCT_GAP_RE.sub(r"\1", " ".join(r for r in results if r)).strip()

    def _queue(self, name: str) -> list[int]:
        if name not in self._queues:
            pred = FILTERS[name]
            idx = [i for i, t in enumerate(self.transcripts) if pred(t)]
            random.shuffle(idx)
            self._queues[name] = idx
            self._totals[name] = len(idx)
        return self._queues[name]

    def next_batch(self, name: str, n: int) -> dict:
        with self._lock:
            queue = self._queue(name)
            # Sampling without replacement; once exhausted, reshuffle and start over.
            exhausted = False
            if not queue:
                del self._queues[name]
                queue = self._queue(name)
                exhausted = True
            batch = [queue.pop() for _ in range(min(n, len(queue)))]
            return {
                "samples": [self.make_sample(i) for i in batch],
                "total_matching": self._totals[name],
                "remaining": len(queue),
                "restarted": exhausted,
            }

    def reset(self, name: str) -> None:
        with self._lock:
            self._queues.pop(name, None)

    def normalize_free_text(self, text: str) -> dict:
        after = self.normalize(text)
        # Only the output is highlighted; the input stays plain editable text.
        _, after_tokens = diff_tokens(text, after)
        return {"after": after, "after_tokens": after_tokens}

    def make_sample(self, index: int) -> dict:
        before = self.transcripts[index]
        after = self.normalize(before)
        before_tokens, after_tokens = diff_tokens(before, after)
        sample = {
            "index": index,
            "before": before,
            "after": after,
            "changed": before != after,
            "before_tokens": before_tokens,
            "after_tokens": after_tokens,
            "stored": None,
        }
        stored = self.stored[index]
        if stored is not None and stored.split() != after.split():
            # Reference is our computed "after"; only the stored side is displayed.
            _, stored_tokens = diff_tokens(after, stored)
            sample["stored"] = stored
            sample["stored_tokens"] = stored_tokens
        return sample


def diff_tokens(before: str, after: str) -> tuple[list[dict], list[dict]]:
    """Word-level alignment via jiwer. Tokens are tagged equal / delete / insert / substitute."""
    ref, hyp = before.split(), after.split()
    if not ref or not hyp:
        return (
            [{"t": w, "op": "delete"} for w in ref],
            [{"t": w, "op": "insert"} for w in hyp],
        )

    out = jiwer.process_words(" ".join(ref), " ".join(hyp))
    before_tokens: list[dict] = []
    after_tokens: list[dict] = []
    for chunk in out.alignments[0]:
        r = ref[chunk.ref_start_idx : chunk.ref_end_idx]
        h = hyp[chunk.hyp_start_idx : chunk.hyp_end_idx]
        op = chunk.type
        before_tokens += [{"t": w, "op": op} for w in r]
        after_tokens += [{"t": w, "op": op} for w in h]
    return before_tokens, after_tokens


def make_handler(inspector: Inspector):
    html = (HERE / "index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status: int = 200):
            self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                return self._send(200, html, "text/html; charset=utf-8")
            if url.path == "/api/info":
                return self._json(
                    {
                        "filters": list(FILTERS),
                        "rows": len(inspector.transcripts),
                        "strip_markup": inspector.strip_markup,
                        "config": str(inspector.config_path.relative_to(ROOT)),
                    }
                )
            if url.path == "/api/samples":
                q = parse_qs(url.query)
                name = q.get("filter", ["digits"])[0]
                if name not in FILTERS:
                    return self._json({"error": f"unknown filter {name!r}"}, 400)
                try:
                    n = max(1, min(100, int(q.get("n", ["10"])[0])))
                except ValueError:
                    return self._json({"error": "n must be an integer"}, 400)
                return self._json(inspector.next_batch(name, n))
            self._json({"error": "not found"}, 404)

        def do_POST(self):
            url = urlparse(self.path)
            if url.path == "/api/reset":
                name = parse_qs(url.query).get("filter", ["digits"])[0]
                if name in FILTERS:
                    inspector.reset(name)
                return self._json({"ok": True})
            if url.path == "/api/normalize":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    text = json.loads(self.rfile.read(length) or b"{}").get("text", "")
                except (ValueError, AttributeError):
                    return self._json({"error": "expected a JSON body like {\"text\": \"...\"}"}, 400)
                if not isinstance(text, str):
                    return self._json({"error": "text must be a string"}, 400)
                return self._json(inspector.normalize_free_text(text))
            self._json({"error": "not found"}, 404)

        def log_message(self, fmt, *args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="JSONL file to sample from")
    parser.add_argument("--field", default="text", help="JSONL property holding the raw text (default: text)")
    parser.add_argument(
        "--stored-field", default="normalized", help="JSONL property holding the previously stored normalization"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="prepare_ivritai YAML profile")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    inspector = Inspector(args.data, args.config, args.field, args.stored_field)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(inspector))
    matching = sum(1 for t in inspector.transcripts if DIGIT_RE.search(t))
    mismatched = sum(
        1
        for t, st in zip(inspector.transcripts, inspector.stored)
        if st is not None and DIGIT_RE.search(t) and st.split() != inspector.normalize(t).split()
    )
    print(f"Digit rows where stored != computed: {mismatched}")
    print(f"Loaded {len(inspector.transcripts)} transcripts ({matching} contain digits)")
    print(f"Serving on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
