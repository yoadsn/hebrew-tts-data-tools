import random

import pytest

from numeric_pairs.core import render, sample, validate_pair
from numeric_pairs.phone_formats import (
    BUSINESS_PREFIXES, GEOGRAPHIC_PREFIXES, MOBILE_PREFIXES, NATIONAL_PREFIXES,
    sample_phone, spoken_phone, validate_phone,
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
    assert {value[:3] for value in seen["national_line"]} == set(NATIONAL_PREFIXES)
    assert {value.replace("-", "").replace(" ", "")[:4] for value in seen["business_line"]} == set(BUSINESS_PREFIXES)
    assert {value[4] for value in seen["israeli_international"]} == {" ", "-"}
    assert all(not value.startswith("+972 0") for value in seen["israeli_international"])


@pytest.mark.parametrize("kind,value", [
    ("landline", "03-555-1234"),
    ("landline", "07-000-1234"),
    ("local_landline", "555-1234"),
    ("national_line", "070-000-1234"),
    ("israeli_international", "+972 050-000-1234"),
    ("israeli_international", "+972 50-123-4567"),
    ("business_line", "1-700-123-456"),
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
