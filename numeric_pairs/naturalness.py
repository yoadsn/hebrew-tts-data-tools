"""Human rating queue for agent-flagged Hebrew examples; no automatic rejection."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from threading import Lock

from .core import render


_lock = Lock()
FLAGS_FILE = Path(__file__).with_name("naturalness_flags.json")
ROUND_ONE_SNAPSHOTS = Path(__file__).with_name("naturalness_round1_pairs.json")
NEXT_FLAGS_FILE = Path(__file__).with_name("naturalness_flags_round2.json")
ROUND_TWO_SNAPSHOTS = Path(__file__).with_name("naturalness_round2_pairs.json")
ROUND_THREE_FLAGS = Path(__file__).with_name("naturalness_flags_round3.json")
ROUND_THREE_SNAPSHOTS = Path(__file__).with_name("naturalness_round3_pairs.json")
ROUND_FOUR_FLAGS = Path(__file__).with_name("naturalness_flags_round4.json")
ROUND_FOUR_SNAPSHOTS = Path(__file__).with_name("naturalness_round4_pairs.json")
VERDICTS = {"natural", "unnatural", "unsure"}


class NaturalnessStore:
    def __init__(self, root: Path, flags_path: Path = FLAGS_FILE):
        self.path = Path(root) / "naturalness-ratings.jsonl"
        self.flags_path = flags_path

    def flags(self) -> list[dict]:
        rounds = ((FLAGS_FILE, ROUND_ONE_SNAPSHOTS, 1),
                  (NEXT_FLAGS_FILE, ROUND_TWO_SNAPSHOTS, 2),
                  (ROUND_THREE_FLAGS, ROUND_THREE_SNAPSHOTS, 3),
                  (ROUND_FOUR_FLAGS, ROUND_FOUR_SNAPSHOTS, 4)) if self.flags_path == FLAGS_FILE else (
                      (self.flags_path, None, 1),)
        latest = {}
        if self.path.exists():
            with _lock:
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    item = json.loads(line)
                    latest[item["id"]] = item
        result = []
        for flag_path, snapshot_path, round_number in rounds:
            if not flag_path.exists():
                continue
            raw = json.loads(flag_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError("Naturalness flags must be a list")
            snapshots = (json.loads(snapshot_path.read_text(encoding="utf-8"))
                         if snapshot_path and snapshot_path.exists() else {})
            for flag in raw:
                context = tuple(flag["context"])
                key = sha256(json.dumps({name: flag[name] for name in (
                    "archetype_id", "sampled", "context", "continuation", "reason_he", "suggestion_he")},
                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
                pair = snapshots.get(key)
                if pair is None:
                    pair = render(flag["archetype_id"], flag["sampled"],
                                  context=context, continuation=flag["continuation"])
                result.append({"id": key, "pair": pair, "reason": flag["reason_he"],
                               "suggestion": flag["suggestion_he"],
                               "severity": flag.get("severity", "medium"),
                               "rating": latest.get(key), "round": round_number})
        return result

    def rate(self, flag_id: str, verdict: str, note: str) -> dict:
        if verdict not in VERDICTS or len(note) > 2000:
            raise ValueError("Choose natural, unnatural or unsure (note max 2,000 characters)")
        if flag_id not in {item["id"] for item in self.flags()}:
            raise ValueError("Unknown naturalness flag")
        record = {"id": flag_id, "verdict": verdict, "note": note.strip(),
                  "created_at": datetime.now(timezone.utc).isoformat()}
        with _lock, self.path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record
