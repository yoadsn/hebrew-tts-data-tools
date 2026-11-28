"""Pipeline state store, OpenChamber Neon dispatcher, and live cost ledger."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import re
from threading import Lock, Thread
import time
from typing import Any, Callable

from .catalog import ARCHETYPES, BY_ID
from .core import sample as sample_archetype
from .corpus_miner import cookie_file, load_ivrit_cookie, mine_spoken_contexts, save_ivrit_cookie
from .corpus_sources import (
    delete_corpus_source,
    load_corpus_sources,
    save_corpus_source,
    search_configured_source,
    sources_file,
)
from .micro_templates import (
    _domain_node_fragment,
    generate_from_templates,
    template_covered_usages,
    validate_and_stress_template,
)
from .openchamber_client import OpenChamberClient, OpenChamberError
from .review import ReviewStore
from .template_library import library_summary, promote_specs_to_library

_pipeline_lock = Lock()

# Tier-1 archetypes that require synthetic-safe identifier/address/flight generators (`archetype_sampler` + `domain`).
TRACK_B_ARCHETYPES: frozenset[str] = frozenset(
    {
        "address",
        "delivery",
        "slash_address",
        "mobile",
        "landline",
        "local_landline",
        "national_line",
        "israeli_international",
        "business_line",
        "card_suffix",
        "card_full",
        "postal",
        "international_phone",
        "civil_id",
        "passport_id",
        "bank_account",
        "license_plate",
        "flight_number",
        "airline_flight",
    }
)

STEP_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("dispatch", "01 · פתיחת סשן Gemini 4 Neon ב-OpenChamber"),
    ("mine", "02 · דגימת הקשרי דיבור מ-explore.ivrit.ai"),
    ("lift", "03 · חילוץ תבניות מיקרו מדוברות (Lifter)"),
    ("compile_stress", "04 · קומפילציה דטרמיניסטית ו-8 דגימות קצה לתבנית"),
    ("critic", "05 · שער בקרת טבעיות מחמיר (8/8 חובה לעבור)"),
    ("finalize", "06 · הפקת המשפטים ושמירה לסקירה וייצוא"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Tired 1-word discourse starters that quickly make a batch feel repetitive when reused.
_OVERUSED_SHORT_STARTERS: frozenset[str] = frozenset(
    {
        "שמע",
        "שמעי",
        "תקשיב",
        "תקשיבי",
        "בסוף",
        "בקיצור",
        "אגב",
        "תכלס",
        "היי",
        "תשמע",
        "תשמעי",
    }
)

# Canned stationery/catalog nouns from Tier-1 domain samplers that betray rigid Tier-1 wrappers
# instead of genuine spoken topics from mined podcasts/protocols.
_CANNED_TIER1_NOUNS: tuple[str, ...] = (
    "קלסרים",
    "חוברות",
    "עפרונות",
    "צנצנות",
    "מדפים",
)

# Numeric usages where Neon should use flexible renderers (`counted_noun`, `decimal_number`,
# `cardinal_number`, `percentage`, etc.) with real-world nouns from mined speech rather than
# Tier-1's canned `domain` sampler (which locks in narrow stationery/textbook wording).
_FLEXIBLE_USAGE_IDS: frozenset[str] = frozenset(
    {
        "approximate",
        "purchase",
        "bulk_purchase",
        "maximum_attendees",
        "weight",
        "distance",
        "area",
        "money",
        "large_shekels",
        "age",
        "minimum_age",
        "year",
        "duration_half",
        "survey",
        "decimal_temp",
        "multi_digit_decimal",
        "plural_millions",
        "million_exact",
    }
)

# Phenomenon-level descriptions (the *numeric usage* represented, NOT a rigid sentence archetype).
_USAGE_PHENOMENON_HINTS: dict[str, str] = {
    "approximate": "prefixed approximate count `כ-N` via `counted_noun` (`approx: 'כ-'`) with ANY real-world noun from the snippet",
    "purchase": "everyday small counted quantity (2–15) of ANY real noun via `counted_noun`",
    "bulk_purchase": "large counted quantity (20–500+) of ANY real-world noun from context via `counted_noun`",
    "maximum_attendees": "upper-bound/cap number (`עד N` / `מקסימום N`) in any natural topic (rooms, budgets, groups, seats)",
    "weight": "weight in kg/g (`קילו` / `ק\"ג`) in everyday speech (fitness, travel, shipping, food)",
    "distance": "distance in km/meters in everyday movement, commuting, travel, or geography",
    "area": "area in square meters (`מ\"ר`) in housing, urban planning, venues, or offices",
    "money": "shekel amounts in everyday prices, bills, fines, or salaries",
    "large_shekels": "six-digit shekel sums (100,000–999,999 ₪) in real housing, car, salary, or budget talk",
    "age": "a person's or thing's age in natural conversation",
    "minimum_age": "minimum age threshold (`מעל גיל N` / `מגיל N`) in real rules, stories, or policy",
    "year": "calendar year (`ב-1998`, `מ-2015 עד 2023`, etc.) in history, career, or life anecdotes",
    "duration_half": "half-hour/half-unit duration (`2.5 שעות`, `שעה וחצי`) via `decimal_number` (`half_style: 'natural'`) or `domain`",
    "survey": "integer percentages (`35%`, `ל-60%`) in discussions, polls, shares, or discounts",
    "decimal_temp": "one-decimal reading (`נקודה`, e.g. temperatures, rates, scores, ratings)",
    "multi_digit_decimal": "multi-digit decimals (`0.08`, `1.375`) read digit-by-digit after `נקודה`",
    "plural_millions": "multi-million counts (2–9M, e.g. `2,500,000` -> `שני מיליון וחמש מאות אלף`) in budgets, populations, or tech",
    "million_exact": "exact million-plus integers (`1,234,567`) in statistics, budgets, or users",
    "opening_hours": "opening/operating hour span (`8:00–12:00`) embedded in a real errand, frustration, or schedule remark",
    "meeting_minute": "non-round 24h clock time (`ב-16:52`) inside a natural scheduling/story sentence",
    "midnight_time": "minutes around midnight (`ב-00:15`, `ב-00:30`) in a real late-night story or logistics remark",
    "departure": "24h clock time (`07:45`) in travel, transit, or daily routine talk",
    "fraction": "simple fractions (`1/2`, `3/4`) in cooking, splits, arguments, or shares",
    "general_fraction": "partitive fractions (`1/3`, `2/3`, `2/5`, `3/8`) in real debate, splits, or comparisons",
    "percent_half": "half-percent values (`4.5%`, `18.5%`) in economy, interest rates, or metrics",
    "negative_temp": "sub-zero/negative numbers (`-6`) in weather, travel, freezers, or ratings",
    "dollar_price": "USD amounts (`$N`) in tech, SaaS, travel, or markets",
    "euro_price": "EUR amounts (`N €`) in European travel, imports, or prices",
    "money_cents": "shekels + agorot (`12.50 ₪`, `7.90 ₪`) in everyday shopping or bills",
    "stopwatch_seconds": "decimal seconds (`9.58 שניות`) in sports, latency, or timing",
    "stopwatch_minute": "minute:second.hundredths (`1:46.30`) in races, laps, or benchmarks",
    "explicit_hundredths": "explicit seconds + hundredths (`12 שניות ו-40 מאיות`) in sports or precision timing",
    "map_scale": "ratio/scale (`1:50,000`, `1:100,000`) in hiking, planning, or models",
    "pill_range": "small numeric range (`2-4`) in dosage, frequency, or everyday limits",
    "age_range": "age bracket (`גילאי 18-25`) in demographics, programs, or anecdotes",
    "child_half_age": "child half-age (`2.5`–`6.5` -> `שנתיים וחצי`) in family or education talk",
    "infant_age": "toddler age `1.5` (`שנה וחצי`) woven into natural family/daycare conversation",
    "decade": "decades (`בשנות ה-80`, `בשנות ה-90`) in culture, history, or nostalgia",
    "calendar": "named-month date (`ב-14 במאי`) in stories, news, or plans",
    "month_end_date": "month-end dates (`29`–`31`) in deadlines, bills, or history",
    "numeric_calendar": "numeric day.month (`ב-23.8`) in casual scheduling or reminders",
    "full_date": "full dotted date (`ל-28.10.2024`) in deadlines, contracts, or events",
    "slash_date": "full slash date (`ל-14/5/1948`) in history, documents, or deadlines",
    "section": "hierarchical legal/policy section (`סעיף 11.1`) in Knesset/contract/regulation talk",
    "version": "semantic version (`5.9.9`) in software, tech, or updates",
    "data_plan": "GB + Mb data/bandwidth units (`50GB במהירות 100Mb`) in telecom or tech talk",
    "road_route": "Israeli highway/bus line (`כביש 6`, `קו 21`) in traffic or commute talk",
    "score": "match score (`2:1`) in sports banter or game recaps",
    "ranking": "ordinal ranking (`ה-3`, `ה-10`) in competitions, lists, or ratings",
    "floor": "feminine floor ordinal (`קומה ה-4`) in real-estate, office, or errands",
}


def _opening_diversity_warnings(templates: list[dict[str, Any]]) -> list[str]:
    """Detect repetitive 1-word cliché openers, canned Tier-1 nouns, or single-number textbook homogeneity."""
    if not templates:
        return []
    starter_to_tids: dict[str, list[str]] = {}
    tids_with_short_starter: set[str] = set()
    tids_with_canned_nouns: list[str] = []
    single_num_tids: list[str] = []

    for tpl in templates:
        tid = str(tpl.get("id") or "")
        samples = tpl.get("stress_samples") or []
        spec = tpl.get("spec") or {}
        num_nodes = [n for n in (spec.get("nodes") or []) if isinstance(n, dict) and "num" in n]
        if len(num_nodes) == 1:
            single_num_tids.append(tid)

        seen_for_tpl: set[str] = set()
        has_canned = False
        for s in samples:
            digits = str(s.get("digits") or "").lstrip()
            if not digits:
                continue
            first_token = re.split(r"[\s,!?.:–—-]+", digits, maxsplit=1)[0]
            if first_token in _OVERUSED_SHORT_STARTERS and first_token not in seen_for_tpl:
                seen_for_tpl.add(first_token)
                starter_to_tids.setdefault(first_token, []).append(tid)
                tids_with_short_starter.add(tid)
            if any(noun in digits for noun in _CANNED_TIER1_NOUNS):
                has_canned = True
        if has_canned:
            tids_with_canned_nouns.append(tid)

    warnings: list[str] = []
    for starter, tids in sorted(starter_to_tids.items()):
        if len(tids) > 1:
            warnings.append(
                f"Overused 1-word starter '{starter},' appears in {len(tids)} templates ({', '.join(tids)}). "
                "Drop the starter on direct-start templates or vary with longer multi-word openers."
            )
    if len(templates) >= 4 and len(tids_with_short_starter) / len(templates) > 0.45:
        warnings.append(
            f"{len(tids_with_short_starter)}/{len(templates)} templates start with a 1-word cliché starter "
            f"({', '.join(sorted(tids_with_short_starter))}). Aim for at least 40–50% direct openings with NO starter "
            "and use richer multi-word openers where context fits."
        )
    if tids_with_canned_nouns:
        warnings.append(
            f"Canned Tier-1 stationery/catalog nouns ({', '.join(_CANNED_TIER1_NOUNS)}) appeared in "
            f"{', '.join(tids_with_canned_nouns)}. Replace `domain` with `counted_noun` using real-world nouns from the mined spoken snippets."
        )
    if len(templates) >= 6 and len(single_num_tids) / len(templates) > 0.65:
        warnings.append(
            f"{len(single_num_tids)}/{len(templates)} templates have only a single numeric expression. "
            "Where natural for the spoken scene, freely mix 2–3 compatible numeric usages in one utterance and list them in `covered_usages`."
        )
    return warnings


def build_neon_prompt(
    *,
    batch_id: str,
    server_url: str,
    target_count: int,
    candidate_templates_target: int,
    min_approved_templates: int,
    corpus_ratio: float,
    user_notes: str,
    temp_dir: str,
    target_archetypes: list[dict[str, Any]] | None = None,
    tier1_coverage: dict[str, Any] | None = None,
    corpus_sources: list[dict[str, Any]] | None = None,
    reuse_snippets_from: list[str] | None = None,
) -> str:
    track_a_count = max(0, round(candidate_templates_target * corpus_ratio))
    track_b_count = max(0, candidate_templates_target - track_a_count)
    if user_notes.strip():
        focus_block = f"\n### User Focus / Explicit Guidance for This Batch\n{user_notes.strip()}\n"
    elif target_archetypes:
        cov_line = ""
        if tier1_coverage:
            cov_line = (
                f" ({tier1_coverage['covered_count']}/{tier1_coverage['total_archetypes']} "
                f"numeric usages currently covered; {tier1_coverage['uncovered_count']} still underrepresented)"
            )
        lines = [
            f"\n### Numeric Usage Palette (Underrepresented Usages to Weave Into Natural Speech{cov_line})",
            "**CRITICAL — READ CAREFULLY:** Your goal is to cover the **numeric reading usages/phenomena** below, "
            "**NOT** rigid textbook archetype sentences! **NEVER** write 1-to-1 textbook wrapper sentences around an archetype title. "
            "Instead, **start from the real spoken snippets returned by `mine`** (their actual conversational rhythm, questions, "
            "anecdotes, explanations, pushback, and topics) and **freely weave and combine 2–3 compatible numeric usages into a single "
            "natural spoken utterance** whenever it sounds authentic. List ALL numeric usage IDs present in a template under "
            "`\"covered_usages\": [...]` — one rich multi-number sentence credits every usage it naturally includes!",
        ]
        for item in target_archetypes:
            aid = item["id"]
            hint = _USAGE_PHENOMENON_HINTS.get(aid) or item.get("description") or ""
            if item.get("track") == "synthetic_identifier":
                ex = f" | `domain` preview: `{item['example_digits']}` -> `{item['example_cardinal']}`" if item.get("example_digits") else ""
                lines.append(f"- **`{aid}`** (synthetic identifier usage): {hint}{ex}")
            elif aid in _FLEXIBLE_USAGE_IDS:
                lines.append(f"- **`{aid}`** (flexible spoken usage — use `counted_noun`/`cardinal_number`/`decimal_number`/`percentage` with real nouns from your snippet, NOT `domain`): {hint}")
            else:
                ex = f" | syntax preview: `{item['example_digits']}` -> `{item['example_cardinal']}`" if item.get("example_digits") else ""
                lines.append(f"- **`{aid}`** (structured numeric usage): {hint}{ex}")
        lines.append(
            "Note on `domain`: Only use `{\"num\": \"domain\", ...}` for synthetic identifiers (phones, IDs, cards, passports, plates, "
            "bank accounts, addresses, flights) or specialized syntax (`opening_hours`, `stopwatch_*`, `map_scale`, `version`, `section`, "
            "`data_plan`, `score`, `fraction`, `general_fraction`, `percent_half`, `money_cents`, `negative_temp`, `road_route`, dates/clocks) — "
            "and check the syntax preview so you never duplicate built-in prepositions (`ב-`, `ל-`, `בשנות`, `סעיף`, `כביש`). "
            "NEVER use `domain` for `approximate`, `purchase`, `bulk_purchase`, or `weight` where it injects canned Tier-1 stationery/catalog nouns "
            "(`קלסרים`, `חוברות`, `עפרונות`, `מדפים`); always use `counted_noun` with real nouns from the spoken scene! "
            "For `infant_age` (fixed `1.5`), pair it with another numeric slot or a varied `micro_bank`."
        )
        focus_block = "\n".join(lines) + "\n"
    else:
        focus_block = ""

    reuse_note = ""
    if reuse_snippets_from:
        reuse_note = (
            " (`mine` is drawing directly from rich spoken snippets ALREADY sampled in previous batches "
            "whose conversational turns were barely tapped — mine them deeply and feel free to extract multiple "
            "distinct spoken angles/templates from different parts of a rich snippet!)"
        )

    extra_sources_block = ""
    if corpus_sources:
        src_lines = [
            "\n#### Optional Targeted Search on Configured Text-File Corpus Sources",
            "In addition to `mine`, these configured `text_file` sources are available for on-demand regex/literal searches whenever you want more real spoken inspiration for a specific topic or numeric pattern:",
        ]
        for src in corpus_sources:
            desc = f" — {src['description']}" if src.get("description") else ""
            src_lines.append(f"- **`{src['id']}`** ({src['name']} · `{src['type']}` via `{src['location']}`){desc}")
        src_lines.append(
            f"Run a regex search (supports `\\d`, `\\s`, etc.) or literal search (`--mode fixed`) with:\n"
            f"```sh\n"
            f"uv run python -m numeric_pairs.pipeline_cli search-source --server-url {server_url} --batch-id {batch_id} --source {corpus_sources[0]['id']} --query '<regex>' --mode regex --limit 15 --context 1\n"
            f"```\n"
            f"(You may also pass `--start-line <N>` to sample further into large files, or `--ignore-case`.)"
        )
        extra_sources_block = "\n".join(src_lines) + "\n"

    return f"""You are running an automated Hebrew TTS Spoken Micro-Template Pipeline batch (`{batch_id}`).
Do NOT explore or grep the repository — everything you need is in this prompt and the `pipeline_cli` tool.
Run commands via your `shell` tool from the current repository root.

### Batch Parameters
- Batch ID: `{batch_id}`
- Server URL: `{server_url}`
- Target final sentences: `{target_count}`
- Candidate MicroTemplates to design: `{candidate_templates_target}` (~{track_a_count} Track A corpus-inspired spoken vignettes + ~{track_b_count} Track B natural voice-note/phone-call vignettes embedding realistic synthetic phones, IDs, passports, cards, plates, addresses, or flights — freely mixing multiple numeric usages inside natural utterances!)
- Minimum 8/8-approved templates required before finalize: `{min_approved_templates}`
- Temp directory for JSON payloads: `{temp_dir}`{focus_block}

### Step-by-Step Execution Protocol (run in exact order)

#### STEP 1 — Load / Mine Spoken Contexts (YOUR PRIMARY INSPIRATION!)
Run:
```sh
uv run python -m numeric_pairs.pipeline_cli mine --server-url {server_url} --batch-id {batch_id}
```
Read the mined spoken snippets printed to stdout{reuse_note}. Notice Whisper ASR quirks (e.g. `בין 60` instead of `בן 60`, `600 ו-7` instead of `607`) — fix them, anonymize real people/politics/show names, and NEVER copy transcripts verbatim.
**CORPUS-FIRST RULE:** Let the mined snippets drive the **voice, syntax, conversational turn, and topic** of your templates! You can extract 2–3 completely different natural spoken templates from different parts/angles of a rich snippet, and combine any numeric usages from the palette that fit naturally in that spoken situation.{extra_sources_block}

#### STEP 2 — Design & Submit Candidate `MicroTemplate` JSON Specs
Write a JSON array of `{candidate_templates_target}` `MicroTemplate` objects to `{temp_dir}/templates_{batch_id}.json` and submit:
```sh
uv run python -m numeric_pairs.pipeline_cli submit-templates --server-url {server_url} --batch-id {batch_id} --file {temp_dir}/templates_{batch_id}.json
```
The Python server immediately compiles every template deterministically through `numeric_pairs` (`adapter.py` + `core.py`) and generates 8 stress realizations per template. If any template fails compilation, fix and submit a small supplement file so at least `{candidate_templates_target}` templates compile cleanly.

##### `MicroTemplate` JSON Schema & Rules
1. Never put raw ASCII digits (`0-9`) inside `"lit"` or `"micro_bank"` strings — ALL numbers must use `"num"` nodes so written/spoken spans align 100%.
2. Never use artificial disclaimer words (`דמה`, `פיקטיבי`, `סימולציית`, `לצורך הדגמה`, `מספר בדיקה`). Frame synthetic identifiers in completely normal everyday spoken Hebrew.
3. Keep ~80% of each sentence's natural spoken glue fixed! Use `"micro_bank"` with 3–5 morphology-locked phrases (matching exact gender, number, person, and tense of the surrounding sentence).
4. **Anti-Textbook & Natural Spoken Variety (CRITICAL!):**
   - **NEVER write dry Tier-1 textbook wrapper frames** like `[Generic factual clause with 1 canned number], ו/אבל [bland moral/filler ending].`
     - ❌ BAD (wooden textbook wrappers — DO NOT WRITE LIKE THIS):
       - `"במשלוח של הבוקר הועברו מהספק כ-10 חוברות, והכול כבר מוכן לפריקה."`
       - `"ההרשמה למפגש הקרוב מוגבלת לעד 93 משתתפים, כדי שנוכל לתת יחס אישי לכל אחד."`
       - `"המזכירות של המרפאה פתוחה מחר בין 8:00–12:00, אבל עדיף להגיע מוקדם לפני התור."`
       - `"הבת הקטנה שלנו בת 3.5, וכבר מדברת שוטף בלי להתבלבל."`
     - ✅ GOOD (corpus-inspired natural spoken Israeli Hebrew — varied syntax, real voice, freely combining numeric types):
       - Question / exasperated reaction: `"רגע, מי בכלל מספיק להגיע לביטוח לאומי בין 8:00–12:00 כשאתה עובד עד 6 בערב ויש שם תור של איזה 40 איש?"`
       - Knesset / policy pushback mixing section + millions + percent + year: `"בסעיף 14.2 של החוק מדברים על תקציב של 3.5 מיליון שקל, אבל בפועל יותר מ-60% מזה תקוע כבר מ-2021."`
       - Podcast anecdote with self-correction / contrast: `"כשהגענו לשם חשבתי שזה עניין של חצי שעה, אבל רק התור בכניסה לקח 45 דקות ושילמנו כמעט 180 ₪ על כלום."`
       - Natural voice note mixing identifier + time/context: `"אם לא תופסים אותי בנייד ב-054-718-3290 אחרי 5 בערב, תנסי במשרד לפני שסוגרים ב-17:45."`
   - **Vary sentence forms across the batch:** mix questions (`?`), mid-conversation reactions, debates/explanations, personal stories, comparisons, and quick voice notes — NOT all declarative `..., ו...` sentences!
   - **Mix multiple numeric usages naturally:** most templates should contain **2–3 natural numeric nodes** when it fits the spoken scene (and declare all represented usage IDs in `"covered_usages": [...]` + optional `"source_snippet_id": "..."` linking to the inspiring snippet).
5. **Sentence Opening & Starter Diversity:**
   - **Omit discourse-starter prefixes on at least 40–50% of templates** — start directly with the subject, time/place framing, verb, question, or main clause (e.g. `"בשבוע שעבר סגרנו..."`, `"אחרי הישיבה התברר ש..."`, `"הוועדה אישרה תקציב של..."`, `"מי בכלל משלם היום..."`).
   - **Avoid overusing tired 1-word cliché starters** (`שמע,`, `שמעי,`, `תקשיב,`, `בסוף,`, `בקיצור,`, `אגב,`, `תכלס,`, `היי,`) — use any given one **at most ONCE** across the entire batch, and never stack starters (`בקיצור, בסוף...`).
   - **When a conversational opener fits the context, prefer longer multi-word / varied openers** and invent fresh context-appropriate ones of your own! Examples (match register & gender to the scene):
     - `אם אני זוכר נכון,` / `תחשוב על זה,` / `תראו,` / `אחי,` / `אחותי,` / `אתה קולט?` / `אתה לא מאמין,` / `שים לב,`
     - plus your own natural multi-word openings (e.g. `מה שמעניין פה זה ש`, `בדיוק בדקתי את זה,`, `עוד נקודה חשובה,`, `האמת שהופתעתי,`, `תגיד לי רגע,`).
   - **Optional opener trick:** a `"micro_bank"` allows at most one `""` (empty string) entry so a single template can naturally mix direct no-starter openings with multi-word openers — put the trailing space inside the non-empty options only, e.g. `{{"kind": "micro_bank", "values": ["", "אם אני זוכר נכון, ", "שים לב, "]}}` followed directly by `{{"lit": "הפרויקט הזה עלה "}}` (no leading space in the next `"lit"`!).
6. Set `"archetype_id"` to the primary valid catalog usage ID and `"covered_usages"` to the list of ALL catalog usage IDs naturally represented in the template (e.g. `["section", "plural_millions", "survey", "year"]`).

##### Supported `slots` definitions:
- `{{"kind": "micro_bank", "values": ["הוא יוצא משם", "אחי יצא משם", "הבחור יצא משם"]}}` (2..10 digit-free strings with identical grammatical person/gender/number; at most one optional `""` allowed for optional openers/modifiers)
- `{{"kind": "int_range", "lower": 11, "upper": 15, "step": 1}}` (for `counted_noun`, ALWAYS set `lower >= 2`!)
- `{{"kind": "derived_int", "base_slot": "n1", "multiplier": 1, "offset_min": 500, "offset_max": 2500, "step": 500}}` (guarantees relational math like `n2 > n1` or `hours = exit_hour + offset`!)
- `{{"kind": "decimal_range", "lower": 0.6, "upper": 1.9, "decimals": 1}}`
- `{{"kind": "archetype_sampler", "archetype_id": "mobile"}}` (samples synthetic-safe values for `"domain"` renderer!)

##### Supported `nodes` items:
- `{{"lit": " יום אחר כך "}}`
- `{{"slot": "person_clause"}}`
- `{{"num": "colloquial_daypart_hour", "slot": "exit_hour", "prefix": "ב"}}` (`slot` int `0..23`, `prefix` in `""`, `"ב"`, `"מ"`, `"עד "`)
- `{{"num": "counted_noun", "slot": "hours_stayed", "approx": "איזה ", "comma_thousands": false, "noun": {{"singular": "שעה", "plural": "שעות", "gender": "f"}}}}` (`approx` in `""`, `"איזה "`, `"בערך "`, `"משהו כמו "`, `"כמעט "`, `"לפחות "`, `"יותר מ-"`, `"עד "`, `"כ-"`)
- `{{"num": "cardinal_number", "slot": "yr", "gender": "f", "prefix": "ב", "comma_thousands": false}}` (`prefix` in `""`, `"ב"`, `"ל"`, `"מ"`, `"כ"`, `"ה"`)
- `{{"num": "percentage", "slot": "pct", "prefix": "ל"}}` (`slot` int `1..100`)
- `{{"num": "decimal_number", "slot": "rate", "prefix": "ל", "half_style": "point"}}` (`slot` from `decimal_range`; `נקודה` readings are automatically feminine in the engine. Optional `"half_style": "natural", "noun_gender": "m"|"f"` reads `.5` as `וחצי` for everyday measurements like `4.5 קילומטר` -> `ארבעה וחצי קילומטר` while keeping `.1`..`.9` as feminine `נקודה`!)
- `{{"num": "adjacent_approx", "slot": "age_base", "step": 1, "gender": "f", "lead": "באזור ה-"}}` (renders e.g. `באזור ה-35, 36` -> `באזור השלושים וחמש, שלושים ושש`)
- `{{"num": "year_span", "start_slot": "y1", "end_slot": "y2"}}` (renders `מ-1919 עד 1933`)
- `{{"num": "domain", "kind": "mobile", "slot": "mob_data"}}` (`slot` MUST be an `"archetype_sampler"` with matching `archetype_id`!)

##### Complete Example `MicroTemplate` (mixing multiple natural usages):
```json
{{
  "id": "spoken_exit_hours_01",
  "archetype_id": "duration_half",
  "covered_usages": ["duration_half", "departure"],
  "source_snippet_id": "ex_01",
  "track": "corpus_inspired",
  "inspiration_summary": "יציאה בצהריים אחרי שהייה ממושכת ללא שינה או אוכל",
  "slots": {{
    "subject_open": {{"kind": "micro_bank", "values": ["הוא יוצא משם", "אחי יצא משם", "הבחור יצא משם"]}},
    "exit_hour": {{"kind": "int_range", "lower": 12, "upper": 15}},
    "hours_stayed": {{"kind": "derived_int", "base_slot": "exit_hour", "offset_min": 14, "offset_max": 20}},
    "deprivation": {{"kind": "micro_bank", "values": ["לא אכל כלום", "לא ישן דקה", "היה בלי קליטה בכלל"]}}
  }},
  "nodes": [
    {{"slot": "subject_open"}},
    {{"lit": " יום אחר כך "}},
    {{"num": "colloquial_daypart_hour", "slot": "exit_hour", "prefix": "ב"}},
    {{"lit": ", כלומר הוא היה שם "}},
    {{"num": "counted_noun", "slot": "hours_stayed", "approx": "איזה ", "noun": {{"singular": "שעה", "plural": "שעות", "gender": "f"}}}},
    {{"lit": " שבהן הוא "}},
    {{"slot": "deprivation"}},
    {{"lit": "."}}
  ]
}}
```

#### STEP 3 — Fetch the 8-Sample Stress Pack
Run:
```sh
uv run python -m numeric_pairs.pipeline_cli get-stress-pack --server-url {server_url} --batch-id {batch_id}
```

#### STEP 4 — Strict 8/8 Native Hebrew TTS Critic Gate (Repair Textbook/Stiff Specs & Flag Engine Bugs!)
Inspect ALL 8 `(digits, cardinal)` realizations for every compiled template. Classify each template into one of 4 `verdict_kind` outcomes — NEVER approve a dry textbook Tier-1 wrapper sentence, NEVER silently throw away a good spoken sentence if only its slot/node wiring needs a quick fix, and NEVER bury an engine bug:

1. **`"approved"`** (`passed_count == 8`, `approved: true`): All 8 realizations sound like genuine spoken Israeli Hebrew (not a dry textbook frame) with full morphological agreement and coherent logic.
2. **`"spec_repairable"`** (`approved: false`): Either a node/slot setting was wrong (wrong noun gender, range too wide, canned Tier-1 nouns), OR `opening_diversity_warnings` flagged repetitive starters / single-number homogeneity, OR the sentence reads like a dry textbook Tier-1 wrapper instead of authentic speech. **Before submitting verdicts, repair/rewrite those templates in-place (`submit-templates` with the same `id` overwrites and re-compiles them!) and run `get-stress-pack` again so they are rescued and approved!**
3. **`"engine_bug"`** (`approved: false`): The `digits` sentence is natural AND your node spec is completely valid, YET our Python engine converted `digits -> cardinal` into ungrammatical Hebrew words. Report `"verdict_kind": "engine_bug"` with the exact offending `digits -> cardinal` example in `reason` so the UI raises a developer **Engine Bug** alert instead of silently hiding it!
4. **`"template_defect"`** (`approved: false`): The Hebrew sentence frame or `micro_bank` concatenation itself is awkward, contradictory, or unnatural.

Write verdicts JSON array to `{temp_dir}/verdicts_{batch_id}.json`:
```json
[
  {{"template_id": "spoken_exit_hours_01", "passed_count": 8, "verdict_kind": "approved", "approved": true, "reason": "8/8 טבעי, זרימה מדוברת מעולה והתאמת מין וזמן מלאה."}}
]
```
Submit verdicts:
```sh
uv run python -m numeric_pairs.pipeline_cli submit-verdicts --server-url {server_url} --batch-id {batch_id} --file {temp_dir}/verdicts_{batch_id}.json
```
If fewer than `{min_approved_templates}` templates passed 8/8 (or fewer than 3 distinct category families survived), submit repaired/replacement templates (`submit-templates`), run `get-stress-pack`, and `submit-verdicts` for them before Step 5.

#### STEP 5 — Finalize the Batch
Run:
```sh
uv run python -m numeric_pairs.pipeline_cli finalize --server-url {server_url} --batch-id {batch_id}
```
Once `finalize` prints `"status": "succeeded"`, reply with a short 3-line Hebrew summary of the batch and stop.
"""


class PipelineStore:
    """Manages pipeline batch state on disk (lazy directories) and coordinates OpenChamber telemetry."""

    def __init__(
        self,
        review_store_getter: Callable[[], ReviewStore],
        oc_client: OpenChamberClient | None = None,
        repo_dir: Path | None = None,
    ):
        self._get_review_store = review_store_getter
        self.oc_client = oc_client or OpenChamberClient()
        self.repo_dir = Path(repo_dir or Path(__file__).resolve().parents[1])
        self._last_sync_ts: dict[str, float] = {}
        self._notifying_batches: set[str] = set()
        self._monitored_batches: set[str] = set()
        self._monitor_interval_s: float = 10.0
        self._monitor_max_wait_s: float = 3600.0

    @property
    def data_root(self) -> Path:
        return self._get_review_store().root

    @property
    def batches_dir(self) -> Path:
        return self.data_root / "pipeline" / "batches"

    def _batch_path(self, batch_id: str) -> Path | None:
        if not batch_id or len(batch_id) > 40 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in batch_id):
            return None
        return self.batches_dir / f"{batch_id}.json"

    def _write_batch(self, batch: dict[str, Any]) -> dict[str, Any]:
        batch["updated_at"] = _now_iso()
        folder = self.batches_dir
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{batch['id']}.json"
        tmp = folder / f"{batch['id']}.tmp"
        tmp.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return batch

    def _read_batch_unlocked(self, batch_id: str) -> dict[str, Any] | None:
        path = self._batch_path(batch_id)
        if path is None or not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _set_step(self, batch: dict[str, Any], step_id: str, status: str, detail: str = "") -> None:
        now = _now_iso()
        for step in batch["steps"]:
            if step["id"] == step_id:
                step["status"] = status
                if detail:
                    step["detail"] = detail
                if status == "running" and not step["started_at"]:
                    step["started_at"] = now
                if status in ("done", "failed"):
                    step["started_at"] = step["started_at"] or now
                    step["completed_at"] = now
                break

    def _log_event(self, batch: dict[str, Any], step_id: str, message: str) -> None:
        batch.setdefault("events", []).append(
            {"time": _now_iso(), "step": step_id, "message": message}
        )
        if len(batch["events"]) > 80:
            batch["events"] = batch["events"][-80:]

    def environment_status(self) -> dict[str, Any]:
        oc_info = self.oc_client.connection_info()
        c_path = cookie_file(self.data_root)
        cookie_val = load_ivrit_cookie(self.data_root)
        sources = load_corpus_sources(self.data_root)
        rs = self._get_review_store()
        return {
            "openchamber": {
                "configured": oc_info["configured"],
                "base_url": oc_info["base_url"],
                "has_password": oc_info["has_password"],
            },
            "ivrit_cookie": {
                "configured": bool(cookie_val),
                "length": len(cookie_val),
                "path": str(c_path),
            },
            "corpus_sources": {
                "count": len(sources),
                "enabled_count": sum(1 for s in sources if s.get("enabled", True)),
                "path": str(sources_file(self.data_root)),
                "sources": sources,
            },
            "reusable_snippets": self.reusable_snippet_pool_summary(),
            "library": library_summary(
                self.data_root,
                official_path=rs.official_library_path,
                include_official=rs.include_official_library,
                include_templates=False,
            ),
            "ledger": self.cost_summary(),
            "tier1_coverage": self.tier1_coverage(),
        }

    def reusable_snippet_pool_summary(self) -> dict[str, Any]:
        """Summarize unique real spoken snippets already mined in previous batches (lazy on read)."""
        folder = self.batches_dir
        if not folder.is_dir():
            return {"total_unique_snippets": 0, "batches": []}
        seen_windows: set[str] = set()
        batch_items: list[dict[str, Any]] = []
        paths = sorted(folder.glob("b_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            snips = data.get("mined_snippets") or []
            real_snips = [s for s in snips if s.get("source") != "spoken-exemplar" and s.get("context_window")]
            if not real_snips:
                continue
            new_unique = 0
            for s in real_snips:
                w = s["context_window"]
                if w not in seen_windows:
                    seen_windows.add(w)
                    new_unique += 1
            batch_items.append(
                {
                    "id": data["id"],
                    "created_at": data.get("created_at", ""),
                    "snippet_count": len(real_snips),
                    "new_unique_count": new_unique,
                    "mine_mode": data.get("mine_mode"),
                }
            )
        return {
            "total_unique_snippets": len(seen_windows),
            "batches": batch_items[:20],
        }

    def _collect_reused_snippets(
        self,
        source_batch_ids: list[str],
        *,
        exclude_batch_id: str,
        target_snippets: int,
        seed: int,
    ) -> dict[str, Any]:
        """Draw a deduplicated, shuffled pool of already-mined spoken snippets from previous batches."""
        folder = self.batches_dir
        if not folder.is_dir():
            return {"mode": "reused_from_batches", "warning": "אין אצוות קודמות לשימוש חוזר.", "snippets": []}

        use_all = any(bid in ("all", "all_existing", "*") for bid in source_batch_ids)
        if use_all:
            candidate_paths = sorted(folder.glob("b_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        else:
            candidate_paths = []
            for bid in source_batch_ids:
                p = self._batch_path(bid)
                if p is not None and p.is_file():
                    candidate_paths.append(p)

        pool: list[dict[str, Any]] = []
        seen_windows: set[str] = set()
        used_batches: list[str] = []
        for path in candidate_paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            bid = data.get("id")
            if not bid or bid == exclude_batch_id:
                continue
            added_from_this = 0
            for s in data.get("mined_snippets") or []:
                window = s.get("context_window") or ""
                if not window or window in seen_windows:
                    continue
                if s.get("source") == "spoken-exemplar":
                    continue
                seen_windows.add(window)
                cloned = dict(s)
                cloned["reused_from_batch"] = bid
                # Drop stale target_archetype tags from older batches so Neon treats the snippet freshly.
                cloned.pop("target_archetype", None)
                pool.append(cloned)
                added_from_this += 1
            if added_from_this > 0:
                used_batches.append(bid)

        rng = random.Random(f"reuse-snips:{seed}:{len(pool)}")
        rng.shuffle(pool)
        chosen = pool[: max(target_snippets, min(40, len(pool)))]
        return {
            "mode": "reused_from_batches",
            "warning": "" if chosen else "לא נמצאו השראות קיימות באצוות שנבחרו.",
            "source_batches": used_batches,
            "snippets": chosen,
        }

    def list_corpus_sources(self, *, enabled_only: bool = False) -> list[dict[str, Any]]:
        return load_corpus_sources(self.data_root, enabled_only=enabled_only)

    def save_corpus_source(self, raw_spec: dict[str, Any]) -> dict[str, Any]:
        return save_corpus_source(self.data_root, raw_spec)

    def delete_corpus_source(self, source_id: str) -> bool:
        return delete_corpus_source(self.data_root, source_id)

    def search_corpus_source(
        self,
        source_id: str,
        *,
        query: str,
        mode: str = "regex",
        limit: int = 20,
        context_lines: int = 0,
        ignore_case: bool = False,
        start_line: int = 1,
        batch_id: str | None = None,
    ) -> dict[str, Any]:
        result = search_configured_source(
            self.data_root,
            source_id,
            query=query,
            mode=mode,
            limit=limit,
            context_lines=context_lines,
            ignore_case=ignore_case,
            start_line=start_line,
        )
        if batch_id:
            with _pipeline_lock:
                batch = self._read_batch_unlocked(batch_id)
                if batch is not None:
                    existing_ids = {s.get("id") for s in batch.get("mined_snippets") or []}
                    added = 0
                    for m in (result.get("matches") or [])[:12]:
                        sid = f"src_{source_id}_{m['line_number']}"
                        if sid in existing_ids:
                            continue
                        existing_ids.add(sid)
                        batch.setdefault("mined_snippets", []).append(
                            {
                                "id": sid,
                                "bucket": f"search:{query[:40]}",
                                "source": result["source_name"],
                                "source_id": source_id,
                                "source_type": result["type"],
                                "episode_title": f"שורה {m['line_number']} ({result['location']})",
                                "line_number": m["line_number"],
                                "hit_text": m.get("text", ""),
                                "context_window": m.get("context_window") or m.get("text", ""),
                            }
                        )
                        added += 1
                    self._log_event(
                        batch,
                        "mine",
                        f"חיפוש יזום במקור '{result['source_name']}' ({source_id}) עבור `{query}`: {result['match_count']} התאמות ({added} נוספו להקשרים).",
                    )
                    self._write_batch(batch)
        return result

    def tier1_coverage(self) -> dict[str, Any]:
        """Compute which Tier-1 numeric usages are already covered by approved in-the-wild templates."""
        counts: dict[str, int] = {}
        folder = self.batches_dir
        if folder.is_dir():
            for path in folder.glob("b_*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                for tpl in data.get("templates") or []:
                    if (tpl.get("verdict") or {}).get("approved"):
                        usages: set[str] = set()
                        aid = tpl.get("archetype_id")
                        if aid in BY_ID:
                            usages.add(aid)
                        for u in tpl.get("covered_usages") or []:
                            if u in BY_ID:
                                usages.add(u)
                        if isinstance(tpl.get("spec"), dict):
                            usages.update(template_covered_usages(tpl["spec"]))
                        for u in usages:
                            counts[u] = counts.get(u, 0) + 1
        covered_ids = sorted(counts)
        uncovered_ids = [a.id for a in ARCHETYPES if a.id not in counts]
        return {
            "total_archetypes": len(ARCHETYPES),
            "covered_count": len(covered_ids),
            "uncovered_count": len(uncovered_ids),
            "covered_ids": covered_ids,
            "uncovered_ids": uncovered_ids,
            "counts_by_archetype": counts,
        }

    def select_default_target_archetypes(
        self,
        *,
        candidate_target: int,
        corpus_ratio: float,
        seed: int,
    ) -> list[dict[str, Any]]:
        """Pick uncovered Tier-1 archetypes stratified across categories and Track A / Track B."""
        cov = self.tier1_coverage()
        counts = cov["counts_by_archetype"]
        rng = random.Random(f"tier1-targets:{seed}:{cov['covered_count']}")

        def _pick_stratified(pool_ids: list[str], want: int) -> list[str]:
            if want <= 0 or not pool_ids:
                return []
            by_cat: dict[str, list[str]] = {}
            for aid in pool_ids:
                by_cat.setdefault(BY_ID[aid].category, []).append(aid)
            cats = list(by_cat.keys())
            rng.shuffle(cats)
            for c in cats:
                # Prefer truly uncovered (count=0) first, then least-covered, randomized within ties.
                rng.shuffle(by_cat[c])
                by_cat[c].sort(key=lambda aid: counts.get(aid, 0))
            picked: list[str] = []
            while len(picked) < want:
                progressed = False
                for c in cats:
                    if by_cat[c]:
                        picked.append(by_cat[c].pop(0))
                        progressed = True
                        if len(picked) >= want:
                            break
                if not progressed:
                    break
            return picked

        all_a = [a.id for a in ARCHETYPES if a.id not in TRACK_B_ARCHETYPES]
        all_b = [a.id for a in ARCHETYPES if a.id in TRACK_B_ARCHETYPES]
        uncovered_a = [aid for aid in all_a if aid not in counts]
        uncovered_b = [aid for aid in all_b if aid not in counts]

        track_a_want = round(candidate_target * corpus_ratio)
        track_b_want = candidate_target - track_a_want

        chosen_a = _pick_stratified(uncovered_a, track_a_want)
        if len(chosen_a) < track_a_want:
            # Top up with least-covered Track A if all Track A are already covered
            rem_a = [aid for aid in all_a if aid not in chosen_a]
            chosen_a.extend(_pick_stratified(rem_a, track_a_want - len(chosen_a)))

        chosen_b = _pick_stratified(uncovered_b, track_b_want)
        if len(chosen_b) < track_b_want:
            rem_b = [aid for aid in all_b if aid not in chosen_b]
            chosen_b.extend(_pick_stratified(rem_b, track_b_want - len(chosen_b)))

        selected_ids = chosen_a + chosen_b
        preview_rng = random.Random(f"tier1-preview:{seed}")
        targets: list[dict[str, Any]] = []
        for aid in selected_ids:
            arch = BY_ID[aid]
            ex_digits, ex_cardinal = "", ""
            try:
                sampled = sample_archetype(aid, preview_rng)
                frag = _domain_node_fragment(aid, sampled)
                ex_digits, ex_cardinal = frag.digits, frag.cardinal
            except Exception:  # noqa: BLE001
                pass
            targets.append(
                {
                    "id": arch.id,
                    "title": arch.title,
                    "description": arch.description,
                    "category": arch.category,
                    "track": "synthetic_identifier" if aid in TRACK_B_ARCHETYPES else "corpus_inspired",
                    "already_covered": aid in counts,
                    "example_digits": ex_digits,
                    "example_cardinal": ex_cardinal,
                }
            )
        return targets

    def update_settings(self, *, ivrit_cookie: str | None = None) -> dict[str, Any]:
        if ivrit_cookie is not None:
            save_ivrit_cookie(self.data_root, ivrit_cookie)
        return self.environment_status()

    def cost_summary(self) -> dict[str, Any]:
        folder = self.batches_dir
        if not folder.is_dir():
            return {
                "total_batches": 0,
                "succeeded_batches": 0,
                "total_pairs_generated": 0,
                "total_cost_usd": 0.0,
                "avg_cost_per_100_pairs_usd": 0.0,
                "total_engine_bugs": 0,
            }
        total_batches = 0
        succeeded = 0
        total_pairs = 0
        total_cost = 0.0
        total_engine_bugs = 0
        for path in folder.glob("b_*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            total_batches += 1
            if data.get("status") == "succeeded":
                succeeded += 1
            total_pairs += len(data.get("pairs") or [])
            total_cost += float(data.get("total_cost_usd") or 0.0)
            total_engine_bugs += sum(1 for bug in (data.get("engine_bugs") or []) if not bug.get("resolved"))
        avg_100 = (total_cost / total_pairs * 100.0) if total_pairs > 0 else 0.0
        return {
            "total_batches": total_batches,
            "succeeded_batches": succeeded,
            "total_pairs_generated": total_pairs,
            "total_cost_usd": round(total_cost, 6),
            "avg_cost_per_100_pairs_usd": round(avg_100, 4),
            "total_engine_bugs": total_engine_bugs,
        }

    def list_batches(self) -> list[dict[str, Any]]:
        folder = self.batches_dir
        if not folder.is_dir():
            return []
        summaries: list[dict[str, Any]] = []
        paths = sorted(folder.glob("b_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:40]
        for path in paths:
            try:
                b = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            sess = (b.get("sessions") or [{}])[0]
            approved_tpls = sum(1 for t in (b.get("templates") or []) if (t.get("verdict") or {}).get("approved"))
            summaries.append(
                {
                    "id": b["id"],
                    "created_at": b["created_at"],
                    "updated_at": b["updated_at"],
                    "status": b["status"],
                    "target_count": b["target_count"],
                    "generated_count": len(b.get("pairs") or []),
                    "approved_templates": approved_tpls,
                    "total_templates": len(b.get("templates") or []),
                    "engine_bugs_count": sum(1 for bug in (b.get("engine_bugs") or []) if not bug.get("resolved")),
                    "seed": b["seed"],
                    "model": b.get("model", "google/gemini-4-neon"),
                    "session_id": sess.get("session_id"),
                    "total_cost_usd": b.get("total_cost_usd", 0.0),
                    "run_id": b.get("run_id"),
                }
            )
        return summaries

    def create_batch(
        self,
        *,
        target_count: int,
        template_count: int | None = None,
        seed: int = 42,
        corpus_ratio: float = 0.75,
        notes: str = "",
        reuse_snippets_from: list[str] | None = None,
        model: str = "google/gemini-4-neon",
        variant: str = "default",
        server_url: str = "http://127.0.0.1:8766",
        dispatch_session: bool = True,
        notify_session_id: str | None = None,
        notify_context: str = "",
    ) -> dict[str, Any]:
        if not (1 <= target_count <= 5000):
            raise ValueError("גודל האצווה חייב להיות בין 1 ל-5,000 משפטים")
        if not (0.0 <= corpus_ratio <= 1.0):
            raise ValueError("יחס הקורפוס חייב להיות בין 0 ל-1")
        if template_count is not None:
            if not (3 <= template_count <= 55):
                raise ValueError("מספר תבניות המיקרו לחילוץ חייב להיות בין 3 ל-55")
            candidate_target = int(template_count)
            min_approved = max(3, min(candidate_target, math.ceil(candidate_target * 0.72)))
        else:
            min_approved = max(3, min(40, math.ceil(target_count / 6)))
            candidate_target = max(5, min(55, math.ceil(target_count / 4) + 2))
        snippets_target = max(8, min(40, candidate_target))
        reuse_ids = [str(bid).strip() for bid in (reuse_snippets_from or []) if str(bid).strip()]

        has_custom_notes = bool(notes.strip())
        cov = self.tier1_coverage()
        target_archetypes = (
            []
            if has_custom_notes
            else self.select_default_target_archetypes(
                candidate_target=candidate_target,
                corpus_ratio=corpus_ratio,
                seed=seed,
            )
        )
        selection_mode = "custom_notes" if has_custom_notes else "tier1_uncovered_default"

        created_at = _now_iso()
        raw_id = sha256(f"{created_at}:{seed}:{target_count}:{notes}".encode("utf-8")).hexdigest()[:12]
        batch_id = f"b_{raw_id}"

        steps = [
            {"id": sid, "title": stitle, "status": "pending", "detail": "", "started_at": None, "completed_at": None}
            for sid, stitle in STEP_DEFINITIONS
        ]
        batch: dict[str, Any] = {
            "id": batch_id,
            "created_at": created_at,
            "updated_at": created_at,
            "status": "running",
            "target_count": target_count,
            "seed": seed,
            "corpus_ratio": corpus_ratio,
            "notes": notes,
            "reuse_snippets_from": reuse_ids,
            "selection_mode": selection_mode,
            "target_archetypes": target_archetypes,
            "model": model,
            "variant": variant,
            "server_url": server_url.rstrip("/"),
            "sizing": {
                "snippets_target": snippets_target,
                "candidate_templates_target": candidate_target,
                "min_approved_templates": min_approved,
            },
            "steps": steps,
            "events": [],
            "sessions": [],
            "total_cost_usd": 0.0,
            "mine_mode": None,
            "mined_snippets": [],
            "templates": [],
            "compile_errors": [],
            "engine_bugs": [],
            "pairs": [],
            "run_id": None,
            "error": None,
            "notify_session_id": (notify_session_id or "").strip() or None,
            "notify_context": (notify_context or "").strip(),
            "notify_sent_at": None,
            "notify_error": None,
        }

        self._set_step(batch, "dispatch", "running", f"יוצר סשן {model} ב-OpenChamber…")
        if target_archetypes:
            ids_preview = ", ".join(t["id"] for t in target_archetypes)
            self._log_event(
                batch,
                "dispatch",
                f"התחלת אצווה {batch_id} עבור {target_count} משפטים (זרע {seed}) · מניפת שימושים מספריים לשילוב טבעי: {ids_preview}.",
            )
        else:
            self._log_event(batch, "dispatch", f"התחלת אצווה {batch_id} עבור {target_count} משפטים (זרע {seed}).")

        with _pipeline_lock:
            self._write_batch(batch)

        if not dispatch_session:
            with _pipeline_lock:
                self._set_step(batch, "dispatch", "done", "מצב בדיקה מקומי (ללא שיגור OpenChamber אוטומטי)")
                return self._write_batch(batch)

        temp_dir = str(self.data_root / "pipeline" / "tmp")
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        enabled_sources = load_corpus_sources(self.data_root, enabled_only=True)
        prompt = build_neon_prompt(
            batch_id=batch_id,
            server_url=server_url.rstrip("/"),
            target_count=target_count,
            candidate_templates_target=candidate_target,
            min_approved_templates=min_approved,
            corpus_ratio=corpus_ratio,
            user_notes=notes,
            temp_dir=temp_dir,
            target_archetypes=target_archetypes,
            tier1_coverage=cov,
            corpus_sources=enabled_sources,
            reuse_snippets_from=reuse_ids or None,
        )

        def _on_bg_prompt_err(err_msg: str) -> None:
            should_notify = False
            with _pipeline_lock:
                cur = self._read_batch_unlocked(batch_id)
                if cur and cur["status"] == "running":
                    cur["status"] = "failed"
                    cur["error"] = f"שגיאה בשליחת ההנחיה לסשן OpenChamber: {err_msg}"
                    self._set_step(cur, "dispatch", "failed", cur["error"])
                    self._log_event(cur, "dispatch", cur["error"])
                    self._write_batch(cur)
                    should_notify = True
            if should_notify:
                self._dispatch_completion_notification(batch_id)

        try:
            sess = self.oc_client.create_and_start_session(
                title=f"Neon Numeric Batch · {target_count} pairs ({batch_id})",
                prompt=prompt,
                directory=str(self.repo_dir),
                model_spec=model,
                variant=variant,
                on_prompt_error=_on_bg_prompt_err,
            )
        except OpenChamberError as exc:
            with _pipeline_lock:
                batch["status"] = "failed"
                batch["error"] = str(exc)
                self._set_step(batch, "dispatch", "failed", str(exc))
                self._log_event(batch, "dispatch", f"כשל בשיגור סשן OpenChamber: {exc}")
                self._write_batch(batch)
            raise ValueError(str(exc)) from exc

        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id) or batch
            batch["sessions"].append(
                {
                    "session_id": sess["session_id"],
                    "role": "neon_pipeline",
                    "model": sess["model"],
                    "variant": sess["variant"],
                    "status": "busy",
                    "outcome": None,
                    "cost_usd": 0.0,
                    "cost_source": "pending",
                    "tokens": {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0},
                    "assistant_turns": 0,
                    "last_activity": "הסשן נוצר ומתחיל עבודה…",
                    "dispatched_at_ts": time.time(),
                }
            )
            self._set_step(batch, "dispatch", "done", f"סשן {sess['session_id']} פעיל ({sess['model']})")
            self._set_step(batch, "mine", "running", "ממתין להפעלת דגימת הקורפוס מהסשן…")
            self._log_event(batch, "dispatch", f"סשן OpenChamber נוצר בהצלחה: {sess['session_id']}")
            saved = self._write_batch(batch)
        if saved.get("notify_session_id"):
            self._start_batch_monitor(batch_id)
        return saved

    def sync_batch_telemetry(self, batch_id: str, *, force: bool = False) -> dict[str, Any] | None:
        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
        if batch is None:
            return None
        if not batch.get("sessions"):
            return batch

        now = time.time()
        last = self._last_sync_ts.get(batch_id, 0.0)
        if not force and batch["status"] in ("succeeded", "failed") and now - last < 15.0:
            return batch
        if not force and now - last < 1.2:
            return batch
        self._last_sync_ts[batch_id] = now

        updated_sessions = []
        total_cost = 0.0
        all_idle = True
        any_failed_outcome = False
        earliest_dispatch = now

        for s_entry in batch["sessions"]:
            sid = s_entry["session_id"]
            earliest_dispatch = min(earliest_dispatch, float(s_entry.get("dispatched_at_ts") or now))
            try:
                tel = self.oc_client.fetch_session_telemetry(sid, str(self.repo_dir))
                merged = {**s_entry, **tel}
            except OpenChamberError:
                merged = dict(s_entry)
            total_cost += float(merged.get("cost_usd") or 0.0)
            if merged.get("status") != "idle":
                all_idle = False
            if merged.get("outcome") in ("failed", "error"):
                any_failed_outcome = True
            updated_sessions.append(merged)

        transitioned_terminal = False
        with _pipeline_lock:
            fresh = self._read_batch_unlocked(batch_id)
            if fresh is None:
                return None
            fresh["sessions"] = updated_sessions
            fresh["total_cost_usd"] = round(total_cost, 6)

            # Detect unexpected session completion before finalize
            if (
                fresh["status"] == "running"
                and all_idle
                and (now - earliest_dispatch) > 10.0
                and any(s.get("assistant_turns", 0) > 0 or any_failed_outcome for s in updated_sessions)
            ):
                # Re-check status wasn't just finalized
                if fresh["status"] == "running":
                    approved_specs = [
                        t["spec"] for t in fresh.get("templates", []) if (t.get("verdict") or {}).get("approved")
                    ]
                    if approved_specs:
                        # Auto-finalize if the agent completed verdicts right as turn ended
                        self._finalize_unlocked(fresh, approved_specs)
                    else:
                        last_act = updated_sessions[-1].get("last_activity") or "הסשן הסתיים ללא השלמת finalize"
                        fresh["status"] = "failed"
                        fresh["error"] = f"סשן ה-OpenChamber נעצר לפני השלמת הצינור ({last_act})"
                        for st in fresh["steps"]:
                            if st["status"] == "running":
                                st["status"] = "failed"
                                st["detail"] = fresh["error"]
                                st["completed_at"] = _now_iso()
                        self._log_event(fresh, "finalize", fresh["error"])
                    transitioned_terminal = True
            saved = self._write_batch(fresh)
        if transitioned_terminal:
            self._dispatch_completion_notification(batch_id)
        return saved

    def run_mine_step(self, batch_id: str) -> dict[str, Any]:
        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
            if batch is None:
                raise ValueError(f"Unknown batch_id: {batch_id}")
            target_arch_objs = list(batch.get("target_archetypes") or [])
            target_arch_ids = [t["id"] for t in target_arch_objs if isinstance(t, dict) and t.get("id")]
            reuse_ids = list(batch.get("reuse_snippets_from") or [])
            if reuse_ids:
                mine_msg = "טוען הקשרי דיבור עשירים שכבר נדגמו מאצוות קודמות (ללא דגימה מחדש)…"
            elif target_arch_ids:
                mine_msg = f"דוגם הקשרי שיחה טבעיים ממקורות הקורפוס (כולל השראה ל-{len(target_arch_ids)} שימושים מספריים)…"
            else:
                mine_msg = "דוגם הקשרי שיחה טבעיים ממקורות הקורפוס…"
            self._set_step(batch, "mine", "running", mine_msg)
            self._write_batch(batch)
            target_snips = batch["sizing"]["snippets_target"]
            seed = batch["seed"]

        if reuse_ids:
            mined = self._collect_reused_snippets(
                reuse_ids,
                exclude_batch_id=batch_id,
                target_snippets=target_snips,
                seed=seed,
            )
            if not mined["snippets"]:
                mined = mine_spoken_contexts(
                    self.data_root,
                    target_snippets=target_snips,
                    seed=seed,
                    target_archetypes=target_arch_ids or None,
                )
        else:
            mined = mine_spoken_contexts(
                self.data_root,
                target_snippets=target_snips,
                seed=seed,
                target_archetypes=target_arch_ids or None,
            )

        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
            assert batch is not None
            batch["mine_mode"] = mined["mode"]
            batch["mined_snippets"] = mined["snippets"]
            mode_labels = {
                "live_ivrit_ai": "מ-explore.ivrit.ai (חי)",
                "live_text_sources": "ממקורות קובצי הטקסט המוגדרים (חי)",
                "live_mixed": "מ-explore.ivrit.ai ומקורות קובצי הטקסט (חי)",
                "reused_from_batches": "בשימוש חוזר מהשראות אצוות קודמות",
                "exemplar_fallback": "מדוגמאות קצב דיבור מובנות",
            }
            mode_label = mode_labels.get(mined["mode"], mined["mode"])
            detail = f"נטענו {len(mined['snippets'])} הקשרי שיחה {mode_label}"
            if mined.get("source_batches"):
                detail += f" ({len(mined['source_batches'])} אצוות מקור)"
            if mined.get("warning"):
                detail += f" ({mined['warning']})"
            self._set_step(batch, "mine", "done", detail)
            self._set_step(batch, "lift", "running", "Gemini 4 Neon מחלץ תבניות מיקרו מדוברות ובנקים מקומיים…")
            self._log_event(batch, "mine", detail)
            self._write_batch(batch)
            return {
                "batch_id": batch_id,
                "mode": mined["mode"],
                "warning": mined.get("warning", ""),
                "sizing": batch["sizing"],
                "selection_mode": batch.get("selection_mode", "custom_notes"),
                "target_archetypes": target_arch_objs,
                "available_sources": [
                    {
                        "id": s["id"],
                        "name": s["name"],
                        "type": s["type"],
                        "location": s["location"],
                        "description": s.get("description", ""),
                    }
                    for s in load_corpus_sources(self.data_root, enabled_only=True)
                ],
                "snippets": mined["snippets"],
            }

    def submit_templates(self, batch_id: str, raw_templates: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(raw_templates, list) or not raw_templates:
            raise ValueError("Expected a non-empty JSON list of MicroTemplate objects")
        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
            if batch is None:
                raise ValueError(f"Unknown batch_id: {batch_id}")
            self._set_step(batch, "lift", "done", f"התקבלו {len(raw_templates)} תבניות מועמדות מ-Neon")
            self._set_step(batch, "compile_stress", "running", "מקמפל תבניות דרך core.py ומייצר 8 דגימות קצה לכל תבנית…")
            self._write_batch(batch)
            seed = batch["seed"]

        compiled_entries: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for idx, spec in enumerate(raw_templates):
            tid = str(spec.get("id", f"tpl_{idx}")) if isinstance(spec, dict) else f"tpl_{idx}"
            try:
                stress_pairs = validate_and_stress_template(spec, stress_count=8, seed=seed)
                compiled_entries.append(
                    {
                        "id": spec["id"],
                        "archetype_id": spec["archetype_id"],
                        "covered_usages": template_covered_usages(spec),
                        "source_snippet_id": spec.get("source_snippet_id") or "",
                        "category": BY_ID[spec["archetype_id"]].category,
                        "track": spec.get("track", "corpus_inspired"),
                        "inspiration_summary": spec.get("inspiration_summary", ""),
                        "spec": spec,
                        "stress_samples": [
                            {
                                "index": s["index"],
                                "digits": s["digits"],
                                "cardinal": s["cardinal"],
                                "alignments": s["alignments"],
                            }
                            for s in stress_pairs
                        ],
                        "verdict": None,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                errors.append({"id": tid, "error": str(exc)})

        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
            assert batch is not None
            existing_by_id = {t["id"]: t for t in batch.get("templates", [])}
            for entry in compiled_entries:
                existing_by_id[entry["id"]] = entry
            batch["templates"] = list(existing_by_id.values())
            batch["compile_errors"] = errors

            total_compiled = len(batch["templates"])
            categories = sorted({t["category"] for t in batch["templates"]})
            detail = (
                f"{total_compiled} תבניות עברו קומפילציה דטרמיניסטית ({total_compiled * 8} דגימות קצה אומתו)"
                + (f"; {len(errors)} נדחו תחבירית" if errors else "")
            )
            self._set_step(batch, "compile_stress", "done" if total_compiled > 0 else "failed", detail)
            if total_compiled > 0:
                self._set_step(batch, "critic", "running", f"ממתין לבקרת טבעיות 8/8 על {total_compiled} תבניות…")
            self._log_event(batch, "compile_stress", detail)
            self._write_batch(batch)
            return {
                "accepted_this_call": [e["id"] for e in compiled_entries],
                "total_compiled_templates": total_compiled,
                "distinct_categories": categories,
                "min_approved_templates_needed": batch["sizing"]["min_approved_templates"],
                "opening_diversity_warnings": _opening_diversity_warnings(batch["templates"]),
                "errors": errors,
            }

    def get_stress_pack(self, batch_id: str) -> dict[str, Any]:
        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
            if batch is None:
                raise ValueError(f"Unknown batch_id: {batch_id}")
            pending_templates = [
                {
                    "template_id": t["id"],
                    "archetype_id": t["archetype_id"],
                    "category": t["category"],
                    "inspiration_summary": t.get("inspiration_summary", ""),
                    "stress_realizations": [
                        {"idx": s["index"], "digits": s["digits"], "cardinal": s["cardinal"]}
                        for s in t["stress_samples"]
                    ],
                }
                for t in batch.get("templates", [])
                if t.get("verdict") is None
            ]
            self._set_step(batch, "critic", "running", f"סשן Neon בודק {len(pending_templates)} תבניות (8 דגימות לכל תבנית)…")
            self._write_batch(batch)
            return {
                "batch_id": batch_id,
                "min_approved_templates_needed": batch["sizing"]["min_approved_templates"],
                "opening_diversity_warnings": _opening_diversity_warnings(batch.get("templates", [])),
                "templates_to_audit": pending_templates,
            }

    def submit_verdicts(self, batch_id: str, verdicts: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(verdicts, list) or not verdicts:
            raise ValueError("Expected a non-empty JSON list of verdict objects")
        allowed_kinds = {"approved", "spec_repairable", "engine_bug", "template_defect"}
        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
            if batch is None:
                raise ValueError(f"Unknown batch_id: {batch_id}")
            by_id = {t["id"]: t for t in batch.get("templates", [])}
            applied = 0
            for v in verdicts:
                if not isinstance(v, dict):
                    continue
                tid = str(v.get("template_id", ""))
                if tid not in by_id:
                    continue
                passed_count = int(v.get("passed_count", 0))
                strict_approved = bool(v.get("approved")) and passed_count == 8
                raw_kind = str(v.get("verdict_kind") or ("approved" if strict_approved else "template_defect")).strip()
                if raw_kind not in allowed_kinds:
                    raw_kind = "approved" if strict_approved else "template_defect"
                if strict_approved:
                    verdict_kind = "approved"
                elif raw_kind == "approved":
                    verdict_kind = "template_defect"
                else:
                    verdict_kind = raw_kind
                failed_idx_raw = v.get("failed_idx")
                reason_str = str(v.get("reason", "")).strip() or ("עבר 8/8" if strict_approved else "לא עבר 8/8")
                if isinstance(failed_idx_raw, int) and 0 <= failed_idx_raw < 8:
                    failed_idx: int | None = failed_idx_raw
                else:
                    m_idx = re.search(r"idx\s*(\d+)", reason_str)
                    failed_idx = int(m_idx.group(1)) if (m_idx and 0 <= int(m_idx.group(1)) < 8) else None
                by_id[tid]["verdict"] = {
                    "passed_count": passed_count,
                    "approved": strict_approved,
                    "verdict_kind": verdict_kind,
                    "failed_idx": failed_idx,
                    "reason": reason_str,
                }
                applied += 1

            approved = [t for t in batch["templates"] if (t.get("verdict") or {}).get("approved")]
            rejected = [t for t in batch["templates"] if t.get("verdict") is not None and not t["verdict"]["approved"]]
            engine_bugs = []
            for t in rejected:
                if t["verdict"].get("verdict_kind") != "engine_bug":
                    continue
                samples = t.get("stress_samples") or []
                f_idx = t["verdict"].get("failed_idx")
                chosen = samples[f_idx] if (isinstance(f_idx, int) and 0 <= f_idx < len(samples)) else (samples[0] if samples else None)
                engine_bugs.append(
                    {
                        "template_id": t["id"],
                        "archetype_id": t["archetype_id"],
                        "failed_idx": f_idx if isinstance(f_idx, int) else 0,
                        "reason": t["verdict"]["reason"],
                        "sample_digits": chosen["digits"] if chosen else "",
                        "sample_cardinal": chosen["cardinal"] if chosen else "",
                        "resolved": False,
                    }
                )
            repairable = [t["id"] for t in rejected if t["verdict"].get("verdict_kind") == "spec_repairable"]
            batch["engine_bugs"] = engine_bugs

            approved_categories = sorted({t["category"] for t in approved})
            detail = f"אושרו {len(approved)} תבניות (8/8 מלא) על פני {len(approved_categories)} משפחות; נפסלו {len(rejected)}"
            if engine_bugs:
                detail += f" · ⚠️ זוהו {len(engine_bugs)} באגי מנוע!"
            self._set_step(batch, "critic", "done" if approved else "running", detail)
            self._log_event(batch, "critic", detail)
            self._write_batch(batch)
            return {
                "applied": applied,
                "approved_templates": len(approved),
                "rejected_templates": len(rejected),
                "engine_bugs_flagged": len(engine_bugs),
                "spec_repairable_templates": repairable,
                "approved_categories": approved_categories,
                "min_approved_templates_needed": batch["sizing"]["min_approved_templates"],
                "ready_to_finalize": len(approved) >= 1,
            }

    def recheck_engine_bugs(self, batch_id: str, *, approve_fixed: bool = True) -> dict[str, Any]:
        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
            if batch is None:
                raise ValueError(f"Unknown batch_id: {batch_id}")
            seed = batch["seed"]
            by_id = {t["id"]: t for t in batch.get("templates", [])}
            resolved_now = 0
            newly_approved_specs: list[dict[str, Any]] = []
            for bug in batch.get("engine_bugs") or []:
                tid = bug.get("template_id")
                t = by_id.get(tid)
                if not t or not t.get("spec"):
                    continue
                old_samples = t.get("stress_samples") or []
                fresh_pairs = validate_and_stress_template(t["spec"], stress_count=8, seed=seed)
                fresh_samples = [
                    {
                        "index": s["index"],
                        "digits": s["digits"],
                        "cardinal": s["cardinal"],
                        "alignments": s["alignments"],
                    }
                    for s in fresh_pairs
                ]
                f_idx = bug.get("failed_idx")
                if not isinstance(f_idx, int):
                    m_idx = re.search(r"idx\s*(\d+)", str(bug.get("reason", "")))
                    f_idx = int(m_idx.group(1)) if (m_idx and 0 <= int(m_idx.group(1)) < len(fresh_samples)) else 0
                bug["failed_idx"] = f_idx
                changed = False
                if 0 <= f_idx < len(old_samples) and 0 <= f_idx < len(fresh_samples):
                    bug["sample_digits"] = fresh_samples[f_idx]["digits"]
                    if not bug.get("resolved"):
                        bug["sample_cardinal"] = old_samples[f_idx]["cardinal"]
                    changed = old_samples[f_idx]["cardinal"] != fresh_samples[f_idx]["cardinal"] or any(
                        o["cardinal"] != n["cardinal"] for o, n in zip(old_samples, fresh_samples)
                    )
                    if changed:
                        bug["fixed_cardinal"] = fresh_samples[f_idx]["cardinal"]
                        bug["resolved"] = True
                        resolved_now += 1
                t["stress_samples"] = fresh_samples

                if approve_fixed and bug.get("resolved") and not (t.get("verdict") or {}).get("approved"):
                    old_verdict = t.get("verdict") or {}
                    old_reason = str(old_verdict.get("reason", "")).strip()
                    t["verdict"] = {
                        "passed_count": 8,
                        "approved": True,
                        "verdict_kind": "approved",
                        "rescued_from_engine_bug": True,
                        "resolved": True,
                        "reason": (
                            f"8/8 אושר לאחר תיקון באג המנוע ({old_reason})"
                            if old_reason and "אושר לאחר תיקון" not in old_reason
                            else (old_reason or "8/8 אושר לאחר תיקון באג המנוע")
                        ),
                    }
                    bug["approved_after_fix"] = True
                    newly_approved_specs.append(t["spec"])

            if newly_approved_specs:
                promote_specs_to_library(
                    self.data_root,
                    newly_approved_specs,
                    source_batch_id=batch["id"],
                    enabled=True,
                )
                approved = [t for t in batch["templates"] if (t.get("verdict") or {}).get("approved")]
                rejected = [t for t in batch["templates"] if t.get("verdict") is not None and not t["verdict"]["approved"]]
                approved_categories = sorted({t["category"] for t in approved})
                critic_detail = (
                    f"אושרו {len(approved)} תבניות (8/8 מלא) על פני {len(approved_categories)} משפחות; "
                    f"נפסלו {len(rejected)} · ✓ {len(newly_approved_specs)} אושרו לאחר תיקון מנוע"
                )
                self._set_step(batch, "critic", "done", critic_detail)

                if batch.get("status") == "succeeded":
                    existing_pairs = list(batch.get("pairs") or [])
                    per_tpl = max(2, round(batch["target_count"] / max(1, len(approved))))
                    extra_count = per_tpl * len(newly_approved_specs)
                    extra_candidates = generate_from_templates(
                        newly_approved_specs,
                        extra_count + 6,
                        seed=seed + 1009,
                    )
                    seen_digits = {p["digits"] for p in existing_pairs}
                    added_pairs: list[dict[str, Any]] = []
                    for p in extra_candidates:
                        if p["digits"] not in seen_digits:
                            seen_digits.add(p["digits"])
                            added_pairs.append(p)
                            if len(added_pairs) >= extra_count:
                                break
                    combined_pairs = existing_pairs + added_pairs
                    review_store = self._get_review_store()
                    old_run_id = batch.get("run_id")
                    run_record = review_store.register_pipeline_run(
                        batch_id=batch["id"],
                        seed=batch["seed"],
                        pairs=combined_pairs,
                        pipeline_meta={
                            "model": batch.get("model"),
                            "approved_templates": len(approved),
                            "total_cost_usd": batch.get("total_cost_usd", 0.0),
                        },
                    )
                    if old_run_id and old_run_id != run_record["id"] and not review_store.feedback(old_run_id):
                        old_path = review_store.root / f"run-{old_run_id}.json"
                        old_path.unlink(missing_ok=True)
                    batch["pairs"] = combined_pairs
                    batch["run_id"] = run_record["id"]
                    fin_detail = (
                        f"נוצרו ואומתו {len(combined_pairs)} זוגות משפטים טבעיים "
                        f"(כולל {len(added_pairs)} מהתבניות שתוקנו) · נשמר כריצה {run_record['id'][:8]}"
                    )
                    self._set_step(batch, "finalize", "done", fin_detail)
                    self._log_event(
                        batch,
                        "finalize",
                        f"✓ אושרו {len(newly_approved_specs)} תבניות לאחר תיקון באג המנוע ונוספו {len(added_pairs)} משפטים לאצווה",
                    )
            elif resolved_now:
                self._log_event(batch, "critic", f"✓ אומת תיקון מנוע עבור {resolved_now} תבניות שסומנו")

            self._write_batch(batch)
            return batch

    def _finalize_unlocked(self, batch: dict[str, Any], approved_specs: list[dict[str, Any]]) -> dict[str, Any]:
        self._set_step(batch, "finalize", "running", f"מפיק דטרמיניסטית {batch['target_count']} זוגות משפטים…")
        pairs = generate_from_templates(approved_specs, batch["target_count"], seed=batch["seed"])
        review_store = self._get_review_store()
        lib_res = promote_specs_to_library(
            self.data_root,
            approved_specs,
            source_batch_id=batch["id"],
            enabled=True,
            official_path=review_store.official_library_path,
            include_official=review_store.include_official_library,
        )
        run_record = review_store.register_pipeline_run(
            batch_id=batch["id"],
            seed=batch["seed"],
            pairs=pairs,
            pipeline_meta={
                "model": batch.get("model"),
                "approved_templates": len(approved_specs),
                "total_cost_usd": batch.get("total_cost_usd", 0.0),
            },
        )
        batch["pairs"] = pairs
        batch["run_id"] = run_record["id"]
        batch["status"] = "succeeded"
        batch["library_promoted"] = {
            "added": lib_res["added"],
            "updated": lib_res["updated"],
            "enabled_total": lib_res["summary"]["enabled_templates"],
        }
        detail = (
            f"נוצרו ואומתו {len(pairs)} זוגות משפטים טבעיים · "
            f"{len(approved_specs)} תבניות מיקרו נשמרו בספרייה ({lib_res['summary']['enabled_templates']} פעילות) · "
            f"ריצה {run_record['id'][:8]}"
        )
        self._set_step(batch, "finalize", "done", detail)
        self._log_event(batch, "finalize", detail)
        return batch

    def finalize_batch(self, batch_id: str) -> dict[str, Any]:
        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
            if batch is None:
                raise ValueError(f"Unknown batch_id: {batch_id}")
            approved_specs = [
                t["spec"] for t in batch.get("templates", []) if (t.get("verdict") or {}).get("approved")
            ]
            if not approved_specs:
                raise ValueError("אין תבניות שעברו בקרת 8/8 להפקת המשפטים")
            self._finalize_unlocked(batch, approved_specs)
            self._write_batch(batch)
        # Do one final telemetry sync to capture end-of-session cost
        synced = self.sync_batch_telemetry(batch_id, force=True) or batch
        self._dispatch_completion_notification(batch_id)
        return {
            "batch_id": batch_id,
            "status": synced["status"],
            "generated_count": len(synced["pairs"]),
            "run_id": synced["run_id"],
            "total_cost_usd": synced["total_cost_usd"],
        }

    def fail_batch(self, batch_id: str, reason: str) -> dict[str, Any]:
        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
            if batch is None:
                raise ValueError(f"Unknown batch_id: {batch_id}")
            batch["status"] = "failed"
            batch["error"] = reason
            for st in batch["steps"]:
                if st["status"] == "running":
                    st["status"] = "failed"
                    st["detail"] = reason
                    st["completed_at"] = _now_iso()
            self._log_event(batch, "error", reason)
            saved = self._write_batch(batch)
        self._dispatch_completion_notification(batch_id)
        return saved

    def cancel_batch(self, batch_id: str) -> dict[str, Any]:
        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
            if batch is None:
                raise ValueError(f"Unknown batch_id: {batch_id}")
            sessions = list(batch.get("sessions") or [])
        for s in sessions:
            sid = s.get("session_id")
            if sid:
                try:
                    self.oc_client.interrupt_session(sid, str(self.repo_dir))
                except OpenChamberError:
                    pass
        self.fail_batch(batch_id, "האצווה הופסקה ידנית מהממשק")
        return self.sync_batch_telemetry(batch_id, force=True) or {}

    @staticmethod
    def _build_completion_notification(batch: dict[str, Any]) -> str:
        approved = sum(1 for t in (batch.get("templates") or []) if (t.get("verdict") or {}).get("approved"))
        total_tpls = len(batch.get("templates") or [])
        unresolved_bugs = sum(1 for b in (batch.get("engine_bugs") or []) if not b.get("resolved"))
        lib_info = batch.get("library_promoted") or {}
        lines = [
            f"[Pipeline Batch Completed] {batch['id']} — status: {batch['status']}",
            (
                f"target_count: {batch.get('target_count')} | generated_pairs: {len(batch.get('pairs') or [])} | "
                f"seed: {batch.get('seed')}"
            ),
            (
                f"templates: {approved}/{total_tpls} approved | compile_errors: {len(batch.get('compile_errors') or [])} | "
                f"engine_bugs: {unresolved_bugs}"
            ),
            (
                f"mine_mode: {batch.get('mine_mode')} | snippets: {len(batch.get('mined_snippets') or [])} | "
                f"cost_usd: ${float(batch.get('total_cost_usd') or 0.0):.4f} | run_id: {batch.get('run_id')}"
            ),
        ]
        if lib_info:
            lines.append(
                f"library_promoted: +{lib_info.get('added', 0)} added, {lib_info.get('updated', 0)} updated "
                f"(enabled_total={lib_info.get('enabled_total', '?')})"
            )
        if batch.get("error"):
            lines.append(f"error: {batch['error']}")
        if batch.get("notify_context"):
            lines.append(f"context: {batch['notify_context']}")
        return "\n".join(lines)

    def _dispatch_completion_notification(self, batch_id: str) -> bool:
        """Wake up `notify_session_id` exactly once when a batch reaches a terminal status."""
        with _pipeline_lock:
            batch = self._read_batch_unlocked(batch_id)
            if not batch:
                return False
            target_sid = batch.get("notify_session_id")
            if not target_sid or batch.get("status") not in ("succeeded", "failed"):
                return False
            if batch.get("notify_sent_at") or batch_id in self._notifying_batches:
                return False
            self._notifying_batches.add(batch_id)
            message = self._build_completion_notification(batch)

        def _send_notify_bg() -> None:
            try:
                # Wait briefly if the target session is still busy/retrying a previous turn
                for _ in range(15):
                    status = self.oc_client.get_session_status(target_sid, str(self.repo_dir))
                    if status not in ("busy", "retry", "waiting"):
                        break
                    time.sleep(4.0)

                last_err: str | None = None
                for attempt, delay in enumerate((0.0, 5.0, 15.0)):
                    if delay > 0:
                        time.sleep(delay)
                    with _pipeline_lock:
                        cur = self._read_batch_unlocked(batch_id)
                        if cur:
                            cur["notify_sent_at"] = _now_iso()
                            cur["notify_error"] = None
                            self._log_event(cur, "finalize", f"שולח הודעת סיום לסשן {target_sid}")
                            self._write_batch(cur)
                    t0 = time.time()
                    try:
                        self.oc_client.send_prompt(
                            target_sid,
                            message,
                            directory=str(self.repo_dir),
                            timeout=900.0,
                        )
                        last_err = None
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_err = str(exc)
                        # If the request ran for >10s, the prompt was already delivered and our
                        # HTTP read merely timed out while the woken session was working; do not resend.
                        if time.time() - t0 > 10.0:
                            last_err = None
                            break
                        if attempt < 2:
                            continue

                if last_err is not None:
                    with _pipeline_lock:
                        cur = self._read_batch_unlocked(batch_id)
                        if cur:
                            cur["notify_sent_at"] = None
                            cur["notify_error"] = last_err
                            self._log_event(cur, "error", f"שליחת הודעת סיום לסשן {target_sid} נכשלה: {last_err}")
                            self._write_batch(cur)
            finally:
                with _pipeline_lock:
                    self._notifying_batches.discard(batch_id)

        Thread(target=_send_notify_bg, name=f"batch-notify-{batch_id[:10]}", daemon=True).start()
        return True

    def _start_batch_monitor(self, batch_id: str) -> None:
        """Background monitor that auto-approves child permissions and ensures terminal notifications fire."""
        with _pipeline_lock:
            if batch_id in self._monitored_batches:
                return
            self._monitored_batches.add(batch_id)

        def _monitor_loop() -> None:
            started = time.time()
            try:
                while time.time() - started < self._monitor_max_wait_s:
                    time.sleep(self._monitor_interval_s)
                    batch = self.sync_batch_telemetry(batch_id, force=True)
                    if batch is None:
                        return
                    if batch.get("status") in ("succeeded", "failed"):
                        self._dispatch_completion_notification(batch_id)
                        return
                # Safety timeout if the child session hung for over an hour
                self.fail_batch(batch_id, "האצווה חרגה מזמן ההמתנה המרבי במנטר הרקע")
            finally:
                with _pipeline_lock:
                    self._monitored_batches.discard(batch_id)

        Thread(target=_monitor_loop, name=f"batch-mon-{batch_id[:10]}", daemon=True).start()

    def resume_pending_monitors(self) -> list[str]:
        """Re-attach background monitors for any running batches with notify_session_id after server restart."""
        folder = self.batches_dir
        if not folder.is_dir():
            return []
        resumed: list[str] = []
        for path in folder.glob("b_*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("status") == "running" and data.get("notify_session_id") and not data.get("notify_sent_at"):
                self._start_batch_monitor(data["id"])
                resumed.append(data["id"])
        return resumed
