"""The only dependency on this repository's existing normalizer.

Copy or replace this adapter when extracting numeric_pairs to another repo.
"""

import importlib.util
from pathlib import Path

# Import the single legacy file without executing normalizer/__init__.py: that package
# currently imports its sibling modules by top-level name and is not package-importable.
_source = Path(__file__).resolve().parent.parent / "normalizer" / "hebrew_spoken_form.py"
_spec = importlib.util.spec_from_file_location("numeric_pairs_legacy_spoken", _source)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load spoken-form adapter from {_source}")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
get_spoken_form = _module.get_spoken_form


def cardinal(value: int, gender: str, *, construct: bool = False) -> str:
    if value < 0 or gender not in {"m", "f"}:
        raise ValueError("Cardinal requires a nonnegative value and m/f gender")
    form = get_spoken_form(str(value), gender + "n" if construct else gender)
    if not form or any(ch.isdigit() for ch in form):
        raise ValueError(f"No cardinal reading for {value} ({gender})")
    return form


def ordinal_feminine(value: int) -> str:
    if not 1 <= value <= 10:
        raise ValueError("Supported feminine ordinals are 1..10")
    form = get_spoken_form(str(value), "f0")
    if not form:
        raise ValueError(f"No ordinal reading for {value}")
    return form


def ordinal_masculine(value: int) -> str:
    if not 1 <= value <= 10:
        raise ValueError("Supported masculine ordinals are 1..10")
    form = get_spoken_form(str(value), "m0")
    if not form:
        raise ValueError(f"No masculine ordinal reading for {value}")
    return form


def clock_time(hour: int, minute: int) -> str:
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Clock time must be between 00:00 and 23:59")
    spoken_hour = cardinal(hour % 12 or 12, "f")
    if minute == 0:
        return spoken_hour
    if minute == 15:
        return spoken_hour + " ורבע"
    if minute == 30:
        return spoken_hour + " וחצי"
    if minute == 45:
        return "רבע ל" + cardinal((hour + 1) % 12 or 12, "f")
    if minute == 1:
        return spoken_hour + " ודקה"
    if minute < 20:
        return spoken_hour + " ו" + cardinal(minute, "f", construct=True) + " דקות"
    return spoken_hour + " " + cardinal(minute, "f")
