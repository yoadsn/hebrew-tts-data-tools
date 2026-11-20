"""Original, composable sentence frames; corpus snippets are never copied here.

Each frame replaces only the outer literals of an archetype's typed template.
The numeric fragments and all intervening literals stay with their renderer, so
multiple aligned expressions (for example house + apartment) remain intact.
"""

from dataclasses import dataclass

from . import lexicon
from .catalog import PURCHASE_BUCKETS, PURCHASE_LIMITS


@dataclass(frozen=True)
class Context:
    starts: tuple[str, ...]
    ends: tuple[str, ...]


# Shared lexical banks: words are interchangeable only inside a compatible
# syntactic/semantic role. Keep tense and noun agreement in the individual start.
SHOP = lexicon.SHOP
REPORT = lexicon.REPORT
RECORD = lexicon.RECORD
SPORT = lexicon.SPORT
WEATHER = lexicon.WEATHER
PRICE = lexicon.PRICE
TIME = lexicon.TIME
DOCUMENT = lexicon.DOCUMENT
MEASURE = lexicon.MEASURE


CONTEXTS = {
    "address": Context(lexicon.ADDRESS_STARTS, lexicon.URBAN_LANDMARKS),
    "delivery": Context(lexicon.DELIVERY_DISPATCH_STARTS, lexicon.DELIVERY_ENDINGS),
    "purchase": Context(lexicon.PURCHASE_STARTS, SHOP),
    "bulk_purchase": Context(lexicon.BULK_PURCHASE_STARTS, lexicon.BULK_PURCHASE_ENDINGS),
    "approximate": Context(lexicon.APPROXIMATE_STARTS, lexicon.APPROXIMATE_ENDINGS),
    "floor": Context(lexicon.FLOOR_STARTS, lexicon.FLOOR_ENDINGS),
    "departure": Context(lexicon.DEPARTURE_STARTS, TIME),
    "survey": Context(lexicon.SURVEY_STARTS, lexicon.SURVEY_ENDINGS),
    "mobile": Context(lexicon.MOBILE_STARTS, lexicon.MOBILE_ENDINGS),
    "ranking": Context(lexicon.RANKING_STARTS, lexicon.RANKING_ENDINGS),
    "age": Context(lexicon.AGE_STARTS, lexicon.AGE_ENDINGS),
    "year": Context(lexicon.YEAR_STARTS, lexicon.YEAR_ENDINGS),
    "calendar": Context(lexicon.CALENDAR_STARTS, lexicon.CALENDAR_ENDINGS),
    "duration_half": Context(lexicon.DURATION_HALF_STARTS, lexicon.DURATION_HALF_ENDINGS),
    "fraction": Context(lexicon.FRACTION_STARTS, lexicon.FRACTION_INGREDIENTS),
    "decimal_temp": Context(lexicon.DECIMAL_TEMP_STARTS, WEATHER),
    "negative_temp": Context(lexicon.NEGATIVE_TEMP_STARTS, lexicon.NEGATIVE_WEATHER_ENDINGS),
    "money": Context(lexicon.MONEY_STARTS, PRICE),
    "weight": Context(lexicon.WEIGHT_STARTS, MEASURE),
    "card_suffix": Context(lexicon.CARD_SUFFIX_STARTS, RECORD),
    "road_route": Context(lexicon.ROAD_ROUTE_STARTS, lexicon.ROAD_ROUTE_ENDINGS),
    "version": Context(lexicon.VERSION_STARTS, lexicon.VERSION_ENDINGS),
    "score": Context(lexicon.SCORE_STARTS, lexicon.SCORE_ENDINGS),
    "age_range": Context(lexicon.AGE_RANGE_STARTS, lexicon.AGE_RANGE_ENDINGS),
    "percent_half": Context(lexicon.PERCENT_HALF_STARTS, REPORT),
    "full_date": Context(lexicon.FULL_DATE_STARTS, lexicon.FULL_DATE_ENDINGS),
    "money_cents": Context(lexicon.MONEY_CENTS_STARTS, PRICE),
    "distance": Context(lexicon.DISTANCE_STARTS, MEASURE),
    "section": Context(lexicon.SECTION_STARTS, DOCUMENT),
    "postal": Context(lexicon.POSTAL_STARTS, lexicon.POSTAL_ENDINGS),
    "infant_age": Context(lexicon.INFANT_AGE_STARTS, lexicon.INFANT_AGE_ENDINGS),
    "decade": Context(lexicon.DECADE_STARTS, lexicon.DECADE_ENDINGS),
    "stopwatch_seconds": Context(lexicon.STOPWATCH_SECONDS_STARTS, SPORT),
    "area": Context(lexicon.AREA_STARTS, MEASURE),
    "map_scale": Context(lexicon.MAP_SCALE_STARTS, DOCUMENT),
    "maximum_attendees": Context(lexicon.MAX_ATTENDEES_STARTS, lexicon.MAX_ATTENDEES_ENDINGS),
    "pill_range": Context(lexicon.PILL_RANGE_STARTS, lexicon.PILL_RANGE_ENDINGS),
    "opening_hours": Context(lexicon.OPENING_HOURS_STARTS, lexicon.OPENING_HOURS_ENDINGS),
    "dollar_price": Context(lexicon.DOLLAR_PRICE_STARTS, PRICE),
    "million_exact": Context(lexicon.MILLION_EXACT_STARTS, lexicon.MILLION_EXACT_ENDINGS),
    "meeting_minute": Context(lexicon.MEETING_MINUTE_STARTS, lexicon.MEETING_MINUTE_ENDINGS),
    "card_full": Context(lexicon.CARD_FULL_STARTS, RECORD),
    "international_phone": Context(lexicon.INTERNATIONAL_PHONE_STARTS, lexicon.MOBILE_ENDINGS),
    "civil_id": Context(lexicon.CIVIL_ID_STARTS, RECORD),
    "passport_id": Context(lexicon.PASSPORT_ID_STARTS, RECORD),
    "stopwatch_minute": Context(lexicon.STOPWATCH_MINUTE_STARTS, lexicon.STOPWATCH_MINUTE_ENDINGS),
    "euro_price": Context(lexicon.EURO_PRICE_STARTS, PRICE),
    "data_plan": Context(lexicon.DATA_PLAN_STARTS, lexicon.DATA_PLAN_ENDINGS),
    "bank_account": Context(lexicon.BANK_ACCOUNT_STARTS, RECORD),
    "license_plate": Context(lexicon.LICENSE_PLATE_STARTS, RECORD),
    "flight_number": Context(lexicon.FLIGHT_STARTS, lexicon.FLIGHT_ENDINGS),
    "numeric_calendar": Context(lexicon.NUMERIC_CALENDAR_STARTS, lexicon.NUMERIC_CALENDAR_ENDINGS),
    "slash_address": Context(lexicon.SLASH_ADDRESS_STARTS, lexicon.SLASH_ADDRESS_ENDINGS),
    "minimum_age": Context(lexicon.MINIMUM_AGE_STARTS, lexicon.MINIMUM_AGE_ENDINGS),
    "large_shekels": Context(lexicon.LARGE_MONEY_STARTS, lexicon.LARGE_MONEY_ENDINGS),
    "explicit_hundredths": Context(lexicon.EXPLICIT_HUNDREDTHS_STARTS, SPORT),
    "slash_date": Context(lexicon.SLASH_DATE_STARTS, lexicon.SLASH_DATE_ENDINGS),
    "landline": Context(lexicon.LANDLINE_STARTS, lexicon.MOBILE_ENDINGS),
    "local_landline": Context(lexicon.LOCAL_LANDLINE_STARTS, lexicon.MOBILE_ENDINGS),
    "national_line": Context(lexicon.NATIONAL_LINE_STARTS, lexicon.MOBILE_ENDINGS),
    "israeli_international": Context(lexicon.ISRAELI_INTERNATIONAL_STARTS, lexicon.MOBILE_ENDINGS),
    "business_line": Context(lexicon.BUSINESS_LINE_STARTS, lexicon.MOBILE_ENDINGS),
    "plural_millions": Context(lexicon.PLURAL_MILLIONS_STARTS, lexicon.PLURAL_MILLIONS_ENDINGS),
    "child_half_age": Context(lexicon.CHILD_HALF_AGE_STARTS, lexicon.CHILD_HALF_AGE_ENDINGS),
    "month_end_date": Context(lexicon.MONTH_END_STARTS, lexicon.MONTH_END_ENDINGS),
    "midnight_time": Context(lexicon.MIDNIGHT_STARTS, lexicon.MIDNIGHT_ENDINGS),
    "general_fraction": Context(lexicon.GENERAL_FRACTION_STARTS, lexicon.GENERAL_FRACTION_ENDINGS),
    "multi_digit_decimal": Context(lexicon.MULTI_DIGIT_DECIMAL_STARTS, lexicon.MULTI_DIGIT_DECIMAL_ENDINGS),
    "airline_flight": Context(lexicon.AIRLINE_FLIGHT_STARTS, lexicon.AIRLINE_FLIGHT_ENDINGS),
}


# Optional continuations add information rather than filler. Each pair is a
# medium clause and a longer clause that can follow *any* start/end combination
# in its group. Keep these digit-free and independent of the sampled value.
# The transcript search returns short segments, not complete sentences; the
# length mix deliberately extends beyond those segment boundaries.
CLAUSE_GROUPS = (
    (("address", "delivery", "slash_address"),
     ", והכתובת נשלחה גם למי שאמור להגיע לשם",
     ", והכתובת הועברה מראש כדי שמי שמגיע למקום יוכל למצוא אותו בלי לבקש שוב הוראות"),
    (("purchase", "approximate"),
     ", בהתאם לרשימה שהוכנה מראש",
     ", כדי שכל הפריטים שנדרשו יהיו מוכנים בזמן בלי שנצטרך לצאת לקנייה נוספת"),
    (("bulk_purchase",),
     ", והכמות נרשמה במערכת המלאי",
     ", כדי שאפשר יהיה לחלק את הפריטים בין המחסנים בהתאם לצרכים של כל סניף"),
    (("floor",),
     ", כך שהאורחים ידעו לאן לעלות",
     ", והנחיות ההגעה נשלחו לאורחים כדי שלא יצטרכו לחפש את החדר בבניין"),
    (("departure",),
     ", ולכן כדאי להגיע לתחנה מעט קודם",
     ", ואם יש שינוי בלוח הזמנים תישלח הודעה לנוסעים לפני שהם יוצאים מהבית"),
    (("survey",),
     ", אך לא כל הנשאלים ענו לשאלה הזאת",
     ", וצריך לזכור שהמדגם כלל רק את מי שבחרו להשתתף בבדיקה"),
    (("mobile",),
     ", כדי לקבל מענה ישיר מהנציג הזמין",
     ", ואם אין מענה אפשר להשאיר הודעה כדי שנחזור עם הפרטים בהמשך היום"),
    (("international_phone",),
     ", וכדאי להביא בחשבון את הפרשי השעות לפני שמחייגים",
     ", ומומלץ לבדוק מראש את שעות המענה המקומיות כדי להשיג נציג זמין"),
    (("israeli_international",),
     ", כולל קידומת המדינה המלאה לחיוג ישיר מחו״ל",
     ", כדי שניתן יהיה ליצור קשר עם המשרד בישראל גם במהלך השהייה בחו״ל"),
    (("landline", "local_landline", "national_line", "business_line"),
     ", והמענה הקולי ינתב את השיחה לשלוחה המתאימה",
     ", ואם הקו תפוס אפשר להמתין על הקו או להשאיר פרטים לחזרה"),
    (("ranking",),
     ", אחרי יום ארוך של תחרויות",
     ", לאחר השלמת כל השלבים וההמתנה לפרסום התוצאות הרשמיות של המקצה"),
    (("age",),
     ", וההכנות לחגיגה כבר החלו בבית",
     ", ולכבוד המאורע נשלחו הזמנות גם לקרובים שלא יצא להם להיפגש בזמן האחרון"),
    (("infant_age",),
     ", והמשפחה כבר שמה לב כמה הוא גדל",
     ", וכשהוא פוגש בני משפחה שלא ראו אותו זמן מה כולם מופתעים מכמה הוא השתנה"),
    (("year",),
     ", כך עולה מהבדיקה ההיסטורית שנערכה",
     ", והפרט מופיע גם במסמכים המקוריים שנשמרו לצורך בדיקה מאוחרת יותר"),
    (("calendar", "numeric_calendar", "full_date", "slash_date"),
     ", והפרטים המלאים יישלחו למשתתפים בהמשך",
     ", ומי שמתכנן להגיע יקבל הודעה נוספת עם הוראות הגעה ושעת פתיחת המקום"),
    (("duration_half",),
     ", מעבר לזמן שהוקצב לכך מראש",
     ", אף על פי שהתכנון המקורי היה לסיים מוקדם יותר ולפנות זמן להמשך היום"),
    (("fraction",),
     ", ואז מערבבים עד שהתערובת נעשית אחידה",
     ", וממשיכים לערבב בעדינות עד שכל החומרים נטמעים בתערובת ואין בה גושים"),
    (("decimal_temp", "negative_temp"),
     ", ולכן כדאי להתלבש בהתאם לפני היציאה",
     ", ולפי התחזית התנאים האלה צפויים להימשך גם בשעות הקרובות באזור"),
    (("money", "money_cents", "dollar_price", "euro_price"),
     ", והמחיר מופיע גם בפרטי ההזמנה",
     ", אבל לפני התשלום כדאי לבדוק אם נוספו חיובים אחרים לסכום שמוצג בהזמנה"),
    (("weight", "distance", "area"),
     ", והנתון נרשם לצורך השוואה בהמשך",
     ", כדי שאפשר יהיה להשוות את התוצאה למדידה נוספת שתיערך לאחר סיום העבודה"),
    (("card_suffix", "card_full", "bank_account"),
     ", והאסמכתא נשמרה להמשך מעקב",
     ", ומומלץ לשמור את האסמכתא שהתקבלה לצורך מעקב מסודר בהמשך החודש"),
    (("civil_id", "passport_id", "license_plate"),
     ", והפרטים אומתו בהצלחה ללא עיכוב",
     ", כך שאפשר להמשיך בתהליך באופן מסודר ובלי להמתין לבירור נוסף"),
    (("road_route",),
     ", אחרי ששינינו את המסלול הרגיל",
     ", משום שהדרך שתכננו מראש הייתה עמוסה וניסינו למצוא מסלול מהיר יותר"),
    (("version",),
     ", אחרי שהצוות סיים לבדוק את העדכון",
     ", ואפשר לראות בה גם את התיקונים שנוספו בעקבות הבדיקות האחרונות של הצוות"),
    (("score",),
     ", בתום דקות קצביות משני צידי המגרש",
     ", אחרי דקות מותחות שבהן שתי הקבוצות ניסו לשנות את התוצאה בכל הזדמנות"),
    (("age_range", "minimum_age"),
     ", כך שאפשר לבדוק מראש מי רשאי להירשם",
     ", ולכן חשוב לעבור על תנאי ההשתתפות לפני ששולחים את טופס ההרשמה"),
    (("percent_half",),
     ", לפי העדכון האחרון שנשלח לצוות",
     ", אבל הנתון הזה עשוי להשתנות שוב לאחר פרסום ההחלטה הבאה בנושא"),
    (("section",),
     ", ואפשר לקרוא שם את ההסבר המלא",
     ", כדי להבין אילו תנאים חלים במקרה הזה לפני שמגישים את הבקשה"),
    (("postal",),
     ", כדי לוודא שהחבילה תגיע ליעדה",
     ", והפרט הזה נבדק פעם נוספת לפני שהמשלוח הועבר לחברת ההפצה"),
    (("decade",),
     ", לפחות לפי התיאור שפורסם",
     ", וכך גם נכתב בתיאור שהועלה לאתר לפני שהיצירה הוצגה לציבור"),
    (("stopwatch_seconds", "stopwatch_minute", "explicit_hundredths"),
     ", אחרי שהמתחרה שיפר את השיא הקודם",
     ", לאחר שבניסיון האחרון הושגה תוצאה טובה יותר מזו שנקבעה מוקדם יותר באותו יום"),
    (("map_scale",),
     ", כדי שיהיה אפשר לעיין בפרטים הקטנים",
     ", והצוות בדק שהסימונים נשארו ברורים גם כשהדפיסו את הקובץ בגודל קטן יותר"),
    (("maximum_attendees",),
     ", ולכן ביקשו מהנרשמים לאשר הגעה",
     ", כדי שלא יגיעו למקום יותר אנשים ממספר המקומות שאפשר להציע להם"),
    (("pill_range",),
     ", ומעדכנים את הרופא במצב",
     ", אבל לפני שמתחילים בטיפול כדאי לקרוא שוב את ההוראות ולוודא שהן מובנות"),
    (("opening_hours",),
     ", כדי שהמבקרים יוכלו לתכנן את ההגעה",
     ", ואם השעות ישתנו בהמשך תופיע הודעה מעודכנת בכניסה למקום"),
    (("million_exact",),
     ", לאחר שהסתיים העדכון האחרון של המאגר",
     ", והצוות מתכנן לבדוק את הספירה שוב אחרי שיושלמו גם הרשומות שעדיין חסרות"),
    (("meeting_minute",),
     ", כדי שכל המשתתפים יספיקו להגיע בזמן",
     ", והמשתתפים התבקשו להגיע מעט קודם כדי שאפשר יהיה להתחיל בלי עיכובים"),
    (("data_plan",),
     ", בהתאם לתנאי השירות המפורטים בעלון ההצטרפות",
     ", ומי ששוקל להצטרף לשירות יכול לבדוק את התנאים המלאים לפני שהוא מזמין"),
    (("flight_number",),
     ", והצוות בשדה ערוך לקבל את פני הנוסעים",
     ", ואם יחול שינוי כלשהו תתפרסם הודעה מעודכנת בזמן אמת"),
    (("large_shekels",),
     ", בהתאם לסיכום התקציבי שאושר עם השלמת השלב הזה",
     ", והצוות השווה את הסכום לאומדן הראשוני שנקבע בתחילת הדרך"),
    (("plural_millions",),
     ", והנתון משקף ביקוש גבוה לאורך התקופה",
     ", והמגמה הזאת נמשכה בעקביות בכל החודשים שנבדקו"),
    (("child_half_age",),
     ", וכולם נהנים לראות כמה הוא גדל",
     ", ובכל מפגש משפחתי כולם מתפעלים מהמהירות שבה הוא לומד מילים ומשחקים חדשים"),
    (("month_end_date",),
     ", ומומלץ להשלים את ההיערכות מבעוד מועד",
     ", וכל הגורמים המעורבים קיבלו תזכורת מסודרת לקראת סגירת החודש"),
    (("midnight_time",),
     ", בהתאם לסבב המשמרות שנקבע מראש",
     ", והתורנים מוודאים שהכול מתנהל כשורה גם בשעות השקטות של הלילה"),
    (("general_fraction",),
     ", בהתאם לקצב הביצוע שנקבע בתוכנית",
     ", והיתרה צפויה להסתיים בשלבים הבאים ללא עיכובים חריגים"),
    (("multi_digit_decimal",),
     ", לאחר שהנתונים אומתו פעם נוספת במערכת",
     ", והתוצאה תואמת את טווח הדיוק שהוגדר לפני תחילת הבדיקה"),
    (("airline_flight",),
     ", ומומלץ לעקוב אחר העדכונים על גבי המסכים בטרמינל",
     ", וצוות הקרקע מעדכן את לוח הטיסות בכל שינוי בשער או בזמן"),
)

CONTINUATIONS = {
    archetype: ("", medium, long)
    for archetypes, medium, long in CLAUSE_GROUPS
    for archetype in archetypes
}

# Date starts 0–11 and 22–27 describe a current appointment, 12–16 and 28–33
# an archival event, and 17–21 and 34–39 a long-term plan.
def date_start_indices(year: int) -> tuple[int, ...]:
    if year < 2020:
        return tuple(range(12, 17)) + tuple(range(28, 34))
    if year > 2027:
        return tuple(range(17, 22)) + tuple(range(34, 40))
    return tuple(range(12)) + tuple(range(22, 28))


PAST_DATE_CONTINUATIONS = (
    "",
    ", כפי שעולה מן הרשומות שנשמרו בארכיון",
    ", והדבר מופיע גם במסמכי התקופה שנשמרו לצורך בדיקה היסטורית",
)

# A frame group is an explicit slice of a lexical bank, not a Cartesian
# product of every opening, ending and clause. Indices refer to CONTEXTS.
# Keep the full banks for inspection and historical examples.
@dataclass(frozen=True)
class FrameGroup:
    name: str
    starts: tuple[int, ...]
    ends: tuple[int, ...]
    continuations: tuple[str, str, str] | None = None


def _indices(bank: tuple[str, ...], predicate) -> tuple[int, ...]:
    return tuple(index for index, text in enumerate(bank) if predicate(text))


_RECORD_CONTAINER_RULES = (
    ("form", ("טופס",), {20, 21, 22}),
    ("system", ("במערכת", "מערכת"), {15, 26}),
    ("interface", ("במסך", "בממשק", "בהודעת"), {27, 30}),
    ("artifact", ("בקובץ", "ברשומת", "בדוח", "ברשימת"), {28, 29, 31}),
    ("file", ("תיק",), {11, 23}),
)
_RECORD_EXPLICIT_LOCATIONS = (
    "בטופס ", "על טופס ", "בקובץ ", "במסך ", "בממשק ", "בהודעת ",
    "ברשומת ", "ברשימת ", "בדוח ", "בכרטיס ", "על חזית ", "על גבי ",
    "בקבלה ", "בקבלת ", "בחשבונית ", "בחשבון ", "בפרופיל ", "במערכת ",
    "בתיק ", "בפוליסת ", "ברישיון ", "בדלפק ", "בשער ", "בכניסה ",
    "באפליקציית ", "בהזמנת ", "בהזמנה ", "באישור ", "בביקורת ", "ברישום ",
    "בהשכרת ", "במוסך ", "בשדה ", "בעמדת ", "בקופת ", "בפרטי ",
    "בהצהרה ", "בפתיחת ", "בבקשת ", "בעמוד ", "בחוזה ", "במחלקת ",
    "במלון ", "באתר ", "בשדה התעופה ", "נציג", "סוכנת", "שומר", "מצלמת",
)
_RECORD_CONCRETE_CONTAINER_ENDS = set(range(20, 32))
_PHONE_ARCHETYPES = {
    "mobile", "international_phone", "landline", "local_landline",
    "national_line", "israeli_international", "business_line",
}


def _without(indices: tuple[int, ...], excluded: set[int]) -> tuple[int, ...]:
    return tuple(i for i in indices if i not in excluded)


def _phone_frame_groups(archetype: str, bank: Context) -> tuple[FrameGroup, ...]:
    ends = tuple(range(len(bank.ends)))
    buckets: dict[tuple[str, tuple[int, ...]], list[int]] = {}
    for index, start_text in enumerate(bank.starts):
        tags: list[str] = []
        blocked: set[int] = set()
        if archetype != "mobile":
            blocked.add(12)  # SMS applies only to mobile numbers
        if archetype == "international_phone":
            blocked.add(5)  # US +1 202 offices do not follow Sun–Thu workweek
        if "הודעה" in start_text:
            tags.append("sms")
            blocked.add(12)
        if "שיחה ישירה" in start_text or "לשיחה " in start_text:
            tags.append("call")
            blocked.add(9)
        if "סיוע" in start_text:
            tags.append("assist")
            blocked.add(16)
        if "העבודה" in start_text:
            blocked.add(13)
        if any(w in start_text for w in ("הזמנה", "הזמנות", "להזמנת")):
            tags.append("order")
            blocked.add(18)
        if any(w in start_text for w in ("לתיאום", "תיאום", "לקביעת תור", "מתאמת")):
            tags.append("coord")
            blocked.add(7)
        if any(w in start_text for w in ("לבירור", "לבירורים", "לשאלות")):
            tags.append("inquiry")
            blocked.add(20)
        if "לפרטים" in start_text:
            tags.append("details")
            blocked.add(15)
        if "מענה" in start_text:
            tags.append("answer")
            blocked.update({8, 22})
        if "שעות הקבלה" in start_text:
            tags.append("hours")
            blocked.add(11)
        for end_index, end_text in enumerate(bank.ends):
            phrase = end_text.strip(" .")
            if phrase and phrase in start_text:
                blocked.add(end_index)
        base = "-".join(tags) if tags else "customer"
        allowed = _without(ends, blocked)
        buckets.setdefault((base, allowed), []).append(index)
    used_names: set[str] = set()
    groups = []
    for (base, allowed_ends), start_indices in buckets.items():
        name = f"{base}-contact"
        suffix = 2
        while name in used_names:
            name = f"{base}-{suffix}-contact"
            suffix += 1
        used_names.add(name)
        groups.append(FrameGroup(name, tuple(start_indices), allowed_ends))
    return tuple(groups)


_STATIC_ID_DOC_MARKERS = (
    "מספר הזהות המעודכן בתיק", "על גבי התעודה", "בתיק הסטודנט", "בהצהרה החתומה",
    "בכרטיס החבר", "בכרטיס העלייה", "בעמוד הפרטים", "בפוליסת ", "בפרופיל הנוסע",
    "ברישיון הרכב", "הרכב החלופי", "בחוזה הליסינג", "הרכב המסחרי", "כרטיס התדלוק",
)


def _record_frame_groups(archetype: str, bank: Context) -> tuple[FrameGroup, ...]:
    ends = tuple(range(len(bank.ends)))
    buckets: dict[tuple[str, tuple[int, ...], bool], list[int]] = {}
    for index, start_text in enumerate(bank.starts):
        tags: list[str] = []
        blocked: set[int] = set()
        if archetype in {"bank_account", "license_plate"}:
            blocked.update(_RECORD_CONCRETE_CONTAINER_ENDS)
            if archetype == "license_plate" and any(
                w in start_text for w in ("בשער ", "מצלמת ", "שומר ", "בעמדת הטעינה", "בכניסה לחניון", "שטיפת", "גרר")
            ):
                blocked.update({11, 12, 16})
        for label, markers, end_indices in _RECORD_CONTAINER_RULES:
            if any(marker in start_text for marker in markers):
                tags.append(label)
                blocked.update(end_indices)
        if any(loc in start_text for loc in _RECORD_EXPLICIT_LOCATIONS):
            tags.append("located")
            blocked.update(_RECORD_CONCRETE_CONTAINER_ENDS)
        if any(w in start_text for w in ("רישום", "נרשם", "נרשמה", "נרשמים", "רשום", "רשמה", "רשם")):
            blocked.update({1, 3, 6, 8, 10, 22, 31})
        if any(w in start_text for w in ("נמסר", "מסר")):
            blocked.update({2, 5, 13})
        if any(w in start_text for w in ("מעודכן", "עודכן", "עדכון", "עדכנה")):
            blocked.update({4, 6})
        if any(w in start_text for w in ("פנייה", "הפונה")):
            blocked.update({12, 16})
        if any(w in start_text for w in ("אישור", "אושר")):
            blocked.update({14, 19, 25})
        if any(w in start_text for w in ("פרטי", "הפרטים")):
            blocked.update({4, 5, 12, 17})
        if "מוקד" in start_text:
            blocked.add(19)
        if "מופיע" in start_text:
            blocked.add(17)
        if any(w in start_text for w in ("מצוין", "צוין", "צוינה", "צוינו", "ציינו")):
            blocked.add(11)
        for end_index, end_text in enumerate(bank.ends):
            phrase = end_text.strip(" .")
            if phrase and phrase in start_text:
                blocked.add(end_index)
        is_static_doc = (
            index != 0
            and archetype in {"civil_id", "passport_id", "license_plate"}
            and any(m in start_text for m in _STATIC_ID_DOC_MARKERS)
        )
        base = "-".join(tags) if tags else "general"
        allowed = _without(ends, blocked)
        buckets.setdefault((base, allowed, is_static_doc), []).append(index)
    static_doc_clauses = (
        "",
        ", והפרטים תואמים את המסמכים הרשמיים שנמסרו",
        ", ומומלץ לוודא שהמספר מעודכן בכל המסמכים הרלוונטיים לפני הפנייה",
    )
    used_names: set[str] = set()
    groups = []
    for (base, allowed_ends, is_static_doc), start_indices in buckets.items():
        name = f"{base}-record"
        suffix = 2
        while name in used_names:
            name = f"{base}-{suffix}-record"
            suffix += 1
        used_names.add(name)
        groups.append(FrameGroup(
            name, tuple(start_indices), allowed_ends,
            static_doc_clauses if is_static_doc else None,
        ))
    return tuple(groups)


def frame_groups(archetype: str, values: dict) -> tuple[FrameGroup, ...]:
    bank = CONTEXTS[archetype]
    starts = tuple(range(len(bank.starts)))
    ends = tuple(range(len(bank.ends)))
    if archetype in _PHONE_ARCHETYPES:
        return _phone_frame_groups(archetype, bank)
    if bank.ends is RECORD:
        return _record_frame_groups(archetype, bank)
    if archetype in {"full_date", "slash_date"}:
        year = values["year"]
        era = "historical" if year < 2020 else "future" if year > 2027 else "current"
        if era == "historical":
            # Archive records cannot be placed at present-day venues or
            # followed by invitations to an event that already took place.
            hist_ends = _indices(bank.ends, lambda text: text in {
                " לפי לוח הזמנים.", " לפי התיעוד.", " לפי הרשומות.",
                " על פי הארכיון.", " ברישומי המוסד.", " לפי פרוטוקול הישיבה.",
                " כפי שנרשם ביומן.", " בהתאם להחלטת הוועדה.", " לפי המסמך הרשמי.",
                " על פי התעודה המקורית.", " לפי סיכום הדיון.", " כפי שצוין בתיק.",
            })
            return (FrameGroup(era, tuple(date_start_indices(year)), hist_ends,
                               ("", ", לפי המסמכים שנשמרו מאז",
                                ", והמידע אומת מול הרשומות המקוריות של אותה תקופה")),)
        if era == "future":
            # Round-two #7 was explicitly accepted, including the venue and
            # attendee clause. Constrain archival dates only.
            return (FrameGroup(era, tuple(date_start_indices(year)),
                               _without(ends, {28, 34})),)
        deadlines = (6, 11)
        interview = (5,)
        tour = (7, 24) if archetype == "full_date" else (7,)
        exam = (8,)
        admin_ends = _indices(bank.ends, lambda text: text in {
            " לפי לוח הזמנים.", " לבקשת הצוות.", " בתיאום עם המארגנים.",
            " לפי הרשומות.", " לפי התיעוד.", " לפי התכנון.", " בהתאם לתוכנית העבודה.",
            " ברישומי המוסד.", " לפי פרוטוקול הישיבה.", " כפי שנרשם ביומן.",
            " בהתאם להחלטת הוועדה.", " לפי המסמך הרשמי.", " לפי סיכום הדיון.",
            " כפי שצוין בתיק.", " לפי הודעת המזכירות.",
        })
        no_archive_only = _without(ends, {28, 34})
        interview_blocked = set(_indices(bank.ends, lambda text: any(
            v in text for v in ("באולם הספורט", "ברחבת העירייה", "במתחם האירועים", "בנוכחות המוזמנים", "במוזיאון", "בגלריה")
        ))) | {28, 34}
        tour_blocked = set(_indices(bank.ends, lambda text: any(
            v in text for v in ("בחדר הישיבות", "באודיטוריום", "באולם הספורט")
        ))) | {28, 34}
        exam_blocked = set(_indices(bank.ends, lambda text: any(
            v in text for v in ("ברחבת העירייה", "במרכז המבקרים", "במוזיאון", "בגלריה", "במתחם האירועים", "בנוכחות המוזמנים")
        ))) | {28, 34}
        special_current = set(deadlines + interview + tour + exam)
        return (
            FrameGroup("current", tuple(i for i in date_start_indices(year) if i not in special_current), no_archive_only),
            FrameGroup("current-interview", interview, _without(ends, interview_blocked),
                       ("", ", וזימון מסודר נשלח מראש בדואר האלקטרוני",
                        ", ומומלץ להגיע למקום כמה דקות לפני השעה שנקבעה")),
            FrameGroup("current-tour", tour, _without(ends, tour_blocked)),
            FrameGroup("current-exam", exam, _without(ends, exam_blocked),
                       ("", ", והנחיות הכניסה לחדר הבחינה פורסמו באתר",
                        ", והנבחנים התבקשו להגיע מוקדם ולהצטייד בתעודה מזהה")),
            FrameGroup("current-deadline", deadlines, admin_ends,
                       ("", ", לפי העדכון האחרון שנשלח לצוות",
                        ", והנחיות המסירה המלאות מופיעות בהודעה המסכמת")),
        )
    if archetype == "address":
        # Keep #18 (arrival opening + address-sharing continuation) intact;
        # only prevent literal institution-landmark self-reference (#17).
        institutions = _indices(bank.starts, lambda text: any(
            term in text for term in ("בית הספר", "החניון", "הספרייה", "נקודת האיסוף", "תחנת האוטובוס", "המרכז הקהילתי")
        ))
        return (
            FrameGroup("general", _without(starts, set(institutions)), ends),
            FrameGroup("civic-institution", institutions, _without(ends, {2, 12, 13, 17, 20, 22})),
        )
    if archetype == "slash_address":
        residence = (2, 5, 12, 20, 26)
        records = (1, 7, 13, 18, 21, 25)
        same_day = (17, 22)
        service_visit = (9, 16, 23, 24)
        pickup_or_notice = (8, 15)
        dispatch = _without(starts, set(residence + records + same_day + service_visit + pickup_or_notice))
        location_ends = (1, 23, 24, 25, 26, 27, 28, 29, 30, 32, 33, 34, 35, 36, 37)
        record_ends = (0, 1, 6, 10, 13, 20, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37)
        visit_ends = _without(ends, {8, 14, 15, 19, 21})
        notice_ends = _without(ends, {8, 14, 21})
        return (
            FrameGroup("delivery-dispatch", dispatch, ends),
            FrameGroup("service-visit", service_visit, visit_ends),
            FrameGroup("pickup-or-notice", pickup_or_notice, notice_ends),
            FrameGroup("same-day-delivery", same_day, _without(ends, {2, 3, 4, 5, 9, 12, 17, 18, 22})),
            FrameGroup("residence", residence, location_ends),
            FrameGroup("address-record", records, record_ends),
        )
    if archetype == "delivery":
        pickup = (18, 25)
        warehouse_dispatch = (8,)
        order_dispatch = (14, 22)
        freight_dispatch = (11, 16)
        general_dispatch = _without(
            starts,
            set(pickup + warehouse_dispatch + order_dispatch + freight_dispatch),
        )
        return (
            FrameGroup("collection", pickup,
                       _indices(bank.ends, lambda text: text not in {
                           " עם שליח עד הבית.", " במסגרת המשלוח היומי.",
                           " במסירה אישית.", " לפי כתובת המגורים."}),
                       ("", ", והכתובת נמסרה למי שאמור לאסוף את החבילה",
                        ", ופרטי הכתובת נבדקו כדי שהאיסוף יתבצע ללא עיכוב")),
            FrameGroup("dispatch", general_dispatch, ends),
            FrameGroup("warehouse-dispatch", warehouse_dispatch, _without(ends, {20})),
            FrameGroup("order-dispatch", order_dispatch, _without(ends, {1, 9})),
            FrameGroup("freight-dispatch", freight_dispatch, _without(ends, {7, 22})),
        )
    if archetype == "purchase":
        institutional = (6, 12, 13, 14, 20, 21, 22, 24, 27, 28, 29)
        morning_retail = (3, 17)
        evening_retail = (1, 26)
        ordered_retail = (10, 11)
        tour_retail = (25,)
        is_furniture = values["noun"]["singular"] in {"שולחן", "כיסא", "מדף", "מנורה"}
        base_retail_ends = _indices(bank.ends, lambda text: text not in {
            " במחסן המרכזי.", " אצל המפיץ.", " במרוכז.", " עבור הצוות.",
            " אצל הספק.", " אצל הספק הקבוע.", " בחנות המפעל.", " לפי הרשימה."}
            and (not is_furniture or text != " בשוק."))
        institutional_ends = _indices(bank.ends, lambda text: text not in {
            " אחרי העבודה.", " בסניף השכונתי.", " בשוק.", " במתחם הקניות.", " לפי הרשימה."})
        sfx = "-furniture" if is_furniture else ""
        general_retail = _without(
            starts,
            set(institutional + morning_retail + evening_retail + ordered_retail + tour_retail),
        )
        return (
            FrameGroup("retail" + sfx, general_retail, base_retail_ends),
            FrameGroup("morning-retail" + sfx, morning_retail, _without(base_retail_ends, {3, 11, 12})),
            FrameGroup("evening-retail" + sfx, evening_retail, _without(base_retail_ends, {12})),
            FrameGroup("ordered-retail" + sfx, ordered_retail, _without(base_retail_ends, {5})),
            FrameGroup("tour-retail" + sfx, tour_retail, _without(base_retail_ends, {3, 17})),
            FrameGroup("institutional", institutional, institutional_ends,
                       ("", ", בהתאם להזמנה המרוכזת שהוכנה מראש",
                        ", כדי להשלים את כל הדרוש לקראת הפעילות המתוכננת")),
        )
    if archetype == "bulk_purchase":
        warehouse = (0, 1, 3, 10, 17)
        supplier = (5,)
        procurement = (4, 6, 8, 11, 13, 14)
        consolidated = (16,)
        branch_opening = (2,)
        distribution = (7, 9, 12, 15, 18, 19)
        return (
            FrameGroup("warehouse-replenishment", warehouse, _without(ends, {0, 6, 8, 15, 18})),
            FrameGroup("supplier-delivery", supplier, _without(ends, {0, 5, 6, 8, 15, 18})),
            FrameGroup("procurement-program", procurement, _without(ends, {1, 4, 7, 11, 14})),
            FrameGroup("consolidated-shipment", consolidated, _without(ends, {1, 4, 7, 11, 12, 14})),
            FrameGroup("branch-opening", branch_opening, _without(ends, {2, 5, 9, 13, 15, 19})),
            FrameGroup("network-distribution", distribution, _without(ends, {2, 5, 9, 13, 15})),
        )
    if archetype == "approximate":
        personal = (0, 1)
        dispatched = (10, 12, 13, 23)
        counted = (4, 14)
        checked = (8,)
        other_inventory = _without(starts, set(personal + dispatched + counted + checked))
        institutional_ends = tuple(range(12, 24)) + tuple(range(32, 38))
        inventory_clauses = (
            "",
            ", לפי הספירה האחרונה במלאי",
            ", כדי שהצוות יוכל לתכנן את החלוקה לפי הכמות שנרשמה",
        )
        groups = [
            FrameGroup("inventory", other_inventory, institutional_ends, inventory_clauses),
            FrameGroup("counted-inventory", counted, _without(institutional_ends, {20}), inventory_clauses),
            FrameGroup("checked-inventory", checked, _without(institutional_ends, {14}), inventory_clauses),
            FrameGroup(
                "dispatched-summary",
                dispatched,
                (12, 13, 15, 16, 20, 22, 32, 33, 34, 35, 36, 37),
                ("", ", בהתאם לנתוני החלוקה שרוכזו השבוע", ", והנתונים הועברו לצוות לצורך תכנון ההזמנה הבאה"),
            ),
        ]
        bucket = PURCHASE_BUCKETS[values["noun"]["singular"]]
        if values["quantity"] <= PURCHASE_LIMITS[bucket]:
            personal_ends = (0, 3, 7, 10, 24, 25, 26, 27, 28, 29, 30, 31)
            groups.append(FrameGroup(
                "personal", (0,), personal_ends,
                ("", ", בהתאם לרשימה שהוכנה מראש", ", כדי לסיים את הקניות לפני שהחנות תיסגר"),
            ))
            groups.append(FrameGroup(
                "personal-list-checked", (1,), personal_ends,
                ("", ", בהתאם לתכנון המוקדם", ", כדי לסיים את הקניות לפני שהחנות תיסגר"),
            ))
        return tuple(groups)
    if archetype == "numeric_calendar":
        is_summer = values["month_number"] in (6, 8)
        personal_starts = (2, 10, 24) if is_summer else (2, 24)
        summer_exhibit = (27,) if is_summer else ()
        deadlines = (7, 9, 19, 22, 26)
        tour = (6, 21)
        campus = (12,)
        exam = (13,)
        large_stage = (11, 23, 25) + summer_exhibit
        excluded_public = {2, 6, 7, 9, 10, 11, 12, 13, 19, 21, 22, 23, 24, 25, 26, 27}
        personal_ends = (23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34)
        deadline_ends = (2, 20, 23, 24, 25, 26, 28, 31, 35, 36, 37)
        public_event_ends = _without(ends, {29, 30, 32, 33, 34})
        return (
            FrameGroup(
                "summer-personal-trip" if is_summer else "personal-trip",
                personal_starts,
                personal_ends,
                ("", ", אחרי שסיימנו לתכנן את הנסיעה",
                 ", וכבר בדקנו את זמני היציאה וההגעה כדי להתארגן מראש"),
            ),
            FrameGroup(
                "deadline", deadlines, deadline_ends,
                ("", ", לפי העדכון האחרון",
                 ", והפרטים המעודכנים מופיעים בהודעה שנשלחה לנרשמים"),
            ),
            FrameGroup("guided-tour", tour, _without(public_event_ends, {1, 3, 5, 9, 10, 12})),
            FrameGroup("campus-open-day", campus, (1, 2, 3, 5, 9, 10, 19, 20, 21, 22, 23, 24, 25, 28, 35, 36)),
            FrameGroup("exam-schedule", exam, _without(public_event_ends, {13, 14, 15, 16, 18, 21, 22})),
            FrameGroup("summer-stage-or-festival" if is_summer else "stage-or-festival",
                       large_stage, _without(public_event_ends, {10})),
            FrameGroup("public-event", _without(starts, excluded_public), public_event_ends),
        )
    if archetype == "decimal_temp":
        forecast = (0,)
        morning = (8,)
        midday = (4, 18)
        kinneret_midday = (12,)
        shade = (6,)
        coast = (9,)
        valley = (10,)
        negev = (11,)
        mountains = (13, 16)
        balcony = (19,)
        station = (3, 5)
        special = set(
            forecast + morning + midday + kinneret_midday + shade
            + coast + valley + negev + mountains + balcony + station
        )
        no_daypart = _without(ends, {3, 5, 9, 14, 17, 18})
        return (
            FrameGroup("forecast", forecast, _without(ends, {6, 7, 9, 15})),
            FrameGroup("general", _without(starts, special), _without(ends, {9})),
            FrameGroup("station-reading", station, _without(ends, {7, 9})),
            FrameGroup("morning-reading", morning, no_daypart),
            FrameGroup("midday-reading", midday, no_daypart),
            FrameGroup("kinneret-midday", kinneret_midday, _without(no_daypart, {12})),
            FrameGroup("shade-reading", shade, _without(ends, {4, 9, 14, 18})),
            FrameGroup("coastal-reading", coast, _without(ends, {9, 12, 13})),
            FrameGroup("valley-reading", valley, _without(ends, {9, 11, 12, 13})),
            FrameGroup("desert-reading", negev, _without(ends, {9, 11})),
            FrameGroup("mountain-reading", mountains, _without(ends, {9, 11, 12, 13})),
            FrameGroup("balcony-reading", balcony, _without(ends, {2, 7, 8, 9, 10, 16})),
        )
    if archetype == "negative_temp":
        morning = (0,)
        night = (1, 7, 10, 13, 14)
        station = (8, 17)
        peaks = (3, 6)
        valleys = (12, 15)
        high_alt = (2, 5, 11, 16, 19)
        general = _without(starts, set(morning + night + station + peaks + valleys + high_alt))
        return (
            FrameGroup("morning-cold", morning, _without(ends, {3, 8, 13, 16, 17})),
            FrameGroup("night-cold", night, _without(ends, {2, 3, 4, 8, 13})),
            FrameGroup("mountain-station", station, _without(ends, {6, 8})),
            FrameGroup("alpine-peak", peaks, _without(ends, {8, 10, 12})),
            FrameGroup("alpine-valley", valleys, _without(ends, {8, 10, 11, 12})),
            FrameGroup("high-altitude", high_alt, _without(ends, {8, 12})),
            FrameGroup("general-cold", general, _without(ends, {8})),
        )
    if archetype == "flight_number":
        daypart = (3, 4)
        return (
            FrameGroup("general-flight", _without(starts, set(daypart)), ends),
            FrameGroup("daypart-flight", daypart, _without(ends, {6, 7})),
        )
    if archetype == "departure":
        hour = values["minute_of_day"] // 60
        morning_ok = 5 <= hour < 12
        night_ok = hour >= 20 or hour < 5
        first_bus_ok = 4 <= hour <= 8
        last_bus_ok = hour >= 20 or hour <= 1
        school_ok = 6 <= hour <= 17
        daytime_ok = 6 <= hour <= 20
        morning_block = set() if morning_ok else {9}
        rail_block = {12, 13, 16, 17, 18, 22} | morning_block
        road_block = {6, 18} | morning_block
        general_road = (0, 3, 9, 10, 11, 15, 17, 19, 22, 24, 26, 29, 31, 33)
        general_rail = (1, 2, 6, 7, 8, 23, 28)
        origin_bus = (12, 13, 25, 27)
        platform_rail = (18, 30)
        groups = [
            FrameGroup("general-transit" if morning_ok else "general-transit-nonmorning",
                       general_road, _without(ends, road_block)),
            FrameGroup("rail-transit" if morning_ok else "rail-transit-nonmorning",
                       general_rail, _without(ends, rail_block)),
            FrameGroup("origin-bus", origin_bus, _without(ends, {6, 9, 12, 17, 18, 22})),
            FrameGroup("platform-rail", platform_rail, _without(ends, {6, 9, 12, 13, 16, 17, 18, 22})),
        ]
        if first_bus_ok:
            groups.append(FrameGroup("first-service" if morning_ok else "first-service-early",
                                     (5,), _without(ends, road_block)))
            groups.append(FrameGroup("first-rail" if morning_ok else "first-rail-early",
                                     (32,), _without(ends, rail_block | {7})))
        if last_bus_ok:
            groups.append(FrameGroup("last-service", (4,), _without(ends, {6, 9, 18})))
        if school_ok:
            groups.append(FrameGroup("school-bus" if morning_ok else "school-bus-afternoon",
                                     (20,), _without(ends, road_block)))
        if daytime_ok:
            groups.append(FrameGroup("conference-shuttle", (16,), _without(ends, {6, 9})))
            groups.append(FrameGroup("guided-tour-departure", (21,), _without(ends, {6, 7, 9, 12, 17, 19})))
        if night_ok:
            groups.append(FrameGroup("night-train", (14,), _without(ends, {9, 12, 13, 16, 17, 18, 22})))
        return tuple(groups)
    if archetype == "score":
        left, right = (int(part) for part in values["score"].split(":"))
        is_tie = left == right
        tie_blocked = {9, 10} if is_tie else set()
        suffix = "-tie" if is_tie else ""
        groups = [
            FrameGroup("halftime-score" + suffix, (0,),
                       _without(ends, {4, 5, 15} | tie_blocked)),
            FrameGroup("full-match" + suffix, (1, 2, 4, 5, 6, 7, 14, 15, 20, 21, 22, 23, 24, 29),
                       _without(ends, tie_blocked)),
            FrameGroup("cup-match" + suffix, (8,),
                       _without(ends, {6, 7, 11, 12} | tie_blocked)),
            FrameGroup("first-round" + suffix, (10,),
                       _without(ends, {7, 12, 13} | tie_blocked)),
            FrameGroup("stage-or-friendly" + suffix, (3, 16, 17, 18, 19),
                       _without(ends, {6, 7, 11, 12, 13} | tie_blocked)),
            FrameGroup("friendly-match" + suffix, (11,),
                       _without(ends, {5, 6, 7, 11, 12, 13, 18} | tie_blocked)),
        ]
        if is_tie:
            groups.append(FrameGroup("drawn-match", (25, 26), _without(ends, tie_blocked)))
        else:
            groups.append(FrameGroup(
                "set-score", (9,), _without(ends, {4, 5, 6, 7, 11, 12, 15}),
                ("", ", לאחר חילופי נקודות ממושכים משני הצדדים",
                 ", אחרי דקות צמודות שבהן שני הצדדים נאבקו על כל נקודה"),
            ))
            groups.append(FrameGroup("winning-match", (12, 13, 27, 28), _without(ends, {3, 9, 10})))
        return tuple(groups)
    if archetype == "data_plan":
        mobile = (0, 2, 3, 7, 8)
        broadband = (1, 9, 10, 14, 18)
        roaming = (12,)
        business = (4,)
        monthly = (5,)
        annual = (15,)
        general = _without(starts, set(mobile + broadband + roaming + business + monthly + annual))
        no_echo = _without(ends, {1})
        return (
            FrameGroup("mobile-plan", mobile, _without(no_echo, {10, 13})),
            FrameGroup("fixed-broadband", broadband, _without(no_echo, {9, 18})),
            FrameGroup("roaming-plan", roaming, _without(no_echo, {7, 9, 10, 13, 14, 18})),
            FrameGroup("business-plan", business, _without(no_echo, {9})),
            FrameGroup("monthly-plan", monthly, _without(no_echo, {7, 14})),
            FrameGroup("annual-plan", annual, _without(no_echo, {5, 7, 14})),
            FrameGroup("general-plan", general, no_echo),
        )
    if archetype == "version":
        server = (4,)
        test_env = (5,)
        app_store = (14,)
        device_fw = (9, 17)
        stable = (18,)
        general = _without(starts, set(server + test_env + app_store + device_fw + stable))
        # Ending 3 ("לאחר הבדיקות") echoes Cont1 ("אחרי שהצוות סיים לבדוק את העדכון");
        # preserve R4 #23 (test_env start=5 with end=8 "עבור כלל המשתמשים").
        return (
            FrameGroup("general-release", general, _without(ends, {3})),
            FrameGroup("server-release", server, _without(ends, {3, 4, 18})),
            FrameGroup("test-environment", test_env, _without(ends, {1, 3, 9})),
            FrameGroup("app-store-release", app_store, _without(ends, {3, 4, 7, 9, 13, 18})),
            FrameGroup("device-firmware", device_fw, _without(ends, {3, 4, 18})),
            FrameGroup("stable-channel", stable, _without(ends, {3, 16})),
        )
    if archetype == "fraction":
        savory_clauses = (
            "",
            ", ומערבבים היטב במהלך הבישול",
            ", וממשיכים לבשל על אש נמוכה עד שכל הטעמים מתמזגים",
        )
        return (
            FrameGroup("general-recipe", (0, 1, 11, 12, 15, 16, 20, 25),
                       (0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 17, 18, 19, 20, 21, 25, 28, 29, 32, 33)),
            FrameGroup("sweet-pour", (3, 6), (0, 1, 2, 5, 6, 14, 17, 20, 21, 28, 29, 32, 33)),
            FrameGroup("savory-pour", (10, 21, 24, 27),
                       (1, 2, 14, 15, 16, 19, 20, 22, 23, 24, 25, 26, 27, 30), savory_clauses),
            FrameGroup("dough-and-filling", (2, 7, 22),
                       (0, 1, 2, 3, 4, 6, 7, 8, 11, 12, 13, 14, 17, 18, 19, 20, 21, 28, 29, 32)),
            FrameGroup("sweet-baking", (9, 13, 14, 26),
                       (0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 14, 17, 18, 20, 21, 28, 29, 32, 33)),
            FrameGroup("sweet-cream-glaze", (17, 18),
                       (0, 1, 3, 5, 6, 12, 13, 14, 17, 18, 20, 21, 25, 28, 29, 32, 33)),
            FrameGroup("savory-sauce", (5,),
                       (1, 2, 8, 14, 15, 16, 18, 19, 20, 22, 23, 24, 25, 26, 27, 30, 32), savory_clauses),
            FrameGroup("savory-pot", (4, 8, 19, 23),
                       (1, 2, 9, 10, 14, 15, 16, 19, 20, 22, 23, 24, 25, 27, 30, 31), savory_clauses),
        )
    if archetype == "age_range":
        study_starts = (13, 14)
        neutral_program = (0, 1, 4, 5, 6, 10, 12, 18)
        audience_groups = {
            "6–12": ("children-6-12", neutral_program + (2, 3, 7, 8, 11, 17, 19)),
            "8–14": ("children-youth-8-14", neutral_program + (2, 3, 7, 8, 17, 19)),
            "12–18": ("teens-12-18", neutral_program + (9, 19)),
            "18–25": ("young-adults-18-25", neutral_program + (15, 16)),
        }
        name, audience_starts = audience_groups[values["age_range"]]
        program_ends = tuple(range(0, 19))
        study_ends = (0, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23)
        study_clauses = (
            "",
            ", בהתאם לחלוקה הדמוגרפית שנקבעה בבדיקה",
            ", והנתונים נותחו בנפרד עבור קבוצת הגיל הזאת בסיכום הממצאים",
        )
        return (
            FrameGroup(name, tuple(sorted(audience_starts)), program_ends),
            FrameGroup("demographic-study", study_starts, study_ends, study_clauses),
        )
    if archetype == "maximum_attendees":
        # A table/room/vehicle cannot hold an auditorium-sized crowd. Avoid
        # repeating "at most", "each round", or "participants" as an ending.
        generic_ends = _indices(bank.ends, lambda text: text not in {
            " משתתפים לכל היותר.", " משתתפים בכל סבב.",
            " משתתפים לפי ההערכה.", " משתתפים במסגרת המגבלה."})
        # #9 explicitly accepted a table with 180 participants; do not
        # invent a physical maximum that overrules the user.
        return (FrameGroup("capacity", starts, generic_ends),)
    if archetype == "pill_range":
        daypart = (12,)
        initial = (15,)
        prn = (17, 27)
        all_stages = (6,)
        symptom = (9,)
        pharmacist_mention = (4, 16, 20)
        dosage_mention = (22,)
        general = _without(starts, set(daypart + initial + prn + all_stages + symptom + pharmacist_mention + dosage_mention))
        return (
            FrameGroup("general-medication", general, _without(ends, {9, 12, 16})),
            FrameGroup("pharmacist-guidance", pharmacist_mention, _without(ends, {9, 12, 16, 24})),
            FrameGroup("dosage-recommendation", dosage_mention, _without(ends, {9, 12, 15, 16, 27})),
            FrameGroup("all-stages", all_stages, _without(ends, {8, 9, 11, 12, 16, 17})),
            FrameGroup("symptom-relief", symptom, _without(ends, {9, 12, 16, 19})),
            FrameGroup("daypart-dose", daypart, (1, 3, 4, 6, 8, 13, 15, 17, 19, 20, 21, 22, 24, 26, 27, 28, 29)),
            FrameGroup("initial-phase", initial, _without(ends, {2, 8, 9, 12, 16, 17, 19})),
            FrameGroup("as-needed", prn, (3, 4, 5, 6, 7, 11, 13, 14, 15, 18, 20, 21, 22, 24, 26, 28, 29)),
        )
    if archetype == "opening_hours":
        hotline = (3,)
        morning_gym = (8,)
        public_cultural = (4, 10, 12, 14, 18)
        walkin_shop = (11, 15, 17)
        commercial_other = (0, 6, 13, 19)
        civic_or_clinic = _without(
            starts,
            set(hotline + morning_gym + public_cultural + walkin_shop + commercial_other),
        )
        return (
            FrameGroup("branch-or-service-hours", commercial_other, _without(ends, {13, 18})),
            FrameGroup("walk-in-retail-hours", walkin_shop, _without(ends, {7, 13, 14, 18})),
            FrameGroup("public-institution-hours", public_cultural, _without(ends, {14})),
            FrameGroup("civic-or-clinic-hours", civic_or_clinic, _without(ends, {14})),
            FrameGroup("morning-facility", morning_gym, _without(ends, {13, 14, 17, 18})),
            FrameGroup("phone-hotline", hotline, _without(ends, {7, 14, 15, 18}),
                       ("", ", כדי שהפונים יוכלו לקבל מענה בשעות הפעילות",
                        ", ואם שעות המענה ישתנו תתפרסם הודעה מעודכנת באתר השירות")),
        )
    if archetype == "weight":
        geo_and_building = {4, 8, 12, 16, 18}
        equipment = (5, 7, 10, 12, 13, 14, 15, 16, 17, 27, 28)
        return (
            FrameGroup("parcel-or-load", _without(starts, set(equipment)), _without(ends, geo_and_building | {14})),
            FrameGroup("equipment-weight", equipment, _without(ends, geo_and_building)),
        )
    if archetype == "area":
        outdoor = (6, 10, 26, 29)
        blueprint_start = (23,)
        other_building = _without(starts, set(outdoor + blueprint_start))
        return (
            FrameGroup("building-space", other_building, _without(ends, {14, 15, 18})),
            FrameGroup("blueprint-space", blueprint_start, _without(ends, {12, 14, 15, 18})),
            FrameGroup("outdoor-plot", outdoor, _without(ends, {10, 11, 12, 14, 15})),
        )
    if archetype == "distance":
        local_routes = (9, 10, 15, 17, 19)
        aerial = (14,)
        geo_ends = _without(ends, {10, 11, 12, 14, 15, 16})
        groups = [
            FrameGroup("intercity-route", _without(starts, set(local_routes + aerial)), geo_ends),
            FrameGroup("aerial-distance", aerial, _without(geo_ends, {8})),
        ]
        if values["kilometers"] <= 50:
            groups.append(FrameGroup("local-route", local_routes, geo_ends))
        return tuple(groups)
    if archetype in {"stopwatch_seconds", "explicit_hundredths"}:
        swimming = (8, 25) if archetype == "stopwatch_seconds" else (8,)
        finish_line = (7, 21) if archetype == "stopwatch_seconds" else (7, 25)
        sprint = (13, 20) if archetype == "stopwatch_seconds" else (13, 20)
        track_record = (12,)
        heat_winner = (14, 22, 29) if archetype == "stopwatch_seconds" else (14,)
        comp_clock = (4, 28) if archetype == "stopwatch_seconds" else (1,)
        stage = (6, 17)
        special = set(swimming + finish_line + sprint + track_record + heat_winner + comp_clock + stage)
        attempt_echo = {12, 13}
        return (
            FrameGroup("general-sport", _without(starts, special), _without(ends, {8} | attempt_echo)),
            FrameGroup("competition-clock", comp_clock, _without(ends, {2, 8, 10} | attempt_echo)),
            FrameGroup("swimming", swimming, _without(ends, {7, 9, 19, 23} | attempt_echo)),
            FrameGroup("finish-line-runner", finish_line, _without(ends, {8, 20} | attempt_echo)),
            FrameGroup("track-sprint", sprint, _without(ends, {8} | attempt_echo)),
            FrameGroup("track-record", track_record, _without(ends, {7, 8} | attempt_echo)),
            FrameGroup("heat-winner", heat_winner, _without(ends, {1, 8, 16, 22} | attempt_echo)),
            FrameGroup("stage-specified", stage, _without(ends, {4, 5, 8, 16, 22} | attempt_echo)),
        )
    if archetype == "stopwatch_minute":
        swimming = (4,)
        track_surface = (14, 16)
        other_track = (3, 10, 18)
        finish_clock = (8,)
        heat_mention = (0, 2, 11)
        champ = (15,)
        decisive = (17,)
        stage = (6, 12, 19)
        special = set(swimming + track_surface + other_track + finish_clock + heat_mention + champ + decisive + stage)
        return (
            FrameGroup("heat-general", heat_mention, _without(ends, {4, 5, 12, 16})),
            FrameGroup("general-sport", _without(starts, special), _without(ends, {5})),
            FrameGroup("swimming", swimming, _without(ends, {2, 14})),
            FrameGroup("track-surface", track_surface, _without(ends, {2, 5})),
            FrameGroup("track", other_track, _without(ends, {5})),
            FrameGroup("finish-clock", finish_clock, _without(ends, {5, 8})),
            FrameGroup("championship-result", champ, _without(ends, {5, 6})),
            FrameGroup("decisive-attempt", decisive, _without(ends, {3, 5, 19})),
            FrameGroup("stage-specified", stage, _without(ends, {4, 5, 9, 12, 16})),
        )
    if archetype in {"money", "money_cents", "dollar_price", "euro_price"}:
        delivery_starts = _indices(
            bank.starts,
            lambda text: any(t in text for t in ("מחיר המשלוח", "דמי המשלוח", "עלות המשלוח", "משלוח האקספרס")),
        )
        completed_bills = _indices(
            bank.starts,
            lambda text: any(
                term in text
                for term in (
                    "החשבון יצא", "סכום החיוב", "עלות התיקון הייתה",
                    "מחיר הארוחה היה", "עלות ההתקנה הייתה", "עלות ההדפסה הייתה",
                    "שילמנו בקופה", "בקבלה נרשם", "סך הקנייה", "בקופה הראשית שילמתי",
                    "בקבלת המרכול", "בחשבונית המס", "סכום הקנייה", "הזמנת החדר במלון הסתכמה",
                    "שמירת החפצים בתחנה עלתה",
                )
            ),
        )
        service_or_fee = _indices(
            bank.starts,
            lambda text: any(
                term in text
                for term in (
                    "עלות השירות", "דמי ההרשמה", "מחיר המנוי",
                    "עלות הבדיקה", "דמי הכניסה", "תעריף הנסיעה",
                    "מחיר הכרטיסייה", "מחיר הסדנה", "מחיר הכרטיס",
                    "התעריף המעודכן", "החיוב החודשי", "דמי החבר", "תעריף החניה",
                    "רישיון התוכנה", "עלות אחסון הענן", "דמי המנוי", "כרטיס הכניסה",
                    "חבילת הגלישה", "עלות חידוש הדומיין", "הקורס המקוון", "אגרת הרישום",
                    "שדרוג החשבון", "כרטיס הרכבת", "תעריף השכרת הרכב", "אגרת הכניסה",
                    "הסיור המודרך", "כרטיס ההמשך", "ארוחת הבוקר במלון", "כרטיס המעבורת",
                )
            ),
        )
        past_ticket = tuple(i for i in service_or_fee if "היה" in bank.starts[i] or "עלה " in bank.starts[i])
        present_service = _without(service_or_fee, set(past_ticket))
        order_price = _indices(bank.starts, lambda text: "מחיר ההזמנה" in text)
        goods = _without(starts, set(delivery_starts + completed_bills + service_or_fee + order_price))
        foreign_block = {7, 12, 23} if archetype in {"dollar_price", "euro_price"} else set()
        groups = [
            FrameGroup("shipping-charge", delivery_starts, _without(ends, {4, 14, 18, 20} | foreign_block)),
            FrameGroup("goods-price", goods, _without(ends, foreign_block)),
            FrameGroup("service-or-fee", present_service, _without(ends, {4, 14, 18, 20} | foreign_block)),
            FrameGroup("past-ticket-price", past_ticket, _without(ends, {1, 2, 4, 6, 8, 10, 13, 14, 18, 19, 20} | foreign_block)),
            FrameGroup(
                "completed-bill", completed_bills,
                _without(ends, {1, 2, 4, 6, 8, 10, 13, 14, 17, 18, 19, 20, 23} | foreign_block),
                ("", ", והסכום מופיע גם בפירוט החשבון", ", והחיוב תועד באישור התשלום שנמסר בסיום העסקה"),
            ),
        ]
        if order_price:
            order_clauses = (
                ("", ", והמחיר מופיע גם בפרטי ההזמנה", ", אבל לפני התשלום כדאי לבדוק אם נוספו חיובים אחרים לסכום שמוצג בהזמנה")
                if 0 in order_price else
                ("", ", והסכום כולל את כל הפריטים שנבחרו", ", ולפני התשלום כדאי לבדוק אם נוספו חיובים נלווים לעסקה")
            )
            groups.append(FrameGroup(
                "order-total-price", order_price,
                _without(ends, {1, 8, 14, 18} | foreign_block),
                order_clauses,
            ))
        return tuple(groups)
    if archetype == "year":
        fem_building = (15, 23)
        fem_org = (0, 14, 17, 25)
        masc_building = (4, 10, 11, 12, 16, 24, 30, 35)
        masc_ongoing = (28,)
        masc_structure = (6, 29, 31)
        archive_inst = (19, 36)
        masc_service = (5, 18, 33)
        journal = (20,)
        legislation = (8, 32, 34, 37)
        events_and_works = (1, 2, 3, 7, 9, 13, 21, 22, 26, 27)
        leg_only_ends = {27, 29}
        return (
            FrameGroup("fem-org", fem_org, _without(ends, {14, 17, 18, 19, 21} | leg_only_ends)),
            FrameGroup("fem-building", fem_building, _without(ends, {14, 17, 18, 19} | leg_only_ends)),
            FrameGroup("masc-building", masc_building, _without(ends, {14, 17} | leg_only_ends)),
            FrameGroup("masc-ongoing-institution", masc_ongoing, _without(ends, {10, 14, 17, 19} | leg_only_ends)),
            FrameGroup("masc-structure", masc_structure, _without(ends, {14, 17, 18, 19} | leg_only_ends)),
            FrameGroup("archive-institution", archive_inst, _without(ends, {4, 14, 17, 21} | leg_only_ends)),
            FrameGroup("masc-service", masc_service, _without(ends, {14, 17, 21} | leg_only_ends)),
            FrameGroup("journal-founded", journal, _without(ends, {10, 11, 12, 17, 21} | leg_only_ends)),
            FrameGroup("legislation", legislation, _without(ends, {6, 7, 8, 9, 10, 11, 12, 14, 15, 17, 18, 19, 21})),
            FrameGroup("events-and-works", events_and_works, _without(ends, {10, 11, 12, 15, 17, 18, 19, 21} | leg_only_ends)),
        )
    if archetype == "age":
        past_milestone = (4, 5, 22, 23, 31)
        retiring = (30,)
        parents_home_block = {16} if values["age"] >= 45 else set()
        celebration_ends = _without(tuple(range(20)) + (21, 22, 25, 26, 29), parents_home_block)
        milestone_ends = (2, 3, 4, 9, 10, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29)
        milestone_clauses = (
            "",
            ", ובני המשפחה ציינו את המאורע במפגש חגיגי",
            ", וקרובים רבים התקשרו לברך לרגל ציון הדרך",
        )
        return (
            FrameGroup("celebration" if not parents_home_block else "adult-celebration",
                       _without(starts, set(past_milestone + retiring)), celebration_ends),
            FrameGroup("past-milestone", past_milestone, milestone_ends, milestone_clauses),
            FrameGroup("retirement-milestone", retiring, _without(milestone_ends, {25}), milestone_clauses),
        )
    if archetype == "survey":
        residents = (6,)
        consumers = (8,)
        employees = (15,)
        students = (18,)
        general = _without(starts, {6, 8, 15, 18})
        return (
            FrameGroup("general-survey", general, ends),
            FrameGroup("residents-survey", residents, _without(ends, {9, 10, 15})),
            FrameGroup("consumers-survey", consumers, _without(ends, {8, 10})),
            FrameGroup("employees-survey", employees, _without(ends, {8, 9, 15})),
            FrameGroup("students-survey", students, _without(ends, {8, 9, 10, 15})),
        )
    if archetype == "duration_half":
        transit_or_wait = (0, 1, 2, 10, 17, 21, 24, 25)
        activity = _without(starts, set(transit_or_wait))
        on_schedule_ends = (11, 16, 19, 20, 21, 22, 23, 24, 25, 26)
        program_only_ends = {7, 12, 13, 17}
        return (
            FrameGroup("transit-duration", transit_or_wait,
                       _without(ends, set(on_schedule_ends) | program_only_ends | {10})),
            FrameGroup("activity-duration", activity, _without(ends, set(on_schedule_ends) | {10})),
            FrameGroup(
                "on-schedule-duration", starts, on_schedule_ends,
                ("", ", בהתאם לתכנון שנקבע מראש", ", כך שאפשר היה להמשיך לשאר המשימות שתוכננו לאותו יום"),
            ),
        )
    if archetype == "decade":
        creative_works = (0, 1, 5, 6, 7, 10, 15, 19)
        founded_entities = (2, 3, 4, 9, 12, 14, 17)
        movements_and_studies = (8, 11, 16)
        urban_entities = (13, 18)
        hist_clauses = (
            "",
            ", לפחות לפי התיאור שפורסם",
            ", והדבר מתועד גם בסקירה ההיסטורית שנשמרה בארכיון המקומי",
        )
        return (
            FrameGroup("creative-work", creative_works, _without(ends, {17})),
            FrameGroup("founded-entity", founded_entities, ends, hist_clauses),
            FrameGroup("movement-or-study", movements_and_studies, _without(ends, {17}), hist_clauses),
            FrameGroup("urban-entity", urban_entities, _without(ends, {1, 2, 6, 7, 8, 17, 19}), hist_clauses),
        )
    if archetype == "minimum_age":
        car_rental = (6,)
        grants_and_exams = (2, 5, 10, 12, 16, 19)
        club = (15,)
        activity = _without(starts, set(car_rental + grants_and_exams + club))
        return (
            FrameGroup("activity-minimum-age", activity, ends),
            FrameGroup("club-membership", club, _without(ends, {6, 14})),
            FrameGroup("grant-or-benefit", grants_and_exams, _without(ends, {8, 12, 14, 18, 19})),
            FrameGroup(
                "car-rental", car_rental, (0, 1, 2, 3, 4, 6, 7, 10, 11, 13, 15, 16),
                ("", ", בהתאם לתנאי הביטוח של החברה", ", ולכן חשוב לבדוק את דרישות הרישיון לפני השלמת ההזמנה"),
            ),
        )
    if archetype == "map_scale":
        non_map_docs = {4, 5, 8, 11, 12, 13, 14, 18, 20}
        printed_maps = (0, 6, 10, 15, 18)
        return (
            FrameGroup("printed-map", printed_maps, _without(ends, non_map_docs | {15})),
            FrameGroup("drawn-map", _without(starts, set(printed_maps)), _without(ends, non_map_docs)),
        )
    if archetype == "ranking":
        race_competitors = (0, 1, 3, 4, 5, 6, 7, 8, 10, 14, 15, 21, 22, 23, 27)
        match_or_team = (2, 9, 11, 12, 13, 16, 17, 18, 19, 20, 24, 25, 26, 28, 29)
        club_starts = (2, 16, 18, 19, 24, 28, 29)
        heat_ends = (0, 11, 17)
        tourney_ends = (1, 2, 3, 4, 5, 6, 10, 12, 13, 18, 19)
        season_ends = (7, 8, 14, 15, 20, 22, 23, 24, 25, 26, 27, 28)
        club_league_ends = (9, 16, 21, 29, 30, 31, 32, 33, 34, 35)
        season_clauses = ("", ", בסיכום כלל המפגשים שנערכו", ", לאחר שקלול כל התוצאות ופרסום הטבלה הרשמית")
        match_clauses = ("", ", אחרי יום ארוך של תחרויות", ", לאחר השלמת כל השלבים וההמתנה לפרסום התוצאות הרשמיות")
        return (
            FrameGroup("race-heat-competitor", race_competitors, heat_ends + tourney_ends),
            FrameGroup("match-or-team-tourney", match_or_team, tourney_ends, match_clauses),
            FrameGroup("season-standing", starts, season_ends, season_clauses),
            FrameGroup("club-league-standing", club_starts, club_league_ends, season_clauses),
        )
    if archetype == "million_exact":
        archive = (0, 18)
        system = (1, 2, 11, 17, 19)
        repository = (3, 13, 16)
        scan = (4, 9)
        merged_file = (6,)
        backup = (7,)
        catalog = (10,)
        audit = (12, 15)
        general = _without(starts, set(archive + system + repository + scan + merged_file + backup + catalog + audit))
        container_ends = {1, 4, 5, 7, 12, 14, 17, 19}
        return (
            FrameGroup("archive-records", archive, _without(ends, {5})),
            FrameGroup("system-records", system, _without(ends, {4})),
            FrameGroup("repository-records", repository, _without(ends, container_ends)),
            FrameGroup("scan-records", scan, _without(ends, {16})),
            FrameGroup("merged-file-records", merged_file, _without(ends, {6} | container_ends)),
            FrameGroup("backup-records", backup, _without(ends, {19})),
            FrameGroup("catalog-records", catalog, _without(ends, container_ends)),
            FrameGroup("audit-records", audit, _without(ends, {2, 3, 8})),
            FrameGroup("general-records", general, ends),
        )
    if archetype == "large_shekels":
        building_projects = (0, 2, 8, 15, 18, 19)
        civil_works = (12, 14, 17)
        grants_and_research = (3, 9, 10)
        tech_and_procurement = (4, 5, 6, 11)
        initial_investment = (7,)
        general_finance = (1, 13, 16)
        return (
            FrameGroup("building-project", building_projects, _without(ends, {7})),
            FrameGroup("civil-works", civil_works, _without(ends, {7, 8})),
            FrameGroup(
                "grants-and-research", grants_and_research,
                _without(ends, {3, 5, 7, 8, 9, 11, 12, 15}),
                ("", ", לפי הדוח הכספי המסכם", ", והנתונים הוצגו לוועדה המלווה עם השלמת הבדיקה התקציבית"),
            ),
            FrameGroup("tech-and-procurement", tech_and_procurement, _without(ends, {8, 12, 15})),
            FrameGroup("initial-investment", initial_investment, _without(ends, {7, 14, 18})),
            FrameGroup("general-finance", general_finance, _without(ends, {7, 12})),
        )
    if archetype == "road_route":
        morning_drive = (14,)
        return_trip = (9,)
        detour = (12,)
        general_route = _without(starts, set(morning_drive + return_trip + detour))
        no_planned_echo = _without(ends, {19})
        return (
            FrameGroup("general-route", general_route, no_planned_echo),
            FrameGroup("morning-route", morning_drive, _without(no_planned_echo, {2, 3, 9})),
            FrameGroup("return-route", return_trip, _without(no_planned_echo, {1, 5, 6, 12, 18})),
            FrameGroup("detour-route", detour, _without(no_planned_echo, {15})),
        )
    if archetype == "postal":
        shipment_starts = (0, 3, 5, 8, 9, 10, 15, 19, 22, 24, 25, 28)
        envelope = (3, 25)
        label = (8,)
        order_confirm = (10,)
        other_shipment = _without(shipment_starts, set(envelope + label + order_confirm))
        form_directory = (1, 16, 26)
        other_directory = _without(starts, set(shipment_starts + form_directory))
        directory_ends = (0, 1, 2, 3, 6, 7, 9, 10, 11, 12, 13, 14, 19)
        directory_clauses = (
            "",
            ", לפי הנתונים המעודכנים במאגר",
            ", והפרט אומת מול רישומי הכתובות הרשמיים",
        )
        return (
            FrameGroup("shipment-postal", other_shipment, ends),
            FrameGroup("envelope-postal", envelope, _without(ends, {5, 17})),
            FrameGroup("package-label-postal", label, _without(ends, {17})),
            FrameGroup("order-postal", order_confirm, _without(ends, {18})),
            FrameGroup("directory-postal", other_directory, _without(directory_ends, {6}), directory_clauses),
            FrameGroup("form-directory-postal", form_directory, _without(directory_ends, {6}), directory_clauses),
        )
    if archetype == "calendar":
        large_or_stage = (7, 8, 10, 16, 17, 22)
        tour = (6,)
        exam = (14,)
        general_cal = _without(starts, set(large_or_stage + tour + exam))
        return (
            FrameGroup("general-calendar", general_cal, ends),
            FrameGroup("stage-or-public-event", large_or_stage, _without(ends, {8})),
            FrameGroup("tour-calendar", tour, _without(ends, {1, 3, 7, 8, 10})),
            FrameGroup("exam-calendar", exam, _without(ends, {11, 12, 13, 14, 16, 20, 21})),
        )
    if archetype == "floor":
        corporate = (14, 19, 20, 24)
        medical = (3, 10)
        open_area = (1, 13, 23, 28, 29, 32, 34, 35)
        elevator_move = (28, 32)
        other_open_area = _without(open_area, set(elevator_move))
        general_rooms = _without(starts, set(corporate + medical + open_area))
        open_clauses = (
            "",
            ", כך שהמבקרים ידעו לאן לעלות",
            ", והכוונה ברורה מופיעה בשילוט שליד המעלית בבניין",
        )
        return (
            FrameGroup("general-room", general_rooms, ends),
            FrameGroup("corporate-floor", corporate, _without(ends, {14, 15, 16})),
            FrameGroup("medical-floor", medical, _without(ends, {14, 16})),
            FrameGroup("open-area-floor", other_open_area, ends, open_clauses),
            FrameGroup("elevator-floor", elevator_move, _without(ends, {1, 7, 19}), open_clauses),
        )
    if archetype == "percent_half":
        past_metrics = (8, 9, 10, 11, 13)
        fixed_discount = (5,)
        forecast_growth = (15,)
        current_rates = _without(starts, set(past_metrics + fixed_discount + forecast_growth))
        past_clauses = (
            "",
            ", לפי הסיכום שנשלח לצוות",
            ", והנתון נבדק מול הדוחות הרשמיים של התקופה הקודמת",
        )
        fixed_clauses = (
            "",
            ", לפי תנאי התוכנית שפורסמו",
            ", והשיעור חל אוטומטית על כל הזמנה שעומדת בתנאים",
        )
        return (
            FrameGroup("current-rate", current_rates, _without(ends, {3, 18})),
            FrameGroup("forecast-rate", forecast_growth, _without(ends, {3})),
            FrameGroup("past-metric", past_metrics, _without(ends, {3, 9, 18}), past_clauses),
            FrameGroup("fixed-discount", fixed_discount, _without(ends, {3, 9, 18}), fixed_clauses),
        )
    if archetype == "infant_age":
        clinic = (11,)
        kindergarten = (13,)
        daycare = (6, 15)
        girls_daycare = (26,)
        girls_other = (22, 23, 24, 25, 27, 28, 29)
        boys_general = _without(tuple(range(22)), set(clinic + kindergarten + daycare))
        boy_ends = tuple(range(26))
        girl_ends = (0, 1, 3, 4, 7, 10, 13, 16, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31)
        girl_clauses = (
            "",
            ", והמשפחה כבר שמה לב כמה היא גדלה",
            ", וכשהיא פוגשת בני משפחה שלא ראו אותה זמן מה כולם מופתעים מכמה היא השתנתה",
        )
        return (
            FrameGroup("general-infant", boys_general, boy_ends),
            FrameGroup("clinic-checkup", clinic, _without(boy_ends, {16})),
            FrameGroup("kindergarten-child", kindergarten, _without(boy_ends, {8, 14, 17})),
            FrameGroup("daycare-toddler", daycare, _without(boy_ends, {8, 14, 17})),
            FrameGroup("girl-infant", girls_other, girl_ends, girl_clauses),
            FrameGroup("girl-daycare-infant", girls_daycare, _without(girl_ends, {31}), girl_clauses),
        )
    if archetype == "section":
        technical = (5, 6, 7, 12, 26)
        legal_admin = (4, 9, 10, 11, 13, 16, 17, 19, 20, 21, 22, 23, 24, 25, 27, 28, 29)
        general_sec = _without(starts, set(technical + legal_admin))
        return (
            FrameGroup("general-section", general_sec, _without(ends, {18})),
            FrameGroup("legal-or-admin-section", legal_admin, _without(ends, {9, 11, 14, 18})),
            FrameGroup(
                "technical-section", technical, _without(ends, {5, 12}),
                ("", ", ואפשר לקרוא שם את ההסבר המלא",
                 ", כדי לוודא שכל הפרטים והדרישות מיושמים כנדרש"),
            ),
        )
    if archetype == "meeting_minute":
        hour = values["minute_of_day"] // 60
        morning_briefing = (3,)
        tomorrow = (0,)
        factory_tour = (6,)
        online_meeting = (12,)
        any_hour_starts = (1, 2, 4, 8, 10, 13, 15, 17, 18)
        business_hours_only = (5, 7, 9, 11, 14, 16, 19)
        groups = [
            FrameGroup("tomorrow-meeting", tomorrow, _without(ends, {17})),
            FrameGroup("general-meeting", any_hour_starts, ends),
            FrameGroup("online-meeting", online_meeting, _without(ends, {8})),
            FrameGroup("factory-tour", factory_tour, _without(ends, {5, 6, 7, 8, 12, 14, 16})),
        ]
        if 8 <= hour <= 20:
            groups.append(FrameGroup("office-hours-meeting", business_hours_only, ends))
        if 6 <= hour < 12:
            groups.append(FrameGroup("morning-briefing", morning_briefing, _without(ends, {17})))
        return tuple(groups)
    if archetype == "plural_millions":
        return (
            FrameGroup("annual-passengers-millions", (0, 1, 2, 3, 5, 6, 7), (0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11)),
            FrameGroup("monthly-passengers-millions", (4,), (0, 2, 4, 5, 6, 7, 8, 9, 10, 11)),
            FrameGroup("users-millions", (8, 9, 10, 12, 13, 14, 15), tuple(range(12, 24))),
            FrameGroup("monthly-users-millions", (11,), (12, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23)),
            FrameGroup("visitors-millions", tuple(range(16, 24)), _without(tuple(range(24, 36)), {25})),
        )
    if archetype == "child_half_age":
        neutral_ends = tuple(range(0, 12))
        boy_ends = neutral_ends + tuple(range(12, 20))
        girl_ends = neutral_ends + tuple(range(20, 28))
        girl_clauses = (
            "",
            ", וכולם נהנים לראות כמה היא גדלה",
            ", ובכל מפגש משפחתי כולם מתפעלים מהמהירות שבה היא לומדת מילים ומשחקים חדשים",
        )
        return (
            FrameGroup("boy-half-age", (0, 1, 2, 3, 4, 6, 7, 9, 10, 11), boy_ends),
            FrameGroup("boy-group-half-age", (8,), _without(boy_ends, {19})),
            FrameGroup("boy-kindergarten-half-age", (5,), _without(boy_ends, {14})),
            FrameGroup("girl-half-age", (12, 13, 14, 15, 16, 18, 19, 21, 22, 23), girl_ends, girl_clauses),
            FrameGroup("girl-group-half-age", (20,), _without(girl_ends, {27}), girl_clauses),
            FrameGroup("girl-kindergarten-half-age", (17,), _without(girl_ends, {22}), girl_clauses),
        )
    if archetype == "month_end_date":
        deadline_starts = tuple(range(0, 12))
        event_starts = tuple(range(12, 24))
        deadline_ends = tuple(range(0, 13))
        event_ends = (0, 3, 5, 9, 10, 12) + tuple(range(13, 26))
        event_clauses = (
            "",
            ", והפרטים המלאים יישלחו למשתתפים בהמשך",
            ", והמארגנים פרסמו מראש את סדר היום המלא של האירוע",
        )
        return (
            FrameGroup("month-end-deadline", deadline_starts, deadline_ends),
            FrameGroup("month-end-event", event_starts, event_ends, event_clauses),
        )
    if archetype == "midnight_time":
        system_starts = tuple(range(0, 12))
        ops_starts = tuple(range(12, 24))
        shared_night = tuple(range(0, 12))
        return (
            FrameGroup("midnight-systems", system_starts, shared_night + tuple(range(12, 18))),
            FrameGroup("midnight-operations", ops_starts, shared_night + tuple(range(18, 24))),
        )
    if archetype == "general_fraction":
        budget_clauses = (
            "",
            ", בהתאם לחלוקה התקציבית שאושרה לשנה הנוכחית",
            ", ושאר המימון יועבר לאחר השלמת אבני הדרך שנקבעו",
        )
        inventory_clauses = (
            "",
            ", בהתאם לתוכנית החלוקה של המרכז הלוגיסטי",
            ", ושאר הפריטים יועברו לסניפים בסבב האספקה הקרוב",
        )
        return (
            FrameGroup("project-fraction", tuple(range(0, 8)), tuple(range(0, 12))),
            FrameGroup("budget-fraction", tuple(range(8, 16)), tuple(range(12, 24)), budget_clauses),
            FrameGroup("inventory-fraction", tuple(range(16, 24)), tuple(range(24, 36)), inventory_clauses),
        )
    if archetype == "multi_digit_decimal":
        calibration = (2, 7)
        lab_starts = (4, 8, 10, 11, 14, 17, 18, 20, 21, 22)
        formula_starts = (0, 3, 9, 15, 16)
        other_metrics = _without(starts, set(calibration + lab_starts + formula_starts))
        return (
            FrameGroup("general-decimal-metric", other_metrics, ends),
            FrameGroup("calibration-decimal", calibration, _without(ends, {4, 10, 20, 21})),
            FrameGroup("lab-measurement-decimal", lab_starts, _without(ends, {1, 5, 10, 14, 19, 20, 21})),
            FrameGroup("formula-or-model-decimal", formula_starts, _without(ends, {1, 5, 8, 14, 19, 23})),
        )
    if archetype == "airline_flight":
        shared_status = tuple(range(0, 8))
        inbound_ends = shared_status + tuple(range(8, 18))
        outbound_ends = shared_status + tuple(range(18, 28))
        europe_inbound = (1, 3, 4, 7, 10)
        other_inbound = _without(tuple(range(0, 12)), set(europe_inbound))
        return (
            FrameGroup("inbound-airline-flight", other_inbound, inbound_ends),
            FrameGroup("inbound-abroad-flight", europe_inbound, _without(inbound_ends, {16})),
            FrameGroup("outbound-airline-flight", tuple(range(12, 24)), outbound_ends),
        )
    return (FrameGroup("general", starts, ends),)


def compatible_frames(archetype: str, values: dict) -> tuple[tuple[int, int, int], ...]:
    """All reviewable start/end/continuation combinations for new samples."""
    frames = []
    for group in frame_groups(archetype, values):
        if not group.starts or not group.ends:
            raise ValueError(f"Empty frame group: {archetype}/{group.name}")
        for start in group.starts:
            for end in group.ends:
                for continuation in range(3):
                    frames.append((start, end, continuation))
    return tuple(frames)


def continuation_for(archetype: str, values: dict, start: int, end: int, index: int) -> str:
    for group in frame_groups(archetype, values):
        if start in group.starts and end in group.ends:
            options = group.continuations or CONTINUATIONS[archetype]
            return options[index]
    # Explicit manual contexts remain renderable for archived examples, but
    # generation never selects them.
    return CONTINUATIONS[archetype][index]
