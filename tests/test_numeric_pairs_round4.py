"""Round-four rated revisions, frozen snapshots, and round-five post-audit fixes."""

import json
from pathlib import Path
import random

import pytest

from numeric_pairs.catalog import ARCHETYPES, CATALOG_VERSION
from numeric_pairs.contexts import CONTEXTS, RECORD, compatible_frames
from numeric_pairs.core import RENDERER_VERSION, generate, render, sample, validate_pair
from numeric_pairs.naturalness import (
    ROUND_FOUR_FLAGS,
    ROUND_FOUR_SNAPSHOTS,
    ROUND_ONE_SNAPSHOTS,
    ROUND_THREE_SNAPSHOTS,
    ROUND_TWO_SNAPSHOTS,
    NaturalnessStore,
)


def test_versions_bumped_for_round_four_and_five_revisions():
    assert CATALOG_VERSION == "starter-19"
    assert RENDERER_VERSION == "18"


def test_round_four_snapshots_and_user_natural_overrides_are_preserved(tmp_path):
    flags = json.loads(ROUND_FOUR_FLAGS.read_text(encoding="utf-8"))
    snapshots = json.loads(ROUND_FOUR_SNAPSHOTS.read_text(encoding="utf-8"))
    frozen_r1 = json.loads(ROUND_ONE_SNAPSHOTS.read_text(encoding="utf-8"))
    frozen_r2 = json.loads(ROUND_TWO_SNAPSHOTS.read_text(encoding="utf-8"))
    frozen_r3 = json.loads(ROUND_THREE_SNAPSHOTS.read_text(encoding="utf-8"))

    items = NaturalnessStore(tmp_path).flags()
    fourth = [item for item in items if item["round"] == 4]
    assert len(flags) == len(snapshots) == len(fourth) == 28
    assert len(items) == 24 + 20 + 25 + 28 == 97
    assert len({item["id"] for item in items}) == len(items)

    # Frozen Round 4 snapshots retain their starter-16 / renderer-15 pairs and spans.
    for flag, item in zip(flags, fourth):
        assert set(flag) == {
            "archetype_id", "sampled", "context",
            "continuation", "reason_he", "suggestion_he", "severity",
        }
        assert item["rating"] is None
        assert item["pair"] == snapshots[item["id"]]
        assert item["pair"]["catalog_version"] == "starter-16"
        assert item["pair"]["renderer_version"] == "15"
        validate_pair(item["pair"])

    # Prior frozen rounds remain intact.
    assert all(item["pair"] == frozen_r1[item["id"]] for item in items[:24])
    assert all(item["pair"] == frozen_r2[item["id"]] for item in items[24:44])
    assert all(item["pair"] == frozen_r3[item["id"]] for item in items[44:69])

    # Explicit user natural ratings in Round 4 (#1 departure :45, #9 survey 100%, #23 version test-env)
    # override agent proposals and remain compatible with unchanged wording.
    natural_r4 = {1, 9, 23}
    for position in natural_r4:
        pair = fourth[position - 1]["pair"]
        frame = (pair["context"]["start"], pair["context"]["end"], pair["continuation"])
        assert frame in compatible_frames(pair["archetype_id"], pair["sampled"])
        current = render(pair["archetype_id"], pair["sampled"], context=frame[:2], continuation=frame[2])
        assert (current["digits"], current["cardinal"]) == (pair["digits"], pair["cardinal"])

    # All 25 user-rated unnatural Round 4 items are excluded from sampling/frames or reworded.
    for position in range(1, 29):
        if position in natural_r4:
            continue
        pair = fourth[position - 1]["pair"]
        if position == 4:
            with pytest.raises(ValueError):
                render("negative_temp", {"magnitude": 1})
            continue
        frame = (pair["context"]["start"], pair["context"]["end"], pair["continuation"])
        if frame in compatible_frames(pair["archetype_id"], pair["sampled"]):
            revised = render(pair["archetype_id"], pair["sampled"], context=frame[:2], continuation=frame[2])
            assert (revised["digits"], revised["cardinal"]) != (pair["digits"], pair["cardinal"]), (
                f"Round 4 #{position} ({pair['archetype_id']}) was neither excluded nor reworded"
            )

    local_data = Path.home() / ".local/share/hebrew-numeric-pairs"
    if (local_data / "naturalness-ratings.jsonl").exists():
        rated_r4 = [item for item in NaturalnessStore(local_data).flags() if item["round"] == 4]
        assert [i for i, x in enumerate(rated_r4, 1) if x["rating"] and x["rating"]["verdict"] == "natural"] == [1, 9, 23]
        assert sum(1 for x in rated_r4 if x["rating"] and x["rating"]["verdict"] == "unnatural") == 25

    first = fourth[0]
    NaturalnessStore(tmp_path).rate(first["id"], "natural", "בדיקה")
    rated = [item for item in NaturalnessStore(tmp_path).flags() if item["id"] == first["id"]][0]
    assert rated["pair"] == first["pair"] and rated["rating"]["note"] == "בדיקה"


def test_round_four_spoken_form_revisions_and_preserved_quarter_to():
    # #1 (rated natural): departure keeps "בשעה רבע ל..." at minute 45.
    dep = render("departure", {"minute_of_day": 19 * 60 + 45}, context=(8, 20), continuation=0)
    assert dep["cardinal"] == "הרכבת לבאר שבע יוצאת בשעה רבע לשמונה בימים ראשון עד חמישי."

    # #2: fraction 3/4 uses construct "שלושת רבעי" before "כוס".
    frac = render("fraction", {"fraction": "3/4"}, context=(10, 15), continuation=1)
    assert "שלושת רבעי כוס ציר ירקות" in frac["cardinal"]
    assert "שלושה רבעים" not in frac["cardinal"]

    # #3: road_route reads 1 in masculine ("כביש אחד", "קו אחד") and >=2 in unmarked feminine.
    rr_one = render("road_route", {"road": 1, "route": 1}, context=(0, 0), continuation=0)
    assert rr_one["cardinal"] == "עברנו דרך כביש אחד ומשם המשכנו בקו אחד בדרך לעיר."
    rr_two = render("road_route", {"road": 2, "route": 5}, context=(0, 0), continuation=0)
    assert rr_two["cardinal"] == "עברנו דרך כביש שתיים ומשם המשכנו בקו חמש בדרך לעיר."

    # #4 (with user note confirming construct "מינוס שתי מעלות"): negative_temp samples >=2 and uses construct for -2.
    neg_two = render("negative_temp", {"magnitude": 2}, context=(0, 0), continuation=0)
    assert neg_two["cardinal"] == "בבוקר נמדדו מינוס שתי מעלות."
    for seed in range(300):
        assert 2 <= sample("negative_temp", random.Random(seed))["magnitude"] <= 20

    # #5: million_exact connects sub-100 remainders with "ו", uses "ושתי" before "רשומות", and avoids sampling 001.
    m_tens = render("million_exact", {"number": 1_300_088}, context=(0, 0), continuation=0)
    assert m_tens["alignments"][0]["cardinal_text"] == "מיליון, שלוש מאות אלף ושמונים ושמונה"
    m_two = render("million_exact", {"number": 1_347_002}, context=(0, 0), continuation=0)
    assert m_two["alignments"][0]["cardinal_text"] == "מיליון, שלוש מאות ארבעים ושבעה אלף ושתי"
    m_hundreds = render("million_exact", {"number": 1_234_567}, context=(0, 0), continuation=0)
    assert m_hundreds["alignments"][0]["cardinal_text"] == "מיליון, מאתיים שלושים וארבעה אלף, חמש מאות שישים ושבע"
    for seed in range(500):
        assert sample("million_exact", random.Random(seed))["number"] % 1000 != 1


def test_round_four_semantic_and_grammatical_frame_constraints():
    # #6 year: feminine and event starts never take masculine ongoing-operation endings or entrance signs.
    year_ctx = CONTEXTS["year"]
    for s, e, _ in compatible_frames("year", {"year": 2026}):
        start, end = year_ctx.starts[s], year_ctx.ends[e]
        if any(w in start for w in ("החברה", "הספרייה", "השכונה", "המעבדה", "האגודה", "האוניברסיטה", "התערוכה", "התוכנית")):
            assert end not in {" בראשית פעילותו.", " במתכונתו הנוכחית.", " ומאז הוא פועל ברציפות."}
        if any(w in start for w in ("המחקר ", "הסרט ", "הספר ", "החוק ", "ההסכם ", "הדוח ", "התקן ")):
            assert end not in {" ומאז הוא פועל ברציפות.", " במתכונתו הנוכחית.", " על פי שלט הכניסה."}

    # #7 age: past-tense milestones never take future time expressions.
    age_ctx = CONTEXTS["age"]
    for s, e, _ in compatible_frames("age", {"age": 78}):
        if "הגיע" in age_ctx.starts[s]:
            assert age_ctx.ends[e] not in {" בחודש הקרוב.", " בשבוע הבא."}

    # #8 survey: audience-specific starts do not clash with other respondent groups; #9 (100% + cont 1) stays valid.
    sv_ctx = CONTEXTS["survey"]
    sv_frames = compatible_frames("survey", {"percent": 100})
    assert (3, 13, 1) in sv_frames
    for s, e, _ in sv_frames:
        start, end = sv_ctx.starts[s], sv_ctx.ends[e]
        if "הצרכנים" in start:
            assert "מהעובדים" not in end and "מהתושבים" not in end
        if "העובדים" in start:
            assert "מהתושבים" not in end and "מהלקוחות" not in end and "מהצרכנים" not in end
        if "הסטודנטים" in start:
            assert not any(g in end for g in ("מהתושבים", "מהלקוחות", "מהעובדים", "מהצרכנים"))

    # #10 mobile: customer call-to-action uses dedicated customer endings rather than lab/dev simulation records.
    mob_ctx = CONTEXTS["mobile"]
    assert len(mob_ctx.starts) >= 20 and len(mob_ctx.ends) >= 20
    for _, e, _ in compatible_frames("mobile", {"phone": "054-000-2380"}):
        assert not any(lab in mob_ctx.ends[e] for lab in ("הבדיקה", "הניסוי", "הדמה", "הפיתוח", "סימולציית", "המעבדה"))

    # #11 weight: no map/blueprint/appraiser endings; parcels do not claim manufacturer weight specs.
    w_ctx = CONTEXTS["weight"]
    for s, e, _ in compatible_frames("weight", {"weight": 8}):
        assert w_ctx.ends[e] not in {" לפי המפה המעודכנת.", " לפי הערכת השמאי.", " לפי תשריט המבנה."}
        if "המזוודה" in w_ctx.starts[s] or "המשלוח" in w_ctx.starts[s]:
            assert w_ctx.ends[e] != " לפי נתוני היצרן."

    # #12 duration_half: on-schedule endings use harmonious continuations; transit/waiting avoid intermissions.
    dh_ctx = CONTEXTS["duration_half"]
    for s, e, c in compatible_frames("duration_half", {"duration": "2.5"}):
        assert dh_ctx.ends[e] != " מעבר למתוכנן."
        if s in {0, 1, 2, 10, 17, 21}:
            assert dh_ctx.ends[e] not in {" כולל ההפסקה.", " כולל שלב הסיום."}
        if dh_ctx.ends[e] in {" כפי שהעריכו מראש.", " במסגרת לוח הזמנים.", " בלי עיכובים מיוחדים."} and c > 0:
            p = render("duration_half", {"duration": "2.5"}, context=(s, e), continuation=c)
            assert "מעבר לזמן" not in p["digits"] and "לסיים מוקדם יותר" not in p["digits"]

    # #13 decade: factories/schools/infrastructure do not use "היצירה הוצגה לציבור"; urban starts avoid kibbutz/moshava.
    dec_ctx = CONTEXTS["decade"]
    for s, e, c in compatible_frames("decade", {"decade": 60}):
        if s not in {0, 1, 5, 6, 7, 10, 15, 19} and c == 2:
            p = render("decade", {"decade": 60}, context=(s, e), continuation=2)
            assert "היצירה" not in p["digits"]
        if s in {13, 18}:
            assert dec_ctx.ends[e] not in {" בקיבוץ.", " במושבה הוותיקה."}

    # #14 decimal_temp & #15 departure & #16 PRICE & #17 numeric_calendar & #18 stopwatch_minute & #19 score
    dt_ctx = CONTEXTS["decimal_temp"]
    for s, e, _ in compatible_frames("decimal_temp", {"whole": 24, "fractional": "5"}):
        if s in {13, 16}:
            assert dt_ctx.ends[e] not in {" מעלות סמוך לחוף.", " מעלות בהרים.", " מעלות בעמק."}
        if s != 0:
            assert dt_ctx.ends[e] != " מעלות לפי התחזית."

    dep_ctx = CONTEXTS["departure"]
    for m in (2 * 60 + 24, 9 * 60 + 30, 16 * 60 + 45):
        for s, e, _ in compatible_frames("departure", {"minute_of_day": m}):
            if "הרכבת" in dep_ctx.starts[s] or "רכבת" in dep_ctx.starts[s]:
                assert dep_ctx.ends[e] not in {" מרחבת החניון.", " מנקודת האיסוף."}
            if m == 9 * 60 + 30:
                assert s != 4  # האוטובוס האחרון
            if m == 2 * 60 + 24:
                assert s != 20  # אוטובוס התלמידים

    for money_arch in ("money", "money_cents", "dollar_price", "euro_price"):
        m_ctx = CONTEXTS[money_arch]
        vals = sample(money_arch, random.Random(3))
        for s, e, _ in compatible_frames(money_arch, vals):
            if any(k in m_ctx.starts[s] for k in ("דמי הכניסה", "דמי ההרשמה", "תעריף הנסיעה", "מחיר המנוי", "מחיר הסדנה")):
                assert m_ctx.ends[e] not in {" כולל משלוח.", " כולל אריזה."}

    assert all(s != 10 for s, _, _ in compatible_frames("numeric_calendar", {"day": 14, "month_number": 4}))
    assert any(s == 10 for s, _, _ in compatible_frames("numeric_calendar", {"day": 14, "month_number": 6}))

    swm_ctx = CONTEXTS["stopwatch_minute"]
    for s, e, _ in compatible_frames("stopwatch_minute", {"minutes": 2, "seconds": 30, "hundredths": 40}):
        if s == 4:
            assert swm_ctx.ends[e] != " על המסלול."
        assert not (s == 8 and e == 8)
        assert not (s == 14 and e == 2)

    sc_ctx = CONTEXTS["score"]
    for s, e, _ in compatible_frames("score", {"score": "2:1"}):
        if "משחק הגביע" in sc_ctx.starts[s]:
            assert sc_ctx.ends[e] not in {" במסגרת הליגה.", " בשלב הבתים."}

    # #20 minimum_age, #21 map_scale, #22 approximate, #24 bulk_purchase, #25 ranking, #26 pill_range, #27 million_exact, #28 large_shekels
    ma_ctx = CONTEXTS["minimum_age"]
    for s, e, _ in compatible_frames("minimum_age", {"minimum_age": 24}):
        if s == 6:
            assert ma_ctx.ends[e] not in {" ומעלה במרכז הקהילתי.", " ומעלה בקבוצות הערב."}

    ms_ctx = CONTEXTS["map_scale"]
    for _, e, _ in compatible_frames("map_scale", {"scale": 100_000}):
        assert ms_ctx.ends[e] not in {" ביומן השינויים.", " בחוזה החתום.", " בהוראות ההפעלה."}

    ap_frames = compatible_frames(
        "approximate", {"noun": {"singular": "סוללה", "plural": "סוללות", "gender": "f"}, "quantity": 5}
    )
    for s, e, c in ap_frames:
        if s in {0, 1}:
            p = render(
                "approximate",
                {"noun": {"singular": "סוללה", "plural": "סוללות", "gender": "f"}, "quantity": 5},
                context=(s, e), continuation=c,
            )
            assert p["digits"].count("רשימה") <= 1

    bp_ctx = CONTEXTS["bulk_purchase"]
    for s, e, _ in compatible_frames(
        "bulk_purchase", {"noun": {"singular": "מנורה", "plural": "מנורות", "gender": "f"}, "quantity": 420}
    ):
        assert not (s == 16 and bp_ctx.ends[e] == " בכמה משלוחים.")
        assert not (s == 5 and bp_ctx.ends[e] == " למרכז ההפצה.")

    rk_ctx = CONTEXTS["ranking"]
    for s, e, c in compatible_frames("ranking", {"rank": 4}):
        if "השחמטאי" in rk_ctx.starts[s]:
            assert "במקצה" not in rk_ctx.ends[e]
        if rk_ctx.ends[e] in {" בדירוג השנתי.", " בסיום העונה.", " בליגה הלאומית."} and c > 0:
            p = render("ranking", {"rank": 4}, context=(s, e), continuation=c)
            assert "יום ארוך של תחרויות" not in p["digits"] and "של המקצה" not in p["digits"]

    pr_ctx = CONTEXTS["pill_range"]
    for s, e, _ in compatible_frames("pill_range", {"minimum": 2, "maximum": 5}):
        if s == 6:
            assert pr_ctx.ends[e] not in {" גלולות בימים הראשונים.", " גלולות למשך שבוע."}

    me_ctx = CONTEXTS["million_exact"]
    for s, e, _ in compatible_frames("million_exact", {"number": 1_708_653}):
        for tok in ("בקובץ המאוחד", "במאגר", "בארכיון", "במערכת"):
            assert not (tok in me_ctx.starts[s] and tok in me_ctx.ends[e])

    ls_ctx = CONTEXTS["large_shekels"]
    for s, e, _ in compatible_frames("large_shekels", {"shekels_large": 500_000}):
        if "המענק המחקרי" in ls_ctx.starts[s]:
            assert ls_ctx.ends[e] not in {" כולל עבודות תשתית.", " לפי הערכת השמאי.", " לפני מע״מ."}
        if s in {12, 14, 17}:
            assert ls_ctx.ends[e] != " כולל ציוד קצה."


def test_round_five_post_audit_improvements():
    # 1. road_route: no "נסענו בבוקר ... לקראת הערב / בשעות הבוקר" or "כפי שתכננו מראש ... שהדרך שתכננו מראש"
    rr_ctx = CONTEXTS["road_route"]
    for s, e, _ in compatible_frames("road_route", {"road": 4, "route": 10}):
        assert rr_ctx.ends[e] != " כפי שתכננו מראש."
        if "בבוקר" in rr_ctx.starts[s]:
            assert rr_ctx.ends[e] not in {" לקראת הערב.", " בשעות הבוקר.", " בשעות אחר הצהריים."}

    # 2. purchase: no morning/evening clash or "לפי הרשימה, בהתאם לרשימה", while preserving R3 #2 (2, 14, 2)
    pur_vals = {"noun": {"singular": "מגבת", "plural": "מגבות", "gender": "f"}, "quantity": 2}
    assert (2, 14, 2) in compatible_frames("purchase", pur_vals)
    pur_ctx = CONTEXTS["purchase"]
    for s, e, _ in compatible_frames("purchase", pur_vals):
        assert pur_ctx.ends[e] != " לפי הרשימה."
        if s in {3, 17}:
            assert pur_ctx.ends[e] not in {" אחרי העבודה.", " בשעות הבוקר."}
        if s in {1, 26}:
            assert pur_ctx.ends[e] != " בשעות הבוקר."

    # 3. postal: municipal/directory starts do not get parcel-shipping endings or continuations
    po_ctx = CONTEXTS["postal"]
    for s, e, c in compatible_frames("postal", {"postal_code": "6100001"}):
        if s in {4, 6, 7, 12, 13, 16, 17, 18}:
            assert po_ctx.ends[e] not in {" על גבי האריזה.", " לצורך ניתוב החבילה.", " על המעטפה הרשומה."}
            if c > 0:
                p = render("postal", {"postal_code": "6100001"}, context=(s, e), continuation=c)
                assert "שהחבילה" not in p["digits"] and "לחברת ההפצה" not in p["digits"]

    # 4. floor, opening_hours, percent_half, slash_address, data_plan, infant_age, calendar, section, meeting_minute, RECORD
    fl_ctx = CONTEXTS["floor"]
    for s, e, _ in compatible_frames("floor", {"floor": 4}):
        if s == 14:
            assert fl_ctx.ends[e] not in {" בבית העירייה.", " בבניין הפקולטה.", " במרכז הרפואי."}

    oh_ctx = CONTEXTS["opening_hours"]
    for s, e, _ in compatible_frames("opening_hours", {"start_hour": 8, "end_hour": 13}):
        if s in {4, 10, 12, 14, 18}:
            assert oh_ctx.ends[e] != " עבור לקוחות הסניף."
        if s == 17:
            assert oh_ctx.ends[e] not in {" בתיאום תור מראש.", " לפי הודעת העירייה."}

    ph_ctx = CONTEXTS["percent_half"]
    for s, e, c in compatible_frames("percent_half", {"whole_percent": 6}):
        if s in {5, 8, 9, 10, 11, 13}:
            assert ph_ctx.ends[e] != " לפי תחזית האגף."
            if c == 2:
                p = render("percent_half", {"whole_percent": 6}, context=(s, e), continuation=2)
                assert "עשוי להשתנות שוב" not in p["digits"]

    sa_ctx = CONTEXTS["slash_address"]
    for s, e, _ in compatible_frames("slash_address", {"street": "הרצל", "house": 10, "apartment": 2}):
        if s in {9, 16}:
            assert sa_ctx.ends[e] not in {" עם שליח עד הבית.", " במסגרת המשלוח היומי."}

    dp_ctx = CONTEXTS["data_plan"]
    for s, e, _ in compatible_frames("data_plan", {"gigabytes": 50, "megabits": 500}):
        assert dp_ctx.ends[e] != " במסלול החדש."
        if s == 4:
            assert dp_ctx.ends[e] != " לכל קו במשפחה."
        if s == 15:
            assert dp_ctx.ends[e] != " ללא הגבלת זמן."

    ia_ctx = CONTEXTS["infant_age"]
    for s, e, _ in compatible_frames("infant_age", {"age_years": "1.5"}):
        assert not (s == 11 and ia_ctx.ends[e] == " לפי הרישום במרפאה.")
        assert not (s == 13 and "בגן" in ia_ctx.ends[e])

    cal_ctx = CONTEXTS["calendar"]
    for s, e, _ in compatible_frames("calendar", {"day": 12, "month": "מאי"}):
        if s in {7, 8, 10, 16, 17, 22}:
            assert cal_ctx.ends[e] != " בחדר הישיבות הראשי."

    sec_ctx = CONTEXTS["section"]
    for s, e, _ in compatible_frames("section", {"section": 4, "subsection": 2}):
        if s in {4, 9, 10, 11, 13, 16, 17, 19}:
            assert sec_ctx.ends[e] not in {" בנספח ההנדסי.", " בהוראות ההפעלה.", " ביומן השינויים."}

    # meeting_minute preserves R3 #20 (4, 14, 0) while gating morning briefing and factory tour
    assert (4, 14, 0) in compatible_frames("meeting_minute", {"minute_of_day": 11 * 60 + 19})
    assert all(s != 3 for s, _, _ in compatible_frames("meeting_minute", {"minute_of_day": 21 * 60 + 19}))
    assert any(s == 3 for s, _, _ in compatible_frames("meeting_minute", {"minute_of_day": 8 * 60 + 19}))
    assert "היום הפתוח בקמפוס יתקיים " in CONTEXTS["numeric_calendar"].starts

    # RECORD archetypes never place two concrete document/UI containers in the same sentence.
    concrete_ends = set(range(20, 32))
    explicit_locs = ("בטופס ", "על טופס ", "בקובץ ", "במסך ", "בממשק ", "בהודעת ",
                     "ברשומת ", "ברשימת ", "בדוח ", "בכרטיס ", "על חזית ", "על גבי ",
                     "בקבלה ", "בקבלת ", "בחשבונית ", "בחשבון ", "בפרופיל ", "במערכת ",
                     "בתיק ", "בפוליסת ", "ברישיון ", "בדלפק ", "בשער ", "בכניסה ",
                     "באפליקציית ", "בהזמנת ", "בהזמנה ", "באישור ", "בביקורת ", "ברישום ",
                     "בהשכרת ", "במוסך ", "בשדה ", "בעמדת ", "בקופת ", "בפרטי ",
                     "בהצהרה ", "בפתיחת ", "בבקשת ", "בעמוד ", "בחוזה ", "במחלקת ")
    for arch in ARCHETYPES:
        ctx = CONTEXTS[arch.id]
        if ctx.ends is not RECORD or arch.id == "mobile":
            continue
        vals = sample(arch.id, random.Random(19))
        for s, e, _ in compatible_frames(arch.id, vals):
            if any(loc in ctx.starts[s] for loc in explicit_locs):
                assert e not in concrete_ends, (arch.id, ctx.starts[s], ctx.ends[e])


def test_no_dema_or_fake_disclaimer_words_in_any_output_sentences():
    import re
    from numeric_pairs.contexts import CONTINUATIONS

    banned_re = re.compile(
        r"(?:^|[\s״\"'\-])(?:דמה|הדמה|כדמה|לדמה)(?:$|[\s.,;!?״\"'])"
        r"|פיקטיבי|פיקטיבית|סימולציית|הדגמה|פרטי אמת|אדם אמיתי"
    )
    for arch in ARCHETYPES:
        ctx = CONTEXTS[arch.id]
        for text in (*ctx.starts, *ctx.ends, *CONTINUATIONS[arch.id]):
            assert not banned_re.search(text), (arch.id, text)
        vals = sample(arch.id, random.Random(77))
        base = render(arch.id, vals)
        assert not banned_re.search(base["digits"]), (arch.id, base["digits"])
        assert not banned_re.search(base["cardinal"]), (arch.id, base["cardinal"])
        for s, e, c in compatible_frames(arch.id, vals):
            pair = render(arch.id, vals, context=(s, e), continuation=c)
            assert not banned_re.search(pair["digits"]), (arch.id, pair["digits"])
            assert not banned_re.search(pair["cardinal"]), (arch.id, pair["cardinal"])


def test_pending_subcases_minimum_ten_pools_and_spot_sample_fixes():
    from numeric_pairs.inspection import describe

    new_ids = {
        "plural_millions", "child_half_age", "month_end_date",
        "midnight_time", "general_fraction", "multi_digit_decimal", "airline_flight",
    }
    assert new_ids <= {a.id for a in ARCHETYPES}

    for arch in ARCHETYPES:
        ctx = CONTEXTS[arch.id]
        assert len(ctx.starts) >= 20, arch.id
        assert len(ctx.ends) >= 20, arch.id
        info = describe(arch.id)
        for group in info["frame_groups"]:
            assert len(group["ends"]) >= 10, (arch.id, group["name"], len(group["ends"]))
        for seed in range(25):
            vals = sample(arch.id, random.Random(seed))
            frames = compatible_frames(arch.id, vals)
            eligible_starts = {s for s, _, _ in frames}
            assert len(eligible_starts) >= 10, (arch.id, seed, len(eligible_starts))
            for s in eligible_starts:
                eligible_ends = {e for s2, e, _ in frames if s2 == s}
                assert len(eligible_ends) >= 10, (arch.id, seed, s, len(eligible_ends))

    # Spot-sample regression checks:
    # 1. Older adults (>=45) never celebrate "בבית ההורים".
    age_ctx = CONTEXTS["age"]
    assert all(age_ctx.ends[e] != " בבית ההורים." for _, e, _ in compatible_frames("age", {"age": 85}))
    assert any(age_ctx.ends[e] == " בבית ההורים." for _, e, _ in compatible_frames("age", {"age": 25}))

    # 2. child_half_age separates boy ("בן") and girl ("בת") predicates and continuations.
    cha_ctx = CONTEXTS["child_half_age"]
    for s, e, c in compatible_frames("child_half_age", {"child_age": "3.5"}):
        pair = render("child_half_age", {"child_age": "3.5"}, context=(s, e), continuation=c)
        validate_pair(pair)
        if " בת " in cha_ctx.starts[s]:
            assert "מדבר " not in pair["digits"] and "הוא גדל" not in pair["digits"]
        else:
            assert "מדברת " not in pair["digits"] and "היא גדלה" not in pair["digits"]

    # 3. airline_flight separates inbound landing from outbound departure predicates.
    af_ctx = CONTEXTS["airline_flight"]
    for s, e, _ in compatible_frames("airline_flight", {"carrier": "LH", "flight": 687}):
        if s < 12:
            assert "תמריא" not in af_ctx.ends[e] and "לעלייה למטוס" not in af_ctx.ends[e]
        else:
            assert "נחתה" not in af_ctx.ends[e] and "פריקת המזוודות" not in af_ctx.ends[e]

    # 4. Clean 100-sample batch generation across the full 69-archetype catalog.
    batch = generate(2026, 100)
    assert len(batch) == 100
    for pair in batch:
        validate_pair(pair)
