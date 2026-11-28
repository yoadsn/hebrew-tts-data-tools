"""Read-only catalog inspection; never creates review runs or feedback."""

import random
from collections import Counter

from . import lexicon
from .catalog import BY_ID, PURCHASE_BUCKET_NAMES, PURCHASE_LIMITS
from .contexts import CLAUSE_GROUPS, CONTEXTS, CONTINUATIONS, DOCUMENT, MEASURE, PRICE, RECORD, REPORT, SHOP, SPORT, TIME, WEATHER, PAST_DATE_CONTINUATIONS, compatible_frames, date_start_indices, frame_groups
from .core import (
    CONTINUATION_CHOICES, ClockRef, DomainRef, Literal, NumberRef, OptionalGroup, OrdinalRef,
    PercentRef, PhoneRef, QuantityRef, SAMPLERS, TEMPLATES, ValueRef, render, sample,
)
from .variants import DEFAULT_FORMAL_WEIGHTS


SHARED_BANKS = {
    "SHOP": SHOP, "REPORT": REPORT, "RECORD": RECORD, "SPORT": SPORT,
    "WEATHER": WEATHER, "PRICE": PRICE, "TIME": TIME,
    "DOCUMENT": DOCUMENT, "MEASURE": MEASURE, "PHONE": lexicon.MOBILE_ENDINGS,
}

# These descriptions document the special generators; ranges and pool contents
# are taken directly from the corresponding SampleSpec below.
GENERATOR_RULES = {
    "clock": "דקה אקראית לאורך היממה (00:00–23:59)",
    "mobile": "קידומות 050/051/052/053/054/055/058; שבע ספרות מנוי בתבנית 3-3-4 או 3-7",
    "landline": "אזורי 02/03/04/08/09; כתיב מקף, רווח או סוגריים; שבע ספרות מנוי מגוונות",
    "local_landline": "שבע ספרות ללא קידומת אזור מקומי: XXX-XXXX",
    "national_line": "קידומות ארציות 072/073/074/076/077/079 עם שבע ספרות מנוי, או מספרי כוכבית (*XXX/*XXXX/*XXXXX)",
    "israeli_international": "‎+972 ואזור חיוג בלי אפס הגישה; נייד/קווי/ארצי עם שבע ספרות מנוי",
    "business_line": "קידומות שירות 1599/1700/1800 בפורמט 1-XXX-XXX-XXX, או מספרי כוכבית (*XXX/*XXXX/*XXXXX)",
    "four_digits": "ארבע ספרות אקראיות, כולל אפסים מובילים",
    "postal_code": "50% חמש ספרות ו־50% שבע ספרות; שבע ספרות נקראות בקבוצות של שתיים וחמש",
    "million_exact": "מעל מיליון ומתחת לשני מיליון; ספרת האחדות אינה אפס",
    "large_shekels": "סכום בן שש ספרות: אלפים ואחריהם שלוש ספרות נוספות",
    "minute_nonround": "שעות 06–23; הדקה אינה 00, 15, 30 או 45",
    "card_full": "16 ספרות בארבע קבוצות עם ספרת ביקורת Luhn לא תקינה (לא ניתן להנפקה)",
    "international_phone": "טלפון בינלאומי מגוון (‎+1/+44/+49/+33/+34/+39/+61)",
    "civil_id": "תשע ספרות עם ספרת ביקורת לא תקינה",
    "passport_id": "8–9 תווים בפורמט ICAO (ספרות בלבד ישראלי/בינלאומי או אותיות A–Z וספרות)",
    "demo_account": "שש ספרות חשבון אקראיות",
    "demo_plate": "לוחית רישוי ישראלית: XX-XXX-XX (7 ספרות) או XXX-XX-XXX (8 ספרות)",
    "plural_millions": "2–9 מיליון; מיליונים עגולים או תוספת מאות/עשרות אלפים, בקריאת שני מיליון / שלושה מיליון",
    "multi_digit_decimal": "שלם 0–19 עם שתי ספרות הפותחות באפס או שלוש ספרות עשרוניות שאינן מסתיימות באפס",
}


def _template(parts):
    output = ""
    for part in parts:
        if isinstance(part, Literal):
            output += part.value
        elif isinstance(part, OptionalGroup):
            output += f"[אם {part.condition}: {_template(part.parts)}]"
        elif isinstance(part, QuantityRef):
            output += "{כמות + שם עצם" + (" בקירוב" if part.approximate else "") + "}"
        elif isinstance(part, (ValueRef, NumberRef, OrdinalRef, ClockRef, PercentRef, PhoneRef)):
            output += "{" + part.key + "}"
        elif isinstance(part, DomainRef):
            output += "{" + part.kind + "}"
        else:
            raise TypeError(f"Unknown template part: {part!r}")
    return output


def describe(archetype_id: str) -> dict:
    """Expose the actual configured frame, pools and sampler—not a second catalog."""
    archetype = BY_ID[archetype_id]
    context = CONTEXTS[archetype_id]
    bank_name = next((name for name, bank in SHARED_BANKS.items() if context.ends is bank), None)
    end_users = ([id for id, other in CONTEXTS.items() if other.ends is context.ends]
                 if bank_name else [archetype_id])
    clause_users = next(names for names, _, _ in CLAUSE_GROUPS if archetype_id in names)
    sampling = []
    for spec in SAMPLERS[archetype_id]:
        item = {"slot": spec.key, "when": spec.when}
        if spec.pool:
            item.update(kind="pool", values=list(spec.pool))
            if archetype_id == "age_range":
                item["rule"] = "קבוצת הפתיחות מותאמת לקהל היעד לפי טווח הגיל"
            elif archetype_id == "score":
                item["rule"] = "בתוצאת תיקו מושמטים פתיחי ניצחון/מערכה וסיומות צד מנצח"
            elif archetype_id == "month_end_date" and spec.key == "month":
                item["rule"] = "מותאם ליום שנבחר: 31 רק בחודשים בני 31 יום, וללא פברואר"
        elif spec.generator:
            rule = GENERATOR_RULES[spec.generator]
            if archetype_id == "departure":
                rule += "; רכבת לילה נדגמת בשעות 20:00–04:59 וסיומת בוקר בשעות 05:00–11:59"
            item.update(kind="generator", name=spec.generator, rule=rule)
        else:
            item.update(kind="range", lower=spec.lower, upper=spec.upper,
                        rule=("אורכי מספרי בתים לבחירה ומשקל ערכי גבול" if spec.key == "house"
                              else "דגימת טווח לפי אורך ספרות, עם משקל ערכי גבול"))
            if spec.key == "house":
                item["rule"] += "; ברירת מחדל 1–3 ספרות, 4–5 לבדיקת מאמץ בלבד"
            elif spec.key == "apartment" and archetype_id in {"delivery", "slash_address"}:
                item["rule"] += "; בדגימה רגילה לכל היותר 120"
            elif spec.key == "quantity" and archetype_id == "purchase":
                item["rule"] += "; מגבלות לפי שם העצם: ריהוט עד 6, מוצרים בני־קיימא עד 12, מזון עד 20, מתכלים קטנים עד 30"
            elif spec.key == "quantity" and archetype_id == "approximate":
                item["rule"] += "; בדגימה עיגול לכפולות של 5/10/50/500 לפי גודל"
            elif spec.key == "kilometers" and archetype_id == "distance":
                item["rule"] += "; מסלולי הליכה וריצה מקומיים מוגבלים עד 50 ק״מ"
        sampling.append(item)
    if archetype_id == "numeric_calendar":
        sampling.append({"slot": "spoken_style", "kind": "pool", "values": [
            "לשמיני", "לאוגוסט"], "when": None, "rule": "שני סגנונות יומיומיים בהסתברות שווה"})
    examples = []
    for index in range(3):
        values = sample(archetype_id, random.Random(f"inspect:{archetype_id}:{index}"))
        frames = compatible_frames(archetype_id, values)
        start, end, _ = frames[(index * max(1, len(frames) // 3)) % len(frames)]
        pair = render(archetype_id, values, seed=index, context=(
            start, end), continuation=index)
        examples.append({"digits": pair["digits"], "cardinal": pair["cardinal"],
                         "alignments": [
                             {"slot": a["slot"], "written": a["digits_text"],
                              "spoken": a["cardinal_text"], "reading": a["reading"]}
                             for a in pair["alignments"]
                         ],
                         "length": ("קצר", "בינוני", "ארוך")[index]})
    group_values = sample(archetype_id, random.Random(f"inspect:groups:{archetype_id}"))
    if archetype_id in {"full_date", "slash_date"}:
        variants = [{**group_values, "year": year} for year in (1948, 2026, 2030)]
    elif archetype_id == "purchase":
        variants = [
            {**group_values, "noun": {"singular": "מגבת", "plural": "מגבות", "gender": "f"}, "quantity": 2},
            {**group_values, "noun": {"singular": "שולחן", "plural": "שולחנות", "gender": "m"}, "quantity": 2},
        ]
    elif archetype_id == "approximate":
        variants = [
            {**group_values, "noun": {"singular": "עגבנייה", "plural": "עגבניות", "gender": "f"}, "quantity": 10},
            {**group_values, "noun": {"singular": "עגבנייה", "plural": "עגבניות", "gender": "f"}, "quantity": 500},
        ]
    elif archetype_id == "departure":
        variants = [{**group_values, "minute_of_day": m} for m in (4 * 60, 6 * 60, 10 * 60, 14 * 60, 22 * 60)]
    elif archetype_id == "meeting_minute":
        variants = [{**group_values, "minute_of_day": m} for m in (8 * 60 + 12, 15 * 60 + 12)]
    elif archetype_id == "numeric_calendar":
        variants = [{**group_values, "month_number": m} for m in (4, 6)]
    elif archetype_id == "score":
        variants = [{**group_values, "score": s} for s in ("3:0", "0:0")]
    elif archetype_id == "age_range":
        variants = [{**group_values, "age_range": r} for r in ("6–12", "8–14", "12–18", "18–25")]
    elif archetype_id == "distance":
        variants = [{**group_values, "kilometers": k} for k in (15, 120)]
    else:
        variants = [group_values]
    groups = list(dict.fromkeys(
        group for values in variants for group in frame_groups(archetype_id, values)
    ))
    return {
        "id": archetype_id, "title": archetype.title, "description": archetype.description,
        "template": _template(TEMPLATES[archetype_id]), "sampling": sampling,
        "quantity_buckets": ({name: {"nouns": list(names), "max": PURCHASE_LIMITS[name]}
                             for name, names in PURCHASE_BUCKET_NAMES.items()}
                            if archetype_id in {"purchase", "approximate"} else None),
        "starts": list(context.starts), "ends": list(context.ends),
        "frame_groups": [{"name": group.name, "starts": list(group.starts),
                          "ends": list(group.ends),
                          "continuations": list(group.continuations or CONTINUATIONS[archetype_id])}
                         for group in groups],
        "end_bank": bank_name, "end_users": end_users,
        "continuations": list(CONTINUATIONS[archetype_id]),
        "past_continuations": (list(PAST_DATE_CONTINUATIONS)
                               if archetype_id in {"full_date", "slash_date"} else None),
        "date_start_groups": ({"present_2020_2027": list(date_start_indices(2024)),
                               "historical_before_2020": list(date_start_indices(1948)),
                               "future_after_2027": list(date_start_indices(2030))}
                              if archetype_id in {"full_date", "slash_date"} else None),
        "continuation_users": list(clause_users),
        "continuation_weights": [
            100 * Counter(CONTINUATION_CHOICES)[index] // len(CONTINUATION_CHOICES)
            for index in range(len(CONTINUATIONS[archetype_id]))
        ],
        "formal_weight": DEFAULT_FORMAL_WEIGHTS.get(archetype_id),
        "examples": examples,
    }
