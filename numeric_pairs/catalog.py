"""Curated, versioned archetypes and lexical pools. No inferred noun genders."""

from dataclasses import dataclass

from .lexicon import PROPOSED_CATALOG_NOUNS, PROPOSED_CATALOG_STREETS

CATALOG_VERSION = "starter-19"


@dataclass(frozen=True)
class Noun:
    singular: str
    plural: str
    gender: str


NOUNS = tuple(Noun(entry.singular, entry.plural, entry.gender)
              for entry in PROPOSED_CATALOG_NOUNS if entry.singular != "אבן")

# Four noun-dependent size classes proposed by Gemini for personal purchases.
PURCHASE_BUCKET_NAMES = {
    "fixture_large": ("שולחן", "כיסא", "מדף", "מנורה"),
    "durable_unit": ("ספר", "קופסה", "צנצנת", "ארגז", "קלסר", "חוברת",
                     "מגבת", "צלחת", "כוס", "שתיל"),
    "grocery_fresh": ("עגבנייה", "מלפפון", "תפוח", "לימון", "בצל",
                      "פלפל", "אגס", "תפוז", "ביצה", "לחמנייה", "פיתה", "עוגייה"),
    "consumable_small": ("מחברת", "כרטיס", "שקית", "אריזה", "בקבוק", "עט",
                         "עיפרון", "תיקייה", "מעטפה", "מדבקה", "נר", "סוללה", "בורג"),
}
PURCHASE_LIMITS = {"fixture_large": 6, "durable_unit": 12,
                   "grocery_fresh": 20, "consumable_small": 30}
PURCHASE_BUCKETS = {name: bucket for bucket, names in PURCHASE_BUCKET_NAMES.items()
                    for name in names}
assert set(PURCHASE_BUCKETS) == {noun.singular for noun in NOUNS}
STREETS = PROPOSED_CATALOG_STREETS
MONTHS = ("ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר")
MONTH_NUMBERS = {month: index for index, month in enumerate(MONTHS, 1)}
MONTH_MAX_DAYS = {
    "ינואר": 31, "פברואר": 28, "מרץ": 31, "אפריל": 30,
    "מאי": 31, "יוני": 30, "יולי": 31, "אוגוסט": 31,
    "ספטמבר": 30, "אוקטובר": 31, "נובמבר": 30, "דצמבר": 31,
}


@dataclass(frozen=True)
class Archetype:
    id: str
    title: str
    description: str
    category: str
    slots: tuple[str, ...]


ARCHETYPES = (
    Archetype("address", "כתובת רחוב", "מספר בית בן 1–5 ספרות, בקריאת מספר סתמי בנקבה", "address", ("street", "house")),
    Archetype("delivery", "משלוח לדירה", "מספר בית ומספר דירה אופציונלי", "address", ("street", "house", "apartment")),
    Archetype("purchase", "קנייה יומיומית", "כמות 2–30, עם תקרה לפי סוג הפריט ושם עצם מותאם מין ומספר", "quantity", ("noun", "quantity")),
    Archetype("approximate", "כמות בקירוב", "תחילית כ־ מחוברת לביטוי המספרי", "quantity", ("noun", "quantity")),
    Archetype("floor", "קומה סידורית", "קומות 1–10; ה-5 מול החמישית", "ordinal", ("floor",)),
    Archetype("departure", "שעת יציאה", "שעת יום בפורמט 24 שעות, בקריאת שעון של 12 שעות", "time", ("minute_of_day",)),
    Archetype("survey", "אחוז בסקר", "אחוז שלם 1–100 עם התאמת יחידה", "percent", ("percent",)),
    Archetype("mobile", "טלפון נייד", "מזהה בן 10 ספרות עם אפסים מובילים", "identifier", ("phone",)),
    Archetype("ranking", "דירוג במקום", "מיקום סידורי בזכר, 1–10", "ordinal", ("rank",)),
    Archetype("age", "גיל בדיבור", "גיל מרומז 18–99 בקריאה בנקבה", "age", ("age",)),
    Archetype("year", "שנה", "שנה בלבד, 1948–2026", "date", ("year",)),
    Archetype("calendar", "יום בחודש", "יום 1–28 ושם חודש עברי מפורש", "date", ("day", "month")),
    Archetype("duration_half", "משך זמן וחצי", "משכים של 1.5–4.5 שעות; דיבור טבעי כמו שלוש וחצי שעות", "duration", ("duration",)),
    Archetype("fraction", "שבר פשוט", "חצי ושלושה רבעים בהקשר של מתכון", "fraction", ("fraction",)),
    Archetype("decimal_temp", "מעלות עשרוניות", "טמפרטורה חיובית עם שבר עשרוני, לרבות רבע/חצי/שלושת רבעי", "decimal", ("whole", "fractional")),
    Archetype("negative_temp", "מעלות מתחת לאפס", "טמפרטורה שלילית שלמה", "signed", ("magnitude",)),
    Archetype("money", "תשלום בשקלים", "סכום שלם 2–999 שקלים, סימן ₪", "money", ("amount",)),
    Archetype("weight", "משקל", "קילוגרמים שלמים 2–99 עם הקיצור ק״ג", "measurement", ("weight",)),
    Archetype("card_suffix", "ארבע ספרות אחרונות", "מזהה מקוצר, כולל אפסים מובילים", "identifier", ("suffix",)),
    Archetype("road_route", "כביש וקו", "מספר כביש ומספר קו בתחבורה", "transport", ("road", "route")),
    Archetype("version", "גרסת תוכנה", "שלושה רכיבים; בדרך כלל ללא אמירת נקודה", "version", ("major", "minor", "patch")),
    Archetype("score", "תוצאת משחק", "תוצאה דו-צדדית בנקודתיים", "score", ("score",)),
    Archetype("age_range", "טווח גילאים", "מספרי גיל במבנה מ–עד", "range", ("age_range",)),
    Archetype("percent_half", "אחוז וחצי", "אחוזים עם חצי אחוז", "percent", ("whole_percent",)),
    Archetype("full_date", "תאריך מלא", "תאריך אחרי נקבע ל־; יום 1–28 וכל חודשי השנה", "date", ("day", "month", "year")),
    Archetype("money_cents", "שקלים ואגורות", "2–99 שקלים; חצי שקל נקרא בדיבור טבעי", "money", ("shekels", "agorot")),
    Archetype("distance", "מרחק בקילומטרים", "מספר שלם 2–999 בקיצור ק״מ", "measurement", ("kilometers",)),
    Archetype("section", "סעיף ותת-סעיף", "מספור היררכי; בדיבור לרוב בלי אמירת תת-סעיף", "document", ("section", "subsection")),
    Archetype("postal", "מיקוד", "רצף חמש ספרות שנקרא ספרה אחר ספרה", "identifier", ("postal_code",)),
    Archetype("infant_age", "גיל שנה וחצי", "גיל תינוק בכתיב 1.5 מול בן שנה וחצי", "age", ("age_years",)),
    Archetype("decade", "עשור", "שנות ה־50 עד ה־90", "date", ("decade",)),
    Archetype("stopwatch_seconds", "שניות ושבר עשרוני", "זמן מדוד בשניות עם שבר עשרוני, בדיבור ללא 'מאיות'", "duration", ("seconds", "hundredths")),
    Archetype("area", "שטח במטרים רבועים", "שטח דירה בקיצור מ״ר", "measurement", ("square_meters",)),
    Archetype("map_scale", "קנה מידה", "יחס 1 למאה אלף או חמישים אלף", "document", ("scale",)),
    Archetype("maximum_attendees", "קיבולת מרבית", "גבול עליון של משתתפים", "range", ("capacity",)),
    Archetype("pill_range", "טווח גלולות", "בין שתי כמויות יומיות של גלולות", "range", ("minimum", "maximum")),
    Archetype("opening_hours", "טווח שעות", "שעות קבלת קהל בפורמט שעון עגול", "time", ("start_hour", "end_hour")),
    Archetype("dollar_price", "מחיר בדולרים", "סכום דולרים שלם עם סימן $", "money", ("dollars",)),
    Archetype("million_exact", "מספר מעל מיליון", "מיליון ועוד אלפים, מאות, עשרות ואחדות; ספרת האחדות אינה אפס", "quantity", ("number",)),
    Archetype("meeting_minute", "פגישה בדקה לא עגולה", "שעת פגישה בכתיב 24 שעות, קריאה טבעית ב־12 שעות", "time", ("minute_of_day",)),
    Archetype("card_full", "מספר כרטיס מלא", "16 ספרות בקבוצות 4; תחילית 0000 שאינה מנפיקת כרטיס", "identifier", ("card_number",)),
    Archetype("international_phone", "טלפון בינלאומי", "מספר שמור בפורמט +1 202-555-01xx", "identifier", ("international_phone",)),
    Archetype("civil_id", "תעודת זהות", "9 ספרות עם ספרת ביקורת לא תקינה; קריאת שלשות", "identifier", ("civil_id",)),
    Archetype("passport_id", "מספר דרכון", "קידומת XX ו־7 ספרות", "identifier", ("passport_id",)),
    Archetype("stopwatch_minute", "סטופר עם דקות", "דקה, שניות ומאיות בפורמט 1:46.30", "duration", ("minutes", "seconds", "hundredths")),
    Archetype("euro_price", "מחיר באירו", "סכום אירו שלם בסימן €", "money", ("euros",)),
    Archetype("data_plan", "נפח ומהירות נתונים", "GB לעומת ג׳יגה-בייט, Mb לעומת מגה ביט", "measurement", ("gigabytes", "megabits")),
    Archetype("bank_account", "סניף וחשבון", "סניף מספרי וחשבון בן 6 ספרות עם תחילית 000", "identifier", ("branch", "account")),
    Archetype("license_plate", "מספר רכב", "תבנית 2-3-2 עם תחילית 00", "identifier", ("plate",)),
    Archetype("flight_number", "מספר טיסה", "קוד חברת תעופה LY עם שלוש ספרות", "transport", ("flight",)),
    Archetype("numeric_calendar", "יום וחודש מספריים", "ב־23.8 מול בעשרים ושלושה לשמיני", "date", ("day", "month_number")),
    Archetype("slash_address", "כתובת בלוכסן", "מספר בית ודירה עם לוכסן, בקריאת דירה", "address", ("street", "house", "apartment")),
    Archetype("minimum_age", "גיל מינימלי", "בני 21 ומעלה", "range", ("minimum_age",)),
    Archetype("large_shekels", "סכום שקלים גדול", "אלפי ומאות אלפי שקלים עם אחדות", "money", ("shekels_large",)),
    Archetype("explicit_hundredths", "מאיות במפורש", "שניות ומאיות כשכל יחידה מצוינת בכתיב", "duration", ("seconds", "hundredths")),
    Archetype("slash_date", "תאריך מלא בלוכסנים", "תאריך יום/חודש/שנה אחרי 'נקבע ל־'", "date", ("day", "month", "year")),
    Archetype("landline", "טלפון קווי עם אזור חיוג", "02/03/04/08/09, שבע ספרות מנוי וקבוצת 000", "identifier", ("phone",)),
    Archetype("local_landline", "טלפון קווי מקומי", "שבע ספרות ללא אזור חיוג, בפורמט 000-XXXX", "identifier", ("phone",)),
    Archetype("national_line", "קו ארצי 07", "קידומות 07X בפורמט 3-3-4 וקבוצת 000", "identifier", ("phone",)),
    Archetype("israeli_international", "טלפון ישראלי עם ‎+972", "נייד, נייח או ארצי בלי אפס הגישה; קבוצת 000", "identifier", ("phone",)),
    Archetype("business_line", "מספר שירות ארצי", "קידומות 1599/1700/1800 וקבוצת 000", "identifier", ("phone",)),
    Archetype("bulk_purchase", "רכש סיטונאי", "כמות גדולה בסביבה מוסדית, בנפרד מקנייה ביתית", "quantity", ("noun", "quantity")),
    Archetype("plural_millions", "מיליונים בלשון רבים", "2–9 מיליון עם אלפים עגולים או מלאים, בקריאת שני מיליון / שלושה מיליון", "quantity", ("millions_value",)),
    Archetype("child_half_age", "גיל ילדים וחצי", "גילאי 2.5–6.5 בקריאה טבעית שנתיים וחצי / שלוש וחצי", "age", ("child_age",)),
    Archetype("month_end_date", "תאריכי סוף חודש", "ימים 29–31 בהתאמה לחודשים תקינים בלוח השנה", "date", ("day", "month")),
    Archetype("midnight_time", "דקות סביב חצות", "00:00–00:20 ו־00:30 בקריאת חצות, חצות ודקה, חצות ורבע וחצות וחצי", "time", ("midnight_minute",)),
    Archetype("general_fraction", "שברים פשוטים כלליים", "שליש, שני שלישים, חמישיות, שישית, שמיניות ועשיריות", "fraction", ("general_fraction",)),
    Archetype("multi_digit_decimal", "עשרוני מרובה ספרות", "מספר עשרוני בן שתי ספרות עם אפס מוביל או שלוש ספרות אחרי הנקודה", "decimal", ("decimal_value",)),
    Archetype("airline_flight", "טיסה בקוד חברת תעופה", "קודי חברות תעופה בינלאומיות בני שתי אותיות ושלוש ספרות", "transport", ("carrier", "flight")),
)

BY_ID = {item.id: item for item in ARCHETYPES}

# The source guide is a coverage map, not an assertion that every example is
# ready to generate. Keep pending subcases visible to reviewers.
SCENARIO_AREAS = (
    ("מספרים, דירוג וגיל", ("purchase", "bulk_purchase", "ranking", "floor", "age", "infant_age", "child_half_age", "million_exact", "plural_millions"), "מיליארדים וסידורים מעבר לעשירי"),
    ("תאריכים ושנים", ("year", "calendar", "month_end_date", "full_date", "decade", "numeric_calendar", "slash_date"), "תאריכים עבריים ושנים לפני 1948"),
    ("שעות ומשך זמן", ("departure", "midnight_time", "duration_half", "stopwatch_seconds", "opening_hours", "meeting_minute", "stopwatch_minute", "explicit_hundredths"), "קריאת שעון צבאית בת 24 שעות"),
    ("שברים, עשרוניים, שליליים ואחוזים", ("fraction", "general_fraction", "decimal_temp", "multi_digit_decimal", "negative_temp", "survey", "percent_half"), "שברים במכנים שרירותיים ואחוזים עשרוניים כלליים"),
    ("כספים ומטבעות", ("money", "money_cents", "dollar_price", "euro_price", "large_shekels"), "טווחי מחירים ומטבעות נוספים"),
    ("מידות וטכנולוגיה", ("weight", "distance", "area", "data_plan"), "יחידות נפח והספק נוספות"),
    ("מזהים ורצפי ספרות", ("mobile", "landline", "local_landline", "national_line", "israeli_international", "business_line", "card_suffix", "postal", "card_full", "international_phone", "civil_id", "passport_id", "bank_account", "license_plate"), "מוקדי חיוג מקוצרים ומספור היסטורי"),
    ("כתובות ותחבורה", ("address", "delivery", "road_route", "flight_number", "airline_flight", "slash_address"), "תאי דואר ומבני כתובת כפריים"),
    ("מסמכים, גרסאות ותוצאות", ("version", "score", "section", "map_scale"), "סעיפים מרובי רמות ויחסי מסך"),
    ("טווחים וקירובים", ("age_range", "approximate", "maximum_attendees", "pill_range", "minimum_age"), "טווחי יחידות נוספים"),
)
