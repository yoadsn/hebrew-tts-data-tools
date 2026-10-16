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
    assert normalize_tts_words(["ב-15", "ימים"], options=options) == ["ב חמישה עשר", "ימים"]
    assert normalize_tts_words(["1995"], options=options) == ["אלף תשע מאות תשעים וחמש"]
    assert normalize_tts_words(["x", '"', "y"], options=options) == ["x", "", "y"]
    assert normalize_tts_words([], options=options) == []


def test_removed_brackets_do_not_shift_the_other_words() -> None:
    options = OPTIONS["defaults"]
    assert normalize_tts_words(["a", "[b", "c]", "d"], options=options) == ["a", "", "", "d"]
