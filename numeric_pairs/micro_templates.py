"""Declarative spoken micro-template compiler and deterministic renderer.

Templates are produced offline by an LLM (Gemini 4 Neon), validated strictly,
and rendered exclusively through `numeric_pairs`'s deterministic Hebrew spoken
form policies (`adapter.py` and `core.py`) so alignments and spoken numbers
never drift or rely on free-form LLM text generation.
"""

from __future__ import annotations

from hashlib import sha256
import json
import random
import re
from typing import Any

from .adapter import cardinal, clock_time
from .catalog import BY_ID, CATALOG_VERSION
from .core import (
    HEBREW_DUAL_NOUNS,
    RENDERER_VERSION,
    Fragment,
    clock,
    domain_fragment,
    number,
    ordinal,
    percentage,
    phone_number,
    quantity,
    sample as sample_archetype,
    text,
    validate_pair,
)

MICRO_TEMPLATE_SCHEMA = "micro-template-v1"

FORBIDDEN_DISCLAIMER_SUBSTRINGS = (
    "דמה",
    "פיקטיבי",
    "סימולציית",
    "לצורך הדגמה",
    "מספר בדיקה",
)

ALLOWED_APPROX = (
    "",
    "איזה ",
    "בערך ",
    "משהו כמו ",
    "כמעט ",
    "לפחות ",
    "יותר מ-",
    "עד ",
    "כ-",
)

ALLOWED_PREFIXES = ("", "ב", "ל", "מ", "כ", "ה", "ו", "וב", "ול", "ומ", "מה")


def _check_no_forbidden_words(s: str, field_name: str) -> None:
    for bad in FORBIDDEN_DISCLAIMER_SUBSTRINGS:
        if bad in s:
            raise ValueError(f"{field_name} contains forbidden artificial disclaimer word {bad!r}")


def _check_no_ascii_digits(s: str, field_name: str) -> None:
    if any(ch.isascii() and ch.isdigit() for ch in s):
        raise ValueError(f"{field_name} must not contain raw ASCII digits ({s!r}); use a numeric node instead")


def _colloquial_daypart_fragment(slot: str, hour24: int, prefix: str = "") -> Fragment:
    if not 0 <= hour24 <= 23:
        raise ValueError(f"colloquial_daypart_hour slot {slot!r} must be 0..23, got {hour24}")
    if prefix not in ("", "ב", "מ", "עד ", "לפני ", "אחרי "):
        raise ValueError(f"Unsupported colloquial_daypart_hour prefix: {prefix!r}")
    if hour24 == 0:
        written_core = "12 בלילה"
        spoken_core = "שתים עשרה בלילה"
    elif 1 <= hour24 <= 4:
        written_core = f"{hour24} בלילה"
        spoken_core = f"{cardinal(hour24, 'f')} בלילה"
    elif 5 <= hour24 <= 11:
        written_core = f"{hour24} בבוקר"
        spoken_core = f"{cardinal(hour24, 'f')} בבוקר"
    elif hour24 == 12:
        written_core = "12 בצהריים"
        spoken_core = "שתים עשרה בצהריים"
    elif 13 <= hour24 <= 15:
        h12 = hour24 - 12
        written_core = f"{h12} בצהריים"
        spoken_core = f"{cardinal(h12, 'f')} בצהריים"
    elif 16 <= hour24 <= 17:
        h12 = hour24 - 12
        written_core = f"{h12} אחרי הצהריים"
        spoken_core = f"{cardinal(h12, 'f')} אחרי הצהריים"
    elif 18 <= hour24 <= 20:
        h12 = hour24 - 12
        written_core = f"{h12} בערב"
        spoken_core = f"{cardinal(h12, 'f')} בערב"
    else:
        h12 = hour24 - 12
        written_core = f"{h12} בלילה"
        spoken_core = f"{cardinal(h12, 'f')} בלילה"

    val_num = hour24 if hour24 <= 12 and hour24 != 0 else (12 if hour24 == 0 else hour24 - 12)
    if prefix in ("ב", "מ"):
        written = f"{prefix}-{written_core}"
        spoken = f"{prefix}{spoken_core}"
    else:
        written = f"{prefix}{written_core}"
        spoken = f"{prefix}{spoken_core}"
    return Fragment(written, spoken, slot, "clock_time", val_num, "colloquial-12h-daypart")


def _counted_noun_fragment(
    slot: str,
    value: int,
    noun: dict[str, str],
    *,
    approx: str = "",
    comma_thousands: bool = False,
) -> Fragment:
    if value < 2:
        raise ValueError(f"counted_noun slot {slot!r} requires integer >= 2 (got {value})")
    if approx not in ALLOWED_APPROX:
        raise ValueError(f"Unsupported approx={approx!r}; allowed: {ALLOWED_APPROX}")
    plural = noun["plural"]
    singular = noun.get("singular", "")
    gender = noun["gender"]
    if gender not in ("m", "f"):
        raise ValueError(f"Noun gender must be 'm' or 'f', got {gender!r}")

    num_str = f"{value:,}" if comma_thousands and value >= 1000 else str(value)
    dual_spoken = (HEBREW_DUAL_NOUNS.get(plural) or HEBREW_DUAL_NOUNS.get(singular)) if value == 2 else None
    if dual_spoken:
        spoken_core = dual_spoken
        reading = "spoken-dual-noun"
    else:
        # Use construct state for 2..10 and thousands, natural spoken form for compound > 20 when appropriate
        use_construct = value <= 10 or (value >= 1000 and value % 1000 == 0)
        spoken_num = "שני" if (value == 2 and gender == "m") else (
            "שתי" if (value == 2 and gender == "f") else cardinal(value, gender, construct=use_construct)
        )
        spoken_core = f"{spoken_num} {plural}"
        reading = "spoken-counted-noun"

    if approx == "כ-":
        written = f"כ-{num_str} {plural}"
        spoken = f"כ{spoken_core}"
        kind = "approximate_quantity"
    elif approx == "יותר מ-":
        written = f"יותר מ-{num_str} {plural}"
        spoken = f"יותר מ{spoken_core}"
        kind = "approximate_quantity"
    elif approx:
        written = f"{approx}{num_str} {plural}"
        spoken = f"{approx}{spoken_core}"
        kind = "approximate_quantity"
    else:
        written = f"{num_str} {plural}"
        spoken = spoken_core
        kind = "quantity"

    return Fragment(written, spoken, slot, kind, num_str if "," in num_str else value, reading)


def _cardinal_fragment(
    slot: str,
    value: int,
    *,
    gender: str = "f",
    prefix: str = "",
    comma_thousands: bool = False,
) -> Fragment:
    if gender not in ("m", "f"):
        raise ValueError(f"cardinal_number gender must be 'm' or 'f', got {gender!r}")
    if prefix not in ALLOWED_PREFIXES:
        raise ValueError(f"Unsupported prefix {prefix!r}; allowed: {ALLOWED_PREFIXES}")
    num_str = f"{value:,}" if comma_thousands and value >= 1000 else str(value)
    spoken_core = cardinal(value, gender)
    if prefix:
        written = f"{prefix}-{num_str}"
        spoken = f"{prefix}{spoken_core}"
    else:
        written = num_str
        spoken = spoken_core
    return Fragment(written, spoken, slot, "cardinal", num_str if "," in num_str else value, "spoken-cardinal")


def _percentage_fragment(slot: str, value: int, *, prefix: str = "") -> Fragment:
    if not 1 <= value <= 100:
        raise ValueError(f"percentage value must be 1..100, got {value}")
    if prefix not in ALLOWED_PREFIXES:
        raise ValueError(f"Unsupported percentage prefix {prefix!r}")
    spoken_core = "אחוז אחד" if value == 1 else (
        "מאה אחוז" if value == 100 else cardinal(value, "m", construct=True) + " אחוזים"
    )
    written_core = f"{value}%"
    if prefix:
        return Fragment(f"{prefix}-{written_core}", f"{prefix}{spoken_core}", slot, "percentage", value, "colloquial-percent")
    return Fragment(written_core, spoken_core, slot, "percentage", value, "colloquial-percent")


def _decimal_fragment(
    slot: str,
    value_str: str,
    *,
    prefix: str = "",
    half_style: str = "point",
    noun_gender: str = "f",
) -> Fragment:
    if prefix not in ALLOWED_PREFIXES:
        raise ValueError(f"Unsupported decimal prefix {prefix!r}")
    if half_style not in ("point", "natural"):
        raise ValueError(f"Unsupported decimal half_style {half_style!r}; expected 'point' or 'natural'")
    if noun_gender not in ("m", "f"):
        raise ValueError(f"Unsupported decimal noun_gender {noun_gender!r}")
    if not re.fullmatch(r"\d+\.\d+", value_str):
        raise ValueError(f"decimal_number value must match digits.digits, got {value_str!r}")
    whole_s, frac_s = value_str.split(".")
    whole_i = int(whole_s)

    if half_style == "natural" and frac_s == "5":
        spoken_core = "חצי" if whole_i == 0 else f"{cardinal(whole_i, noun_gender)} וחצי"
        reading = "spoken-decimal-half"
    else:
        # With "נקודה", Hebrew numerals are unconditionally abstract feminine ("ארבע נקודה שש", never *"ארבעה נקודה שש").
        whole_spoken = cardinal(whole_i, "f")
        if len(frac_s) == 1:
            frac_spoken = cardinal(int(frac_s), "f")
        else:
            frac_spoken = " ".join(cardinal(int(d), "f") for d in frac_s)
        spoken_core = f"{whole_spoken} נקודה {frac_spoken}"
        reading = "spoken-decimal"

    if prefix:
        return Fragment(f"{prefix}-{value_str}", f"{prefix}{spoken_core}", slot, "decimal", value_str, reading)
    return Fragment(value_str, spoken_core, slot, "decimal", value_str, reading)


def _adjacent_approx_fragment(
    slot: str,
    base_val: int,
    *,
    step: int = 1,
    gender: str = "f",
    lead: str = "באזור ה-",
    separator: str = ", ",
) -> Fragment:
    if base_val < 2 or step < 1:
        raise ValueError("adjacent_approx requires base_val >= 2 and step >= 1")
    if lead not in ("", "באזור ה-", "סביב ה-", "בין "):
        raise ValueError(f"Unsupported adjacent_approx lead: {lead!r}")
    second_val = base_val + step
    s1 = cardinal(base_val, gender)
    s2 = cardinal(second_val, gender)
    if lead == "בין ":
        written = f"בין {base_val} ל-{second_val}"
        spoken = f"בין {s1} ל{s2}"
    elif lead.endswith("ה-"):
        stem = lead[:-2]
        written = f"{lead}{base_val}{separator}{second_val}"
        spoken = f"{stem}ה{s1}, {s2}"
    else:
        written = f"{base_val}–{second_val}"
        spoken = f"{s1} {s2}"
    return Fragment(written, spoken, slot, "range", str(base_val), "adjacent-spoken-approx")


def _year_span_fragment(slot_start: str, start_year: int, end_year: int) -> Fragment:
    if not (1700 <= start_year < end_year <= 2050):
        raise ValueError(f"Invalid year_span {start_year}..{end_year}")
    written = f"מ-{start_year} עד {end_year}"
    spoken = f"מ{cardinal(start_year, 'f')} עד {cardinal(end_year, 'f')}"
    return Fragment(written, spoken, slot_start, "date", f"{start_year}", "spoken-year-span")


def _domain_node_fragment(kind: str, sampled_arch: dict[str, Any], prefix: str = "") -> Fragment:
    if kind == "address":
        street, house = sampled_arch["street"], sampled_arch["house"]
        return Fragment(f"{street} {house}", f"{street} {cardinal(house, 'f')}", "house", "cardinal", house, "street-house")
    if kind == "delivery":
        street, house = sampled_arch["street"], sampled_arch["house"]
        if sampled_arch.get("include_apartment"):
            apt = sampled_arch["apartment"]
            return Fragment(
                f"{street} {house}, דירה {apt}",
                f"{street} {cardinal(house, 'f')}, דירה {cardinal(apt, 'f')}",
                "house",
                "address",
                house,
                "delivery-street-house-apt",
            )
        return Fragment(f"{street} {house}", f"{street} {cardinal(house, 'f')}", "house", "cardinal", house, "street-house")
    if kind == "floor":
        return ordinal(sampled_arch["floor"])
    if kind == "departure":
        frag = clock(sampled_arch["minute_of_day"])
        if prefix == "ב":
            return Fragment("ב-" + frag.digits, "ב" + frag.cardinal, frag.slot, frag.kind, frag.value, frag.reading)
        return frag
    if kind == "survey":
        return percentage(sampled_arch["percent"])
    if kind == "mobile":
        return phone_number(sampled_arch["phone"])
    if kind in {"purchase", "bulk_purchase", "approximate"}:
        return quantity(sampled_arch["quantity"], sampled_arch["noun"], approximate=(kind == "approximate"))
    if kind == "road_route":
        road, route = sampled_arch["road"], sampled_arch["route"]
        r_gen = "m" if road == 1 else "f"
        rt_gen = "m" if route == 1 else "f"
        return Fragment(
            f"כביש {road} לקו {route}",
            f"כביש {cardinal(road, r_gen)} לקו {cardinal(route, rt_gen)}",
            "road",
            "cardinal",
            road,
            "road-and-route",
        )
    return domain_fragment(kind, sampled_arch, "natural")


def sample_micro_slots(
    spec: dict[str, Any],
    rng: random.Random,
    *,
    mode: str = "random",
    variant_idx: int = 0,
) -> dict[str, Any]:
    """Sample slot values deterministically, supporting boundary stress modes."""
    slots: dict[str, dict[str, Any]] = spec.get("slots", {})
    values: dict[str, Any] = {}

    # Pass 1: independent slots
    for name, sdef in slots.items():
        kind = sdef.get("kind")
        if kind == "derived_int":
            continue
        if kind == "micro_bank":
            bank = sdef["values"]
            if mode == "stress":
                values[name] = bank[variant_idx % len(bank)]
            else:
                values[name] = rng.choice(bank)
        elif kind == "int_range":
            low = int(sdef["lower"])
            high = int(sdef["upper"])
            step = int(sdef.get("step", 1))
            if step < 1 or low > high:
                raise ValueError(f"Invalid int_range in slot {name!r}: {low}..{high} step {step}")
            grid = list(range(low, high + 1, step))
            if not grid:
                grid = [low]
            if mode == "stress":
                # Probe min, max, 2/10/11/20 boundaries when inside grid, and middle points
                specials = [g for g in grid if g in (2, 3, 10, 11, 12, 20, 21, 100, 1000)]
                picks = [grid[0], grid[-1], *specials, grid[len(grid) // 2]]
                if variant_idx < len(picks):
                    values[name] = picks[variant_idx]
                else:
                    values[name] = rng.choice(grid)
            else:
                values[name] = rng.choice(grid)
        elif kind == "decimal_range":
            low_f = float(sdef["lower"])
            high_f = float(sdef["upper"])
            decimals = int(sdef.get("decimals", 1))
            if decimals < 1 or decimals > 3 or low_f >= high_f:
                raise ValueError(f"Invalid decimal_range in slot {name!r}")
            scale = 10 ** decimals
            lo_i = round(low_f * scale)
            hi_i = round(high_f * scale)
            candidates = [i for i in range(lo_i, hi_i + 1) if i % 10 != 0]
            if not candidates:
                candidates = [lo_i]
            chosen = candidates[variant_idx % len(candidates)] if mode == "stress" else rng.choice(candidates)
            values[name] = f"{chosen / scale:.{decimals}f}"
        elif kind == "archetype_sampler":
            arch_id = sdef["archetype_id"]
            if arch_id not in BY_ID:
                raise ValueError(f"Unknown archetype_id {arch_id!r} in slot {name!r}")
            values[name] = sample_archetype(arch_id, rng)
        else:
            raise ValueError(f"Unsupported slot kind {kind!r} in slot {name!r}")

    # Pass 2: derived_int slots (supports chained dependencies up to depth 4)
    pending = [name for name, sdef in slots.items() if sdef.get("kind") == "derived_int"]
    for _ in range(4):
        if not pending:
            break
        next_pending = []
        for name in pending:
            sdef = slots[name]
            base_slot = sdef["base_slot"]
            if base_slot not in values:
                next_pending.append(name)
                continue
            base_val = int(values[base_slot])
            mult = float(sdef.get("multiplier", 1))
            off_min = int(sdef.get("offset_min", 1))
            off_max = int(sdef.get("offset_max", off_min))
            step = int(sdef.get("step", 1))
            if off_min > off_max or step < 1:
                raise ValueError(f"Invalid derived_int offsets in slot {name!r}")
            offsets = list(range(off_min, off_max + 1, step)) or [off_min]
            offset = offsets[variant_idx % len(offsets)] if mode == "stress" else rng.choice(offsets)
            computed = int(round(base_val * mult)) + offset
            if "min_value" in sdef:
                computed = max(int(sdef["min_value"]), computed)
            if "max_value" in sdef:
                computed = min(int(sdef["max_value"]), computed)
            values[name] = computed
        pending = next_pending
    if pending:
        raise ValueError(f"Unresolved or circular derived_int base_slot in: {pending}")

    return values


def render_micro_template(
    spec: dict[str, Any],
    values: dict[str, Any],
    *,
    seed: int = 0,
    index: int = 0,
) -> dict[str, Any]:
    """Render a validated MicroTemplate spec + sampled slot values into a numeric_pairs dict."""
    template_id = spec["id"]
    archetype_id = spec["archetype_id"]
    if archetype_id not in BY_ID:
        raise ValueError(f"Unknown archetype_id {archetype_id!r} on template {template_id!r}")

    pieces: list[Fragment] = []
    for node in spec["nodes"]:
        if "lit" in node:
            lit_val = str(node["lit"])
            _check_no_ascii_digits(lit_val, f"template {template_id} lit")
            _check_no_forbidden_words(lit_val, f"template {template_id} lit")
            pieces.append(text(lit_val))
        elif "slot" in node and "num" not in node:
            slot_name = node["slot"]
            slot_val = str(values[slot_name])
            _check_no_ascii_digits(slot_val, f"template {template_id} slot {slot_name}")
            _check_no_forbidden_words(slot_val, f"template {template_id} slot {slot_name}")
            pieces.append(text(slot_val))
        elif "num" in node:
            renderer = node["num"]
            if renderer == "counted_noun":
                slot_name = node["slot"]
                pieces.append(
                    _counted_noun_fragment(
                        slot_name,
                        int(values[slot_name]),
                        node["noun"],
                        approx=node.get("approx", ""),
                        comma_thousands=bool(node.get("comma_thousands", False)),
                    )
                )
            elif renderer == "cardinal_number":
                slot_name = node["slot"]
                pieces.append(
                    _cardinal_fragment(
                        slot_name,
                        int(values[slot_name]),
                        gender=node.get("gender", "f"),
                        prefix=node.get("prefix", ""),
                        comma_thousands=bool(node.get("comma_thousands", False)),
                    )
                )
            elif renderer == "colloquial_daypart_hour":
                slot_name = node["slot"]
                pieces.append(
                    _colloquial_daypart_fragment(
                        slot_name,
                        int(values[slot_name]),
                        prefix=node.get("prefix", ""),
                    )
                )
            elif renderer == "clock_24h":
                slot_name = node["slot"]
                frag = clock(int(values[slot_name]))
                pfx = node.get("prefix", "")
                if pfx:
                    frag = Fragment(f"{pfx}-{frag.digits}", f"{pfx}{frag.cardinal}", frag.slot, frag.kind, frag.value, frag.reading)
                pieces.append(frag)
            elif renderer == "percentage":
                slot_name = node["slot"]
                pieces.append(_percentage_fragment(slot_name, int(values[slot_name]), prefix=node.get("prefix", "")))
            elif renderer == "decimal_number":
                slot_name = node["slot"]
                pieces.append(
                    _decimal_fragment(
                        slot_name,
                        str(values[slot_name]),
                        prefix=node.get("prefix", ""),
                        half_style=node.get("half_style", "point"),
                        noun_gender=node.get("noun_gender", "f"),
                    )
                )
            elif renderer == "adjacent_approx":
                slot_name = node["slot"]
                pieces.append(
                    _adjacent_approx_fragment(
                        slot_name,
                        int(values[slot_name]),
                        step=int(node.get("step", 1)),
                        gender=node.get("gender", "f"),
                        lead=node.get("lead", "באזור ה-"),
                        separator=node.get("separator", ", "),
                    )
                )
            elif renderer == "year_span":
                s_slot = node["start_slot"]
                e_slot = node["end_slot"]
                pieces.append(_year_span_fragment(s_slot, int(values[s_slot]), int(values[e_slot])))
            elif renderer == "domain":
                kind = node["kind"]
                s_slot = node["slot"]
                sampled_arch = values[s_slot]
                if not isinstance(sampled_arch, dict):
                    raise ValueError(f"domain renderer requires slot {s_slot!r} to be an archetype_sampler dict")
                pieces.append(_domain_node_fragment(kind, sampled_arch, prefix=node.get("prefix", "")))
            else:
                raise ValueError(f"Unknown numeric renderer {renderer!r} in template {template_id!r}")
        else:
            raise ValueError(f"Malformed node {node!r} in template {template_id!r}")

    digits_out, spoken_out, alignments = "", "", []
    for piece in pieces:
        if piece.slot:
            alignments.append(
                {
                    "slot": piece.slot,
                    "kind": piece.kind,
                    "value": piece.value,
                    "reading": piece.reading,
                    "digits_span": [len(digits_out), len(digits_out) + len(piece.digits)],
                    "cardinal_span": [len(spoken_out), len(spoken_out) + len(piece.cardinal)],
                    "digits_text": piece.digits,
                    "cardinal_text": piece.cardinal,
                }
            )
        digits_out += piece.digits
        spoken_out += piece.cardinal

    _check_no_forbidden_words(digits_out, f"template {template_id} output")
    _check_no_forbidden_words(spoken_out, f"template {template_id} spoken output")
    if digits_out != digits_out.strip() or "  " in digits_out:
        raise ValueError(
            f"Template {template_id!r} produced leading/trailing or double whitespace ({digits_out!r}); "
            "when using an optional '' in a micro_bank opener, include the trailing space inside the non-empty options only"
        )

    identity = {
        "archetype_id": archetype_id,
        "micro_template_id": template_id,
        "seed": seed,
        "index": index,
        "sampled": values,
        "catalog_version": CATALOG_VERSION,
        "renderer_version": RENDERER_VERSION,
        "pipeline_schema": MICRO_TEMPLATE_SCHEMA,
    }
    sample_id = sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
    pair = {
        "id": sample_id,
        **identity,
        "digits": digits_out,
        "cardinal": spoken_out,
        "alignments": alignments,
    }
    validate_pair(pair)
    return pair


def template_covered_usages(spec: dict[str, Any]) -> list[str]:
    """Return all valid numeric usage IDs (from catalog BY_ID) represented by a template."""
    seen: list[str] = []

    def _add(aid: Any) -> None:
        if isinstance(aid, str) and aid in BY_ID and aid not in seen:
            seen.append(aid)

    _add(spec.get("archetype_id"))
    for extra in spec.get("covered_usages") or []:
        _add(extra)
    for node in spec.get("nodes") or []:
        if isinstance(node, dict) and node.get("num") == "domain":
            _add(node.get("kind"))
    return seen


def validate_and_stress_template(spec: dict[str, Any], *, stress_count: int = 8, seed: int = 42) -> list[dict[str, Any]]:
    """Validate a MicroTemplate spec and compile `stress_count` boundary/varied realizations."""
    if not isinstance(spec, dict):
        raise ValueError("Template must be a JSON object")
    template_id = str(spec.get("id", "")).strip()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{3,80}", template_id):
        raise ValueError(f"Template id {template_id!r} must be 3..80 ASCII slug chars")
    archetype_id = spec.get("archetype_id", "")
    if archetype_id not in BY_ID:
        raise ValueError(f"Template {template_id!r}: archetype_id {archetype_id!r} must be one of {sorted(BY_ID)}")
    covered_usages = spec.get("covered_usages")
    if covered_usages is not None:
        if not isinstance(covered_usages, list) or not all(isinstance(u, str) and u in BY_ID for u in covered_usages):
            raise ValueError(f"Template {template_id!r}: covered_usages must be a list of valid catalog IDs")
    nodes = spec.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError(f"Template {template_id!r} must have a non-empty 'nodes' list")
    if not any(isinstance(n, dict) and "num" in n for n in nodes):
        raise ValueError(f"Template {template_id!r} must include at least one numeric node ('num')")

    slots = spec.get("slots", {})
    if not isinstance(slots, dict) or not slots:
        raise ValueError(f"Template {template_id!r} must define a non-empty 'slots' object")
    for s_name, s_def in slots.items():
        if not isinstance(s_def, dict):
            raise ValueError(f"Slot {s_name!r} must be an object")
        if s_def.get("kind") == "micro_bank":
            vals = s_def.get("values")
            if (
                not isinstance(vals, list)
                or not (2 <= len(vals) <= 10)
                or not all(isinstance(v, str) for v in vals)
                or any(v != "" and not v.strip() for v in vals)
                or sum(1 for v in vals if v == "") > 1
                or not any(v.strip() for v in vals)
            ):
                raise ValueError(
                    f"Slot {s_name!r} micro_bank must have 2..10 strings (at most one optional empty string '')"
                )
            for v in vals:
                _check_no_ascii_digits(v, f"slot {s_name} micro_bank")
                _check_no_forbidden_words(v, f"slot {s_name} micro_bank")

    samples: list[dict[str, Any]] = []
    seen_digits: set[str] = set()
    for i in range(stress_count):
        rng = random.Random(f"stress:{seed}:{template_id}:{i}")
        mode = "stress" if i < 6 else "random"
        vals = sample_micro_slots(spec, rng, mode=mode, variant_idx=i)
        pair = render_micro_template(spec, vals, seed=seed, index=i)
        seen_digits.add(pair["digits"])
        samples.append(pair)
    if len(seen_digits) < min(3, stress_count):
        raise ValueError(
            f"Template {template_id!r} has insufficient variation ({len(seen_digits)} unique outputs across {stress_count} draws)"
        )
    return samples


def generate_from_templates(
    templates: list[dict[str, Any]],
    count: int,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Deterministically sample `count` deduplicated, validated pairs across approved templates."""
    if not templates:
        raise ValueError("Cannot generate pairs: zero approved templates")
    if count < 1 or count > 100_000:
        raise ValueError("count must be between 1 and 100,000")

    results: list[dict[str, Any]] = []
    seen_digits: set[str] = set()
    ordered = list(templates)

    for index in range(count):
        cycle = index // len(ordered)
        cycle_list = ordered.copy()
        random.Random(f"pipe-cycle:{seed}:{cycle}").shuffle(cycle_list)
        spec = cycle_list[index % len(ordered)]
        chosen_pair: dict[str, Any] | None = None
        for attempt in range(48):
            rng = random.Random(f"pipe-row:{seed}:{index}:{attempt}:{spec['id']}")
            vals = sample_micro_slots(spec, rng, mode="random")
            candidate = render_micro_template(spec, vals, seed=seed, index=index)
            chosen_pair = candidate
            if candidate["digits"] not in seen_digits:
                break
        assert chosen_pair is not None
        seen_digits.add(chosen_pair["digits"])
        results.append(chosen_pair)
    return results
