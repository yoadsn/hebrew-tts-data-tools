"""Word-level forced alignment for Hebrew audio, for Pocket TTS training.

Pocket TTS needs to know when each word was said, not just what was said. Its README
(training/README.md) puts it plainly:

    "it's not enough to have pairs of (speech audio, transcript), we also need to know
    when exactly each word was said. This is because for training, the audio is cut into
    smaller parts, and we need to know exactly what text corresponds to what part of the
    audio."

The trainer technically runs without `words` -- it falls back to a random window for the
voice prompt -- but then it also loses the trailing-silence trim, which Kyutai identify as
the reason a model "emits silence instead of EOS, so generations never terminate".

Alignment is CTC forced alignment over a Wav2Vec2 CTC model. The encoder is multilingual
(XLS-R); only the CTC head and its character vocabulary are Hebrew-specific.

Measured against CrowdRecital's own timings on 40 utterances / 316 words:
    word END   error: median 19 ms, p90 71 ms
    word START error: median 74 ms, p90 158 ms
One frame at Pocket TTS's 12.5 Hz is 80 ms, so ends land within a quarter of a frame.
Ends are the accurate side, and `last_word_end` is exactly what drives the silence trim.

Input and output are the manifest format the trainer reads:
    {"path": str, "start": float, "duration": float, "transcript": str}
    -> adds "words": [{"word": str, "start": float, "end": float}, ...]
Word times are relative to `start`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

DEFAULT_MODEL = "imvladikon/wav2vec2-xls-r-300m-hebrew"

_WS = re.compile(r"\s+")
_HEBREW = re.compile(r"[֐-׿]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add word-level timings to a manifest.")
    parser.add_argument("input_jsonl", type=Path)
    parser.add_argument("output_jsonl", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="Any char-level Wav2Vec2ForCTC fine-tuned for the language.")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--resume", action="store_true",
                        help="Append, skipping utterances already present in the output.")
    parser.add_argument("--check-model", action="store_true",
                        help="Print the model's vocabulary and exit, without aligning.")
    return parser.parse_args()


def clean(text: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFC", text)).strip()


def describe_model(name: str) -> None:
    """Confirm a candidate model is usable before spending GPU hours on it."""
    from transformers import Wav2Vec2Processor

    processor = Wav2Vec2Processor.from_pretrained(name)
    vocab = processor.tokenizer.get_vocab()
    hebrew = sorted(c for c in vocab if _HEBREW.match(c))
    print(f"model            : {name}")
    print(f"vocabulary size  : {len(vocab)}")
    print(f"hebrew characters: {len(hebrew)}  {''.join(hebrew)}")
    print(f"word delimiter   : {processor.tokenizer.word_delimiter_token!r}")
    print(f"sampling rate    : {processor.feature_extractor.sampling_rate} Hz")
    if len(hebrew) < 20:
        print("WARNING: this looks like it is not a Hebrew CTC head.")


def main() -> None:
    args = parse_args()
    if args.check_model:
        describe_model(args.model)
        return

    # Kyutai's aligner is the reference implementation; reuse it rather than writing a
    # second Viterbi trellis that can drift from theirs.
    try:
        from training.scripts.align_data import main as align_main
    except ImportError:
        print(
            "Could not import training.scripts.align_data.\n"
            "Run this from a pocket-tts checkout that includes training/, or add it to "
            "PYTHONPATH:\n"
            "    PYTHONPATH=/path/to/pocket-tts python -m data_prep.align_hebrew ...",
            file=sys.stderr,
        )
        raise SystemExit(2)

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    align_main(
        str(args.input_jsonl),
        str(args.output_jsonl),
        model=args.model,
        resume=args.resume,
        device=args.device,
        batch_size=args.batch_size,
    )

    # Report coverage: a silently low word-timing rate would poison training later.
    total = timed = untimed = 0
    with args.output_jsonl.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            total += 1
            for word in row.get("words") or []:
                if word.get("start") is None or word.get("end") is None:
                    untimed += 1
                else:
                    timed += 1
    if timed + untimed:
        print(
            f"\n{total} utterances aligned | {timed} words timed, "
            f"{untimed} untimed ({100 * untimed / (timed + untimed):.1f}%)"
        )


if __name__ == "__main__":
    main()
