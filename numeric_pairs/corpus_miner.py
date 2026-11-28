"""Stratified spoken-context miner from explore.ivrit.ai with graceful fallback.

Queries natural spoken Hebrew podcasts across varied numeric regexes, expands
each hit with surrounding transcript segments (`/api/episodes/{id}/segments`),
redacts personal identifiers, and filters out repetitive show-intro boilerplate.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import random
import re
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from .candidates import _SENSITIVE
from .corpus_sources import (
    CorpusSourceError,
    load_corpus_sources,
    search_text_file_source,
)

PODCAST_SOURCES = (
    "גיקונומי",
    "אחד ביום",
    "בזמן שעבדתם",
    "שנקל",
    "לא סותמים",
    "עוד פודקאסט לסטארטאפים",
    "היסטוריה גדולה בקטנה",
    "מפתחים חסרי תרבות",
    "האוניברסיטה הפתוחה",
    "הפודקאסט של נדב פרי",
    "על המשמעות",
    "חיות כיס",
)

REGEX_BUCKETS = (
    ("multi_digit_counts", r"\d\d+"),
    ("structured_decimals_pct", r"\d+[:./%]\d*"),
    ("prefixed_numbers", r"[בלמכ]-\d+"),
    ("spoken_units", r"\d+\s*(שעות|דקות|שנים|מטר|אחוז|שקל|דולר)"),
)

# Tailored explore.ivrit.ai search queries (mode, query) for every Tier-1 catalog archetype.
ARCHETYPE_MINING_QUERIES: dict[str, tuple[str, str]] = {
    "address": ("exact", "רחוב"),
    "delivery": ("exact", "משלוח"),
    "purchase": ("exact", "קניתי"),
    "approximate": ("regex", r"כ-\d+"),
    "floor": ("exact", "קומה"),
    "departure": ("exact", "בשעה"),
    "survey": ("exact", "אחוז"),
    "mobile": ("exact", "טלפון"),
    "ranking": ("exact", "המקום"),
    "age": ("exact", "בגיל"),
    "year": ("regex", r"ב-?(19\d\d|20[0-2]\d)"),
    "calendar": ("exact", "באוקטובר"),
    "duration_half": ("exact", "וחצי"),
    "fraction": ("exact", "רבע"),
    "decimal_temp": ("exact", "מעלות"),
    "negative_temp": ("exact", "מינוס"),
    "money": ("exact", "שקל"),
    "weight": ("exact", "קילו"),
    "card_suffix": ("exact", "אשראי"),
    "road_route": ("exact", "כביש"),
    "version": ("exact", "גרסה"),
    "score": ("exact", "ניצחון"),
    "age_range": ("exact", "גילאי"),
    "percent_half": ("exact", "אחוז"),
    "full_date": ("exact", "בתאריך"),
    "money_cents": ("exact", "אגורות"),
    "distance": ("exact", "קילומטר"),
    "section": ("exact", "סעיף"),
    "postal": ("exact", "דואר"),
    "infant_age": ("exact", "תינוק"),
    "decade": ("regex", r"שנות\s+ה-?\d0"),
    "stopwatch_seconds": ("exact", "שניות"),
    "area": ("exact", "מטר"),
    "map_scale": ("exact", "מפה"),
    "maximum_attendees": ("exact", "משתתפים"),
    "pill_range": ("exact", "כדורים"),
    "opening_hours": ("regex", r"\d+:00"),
    "dollar_price": ("exact", "דולר"),
    "million_exact": ("exact", "מיליון"),
    "meeting_minute": ("exact", "פגישה"),
    "card_full": ("exact", "כרטיס"),
    "international_phone": ("exact", "שיחה"),
    "civil_id": ("exact", "תעודת"),
    "passport_id": ("exact", "דרכון"),
    "stopwatch_minute": ("exact", "דקות"),
    "euro_price": ("exact", "יורו"),
    "data_plan": ("exact", "ג'יגה"),
    "bank_account": ("exact", "סניף"),
    "license_plate": ("exact", "רכב"),
    "flight_number": ("exact", "טיסה"),
    "numeric_calendar": ("exact", "תאריך"),
    "slash_address": ("exact", "דירה"),
    "minimum_age": ("exact", "מעל גיל"),
    "large_shekels": ("exact", "אלף שקל"),
    "explicit_hundredths": ("exact", "מאיות"),
    "slash_date": ("exact", "תאריך"),
    "landline": ("exact", "משרד"),
    "local_landline": ("exact", "טלפון"),
    "national_line": ("exact", "מוקד"),
    "israeli_international": ("exact", "חו\"ל"),
    "business_line": ("exact", "שירות"),
    "bulk_purchase": ("exact", "הזמנה"),
    "plural_millions": ("exact", "מיליון"),
    "child_half_age": ("exact", "שנתיים"),
    "month_end_date": ("exact", "דצמבר"),
    "midnight_time": ("exact", "חצות"),
    "general_fraction": ("exact", "שליש"),
    "multi_digit_decimal": ("regex", r"\d+\.\d\d+"),
    "airline_flight": ("exact", "טיסה"),
}

_HAS_DIGIT = re.compile(r"\d")

_INTRO_NOISE = re.compile(r"(פרק\s*#?\s*\d+|מבית\s+N12|גיקונומי\s+\d+)", re.IGNORECASE)

# Spoken-prosody rhythm exemplars (original, non-copied) used when no ivrit.ai
# session cookie is configured or when offline/testing.
FALLBACK_SPOKEN_EXEMPLARS: tuple[dict[str, Any], ...] = (
    {
        "id": "ex_01",
        "bucket": "spoken_units",
        "source": "spoken-exemplar",
        "episode_title": "שיחה יומיומית · זמנים ושעות",
        "hit_text": "הוא יוצא משם יום אחר כך ב-12 בצהריים",
        "context_window": "הוא נכנס בערב ובכלל לא הבין כמה זמן זה ייקח. הוא יוצא משם יום אחר כך ב-12 בצהריים, כלומר הוא שם איזה 30 שעות שבהן הוא לא אכל כלום.",
    },
    {
        "id": "ex_02",
        "bucket": "structured_decimals_pct",
        "source": "spoken-exemplar",
        "episode_title": "אקטואליה מוסברת · השוואת מדדים",
        "hit_text": "קצב ההדבקה עלה כבר ל-0.9",
        "context_window": "במדינות אחרות החזירו הגבלות בגלל 4,000 פניות ביום. אצלנו ראינו השבוע כבר יותר מ-5,500 פניות ביום, והמדד השבועי עלה כבר ל-0.9.",
    },
    {
        "id": "ex_03",
        "bucket": "multi_digit_counts",
        "source": "spoken-exemplar",
        "episode_title": "סיפור משפחתי · פערי גילאים",
        "hit_text": "הוא באזור ה-35, 36",
        "context_window": "יואב הוא האח הבכור במשפחה, הוא באזור ה-35, 36. אחיו הקטן לעומתו רק בן 27, אבל כולם מתייעצים איתו קודם.",
    },
    {
        "id": "ex_04",
        "bucket": "spoken_units",
        "source": "spoken-exemplar",
        "episode_title": "שיחה חופשית · מרחק מוחשי",
        "hit_text": "פותח קופסה 20 מטר ממנו",
        "context_window": "תחשוב על מישהו שרגיש לריח חזק, אפילו אם אני פותח אריזה כזאת 20 מטר ממנו בחדר פתוח זה מיד משפיע עליו, כאילו זה בלתי נתפס.",
    },
    {
        "id": "ex_05",
        "bucket": "prefixed_numbers",
        "source": "spoken-exemplar",
        "episode_title": "הסבר היסטורי · תיקון חישוב תוך כדי דיבור",
        "hit_text": "מ-1919 עד 1933",
        "context_window": "למה כולם זוכרים את זה בתור תקופה של 20 שנה? רגע, זה בעצם לא 20 שנה, המסגרת הזאת התקיימה מ-1919 עד 1933, בקושי 14 שנים.",
    },
    {
        "id": "ex_06",
        "bucket": "structured_decimals_pct",
        "source": "spoken-exemplar",
        "episode_title": "פודקאסט כלכלה · שחיקה ותקציב",
        "hit_text": "הורדה של היקף המשרות ל-60%",
        "context_window": "בפועל אין שום צעד דרמטי חוץ מהמלצה אחת שמדברת על הורדת נפח הפעילות במשרדים ל-60%. ספוילר, בשטח כמעט כולם ממשיכים להגיע כרגיל.",
    },
    {
        "id": "ex_07",
        "bucket": "multi_digit_counts",
        "source": "spoken-exemplar",
        "episode_title": "יזמות ומכירות · צמיחה חודשית",
        "hit_text": "היו סוגרים 20 אלף דולר בחודש",
        "context_window": "כשאני הצטרפתי לצוות הם בקושי היו סוגרים 25,000 דולר מכירות בחודש, ותוך פחות משנה עם 12 לקוחות קבועים זה כבר קפץ לגמרי.",
    },
    {
        "id": "ex_08",
        "bucket": "spoken_units",
        "source": "spoken-exemplar",
        "episode_title": "מחקר שדה · מרכזים ומשתתפים",
        "hit_text": "אספנו נתונים מ-18 מרכזים",
        "context_window": "את המשתתפים לבדיקה לקחנו בעצם מ-18 מרכזים שונים ברחבי הארץ, ובסך הכול השתתפו שם איזה 450 חניכים לאורך הסמסטר.",
    },
)


def cookie_file(data_root: Path) -> Path:
    return Path(data_root) / "ivrit_cookie.txt"


def load_ivrit_cookie(data_root: Path) -> str:
    env_cookie = os.environ.get("IVRIT_AI_COOKIE", "").strip()
    if env_cookie:
        return env_cookie
    path = cookie_file(data_root)
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


def save_ivrit_cookie(data_root: Path, raw_cookie: str) -> dict[str, Any]:
    cleaned = raw_cookie.strip()
    # Allow pasting a full `-b '...'` line or `cookie: ...` header as a convenience
    if cleaned.lower().startswith("cookie:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    cleaned = cleaned.strip("'\"")
    path = cookie_file(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cleaned:
        if path.exists():
            path.unlink()
        return {"configured": False, "length": 0}
    path.write_text(cleaned, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return {"configured": True, "length": len(cleaned)}


def _ivrit_get_json(url: str, cookie: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "accept": "application/json",
            "accept-language": "en-US,en;q=0.9,he;q=0.8",
            "cookie": cookie,
            "referer": "https://explore.ivrit.ai/",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
            ),
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _clean_text(raw: str) -> str:
    collapsed = re.sub(r"\s+", " ", raw).strip()
    return _SENSITIVE.sub("[מזהה מוסתר]", collapsed)


def mine_spoken_contexts(
    data_root: Path,
    *,
    target_snippets: int = 12,
    seed: int = 42,
    radius: int = 4,
    target_archetypes: list[str] | None = None,
) -> dict[str, Any]:
    """Mine spoken context windows around numeric expressions from explore.ivrit.ai and configured text_file sources."""
    target_snippets = max(4, min(40, target_snippets))
    rng = random.Random(f"ivrit-mine:{seed}")
    cookie = load_ivrit_cookie(data_root)
    text_sources = [
        s for s in load_corpus_sources(data_root, enabled_only=True) if s.get("type") == "text_file"
    ]

    if not cookie and not text_sources:
        picks = list(FALLBACK_SPOKEN_EXEMPLARS)
        rng.shuffle(picks)
        return {
            "mode": "exemplar_fallback",
            "warning": "לא הוגדרה עוגיית explore.ivrit.ai או מקור טקסט; נעשה שימוש בדוגמאות קצב דיבור מובנות.",
            "snippets": picks[:target_snippets],
        }

    snippets: list[dict[str, Any]] = []
    seen_windows: set[str] = set()
    errors: list[str] = []
    ivrit_count = 0
    text_source_count = 0

    def _collect_from_text_source(
        src: dict[str, Any],
        bucket_name: str,
        mode: str,
        query: str,
        limit: int,
        *,
        target_archetype: str | None = None,
    ) -> int:
        nonlocal text_source_count
        search_mode = "fixed" if mode == "exact" else "regex"
        fetch_limit = max(6, min(30, limit * 4))
        # Vary starting line on large remote text corpora so successive seeded batches
        # sample fresh spoken contexts instead of repeating the top lines of the file.
        start_line = rng.randint(1, 500_000) if src.get("location") == "ssh" else 1
        try:
            res = search_text_file_source(
                src,
                query=query,
                mode=search_mode,
                limit=fetch_limit,
                context_lines=1,
                start_line=start_line,
                timeout=10.0,
            )
            if not res.get("matches") and start_line > 1:
                res = search_text_file_source(
                    src,
                    query=query,
                    mode=search_mode,
                    limit=fetch_limit,
                    context_lines=1,
                    start_line=1,
                    timeout=10.0,
                )
        except (CorpusSourceError, ValueError) as exc:
            errors.append(f"{src['id']}/{bucket_name}: {exc}")
            return 0

        matches = list(res.get("matches") or [])
        if not matches:
            return 0
        digit_matches = [m for m in matches if _HAS_DIGIT.search(m.get("text", ""))]
        pool = digit_matches or matches
        rng.shuffle(pool)

        collected = 0
        for m in pool:
            if collected >= limit or len(snippets) >= target_snippets:
                break
            window = m.get("context_window") or m.get("text") or ""
            if len(window) < 25 or window in seen_windows:
                continue
            seen_windows.add(window)
            entry: dict[str, Any] = {
                "id": f"src_{src['id']}_{m['line_number']}",
                "bucket": bucket_name,
                "source": src["name"],
                "source_id": src["id"],
                "source_type": src["type"],
                "episode_title": f"שורה {m['line_number']} ({src['location']})",
                "line_number": m["line_number"],
                "hit_text": m.get("text", ""),
                "context_window": window[:700],
            }
            if target_archetype:
                entry["target_archetype"] = target_archetype
            snippets.append(entry)
            collected += 1
            text_source_count += 1
        return collected

    if cookie:
        chosen_sources = list(PODCAST_SOURCES)
        rng.shuffle(chosen_sources)
        source_qs = "&".join(f"source={urllib.parse.quote_plus(src)}" for src in chosen_sources[:9])
        ivrit_cap = (
            max(2, target_snippets - max(2, round(target_snippets * 0.35)))
            if text_sources
            else target_snippets
        )

        def _collect_from_query(
            bucket_name: str,
            mode: str,
            query: str,
            limit: int,
            *,
            target_archetype: str | None = None,
        ) -> int:
            nonlocal ivrit_count
            page = rng.randint(1, 5) if target_archetype else rng.randint(1, 8)
            search_seed = rng.randint(100_000, 999_999_999)
            url = (
                f"https://explore.ivrit.ai/api/search?"
                f"q={urllib.parse.quote(query)}&mode={mode}&{source_qs}"
                f"&page={page}&per_page=15&shuffle=true&seed={search_seed}"
            )
            try:
                res = _ivrit_get_json(url, cookie)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                errors.append(f"{bucket_name}: {exc}")
                return 0

            episodes = list(res.get("episodes") or [])
            if not episodes and page > 1:
                # Retry page 1 for rarer targeted queries so low-volume topics still return hits.
                url_p1 = (
                    f"https://explore.ivrit.ai/api/search?"
                    f"q={urllib.parse.quote(query)}&mode={mode}&{source_qs}"
                    f"&page=1&per_page=15&shuffle=true&seed={search_seed}"
                )
                try:
                    res = _ivrit_get_json(url_p1, cookie)
                    episodes = list(res.get("episodes") or [])
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
                    return 0

            rng.shuffle(episodes)
            collected = 0
            for ep in episodes:
                if collected >= limit or ivrit_count >= ivrit_cap or len(snippets) >= target_snippets:
                    break
                ep_idx = ep.get("episode_idx")
                if ep_idx is None:
                    continue
                hits = [
                    h for h in (ep.get("hits") or [])
                    if h.get("segment_idx", 0) > 22 and not _INTRO_NOISE.search(h.get("text", ""))
                ]
                if not hits:
                    continue
                digit_hits = [h for h in hits if _HAS_DIGIT.search(h.get("text", ""))]
                hit = rng.choice(digit_hits or hits)
                seg_idx = hit["segment_idx"]
                ctx_url = f"https://explore.ivrit.ai/api/episodes/{ep_idx}/segments?center={seg_idx}&radius={radius}"
                try:
                    ctx_raw = _ivrit_get_json(ctx_url, cookie)
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                    errors.append(f"ep {ep_idx}: {exc}")
                    continue
                segs = ctx_raw if isinstance(ctx_raw, list) else ctx_raw.get("segments", [])
                window = _clean_text(" ".join(s.get("text", "").strip() for s in segs if s.get("text")))
                if len(window) < 35 or window in seen_windows:
                    continue
                seen_windows.add(window)
                entry: dict[str, Any] = {
                    "id": f"ivrit_{ep_idx}_{seg_idx}",
                    "bucket": bucket_name,
                    "source": ep.get("source", "ivrit.ai"),
                    "episode_title": ep.get("title", ""),
                    "episode_idx": ep_idx,
                    "segment_idx": seg_idx,
                    "hit_text": _clean_text(hit.get("text", "")),
                    "context_window": window[:700],
                }
                if target_archetype:
                    entry["target_archetype"] = target_archetype
                snippets.append(entry)
                collected += 1
                ivrit_count += 1
            return collected

        # Pass 1: Up to ~50% targeted queries for uncovered numeric usages (leaving ~50% for rich general numeric speech).
        if target_archetypes:
            targeted_ids = [aid for aid in target_archetypes if aid in ARCHETYPE_MINING_QUERIES]
            rng.shuffle(targeted_ids)
            targeted_cap = max(2, ivrit_cap // 2)
            for aid in targeted_ids:
                if ivrit_count >= targeted_cap or len(snippets) >= target_snippets:
                    break
                mode, query = ARCHETYPE_MINING_QUERIES[aid]
                _collect_from_query(f"tier1:{aid}", mode, query, 1, target_archetype=aid)

        # Pass 2: General stratified numeric buckets (always runs to ensure rich multi-number natural spoken cadence).
        if ivrit_count < ivrit_cap and len(snippets) < target_snippets:
            remaining = min(ivrit_cap - ivrit_count, target_snippets - len(snippets))
            per_bucket = max(2, (remaining + len(REGEX_BUCKETS) - 1) // len(REGEX_BUCKETS))
            for bucket_name, pattern in REGEX_BUCKETS:
                if ivrit_count >= ivrit_cap or len(snippets) >= target_snippets:
                    break
                _collect_from_query(bucket_name, "regex", pattern, per_bucket)

    # Pass 3: Sample configured enabled text_file sources (local or remote SSH) for additional spoken inspiration.
    if text_sources and len(snippets) < target_snippets:
        shuffled_sources = list(text_sources)
        rng.shuffle(shuffled_sources)
        text_rem = target_snippets - len(snippets)
        text_targeted_cap = text_source_count + max(1, text_rem // 2)
        if target_archetypes:
            targeted_ids = [aid for aid in target_archetypes if aid in ARCHETYPE_MINING_QUERIES]
            rng.shuffle(targeted_ids)
            for idx, aid in enumerate(targeted_ids):
                if text_source_count >= text_targeted_cap or len(snippets) >= target_snippets:
                    break
                src = shuffled_sources[idx % len(shuffled_sources)]
                mode, query = ARCHETYPE_MINING_QUERIES[aid]
                _collect_from_text_source(src, f"tier1:{aid}", mode, query, 1, target_archetype=aid)

        if len(snippets) < target_snippets:
            buckets = list(REGEX_BUCKETS)
            rng.shuffle(buckets)
            for idx, (bucket_name, pattern) in enumerate(buckets):
                if len(snippets) >= target_snippets:
                    break
                src = shuffled_sources[idx % len(shuffled_sources)]
                rem = target_snippets - len(snippets)
                _collect_from_text_source(src, bucket_name, "regex", pattern, max(1, min(3, rem)))

    if not snippets:
        picks = list(FALLBACK_SPOKEN_EXEMPLARS)
        rng.shuffle(picks)
        return {
            "mode": "exemplar_fallback",
            "warning": (
                "פנייה למקורות הקורפוס לא החזירה קטעים: "
                + ("; ".join(errors[:2]) if errors else "אין תוצאות")
            ),
            "snippets": picks[:target_snippets],
        }

    if ivrit_count > 0 and text_source_count > 0:
        mine_mode = "live_mixed"
    elif text_source_count > 0:
        mine_mode = "live_text_sources"
    else:
        mine_mode = "live_ivrit_ai"

    return {
        "mode": mine_mode,
        "warning": "; ".join(errors[:2]) if errors and not (ivrit_count and text_source_count) else "",
        "snippets": snippets,
    }
