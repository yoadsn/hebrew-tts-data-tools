"""Generate local JSONL without running the web app."""

import argparse
import json

from .catalog import ARCHETYPES
from .core import generate


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate paired Hebrew numeric sentences")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=len(ARCHETYPES))
    parser.add_argument("--archetype", action="append", dest="archetypes")
    args = parser.parse_args()
    for pair in generate(args.seed, args.count, args.archetypes):
        print(json.dumps(pair, ensure_ascii=False))


if __name__ == "__main__":
    main()
