"""Generate local JSONL or a directory bundle without running the web app."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from .catalog import ARCHETYPES, CATALOG_VERSION
from .core import RENDERER_VERSION, generate, validate_pair
from .export import build_export
from .variants import resolve_weights


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate paired Hebrew numeric sentences")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=len(ARCHETYPES))
    parser.add_argument("--archetype", action="append", dest="archetypes")
    parser.add_argument("--output", type=Path, help="Write JSONL pairs to a single file instead of stdout")
    parser.add_argument("--out-dir", type=Path, help="Write pairs.jsonl, train/dev/test splits, and manifest.json")
    args = parser.parse_args()

    pairs = generate(args.seed, args.count, args.archetypes)
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
            "catalog_version": CATALOG_VERSION,
            "renderer_version": RENDERER_VERSION,
        }
        run_id = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
        run = {"id": run_id, **identity, "pairs": pairs}
        manifest, splits = build_export(run, {})
        manifest["pairs_file"] = "pairs.jsonl"
        manifest["unique_digits"] = len({pair["digits"] for pair in pairs})
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
