"""Conservative corpus evidence and human-reviewed, non-executable proposals."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from pathlib import Path
from threading import Lock

_lock = Lock()
# Identifiers are redacted before any evidence is persisted. Do not use this
# heuristic to claim a corpus is anonymized: the importer must check consent.
_SENSITIVE = re.compile(r"(?<!\d)(?:0\d{1,2}[- ]?\d{7}|\d{7,})(?!\d)|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_NUMBER = re.compile(r"(?<![\w\d])\d{1,2}:\d{2}(?!\d)|(?<!\d)\d{1,5}(?:%|(?:[.,]\d{1,3})?)(?!\d)")


def _kind(expression: str) -> str:
    if ":" in expression:
        return "time"
    if expression.endswith("%"):
        return "percent"
    if "." in expression or "," in expression:
        return "decimal_or_grouped"
    return "integer"


def extract(sentences: str) -> list[dict]:
    """Group identical structural contexts; never retain identifier digits."""
    if len(sentences) > 20000 or len(sentences.splitlines()) > 100:
        raise ValueError("Corpus paste is limited to 100 lines and 20,000 characters")
    found: dict[str, dict] = {}
    for line in sentences.splitlines():
        line = _SENSITIVE.sub("[מזהה מוסתר]", line.strip())
        if not line or len(line) > 300:
            continue
        for match in _NUMBER.finditer(line):
            expression = match.group()
            kind = _kind(expression)
            # Retain context rather than digits. A sentence may have multiple
            # expressions, each of which becomes a separate candidate.
            pattern = line[:match.start()] + "{NUM}" + line[match.end():]
            pattern = _NUMBER.sub("{NUM}", pattern)
            key = sha256((kind + "\0" + pattern).encode()).hexdigest()[:20]
            record = found.setdefault(key, {"id": key, "pattern": pattern,
                                            "kind": kind, "count": 0, "evidence": []})
            record["count"] += 1
            if len(record["evidence"]) < 3:
                record["evidence"].append(line[:match.start()] + "[מספר]" + line[match.end():])
    return list(found.values())


class CandidateStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "candidates.json"
        self.evaluation_path = self.root / "held-out-evaluation.json"

    def list(self) -> list[dict]:
        with _lock:
            return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def ingest(self, *, sentences: str, source: str, license: str,
               restrictions: str, approved_for_derivation: bool,
               purpose: str = "derivation") -> list[dict]:
        if purpose not in {"derivation", "evaluation"}:
            raise ValueError("Choose derivation or evaluation")
        if not approved_for_derivation or not source.strip() or not license.strip():
            raise ValueError("Source, license and explicit corpus-use permission are required")
        if any(len(field) > 300 for field in (source, license, restrictions)):
            raise ValueError("Provenance fields must be at most 300 characters")
        extracted = extract(sentences)
        provenance = {"source": source.strip(), "license": license.strip(),
                      "restrictions": restrictions.strip()}
        with _lock:
            if purpose == "evaluation":
                # The held-out source never enters candidate evidence or proposals.
                records = json.loads(self.evaluation_path.read_text(encoding="utf-8")) if self.evaluation_path.exists() else []
                records.append({"provenance": provenance, "patterns": [item["pattern"] for item in extracted],
                                "count": sum(item["count"] for item in extracted)})
                self._atomic_write(self.evaluation_path, records)
                return extracted
            candidates = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
            by_id = {candidate["id"]: candidate for candidate in candidates}
            for item in extracted:
                if item["id"] in by_id:
                    previous = by_id[item["id"]]
                    previous["count"] += item["count"]
                    previous["evidence"] = list(dict.fromkeys(previous["evidence"] + item["evidence"]))[:3]
                    if provenance not in previous["provenance"]:
                        previous["provenance"].append(provenance)
                else:
                    item.update({"status": "pending", "provenance": [provenance], "review": None})
                    candidates.append(item)
            self._write(candidates)
        return extracted

    def review(self, candidate_id: str, *, status: str, grammar: str, slots: str,
               safe_ranges: str, written_policy: str, spoken_policy: str, note: str) -> dict:
        if status not in {"approved", "rejected"}:
            raise ValueError("Choose approved or rejected")
        fields = (grammar, slots, safe_ranges, written_policy, spoken_policy, note)
        if any(len(field) > 2000 for field in fields):
            raise ValueError("Review fields must be at most 2,000 characters")
        if status == "approved" and not all(field.strip() for field in fields[:5]):
            raise ValueError("Approval requires grammar, slots, ranges and both reading policies")
        with _lock:
            candidates = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
            for item in candidates:
                if item["id"] == candidate_id:
                    item["status"] = status
                    item["review"] = {"grammar": grammar.strip(), "slots": slots.strip(),
                                      "safe_ranges": safe_ranges.strip(), "written_policy": written_policy.strip(),
                                      "spoken_policy": spoken_policy.strip(), "note": note.strip(),
                                      "created_at": datetime.now(timezone.utc).isoformat()}
                    self._write(candidates)
                    return item
        raise ValueError("Unknown candidate")

    def _write(self, candidates: list[dict]) -> None:
        self._atomic_write(self.path, candidates)

    @staticmethod
    def _atomic_write(path: Path, records: list[dict]) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
