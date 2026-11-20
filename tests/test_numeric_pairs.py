import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from numeric_pairs.catalog import BY_ID, SCENARIO_AREAS
from numeric_pairs.core import generate, render, sampled_number, validate_pair
from numeric_pairs.coverage import summarize
from numeric_pairs.review import ReviewStore
from numeric_pairs.candidates import CandidateStore, extract
from numeric_pairs.export import build_export, save_export


@pytest.mark.parametrize("value,expected", [(1, "אחת"), (2, "שתיים"), (120, "מאה ועשרים")])
def test_address_values_and_exact_spans(value, expected):
    pair = render("address", {"street": "הרצל", "house": value})
    assert pair["digits"] == f"המשרד ממוקם ברחוב הרצל {value}"
    assert pair["cardinal"] == f"המשרד ממוקם ברחוב הרצל {expected}"
    alignment = pair["alignments"][0]
    assert pair["digits"][slice(*alignment["digits_span"])] == str(value)
    assert pair["cardinal"][slice(*alignment["cardinal_span"])] == expected


def test_one_and_two_agreement():
    noun = {"singular": "עגבנייה", "plural": "עגבניות", "gender": "f"}
    two = render("purchase", {"noun": noun, "quantity": 2})
    assert two["cardinal"] == "קניתי שתי עגבניות היום."
    with pytest.raises(ValueError):
        render("purchase", {"noun": noun, "quantity": 1})
    masculine = {"singular": "שולחן", "plural": "שולחנות", "gender": "m"}
    assert render("purchase", {"noun": masculine, "quantity": 2})["cardinal"] == "קניתי שני שולחנות היום."


def test_attached_prefix_alignment():
    noun = {"singular": "עגבנייה", "plural": "עגבניות", "gender": "f"}
    pair = render("approximate", {"noun": noun, "quantity": 50})
    assert pair["digits"] == "קניתי כ-50 עגבניות היום."
    assert pair["cardinal"] == "קניתי כחמישים עגבניות היום."
    alignment = pair["alignments"][0]
    assert pair["digits"][slice(*alignment["digits_span"])] == "כ-50 עגבניות"
    assert pair["cardinal"][slice(*alignment["cardinal_span"])] == "כחמישים עגבניות"


def test_optional_second_number_and_repeated_values():
    values = {"street": "הרצל", "house": 9, "apartment": 9, "include_apartment": True}
    pair = render("delivery", values)
    assert pair["digits"] == "החבילה נשלחה לרחוב הרצל 9, דירה 9"
    assert len(pair["alignments"]) == 2
    assert [pair["digits"][slice(*a["digits_span"])] for a in pair["alignments"]] == ["9", "9"]
    values["include_apartment"] = False
    values.pop("apartment")
    assert len(render("delivery", values)["alignments"]) == 1


def test_generation_is_deterministic_and_bounded():
    pairs = generate(21, 80)
    assert pairs == generate(21, 80)
    assert {pair["archetype_id"] for pair in pairs} == set(BY_ID)
    assert all(not pair["digits"].startswith("0") for pair in pairs)
    for pair in pairs:
        validate_pair(pair)
        if "house" in pair["sampled"]:
            assert 1 <= pair["sampled"]["house"] <= 99999
    with pytest.raises(ValueError):
        generate(1, 201)
    with pytest.raises(ValueError):
        generate(1, 1, [])
    with pytest.raises(ValueError):
        generate(1, True)
    with pytest.raises(ValueError):
        render("address", {"street": "הרצל", "house": 0})
    with pytest.raises(ValueError):
        render("address", {"street": "הרצל", "house": 100000})


def test_number_sampler_covers_all_digit_lengths():
    import random
    rng = random.Random(2)
    values = [sampled_number(rng, 1, 99999) for _ in range(500)]
    assert {len(str(number)) for number in values} == {1, 2, 3, 4, 5}


def test_semantic_renderers_and_spans():
    cases = (
        ("floor", {"floor": 5}, "ה-5", "החמישית"),
        ("departure", {"minute_of_day": 21 * 60 + 30}, "21:30", "תשע וחצי"),
        ("survey", {"percent": 2}, "2%", "שני אחוזים"),
        ("survey", {"percent": 1}, "1%", "אחוז אחד"),
        ("mobile", {"phone": "050-7894567"}, "050-7894567", "אפס חמש אפס, שבע שמונה תשע, ארבע חמש שש שבע"),
    )
    for archetype, values, digits, spoken in cases:
        pair = render(archetype, values)
        alignment = pair["alignments"][0]
        assert pair["digits"][slice(*alignment["digits_span"])] == digits
        assert pair["cardinal"][slice(*alignment["cardinal_span"])] == spoken
    with pytest.raises(ValueError):
        render("mobile", {"phone": "50-7894567"})


@pytest.mark.parametrize("time,spoken", [
    ("15:16", "שלוש ושש עשרה דקות"),
    ("05:14", "חמש וארבע עשרה דקות"),
    ("15:01", "שלוש ודקה"),
    ("15:02", "שלוש ושתי דקות"),
    ("15:15", "שלוש ורבע"),
    ("15:19", "שלוש ותשע עשרה דקות"),
    ("15:20", "שלוש עשרים"),
    ("15:21", "שלוש עשרים ואחת"),
    ("15:30", "שלוש וחצי"),
    ("15:45", "רבע לארבע"),
    ("23:59", "אחת עשרה חמישים ותשע"),
])
def test_reviewed_time_boundaries(time, spoken):
    hour, minute = map(int, time.split(":"))
    pair = render("departure", {"minute_of_day": hour * 60 + minute})
    assert pair["alignments"][0]["digits_text"] == time
    assert pair["alignments"][0]["cardinal_text"] == spoken
    validate_pair(pair)


def test_reviewed_phone_grouping():
    pair = render("mobile", {"phone": "050-3159268"})
    assert pair["alignments"][0]["cardinal_text"] == "אפס חמש אפס, שלוש אחת חמש, תשע שתיים שש שמונה"
    validate_pair(pair)


@pytest.mark.parametrize("archetype,values,digits,spoken", [
    ("ranking", {"rank": 3}, "ה-3", "השלישי"),
    ("age", {"age": 42}, "42", "ארבעים ושתיים"),
    ("year", {"year": 2001}, "2001", "אלפיים ואחת"),
    ("calendar", {"day": 1, "month": "ספטמבר"}, "ב-1 בספטמבר", "באחד בספטמבר"),
    ("calendar", {"day": 15, "month": "נובמבר"}, "ב-15 בנובמבר", "בחמישה עשר בנובמבר"),
    ("duration_half", {"duration": "2.5"}, "2.5 שעות", "שעתיים וחצי"),
    ("duration_half", {"duration": "3.5"}, "3.5 שעות", "שלוש וחצי שעות"),
    ("fraction", {"fraction": "3/4"}, "3/4", "שלושת רבעי"),
    ("decimal_temp", {"whole": 37, "fractional": "5"}, "37.5", "שלושים ושבע וחצי"),
    ("decimal_temp", {"whole": 37, "fractional": "25"}, "37.25", "שלושים ושבע ורבע"),
    ("decimal_temp", {"whole": 37, "fractional": "75"}, "37.75", "שלושים ושבע ושלושת רבעי"),
    ("negative_temp", {"magnitude": 4}, "-4", "מינוס ארבע"),
    ("money", {"amount": 2}, "2 ₪", "שני שקלים"),
    ("weight", {"weight": 8}, '8 ק"ג', "שמונה קילוגרמים"),
    ("card_suffix", {"suffix": "0080"}, "0080", "אפס אפס שמונה אפס"),
    ("version", {"major": 14, "minor": 2, "patch": 1}, "14.2.1", "ארבע עשרה שתיים אחת"),
    ("score", {"score": "3:0"}, "3:0", "שלוש אפס"),
    ("age_range", {"age_range": "6–12"}, "6–12", "שש עד שתים עשרה"),
    ("percent_half", {"whole_percent": 4}, "4.5%", "ארבעה וחצי אחוזים"),
    ("full_date", {"day": 14, "month": "מאי", "year": 1948}, "ל-14.5.1948", "לארבעה עשר במאי, אלף תשע מאות ארבעים ושמונה"),
    ("money_cents", {"shekels": 14, "agorot": 90}, "14.90 ₪", "ארבעה עשר שקלים ותשעים אגורות"),
    ("distance", {"kilometers": 55}, '55 ק"מ', "חמישים וחמישה קילומטרים"),
    ("section", {"section": 14, "subsection": 3}, "סעיף 14.3", "סעיף ארבע עשרה, שלוש"),
    ("postal", {"postal_code": "05812"}, "05812", "אפס חמש שמונה אחת שתיים"),
])
def test_guide_derived_archetypes(archetype, values, digits, spoken):
    pair = render(archetype, values)
    alignment = pair["alignments"][0]
    assert alignment["digits_text"] == digits
    assert alignment["cardinal_text"] == spoken
    validate_pair(pair)


@pytest.mark.parametrize("archetype,values,natural,formal", [
    ("section", {"section": 18, "subsection": 5},
     "סעיף שמונה עשרה, חמש", "סעיף שמונה עשרה, תת-סעיף חמש"),
    ("decimal_temp", {"whole": 15, "fractional": "5"},
     "חמש עשרה וחצי", "חמש עשרה נקודה חמש"),
    ("version", {"major": 3, "minor": 1, "patch": 9},
     "שלוש אחת תשע", "שלוש נקודה אחת נקודה תשע"),
    ("money_cents", {"shekels": 64, "agorot": 50},
     "שישים וארבע וחצי שקל", "שישים וארבעה שקלים וחמישים אגורות"),
    ("full_date", {"day": 20, "month": "ינואר", "year": 2026},
     "לעשרים בינואר, אלפיים עשרים ושש", "לעשרים בינואר שנת אלפיים עשרים ושש"),
    ("duration_half", {"duration": "3.5"},
     "שלוש וחצי שעות", "שלוש שעות וחצי"),
])
def test_reviewed_natural_and_dormant_formal_readings(archetype, values, natural, formal):
    ordinary = render(archetype, values)
    dormant = render(archetype, values, reading_variant="formal")
    assert ordinary["alignments"][0]["cardinal_text"] == natural
    assert dormant["alignments"][0]["cardinal_text"] == formal
    assert ordinary["digits"] == dormant["digits"]
    assert ordinary["id"] != dormant["id"]
    assert ordinary["reading_variant"] == "natural"
    assert dormant["reading_variant"] == "formal"
    validate_pair(ordinary)
    validate_pair(dormant)


def test_variant_weights_are_reproducible_and_zero_by_default(tmp_path):
    from numeric_pairs.variants import DEFAULT_FORMAL_WEIGHTS

    assert set(DEFAULT_FORMAL_WEIGHTS) == {
        "section", "decimal_temp", "version", "money_cents", "full_date",
        "duration_half", "large_shekels", "area", "numeric_calendar"}
    assert set(DEFAULT_FORMAL_WEIGHTS.values()) == {0.0}
    defaults = generate(77, 180, list(DEFAULT_FORMAL_WEIGHTS))
    assert all(pair["reading_variant"] == "natural" for pair in defaults)
    formal = generate(77, 180, list(DEFAULT_FORMAL_WEIGHTS),
                      variant_weights=dict.fromkeys(DEFAULT_FORMAL_WEIGHTS, 1.0))
    assert all(pair["reading_variant"] == "formal" for pair in formal)
    assert formal == generate(77, 180, list(DEFAULT_FORMAL_WEIGHTS),
                              variant_weights=dict.fromkeys(DEFAULT_FORMAL_WEIGHTS, 1.0))
    mixed = generate(77, 200, ["version"], variant_weights={"version": .1})
    assert 5 <= sum(pair["reading_variant"] == "formal" for pair in mixed) <= 40
    with pytest.raises(ValueError):
        generate(77, 10, variant_weights={"unknown": .5})
    with pytest.raises(ValueError):
        generate(77, 10, variant_weights={"version": 1.1})
    store = ReviewStore(tmp_path)
    natural_run = store.create_run(77, 6, ["version"])
    formal_run = store.create_run(77, 6, ["version"], variant_weights={"version": 1.0})
    assert natural_run["id"] != formal_run["id"]
    assert natural_run["variant_weights"]["version"] == 0.0
    assert formal_run["variant_weights"]["version"] == 1.0
    assert store.get_run(natural_run["id"]) == natural_run


def test_guide_coverage_and_sampling_constraints():
    from numeric_pairs.core import sampled_number
    import random
    assert len(SCENARIO_AREAS) == 10
    assert len(BY_ID) == 69
    assert {name for _, ids, _ in SCENARIO_AREAS for name in ids} == set(BY_ID)
    pairs = generate(42, min(200, len(BY_ID) * 4))
    assert {pair["archetype_id"] for pair in pairs} == set(BY_ID)
    assert {pair["sampled"]["minor"] for pair in generate(9, 200, ["version"])} >= {0, 1, 9}
    assert 0 in {sampled_number(random.Random(seed), 0, 9) for seed in range(100)}
    for archetype, values in [
        ("calendar", {"day": 29, "month": "מאי"}),
        ("ranking", {"rank": 11}),
        ("card_suffix", {"suffix": "123"}),
        ("fraction", {"fraction": "2/3"}),
        ("full_date", {"day": 31, "month": "מאי", "year": 2024}),
        ("postal", {"postal_code": "1234"}),
        ("infant_age", {"age_years": "2.5"}),
        ("decade", {"decade": 40}),
        ("stopwatch_seconds", {"seconds": 9, "hundredths": 0}),
        ("map_scale", {"scale": 25000}),
        ("pill_range", {"minimum": 4, "maximum": 4}),
        ("opening_hours", {"start_hour": 7, "end_hour": 12}),
        ("million_exact", {"number": 1000000}),
        ("million_exact", {"number": 1234560}),
        ("meeting_minute", {"minute_of_day": 9 * 60 + 30}),
        ("card_full", {"card_number": "4111111111111111"}),
        ("international_phone", {"international_phone": "+1 202-555-9999"}),
        ("civil_id", {"civil_id": "000000000"}),
        ("passport_id", {"passport_id": "AB1234567"}),
        ("bank_account", {"branch": 630, "account": "123456"}),
        ("license_plate", {"plate": "23-456-78"}),
        ("plural_millions", {"millions_value": 1_500_000}),
        ("plural_millions", {"millions_value": 2_000_001}),
        ("child_half_age", {"child_age": "1.5"}),
        ("month_end_date", {"day": 31, "month": "אפריל"}),
        ("month_end_date", {"day": 29, "month": "פברואר"}),
        ("midnight_time", {"midnight_minute": 38}),
        ("general_fraction", {"general_fraction": "1/2"}),
        ("multi_digit_decimal", {"decimal_value": "3.5"}),
        ("multi_digit_decimal", {"decimal_value": "3.140"}),
        ("airline_flight", {"carrier": "LY", "flight": 315}),
    ]:
        with pytest.raises(ValueError):
            render(archetype, values)


@pytest.mark.parametrize("archetype,values,digits,spoken", [
    ("infant_age", {"age_years": "1.5"}, "1.5", "שנה וחצי"),
    ("decade", {"decade": 90}, "בשנות ה-90", "בשנות התשעים"),
    ("stopwatch_seconds", {"seconds": 9, "hundredths": 58},
     "9.58 שניות", "תשע נקודה חמישים ושמונה שניות"),
    ("stopwatch_seconds", {"seconds": 28, "hundredths": 10},
     "28.10 שניות", "עשרים ושמונה נקודה אחת שניות"),
    ("stopwatch_seconds", {"seconds": 28, "hundredths": 12},
     "28.12 שניות", "עשרים ושמונה נקודה שתים עשרה שניות"),
    ("area", {"square_meters": 100}, '100 מ"ר', "מאה מטר רבוע"),
    ("map_scale", {"scale": 100000}, "1:100,000", "אחד למאה אלף"),
    ("maximum_attendees", {"capacity": 50}, "50", "חמישים"),
    ("pill_range", {"minimum": 2, "maximum": 4}, "2-4", "בין שתיים לארבע"),
    ("opening_hours", {"start_hour": 8, "end_hour": 12}, "8:00–12:00", "שמונה לשתים עשרה"),
    ("dollar_price", {"dollars": 35}, "$35", "שלושים וחמישה דולר"),
])
def test_new_pending_guide_subcases(archetype, values, digits, spoken):
    pair = render(archetype, values)
    assert pair["alignments"][0]["digits_text"] == digits
    assert pair["alignments"][0]["cardinal_text"] == spoken
    validate_pair(pair)


@pytest.mark.parametrize("archetype,values,digits,spoken", [
    ("million_exact", {"number": 1234567}, "1,234,567", "מיליון, מאתיים שלושים וארבעה אלף, חמש מאות שישים ושבע"),
    ("meeting_minute", {"minute_of_day": 9 * 60 + 7}, "ב-09:07", "בתשע ושבע דקות"),
    ("card_full", {"card_number": "0000123400567891"}, "0000-1234-0056-7891", "אפס אפס אפס אפס, אחת שתיים שלוש ארבע, אפס אפס חמש שש, שבע שמונה תשע אחת"),
    ("international_phone", {"international_phone": "+1 202-555-0142"}, "+1 202-555-0142", "פלוס אחת, שתיים אפס שתיים, חמש חמש חמש, אפס אחת ארבע שתיים"),
    ("civil_id", {"civil_id": "000934040"}, "000934040", "אפס אפס אפס, תשע שלוש ארבע, אפס ארבע אפס"),
    ("passport_id", {"passport_id": "XX1234567"}, "XX1234567", "איקס איקס אחת שתיים שלוש ארבע חמש שש שבע"),
    ("stopwatch_minute", {"minutes": 1, "seconds": 46, "hundredths": 30}, "1:46.30", "דקה אחת, ארבעים ושש שניות ושלושים מאיות"),
    ("euro_price", {"euros": 35}, "35 €", "שלושים וחמישה אירו"),
    ("data_plan", {"gigabytes": 100, "megabits": 1000}, "100GB במהירות 1000Mb", "מאה ג'יגה-בייט במהירות אלף מגה ביט"),
    ("bank_account", {"branch": 630, "account": "000802"}, "לסניף 630, חשבון 000802", "לסניף שש מאות ושלושים, חשבון אפס אפס אפס, שמונה אפס שתיים"),
    ("license_plate", {"plate": "00-456-78"}, "00-456-78", "אפס אפס, ארבע חמש שש, שבע שמונה"),
    ("flight_number", {"flight": 481}, "LY481", "אל ואיי ארבע שמונה אחת"),
    ("numeric_calendar", {"day": 23, "month_number": 8}, "ב-23.8", "בעשרים ושלוש לשמיני"),
    ("slash_address", {"street": "הרצל", "house": 54, "apartment": 9}, "הרצל 54/9", "הרצל חמישים וארבע, דירה תשע"),
    ("minimum_age", {"minimum_age": 21}, "21", "עשרים ואחת"),
    ("maximum_attendees", {"capacity": 143}, "143", "מאה ארבעים ושלושה"),
    ("maximum_attendees", {"capacity": 120}, "120", "מאה ועשרים"),
    ("maximum_attendees", {"capacity": 115}, "115", "מאה וחמישה עשר"),
    ("area", {"square_meters": 183}, '183 מ"ר', "מאה שמונים ושלושה מטר רבוע"),
    ("large_shekels", {"shekels_large": 125001}, "125,001 ₪", "מאה עשרים וחמישה אלף ואחד שקלים"),
    ("large_shekels", {"shekels_large": 131775}, "131,775 ₪", "מאה שלושים ואחד אלף שבע מאות שבעים וחמישה שקל"),
    ("explicit_hundredths", {"seconds": 2, "hundredths": 80}, "2 שניות ו-80 מאיות", "שתי שניות ושמונים מאיות"),
    ("explicit_hundredths", {"seconds": 28, "hundredths": 10}, "28 שניות ו-10 מאיות", "עשרים ושמונה שניות ועשר מאיות"),
    ("slash_date", {"day": 14, "month": "מאי", "year": 1948}, "ל-14/5/1948", "לארבעה עשר במאי, אלף תשע מאות ארבעים ושמונה"),
    ("full_date", {"day": 28, "month": "אוקטובר", "year": 2024}, "ל-28.10.2024", "לעשרים ושמונה באוקטובר, אלפיים עשרים וארבע"),
    ("plural_millions", {"millions_value": 2_000_000}, "2,000,000", "שני מיליון"),
    ("plural_millions", {"millions_value": 2_500_000}, "2,500,000", "שני מיליון וחמש מאות אלף"),
    ("plural_millions", {"millions_value": 3_750_000}, "3,750,000", "שלושה מיליון, שבע מאות וחמישים אלף"),
    ("child_half_age", {"child_age": "2.5"}, "2.5", "שנתיים וחצי"),
    ("child_half_age", {"child_age": "4.5"}, "4.5", "ארבע וחצי"),
    ("month_end_date", {"day": 29, "month": "מאי"}, "ב-29 במאי", "בעשרים ותשעה במאי"),
    ("month_end_date", {"day": 30, "month": "אפריל"}, "ב-30 באפריל", "בשלושים באפריל"),
    ("month_end_date", {"day": 31, "month": "דצמבר"}, "ב-31 בדצמבר", "בשלושים ואחד בדצמבר"),
    ("midnight_time", {"midnight_minute": 0}, "ב-00:00", "בחצות"),
    ("midnight_time", {"midnight_minute": 1}, "ב-00:01", "בחצות ודקה"),
    ("midnight_time", {"midnight_minute": 2}, "ב-00:02", "בחצות ושתי דקות"),
    ("midnight_time", {"midnight_minute": 15}, "ב-00:15", "בחצות ורבע"),
    ("midnight_time", {"midnight_minute": 20}, "ב-00:20", "בחצות ועשרים"),
    ("midnight_time", {"midnight_minute": 30}, "ב-00:30", "בחצות וחצי"),
    ("general_fraction", {"general_fraction": "1/3"}, "1/3", "שליש"),
    ("general_fraction", {"general_fraction": "2/3"}, "2/3", "שני שלישים"),
    ("general_fraction", {"general_fraction": "2/5"}, "2/5", "שתי חמישיות"),
    ("general_fraction", {"general_fraction": "3/8"}, "3/8", "שלוש שמיניות"),
    ("multi_digit_decimal", {"decimal_value": "0.08"}, "0.08", "אפס נקודה אפס שמונה"),
    ("multi_digit_decimal", {"decimal_value": "1.375"}, "1.375", "אחת נקודה שלוש שבע חמש"),
    ("airline_flight", {"carrier": "LH", "flight": 687}, "LH687", "אל אייץ' שש שמונה שבע"),
    ("airline_flight", {"carrier": "BA", "flight": 165}, "BA165", "בי איי אחת שש חמש"),
])
def test_extended_guide_and_long_identifier_spans(archetype, values, digits, spoken):
    pair = render(archetype, values)
    assert pair["alignments"][0]["digits_text"] == digits
    assert pair["alignments"][0]["cardinal_text"] == spoken
    validate_pair(pair)


def test_exact_millions_and_synthetic_identifiers_across_seeds():
    from numeric_pairs.core import valid_civil_id

    archetypes = ["million_exact", "meeting_minute", "card_full", "international_phone", "civil_id",
                  "passport_id", "stopwatch_minute", "bank_account", "license_plate"]
    for seed in range(20):
        pairs = {p["archetype_id"]: p for p in generate(seed, len(archetypes), archetypes)}
        million = pairs["million_exact"]["sampled"]["number"]
        assert 1_000_000 < million < 2_000_000 and million % 10 != 0
        assert pairs["meeting_minute"]["sampled"]["minute_of_day"] % 60 not in (0, 15, 30, 45)
        assert pairs["card_full"]["sampled"]["card_number"].startswith("0000")
        assert pairs["international_phone"]["sampled"]["international_phone"].startswith("+1 202-555-01")
        assert not valid_civil_id(pairs["civil_id"]["sampled"]["civil_id"])
        assert pairs["passport_id"]["sampled"]["passport_id"].startswith("XX")
        assert pairs["bank_account"]["sampled"]["account"].startswith("000")
        assert pairs["license_plate"]["sampled"]["plate"].startswith("00-")


def test_every_archetype_has_reusable_contexts_and_exact_alignments():
    import random

    from numeric_pairs.catalog import ARCHETYPES
    from numeric_pairs.contexts import CONTEXTS, CONTINUATIONS
    from numeric_pairs.core import sample

    assert set(CONTEXTS) == {item.id for item in ARCHETYPES}
    assert set(CONTINUATIONS) == set(CONTEXTS)
    for item in ARCHETYPES:
        bank = CONTEXTS[item.id]
        assert len(set(bank.starts)) >= 2
        assert len(set(bank.ends)) >= 3
        seen = set()
        sampled_values = []
        for seed in range(100):
            values = sample(item.id, random.Random(seed))
            numeric = tuple(a["digits_text"] for a in render(item.id, values)["alignments"])
            if all(numeric != previous for _, previous in sampled_values):
                sampled_values.append((values, numeric))
            if len(sampled_values) == 2:
                break
        for values, numeric in sampled_values:
            for start in range(len(bank.starts)):
                for end in range(len(bank.ends)):
                    pair = render(item.id, values, context=(start, end))
                    validate_pair(pair)
                    assert tuple(a["digits_text"] for a in pair["alignments"]) == numeric
                    assert pair["digits"].startswith(bank.starts[start])
                    assert pair["digits"].endswith(bank.ends[end])
                    assert pair["cardinal"].startswith(bank.starts[start])
                    assert pair["cardinal"].endswith(bank.ends[end])
                    seen.add(pair["digits"])
        assert len(seen) >= 10, (item.id, len(seen))


def test_context_selection_is_deterministic_and_cannot_mutate_numeric_readings():
    import random

    from numeric_pairs.core import sample

    archetypes = ["delivery", "road_route", "million_exact", "card_full", "meeting_minute"]
    for item in archetypes:
        values = sample(item, random.Random(11))
        original = render(item, values)
        contextual = render(item, values, context=(1, 1))
        assert original["id"] != contextual["id"]
        assert [(a["digits_text"], a["cardinal_text"], a["reading"]) for a in original["alignments"]] == [
            (a["digits_text"], a["cardinal_text"], a["reading"]) for a in contextual["alignments"]]
        validate_pair(contextual)
    for invalid in [(-1, 0), (0, 999), (True, 0), (0,), ("1", 0)]:
        with pytest.raises(ValueError, match="context"):
            render("address", {"street": "הרצל", "house": 42}, context=invalid)
    assert generate(23, 56) == generate(23, 56)
    assert all("context" in pair for pair in generate(23, 56))
    for include_apartment in (False, True):
        values = {"street": "הרצל", "house": 42, "include_apartment": include_apartment}
        if include_apartment:
            values["apartment"] = 5
        pair = render("delivery", values, context=(0, 2))
        assert len(pair["alignments"]) == 1 + include_apartment
        assert pair["digits"].endswith(" במהלך השבוע.")
        validate_pair(pair)


def test_longer_sentence_mix_preserves_readings_and_spans():
    import random

    from numeric_pairs.catalog import ARCHETYPES
    from numeric_pairs.contexts import CLAUSE_GROUPS, CONTINUATIONS
    from numeric_pairs.core import sample

    assert sum(len(names) for names, _, _ in CLAUSE_GROUPS) == len(CONTINUATIONS) == len(ARCHETYPES)
    for archetype in ARCHETYPES:
        values = sample(archetype.id, random.Random(31))
        original = render(archetype.id, values, context=(0, 0), continuation=0)
        for option in (1, 2):
            extended = render(archetype.id, values, context=(0, 0), continuation=option)
            assert extended["digits"].endswith(CONTINUATIONS[archetype.id][option] + ".")
            assert len(extended["digits"].split()) > len(original["digits"].split())
            assert [(a["digits_text"], a["cardinal_text"]) for a in extended["alignments"]] == [
                (a["digits_text"], a["cardinal_text"]) for a in original["alignments"]]
            validate_pair(extended)
    with pytest.raises(ValueError, match="continuation"):
        render("address", {"street": "הרצל", "house": 42}, context=(0, 0), continuation=3)
    with pytest.raises(ValueError, match="continuation"):
        render("address", {"street": "הרצל", "house": 42}, continuation=1)
    samples = [pair for seed in range(30) for pair in generate(seed, len(ARCHETYPES))]
    counts = [len(pair["digits"].split()) for pair in samples]
    assert min(counts) < 10
    assert sum(10 <= n < 18 for n in counts) / len(counts) >= 0.25
    assert sum(n >= 18 for n in counts) / len(counts) >= 0.10


def test_new_batch_generation_and_historical_feedback(tmp_path):
    from numeric_pairs.catalog import ARCHETYPES
    from numeric_pairs.core import RENDERER_VERSION

    first = generate(15, len(ARCHETYPES))
    assert first == generate(15, len(ARCHETYPES))
    assert len({pair["archetype_id"] for pair in first}) == len(ARCHETYPES)
    assert {pair["renderer_version"] for pair in first} == {RENDERER_VERSION}
    store = ReviewStore(tmp_path)
    run = store.create_run(15, len(ARCHETYPES))
    assert {pair["archetype_id"] for pair in run["pairs"]} == set(BY_ID)
    assert run["pairs"] == first


def test_address_sampling_controls_and_coverage_defaults():
    pairs = generate(8, 40, ["address"], address_lengths=(5,), boundary_weight=1)
    assert all(len(str(pair["sampled"]["house"])) == 5 for pair in pairs)
    assert pairs != generate(8, 40, ["address"], address_lengths=(5,), boundary_weight=0)
    assert summarize(pairs, {})["valid"] == 40
    assert summarize(pairs, {})["implicit_valid"] == 40
    feedback = {pairs[0]["id"]: {"verdict": "reject"}, pairs[1]["id"]: {"verdict": "correct"},
                pairs[2]["id"]: {"verdict": "accept"}}
    coverage = summarize(pairs, feedback)
    assert (coverage["valid"], coverage["rejected"], coverage["needs_correction"], coverage["explicit_valid"]) == (38, 1, 1, 1)
    assert coverage["digit_lengths"] == {"cardinal:5": 40}
    assert not coverage["qa_failures"]
    with pytest.raises(ValueError):
        generate(8, 2, ["address"], address_lengths=())



def test_review_run_and_append_only_feedback(tmp_path):
    store = ReviewStore(tmp_path)
    run = store.create_run(17, 2, ["address"])
    assert store.create_run(17, 2, ["address"]) == run
    assert store.get_run(run["id"]) == run
    assert store.get_run("../feedback.jsonl") is None
    pair_id = run["pairs"][0]["id"]
    store.save_feedback(run["id"], pair_id, "reject", "לא טבעי")
    assert store.coverage(run["id"])["valid"] == 1
    store.save_feedback(run["id"], pair_id, "correct", "עדיף אחרת")
    assert store.feedback(run["id"])[pair_id]["verdict"] == "correct"
    assert len((tmp_path / "feedback.jsonl").read_text().splitlines()) == 2
    with pytest.raises(ValueError):
        store.save_feedback(run["id"], "missing", "accept", "")
    with pytest.raises(ValueError):
        store.save_feedback(run["id"], pair_id, "correct", "")
    assert json.loads((tmp_path / f"run-{run['id']}.json").read_text())["id"] == run["id"]


def test_never_ran_uses_generated_pairs_across_all_saved_runs(tmp_path):
    store = ReviewStore(tmp_path)
    assert store.never_ran_archetypes() == list(BY_ID)
    first = store.create_run(3, 1, ["stopwatch_seconds", "pill_range"])
    sampled = first["pairs"][0]["archetype_id"]
    assert sampled not in store.never_ran_archetypes()
    assert (set(["stopwatch_seconds", "pill_range"]) - {sampled}).issubset(store.never_ran_archetypes())
    store.save_feedback(first["id"], first["pairs"][0]["id"], "correct", "הקריאה הטבעית שונה")
    for seed in range(31):
        store.create_run(1000 + seed, 1, ["age"])
    assert len(store.list_runs()) == 30
    assert sampled not in store.never_ran_archetypes()
    assert "age" not in store.never_ran_archetypes()
    assert store.feedback(first["id"])[first["pairs"][0]["id"]]["verdict"] == "correct"


def test_corpus_candidates_require_rights_and_human_review(tmp_path):
    store = CandidateStore(tmp_path)
    text = "הרכבת יוצאת בשעה 15:16.\nהרכבת יוצאת בשעה 05:14.\nחייגו 050-3159268 או כתבו ל-test@example.com"
    with pytest.raises(ValueError):
        store.ingest(sentences=text, source="source", license="CC BY", restrictions="",
                     approved_for_derivation=False)
    proposed = store.ingest(sentences=text, source="source", license="CC BY", restrictions="credit required",
                            approved_for_derivation=True)
    assert len(proposed) == 1
    item = store.list()[0]
    assert item["count"] == 2
    assert item["kind"] == "time"
    assert item["status"] == "pending"
    assert "{NUM}" in item["pattern"]
    assert "050-3159268" not in (tmp_path / "candidates.json").read_text()
    with pytest.raises(ValueError):
        store.review(item["id"], status="approved", grammar="", slots="", safe_ranges="",
                     written_policy="", spoken_policy="", note="")
    approved = store.review(item["id"], status="approved", grammar="שעת יציאה", slots="time",
                            safe_ranges="00:00–23:59", written_policy="HH:MM",
                            spoken_policy="שעה ודקות", note="validated")
    assert approved["status"] == "approved"
    assert CandidateStore(tmp_path).list()[0]["review"]["slots"] == "time"
    assert extract("חייגו 050-3159268")== []
    store.ingest(sentences="הפגישה בשעה 09:20.", source="held out", license="CC BY", restrictions="",
                 approved_for_derivation=True, purpose="evaluation")
    assert len(store.list()) == 1
    assert "09:20" not in (tmp_path / "held-out-evaluation.json").read_text()


def test_export_is_versioned_reproducible_and_holds_out_families(tmp_path):
    store = ReviewStore(tmp_path)
    run = store.create_run(10, 80)
    first, second = run["pairs"][:2]
    feedback = {first["id"]: {"verdict": "reject"}, second["id"]: {"verdict": "correct"}}
    manifest, splits = build_export(run, feedback)
    assert manifest["exported"] == 78
    assert manifest["verdicts"]["implicit_valid"] == 78
    assert all(manifest["quality_gates"].values())
    assert all(splits.values())
    assert not {first["id"], second["id"]} & {row["id"] for rows in splits.values() for row in rows}
    families = [{BY_ID[row["archetype_id"]].category for row in rows} for rows in splits.values()]
    assert not any(a & b for i, a in enumerate(families) for b in families[i + 1:])
    saved = save_export(tmp_path, run, feedback)
    assert saved == save_export(tmp_path, run, feedback)
    folder = tmp_path / "exports" / saved["id"]
    assert json.loads((folder / "manifest.json").read_text()) == manifest
    assert sum(len((folder / f"{name}.jsonl").read_text().splitlines()) for name in splits) == 78
    with pytest.raises(ValueError, match="three valid category"):
        build_export(store.create_run(9, 10, ["address"]), {})
    broken = json.loads(json.dumps(run))
    broken["pairs"][2]["alignments"][0]["digits_span"] = [0, 1]
    with pytest.raises(ValueError):
        build_export(broken, feedback)


def test_standalone_core_with_replaced_spoken_adapter(tmp_path):
    package = tmp_path / "numeric_pairs"
    shutil.copytree(Path(__file__).resolve().parents[1] / "numeric_pairs", package,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (package / "adapter.py").write_text(
        "def cardinal(value, gender, *, construct=False): return 'מילה'\n"
        "def ordinal_feminine(value): return 'ראשונה'\n"
        "def ordinal_masculine(value): return 'ראשון'\n"
        "def clock_time(hour, minute): return 'שעה'\n", encoding="utf-8")
    result = subprocess.run([sys.executable, "-c",
                             "from numeric_pairs.core import render; print(render('address', {'street':'הרצל','house':5})['cardinal'])"],
                            cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(tmp_path)},
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "המשרד ממוקם ברחוב הרצל מילה"


def test_web_generation_review_and_validation(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from numeric_pairs.web import app as web

    monkeypatch.setattr(web, "store", ReviewStore(tmp_path))
    monkeypatch.setattr(web, "candidate_store", CandidateStore(tmp_path))
    client = TestClient(web.app)
    assert client.get("/").status_code == 200
    assert client.get("/api/catalog").json()["catalog_version"] == "starter-19"
    assert client.get("/api/archetypes/not-real/design").status_code == 404
    for archetype_id in BY_ID:
        design = client.get(f"/api/archetypes/{archetype_id}/design")
        assert design.status_code == 200
        data = design.json()
        assert data["id"] == archetype_id
        assert data["template"] and data["sampling"] and data["starts"] and data["ends"]
        assert [example["length"] for example in data["examples"]] == ["קצר", "בינוני", "ארוך"]
        assert [len(example["digits"].split()) for example in data["examples"]] == sorted(
            len(example["digits"].split()) for example in data["examples"])
        assert all(not any(char.isdigit() for char in example["cardinal"]) for example in data["examples"])
        assert all(example["alignments"] for example in data["examples"])
        assert all(a["written"] in example["digits"] and a["spoken"] in example["cardinal"]
                   for example in data["examples"] for a in example["alignments"])
    assert client.get("/api/archetypes/delivery/design").json()["template"].count("include_apartment") == 1
    assert client.get("/api/archetypes/purchase/design").json()["sampling"][0]["values"][0]["gender"] in {"m", "f"}
    assert client.get("/api/archetypes/card_full/design").json()["sampling"][0]["rule"].find("0000") >= 0
    assert list(tmp_path.iterdir()) == []
    assert set(client.get("/api/archetypes/never-ran").json()["archetypes"]) == set(BY_ID)
    assert client.get("/api/catalog").json()["default_formal_weights"]["version"] == 0.0
    assert len(client.get("/api/catalog").json()["scenario_areas"]) == 10
    assert client.post("/api/runs", json={"seed": 5, "count": 2, "archetypes": ["address"]}).status_code == 200
    run = client.post("/api/runs", json={"seed": 5, "count": 2, "archetypes": ["address"]}).json()
    assert "address" not in client.get("/api/archetypes/never-ran").json()["archetypes"]
    assert client.get(f"/api/runs/{run['id']}").json()["pairs"] == run["pairs"]
    assert client.get(f"/api/runs/{run['id']}/coverage").json()["implicit_valid"] == 2
    assert client.post("/api/runs", json={"seed": 5, "count": 0}).status_code == 422
    assert client.post("/api/runs", json={"seed": 5, "count": 2, "archetypes": []}).status_code == 422
    assert client.post("/api/runs", json={"seed": 5, "count": 2, "variant_weights": {"version": 2}}).status_code == 422
    assert all(pair["reading_variant"] == "formal" for pair in client.post("/api/runs", json={
        "seed": 5, "count": 3, "archetypes": ["version"], "variant_weights": {"version": 1.0}}).json()["pairs"])
    assert client.get("/api/runs/not-a-run").status_code == 404
    response = client.post(f"/api/runs/{run['id']}/feedback", json={
        "pair_id": run["pairs"][0]["id"], "verdict": "accept", "note": "תקין"})
    assert response.status_code == 200
    assert client.get(f"/api/runs/{run['id']}").json()["feedback"][run["pairs"][0]["id"]]["verdict"] == "accept"
    assert client.get(f"/api/runs/{run['id']}/coverage").json()["valid"] == 2
    assert client.get("/api/candidates").json() == []
    corpus = {"sentences": "הרכבת יוצאת בשעה 15:16.", "source": "test", "license": "CC BY",
              "restrictions": "", "approved_for_derivation": True}
    imported = client.post("/api/candidates/import", json=corpus)
    assert imported.status_code == 200
    candidate_id = imported.json()[0]["id"]
    assert client.post(f"/api/candidates/{candidate_id}/review", json={"status": "approved"}).status_code == 422
    review = {"status": "approved", "grammar": "time", "slots": "hour, minute",
              "safe_ranges": "00:00–23:59", "written_policy": "HH:MM", "spoken_policy": "clock"}
    assert client.post(f"/api/candidates/{candidate_id}/review", json=review).json()["status"] == "approved"
    assert client.get("/api/candidates").json()[0]["status"] == "approved"
    assert client.post(f"/api/runs/{run['id']}/export").status_code == 422
    bigger = client.post("/api/runs", json={"seed": 8, "count": 32}).json()
    exported = client.post(f"/api/runs/{bigger['id']}/export").json()
    assert exported["manifest"]["exported"] == 32
    assert client.get(f"/api/exports/{exported['id']}/train.jsonl").status_code == 200
    assert client.get(f"/api/exports/{exported['id']}/../feedback.jsonl").status_code == 404
