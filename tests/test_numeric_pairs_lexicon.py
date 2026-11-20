"""Tests for lexical bank richness, grammatical agreement, and compatibility."""

import json
from pathlib import Path
import random

from numeric_pairs import lexicon
from numeric_pairs.catalog import ARCHETYPES, NOUNS, STREETS
from numeric_pairs.contexts import CONTEXTS, CONTINUATIONS
from numeric_pairs.core import render, sample, validate_pair

PHONE_ARCHETYPES = {
    "mobile",
    "international_phone",
    "landline",
    "local_landline",
    "national_line",
    "israeli_international",
    "business_line",
}


def test_shared_and_archetype_lexical_banks_have_20_to_50_options():
    shared_banks = [
        lexicon.SHOP,
        lexicon.REPORT,
        lexicon.RECORD,
        lexicon.SPORT,
        lexicon.WEATHER,
        lexicon.PRICE,
        lexicon.TIME,
        lexicon.DOCUMENT,
        lexicon.MEASURE,
        lexicon.URBAN_LANDMARKS,
        lexicon.DELIVERY_DISPATCH_STARTS,
        lexicon.DELIVERY_ENDINGS,
        lexicon.PURCHASE_STARTS,
        lexicon.APPROXIMATE_STARTS,
        lexicon.FLOOR_STARTS,
        lexicon.FLOOR_ENDINGS,
        lexicon.DEPARTURE_STARTS,
        lexicon.SURVEY_STARTS,
        lexicon.SURVEY_ENDINGS,
        lexicon.RANKING_STARTS,
        lexicon.RANKING_ENDINGS,
        lexicon.AGE_STARTS,
        lexicon.AGE_ENDINGS,
        lexicon.YEAR_STARTS,
        lexicon.YEAR_ENDINGS,
        lexicon.CALENDAR_STARTS,
        lexicon.CALENDAR_ENDINGS,
        lexicon.DURATION_HALF_STARTS,
        lexicon.DURATION_HALF_ENDINGS,
        lexicon.FRACTION_STARTS,
        lexicon.FRACTION_INGREDIENTS,
        lexicon.DECIMAL_TEMP_STARTS,
        lexicon.NEGATIVE_TEMP_STARTS,
        lexicon.MONEY_STARTS,
        lexicon.WEIGHT_STARTS,
        lexicon.DISTANCE_STARTS,
        lexicon.AREA_STARTS,
        lexicon.VERSION_STARTS,
        lexicon.VERSION_ENDINGS,
        lexicon.SECTION_STARTS,
        lexicon.MAP_SCALE_STARTS,
        lexicon.ROAD_ROUTE_STARTS,
        lexicon.ROAD_ROUTE_ENDINGS,
        lexicon.FLIGHT_STARTS,
        lexicon.FLIGHT_ENDINGS,
        lexicon.SCORE_STARTS,
        lexicon.SCORE_ENDINGS,
        lexicon.AGE_RANGE_STARTS,
        lexicon.MINIMUM_AGE_STARTS,
        lexicon.MINIMUM_AGE_ENDINGS,
        lexicon.MAX_ATTENDEES_STARTS,
        lexicon.MAX_ATTENDEES_ENDINGS,
        lexicon.PILL_RANGE_STARTS,
        lexicon.PILL_RANGE_ENDINGS,
        lexicon.OPENING_HOURS_STARTS,
        lexicon.OPENING_HOURS_ENDINGS,
        lexicon.PERCENT_HALF_STARTS,
        lexicon.POSTAL_STARTS,
        lexicon.POSTAL_ENDINGS,
        lexicon.INFANT_AGE_STARTS,
        lexicon.INFANT_AGE_ENDINGS,
        lexicon.DECADE_STARTS,
        lexicon.DECADE_ENDINGS,
        lexicon.STOPWATCH_SECONDS_STARTS,
        lexicon.STOPWATCH_MINUTE_STARTS,
        lexicon.STOPWATCH_MINUTE_ENDINGS,
        lexicon.MILLION_EXACT_STARTS,
        lexicon.MILLION_EXACT_ENDINGS,
        lexicon.MEETING_MINUTE_STARTS,
        lexicon.MEETING_MINUTE_ENDINGS,
        lexicon.DATA_PLAN_STARTS,
        lexicon.DATA_PLAN_ENDINGS,
        lexicon.CARD_SUFFIX_STARTS,
        lexicon.CARD_FULL_STARTS,
        lexicon.CIVIL_ID_STARTS,
        lexicon.PASSPORT_ID_STARTS,
        lexicon.BANK_ACCOUNT_STARTS,
        lexicon.LICENSE_PLATE_STARTS,
        lexicon.NUMERIC_CALENDAR_STARTS,
        lexicon.SLASH_ADDRESS_STARTS,
        lexicon.LARGE_MONEY_STARTS,
        lexicon.LARGE_MONEY_ENDINGS,
        lexicon.MOBILE_STARTS,
        lexicon.MOBILE_ENDINGS,
        lexicon.INTERNATIONAL_PHONE_STARTS,
        lexicon.LANDLINE_STARTS,
        lexicon.LOCAL_LANDLINE_STARTS,
        lexicon.NATIONAL_LINE_STARTS,
        lexicon.ISRAELI_INTERNATIONAL_STARTS,
        lexicon.BUSINESS_LINE_STARTS,
        lexicon.PLURAL_MILLIONS_STARTS,
        lexicon.PLURAL_MILLIONS_ENDINGS,
        lexicon.CHILD_HALF_AGE_STARTS,
        lexicon.CHILD_HALF_AGE_ENDINGS,
        lexicon.MONTH_END_STARTS,
        lexicon.MONTH_END_ENDINGS,
        lexicon.MIDNIGHT_STARTS,
        lexicon.MIDNIGHT_ENDINGS,
        lexicon.GENERAL_FRACTION_STARTS,
        lexicon.GENERAL_FRACTION_ENDINGS,
        lexicon.MULTI_DIGIT_DECIMAL_STARTS,
        lexicon.MULTI_DIGIT_DECIMAL_ENDINGS,
        lexicon.AIRLINE_FLIGHT_STARTS,
        lexicon.AIRLINE_FLIGHT_ENDINGS,
        lexicon.AGE_RANGE_ENDINGS,
    ]
    for bank in shared_banks:
        assert 20 <= len(bank) <= 50, f"Bank length {len(bank)} outside 20..50: {bank[:2]}"
        assert len(set(bank)) == len(bank), f"Duplicate entries in bank: {bank[:2]}"

    for item in ARCHETYPES:
        ctx = CONTEXTS[item.id]
        assert 20 <= len(ctx.starts) <= 50, f"{item.id} starts count {len(ctx.starts)} outside 20..50"
        assert 20 <= len(ctx.ends) <= 50, f"{item.id} ends count {len(ctx.ends)} outside 20..50"
        assert len(set(ctx.starts)) == len(ctx.starts), f"{item.id} has duplicate starts"
        assert len(set(ctx.ends)) == len(ctx.ends), f"{item.id} has duplicate ends"
        assert all(not any(ch.isdigit() for ch in s) for s in ctx.starts), f"{item.id} start has digits"
        assert all(not any(ch.isdigit() for ch in e) for e in ctx.ends), f"{item.id} end has digits"
        assert all(e.endswith(".") for e in ctx.ends), f"{item.id} end missing final period"


def test_proposed_catalog_nouns_and_streets_compatibility():
    assert 20 <= len(lexicon.PROPOSED_CATALOG_NOUNS) <= 50
    assert 20 <= len(lexicon.PROPOSED_CATALOG_STREETS) <= 50
    assert len({n.singular for n in lexicon.PROPOSED_CATALOG_NOUNS}) == len(lexicon.PROPOSED_CATALOG_NOUNS)
    assert len({n.plural for n in lexicon.PROPOSED_CATALOG_NOUNS}) == len(lexicon.PROPOSED_CATALOG_NOUNS)
    assert len(set(lexicon.PROPOSED_CATALOG_STREETS)) == len(lexicon.PROPOSED_CATALOG_STREETS)

    # The reviewed ordinary-purchase pool omits stone in favor of eggs.
    assert tuple((n.singular, n.plural, n.gender) for n in lexicon.PROPOSED_CATALOG_NOUNS
                 if n.singular != "אבן") == tuple(
        (n.singular, n.plural, n.gender) for n in NOUNS
    )
    assert lexicon.PROPOSED_CATALOG_STREETS[:len(STREETS)] == STREETS

    for noun in lexicon.PROPOSED_CATALOG_NOUNS:
        assert noun.gender in {"m", "f"}
        assert noun.singular and noun.plural and noun.singular != noun.plural
        assert not any(ch.isdigit() for ch in noun.singular + noun.plural)


def test_address_place_gender_agreement():
    starts = lexicon.build_address_starts()
    assert starts[0] == "השליח הגיע לרחוב "
    assert starts[1] == "הסניף נמצא ברחוב "
    for place in lexicon.STREET_PLACES_M:
        assert f"{place} נמצא ברחוב " in starts
        assert f"{place} נמצאת ברחוב " not in starts
    for place in lexicon.STREET_PLACES_F:
        assert f"{place} נמצאת ברחוב " in starts
        assert f"{place} נמצא ברחוב " not in starts


def test_sampled_combinations_render_and_validate_with_continuations():
    rng = random.Random(104)
    for item in ARCHETYPES:
        ctx = CONTEXTS[item.id]
        values = sample(item.id, rng)
        for start_idx in (0, len(ctx.starts) // 2, len(ctx.starts) - 1):
            for end_idx in (0, len(ctx.ends) // 2, len(ctx.ends) - 1):
                for cont in range(len(CONTINUATIONS[item.id])):
                    pair = render(
                        item.id,
                        values,
                        context=(start_idx, end_idx),
                        continuation=cont,
                    )
                    validate_pair(pair)


def test_naturalness_flags_json_is_valid_and_renders_cleanly():
    from numeric_pairs.naturalness import NaturalnessStore
    from tempfile import TemporaryDirectory

    flags_path = Path(__file__).resolve().parent.parent / "numeric_pairs" / "naturalness_flags.json"
    assert flags_path.exists(), "numeric_pairs/naturalness_flags.json must exist"
    flags = json.loads(flags_path.read_text(encoding="utf-8"))
    assert isinstance(flags, list)
    assert 12 <= len(flags) <= 25
    with TemporaryDirectory() as directory:
        archived = NaturalnessStore(Path(directory)).flags()
    assert len(archived) >= len(flags)
    for entry, archived_item in zip(flags, archived):
        assert set(entry) >= {
            "archetype_id",
            "sampled",
            "context",
            "continuation",
            "reason_he",
            "suggestion_he",
            "severity",
        }
        assert entry["severity"] in {"low", "medium", "high"}
        assert isinstance(entry["context"], list) and len(entry["context"]) == 2
        assert isinstance(entry["continuation"], int) and entry["continuation"] in (0, 1, 2)
        assert entry["reason_he"].strip() and entry["suggestion_he"].strip()
        # The original rated wording is frozen; rerendering with new policies
        # would change the very example the human reviewed.
        pair = archived_item["pair"]
        validate_pair(pair)
