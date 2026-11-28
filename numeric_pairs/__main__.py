"""Generate local JSONL or a directory bundle without running the web app."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from .catalog import ARCHETYPES, CATALOG_VERSION
from .core import RENDERER_VERSION, validate_pair
from .export import build_export
from .template_library import (
    DEFAULT_MICRO_TEMPLATE_RATIO,
    generate_mixed_dataset,
    library_file,
    load_library_entries,
    official_library_file,
)
from .variants import resolve_weights


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate paired Hebrew numeric sentences (default 80% MicroTemplates + 20% Tier-1)"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=len(ARCHETYPES))
    parser.add_argument("--archetype", action="append", dest="archetypes")
    parser.add_argument(
        "--micro-ratio",
        type=float,
        default=DEFAULT_MICRO_TEMPLATE_RATIO,
        help="Fraction of pairs drawn from the curated MicroTemplate library (0.0..1.0, default 0.8 = 80%% micro / 20%% Tier-1)",
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=None,
        help="Path to a specific micro_template_library.json (by default merges official in-repo library + local overlay)",
    )
    parser.add_argument(
        "--official-only",
        action="store_true",
        help="Use ONLY the official in-repo numeric_pairs/micro_template_library.json (ignore local unpublished drafts)",
    )
    parser.add_argument(
        "--no-library",
        action="store_true",
        help="Force 100%% Tier-1 simple templates (equivalent to --micro-ratio 0.0)",
    )
    parser.add_argument("--output", type=Path, help="Write JSONL pairs to a single file instead of stdout")
    parser.add_argument("--out-dir", type=Path, help="Write pairs.jsonl, train/dev/test splits, and manifest.json")
    args = parser.parse_args()

    ratio = 0.0 if args.no_library else args.micro_ratio
    if args.library is not None and ratio > 0.0:
        resolved = library_file(explicit_path=args.library)
        if not resolved.is_file():
            raise SystemExit(f"MicroTemplate library file not found: {resolved}")
        lib_entries = load_library_entries(explicit_path=resolved, enabled_only=True)
        if not lib_entries:
            raise SystemExit(f"MicroTemplate library has zero enabled templates: {resolved}")
    elif args.official_only and ratio > 0.0:
        off = official_library_file()
        lib_entries = load_library_entries(explicit_path=off, enabled_only=True) if off.is_file() else []
    elif ratio > 0.0:
        lib_entries = load_library_entries(include_official=True, enabled_only=True)
    else:
        lib_entries = []

    pairs, mix_meta = generate_mixed_dataset(
        args.seed,
        args.count,
        micro_templates=lib_entries,
        micro_template_ratio=ratio,
        archetypes=args.archetypes,
    )
    for pair in pairs:
        validate_pair(pair)

    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        weights = resolve_weights(None)
        identity = {
            "seed": args.seed,
            "count": args.count,
            "archetypes": args.archetypes,
            "address_lengths": [1, 2, 3],
            "boundary_weight": 0.25,
            "variant_weights": weights,
            "micro_template_ratio": mix_meta["requested_micro_template_ratio"],
            "library_fingerprint": mix_meta["library_fingerprint"],
            "catalog_version": CATALOG_VERSION,
            "renderer_version": RENDERER_VERSION,
        }
        run_id = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
        run = {"id": run_id, **identity, "mix": mix_meta, "pairs": pairs}
        manifest, splits = build_export(run, {})
        manifest["pairs_file"] = "pairs.jsonl"
        manifest["unique_digits"] = len({pair["digits"] for pair in pairs})
        manifest["mix"] = mix_meta
        (args.out_dir / "pairs.jsonl").write_text(
            "".join(json.dumps(pair, ensure_ascii=False) + "\n" for pair in pairs),
            encoding="utf-8",
        )
        for split_name, rows in splits.items():
            (args.out_dir / f"{split_name}.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
        (args.out_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            "".join(json.dumps(pair, ensure_ascii=False) + "\n" for pair in pairs),
            encoding="utf-8",
        )
        return

    for pair in pairs:
        print(json.dumps(pair, ensure_ascii=False))


if __name__ == "__main__":
    main()
