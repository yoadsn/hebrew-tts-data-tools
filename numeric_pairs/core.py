"""Sample semantic values once, then render both views and offsets together."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import random
from typing import Any

from .adapter import cardinal, clock_time, ordinal_feminine, ordinal_masculine
from .catalog import ARCHETYPES, BY_ID, CATALOG_VERSION, MONTH_MAX_DAYS, MONTH_NUMBERS, MONTHS, NOUNS, STREETS, PURCHASE_BUCKETS, PURCHASE_LIMITS
from .contexts import CONTEXTS, CONTINUATIONS, compatible_frames, continuation_for
from .phone_formats import sample_phone, spoken_phone, validate_phone
from .variants import DEFAULT_FORMAL_WEIGHTS, resolve_weights
import re

RENDERER_VERSION = "19"
CONTINUATION_CHOICES = (0, 0, 0, 1, 1, 1, 1, 2, 2, 2)

GENERAL_FRACTION_SPOKEN = {
    "1/3": "שליש",
    "2/3": "שני שלישים",
    "1/4": "רבע",
    "3/4": "שלושה רבעים",
    "1/5": "חמישית",
    "2/5": "שתי חמישיות",
    "3/5": "שלוש חמישיות",
    "4/5": "ארבע חמישיות",
    "1/6": "שישית",
    "1/8": "שמינית",
    "3/8": "שלוש שמיניות",
    "5/8": "חמש שמיניות",
    "1/10": "עשירית",
    "3/10": "שלוש עשיריות",
}

AIRLINE_CODE_SPOKEN = {
    "BA": "בי איי",
    "AF": "איי אף",
    "LH": "אל אייץ'",
    "DL": "די אל",
    "UA": "יו איי",
    "TK": "טי קיי",
    "LX": "אל איקס",
    "KL": "קיי אל",
}

LATIN_LETTER_SPOKEN = {
    "A": "איי", "B": "בי", "C": "סי", "D": "די", "E": "אי", "F": "אף", "G": "ג'י",
    "H": "אייץ'", "I": "איי", "J": "ג'יי", "K": "קיי", "L": "אל", "M": "אם", "N": "אן",
    "O": "או", "P": "פי", "Q": "קיו", "R": "אר", "S": "אס", "T": "טי", "U": "יו",
    "V": "וי", "W": "דאבליו", "X": "איקס", "Y": "ואי", "Z": "זד",
}
_PASSPORT_LETTERS = tuple(LATIN_LETTER_SPOKEN)
_CARD_PREFIXES = ("4580", "4111", "5326", "5189", "4581", "5299", "4242", "5500")
_INTL_PHONE_TEMPLATES = (
    # (country_code, area_choices, mid_len, end_len)
    ("1", ("212", "310", "415", "305", "617", "312"), 3, 4),
    ("44", ("20", "161", "113", "131"), 4, 4),
    ("49", ("30", "40", "89", "221"), 4, 4),
    ("33", ("1", "4", "6"), 3, 4),
    ("34", ("91", "93", "96"), 3, 4),
    ("39", ("02", "06", "011"), 3, 4),
    ("61", ("2", "3", "7"), 4, 4),
)


@dataclass(frozen=True)
class Fragment:
    digits: str
    cardinal: str
    slot: str | None = None
    kind: str | None = None
    value: int | str | None = None
    reading: str | None = None


@dataclass(frozen=True)
class SampleSpec:
    """A fixed pool or a dynamically sampled integer, optionally gated by another slot."""

    key: str
    pool: tuple[Any, ...] = ()
    lower: int = 0
    upper: int = 0
    when: str | None = None
    generator: str | None = None


@dataclass(frozen=True)
class Literal:
    value: str


@dataclass(frozen=True)
class ValueRef:
    key: str


@dataclass(frozen=True)
class NumberRef:
    key: str


@dataclass(frozen=True)
class OrdinalRef:
    key: str


@dataclass(frozen=True)
class ClockRef:
    key: str


@dataclass(frozen=True)
class PercentRef:
    key: str


@dataclass(frozen=True)
class PhoneRef:
    key: str


@dataclass(frozen=True)
class DomainRef:
    """A typed numeric expression with an archetype-specific reading policy."""

    kind: str


@dataclass(frozen=True)
class QuantityRef:
    approximate: bool = False


@dataclass(frozen=True)
class OptionalGroup:
    condition: str
    parts: tuple[Any, ...]


# Archetype definitions are declarative. Adding a new sentence architecture only
# requires a tuple of sampling rules and a tree of literal/typed/optional pieces.
SAMPLERS = {
    "address": (SampleSpec("street", STREETS), SampleSpec("house", lower=1, upper=99999)),
    "delivery": (SampleSpec("street", STREETS), SampleSpec("house", lower=1, upper=99999),
                  SampleSpec("include_apartment", (True, False)),
                  SampleSpec("apartment", lower=1, upper=120, when="include_apartment")),
    "purchase": (SampleSpec("noun", tuple(asdict(noun) for noun in NOUNS)),
                  SampleSpec("quantity", lower=2, upper=30)),
    "bulk_purchase": (SampleSpec("noun", tuple(asdict(noun) for noun in NOUNS)),
                      SampleSpec("quantity", lower=31, upper=9999)),
    "approximate": (SampleSpec("noun", tuple(asdict(noun) for noun in NOUNS)),
                    SampleSpec("quantity", lower=2, upper=9999)),
    "floor": (SampleSpec("floor", lower=1, upper=10),),
    "departure": (SampleSpec("minute_of_day", generator="clock"),),
    "survey": (SampleSpec("percent", lower=1, upper=100),),
    "mobile": (SampleSpec("phone", generator="mobile"),),
    "ranking": (SampleSpec("rank", lower=1, upper=10),),
    "age": (SampleSpec("age", lower=18, upper=99),),
    "year": (SampleSpec("year", lower=1948, upper=2026),),
    "calendar": (SampleSpec("day", lower=1, upper=28), SampleSpec("month", MONTHS)),
    "duration_half": (SampleSpec("duration", ("1.5", "2.5", "3.5", "4.5")),),
    "fraction": (SampleSpec("fraction", ("1/2", "3/4")),),
    "decimal_temp": (SampleSpec("whole", lower=10, upper=45),
                     SampleSpec("fractional", tuple(str(i) for i in range(1, 10)) + ("25", "75"))),
    "negative_temp": (SampleSpec("magnitude", lower=2, upper=20),),
    "money": (SampleSpec("amount", lower=2, upper=999),),
    "weight": (SampleSpec("weight", lower=2, upper=99),),
    "card_suffix": (SampleSpec("suffix", generator="four_digits"),),
    "road_route": (SampleSpec("road", lower=1, upper=99), SampleSpec("route", lower=1, upper=999)),
    "version": (SampleSpec("major", lower=1, upper=20), SampleSpec("minor", lower=0, upper=9),
                SampleSpec("patch", lower=0, upper=9)),
    "score": (SampleSpec("score", ("3:0", "2:1", "4:2", "1:0", "0:0")),),
    "age_range": (SampleSpec("age_range", ("6–12", "8–14", "12–18", "18–25")),),
    "percent_half": (SampleSpec("whole_percent", lower=2, upper=20),),
    "full_date": (SampleSpec("day", lower=1, upper=28), SampleSpec("month", MONTHS),
                  SampleSpec("year", (1948, 2001, 2024, 2026, 2027, 2028, 2030))),
    "money_cents": (SampleSpec("shekels", lower=2, upper=99),
                    SampleSpec("agorot", (10, 25, 50, 90))),
    "distance": (SampleSpec("kilometers", lower=2, upper=999),),
    "section": (SampleSpec("section", lower=1, upper=20), SampleSpec("subsection", lower=1, upper=9)),
    "postal": (SampleSpec("postal_code", generator="postal_code"),),
    "infant_age": (SampleSpec("age_years", ("1.5",)),),
    "decade": (SampleSpec("decade", (50, 60, 70, 80, 90)),),
    "stopwatch_seconds": (SampleSpec("seconds", lower=2, upper=59),
                          SampleSpec("hundredths", lower=10, upper=99)),
    "area": (SampleSpec("square_meters", lower=20, upper=200),),
    "map_scale": (SampleSpec("scale", (50000, 100000)),),
    "maximum_attendees": (SampleSpec("capacity", lower=2, upper=200),),
    "pill_range": (SampleSpec("minimum", lower=2, upper=3), SampleSpec("maximum", lower=4, upper=6)),
    "opening_hours": (SampleSpec("start_hour", (8, 9, 10)), SampleSpec("end_hour", (12, 13, 14))),
    "dollar_price": (SampleSpec("dollars", lower=2, upper=99),),
    "million_exact": (SampleSpec("number", generator="million_exact"),),
    "meeting_minute": (SampleSpec("minute_of_day", generator="minute_nonround"),),
    "card_full": (SampleSpec("card_number", generator="card_full"),),
    "international_phone": (SampleSpec("international_phone", generator="international_phone"),),
    "civil_id": (SampleSpec("civil_id", generator="civil_id"),),
    "passport_id": (SampleSpec("passport_id", generator="passport_id"),),
    "stopwatch_minute": (SampleSpec("minutes", lower=1, upper=4),
                          SampleSpec("seconds", lower=10, upper=59), SampleSpec("hundredths", lower=10, upper=99)),
    "euro_price": (SampleSpec("euros", lower=2, upper=999),),
    "data_plan": (SampleSpec("gigabytes", (20, 50, 100)), SampleSpec("megabits", (100, 500, 1000))),
    "bank_account": (SampleSpec("branch", (101, 630, 802)), SampleSpec("account", generator="demo_account")),
    "license_plate": (SampleSpec("plate", generator="demo_plate"),),
    "flight_number": (SampleSpec("flight", lower=101, upper=999),),
    "numeric_calendar": (SampleSpec("day", lower=1, upper=28), SampleSpec("month_number", (4, 6, 8, 10))),
    "slash_address": (SampleSpec("street", STREETS), SampleSpec("house", lower=1, upper=999),
                      SampleSpec("apartment", lower=1, upper=120)),
    "minimum_age": (SampleSpec("minimum_age", lower=18, upper=30),),
    "large_shekels": (SampleSpec("shekels_large", generator="large_shekels"),),
    "explicit_hundredths": (SampleSpec("seconds", lower=2, upper=59),
                             SampleSpec("hundredths", lower=10, upper=99)),
    "slash_date": (SampleSpec("day", lower=1, upper=28), SampleSpec("month", MONTHS),
                   SampleSpec("year", (1948, 2001, 2024, 2026, 2027, 2028, 2030))),
    "landline": (SampleSpec("phone", generator="landline"),),
    "local_landline": (SampleSpec("phone", generator="local_landline"),),
    "national_line": (SampleSpec("phone", generator="national_line"),),
    "israeli_international": (SampleSpec("phone", generator="israeli_international"),),
    "business_line": (SampleSpec("phone", generator="business_line"),),
    "plural_millions": (SampleSpec("millions_value", generator="plural_millions"),),
    "child_half_age": (SampleSpec("child_age", ("2.5", "3.5", "4.5", "5.5", "6.5")),),
    "month_end_date": (
        SampleSpec("day", (29, 30, 31)),
        SampleSpec("month", tuple(m for m in MONTHS if MONTH_MAX_DAYS[m] >= 29)),
    ),
    "midnight_time": (SampleSpec("midnight_minute", (*range(0, 21), 30)),),
    "general_fraction": (SampleSpec("general_fraction", tuple(GENERAL_FRACTION_SPOKEN)),),
    "multi_digit_decimal": (SampleSpec("decimal_value", generator="multi_digit_decimal"),),
    "airline_flight": (
        SampleSpec("carrier", tuple(AIRLINE_CODE_SPOKEN)),
        SampleSpec("flight", lower=101, upper=999),
    ),
}

TEMPLATES = {
    "address": (Literal("המשרד ממוקם ברחוב "), ValueRef("street"), Literal(" "), NumberRef("house")),
    "delivery": (Literal("החבילה נשלחה לרחוב "), ValueRef("street"), Literal(" "), NumberRef("house"),
                 OptionalGroup("include_apartment", (Literal(", דירה "), NumberRef("apartment")))),
    "purchase": (Literal("קניתי "), QuantityRef(), Literal(" היום.")),
    "bulk_purchase": (Literal("למחסן הזמנו "), QuantityRef(), Literal(".")),
    "approximate": (Literal("קניתי "), QuantityRef(approximate=True), Literal(" היום.")),
    "floor": (Literal("המשרד ממוקם בקומה "), OrdinalRef("floor"), Literal(".")),
    "departure": (Literal("הרכבת יוצאת בשעה "), ClockRef("minute_of_day"), Literal(".")),
    "survey": (Literal("בסקר, "), PercentRef("percent"), Literal(" מהמשיבים הסכימו.")),
    "mobile": (Literal("לתיאום תור התקשרו למספר "), PhoneRef("phone"), Literal(".")),
    "ranking": (Literal("השחקן דורג במקום "), DomainRef("ranking"), Literal(" בטורניר.")),
    "age": (Literal("הוא חוגג היום "), DomainRef("age"), Literal(".")),
    "year": (Literal("הסרט יצא לאקרנים בשנת "), DomainRef("year"), Literal(".")),
    "calendar": (Literal("אירוע ההשקה יתקיים "), DomainRef("calendar"), Literal(".")),
    "duration_half": (Literal("לקח לנו "), DomainRef("duration_half"), Literal(" להגיע לצפון.")),
    "fraction": (Literal("למתכון צריך להוסיף "), DomainRef("fraction"), Literal(" כוס סוכר.")),
    "decimal_temp": (Literal("הטמפרטורה שנמדדה הייתה "), DomainRef("decimal_temp"), Literal(" מעלות.")),
    "negative_temp": (Literal("הטמפרטורה בחרמון הייתה "), DomainRef("negative_temp"), Literal(" מעלות.")),
    "money": (Literal("המוצר עולה "), DomainRef("money"), Literal(".")),
    "weight": (Literal("החבילה שוקלת "), DomainRef("weight"), Literal(".")),
    "card_suffix": (Literal("החיוב בוצע בכרטיס המסתיים בספרות "), DomainRef("card_suffix"), Literal(".")),
    "road_route": (Literal("נסענו צפונה על כביש "), NumberRef("road"), Literal(" ומשם המשכנו בקו "), NumberRef("route"), Literal(".")),
    "version": (Literal("העדכון החדש הוא גרסה "), DomainRef("version"), Literal(".")),
    "score": (Literal("המשחק הסתיים בתוצאה "), DomainRef("score"), Literal(".")),
    "age_range": (Literal("הפעילות מיועדת לילדים בגילאי "), DomainRef("age_range"), Literal(".")),
    "percent_half": (Literal("הריבית עומדת על "), DomainRef("percent_half"), Literal(".")),
    "full_date": (Literal("האירוע נקבע "), DomainRef("full_date"), Literal(".")),
    "money_cents": (Literal("המוצר עולה "), DomainRef("money_cents"), Literal(".")),
    "distance": (Literal("המרחק בין הערים הוא "), DomainRef("distance"), Literal(".")),
    "section": (Literal("ההגבלות מפורטות תחת "), DomainRef("section"), Literal(".")),
    "postal": (Literal("כתובת המשלוח כוללת מיקוד "), DomainRef("postal"), Literal(".")),
    "infant_age": (Literal("התינוק כבר בן "), DomainRef("infant_age"), Literal(".")),
    "decade": (Literal("החברה הוקמה "), DomainRef("decade"), Literal(".")),
    "stopwatch_seconds": (Literal("השיא עומד על "), DomainRef("stopwatch_seconds"), Literal(".")),
    "area": (Literal("שטח הדירה הוא "), DomainRef("area"), Literal(".")),
    "map_scale": (Literal("המפה משורטטת בקנה מידה של "), DomainRef("map_scale"), Literal(".")),
    "maximum_attendees": (Literal("הקיבולת המרבית היא עד "), DomainRef("maximum_attendees"), Literal(" משתתפים.")),
    "pill_range": (Literal("קח "), DomainRef("pill_range"), Literal(" גלולות ביום.")),
    "opening_hours": (Literal("קבלת הקהל מתקיימת בין "), DomainRef("opening_hours"), Literal(".")),
    "dollar_price": (Literal("מחיר הכרטיס הוא "), DomainRef("dollar_price"), Literal(".")),
    "million_exact": (Literal("המערכת עיבדה "), DomainRef("million_exact"), Literal(" רשומות.")),
    "meeting_minute": (Literal("הפגישה תתחיל מחר "), DomainRef("meeting_minute"), Literal(".")),
    "card_full": (Literal("מספר כרטיס האשראי לחיוב הוא "), DomainRef("card_full"), Literal(".")),
    "international_phone": (Literal("מוקד השירות בחו״ל זמין במספר "), DomainRef("international_phone"), Literal(".")),
    "civil_id": (Literal("מספר תעודת הזהות שנמסר הוא "), DomainRef("civil_id"), Literal(".")),
    "passport_id": (Literal("מספר הדרכון של הנוסע הוא "), DomainRef("passport_id"), Literal(".")),
    "stopwatch_minute": (Literal("הזמן המדוד במקצה היה "), DomainRef("stopwatch_minute"), Literal(".")),
    "euro_price": (Literal("המוצר עולה "), DomainRef("euro_price"), Literal(".")),
    "data_plan": (Literal("חבילת הגלישה כוללת "), DomainRef("data_plan"), Literal(".")),
    "bank_account": (Literal("ההעברה הבנקאית בוצעה "), DomainRef("bank_account"), Literal(".")),
    "license_plate": (Literal("מספר הרכב המעודכן בתו החניה הוא "), DomainRef("license_plate"), Literal(".")),
    "flight_number": (Literal("הטיסה שמספרה "), DomainRef("flight_number"), Literal(" תמריא בזמן.")),
    "numeric_calendar": (Literal("אנחנו טסים לחופשה "), DomainRef("numeric_calendar"), Literal(".")),
    "slash_address": (Literal("אני גר ברחוב "), DomainRef("slash_address"), Literal(".")),
    "minimum_age": (Literal("המילגה מיועדת לבני "), DomainRef("minimum_age"), Literal(" ומעלה.")),
    "large_shekels": (Literal("עלות השיפוץ הייתה "), DomainRef("large_shekels"), Literal(".")),
    "explicit_hundredths": (Literal("השיא המדויק עומד על "), DomainRef("explicit_hundredths"), Literal(".")),
    "slash_date": (Literal("הפגישה נקבעה "), DomainRef("slash_date"), Literal(".")),
    "landline": (Literal("מזכירות הסניף עונה בטלפון הקווי "), DomainRef("landline"), Literal(".")),
    "local_landline": (Literal("באזור החיוג המקומי ניתן להתקשר אל "), DomainRef("local_landline"), Literal(".")),
    "national_line": (Literal("מרכזיית החברה פועלת במספר "), DomainRef("national_line"), Literal(".")),
    "israeli_international": (Literal("לחיוג לישראל מחו״ל יש להתקשר למספר "), DomainRef("israeli_international"), Literal(".")),
    "business_line": (Literal("מוקד שירות הלקוחות הארצי עונה במספר "), DomainRef("business_line"), Literal(".")),
    "plural_millions": (Literal("בשדה התעופה עברו השנה "), DomainRef("plural_millions"), Literal(" נוסעים.")),
    "child_half_age": (Literal("הילד כבר בן "), DomainRef("child_half_age"), Literal(".")),
    "month_end_date": (Literal("שנת הכספים מסתיימת "), DomainRef("month_end_date"), Literal(".")),
    "midnight_time": (Literal("גיבוי המערכת הלילי מתחיל "), DomainRef("midnight_time"), Literal(".")),
    "general_fraction": (Literal("הצוות כבר השלים "), DomainRef("general_fraction"), Literal(" מהמשימות.")),
    "multi_digit_decimal": (Literal("מקדם ההמרה נקבע על "), DomainRef("multi_digit_decimal"), Literal(".")),
    "airline_flight": (Literal("הטיסה הבינלאומית שמספרה "), DomainRef("airline_flight"), Literal(" נחתה בזמן.")),
}


def text(value: str) -> Fragment:
    return Fragment(value, value)


def number(slot: str, value: int, gender: str = "f", prefix: str = "") -> Fragment:
    return Fragment(prefix + "-" + str(value) if prefix else str(value),
                    prefix + cardinal(value, gender), slot, "cardinal", value, "cardinal")


HEBREW_DUAL_NOUNS: dict[str, str] = {
    "יום": "יומיים",
    "ימים": "יומיים",
    "חודש": "חודשיים",
    "חודשים": "חודשיים",
    "שבוע": "שבועיים",
    "שבועות": "שבועיים",
    "שנה": "שנתיים",
    "שנים": "שנתיים",
    "שעה": "שעתיים",
    "שעות": "שעתיים",
    "פעם": "פעמיים",
    "פעמים": "פעמיים",
    "מאה": "מאתיים",
    "מאות": "מאתיים",
    "אלף": "אלפיים",
    "אלפים": "אלפיים",
}


def quantity(value: int, noun: dict[str, str], *, approximate: bool = False) -> Fragment:
    singular, plural, gender = noun["singular"], noun["plural"], noun["gender"]
    if value == 1:
        if approximate:
            raise ValueError("Approximation is restricted to plural quantities")
        return Fragment(f"1 {singular}", f"{singular} אחת" if gender == "f" else f"{singular} אחד",
                        "quantity", "quantity", value, "cardinal-after-noun")
    dual = (HEBREW_DUAL_NOUNS.get(plural) or HEBREW_DUAL_NOUNS.get(singular)) if value == 2 else None
    pfx = "כ" if approximate else ""
    if dual:
        return Fragment(f"{pfx + '-' if pfx else ''}{value} {plural}",
                        f"{pfx}{dual}", "quantity", "approximate_quantity" if approximate else "quantity",
                        value, "hebrew-dual")
    spoken = cardinal(value, gender, construct=True)
    return Fragment(f"{pfx + '-' if pfx else ''}{value} {plural}",
                    f"{pfx}{spoken} {plural}", "quantity", "approximate_quantity" if approximate else "quantity",
                    value, "construct-cardinal")


def ordinal(value: int) -> Fragment:
    return Fragment(f"ה-{value}", "ה" + ordinal_feminine(value), "floor", "ordinal", value, "feminine-ordinal")


def clock(minutes: int) -> Fragment:
    hour, minute = divmod(minutes, 60)
    written = f"{hour:02d}:{minute:02d}"
    return Fragment(written, clock_time(hour, minute), "minute_of_day", "clock_time", written, "12-hour-no-daypart")


def percentage(value: int) -> Fragment:
    spoken = "אחוז אחד" if value == 1 else cardinal(value, "m", construct=True) + " אחוזים"
    return Fragment(f"{value}%", spoken, "percent", "percentage", value, "masculine-percent")


def phone_number(value: str) -> Fragment:
    spoken, _ = spoken_phone("mobile", value)
    return Fragment(value, spoken, "phone", "identifier", value, "digit-by-digit-3-3-4")


def spoken_digits(value: str, groups: tuple[int, ...] = ()) -> str:
    """Read a synthetic identifier as digits; commas delimit known groups."""
    if not groups:
        groups = (len(value),)
    if sum(groups) != len(value):
        raise ValueError("Identifier groups must cover every digit")
    chunks, offset = [], 0
    for length in groups:
        chunks.append(" ".join(cardinal(int(d), "f") for d in value[offset:offset + length]))
        offset += length
    return ", ".join(chunks)


def valid_civil_id(value: str) -> bool:
    """Israeli ID checksum; generated test identifiers must fail this check."""
    if len(value) != 9 or not value.isascii() or not value.isdigit():
        return False
    return sum(sum(divmod(int(digit) * (1 + i % 2), 10)) for i, digit in enumerate(value)) % 10 == 0


def valid_luhn(value: str) -> bool:
    """Standard Luhn payment-card checksum; generated full cards fail this check."""
    if not value or not value.isascii() or not value.isdigit():
        return False
    total = 0
    for idx, ch in enumerate(reversed(value)):
        digit = int(ch)
        if idx % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _sample_passport_id(rng: random.Random) -> str:
    """Sample realistic ICAO 8–9 char passport numbers (Israeli 8-digit + international formats)."""
    style = rng.choices(
        ("il_8d", "num_9d", "two_let", "one_let", "mixed"),
        weights=(35, 15, 20, 20, 10),
        k=1,
    )[0]
    if style == "il_8d":
        return str(rng.randint(1, 9)) + "".join(str(rng.randrange(10)) for _ in range(7))
    if style == "num_9d":
        return str(rng.randint(1, 9)) + "".join(str(rng.randrange(10)) for _ in range(8))
    if style == "two_let":
        d_len = rng.choice((6, 7))
        return "".join(rng.choice(_PASSPORT_LETTERS) for _ in range(2)) + "".join(str(rng.randrange(10)) for _ in range(d_len))
    if style == "one_let":
        d_len = rng.choice((7, 8))
        return rng.choice(_PASSPORT_LETTERS) + "".join(str(rng.randrange(10)) for _ in range(d_len))
    # Mixed alphanumeric 9-char (e.g. France 12AB34567 or Germany C01X00T47)
    if rng.random() < 0.5:
        return (
            "".join(str(rng.randrange(10)) for _ in range(2))
            + "".join(rng.choice(_PASSPORT_LETTERS) for _ in range(2))
            + "".join(str(rng.randrange(10)) for _ in range(5))
        )
    return (
        rng.choice(_PASSPORT_LETTERS)
        + "".join(str(rng.randrange(10)) for _ in range(2))
        + rng.choice(_PASSPORT_LETTERS)
        + "".join(str(rng.randrange(10)) for _ in range(2))
        + rng.choice(_PASSPORT_LETTERS)
        + "".join(str(rng.randrange(10)) for _ in range(2))
    )


def _spoken_passport_id(value: str) -> tuple[str, str]:
    if value.isdigit():
        groups = (4, 4) if len(value) == 8 else (3, 3, 3)
        return spoken_digits(value, groups), f"icao-digits-{len(value)}"
    tokens = [
        LATIN_LETTER_SPOKEN[ch] if ch.isalpha() else cardinal(int(ch), "f")
        for ch in value
    ]
    return " ".join(tokens), "icao-alphanumeric-passport"


def _sample_international_phone(rng: random.Random) -> str:
    cc, areas, mid_len, end_len = rng.choice(_INTL_PHONE_TEMPLATES)
    area = rng.choice(areas)
    mid = str(rng.randint(2, 9)) + "".join(str(rng.randrange(10)) for _ in range(mid_len - 1))
    end = "".join(str(rng.randrange(10)) for _ in range(end_len))
    return f"+{cc} {area}-{mid}-{end}"


def domain_fragment(kind: str, values: dict[str, Any], variant: str = "natural") -> Fragment:
    """Each policy owns its complete written/spoken expression and offsets."""
    if variant not in {"natural", "formal"}:
        raise ValueError(f"Unknown reading variant: {variant}")
    if kind == "ranking":
        value = values["rank"]
        return Fragment(f"ה-{value}", "ה" + ordinal_masculine(value), "rank", "ordinal", value, "masculine-ordinal")
    if kind == "age":
        value = values["age"]
        return Fragment(str(value), cardinal(value, "f"), "age", "age", value, "feminine-age")
    if kind == "year":
        value = values["year"]
        return Fragment(str(value), cardinal(value, "f"), "year", "year", value, "feminine-year")
    if kind == "calendar":
        day, month = values["day"], values["month"]
        return Fragment(f"ב-{day} ב{month}", f"ב{cardinal(day, 'm')} ב{month}", "day", "date", day, "masculine-day-named-month")
    if kind == "duration_half":
        value = values["duration"]
        hours = int(value[0])
        if variant == "formal":
            spoken = {1: "שעה וחצי", 2: "שעתיים וחצי"}.get(hours, cardinal(hours, "f", construct=True) + " שעות וחצי")
        else:
            spoken = {1: "שעה וחצי", 2: "שעתיים וחצי"}.get(hours, cardinal(hours, "f") + " וחצי שעות")
        return Fragment(f"{value} שעות", spoken, "duration", "duration", value, f"{variant}-hours-and-half")
    if kind == "fraction":
        value = values["fraction"]
        spoken = {"1/2": "חצי", "3/4": "שלושת רבעי"}[value]
        return Fragment(value, spoken, "fraction", "fraction", value, "curated-fraction")
    if kind == "decimal_temp":
        fractional = values["fractional"]
        value = f"{values['whole']}.{fractional}"
        whole_spoken = cardinal(values["whole"], "f")
        if variant == "natural" and fractional in {"5", "25", "75"}:
            spoken = whole_spoken + {"5": " וחצי", "25": " ורבע", "75": " ושלושת רבעי"}[fractional]
            reading = "natural-fractional-temperature"
        else:
            fractional_spoken = (cardinal(int(fractional), "f") if len(fractional) == 1
                                 else " ".join(cardinal(int(d), "f") for d in fractional))
            spoken = whole_spoken + " נקודה " + fractional_spoken
            reading = "formal-point-temperature" if variant == "formal" else "point-temperature"
        return Fragment(value, spoken, "temperature", "decimal", value, reading)
    if kind == "negative_temp":
        value = values["magnitude"]
        spoken = "מינוס שתי" if value == 2 else "מינוס " + cardinal(value, "f")
        return Fragment(f"-{value}", spoken, "temperature", "signed", -value, "minus-feminine")
    if kind == "money":
        value = values["amount"]
        return Fragment(f"{value} ₪", cardinal(value, "m", construct=True) + " שקלים", "amount", "money", value, "masculine-shekels")
    if kind == "weight":
        value = values["weight"]
        return Fragment(f"{value} ק\"ג", cardinal(value, "m", construct=True) + " קילוגרמים", "weight", "measurement", value, "masculine-kilograms")
    if kind == "card_suffix":
        value = values["suffix"]
        return Fragment(value, " ".join(cardinal(int(d), "f") for d in value), "suffix", "identifier", value, "digit-by-digit")
    if kind == "version":
        components = (values["major"], values["minor"], values["patch"])
        value = ".".join(map(str, components))
        separator = " נקודה " if variant == "formal" else " "
        return Fragment(value, separator.join(cardinal(part, "f") for part in components), "version", "version", value, f"{variant}-version-components")
    if kind == "score":
        value = values["score"]
        return Fragment(value, " ".join(cardinal(int(part), "f") for part in value.split(":")), "score", "score", value, "score-sides")
    if kind == "age_range":
        value = values["age_range"]
        start, end = (int(part) for part in value.split("–"))
        return Fragment(value, cardinal(start, "f") + " עד " + cardinal(end, "f"), "age_range", "range", value, "feminine-age-range")
    if kind == "percent_half":
        value = f"{values['whole_percent']}.5%"
        spoken = cardinal(values["whole_percent"], "m") + " וחצי אחוזים"
        return Fragment(value, spoken, "percent", "percentage", value, "masculine-percent-half")
    if kind == "full_date":
        day, month, year = values["day"], values["month"], values["year"]
        value = f"{day}.{MONTH_NUMBERS[month]}.{year}"
        year_spoken = cardinal(year, "f")
        spoken = (f"ל{cardinal(day, 'm')} ב{month} שנת {year_spoken}" if variant == "formal"
                  else f"ל{cardinal(day, 'm')} ב{month}, {year_spoken}")
        return Fragment("ל-" + value, spoken, "full_date", "date", value, f"{variant}-day-month-year")
    if kind == "money_cents":
        shekels, agorot = values["shekels"], values["agorot"]
        value = f"{shekels}.{agorot:02d}"
        if variant == "natural" and agorot == 50:
            spoken = cardinal(shekels, "f") + " וחצי שקל"
            reading = "natural-half-shekel-price"
        else:
            spoken = cardinal(shekels, "m", construct=True) + " שקלים ו" + cardinal(agorot, "f", construct=True) + " אגורות"
            reading = "formal-shekels-and-agorot" if variant == "formal" else "shekels-and-agorot"
        return Fragment(value + " ₪", spoken, "money", "money", value, reading)
    if kind == "distance":
        value = values["kilometers"]
        return Fragment(f"{value} ק\"מ", cardinal(value, "m", construct=True) + " קילומטרים", "kilometers", "measurement", value, "masculine-kilometers")
    if kind == "section":
        major, minor = values["section"], values["subsection"]
        value = f"{major}.{minor}"
        spoken_major = "אחד" if major == 1 else cardinal(major, "f")
        spoken_minor = "אחד" if minor == 1 else cardinal(minor, "f")
        spoken = f"סעיף {spoken_major}, " + ("תת-סעיף " if variant == "formal" else "") + spoken_minor
        return Fragment("סעיף " + value, spoken, "section", "document", value, f"{variant}-hierarchical-section")
    if kind == "postal":
        value = values["postal_code"]
        groups = (2, 5) if len(value) == 7 else ()
        return Fragment(value, spoken_digits(value, groups), "postal_code", "identifier", value,
                        "digit-by-digit-2-5" if groups else "digit-by-digit")
    if kind == "infant_age":
        value = values["age_years"]
        return Fragment(value, "שנה וחצי", "age_years", "age", value, "year-and-half")
    if kind == "decade":
        value = values["decade"]
        return Fragment(f"בשנות ה-{value}", f"בשנות ה{cardinal(value, 'm')}",
                        "decade", "date", value, "decade")
    if kind == "stopwatch_seconds":
        seconds, hundredths = values["seconds"], values["hundredths"]
        value = f"{seconds}.{hundredths:02d}"
        decimal = value.split(".")[1].rstrip("0")
        spoken = f"{cardinal(seconds, 'f')} נקודה {cardinal(int(decimal), 'f')} שניות"
        return Fragment(value + " שניות", spoken, "stopwatch", "duration", value, "spoken-decimal-seconds")
    if kind == "area":
        value = values["square_meters"]
        natural = variant == "natural" and value > 10
        spoken = (cardinal(value, "m") + " מטר רבוע" if natural
                  else cardinal(value, "m", construct=True) + " מטרים רבועים")
        return Fragment(f'{value} מ"ר', spoken, "square_meters", "measurement", value,
                        "natural-square-meter" if natural else "square-meters")
    if kind == "map_scale":
        value = values["scale"]
        return Fragment(f"1:{value:,}", "אחד ל" + cardinal(value, "f"),
                        "scale", "ratio", f"{value:,}", "one-to-scale")
    if kind == "maximum_attendees":
        value = values["capacity"]
        return Fragment(str(value), cardinal(value, "m", construct=True),
                        "capacity", "limit", value, "maximum-masculine")
    if kind == "pill_range":
        low, high = values["minimum"], values["maximum"]
        value = f"{low}-{high}"
        return Fragment(value, f"בין {cardinal(low, 'f')} ל{cardinal(high, 'f')}",
                        "pill_range", "range", value, "between-feminine")
    if kind == "opening_hours":
        start, end = values["start_hour"], values["end_hour"]
        value = f"{start}:00–{end}:00"
        return Fragment(value, f"{cardinal(start, 'f')} ל{cardinal(end % 12 or 12, 'f')}",
                        "hours", "time_range", value, "between-12-hour-clock")
    if kind == "dollar_price":
        value = values["dollars"]
        return Fragment(f"${value}", cardinal(value, "m", construct=True) + " דולר",
                        "dollars", "money", value, "masculine-dollars")
    if kind == "million_exact":
        value = values["number"]
        written = f"{value:,}"
        thousands, remainder = divmod(value % 1_000_000, 1000)
        head = ", ".join(part for part in (
            "מיליון", cardinal(thousands * 1000, "f") if thousands else "") if part)
        if not remainder:
            spoken = head
        elif remainder >= 100:
            spoken = f"{head}, {cardinal(remainder, 'f')}"
        else:
            tail = "שתי" if remainder == 2 else cardinal(remainder, "f")
            spoken = f"{head} ו{tail}"
        return Fragment(written, spoken, "number", "large_quantity", written, "million-group-pauses")
    if kind == "meeting_minute":
        hour, minute = divmod(values["minute_of_day"], 60)
        written = f"{hour:02d}:{minute:02d}"
        return Fragment("ב-" + written, "ב" + clock_time(hour, minute),
                        "minute_of_day", "clock_time", written, "nonround-clock")
    if kind == "card_full":
        digits = values["card_number"]
        written = "-".join(digits[i:i + 4] for i in range(0, 16, 4))
        return Fragment(written, spoken_digits(digits, (4, 4, 4, 4)),
                        "card_number", "identifier", written, "synthetic-card-4-4-4-4")
    if kind == "international_phone":
        value = values["international_phone"]
        parts = re.split(r"[ -]+", value.lstrip("+"))
        digits = "".join(parts)
        groups = tuple(len(part) for part in parts)
        return Fragment(value, "פלוס " + spoken_digits(digits, groups),
                        "international_phone", "identifier", value,
                        "intl-phone-" + "-".join(str(g) for g in groups))
    if kind == "civil_id":
        value = values["civil_id"]
        return Fragment(value, spoken_digits(value, (3, 3, 3)),
                        "civil_id", "identifier", value, "invalid-checksum-3-3-3")
    if kind == "passport_id":
        value = values["passport_id"]
        spoken, reading = _spoken_passport_id(value)
        return Fragment(value, spoken, "passport_id", "identifier", value, reading)
    if kind == "stopwatch_minute":
        minutes, seconds, hundredths = (values[key] for key in ("minutes", "seconds", "hundredths"))
        written = f"{minutes}:{seconds:02d}.{hundredths:02d}"
        spoken_minutes = "דקה אחת" if minutes == 1 else cardinal(minutes, "f", construct=True) + " דקות"
        spoken = f"{spoken_minutes}, {cardinal(seconds, 'f')} שניות ו{cardinal(hundredths, 'f')} מאיות"
        return Fragment(written, spoken, "stopwatch", "duration", written, "minute-second-hundredth")
    if kind == "euro_price":
        value = values["euros"]
        return Fragment(f"{value} €", cardinal(value, "m", construct=True) + " אירו",
                        "euros", "money", value, "masculine-euros")
    if kind == "data_plan":
        gigabytes, megabits = values["gigabytes"], values["megabits"]
        written = f"{gigabytes}GB במהירות {megabits}Mb"
        spoken = f"{cardinal(gigabytes, 'f')} ג'יגה-בייט במהירות {cardinal(megabits, 'f')} מגה ביט"
        return Fragment(written, spoken, "data_plan", "measurement", written, "data-units")
    if kind == "bank_account":
        branch, account = values["branch"], values["account"]
        written = f"לסניף {branch}, חשבון {account}"
        spoken = f"לסניף {cardinal(branch, 'f')}, חשבון {spoken_digits(account, (3, 3))}"
        return Fragment(written, spoken, "account", "identifier", written, "synthetic-bank-3-3")
    if kind == "license_plate":
        value = values["plate"]
        parts = value.split("-")
        groups = tuple(len(part) for part in parts)
        return Fragment(value, spoken_digits("".join(parts), groups),
                        "plate", "identifier", value,
                        "israeli-plate-" + "-".join(str(g) for g in groups))
    if kind == "flight_number":
        value = values["flight"]
        return Fragment(f"LY{value}", "אל ואיי " + spoken_digits(str(value)),
                        "flight", "identifier", value, "ly-digit-flight")
    if kind == "numeric_calendar":
        day, month = values["day"], values["month_number"]
        written = f"{day}.{month}"
        spoken_month = {4: "רביעי", 6: "שישי", 8: "שמיני", 10: "עשירי"}[month]
        month_name = MONTHS[month - 1]
        day_spoken = ordinal_masculine(day) if day <= 10 else cardinal(day, "f")
        if variant == "formal":
            spoken, reading = f"ב{cardinal(day, 'm')} ב{month_name}", "formal-named-month"
        elif values.get("spoken_style", "ordinal") == "named":
            spoken, reading = f"ב{day_spoken} ל{month_name}", "natural-named-month"
        else:
            spoken, reading = f"ב{day_spoken} ל{spoken_month}", "natural-ordinal-month"
        return Fragment("ב-" + written, spoken, "day", "date", written, reading)
    if kind == "slash_address":
        street, house, apartment = values["street"], values["house"], values["apartment"]
        written = f"{street} {house}/{apartment}"
        spoken = f"{street} {cardinal(house, 'f')}, דירה {cardinal(apartment, 'f')}"
        return Fragment(written, spoken, "address", "address", written, "house-slash-apartment")
    if kind == "minimum_age":
        value = values["minimum_age"]
        return Fragment(str(value), cardinal(value, "f"), "minimum_age", "limit", value, "minimum-feminine-age")
    if kind == "large_shekels":
        value = values["shekels_large"]
        written = f"{value:,} ₪"
        natural = variant == "natural"
        spoken = (cardinal(value, "m") + (" שקלים" if value % 10 == 1 else " שקל") if natural
                  else cardinal(value, "m", construct=True) + " שקלים")
        return Fragment(written, spoken, "shekels_large", "money", f"{value:,}",
                        "natural-large-shekel" if natural else "formal-large-shekels")
    if kind == "explicit_hundredths":
        seconds, hundredths = values["seconds"], values["hundredths"]
        written = f"{seconds} שניות ו-{hundredths} מאיות"
        spoken_seconds = "שתי" if seconds == 2 else cardinal(seconds, "f")
        spoken_hundredths = "שתי" if hundredths == 2 else cardinal(hundredths, "f")
        spoken = f"{spoken_seconds} שניות ו{spoken_hundredths} מאיות"
        return Fragment(written, spoken, "hundredths", "duration", written, "explicit-hundredths")
    if kind == "slash_date":
        day, month, year = values["day"], values["month"], values["year"]
        written = f"{day}/{MONTH_NUMBERS[month]}/{year}"
        spoken = f"ל{cardinal(day, 'm')} ב{month}, {cardinal(year, 'f')}"
        return Fragment("ל-" + written, spoken, "slash_date", "date", written, "day-month-year-slash")
    if kind in {"landline", "local_landline", "national_line", "israeli_international", "business_line"}:
        value = values["phone"]
        spoken, policy = spoken_phone(kind, value)
        return Fragment(value, spoken, "phone", "identifier", value, policy)
    if kind == "plural_millions":
        value = values["millions_value"]
        written = f"{value:,}"
        millions, rest = divmod(value, 1_000_000)
        thousands, remainder = divmod(rest, 1000)
        millions_spoken = cardinal(millions, "m", construct=True) + " מיליון"
        if thousands == 0 and remainder == 0:
            spoken = millions_spoken
        elif remainder == 0:
            th_spoken = cardinal(thousands * 1000, "f")
            spoken = f"{millions_spoken}, {th_spoken}" if " ו" in th_spoken else f"{millions_spoken} ו{th_spoken}"
        else:
            head = f"{millions_spoken}, {cardinal(thousands * 1000, 'f')}" if thousands else millions_spoken
            if remainder >= 100:
                spoken = f"{head}, {cardinal(remainder, 'm')}"
            else:
                tail = "שני" if remainder == 2 else cardinal(remainder, "m")
                spoken = f"{head} ו{tail}"
        return Fragment(written, spoken, "millions_value", "large_quantity", written, "plural-millions")
    if kind == "child_half_age":
        value = values["child_age"]
        years = int(value[0])
        spoken = "שנתיים וחצי" if years == 2 else cardinal(years, "f") + " וחצי"
        return Fragment(value, spoken, "child_age", "age", value, "child-years-and-half")
    if kind == "month_end_date":
        day, month = values["day"], values["month"]
        return Fragment(f"ב-{day} ב{month}", f"ב{cardinal(day, 'm')} ב{month}",
                        "day", "date", day, "masculine-month-end-day")
    if kind == "midnight_time":
        minute = values["midnight_minute"]
        written_val = f"00:{minute:02d}"
        if minute == 0:
            spoken = "בחצות"
        elif minute == 1:
            spoken = "בחצות ודקה"
        elif minute == 15:
            spoken = "בחצות ורבע"
        elif minute == 20:
            spoken = "בחצות ועשרים"
        elif minute == 30:
            spoken = "בחצות וחצי"
        else:
            spoken = f"בחצות ו{cardinal(minute, 'f', construct=True)} דקות"
        return Fragment("ב-" + written_val, spoken, "midnight_minute", "clock_time", written_val, "midnight-minutes")
    if kind == "general_fraction":
        value = values["general_fraction"]
        return Fragment(value, GENERAL_FRACTION_SPOKEN[value], "general_fraction", "fraction", value, "partitive-fraction")
    if kind == "multi_digit_decimal":
        value = values["decimal_value"]
        whole_str, frac_str = value.split(".")
        frac_spoken = " ".join(cardinal(int(d), "f") for d in frac_str)
        spoken = f"{cardinal(int(whole_str), 'f')} נקודה {frac_spoken}"
        return Fragment(value, spoken, "decimal_value", "decimal", value, "digit-by-digit-decimal")
    if kind == "airline_flight":
        carrier, flight = values["carrier"], values["flight"]
        written = f"{carrier}{flight}"
        spoken = f"{AIRLINE_CODE_SPOKEN[carrier]} {spoken_digits(str(flight))}"
        return Fragment(written, spoken, "flight", "identifier", written, "iata-carrier-digit-flight")
    raise ValueError(f"Unknown domain expression: {kind}")


def sampled_number(rng: random.Random, low: int, high: int,
                   lengths: tuple[int, ...] | None = None, boundary_weight: float = 0.25) -> int:
    """Uniform digit-length bands, with some boundary and internal-zero cases."""
    bands = [(max(low, 0 if width == 1 else 10 ** (width - 1)), min(high, 10 ** width - 1))
             for width in range(1, len(str(high)) + 1)]
    bands = [(a, b) for a, b in bands if a <= b]
    if lengths is not None:
        bands = [(a, b) for a, b in bands if len(str(a)) in lengths]
    if not bands or not 0 <= boundary_weight <= 1:
        raise ValueError("No matching number bands or invalid boundary weight")
    a, b = rng.choice(bands)
    candidates = {a, b, (a + b) // 2}
    candidates.update(n for n in (1, 2, 10, 11, 20, 100, 101, 1000, 1001, 10000, 10001)
                      if a <= n <= b)
    if rng.random() < boundary_weight:
        return rng.choice(sorted(candidates))
    return rng.randint(a, b)


def sample(archetype_id: str, rng: random.Random, *,
           address_lengths: tuple[int, ...] = (1, 2, 3), boundary_weight: float = 0.25) -> dict[str, Any]:
    if archetype_id not in BY_ID:
        raise ValueError(f"Unknown archetype: {archetype_id}")
    values: dict[str, Any] = {}
    for spec in SAMPLERS[archetype_id]:
        if spec.when and not values[spec.when]:
            continue
        if spec.pool:
            values[spec.key] = rng.choice(spec.pool)
        elif spec.generator == "clock":
            values[spec.key] = rng.randrange(24 * 60)
        elif spec.generator in {"mobile", "landline", "local_landline", "national_line",
                                "israeli_international", "business_line"}:
            values[spec.key] = sample_phone(spec.generator, rng)
        elif spec.generator == "four_digits":
            values[spec.key] = "".join(str(rng.randrange(10)) for _ in range(4))
        elif spec.generator == "postal_code":
            values[spec.key] = "".join(str(rng.randrange(10)) for _ in range(rng.choice((5, 7))))
        elif spec.generator == "million_exact":
            tens_block = rng.randrange(100) * 10
            unit = rng.randrange(2, 10) if tens_block == 0 else rng.randrange(1, 10)
            values[spec.key] = 1_000_000 + rng.randrange(1, 1000) * 1000 + tens_block + unit
        elif spec.generator == "large_shekels":
            values[spec.key] = rng.randrange(101, 1000) * 1000 + rng.randrange(1000)
        elif spec.generator == "minute_nonround":
            values[spec.key] = rng.randrange(6, 24) * 60 + rng.choice(
                [minute for minute in range(1, 60) if minute not in (15, 30, 45)])
        elif spec.generator == "card_full":
            prefix = rng.choice(_CARD_PREFIXES) + "".join(str(rng.randrange(10)) for _ in range(11))
            invalid_digits = [str(d) for d in range(10) if not valid_luhn(prefix + str(d))]
            values[spec.key] = prefix + rng.choice(invalid_digits)
        elif spec.generator == "international_phone":
            values[spec.key] = _sample_international_phone(rng)
        elif spec.generator == "civil_id":
            prefix = rng.choice(("0", "2", "3")) + "".join(str(rng.randrange(10)) for _ in range(7))
            invalid_digits = [str(d) for d in range(10) if not valid_civil_id(prefix + str(d))]
            values[spec.key] = prefix + rng.choice(invalid_digits)
        elif spec.generator == "passport_id":
            values[spec.key] = _sample_passport_id(rng)
        elif spec.generator == "demo_account":
            values[spec.key] = str(rng.randint(100000, 999999))
        elif spec.generator == "demo_plate":
            if rng.random() < 0.5:
                p1 = f"{rng.randint(10, 99)}"
                p2 = f"{rng.randrange(1000):03d}"
                p3 = f"{rng.randrange(100):02d}"
            else:
                p1 = f"{rng.randint(100, 999)}"
                p2 = f"{rng.randrange(100):02d}"
                p3 = f"{rng.randrange(1000):03d}"
            values[spec.key] = f"{p1}-{p2}-{p3}"
        elif spec.generator == "plural_millions":
            millions = rng.randint(2, 9)
            mode = rng.randrange(3)
            if mode == 0:
                values[spec.key] = millions * 1_000_000
            elif mode == 1:
                values[spec.key] = millions * 1_000_000 + rng.randint(1, 9) * 100_000
            else:
                values[spec.key] = millions * 1_000_000 + rng.randint(1, 99) * 10_000
        elif spec.generator == "multi_digit_decimal":
            whole = rng.randrange(20)
            if rng.randrange(4) == 0:
                frac = f"0{rng.randint(1, 9)}"
            else:
                frac = f"{rng.randrange(100):02d}{rng.randint(1, 9)}"
            values[spec.key] = f"{whole}.{frac}"
        else:
            high = (PURCHASE_LIMITS[PURCHASE_BUCKETS[values["noun"]["singular"]]]
                    if archetype_id == "purchase" and spec.key == "quantity" else spec.upper)
            if archetype_id == "approximate" and spec.key == "quantity":
                bucket = PURCHASE_BUCKETS[values["noun"]["singular"]]
                high = 1500 if bucket == "fixture_large" else 5000 if bucket == "grocery_fresh" else spec.upper
            values[spec.key] = sampled_number(rng, spec.lower, high,
                                               address_lengths if spec.key == "house" else None, boundary_weight)
        if archetype_id == "approximate" and spec.key == "quantity":
            number = values[spec.key]
            step = 5 if number < 50 else 10 if number < 100 else 50 if number < 1000 else 500
            values[spec.key] = max(5, min(9999 // step * step, round(number / step) * step))
    if archetype_id == "numeric_calendar":
        values["spoken_style"] = rng.choice(("ordinal", "named"))
    if archetype_id == "month_end_date":
        valid_months = [m for m in MONTHS if MONTH_MAX_DAYS[m] >= values["day"]]
        if values["month"] not in valid_months:
            values["month"] = rng.choice(valid_months)
    return values


def validate_values(archetype_id: str, values: dict[str, Any]) -> None:
    expected = set()
    for spec in SAMPLERS[archetype_id]:
        if spec.when and not values.get(spec.when):
            continue
        expected.add(spec.key)
        value = values.get(spec.key)
        if spec.pool:
            if value not in spec.pool:
                raise ValueError(f"Invalid {spec.key} for {archetype_id}: {value!r}")
        elif spec.generator == "clock":
            if type(value) is not int or not 0 <= value < 1440:
                raise ValueError("minute_of_day must be 0..1439")
        elif spec.generator in {"mobile", "landline", "local_landline", "national_line",
                                "israeli_international", "business_line"}:
            if not validate_phone(spec.generator, value):
                raise ValueError(f"phone does not match {spec.generator} format")
        elif spec.generator == "four_digits":
            if not isinstance(value, str) or len(value) != 4 or not value.isascii() or not value.isdigit():
                raise ValueError("suffix must contain exactly four ASCII digits")
        elif spec.generator == "postal_code":
            if not isinstance(value, str) or len(value) not in (5, 7) or not value.isascii() or not value.isdigit():
                raise ValueError("postal_code must contain five or seven ASCII digits")
        elif spec.generator == "million_exact":
            if type(value) is not int or not 1_000_001 <= value <= 1_999_999 or value % 10 == 0:
                raise ValueError("number must exceed one million and have nonzero units")
        elif spec.generator == "large_shekels":
            if type(value) is not int or not 101_000 <= value <= 999_999:
                raise ValueError("large shekel amount must have six digits")
        elif spec.generator == "minute_nonround":
            if type(value) is not int or not 6 * 60 <= value < 24 * 60 or value % 60 in (0, 15, 30, 45):
                raise ValueError("meeting must have a non-round minute")
        elif spec.generator == "card_full":
            if not isinstance(value, str) or len(value) != 16 or not value.isascii() or not value.isdigit() or (not value.startswith("0000") and valid_luhn(value)):
                raise ValueError("card must be a 16-digit non-issuable (invalid-Luhn or 0000) number")
        elif spec.generator == "international_phone":
            if not isinstance(value, str) or not value.isascii() or not re.fullmatch(r"\+[1-9]\d{0,2} \d{1,3}-\d{3,4}-\d{4}", value):
                raise ValueError("international phone must match '+<cc> <area>-<mid>-<end>'")
        elif spec.generator == "civil_id":
            if not isinstance(value, str) or len(value) != 9 or not value.isascii() or not value.isdigit() or valid_civil_id(value):
                raise ValueError("civil ID must be a 9-digit invalid-checksum value")
        elif spec.generator == "passport_id":
            if not isinstance(value, str) or not value.isascii() or not re.fullmatch(r"[A-Z0-9]{8,9}", value) or sum(c.isdigit() for c in value) < 5:
                raise ValueError("passport must be an 8–9 char uppercase ICAO alphanumeric identifier with at least 5 digits")
        elif spec.generator == "demo_account":
            if not isinstance(value, str) or len(value) != 6 or not value.isascii() or not value.isdigit():
                raise ValueError("account must be six ASCII digits")
        elif spec.generator == "demo_plate":
            if not isinstance(value, str) or not value.isascii() or not re.fullmatch(r"(?:\d{2}-\d{3}-\d{2}|\d{3}-\d{2}-\d{3})", value):
                raise ValueError("plate must match XX-XXX-XX or XXX-XX-XXX")
        elif spec.generator == "plural_millions":
            if type(value) is not int or not 2_000_000 <= value <= 9_999_999 or value % 1000 == 1:
                raise ValueError("plural_millions must be 2,000,000..9,999,999 without 001 remainder")
        elif spec.generator == "multi_digit_decimal":
            if not isinstance(value, str) or not value.isascii() or not re.fullmatch(r"(?:0|[1-9]\d?)\.(?:0[1-9]|\d{2}[1-9])", value):
                raise ValueError("multi_digit_decimal must be 0..99 with .01-.09 or three decimal places ending nonzero")
        elif type(value) is not int or not spec.lower <= value <= spec.upper:
            raise ValueError(f"{spec.key} must be an integer in {spec.lower}..{spec.upper}")
    if archetype_id == "month_end_date" and values.get("day") and values.get("month") in MONTH_MAX_DAYS:
        if values["day"] > MONTH_MAX_DAYS[values["month"]]:
            raise ValueError(f"{values['month']} does not have {values['day']} days")
    if archetype_id == "numeric_calendar" and values.get("spoken_style") in {"ordinal", "named"}:
        expected.add("spoken_style")
    if values.keys() != expected:
        raise ValueError(f"Expected precisely these sampled slots: {sorted(expected)}")


def fragments(archetype_id: str, values: dict[str, Any], *, reading_variant: str = "natural",
              context: tuple[int, int] | None = None, continuation: int | None = None) -> list[Fragment]:
    if archetype_id not in TEMPLATES:
        raise ValueError(f"Unknown archetype: {archetype_id}")
    parts = TEMPLATES[archetype_id]
    if context is not None:
        bank = CONTEXTS[archetype_id]
        if (not isinstance(context, tuple) or len(context) != 2
                or any(type(n) is not int for n in context)
                or not 0 <= context[0] < len(bank.starts)
                or not 0 <= context[1] < len(bank.ends)):
            raise ValueError("Unknown sentence context")
        # Swap only the outer literals: all typed numeric parts, optional groups
        # and literals between aligned expressions stay with the archetype.
        parts = (Literal(bank.starts[context[0]]), *parts[1:])
        if isinstance(parts[-1], Literal):
            parts = (*parts[:-1], Literal(bank.ends[context[1]]))
        else:
            parts = (*parts, Literal(bank.ends[context[1]]))
    if continuation is not None:
        if context is None or type(continuation) is not int or not 0 <= continuation < 3:
            raise ValueError("Unknown sentence continuation")
        clause = continuation_for(archetype_id, values, *context, continuation)
        if not isinstance(parts[-1], Literal) or not parts[-1].value.endswith("."):
            raise ValueError("Sentence continuation requires a final period")
        ending = parts[-1].value
        parts = (*parts[:-1], Literal(ending[:-1] + clause + "."))

    def expand(parts: tuple[Any, ...]) -> list[Fragment]:
        result = []
        for part in parts:
            if isinstance(part, Literal):
                result.append(text(part.value))
            elif isinstance(part, ValueRef):
                result.append(text(values[part.key]))
            elif isinstance(part, NumberRef):
                val = values[part.key]
                gender = "m" if part.key in {"road", "route"} and val == 1 else "f"
                result.append(number(part.key, val, gender=gender))
            elif isinstance(part, OrdinalRef):
                result.append(ordinal(values[part.key]))
            elif isinstance(part, ClockRef):
                result.append(clock(values[part.key]))
            elif isinstance(part, PercentRef):
                result.append(percentage(values[part.key]))
            elif isinstance(part, PhoneRef):
                result.append(phone_number(values[part.key]))
            elif isinstance(part, DomainRef):
                result.append(domain_fragment(part.kind, values, reading_variant))
            elif isinstance(part, QuantityRef):
                result.append(quantity(values["quantity"], values["noun"], approximate=part.approximate))
            elif isinstance(part, OptionalGroup):
                if values[part.condition]:
                    result.extend(expand(part.parts))
            else:
                raise TypeError(f"Unsupported template piece: {part!r}")
        return result

    return expand(parts)


def render(archetype_id: str, values: dict[str, Any], *, seed: int = 0, index: int = 0,
           reading_variant: str = "natural",
           context: tuple[int, int] | None = None, continuation: int | None = None) -> dict[str, Any]:
    """Offsets are half-open Python Unicode code-point positions in the final strings."""
    if archetype_id not in BY_ID:
        raise ValueError(f"Unknown archetype: {archetype_id}")
    if reading_variant not in {"natural", "formal"}:
        raise ValueError(f"Unknown reading variant: {reading_variant}")
    validate_values(archetype_id, values)
    digits, spoken, alignments = "", "", []
    for piece in fragments(archetype_id, values, reading_variant=reading_variant,
                           context=context, continuation=continuation):
        if piece.slot:
            alignments.append({"slot": piece.slot, "kind": piece.kind, "value": piece.value,
                               "reading": piece.reading, "digits_span": [len(digits), len(digits) + len(piece.digits)],
                               "cardinal_span": [len(spoken), len(spoken) + len(piece.cardinal)],
                               "digits_text": piece.digits, "cardinal_text": piece.cardinal})
        digits += piece.digits
        spoken += piece.cardinal
    identity = {"archetype_id": archetype_id, "seed": seed, "index": index,
                 "sampled": values, "catalog_version": CATALOG_VERSION, "renderer_version": RENDERER_VERSION}
    if archetype_id in DEFAULT_FORMAL_WEIGHTS:
        identity["reading_variant"] = reading_variant
    if context is not None:
        identity["context"] = {"start": context[0], "end": context[1]}
    if continuation is not None:
        identity["continuation"] = continuation
    sample_id = sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
    pair = {"id": sample_id, **identity, "digits": digits, "cardinal": spoken, "alignments": alignments}
    validate_pair(pair)
    return pair


def validate_pair(pair: dict[str, Any]) -> None:
    if not pair["alignments"]:
        raise ValueError("Sentence must contain a numeric expression")
    previous = {"digits": 0, "cardinal": 0}
    for alignment in pair["alignments"]:
        for view in previous:
            start, end = alignment[f"{view}_span"]
            if not (previous[view] <= start < end <= len(pair[view])):
                raise ValueError("Invalid or overlapping alignment")
            if pair[view][start:end] != alignment[f"{view}_text"]:
                raise ValueError("Alignment does not slice its own rendering")
            if view == "digits" and str(alignment["value"]) not in alignment["digits_text"]:
                raise ValueError("Written expression does not contain the sampled value")
        d_start, _ = alignment["digits_span"]
        c_start, _ = alignment["cardinal_span"]
        if pair["digits"][previous["digits"]:d_start] != pair["cardinal"][previous["cardinal"]:c_start]:
            raise ValueError("Unaligned text differs across views")
        for view in previous:
            previous[view] = alignment[f"{view}_span"][1]
        if any(char.isdigit() for char in alignment["cardinal_text"]):
            raise ValueError("Spoken numeric expression contains digits")
    if pair["digits"][previous["digits"]:] != pair["cardinal"][previous["cardinal"]:]:
        raise ValueError("Unaligned trailing text differs across views")
    if any(char.isdigit() for char in pair["cardinal"]):
        raise ValueError("Spoken sentence contains digits")


MAX_GENERATE_COUNT = 100_000


def generate(seed: int, count: int, archetypes: list[str] | None = None, *,
               address_lengths: tuple[int, ...] = (1, 2, 3),
              boundary_weight: float = 0.25,
              variant_weights: dict[str, float] | None = None) -> list[dict[str, Any]]:
    if type(seed) is not int or type(count) is not int or not 1 <= count <= MAX_GENERATE_COUNT:
        raise ValueError(f"Seed must be an integer and count must be between 1 and {MAX_GENERATE_COUNT}")
    ids = list(dict.fromkeys(archetypes if archetypes is not None else [a.id for a in ARCHETYPES]))
    if not ids or any(name not in BY_ID for name in ids):
        raise ValueError("Select at least one known archetype")
    if not address_lengths or any(type(length) is not int or length not in range(1, 6) for length in address_lengths):
        raise ValueError("Address lengths must be a nonempty subset of 1..5")
    if not 0 <= boundary_weight <= 1:
        raise ValueError("Boundary weight must be between 0 and 1")
    weights = resolve_weights(variant_weights)
    result = []
    seen_digits: set[str] = set()
    for index in range(count):
        cycle = index // len(ids)
        order = ids.copy()
        random.Random(f"{seed}:cycle:{cycle}:{CATALOG_VERSION}").shuffle(order)
        archetype_id = order[index % len(ids)]
        pair = None
        for attempt in range(64):
            key = (f"{seed}:row:{index}:{CATALOG_VERSION}" if attempt == 0
                   else f"{seed}:row:{index}:retry:{attempt}:{CATALOG_VERSION}")
            rng = random.Random(key)
            sampled = sample(archetype_id, rng, address_lengths=address_lengths,
                             boundary_weight=boundary_weight)
            reading_variant = "natural"
            if archetype_id in weights and rng.random() < weights[archetype_id]:
                reading_variant = "formal"
            frames = compatible_frames(archetype_id, sampled)
            start = rng.choice(tuple(dict.fromkeys(start for start, _, _ in frames)))
            ending = rng.choice(tuple(dict.fromkeys(end for s, end, _ in frames if s == start)))
            context = (start, ending)
            continuation = rng.choice(CONTINUATION_CHOICES)
            candidate = render(archetype_id, sampled, seed=seed, index=index,
                               reading_variant=reading_variant, context=context,
                               continuation=continuation)
            pair = candidate
            if candidate["digits"] not in seen_digits:
                break
        assert pair is not None
        seen_digits.add(pair["digits"])
        result.append(pair)
    return result
