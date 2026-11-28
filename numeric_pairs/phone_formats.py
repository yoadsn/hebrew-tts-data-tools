"""Curated Israeli telephone shapes, with test-only subscriber blocks.

Prefix classes follow the linked Hebrew Wikipedia numbering-plan summary.
Israel has no established fictional-number block comparable to NANP 555-01xx.
We therefore use visibly synthetic 000 subscriber groups for generated full
numbers, never claiming they are formally reserved or suitable to dial.
"""

import random
import re

from .adapter import cardinal

SOURCE = "https://he.wikipedia.org/wiki/קידומת_טלפון_בישראל"
MOBILE_PREFIXES = ("050", "051", "052", "053", "054", "055", "058")
GEOGRAPHIC_PREFIXES = ("02", "03", "04", "08", "09")
NATIONAL_PREFIXES = ("072", "073", "074", "076", "077", "079")
BUSINESS_PREFIXES = ("1599", "1700", "1800")
STAR_PHONE_KINDS = ("business_line", "national_line")
STAR_LENGTH_CHOICES = (4, 5, 3)
STAR_LENGTH_WEIGHTS = (70, 20, 10)
STAR_PHONE_PROBABILITY = {
    "business_line": 0.50,
    "national_line": 0.40,
}


def _last_four(rng: random.Random) -> str:
    return f"{rng.randrange(10000):04d}"


def _exchange_three(rng: random.Random) -> str:
    return f"{rng.randint(200, 999)}"


def sample_star_phone(rng: random.Random) -> str:
    length = rng.choices(STAR_LENGTH_CHOICES, weights=STAR_LENGTH_WEIGHTS, k=1)[0]
    first = str(rng.randint(1, 9))
    rest = "".join(str(rng.randrange(10)) for _ in range(length - 1))
    return f"*{first}{rest}"


def is_star_phone(value: str) -> bool:
    return isinstance(value, str) and value.isascii() and bool(re.fullmatch(r"\*\d{3,5}", value))


def sample_phone(kind: str, rng: random.Random) -> str:
    mid = _exchange_three(rng)
    last = _last_four(rng)
    if kind == "mobile":
        prefix = rng.choice(MOBILE_PREFIXES)
        return rng.choice((f"{prefix}-{mid}-{last}", f"{prefix}-{mid}{last}"))
    if kind == "landline":
        prefix = rng.choice(GEOGRAPHIC_PREFIXES)
        return rng.choice((f"{prefix}-{mid}-{last}", f"({prefix}) {mid}-{last}", f"{prefix} {mid} {last}"))
    if kind == "local_landline":
        return f"{mid}-{last}"
    if kind == "national_line":
        if rng.random() < STAR_PHONE_PROBABILITY[kind]:
            return sample_star_phone(rng)
        prefix = rng.choice(NATIONAL_PREFIXES)
        return rng.choice((f"{prefix}-{mid}-{last}", f"{prefix} {mid} {last}"))
    if kind == "israeli_international":
        prefix = rng.choice(MOBILE_PREFIXES + GEOGRAPHIC_PREFIXES + NATIONAL_PREFIXES)[1:]
        return rng.choice((f"+972 {prefix}-{mid}-{last}", f"+972-{prefix}-{mid}-{last}"))
    if kind == "business_line":
        if rng.random() < STAR_PHONE_PROBABILITY[kind]:
            return sample_star_phone(rng)
        prefix = rng.choice(BUSINESS_PREFIXES)
        suffix = f"{rng.randrange(1000):03d}"
        return rng.choice((f"1-{prefix[1:]}-{mid}-{suffix}", f"1 {prefix[1:]} {mid} {suffix}"))
    raise ValueError(f"Unknown phone format: {kind}")


def _digits(value: str) -> str:
    return re.sub(r"[ ()+-]", "", value)


def validate_phone(kind: str, value: str) -> bool:
    if not isinstance(value, str) or not value.isascii():
        return False
    if kind == "mobile":
        prefix = value[:3]
        return prefix in MOBILE_PREFIXES and bool(re.fullmatch(
            rf"{prefix}-(?:\d{{7}}|\d{{3}}-\d{{4}})", value))
    if kind == "landline":
        return any(bool(re.fullmatch(
            rf"(?:{prefix}-\d{{3}}-\d{{4}}|\({prefix}\) \d{{3}}-\d{{4}}|{prefix} \d{{3}} \d{{4}})", value))
            for prefix in GEOGRAPHIC_PREFIXES)
    if kind == "local_landline":
        return bool(re.fullmatch(r"\d{3}-\d{4}", value))
    if kind == "national_line":
        return is_star_phone(value) or any(
            bool(re.fullmatch(rf"(?:{prefix}-\d{{3}}-\d{{4}}|{prefix} \d{{3}} \d{{4}})", value))
            for prefix in NATIONAL_PREFIXES
        )
    if kind == "israeli_international":
        return any(bool(re.fullmatch(rf"\+972[ -]{prefix[1:]}-\d{{3}}-\d{{4}}", value))
                   for prefix in MOBILE_PREFIXES + GEOGRAPHIC_PREFIXES + NATIONAL_PREFIXES)
    if kind == "business_line":
        return is_star_phone(value) or any(
            bool(re.fullmatch(rf"(?:1-{prefix[1:]}-\d{{3}}-\d{{3}}|1 {prefix[1:]} \d{{3}} \d{{3}})", value))
            for prefix in BUSINESS_PREFIXES
        )
    return False


def spoken_phone(kind: str, value: str) -> tuple[str, str]:
    """Return spoken digits and reading ID, preserving zeros and visible groups."""
    if not validate_phone(kind, value):
        raise ValueError(f"Invalid {kind} test phone")
    if value.startswith("*"):
        digits = value[1:]
        spoken = "כוכבית " + " ".join(cardinal(int(digit), "f") for digit in digits)
        return spoken, f"digits-star-{len(digits)}"
    digits = _digits(value)
    if kind == "local_landline":
        groups = (3, 4)
    elif kind == "landline":
        groups = (2, 3, 4)
    elif kind == "israeli_international":
        prefix_length = len(digits) - 3 - 7
        groups = (3, prefix_length, 3, 4)
    elif kind == "business_line":
        groups = (1, 3, 3, 3)
    else:
        groups = (3, 3, 4)
    assert sum(groups) == len(digits)
    output = []
    offset = 0
    for length in groups:
        output.append(" ".join(cardinal(int(digit), "f") for digit in digits[offset:offset + length]))
        offset += length
    return ("פלוס " if kind == "israeli_international" else "") + ", ".join(output), (
        "digits-" + "-".join(str(length) for length in groups))
