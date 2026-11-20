"""Run-level distribution and quality accounting. Unreviewed means valid."""

from collections import Counter
from typing import Any

from .catalog import BY_ID
from .core import validate_pair


def summarize(pairs: list[dict[str, Any]], feedback: dict[str, dict[str, Any]]) -> dict[str, Any]:
    archetypes: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    lengths: Counter[str] = Counter()
    readings: Counter[str] = Counter()
    genders: Counter[str] = Counter()
    verdicts: Counter[str] = Counter()
    failures = []
    for pair in pairs:
        archetypes[pair["archetype_id"]] += 1
        categories[BY_ID[pair["archetype_id"]].category] += 1
        gender = pair["sampled"].get("noun", {}).get("gender")
        if gender:
            genders[gender] += 1
        verdicts[feedback.get(pair["id"], {}).get("verdict", "implicit_valid")] += 1
        try:
            validate_pair(pair)
        except (ValueError, KeyError, TypeError) as exc:
            failures.append({"id": pair["id"], "error": str(exc)})
        for alignment in pair["alignments"]:
            kind = alignment["kind"]
            kinds[kind] += 1
            readings[alignment["reading"]] += 1
            digit_count = sum(ch.isdigit() for ch in alignment["digits_text"])
            lengths[f"{kind}:{digit_count}"] += 1
    return {
        "total": len(pairs),
        "valid": verdicts["implicit_valid"] + verdicts["accept"],
        "implicit_valid": verdicts["implicit_valid"],
        "explicit_valid": verdicts["accept"],
        "rejected": verdicts["reject"],
        "needs_correction": verdicts["correct"],
        "by_archetype": dict(sorted(archetypes.items())),
        "by_category": dict(sorted(categories.items())),
        "by_kind": dict(sorted(kinds.items())),
        "digit_lengths": dict(sorted(lengths.items())),
        "by_reading": dict(sorted(readings.items())),
        "noun_gender": dict(sorted(genders.items())),
        "qa_failures": failures,
    }
