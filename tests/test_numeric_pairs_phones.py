from collections import Counter
import random

import pytest

from numeric_pairs.core import render, sample, validate_pair
from numeric_pairs.phone_formats import (
    BUSINESS_PREFIXES, GEOGRAPHIC_PREFIXES, MOBILE_PREFIXES, NATIONAL_PREFIXES,
    STAR_PHONE_KINDS, is_star_phone, sample_phone, sample_star_phone,
    spoken_phone, validate_phone,
)


KINDS = ("mobile", "landline", "local_landline", "national_line",
         "israeli_international", "business_line")


@pytest.mark.parametrize("kind", KINDS)
def test_israeli_phone_shapes_are_examples_with_exact_spans(kind):
    seen = set()
    for seed in range(120):
        value = sample_phone(kind, random.Random(seed))
        seen.add(value)
        assert validate_phone(kind, value)
        if kind in STAR_PHONE_KINDS and value.startswith("*"):
            assert is_star_phone(value)
        else:
            assert "000" in value
        spoken, policy = spoken_phone(kind, value)
        assert policy.startswith("digits-")
        assert not any(char.isdigit() for char in spoken)
        pair = render(kind, {"phone": value}) if kind != "mobile" else render("mobile", {"phone": value})
        assert pair["alignments"][0]["digits_text"] == value
        assert pair["alignments"][0]["cardinal_text"] == spoken
        validate_pair(pair)
    assert len(seen) >= 20


def test_all_curated_prefix_classes_are_sampled_and_phone_types_are_distinct():
    seen = {kind: {sample_phone(kind, random.Random(seed)) for seed in range(1000)}
            for kind in KINDS}
    assert {value[:3] for value in seen["mobile"]} == set(MOBILE_PREFIXES)
    assert {value[1:3] if value.startswith("(") else value[:2]
            for value in seen["landline"] if value.startswith("(") or value.startswith("0")} == set(GEOGRAPHIC_PREFIXES)
    assert {value[:3] for value in seen["national_line"] if not value.startswith("*")} == set(NATIONAL_PREFIXES)
    assert {value.replace("-", "").replace(" ", "")[:4]
            for value in seen["business_line"] if not value.startswith("*")} == set(BUSINESS_PREFIXES)
    assert {value[4] for value in seen["israeli_international"]} == {" ", "-"}
    assert all(not value.startswith("+972 0") for value in seen["israeli_international"])
    for kind in STAR_PHONE_KINDS:
        star_values = [value for value in seen[kind] if value.startswith("*")]
        assert len(star_values) >= 200
        assert {len(value) - 1 for value in star_values} == {3, 4, 5}
    for kind in KINDS:
        if kind not in STAR_PHONE_KINDS:
            assert all(not value.startswith("*") for value in seen[kind])


@pytest.mark.parametrize("kind", STAR_PHONE_KINDS)
@pytest.mark.parametrize("value,expected_spoken,expected_reading", [
    ("*1213", "כוכבית אחת שתיים אחת שלוש", "digits-star-4"),
    ("*509", "כוכבית חמש אפס תשע", "digits-star-3"),
    ("*24680", "כוכבית שתיים ארבע שש שמונה אפס", "digits-star-5"),
])
def test_star_phone_spoken_readings_and_alignments(kind, value, expected_spoken, expected_reading):
    assert validate_phone(kind, value)
    spoken, reading = spoken_phone(kind, value)
    assert spoken == expected_spoken
    assert reading == expected_reading
    pair = render(kind, {"phone": value})
    assert pair["alignments"][0]["digits_text"] == value
    assert pair["alignments"][0]["cardinal_text"] == expected_spoken
    assert pair["alignments"][0]["reading"] == expected_reading
    validate_pair(pair)


def test_star_phone_digit_length_distribution():
    rng = random.Random(42)
    counts = Counter(len(sample_star_phone(rng)) - 1 for _ in range(5000))
    assert set(counts) == {3, 4, 5}
    assert 0.67 <= counts[4] / 5000 <= 0.73
    assert 0.17 <= counts[5] / 5000 <= 0.23
    assert 0.08 <= counts[3] / 5000 <= 0.12


@pytest.mark.parametrize("kind,value", [
    ("landline", "03-555-1234"),
    ("landline", "07-000-1234"),
    ("landline", "*1213"),
    ("local_landline", "555-1234"),
    ("local_landline", "*1213"),
    ("mobile", "*1213"),
    ("national_line", "070-000-1234"),
    ("national_line", "*12"),
    ("national_line", "*123456"),
    ("israeli_international", "+972 050-000-1234"),
    ("israeli_international", "+972 50-123-4567"),
    ("israeli_international", "*1213"),
    ("business_line", "1-700-123-456"),
    ("business_line", "*12"),
    ("business_line", "*123456"),
    ("business_line", "*12-13"),
    ("business_line", "1213"),
])
def test_non_example_subscribers_and_wrong_prefix_classes_are_rejected(kind, value):
    assert not validate_phone(kind, value)
    with pytest.raises(ValueError):
        render(kind, {"phone": value})


def test_existing_reviewed_mobile_reading_is_unchanged():
    pair = render("mobile", {"phone": "050-7894567"})
    assert pair["alignments"][0]["cardinal_text"] == (
        "אפס חמש אפס, שבע שמונה תשע, ארבע חמש שש שבע")
    assert pair["alignments"][0]["reading"] == "digit-by-digit-3-3-4"
    assert sample("mobile", random.Random(23))["phone"] != "050-7894567"
