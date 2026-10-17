"""normalize_tts_words must agree with normalize_tts_text on the same words.

Run with:  python -m pytest tests -q
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "normalizer"))

from hebrew_tts_normalizer import (  # noqa: E402
    TTSNormalizeOptions,
    load_word_replacements,
    normalize_tts_text,
    normalize_tts_words,
    normalize_tts_words_detailed,
)

OPTIONS = {
    "training": TTSNormalizeOptions(
        apply_word_replacements=True,
        expand_numbers=True,
        remove_parentheses=False,
    ),
    "defaults": TTSNormalizeOptions(),
    "detached-punctuation": TTSNormalizeOptions(
        expand_numbers=True, attach_punctuations_to_token=False
    ),
    "no-collapse": TTSNormalizeOptions(expand_numbers=True, collapse_whitespace=False),
}

SENTENCES = [
    "14 ימים",
    "סעיף 2 בתקנות",
    "ב-15 ימים ו-15 שנים",
    "פי 3 ימים במאה 20 שנה",
    "אחרי 14 ימים , 2 שנים .",
    "הלך . ואז ? כן !",
    "foo[bar baz]qux 5 ימים",
    "a (b c) 14 ימים ( 3 ) 14 שנים",
    'קיבלנו " 5 ימים " ועוד 1995',
    "27/01/2026 ו-050-1234567 וגם 3-4 ו-2.5kg",
    "רצנו 20 km , 5 % ו-3 kg. m r p w ב 14:00",
    "ב-20 km ו-5 % ול-2.5kg ב-5 days 52 ילדים",
    "סעיף 60(ב) ו-12(א)(2). (ג) foo(bar)",
    'הלכנו 3 ק"מ ו-5ק"ג ב-5G ו-4K ו-5g',
    "יש 8 ,9 ילדים ,10 ;11. ,12",
    "בגילאי 17-14, ובין 30%-35% או 20-25km ו-5-13 ו-14-17 ילדים 3-4 ק\"ג 3-4 שנים.",
    "סעיף 18א ו-78ב וגם 8,9 ו-8 .5kg ו-3,5 ק\"ג .5",
    "x\t5\nימים 😀 7 שנים",
    "5",
    "",
    "   ",
]


def _joined(results: list[str], keep_punctuations: bool) -> str:
    text = " ".join(part for part in results if part)
    if keep_punctuations:
        text = re.sub(r"\s+([.,?!])", r"\1", text)
    return text.strip()


@pytest.mark.parametrize("name", OPTIONS)
@pytest.mark.parametrize("sentence", SENTENCES)
def test_words_join_back_to_the_whole_sentence(name: str, sentence: str) -> None:
    options = OPTIONS[name]
    replacements = load_word_replacements() if options.apply_word_replacements else None
    words = sentence.split(" ") if not options.collapse_whitespace else sentence.split()

    results = normalize_tts_words(words, options=options, word_replacements=replacements)

    assert len(results) == len(words)
    whole = normalize_tts_text(" ".join(words), options=options, word_replacements=replacements)
    assert _joined(results, options.keep_punctuations) == whole


def test_each_result_belongs_to_its_own_word() -> None:
    options = OPTIONS["training"]
    assert normalize_tts_words(["14", "ימים"], options=options) == ["ארבעה עשר", "ימים"]
    assert normalize_tts_words(["ב-15", "ימים"], options=options) == ["בחמישה עשר", "ימים"]
    assert normalize_tts_words(["1995"], options=options) == ["אלף תשע מאות תשעים וחמש"]
    assert normalize_tts_words(["א", '"', "ב"], options=options) == ["א", "", "ב"]
    assert normalize_tts_words([], options=options) == []


def test_removed_brackets_do_not_shift_the_other_words() -> None:
    options = OPTIONS["defaults"]
    assert normalize_tts_words(["a", "[b", "c]", "d"], options=options) == ["a", "", "", "d"]


@pytest.mark.parametrize(
    "text, expected",
    [
        # The number's own sentence end stops the gender lookahead.
        ("בשנת 2024. הנתונים", "בשנת אלפיים עשרים וארבע. הנתונים"),
        ("בשנת 2024 הנתונים", "בשנת אלפיים עשרים וארבעה הנתונים"),
        # A prefix stays attached to the number.
        ("ל-2 ימים", "לשני ימים"),
        ("ב-15 ימים ו-15 שנים", "בחמישה עשר ימים וחמש עשרה שנים"),
        ("ב-15% מהאנשים", "בחמישה עשר אחוז מהאנשים"),
        # Only a plain number keeps the hyphen; anything else is split as before.
        ("ב-NASA", "ב NASA"),
        ("ו-050-1234567", "ו אפס חמש אפס אחת שתיים שלוש ארבע חמש שש שבע"),
        # Short dates are DD-MM; out-of-range pairs are ranges.
        ("27-01", "עשרים ושבע לראשון"),
        ("20-25", "עשרים עד עשרים וחמש"),
        ("0-5", "אפס עד חמש"),
        ("5-13", "חמש עד שלוש עשרה"),
        # A range reads "עד"; after "בין" the end value takes ל. The order of the text is kept.
        ("בגילאי 14-17, וראתה", "בגילאי ארבע עשרה עד שבע עשרה, וראתה"),
        ("בגילאי 17-14, וראתה", "בגילאי שבע עשרה עד ארבע עשרה, וראתה"),
        ("של בין 30%-35%", "של בין שלושים אחוז לשלושים וחמישה אחוז"),
        ("30%-35%", "שלושים אחוז עד שלושים וחמישה אחוז"),
        ("30-35%", "שלושים עד שלושים וחמישה אחוז"),
        ("בין 35-30 ילדים", "בין שלושים וחמישה לשלושים ילדים"),
        ("בין 20-25km", "בין עשרים לעשרים וחמישה קילומטר"),
        ("2.5-3.5kg", "שניים וחצי עד שלושה וחצי קילוגרם"),
        ("1,000-2,000", "אלף עד אלפיים"),
        # A prefix goes on the first number of a range.
        ("ו-14-17 ילדים", "וארבעה עשר עד שבעה עשר ילדים"),
        ("ב-30%-35%", "בשלושים אחוז עד שלושים וחמישה אחוז"),
        ("ל-5-6 ק\"ג", "לחמישה עד שישה קילוגרם"),
        # A unit after the numbers means a range, not a date (3-4 is DD-MM otherwise).
        ("3-4 ק\"ג", "שלושה עד ארבעה קילוגרם"),
        ("3-4 ק\"ג.", "שלושה עד ארבעה קילוגרם."),
        ("2-3 km", "שני עד שלושה קילומטר"),
        ("3-4 שנים", "שלוש עד ארבע שנים"),
        ("20-25 %", "עשרים עד עשרים וחמישה אחוז"),
        # Days up to 10 are spoken as ordinals in a date.
        ("3-4", "שלישי לרביעי"),
        ("10-11", "עשירי לאחד עשר"),
        ("5/1/2026", "חמישי לראשון אלפיים עשרים ושש"),
        ("1-2", "הראשון לשני"),
        # A unit works the same whether or not a space separates it from the number.
        ("20km", "עשרים קילומטר"),
        ("20 km", "עשרים קילומטר"),
        ("רצנו 20 km. אחר כך", "רצנו עשרים קילומטר. אחר כך"),
        ("2.5 kg", "שניים וחצי קילוגרם"),
        ("20 %", "עשרים אחוז"),
        ("-5 °C", "מינוס חמש מעלות"),
        # Punctuation stuck to the front of a word belongs to the previous word.
        ("8 ,9", "שמונה, תשע"),
        ("יש 8 ,9 ילדים", "יש שמונה, תשעה ילדים"),
        ("אמר ,שלום", "אמר, שלום"),
        ("8 ;9.", "שמונה, תשע."),
        (",9 ילדים", "תשעה ילדים"),
        # "," is only a thousands separator in Hebrew, so other digit,digit tokens are lists.
        ("8,9", "שמונה, תשע"),
        ("8,9km", "שמונה, תשעה קילומטר"),
        ("1,000", "אלף"),
        ("12,345 ילדים", "שנים עשר אלף שלוש מאות ארבעים וחמישה ילדים"),
        # A leading-dot decimal is a fraction: .5 is half.
        (".5", "חצי"),
        ("8 .5kg", "שמונה חצי קילוגרם"),
        (".25", "נקודה עשרים וחמש"),
        ("0.25", "אפס נקודה עשרים וחמש"),
        (".05", "נקודה אפס חמש"),
        (".5kg", "חצי קילוגרם"),
        # A number glued to a Hebrew letter (or followed by one in parentheses) is a section
        # number: the number, then the letter's name.
        ("18א", "שמונה עשרה אלף"),
        ("ב-18א", "בשמונה עשרה אלף"),
        (
            "לפי סעיף 18א לחוק שירותי תשלום וסעיף 78ב לחוק ההוצאה לפועל",
            "לפי סעיף שמונה עשרה אלף לחוק שירותי תשלום וסעיף שבעים ושמונה בית לחוק ההוצאה לפועל",
        ),
        ("12ב(2)", "שתים עשרה בית שתיים"),
        ("3ץ", "שלוש צדי"),
        # Letters before digits make an identifier. Up to 3 digits are a number, more are read
        # digit by digit, and each suffix letter (up to 4) is read on its own.
        ("שמספרו R232D", "שמספרו אר מאתיים שלושים ושתיים די"),
        ("(ג1) זה מה שנשאר לנו", "גימל אחת זה מה שנשאר לנו"),
        ("A12", "איי שתים עשרה"),
        ("B52", "בי חמישים ושתיים"),
        ("K300", "קיי שלוש מאות"),
        ("x0", "איקס אפס"),
        ("A007", "איי אפס אפס שבע"),
        ("R2020", "אר שתיים אפס שתיים אפס"),
        ("COVID19", "COVID תשע עשרה"),
        ("R232D.", "אר מאתיים שלושים ושתיים די."),
        ("AB12CDEF", "AB שתים עשרה סי די אי אף"),
        ("ג1אב", "גימל אחת אלף בית"),
        # ב ל ו ש כ מ before digits are a prefix whose hyphen or space was left out.
        ("ב2020", "באלפיים ועשרים"),
        ("ל5 ילדים", "לחמישה ילדים"),
        ("ו5", "וחמש"),
        ("כ20km", "כעשרים קילומטר"),
        ("ב5ק", "בית חמש קוף"),
        ("ב5ק\"ג", "בחמישה קילוגרם"),
        ("ל3אב", "למד שלוש אלף בית"),
        ("R2.5", "R2.5"),
        # A unit only merges with the number when the next word starts with the unit.
        ("8 ,9km", "שמונה, תשעה קילומטר"),
        ("8 9km", "שמונה תשעה קילומטר"),
        # A parenthesis inside a token separates words; it must not eat only the ")".
        ("סעיף 60(ב)", "סעיף שישים בית"),
        ("סעיף 60(ב) לחוק.", "סעיף שישים בית לחוק."),
        ("סעיף 12(א)(2).", "סעיף שתים עשרה אלף שתיים."),
        ("(ב) ו-(ג).", "ב ו ג."),
        ("foo(bar).", "foo bar."),
        # A prefix stays attached to a number with a unit, glued or separate.
        ("ב-20km", "בעשרים קילומטר"),
        ("ב-20 km", "בעשרים קילומטר"),
        ("ו-5 %", "וחמישה אחוז"),
        ("ל-2.5 kg.", "לשניים וחצי קילוגרם."),
        ("מ-20°C", "מעשרים מעלות"),
        ("ב-5 days", "בחמש days"),
        # "שני"/"שתי" is the form of a bare 2; inside a longer number it is "שניים"/"שתיים".
        ("2 ילדים", "שני ילדים"),
        ("2 ילדות", "שתי ילדות"),
        ("52 ילדים", "חמישים ושניים ילדים"),
        ("52 ילדות", "חמישים ושתיים ילדות"),
        ("102 ילדים", "מאה ושניים ילדים"),
        ("2002 ילדות", "אלפיים ושתיים ילדות"),
        ("12 ילדים", "שנים עשר ילדים"),
        # Hebrew unit abbreviations, in either quote style, glued or separate.
        ('3 ק"מ', "שלושה קילומטר"),
        ("3 ק״מ.", "שלושה קילומטר."),
        ('3ק"מ', "שלושה קילומטר"),
        ('ב-3 ק"מ', "בשלושה קילומטר"),
        ('ב-3ק"מ', "בשלושה קילומטר"),
        ('2 ס"מ', "שני סנטימטר"),
        ('5 ק"ג', "חמישה קילוגרם"),
        ('70 קמ"ש', "שבעים קילומטר בשעה"),
        # A single-letter unit symbol is case-sensitive; other letters after a number are spelled.
        ("5g", "חמישה גרם"),
        ("5 KM", "חמישה קילומטר"),
        ("5G", "חמש ג'י"),
        ("5 G", "חמש ג'י"),
        ("4K", "ארבע קיי"),
        ("ב-5G", "בחמש ג'י"),
        ("רשת 5G חדשה", "רשת חמש ג'י חדשה"),
        # A unit symbol that is not after a number is left alone; a lone capital is not a unit.
        ("km", "km"),
        ("20 G", "עשרים ג'י"),
        ("20. km", "עשרים. km"),
        # Latin letters missing from the replacements table are spelled out.
        ("m r p w", "אם אר פי דאבליו"),
        ("x y a", "איקס ואי איי"),
        # Times are read as written, without "morning" or "afternoon".
        ("אכלנו ב 14:00", "אכלנו ב שתיים"),
        ("ב-14:30", "בשתיים וחצי"),
        ("09:15", "תשע ורבע"),
        ("00:00", "שתים עשרה"),
        ("14:45", "שתיים ארבעים וחמש"),
    ],
)
def test_expansions(text: str, expected: str) -> None:
    assert normalize_tts_text(text, options=OPTIONS["training"]) == expected


def test_separated_unit_belongs_to_the_number_word() -> None:
    options = OPTIONS["training"]
    assert normalize_tts_words(["רצנו", "20", "km."], options=options) == [
        "רצנו", "עשרים קילומטר.", "",
    ]


@pytest.mark.parametrize("name", OPTIONS)
@pytest.mark.parametrize("sentence", SENTENCES)
def test_detailed_texts_match_normalize_tts_words(name: str, sentence: str) -> None:
    options = OPTIONS[name]
    replacements = load_word_replacements() if options.apply_word_replacements else None
    words = sentence.split(" ") if not options.collapse_whitespace else sentence.split()

    detailed = normalize_tts_words_detailed(words, options=options, word_replacements=replacements)

    assert [item.text for item in detailed] == normalize_tts_words(
        words, options=options, word_replacements=replacements
    )


def test_a_separated_unit_is_reported_as_consumed_by_the_number() -> None:
    options = OPTIONS["training"]
    detailed = normalize_tts_words_detailed(["שקלנו", "2.5", "kg", "של"], options=options)
    assert [item.text for item in detailed] == ["שקלנו", "שניים וחצי קילוגרם", "", "של"]
    assert [item.consumed for item in detailed] == [(), (2,), (), ()]


def test_nothing_is_consumed_when_words_are_merely_dropped() -> None:
    options = OPTIONS["training"]
    detailed = normalize_tts_words_detailed(["אחד", "😀", "[הערה]", "20", "ימים"], options=options)
    assert [item.text for item in detailed][1:3] == ["", ""]
    assert all(item.consumed == () for item in detailed)
    # A unit glued to the number, or one that is not a unit, is not a separate consumption.
    detailed = normalize_tts_words_detailed(["20km", "5", "ימים"], options=options)
    assert all(item.consumed == () for item in detailed)
