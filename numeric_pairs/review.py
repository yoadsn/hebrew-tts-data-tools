"""Local review state, kept outside the source tree by default."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from .catalog import ARCHETYPES, CATALOG_VERSION
from .core import RENDERER_VERSION, generate
from .variants import resolve_weights

_lock = Lock()


class ReviewStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or os.environ.get("NUMERIC_PAIRS_DATA_DIR", Path.home() / ".local/share/hebrew-numeric-pairs"))
        self.root.mkdir(parents=True, exist_ok=True)

    def create_run(self, seed: int, count: int, archetypes: list[str] | None = None, *,
                   address_lengths: tuple[int, ...] = (1, 2, 3),
                   boundary_weight: float = 0.25,
                   variant_weights: dict[str, float] | None = None) -> dict[str, Any]:
        weights = resolve_weights(variant_weights)
        pairs = generate(seed, count, archetypes, address_lengths=address_lengths,
                         boundary_weight=boundary_weight, variant_weights=weights)
        identity = {"seed": seed, "count": count, "archetypes": archetypes,
                    "address_lengths": list(address_lengths), "boundary_weight": boundary_weight,
                    "variant_weights": weights,
                    "catalog_version": CATALOG_VERSION, "renderer_version": RENDERER_VERSION}
        run_id = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
        path = self.root / f"run-{run_id}.json"
        with _lock:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
            data = {"id": run_id, **identity, "pairs": pairs}
            temporary = self.root / f"run-{run_id}.tmp"
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
        return data

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        if len(run_id) != 20 or any(ch not in "0123456789abcdef" for ch in run_id):
            return None
        path = self.root / f"run-{run_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def list_runs(self) -> list[dict[str, Any]]:
        runs = []
        for path in sorted(self.root.glob("run-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
            data = json.loads(path.read_text(encoding="utf-8"))
            runs.append({"id": data["id"], "seed": data["seed"], "count": data["count"],
                         "catalog_version": data["catalog_version"]})
        return runs

    def never_ran_archetypes(self) -> list[str]:
        """Count generated samples, not selected ids; scan beyond the 30-run UI archive."""
        seen = set()
        for path in self.root.glob("run-*.json"):
            run = json.loads(path.read_text(encoding="utf-8"))
            seen.update(pair["archetype_id"] for pair in run["pairs"])
        return [item.id for item in ARCHETYPES if item.id not in seen]

    def save_feedback(self, run_id: str, pair_id: str, verdict: str, note: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run is None or pair_id not in {pair["id"] for pair in run["pairs"]}:
            raise ValueError("Unknown run or sample")
        if verdict not in {"accept", "reject", "correct"} or len(note) > 2000:
            raise ValueError("Invalid verdict or note (max 2000 characters)")
        if verdict == "correct" and not note.strip():
            raise ValueError("A correction needs a note")
        record = {"run_id": run_id, "pair_id": pair_id, "verdict": verdict, "note": note,
                  "created_at": datetime.now(timezone.utc).isoformat()}
        with _lock, (self.root / "feedback.jsonl").open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def feedback(self, run_id: str) -> dict[str, dict[str, Any]]:
        path = self.root / "feedback.jsonl"
        if not path.exists():
            return {}
        result = {}
        with _lock, path.open(encoding="utf-8") as source:
            for line in source:
                item = json.loads(line)
                if item["run_id"] == run_id:
                    result[item["pair_id"]] = item
        return result

    def coverage(self, run_id: str) -> dict[str, Any] | None:
        from .coverage import summarize

        run = self.get_run(run_id)
        return summarize(run["pairs"], self.feedback(run_id)) if run else None
