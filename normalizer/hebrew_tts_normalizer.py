# -*- coding: utf-8 -*-
"""
Hebrew TTS-oriented text normalizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Set
import csv
import re

from hebrew_spoken_form import get_spoken_form, is_preposition_prefix

# --- Constants & Sets ---

__HEBREW_MULTIPLY_WORD = "פי"
__HEBREW_CENTURY_WORD = "מאה"
__HEBREW_MASCULINE_PLURAL_SUFFIX = "ים"
__HEBREW_FEMININE_PLURAL_SUFFIX = "ות"
__HEBREW_THE_PREFIX = "ה"

# Taken from: https://safa-ivrit.org/irregulars/pluralml.php
__HEBREW_EX_FEMININE_PLURALS = {
    "אבנים", "ביצים", "גפנים", "דבורים", "דבלים", "דרכים", "יונים", "כינים",
    "כבשים", "מחטים", "מילים", "נשים", "עדשים", "עיזים", "ערים", "פילגשים",
    "פנינים", "פעמים", "ציפורים", "צפרדעים", "שיבולים", "שנים", "שקמים",
    "תאנים", "תולעים"
}

# Taken from: https://www.safa-ivrit.org/irregulars/pluralfm.php
__HEBREW_EX_MASCULINE_PLURALS = {
    "אבות", "אולמות", "אוצרות", "אורות", "אותות", "אילנות", "אסונות",
    "ארונות", "אריות", "ארמונות", "בורות", "ביזיונות", "גבולות", "גגות",
    "גייסות", "גיליונות", 'דו"חות', "דורות", "דיברות", "וילונות", "זיכרונות",
    "זנבות", "חלומות", "חלונות", "חלזונות", "חסרונות", "חשבונות", "חשדות",
    "חששות", "יינות", "יתרונות", "כוחות", "כינורות", "כיסאות", "כסאות", "לוחות",
    "לילות", "מוחות", "מוסדות", "מזלגות", "מזלות", "מחוזות", "מחנות",
    "מטבעות", "מכרות", "מלונות", "מסעות", "מעונות", "מעיינות", "מעמדות",
    "מקומות", "מקורות", "משקאות", "נהרות", "ניירות", "נרות", "סודות",
    "סולמות", "ספקות", "עופות", "עורות", "עפרונות", "עקרונות", "פיקדונות",
    "פירות", "פתרונות", "צבאות", "צינורות", "צרורות", "קולות", "קירות",
    "קצוות", "קרבות", "קרונות", "רגשות", "רחובות", "ריאיונות", "רעיונות",
    "רצונות", "שבועות", "שדות", "שולחנות", "שופרות", "שטרות", "שיטפונות",
    "שמות"
}

__HEBREW_KNOWN_MASCULINE = {
    "קילוגרם", "קילומטר", "מטר", "סנטימטר", "מילימטר", "שקל", "דולר", "אירו", "אחוז",
    "יום", "חודש", "שבוע"
}

_CHAR_CONVERSION_DICT = {
    # Convert white spaces into blanks:
    "\u0001": "", "\u0007": "", "\t": " ", "\n": " ",
    # Remove non-standard blanks:
    "\u200a": "", "\u200b": "", "\u200c": "", "\u200d": "", "\u200e": "", "\u200f": "",
    # Remove left-to-right and right-to-left markers:
    "\u202a": "", "\u202b": "", "\u202c": "", "\u202d": "", "\u202e": "",
    # Convert Unicode hyphens to a simple dash:
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u2015": "-", "\u05be": "-",
    # Convert Unicode quotation marks to simple quote:
    "\u00ab": '"', "\u00bb": '"', "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u201f": '"', "\u05f4": '"',
    # Convert Unicode apostrophes marks to simple apostrophe:
    "\u2018": "'", "\u2019": "'", "\u201b": "'", "\u05f3": "'",
    # Remove Backslashes
    "\\": "",
}

_SUFFIX_PUNCT_MAP = {
    ".": ".", "..": ".", "...": ".", ",": ",", ";": ",", ":": ",",
    "?": "?", "?!": "?", "!?": "?", "??": "?", "!": "!", "!!": "!",
    "!!!": "!", "…": ".",
}

_SENTENCE_END_PUNCT = (".", "?", "!")

_DROP_PREFIX_MARKS = ('"', "(", "[", "{")
_DROP_SUFFIX_MARKS = ('"', ")", "]", "}")

_BUILTIN_ABBREVIATIONS: Dict[str, str] = {
    'רו"ח': "רואה חשבון",
    'עו"ד': "עורך דין",
    'ד"ר': "דוקטור",
    'פרופ\'': "פרופסור",
    'מס\'': "מספר",
    'רח\'': "רחוב",
    'בע"מ': "בעמ",
    'ת"א': "תל אביב",
    'מע"מ': "מעמ",
}

# Map unit symbol to (Hebrew Name, Gender)
_UNIT_MAP: Dict[str, Tuple[str, str]] = {
    "km": ("קילומטר", "m"),
    "m": ("מטר", "m"),
    "cm": ("סנטימטר", "m"),
    "mm": ("מילימטר", "m"),
    "kg": ("קילוגרם", "m"),
    "g": ("גרם", "m"),
    "ml": ("מיליליטר", "m"),
    "l": ("ליטר", "m"),
    "L": ("ליטר", "m"),
    "GB": ("גיגה בייט", "m"),
    "Mb": ("מגה ביט", "m"),
    "MB": ("מגה בייט", "m"),
    "%": ("אחוז", "m"),
}

_EMOJI_RE = re.compile(
    "["  # noqa: W605
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F700-\U0001F77F"  # alchemical
    "\U0001F780-\U0001F7FF"  # geometric extended
    "\U0001F800-\U0001F8FF"  # arrows C
    "\U0001F900-\U0001F9FF"  # supplemental symbols & pictographs
    "\U0001FA00-\U0001FAFF"  # symbols & pictographs extended-A
    "\U00002700-\U000027BF"  # dingbats
    "\U00002600-\U000026FF"  # misc symbols
    "]+"
)

# Date regexes
# Short: 27/01 or 27-01 (require / or -)
_DATE_SHORT_RE = re.compile(r"^(\d{1,2})([/-])(\d{1,2})$")
# Long: 27/01/2026 or 27.01.2026 (allow .)
_DATE_LONG_RE = re.compile(r"^(\d{1,2})([./-])(\d{1,2})\2(\d{2,4})$")

_MONTH_ORDINAL_MAP = {
    1: "לראשון", 2: "לשני", 3: "לשלישי", 4: "לרביעי", 5: "לחמישי",
    6: "לשישי", 7: "לשביעי", 8: "לשמיני", 9: "לתשיעי", 10: "לעשירי",
    11: "לאחד עשר", 12: "לשנים עשר"
}

_NUM_UNIT_RE = re.compile(r"^([+-]?\d[\d,]*(?:\.\d+)?)(°[CF]|[A-Za-z%]{1,4})$")
_PHONE_RE = re.compile(r"^0\d{1,2}-?\d{7}$")

# What may follow "ב-" for the prefix to stay attached: a plain number, time or percent,
# optionally followed by punctuation (ב-15, ב-15:30, ב-2.5%, ב-15.).
_PREFIXED_NUMBER_TAIL_RE = re.compile(r"^\d+(?:[.,:]\d+)*[%₪$€]?[.,;:!?\"')\]}…]*$")

@dataclass(frozen=True)
class TTSNormalizeOptions:
    # cleanup
    normalize_unicode: bool = True
    remove_parentheses: bool = True
    remove_brackets: bool = True
    collapse_whitespace: bool = True

    # punctuation
    keep_punctuations: bool = True
    attach_punctuations_to_token: bool = True
    
    # special handling
    strip_parentheses: bool = True # If remove_parentheses=False, do we still strip '(' and ')' chars?

    # text rewriting (off by default for safety)
    apply_word_replacements: bool = False
    expand_numbers: bool = False

    # tts-specific expansions
    expand_abbreviations: bool = True
    translate_units: bool = True
    remove_emojis: bool = True
    split_dashes_between_words: bool = True

    # splitting (rarely needed; leave conservative)
    split_markers: Tuple[str, ...] = ("/", "-")


def load_word_replacements_tsv(path: str | Path) -> Dict[str, str]:
    path = Path(path)
    repl: Dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            src = (row.get("SOURCE") or "").strip()
            tgt = (row.get("TARGET") or "").strip()
            if not src or not tgt:
                continue
            repl[src] = tgt
    return repl


def _apply_unicode_cleanup(text: str) -> str:
    out_chars: List[str] = []
    for ch in text:
        out_chars.append(_CHAR_CONVERSION_DICT.get(ch, ch))
    return "".join(out_chars)


def _strip_outer_marks(token: str) -> str:
    # Remove wrapper punctuation like quotes/brackets; keep the core content.
    while token.startswith(_DROP_PREFIX_MARKS):
        token = token[1:]
    while token.endswith(_DROP_SUFFIX_MARKS):
        token = token[:-1]
    return token


def _remove_emojis(text: str) -> str:
    return _EMOJI_RE.sub("", text)


def _split_suffix_punct(token: str) -> Tuple[str, str]:
    token = token.strip()
    if not token:
        return "", ""
    for punct in sorted(_SUFFIX_PUNCT_MAP.keys(), key=len, reverse=True):
        if token.endswith(punct) and len(token) > len(punct):
            core = token[: -len(punct)]
            return core, _SUFFIX_PUNCT_MAP[punct]
    return token, ""


def _normalize_abbrev_key(token: str) -> str:
    return token.replace("״", '"').replace("׳", "'")


def _expand_abbreviation(token: str, repl: Dict[str, str]) -> Optional[str]:
    tok = _normalize_abbrev_key(token)
    if tok in repl: return repl[tok]
    if tok in _BUILTIN_ABBREVIATIONS: return _BUILTIN_ABBREVIATIONS[tok]
    if len(tok) >= 2 and tok[0] in ("ה", "ו", "ב", "ל", "כ", "מ"):
        prefix = tok[0]
        rest = tok[1:]
        rest = _normalize_abbrev_key(rest)
        if rest in repl: return prefix + repl[rest]
        if rest in _BUILTIN_ABBREVIATIONS: return prefix + _BUILTIN_ABBREVIATIONS[rest]
    return None


def _translate_unit_suffix(token: str) -> Optional[str]:
    m = _NUM_UNIT_RE.match(token)
    if not m: return None
    num_str = m.group(1)
    unit = m.group(2)
    
    # Identify unit name and gender
    target_unit = ""
    gender = "m" # Default

    if unit in ("°C", "°c"):
        target_unit = "מעלות"
        gender = "f"
    elif unit in ("°F", "°f"):
        target_unit = "מעלות פרנהייט"
        gender = "f"
    else:
        # Check map
        found = False
        if unit in _UNIT_MAP:
            target_unit, gender = _UNIT_MAP[unit]
            found = True
        else:
            unit_lower = unit.lower()
            if unit_lower in _UNIT_MAP:
                target_unit, gender = _UNIT_MAP[unit_lower]
                found = True
        
        if not found:
            return None

    # Expand number part
    # For units like KG (Masculine), "2.5" should be "SNEIEM va-hetzi".
    # For degrees (Feminine), "2.5" should be "SHTEIEM va-hetzi".
    # We pass 'mn' or 'fn' if we want construct state? No, "2.5 Kg" is absolute number + unit noun.
    # But "2 Kg" -> "Shnei Kilogram". This is construct.
    # "2.5 Kg" -> "Shnayim va-hetzi kilogram" (Absolute).
    # Heuristic: If integer, use construct? If float, use absolute?
    # Usually "Shnei Kilogram" (2 kg). "Shnayim va-hetzi kilogram" (2.5 kg).
    # So if it has a fraction, it behaves like absolute.
    # If integer, behaves like construct.
    
    is_integer = '.' not in num_str
    
    eff_gender = gender
    if is_integer:
         if gender == 'm': eff_gender = 'mn'
         if gender == 'f': eff_gender = 'fn'
    
    expanded_num = get_spoken_form(num_str, eff_gender)
    if not expanded_num:
        expanded_num = num_str
        
    return f"{expanded_num} {target_unit}"


def _expand_phone(token: str) -> Optional[str]:
    if _PHONE_RE.match(token):
        digits = []
        for ch in token:
            if ch.isdigit():
                d_spoken = get_spoken_form(ch, "f")
                if d_spoken:
                    digits.append(d_spoken)
        return " ".join(digits)
    return None


def _maybe_expand_number(token: str, gender: str = "f") -> Optional[str]:
    return get_spoken_form(token, gender)


def _expand_date(token: str) -> Optional[str]:
    # Check long regex first
    m = _DATE_LONG_RE.match(token)
    year_str = None
    if m:
        day = int(m.group(1))
        month = int(m.group(3))
        year_str = m.group(4)
    else:
        # Check short regex
        m = _DATE_SHORT_RE.match(token)
        if m:
            day = int(m.group(1))
            month = int(m.group(3))
        else:
            return None
    
    if day < 1 or day > 31 or month < 1 or month > 12:
        return None
        
    # Day
    if day == 1:
        day_str = "הראשון"
    else:
        # Date numbers are usually masculine "Ehad", "Shnayim" (absolute)? 
        # "Shisha be-mai". "Esrim ve-shiva be-mai".
        # User requested "Esrim ve-sheva" (F).
        # We will use 'f' as per feedback.
        day_str = get_spoken_form(str(day), "f")
    
    # Month
    month_str = _MONTH_ORDINAL_MAP.get(month)
    if not month_str:
        return None
        
    # Year
    year_spoken = ""
    if year_str:
        year_spoken = get_spoken_form(year_str, "f")
        
    parts = [day_str, month_str]
    if year_spoken:
        parts.append(year_spoken)
        
    return " ".join(parts)


def load_word_replacements(path: Path | None = None) -> Dict[str, str]:
    path = path or Path(__file__).resolve().parent / "ex_reps_all.tsv"
    return load_word_replacements_tsv(path)


# The helpers below take an optional per-character `owners` list (the index of the input word
# each character came from) and keep it aligned with the text. `owners=None` is the plain
# string path used by normalize_tts_text.

def _delete_matches(
    pattern: "re.Pattern[str]", text: str, owners: Optional[List[int]]
) -> Tuple[str, Optional[List[int]]]:
    if owners is None:
        return pattern.sub("", text), None
    kept: List[str] = []
    kept_owners: List[int] = []
    pos = 0
    for m in pattern.finditer(text):
        kept.append(text[pos:m.start()])
        kept_owners.extend(owners[pos:m.start()])
        pos = m.end()
    kept.append(text[pos:])
    kept_owners.extend(owners[pos:])
    return "".join(kept), kept_owners


def _collapse_whitespace(
    text: str, owners: Optional[List[int]]
) -> Tuple[str, Optional[List[int]]]:
    if owners is None:
        return re.sub(r"\s+", " ", text).strip(), None
    out: List[str] = []
    out_owners: List[int] = []
    pos = 0
    for m in re.finditer(r"\s+", text):
        out.append(text[pos:m.start()])
        out_owners.extend(owners[pos:m.start()])
        out.append(" ")
        out_owners.append(owners[m.start()])
        pos = m.end()
    out.append(text[pos:])
    out_owners.extend(owners[pos:])
    joined = "".join(out)
    lead = len(joined) - len(joined.lstrip())
    return joined.strip(), out_owners[lead:len(joined.rstrip())]


def _is_prefixed_number(m: "re.Match[str]") -> bool:
    """For a match of `(\\S)-(\\S)`: is the whole token a Hebrew prefix followed by a number?"""
    text = m.string
    start = text.rfind(" ", 0, m.start()) + 1
    end = text.find(" ", m.end())
    end = len(text) if end < 0 else end
    head = text[start:m.start() + 1].lstrip("".join(_DROP_PREFIX_MARKS))
    return is_preposition_prefix(head) and bool(_PREFIXED_NUMBER_TAIL_RE.match(text[m.start(2):end]))


def _preprocess(
    text: str, options: TTSNormalizeOptions, owners: Optional[List[int]] = None
) -> Tuple[str, Optional[List[int]]]:
    """Character-level cleanup that runs before tokenization."""
    proc = text
    if options.normalize_unicode:
        if owners is None:
            proc = _apply_unicode_cleanup(proc)
        else:
            chars: List[str] = []
            new_owners: List[int] = []
            for ch, owner in zip(proc, owners):
                rep = _CHAR_CONVERSION_DICT.get(ch, ch)
                chars.append(rep)
                new_owners.extend([owner] * len(rep))
            proc, owners = "".join(chars), new_owners
    if options.remove_emojis:
        proc, owners = _delete_matches(_EMOJI_RE, proc, owners)

    # Strip parentheses/brackets content if requested. These patterns can span words.
    if options.remove_parentheses:
        proc, owners = _delete_matches(re.compile(r"\(.*?\)"), proc, owners)
    if options.remove_brackets:
        proc, owners = _delete_matches(re.compile(r"\[.*?\]"), proc, owners)

    if options.split_dashes_between_words:
        # Only split if BOTH sides are NOT digits (avoid splitting 050-123 or 2026-01)
        # Regex: Lookbehind for non-digit, Lookahead for non-digit
        # Note: \D matches any non-digit character (including space, punctuation, letters)
        # We want to split "Word-Word" but not "0-1" or "0-Word"?
        # Actually usually "0-Word" should split.
        # Only "Digit-Digit" should stay.
        def repl(m):
            # Check if both sides are digits
            if m.group(1).isdigit() and m.group(2).isdigit():
                return m.group(0) # Keep hyphen
            # Keep the hyphen in a prefixed number (ב-15) so get_spoken_form can attach the prefix.
            if options.expand_numbers and m.group(2).isdigit() and _is_prefixed_number(m):
                return m.group(0)
            return f"{m.group(1)} {m.group(2)}" # Replace hyphen with space
        
        # Every replacement keeps the length of the match, so `owners` stays aligned.
        proc = re.sub(r"(\S)-(\S)", repl, proc)

    if options.collapse_whitespace:
        proc, owners = _collapse_whitespace(proc, owners)

    return proc, owners


def _normalize_raw_tokens(
    raw_tokens: List[str],
    options: TTSNormalizeOptions,
    repl: Dict[str, str],
) -> Tuple[List[str], List[int]]:
    """Run the token loop. Returns the output tokens and, for each, the index of the raw
    token it came from."""
    out_tokens: List[str] = []
    out_sources: List[int] = []

    def emit(token: str) -> None:
        out_tokens.append(token)
        out_sources.append(ind)

    punctuation_marks = set([".", ",", ":", ";", "!", "?", '"', "…", ")", "]", "}"])

    for ind, raw_tok in enumerate(raw_tokens):
        # 1. Strip outer marks (quotes, parens if enabled)
        # Note: If remove_parentheses=False, we still want to strip the CHARACTERS '(' and ')'
        # _strip_outer_marks uses _DROP_PREFIX_MARKS which includes '('.
        tok = _strip_outer_marks(raw_tok)
        if not tok: continue
        
        tok, suffix_punct = _split_suffix_punct(tok)
        tok = tok.strip()
        tok = _strip_outer_marks(tok)
        if not tok: continue

        tok_out = tok

        # Gender Detection
        gender = "f"
        prev_tok = out_tokens[-1] if out_tokens else ""
        if prev_tok == __HEBREW_MULTIPLY_WORD:
             gender = "m"
        elif prev_tok.endswith(__HEBREW_CENTURY_WORD):
             gender = "f0"
        
        # The next word only tells us the counted noun within the same sentence.
        if suffix_punct not in _SENTENCE_END_PUNCT and ind + 1 < len(raw_tokens):
            next_word = raw_tokens[ind + 1]
            while len(next_word) > 1 and next_word[-1] in punctuation_marks:
                next_word = next_word[:-1]
            next_word_no_the = next_word[len(__HEBREW_THE_PREFIX):] if next_word.startswith(__HEBREW_THE_PREFIX) else None
            
            if next_word in __HEBREW_KNOWN_MASCULINE:
                 gender = "mn"
            elif next_word.endswith(__HEBREW_MASCULINE_PLURAL_SUFFIX):
                 if (next_word in __HEBREW_EX_FEMININE_PLURALS) or (next_word_no_the and next_word_no_the in __HEBREW_EX_FEMININE_PLURALS):
                     gender = "fn"
                 else:
                     gender = "mn"
            elif next_word.endswith(__HEBREW_FEMININE_PLURAL_SUFFIX):
                 if (next_word in __HEBREW_EX_MASCULINE_PLURALS) or (next_word_no_the and next_word_no_the in __HEBREW_EX_MASCULINE_PLURALS):
                     gender = "mn"
                 else:
                     gender = "fn"
        
        # 1. Abbreviations
        if options.expand_abbreviations:
            expanded = _expand_abbreviation(tok_out, repl if options.apply_word_replacements else {})
            if expanded: tok_out = expanded
        elif options.apply_word_replacements and tok_out in repl:
            tok_out = repl[tok_out]

        # 2. Units (handles "2.5kg", "-5C")
        # NOTE: This consumes the number!
        if options.translate_units:
            translated = _translate_unit_suffix(tok_out)
            if translated:
                tok_out = translated
                # Skip number expansion for this token as it's already done
                if options.keep_punctuations and suffix_punct:
                    if options.attach_punctuations_to_token:
                        tok_out = f"{tok_out}{suffix_punct}"
                    else:
                        emit(tok_out)
                        emit(suffix_punct)
                        continue
                emit(tok_out)
                continue

        if options.expand_numbers:
            # 3. Dates
            date_expanded = _expand_date(tok_out)
            if date_expanded:
                tok_out = date_expanded
            else:
                # 4. Phone numbers
                phone_expanded = _expand_phone(tok_out)
                if phone_expanded:
                    tok_out = phone_expanded
                else:
                    # 5. Numbers
                    spoken = _maybe_expand_number(tok_out, gender)
                    if spoken:
                        tok_out = spoken

        # 6. Split markers
        if options.expand_numbers and options.split_markers:
            for marker in options.split_markers:
                if marker in tok_out:
                    parts = tok_out.split(marker)
                    spoken_parts: List[str] = []
                    ok = True
                    for p in parts:
                        p = p.strip()
                        if not p:
                             ok = False
                             break
                        s = _maybe_expand_number(p, "f")
                        if not s:
                             ok = False
                             break
                        spoken_parts.append(s)
                    if ok:
                        tok_out = " ".join(spoken_parts)
                    break

        if options.keep_punctuations and suffix_punct:
            if options.attach_punctuations_to_token:
                tok_out = f"{tok_out}{suffix_punct}"
            else:
                emit(tok_out)
                emit(suffix_punct)
                continue

        emit(tok_out)

    return out_tokens, out_sources


def _join_output(tokens: List[str], options: TTSNormalizeOptions) -> str:
    out = " ".join(tokens)
    if options.keep_punctuations:
        out = re.sub(r"\s+([.,?!])", r"\1", out)
    return out.strip()


def normalize_tts_text(
    text: str,
    *,
    options: TTSNormalizeOptions = TTSNormalizeOptions(),
    word_replacements: Optional[Dict[str, str]] = None,
) -> str:
    proc, _ = _preprocess(text, options)
    if not proc:
        return ""

    repl = word_replacements or {}

    out_tokens, _ = _normalize_raw_tokens(proc.split(" "), options, repl)
    return _join_output(out_tokens, options)


def normalize_tts_words(
    words: Sequence[str],
    *,
    options: TTSNormalizeOptions = TTSNormalizeOptions(),
    word_replacements: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Normalize a sentence given as separate words, keeping each word's own result apart.

    Number gender, `פי`/`מאה` handling, bracket removal and punctuation spacing all depend
    on the neighbouring tokens, so words normalized one at a time come out different from
    the same words normalized together. This runs the same pipeline as normalize_tts_text
    over `" ".join(words)` and reports which input word each output token came from.

    Returns one string per input word: "" when the word was dropped, several
    space-separated tokens when it expanded (`1995`). Joining the non-empty results with a
    space and applying the `\\s+([.,?!])` -> `\\1` rule across the boundaries (a result that
    starts with punctuation belongs to the end of the previous one) reproduces
    normalize_tts_text(" ".join(words)). A word is credited with the raw tokens that begin
    in it; if brackets removed a word boundary, the merged token goes to the first word.
    """
    words = list(words)
    if not words:
        return []
    owners: List[int] = []
    for index, word in enumerate(words):
        owners.extend([index] * (len(word) + 1))
    del owners[-1]

    proc, owners = _preprocess(" ".join(words), options, owners)
    results: List[List[str]] = [[] for _ in words]
    if proc:
        raw_tokens = proc.split(" ")
        token_owners: List[int] = []
        offset = 0
        for tok in raw_tokens:
            token_owners.append(owners[min(offset, len(owners) - 1)])
            offset += len(tok) + 1
        out_tokens, out_sources = _normalize_raw_tokens(raw_tokens, options, word_replacements or {})
        for token, source in zip(out_tokens, out_sources):
            results[token_owners[source]].append(token)
    return [_join_output(tokens, options) for tokens in results]
