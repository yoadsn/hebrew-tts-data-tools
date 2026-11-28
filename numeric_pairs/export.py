"""Versioned JSONL export with default-valid review semantics and family holdouts."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .catalog import BY_ID
from .core import validate_pair

SCHEMA_VERSION = "1"


def build_export(run: dict[str, Any], feedback: dict[str, dict[str, Any]]) -> tuple[dict, dict[str, list[dict]]]:
    """Split whole semantic categories, never variants of one family across sets."""
    valid = []
    verdicts: Counter[str] = Counter()
    for pair in run["pairs"]:
        verdict = feedback.get(pair["id"], {}).get("verdict", "implicit_valid")
        verdicts[verdict] += 1
        if verdict in {"reject", "correct"}:
            continue  # Correction text is a proposal, not a rewritten pair.
        if verdict not in {"accept", "implicit_valid"}:
            raise ValueError(f"Unknown review verdict: {verdict}")
        validate_pair(pair)
        valid.append(pair)
    families = sorted({BY_ID[pair["archetype_id"]].category for pair in valid},
                      key=lambda family: sha256(f"{run['seed']}:{family}".encode()).hexdigest())
    if len(families) < 3:
        raise ValueError("Export requires at least three valid category families for held-out train/dev/test")
    assignment = {family: "train" for family in families[:-2]}
    assignment[families[-2]] = "dev"
    assignment[families[-1]] = "test"
    splits: dict[str, list[dict]] = {"train": [], "dev": [], "test": []}
    for pair in valid:
        splits[assignment[BY_ID[pair["archetype_id"]].category]].append({
            "schema_version": SCHEMA_VERSION, "split": assignment[BY_ID[pair["archetype_id"]].category],
            **pair,
        })
    values = {name: {str(a["value"]) for row in rows for a in row["alignments"]}
              for name, rows in splits.items()}
    templates_by_split = {
        name: {row["micro_template_id"] for row in rows if row.get("micro_template_id")}
        for name, rows in splits.items()
    }
    template_leakage = any(
        templates_by_split[a] & templates_by_split[b]
        for a, b in (("train", "dev"), ("train", "test"), ("dev", "test"))
    )
    source_tiers: Counter[str] = Counter(
        row.get("source_tier") or ("micro_template" if row.get("micro_template_id") else "tier1")
        for row in valid
    )
    unique_micro_templates = len({row["micro_template_id"] for row in valid if row.get("micro_template_id")})
    sampling_meta: dict[str, Any] = {
        "archetypes": run.get("archetypes"),
        "address_lengths": run.get("address_lengths"),
        "boundary_weight": run.get("boundary_weight"),
        "variant_weights": run.get("variant_weights"),
    }
    if "micro_template_ratio" in run:
        sampling_meta["micro_template_ratio"] = run.get("micro_template_ratio")
    if run.get("library_fingerprint"):
        sampling_meta["library_fingerprint"] = run.get("library_fingerprint")
    elif isinstance(run.get("mix"), dict) and run["mix"].get("library_fingerprint"):
        sampling_meta["library_fingerprint"] = run["mix"]["library_fingerprint"]

    manifest = {"schema_version": SCHEMA_VERSION, "run_id": run["id"],
                "catalog_version": run["catalog_version"], "renderer_version": run["renderer_version"],
                "seed": run["seed"], "sampling": sampling_meta,
                "generated": len(run["pairs"]), "exported": len(valid), "verdicts": dict(sorted(verdicts.items())),
                "source_tiers": dict(sorted(source_tiers.items())),
                "unique_micro_templates": unique_micro_templates,
                "split_strategy": "held-out-category-family-v1", "family_assignment": assignment,
                "splits": {name: len(rows) for name, rows in splits.items()},
                "value_overlap": {f"{a}-{b}": len(values[a] & values[b])
                                  for a, b in (("train", "dev"), ("train", "test"), ("dev", "test"))},
                "quality_gates": {"all_spans_valid": True, "all_spoken_digit_free": True,
                                  "three_nonempty_splits": all(splits.values()),
                                  "rejected_and_corrections_excluded": True,
                                  "zero_template_leakage": not template_leakage}}
    if not manifest["quality_gates"]["three_nonempty_splits"]:
        raise ValueError("Export requires nonempty train/dev/test splits")
    return manifest, splits


def save_export(root: Path, run: dict[str, Any], feedback: dict[str, dict[str, Any]]) -> dict:
    manifest, splits = build_export(run, feedback)
    fingerprint = sha256(json.dumps({"run": run["id"], "verdicts": {
        key: item["verdict"] for key, item in sorted(feedback.items())}}, sort_keys=True).encode()).hexdigest()[:16]
    export_id = f"{run['id']}-{fingerprint}"
    folder = Path(root) / "exports" / export_id
    folder.mkdir(parents=True, exist_ok=True)
    for name, rows in splits.items():
        text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        (folder / f"{name}.jsonl").write_text(text, encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"id": export_id, "manifest": manifest}
