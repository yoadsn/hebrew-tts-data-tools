"""Compatibility rules implement rated feedback without altering reviewed pairs."""

import json
from pathlib import Path
import random

from numeric_pairs import lexicon
from numeric_pairs.catalog import ARCHETYPES, BY_ID, CATALOG_VERSION, NOUNS, PURCHASE_BUCKETS, PURCHASE_LIMITS
from numeric_pairs.contexts import CONTEXTS, RECORD, compatible_frames, frame_groups
from numeric_pairs.core import RENDERER_VERSION, generate, render, sample, validate_pair
from numeric_pairs.inspection import describe
from numeric_pairs.naturalness import (
    ROUND_ONE_SNAPSHOTS,
    ROUND_TWO_SNAPSHOTS,
    ROUND_THREE_FLAGS,
    ROUND_THREE_SNAPSHOTS,
    NaturalnessStore,
)


def test_versions_bumped_for_round_three_revisions():
    assert CATALOG_VERSION == "starter-19"
    assert RENDERER_VERSION == "19"


def test_round_two_ratings_are_frozen(tmp_path):
    frozen = json.loads(ROUND_TWO_SNAPSHOTS.read_text(encoding="utf-8"))
    items = NaturalnessStore(tmp_path).flags()[24:44]
    assert len(items) == 20
    assert all(item["round"] == 2 and item["pair"] == frozen[item["id"]]
               for item in items)
    for item in items:
        validate_pair(item["pair"])
    # These exact contexts were approved, even though the other findings
    # share their archetype.
    for position in (7, 9, 16):
        item = items[position - 1]
        pair = item["pair"]
        values = pair["sampled"]
        frame = (pair["context"]["start"], pair["context"]["end"], pair["continuation"])
        assert frame in compatible_frames(pair["archetype_id"], values)
        current = render(pair["archetype_id"], values, context=frame[:2],
                         continuation=frame[2])
        assert (current["digits"], current["cardinal"]) == (pair["digits"], pair["cardinal"])


def test_noun_quantity_buckets_are_complete_and_sampled():
    assert set(PURCHASE_BUCKETS) == {noun.singular for noun in NOUNS}
    assert PURCHASE_LIMITS == {"fixture_large": 6, "durable_unit": 12,
                               "grocery_fresh": 20, "consumable_small": 30}
    for seed in range(1000):
        values = sample("purchase", random.Random(seed))
        assert 2 <= values["quantity"] <= PURCHASE_LIMITS[
            PURCHASE_BUCKETS[values["noun"]["singular"]]]
        validate_pair(render("purchase", values))


def test_round_two_contradictions_are_excluded_or_reworded(tmp_path):
    items = NaturalnessStore(tmp_path).flags()[24:44]
    for position in (1, 2, 3, 4, 5, 6, 8, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20):
        pair = items[position - 1]["pair"]
        if position == 3:
            # The old 28-table purchase remains renderable for history, but
            # noun-dependent sampling now limits a personal purchase to 6.
            assert pair["sampled"]["quantity"] > PURCHASE_LIMITS[
                PURCHASE_BUCKETS[pair["sampled"]["noun"]["singular"]]]
            continue
        frame = (pair["context"]["start"], pair["context"]["end"], pair["continuation"])
        if frame in compatible_frames(pair["archetype_id"], pair["sampled"]):
            revised = render(pair["archetype_id"], pair["sampled"],
                             context=(frame[0], frame[1]), continuation=frame[2])
            assert revised["digits"] != pair["digits"] or revised["cardinal"] != pair["cardinal"]


def test_plural_large_shekels_only_for_last_digit_one():
    assert "ואחד שקלים" in render("large_shekels", {"shekels_large": 125001})["cardinal"]
    assert "ושניים שקל" in render("large_shekels", {"shekels_large": 125002})["cardinal"]
    # Half-shekel reading was accepted; only the shipping context was wrong.
    values = {"shekels": 36, "agorot": 50}
    assert "וחצי שקל" in render("money_cents", values)["cardinal"]


def test_round_three_snapshots_and_natural_decisions_are_preserved(tmp_path):
    assert ROUND_THREE_FLAGS.exists()
    raw = json.loads(ROUND_THREE_FLAGS.read_text(encoding="utf-8"))
    frozen_r1 = json.loads(ROUND_ONE_SNAPSHOTS.read_text(encoding="utf-8"))
    frozen_r3 = json.loads(ROUND_THREE_SNAPSHOTS.read_text(encoding="utf-8"))
    assert len(raw) == 25
    assert len(frozen_r3) == 25

    all_items = NaturalnessStore(tmp_path).flags()
    round_one = all_items[:24]
    round_three = [item for item in all_items if item["round"] == 3]
    assert len(round_three) == 25
    assert not {item["id"] for item in round_three} & {item["id"] for item in all_items[:44]}

    # Frozen Round 3 snapshots keep their original starter-15 / renderer-14 text and spans.
    signatures = set()
    for flag, item in zip(raw, round_three):
        assert set(flag) == {"archetype_id", "sampled", "context",
                             "continuation", "reason_he", "suggestion_he", "severity"}
        assert item["round"] == 3 and item["rating"] is None
        signature = (flag["archetype_id"], json.dumps(flag["sampled"], sort_keys=True,
                                                       ensure_ascii=False),
                     (*flag["context"], flag["continuation"]))
        assert signature not in signatures
        signatures.add(signature)
        assert flag["reason_he"] and flag["suggestion_he"]
        assert item["pair"] == frozen_r3[item["id"]]
        assert item["pair"]["catalog_version"] == "starter-15"
        assert item["pair"]["renderer_version"] == "14"
        validate_pair(item["pair"])

    # Round 1 approved natural items (#7, #9, #10, #11, #16) must remain eligible and intact.
    for position in (7, 9, 10, 11, 16):
        pair = round_one[position - 1]["pair"]
        assert pair == frozen_r1[round_one[position - 1]["id"]]
        frame = (pair["context"]["start"], pair["context"]["end"], pair["continuation"])
        assert frame in compatible_frames(pair["archetype_id"], pair["sampled"])
        current = render(pair["archetype_id"], pair["sampled"], context=frame[:2], continuation=frame[2])
        assert (current["digits"], current["cardinal"]) == (pair["digits"], pair["cardinal"])

    # Round 3 approved natural items (#2 purchase, #18 address, #20 meeting_minute) must remain intact.
    natural_r3 = {2, 18, 20}
    for position in natural_r3:
        pair = round_three[position - 1]["pair"]
        frame = (pair["context"]["start"], pair["context"]["end"], pair["continuation"])
        assert frame in compatible_frames(pair["archetype_id"], pair["sampled"])
        current = render(pair["archetype_id"], pair["sampled"], context=frame[:2], continuation=frame[2])
        assert (current["digits"], current["cardinal"]) == (pair["digits"], pair["cardinal"])

    # All 22 approved unnatural Round 3 items must be excluded from compatible_frames or reworded.
    for position in range(1, 26):
        if position in natural_r3:
            continue
        pair = round_three[position - 1]["pair"]
        frame = (pair["context"]["start"], pair["context"]["end"], pair["continuation"])
        if frame in compatible_frames(pair["archetype_id"], pair["sampled"]):
            revised = render(pair["archetype_id"], pair["sampled"], context=frame[:2], continuation=frame[2])
            assert (revised["digits"], revised["cardinal"]) != (pair["digits"], pair["cardinal"]), (
                f"Round 3 #{position} ({pair['archetype_id']}) was neither excluded nor reworded"
            )

    # Local rating history (when present) joins cleanly without mutating snapshots.
    local_data = Path.home() / ".local/share/hebrew-numeric-pairs"
    if (local_data / "naturalness-ratings.jsonl").exists():
        rated_r3 = [item for item in NaturalnessStore(local_data).flags() if item["round"] == 3]
        assert [i for i, x in enumerate(rated_r3, 1) if x["rating"] and x["rating"]["verdict"] == "natural"] == [2, 18, 20]
        assert sum(1 for x in rated_r3 if x["rating"] and x["rating"]["verdict"] == "unnatural") == 22


def test_explicit_hundredths_construct_two_preserves_composite_readings():
    pair_two = render("explicit_hundredths", {"seconds": 2, "hundredths": 80}, context=(7, 9), continuation=1)
    assert "שתי שניות ושמונים מאיות" in pair_two["cardinal"]
    assert "שתיים שניות" not in pair_two["cardinal"]
    validate_pair(pair_two)

    # Composite numbers above 20 keep regular feminine forms per Round 1 #16.
    for seconds, expected_prefix in ((22, "עשרים ושתיים שניות"), (52, "חמישים ושתיים שניות")):
        comp = render("explicit_hundredths", {"seconds": seconds, "hundredths": 25})
        assert comp["alignments"][0]["cardinal_text"].startswith(expected_prefix)
        validate_pair(comp)

    minute_pair = render("stopwatch_minute", {"minutes": 1, "seconds": 52, "hundredths": 75}, context=(0, 2), continuation=0)
    assert minute_pair["cardinal"] == "הזמן במקצה היה דקה אחת, חמישים ושתיים שניות ושבעים וחמש מאיות על המסלול."
    decimal_pair = render("stopwatch_seconds", {"seconds": 2, "hundredths": 58})
    assert decimal_pair["alignments"][0]["cardinal_text"] == "שתיים נקודה חמישים ושמונה שניות"


def test_temperature_flight_and_clock_departure_compatibility():
    # #3 decimal_temp: no conflicting dayparts or shade/peak-day self-echoes.
    dec_ctx = CONTEXTS["decimal_temp"]
    for s, e, _ in compatible_frames("decimal_temp", {"whole": 27, "fractional": "25"}):
        start, end = dec_ctx.starts[s], dec_ctx.ends[e]
        if any(tok in start for tok in ("הצהריים", "בצהריים", "בשיא היום", "הבוקר")):
            assert end not in {" מעלות בשעות הבוקר.", " מעלות בצהריים.", " מעלות בשעות הערב.",
                               " מעלות בשיא היום.", " מעלות לאחר השקיעה."}
        if "בצל" in start:
            assert end not in {" מעלות בצל.", " מעלות בשעות הערב.", " מעלות לאחר השקיעה."}

    # #4 negative_temp: no morning/night contradiction or mountain-station repetition.
    neg_ctx = CONTEXTS["negative_temp"]
    for s, e, _ in compatible_frames("negative_temp", {"magnitude": 17}):
        start, end = neg_ctx.starts[s], neg_ctx.ends[e]
        if "בבוקר" in start:
            assert end not in {" מעלות בשעות הבוקר.", " מעלות בשעות הלילה.",
                               " מעלות לפני הזריחה.", " מעלות לאחר השקיעה."}
        if "לילה" in start or "ליל " in start:
            assert end not in {" מעלות בשעות הבוקר.", " מעלות בצל.", " מעלות בשעות הלילה."}
        if "ההררית" in start:
            assert end != " מעלות בתחנה ההררית."

    # #5 flight_number: morning/evening flights never take morning/evening departure suffixes.
    flight_ctx = CONTEXTS["flight_number"]
    for s, e, _ in compatible_frames("flight_number", {"flight": 206}):
        if "טיסת הבוקר" in flight_ctx.starts[s] or "טיסת הערב" in flight_ctx.starts[s]:
            assert flight_ctx.ends[e] not in {" תמריא בשעות הבוקר.", " תמריא בשעות הערב."}

    # #6 departure: night train gated by night clock hours and never "בכל בוקר"; morning ending gated to 05:00-11:59.
    dep_ctx = CONTEXTS["departure"]
    morning_frames = compatible_frames("departure", {"minute_of_day": 10 * 60 + 37})
    afternoon_frames = compatible_frames("departure", {"minute_of_day": 15 * 60 + 20})
    night_frames = compatible_frames("departure", {"minute_of_day": 23 * 60 + 15})
    assert all(s != 14 for s, _, _ in morning_frames)
    assert all(s != 14 for s, _, _ in afternoon_frames)
    assert any(s == 14 for s, _, _ in night_frames)
    assert any(e == 9 for _, e, _ in morning_frames)
    assert all(e != 9 for _, e, _ in afternoon_frames)
    assert all(e != 9 for _, e, _ in night_frames)
    for frames in (morning_frames, afternoon_frames, night_frames):
        for s, e, _ in frames:
            assert not ("מהרציף המרכזי" in dep_ctx.starts[s] and dep_ctx.ends[e] == " מהרציף המרכזי.")
            assert not ("מהחניון" in dep_ctx.starts[s] and dep_ctx.ends[e] == " מרחבת החניון.")
            assert not ("לתחנה המרכזית" in dep_ctx.starts[s] and dep_ctx.ends[e] == " מהתחנה המרכזית.")


def test_score_tie_and_sport_phase_compatibility():
    score_ctx = CONTEXTS["score"]
    tie_frames = compatible_frames("score", {"score": "0:0"})
    for s, e, _ in tie_frames:
        assert "ניצחה" not in score_ctx.starts[s]
        assert "המערכה הראשונה" not in score_ctx.starts[s]
        assert score_ctx.ends[e] not in {" לטובת המארחת.", " לטובת האורחת."}

    win_frames = compatible_frames("score", {"score": "4:2"})
    assert any("ניצחה" in score_ctx.starts[s] for s, _, _ in win_frames)
    for s, e, c in win_frames:
        start, end = score_ctx.starts[s], score_ctx.ends[e]
        if "המחצית" in start or "המערכה הראשונה" in start:
            assert end not in {" בסיום תשעים דקות.", " לאחר הארכה.", " לאחר משחק צמוד."}
        if "ניצחה" in start:
            assert end not in {" לטובת המארחת.", " לטובת האורחת."}
        if "המערכה הראשונה" in start and c > 0:
            rendered = render("score", {"score": "4:2"}, context=(s, e), continuation=c)
            assert "שתי הקבוצות תקפו" not in rendered["digits"]
            validate_pair(rendered)


def test_fraction_liquid_solid_and_sweet_savory_splits():
    ctx = CONTEXTS["fraction"]
    solids = {" כוס סוכר.", " כוס קמח.", " כוס אורז.", " כוס עדשים.",
              " כוס שיבולת שועל.", " כוס קקאו.", " כוס אבקת סוכר."}
    savory_only = {" כוס אורז.", " כוס עדשים.", " כוס ציר ירקות.", " כוס יין לבן."}
    sweet_only = {" כוס סוכר.", " כוס מיץ תפוזים.", " כוס שמנת מתוקה.",
                  " כוס קקאו.", " כוס אבקת סוכר.", " כוס סירופ מייפל."}

    frames = compatible_frames("fraction", {"fraction": "3/4"})
    assert {s for s, _, _ in frames} == set(range(len(ctx.starts)))
    assert {e for _, e, _ in frames} == set(range(len(ctx.ends)))

    for s, e, c in frames:
        start, end = ctx.starts[s], ctx.ends[e]
        if "יוצקים" in start or "שופכים" in start:
            assert end not in solids and end not in {" כוס יוגורט.", " כוס טחינה גולמית."}
        if any(word in start for word in ("לעוגה", "לקרם", "לזיגוג", "לבלילה", "ההתפחה", "האפייה")):
            assert end not in savory_only and end != " כוס שמן זית."
        if any(word in start for word in ("לסיר", "לרוטב", "למרק", "למחבת", "לתבשיל")):
            assert end not in sweet_only and end != " כוס חלב."
            if c > 0:
                pair = render("fraction", {"fraction": "1/2"}, context=(s, e), continuation=c)
                assert "גושים" not in pair["digits"]
                validate_pair(pair)


def test_age_ranges_match_audiences():
    ctx = CONTEXTS["age_range"]
    for age_range, forbidden in (
        ("6–12", ("סטודנטים", "צעירים", "בני נוער")),
        ("8–14", ("סטודנטים", "צעירים", "בני נוער", "שעת סיפור")),
        ("12–18", ("סטודנטים", "צעירים", "לילדים")),
        ("18–25", ("לילדים", "לתלמידים", "בני נוער")),
    ):
        frames = compatible_frames("age_range", {"age_range": age_range})
        assert len({s for s, _, _ in frames}) >= 12
        for s, _, _ in frames:
            assert not any(term in ctx.starts[s] for term in forbidden), (age_range, ctx.starts[s])


def test_domain_banks_for_data_plan_version_pills_dates_addresses_measures_and_records():
    # #9 data_plan
    dp_ctx = CONTEXTS["data_plan"]
    for s, e, _ in compatible_frames("data_plan", {"gigabytes": 50, "megabits": 500}):
        if "בחו״ל" in dp_ctx.starts[s]:
            assert dp_ctx.ends[e] not in {" בכל רחבי הארץ.", " כולל נתב אלחוטי.", " ללא עלות התקנה."}
        if "הסלולר" in dp_ctx.starts[s]:
            assert dp_ctx.ends[e] not in {" כולל נתב אלחוטי.", " ללא עלות התקנה."}
        if "הביתית" in dp_ctx.starts[s] or "הסיבים" in dp_ctx.starts[s]:
            assert dp_ctx.ends[e] not in {" בכל רחבי הארץ.", " לכל קו במשפחה."}

    # #10, #11 version uses dedicated VERSION_ENDINGS without legal/printed-edition endings
    ver_ctx = CONTEXTS["version"]
    assert ver_ctx.ends is lexicon.VERSION_ENDINGS
    for forbidden in (" בחוזה החתום.", " בתקנון.", " בגרסה המודפסת."):
        assert forbidden not in ver_ctx.ends
    for s, e, _ in compatible_frames("version", {"major": 1, "minor": 3, "patch": 4}):
        if "סביבת הבדיקות" in ver_ctx.starts[s]:
            assert ver_ctx.ends[e] not in {" בסביבת הייצור.", " בסביבת הפיתוח.", " לאחר הבדיקות."}

    # #13, #14 pill_range
    pill_ctx = CONTEXTS["pill_range"]
    for s, e, _ in compatible_frames("pill_range", {"minimum": 2, "maximum": 4}):
        start, end = pill_ctx.starts[s], pill_ctx.ends[e]
        if "בבוקר או בערב" in start:
            assert end not in {" גלולות בבוקר ובערב.", " גלולות לפני השינה."}
        if "במידת הצורך" in start:
            assert end not in {" גלולות באופן קבוע.", " גלולות בכל יום.", " גלולות ביום.", " גלולות לפי הצורך."}

    # #16 slash_address
    sa_ctx = CONTEXTS["slash_address"]
    sa_frames = compatible_frames("slash_address", {"street": "האורן", "house": 12, "apartment": 4})
    residence_ends = {e for s, e, _ in sa_frames if s in (2, 5, 12)}
    assert len(residence_ends) >= 9
    for e in residence_ends:
        assert sa_ctx.ends[e] not in {" במסירה אישית.", " עם שליח עד הבית.", " לפי רישומי המחסן."}

    # #17 address (no self-landmark echo)
    addr_ctx = CONTEXTS["address"]
    for s, e, _ in compatible_frames("address", {"street": "הרימון", "house": 79}):
        start, end = addr_ctx.starts[s], addr_ctx.ends[e]
        assert not ("בית הספר" in start and "בית הספר" in end)
        assert not ("החניון" in start and "החניון" in end)
        assert not ("הספרייה" in start and "הספרייה" in end)

    # #19 full_date & slash_date current deadlines
    for date_arch in ("full_date", "slash_date"):
        d_ctx = CONTEXTS[date_arch]
        for s, e, c in compatible_frames(date_arch, {"day": 1, "month": "מאי", "year": 2024}):
            if s in (6, 11):
                assert "באולם" not in d_ctx.ends[e] and "במתנ״ס" not in d_ctx.ends[e]
                if c > 0:
                    rendered = render(date_arch, {"day": 1, "month": "מאי", "year": 2024}, context=(s, e), continuation=c)
                    assert "הוראות הגעה" not in rendered["digits"] and "למשתתפים" not in rendered["digits"]

    # #21 opening_hours phone hotline
    oh_ctx = CONTEXTS["opening_hours"]
    for s, e, c in compatible_frames("opening_hours", {"start_hour": 8, "end_hour": 12}):
        if s == 3:
            assert oh_ctx.ends[e] != " כפי שמופיע בשלט הכניסה."
            if c > 0:
                rendered = render("opening_hours", {"start_hour": 8, "end_hour": 12}, context=(s, e), continuation=c)
                assert "שהמבקרים" not in rendered["digits"] and "בכניסה למקום" not in rendered["digits"]

    # #22 area & #23 distance
    area_ctx = CONTEXTS["area"]
    for _, e, _ in compatible_frames("area", {"square_meters": 59}):
        assert area_ctx.ends[e] not in {" לפי נתוני היצרן.", " בבדיקת הקבלה."}

    dist_ctx = CONTEXTS["distance"]
    short_dist = compatible_frames("distance", {"kilometers": 20})
    long_dist = compatible_frames("distance", {"kilometers": 150})
    assert any(s == 9 for s, _, _ in short_dist)
    assert all(s not in {9, 10, 15, 17, 19} for s, _, _ in long_dist)
    for _, e, _ in short_dist + long_dist:
        assert dist_ctx.ends[e] not in {
            " ברוטו.", " נטו.", " לפי תשריט המבנה.",
            " לפי נתוני היצרן.", " בבדיקת הקבלה.", " לפי הערכת השמאי.",
        }

    # #24 bulk_purchase: no repeated purpose phrases
    bp_ctx = CONTEXTS["bulk_purchase"]
    bp_frames = compatible_frames(
        "bulk_purchase", {"noun": {"singular": "תפוז", "plural": "תפוזים", "gender": "m"}, "quantity": 500}
    )
    for s, e, _ in bp_frames:
        start, end = bp_ctx.starts[s], bp_ctx.ends[e]
        for echo in ("חידוש המלאי", "הזמנה מרוכזת", "תוכנית האספקה", "הזמנת הרכש", "ההזמנה הסיטונאית", "המחסן"):
            assert not (echo in start and echo in end), (start, end)

    # #25 RECORD archetypes: no exact or container-noun echo
    for arch, ctx in CONTEXTS.items():
        if ctx.ends is not RECORD:
            continue
        values = sample(arch, random.Random(7))
        for s, e, _ in compatible_frames(arch, values):
            start, end = ctx.starts[s], ctx.ends[e]
            phrase = end.strip(" .")
            if phrase:
                assert phrase not in start, (arch, start, end)
            for token in ("טופס", "קובץ", "מסך", "רשומת", "טבלת", "דוח", "תסריט", "ממשק", "סימולציית", "סביבת"):
                assert not (token in start and token in end), (arch, token, start, end)


def test_no_generated_pair_escapes_its_compatible_group_and_variation_holds():
    seen_sentences: dict[str, set[str]] = {arch.id: set() for arch in ARCHETYPES}
    for seed in range(20):
        for pair in generate(seed, len(ARCHETYPES)):
            frame = (pair["context"]["start"], pair["context"]["end"], pair["continuation"])
            assert frame in compatible_frames(pair["archetype_id"], pair["sampled"])
            validate_pair(pair)
            seen_sentences[pair["archetype_id"]].add(pair["digits"])
    assert all(len(sentences) >= 10 for sentences in seen_sentences.values())


def test_inspection_exposes_accurate_value_aware_groups_across_all_archetypes():
    for archetype_id in BY_ID:
        info = describe(archetype_id)
        assert info["frame_groups"], archetype_id
        group_names = [group["name"] for group in info["frame_groups"]]
        assert len(group_names) == len(set(group_names)), f"Duplicate group names in {archetype_id}: {group_names}"
        assert all(not name.startswith("sport-") for name in group_names)
        assert all(group["starts"] and group["ends"] and len(group["continuations"]) == 3
                   for group in info["frame_groups"])
        assert all(example["cardinal"] and example["digits"] for example in info["examples"])

    assert {g["name"] for g in describe("age_range")["frame_groups"]} == {
        "children-6-12", "children-youth-8-14", "teens-12-18", "young-adults-18-25", "demographic-study"
    }
    assert {"night-train", "general-transit", "general-transit-nonmorning"} <= {
        g["name"] for g in describe("departure")["frame_groups"]
    }
    assert {"winning-match", "set-score", "full-match", "full-match-tie"} <= {
        g["name"] for g in describe("score")["frame_groups"]
    }
    assert {"historical", "current", "current-deadline", "future"} <= {
        g["name"] for g in describe("full_date")["frame_groups"]
    }
    assert {g["name"] for g in describe("distance")["frame_groups"]} == {
        "intercity-route", "aerial-distance", "local-route"
    }
    assert describe("version")["end_bank"] is None
    assert describe("version")["end_users"] == ["version"]
