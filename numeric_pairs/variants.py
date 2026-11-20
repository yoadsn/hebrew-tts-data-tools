"""Reviewable spoken-form policies. Zero means the formal form is dormant.

Weights are snapshotted into each run, so future policy changes cannot rewrite
old examples or move their feedback to a newly rendered sentence.
"""

DEFAULT_FORMAL_WEIGHTS = {
    "section": 0.0,
    "decimal_temp": 0.0,
    "version": 0.0,
    "money_cents": 0.0,
    "full_date": 0.0,
    "duration_half": 0.0,
    "large_shekels": 0.0,
    "area": 0.0,
    "numeric_calendar": 0.0,
}


def resolve_weights(overrides: dict[str, float] | None = None) -> dict[str, float]:
    weights = DEFAULT_FORMAL_WEIGHTS.copy()
    if overrides is not None:
        for key, weight in overrides.items():
            if key not in weights or isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= weight <= 1:
                raise ValueError(f"Invalid formal variant weight for {key}")
            weights[key] = float(weight)
    return weights
