"""User-approved changes, with round-one feedback still attached to original text."""

import random
from collections import Counter
from pathlib import Path

from numeric_pairs.catalog import NOUNS
from numeric_pairs.contexts import CONTEXTS, date_start_indices
from numeric_pairs.core import generate, render, sample, validate_pair
from numeric_pairs.naturalness import NaturalnessStore


def test_approved_sampling_limits_and_two_postal_lengths():
    postal_lengths = Counter()
    for seed in range(1000):
        rng = random.Random(seed)
        address = sample("delivery", rng)
        assert len(str(address["house"])) <= 3
        if address["include_apartment"]:
            assert 1 <= address["apartment"] <= 120
        assert sample("slash_address", random.Random(seed))["apartment"] <= 120
        assert 2 <= sample("purchase", random.Random(seed))["quantity"] <= 30
        assert 31 <= sample("bulk_purchase", random.Random(seed))["quantity"] <= 9999
        approximate = sample("approximate", random.Random(seed))["quantity"]
        assert approximate % 5 == 0
        assert not any(noun.singular == "אבן" for noun in NOUNS)
        code = sample("postal", random.Random(seed))["postal_code"]
        postal_lengths[len(code)] += 1
        pair = render("postal", {"postal_code": code})
        if len(code) == 7:
            assert pair["alignments"][0]["cardinal_text"].count(", ") == 1
            assert pair["alignments"][0]["reading"] == "digit-by-digit-2-5"
    assert 400 < postal_lengths[5] < 600
    assert 400 < postal_lengths[7] < 600
    assert len(str(sample("address", random.Random(13), address_lengths=(5,))["house"])) == 5


def test_reviewed_readings_and_variants():
    assert render("opening_hours", {"start_hour": 8, "end_hour": 14},
                  context=(0, 0))["cardinal"].startswith("הסניף פתוח בין שמונה לשתיים")
    calendar = {"day": 23, "month_number": 8}
    assert render("numeric_calendar", {**calendar, "spoken_style": "ordinal"})["alignments"][0]["cardinal_text"] == "בעשרים ושלוש לשמיני"
    assert render("numeric_calendar", {**calendar, "spoken_style": "named"})["alignments"][0]["cardinal_text"] == "בעשרים ושלוש לאוגוסט"
    assert render("numeric_calendar", {**calendar, "spoken_style": "named"},
                  reading_variant="formal")["alignments"][0]["cardinal_text"] == "בעשרים ושלושה באוגוסט"
    assert "בראשון לשמיני" in render("numeric_calendar", {
        "day": 1, "month_number": 8, "spoken_style": "ordinal"})["cardinal"]
    assert render("numeric_calendar", {
        "day": 2, "month_number": 8, "spoken_style": "ordinal"})["alignments"][0]["cardinal_text"] == "בשני לשמיני"
    assert render("numeric_calendar", {
        "day": 2, "month_number": 8, "spoken_style": "named"})["alignments"][0]["cardinal_text"] == "בשני לאוגוסט"
    assert render("numeric_calendar", {
        "day": 5, "month_number": 10, "spoken_style": "named"})["alignments"][0]["cardinal_text"] == "בחמישי לאוקטובר"
    assert render("numeric_calendar", {
        "day": 10, "month_number": 4, "spoken_style": "ordinal"})["alignments"][0]["cardinal_text"] == "בעשירי לרביעי"
    assert "שקל" in render("large_shekels", {"shekels_large": 673822})["cardinal"]
    assert "שקלים" in render("large_shekels", {"shekels_large": 673822},
                            reading_variant="formal")["cardinal"]
    for kind, values in (("large_shekels", {"shekels_large": 673822}),
                         ("area", {"square_meters": 152}),
                         ("numeric_calendar", {**calendar, "spoken_style": "named"})):
        assert render(kind, values)["id"] != render(kind, values, reading_variant="formal")["id"]
    assert "מטר רבוע" in render("area", {"square_meters": 152})["cardinal"]
    assert "מטרים רבועים" in render("area", {"square_meters": 152},
                                  reading_variant="formal")["cardinal"]
    assert "מיליון, " in render("million_exact", {"number": 1762889})["cardinal"]
    assert "אפס אפס אפס, " in render("bank_account", {
        "branch": 101, "account": "000794"})["cardinal"]


def test_generated_dates_use_era_frames_and_contexts_do_not_cross_domains():
    pairs = [p for seed in range(15) for p in generate(
        seed, 124, ["full_date", "slash_date"])]
    assert {("past" if p["sampled"]["year"] < 2020 else
             "future" if p["sampled"]["year"] > 2027 else "current")
            for p in pairs} == {"past", "current", "future"}
    for pair in pairs:
        assert pair["context"]["start"] in date_start_indices(pair["sampled"]["year"])
        if pair["sampled"]["year"] < 2020:
            assert "יישלחו" not in pair["cardinal"]
        validate_pair(pair)
    contexts = CONTEXTS["opening_hours"]
    assert all("בין השעות" not in start for start in contexts.starts)
    assert all("בין " in start for start in contexts.starts)
    assert all("בין השעות" not in end for end in contexts.ends)


def test_round_one_rating_identity_survives_new_generator(tmp_path):
    frozen = NaturalnessStore(tmp_path).flags()
    assert len(frozen) >= 24
    assert all(item["pair"]["catalog_version"] == "starter-13" for item in frozen[:24])
    first = frozen[0]
    NaturalnessStore(tmp_path).rate(first["id"], "unnatural", "הערת בדיקה")
    refreshed = NaturalnessStore(tmp_path).flags()[0]
    assert refreshed["pair"] == first["pair"]
    assert refreshed["rating"]["note"] == "הערת בדיקה"
