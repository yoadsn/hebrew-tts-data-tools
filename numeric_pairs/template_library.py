"""Curated MicroTemplate library (Official in-repo + Local overlay) and mixed 80/20 synthesizer.

Architecture (Option 1 — Official in-repo + Local workspace overlay):
- Official library (tracked in git): `numeric_pairs/micro_template_library.json`
  Holds clean, validated, deliberately published MicroTemplate specs (zero raw
  transcripts, zero PII, zero local credentials). Available out of the box on
  any fresh `git clone`.
- Local library (outside git): `~/.local/share/hebrew-numeric-pairs/micro_template_library.json`
  Automatically receives newly finalized Neon batches so you can inspect, test,
  enable/disable, and curate locally before publishing selected templates to the
  official in-repo file.

At dataset generation time (`python -m numeric_pairs` or `ReviewStore.create_run`),
enabled templates from the Official library + Local overlay are merged and blended
with Tier-1 simple templates (default 80% MicroTemplates / 20% Tier-1, configurable).
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import random
from threading import Lock
from typing import Any

from .catalog import ARCHETYPES, BY_ID
from .core import generate as generate_tier1, validate_pair
from .micro_templates import (
    generate_from_templates,
    render_micro_template,
    sample_micro_slots,
    template_covered_usages,
    validate_and_stress_template,
)

DEFAULT_MICRO_TEMPLATE_RATIO = 0.8
LIBRARY_SCHEMA = "micro-template-library-v1"
LIBRARY_ENV = "NUMERIC_PAIRS_TEMPLATE_LIBRARY"
OFFICIAL_LIBRARY_ENV = "NUMERIC_PAIRS_OFFICIAL_LIBRARY"

_library_lock = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_data_root() -> Path:
    return Path(os.environ.get("NUMERIC_PAIRS_DATA_DIR", Path.home() / ".local/share/hebrew-numeric-pairs"))


def official_library_file(*, explicit_path: Path | None = None) -> Path:
    """Resolve the official in-repo `numeric_pairs/micro_template_library.json` path (lazy)."""
    if explicit_path is not None:
        return Path(explicit_path)
    env_override = os.environ.get(OFFICIAL_LIBRARY_ENV, "").strip()
    if env_override:
        return Path(env_override)
    return Path(__file__).with_name("micro_template_library.json")


def library_file(data_root: Path | None = None, *, explicit_path: Path | None = None) -> Path:
    """Resolve the local workspace `micro_template_library.json` path without creating directories."""
    if explicit_path is not None:
        return Path(explicit_path)
    env_override = os.environ.get(LIBRARY_ENV, "").strip()
    if env_override:
        return Path(env_override)
    root = Path(data_root) if data_root is not None else default_data_root()
    return root / "micro_template_library.json"


def _spec_digest(spec: dict[str, Any]) -> str:
    return sha256(json.dumps(spec, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _library_fingerprint(entries: list[dict[str, Any]]) -> str:
    enabled_specs = [
        {"id": e["id"], "spec": e["spec"]}
        for e in sorted(entries, key=lambda x: x["id"])
        if e.get("enabled", True)
    ]
    if not enabled_specs:
        return "empty"
    return sha256(json.dumps(enabled_specs, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _read_raw_library(path: Path) -> dict[str, Any]:
    """Read library JSON lazily; returns an empty payload if the file does not exist."""
    if not path.is_file():
        return {"schema": LIBRARY_SCHEMA, "updated_at": None, "templates": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema": LIBRARY_SCHEMA, "updated_at": None, "templates": []}
    if not isinstance(data, dict) or not isinstance(data.get("templates"), list):
        return {"schema": LIBRARY_SCHEMA, "updated_at": None, "templates": []}
    return data


def _write_raw_library(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["schema"] = LIBRARY_SCHEMA
    data["updated_at"] = _now_iso()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _preview_pair(spec: dict[str, Any]) -> dict[str, str]:
    rng = random.Random(f"lib-preview:{spec['id']}")
    vals = sample_micro_slots(spec, rng, mode="stress", variant_idx=0)
    pair = render_micro_template(spec, vals, seed=42, index=0)
    return {"digits": pair["digits"], "cardinal": pair["cardinal"]}


def _build_entry(
    spec: dict[str, Any],
    *,
    source_batch_id: str = "manual",
    enabled: bool = True,
    existing_added_at: str | None = None,
) -> dict[str, Any]:
    samples = validate_and_stress_template(spec, stress_count=3, seed=42)
    tid = str(spec["id"]).strip()
    aid = spec["archetype_id"]
    num_nodes = [n for n in (spec.get("nodes") or []) if isinstance(n, dict) and "num" in n]
    return {
        "id": tid,
        "archetype_id": aid,
        "covered_usages": template_covered_usages(spec),
        "category": BY_ID[aid].category,
        "track": spec.get("track", "corpus_inspired"),
        "source_batch_id": source_batch_id,
        "inspiration_summary": spec.get("inspiration_summary", ""),
        "num_count": len(num_nodes),
        "enabled": bool(enabled),
        "added_at": existing_added_at or _now_iso(),
        "preview": {"digits": samples[0]["digits"], "cardinal": samples[0]["cardinal"]},
        "spec": spec,
    }


def _merge_official_and_local(
    official_entries: list[dict[str, Any]],
    local_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge Official (in-repo) base templates with Local workspace overlay."""
    off_by_id: dict[str, dict[str, Any]] = {
        e["id"]: e for e in official_entries if isinstance(e, dict) and e.get("id") and isinstance(e.get("spec"), dict)
    }
    loc_by_id: dict[str, dict[str, Any]] = {
        e["id"]: e for e in local_entries if isinstance(e, dict) and e.get("id") and isinstance(e.get("spec"), dict)
    }

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Keep local ordering first (newest / active workspace), then official-only entries.
    for e in local_entries:
        tid = e.get("id")
        if not tid or tid in seen or not isinstance(e.get("spec"), dict):
            continue
        seen.add(tid)
        off = off_by_id.get(tid)
        if off is None:
            publish_status = "unpublished"
            source_scope = "local"
            published = False
            published_at = None
        else:
            same_spec = _spec_digest(e["spec"]) == _spec_digest(off["spec"])
            publish_status = "published" if same_spec else "modified"
            source_scope = "both"
            published = same_spec
            published_at = off.get("published_at") or off.get("added_at")
        merged.append(
            {
                **e,
                "published": published,
                "publish_status": publish_status,
                "source_scope": source_scope,
                "published_at": published_at,
            }
        )

    for e in official_entries:
        tid = e.get("id")
        if not tid or tid in seen or not isinstance(e.get("spec"), dict):
            continue
        seen.add(tid)
        merged.append(
            {
                **e,
                "enabled": bool(e.get("enabled", True)),
                "published": True,
                "publish_status": "published",
                "source_scope": "official",
                "published_at": e.get("published_at") or e.get("added_at"),
            }
        )

    return merged


def load_library_entries(
    data_root: Path | None = None,
    *,
    explicit_path: Path | None = None,
    official_path: Path | None = None,
    include_official: bool = True,
    enabled_only: bool = False,
) -> list[dict[str, Any]]:
    """Return merged library entries lazily (creates no files or directories on read).

    If `explicit_path` is provided, loads ONLY that single file (for deterministic CLI `--library`).
    Otherwise merges Official (`numeric_pairs/micro_template_library.json`, when `include_official=True`)
    with Local (`<data_root>/micro_template_library.json`).
    """
    if explicit_path is not None:
        raw = _read_raw_library(Path(explicit_path))
        entries = [
            {
                **e,
                "published": True,
                "publish_status": "published",
                "source_scope": "explicit",
                "published_at": e.get("published_at") or e.get("added_at"),
            }
            for e in raw.get("templates", [])
            if isinstance(e, dict) and isinstance(e.get("spec"), dict)
        ]
    else:
        local_raw = _read_raw_library(library_file(data_root))
        local_entries = [
            e for e in local_raw.get("templates", []) if isinstance(e, dict) and isinstance(e.get("spec"), dict)
        ]
        if include_official:
            off_file = official_library_file(explicit_path=official_path)
            off_raw = _read_raw_library(off_file)
            off_entries = [
                e for e in off_raw.get("templates", []) if isinstance(e, dict) and isinstance(e.get("spec"), dict)
            ]
            entries = _merge_official_and_local(off_entries, local_entries)
        else:
            entries = _merge_official_and_local([], local_entries)

    if enabled_only:
        entries = [e for e in entries if e.get("enabled", True)]
    return entries


def library_summary(
    data_root: Path | None = None,
    *,
    explicit_path: Path | None = None,
    official_path: Path | None = None,
    include_official: bool = True,
    include_templates: bool = True,
) -> dict[str, Any]:
    """Summarize the merged Official + Local MicroTemplate library (strictly read-only/lazy)."""
    local_path = library_file(data_root, explicit_path=explicit_path)
    off_file = official_library_file(explicit_path=official_path) if (include_official and explicit_path is None) else None

    entries = load_library_entries(
        data_root,
        explicit_path=explicit_path,
        official_path=official_path,
        include_official=include_official,
        enabled_only=False,
    )
    enabled_entries = [e for e in entries if e.get("enabled", True)]
    published_entries = [e for e in entries if e.get("publish_status") == "published"]
    unpublished_entries = [e for e in entries if e.get("publish_status") in ("unpublished", "modified")]

    local_raw = _read_raw_library(local_path)
    off_raw = _read_raw_library(off_file) if off_file is not None else {"updated_at": None, "templates": []}

    covered_usages: set[str] = set()
    by_category: dict[str, int] = {}
    batches_map: dict[str, dict[str, Any]] = {}

    for e in entries:
        bid = str(e.get("source_batch_id") or "manual")
        b_info = batches_map.setdefault(
            bid,
            {
                "batch_id": bid,
                "total": 0,
                "enabled": 0,
                "published": 0,
                "unpublished": 0,
                "multi_num": 0,
                "added_at": e.get("added_at", ""),
            },
        )
        b_info["total"] += 1
        if e.get("enabled", True):
            b_info["enabled"] += 1
            for u in e.get("covered_usages") or [e.get("archetype_id")]:
                if u in BY_ID:
                    covered_usages.add(u)
            cat = e.get("category") or (BY_ID[e["archetype_id"]].category if e.get("archetype_id") in BY_ID else "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1
        if e.get("publish_status") == "published":
            b_info["published"] += 1
        else:
            b_info["unpublished"] += 1
        num_count = e.get("num_count")
        if num_count is None:
            num_count = len([n for n in (e["spec"].get("nodes") or []) if isinstance(n, dict) and "num" in n])
        if num_count >= 2:
            b_info["multi_num"] += 1

    batches_list = sorted(batches_map.values(), key=lambda x: x["added_at"], reverse=True)
    result: dict[str, Any] = {
        "schema": LIBRARY_SCHEMA,
        "path": str(local_path),
        "exists": local_path.is_file() or bool(off_file and off_file.is_file()),
        "local_exists": local_path.is_file(),
        "official_path": str(off_file) if off_file is not None else None,
        "official_exists": bool(off_file and off_file.is_file()),
        "official_templates": len(off_raw.get("templates", [])) if off_file is not None else 0,
        "published_templates": len(published_entries),
        "unpublished_templates": len(unpublished_entries),
        "unpublished_enabled_templates": sum(1 for e in unpublished_entries if e.get("enabled", True)),
        "updated_at": local_raw.get("updated_at") or off_raw.get("updated_at"),
        "official_updated_at": off_raw.get("updated_at"),
        "fingerprint": _library_fingerprint(entries),
        "total_templates": len(entries),
        "enabled_templates": len(enabled_entries),
        "covered_usages_count": len(covered_usages),
        "total_archetypes": len(ARCHETYPES),
        "covered_usages": sorted(covered_usages),
        "by_category": dict(sorted(by_category.items())),
        "batches": batches_list,
    }
    if include_templates:
        result["templates"] = [
            {
                "id": e["id"],
                "archetype_id": e["archetype_id"],
                "covered_usages": e.get("covered_usages") or template_covered_usages(e["spec"]),
                "category": e.get("category") or BY_ID[e["archetype_id"]].category,
                "track": e.get("track", "corpus_inspired"),
                "source_batch_id": e.get("source_batch_id", "manual"),
                "inspiration_summary": e.get("inspiration_summary", ""),
                "num_count": e.get("num_count")
                if e.get("num_count") is not None
                else len([n for n in (e["spec"].get("nodes") or []) if isinstance(n, dict) and "num" in n]),
                "enabled": bool(e.get("enabled", True)),
                "published": bool(e.get("published", False)),
                "publish_status": e.get("publish_status", "unpublished"),
                "source_scope": e.get("source_scope", "local"),
                "added_at": e.get("added_at", ""),
                "published_at": e.get("published_at"),
                "preview": e.get("preview") or _preview_pair(e["spec"]),
            }
            for e in entries
        ]
    return result


def promote_specs_to_library(
    data_root: Path | None,
    specs: list[dict[str, Any]],
    *,
    source_batch_id: str = "manual",
    enabled: bool = True,
    explicit_path: Path | None = None,
    preserve_existing_enabled: bool = True,
    official_path: Path | None = None,
    include_official: bool = False,
) -> dict[str, Any]:
    """Validate and upsert MicroTemplate specs into the local `micro_template_library.json`."""
    path = library_file(data_root, explicit_path=explicit_path)
    added = 0
    updated = 0
    errors: list[dict[str, str]] = []

    with _library_lock:
        raw = _read_raw_library(path)
        by_id: dict[str, dict[str, Any]] = {
            e["id"]: e for e in raw.get("templates", []) if isinstance(e, dict) and e.get("id")
        }
        order: list[str] = list(by_id.keys())

        for spec in specs:
            tid = str(spec.get("id", "")).strip() if isinstance(spec, dict) else ""
            try:
                prev = by_id.get(tid)
                eff_enabled = bool(prev.get("enabled", enabled)) if (prev is not None and preserve_existing_enabled) else enabled
                entry = _build_entry(
                    spec,
                    source_batch_id=source_batch_id,
                    enabled=eff_enabled,
                    existing_added_at=prev.get("added_at") if prev else None,
                )
            except Exception as exc:
                errors.append({"template_id": tid or "<unknown>", "error": str(exc)})
                continue

            if entry["id"] in by_id:
                updated += 1
            else:
                added += 1
                order.append(entry["id"])
            by_id[entry["id"]] = entry

        raw["templates"] = [by_id[tid] for tid in order]
        _write_raw_library(path, raw)

    return {
        "added": added,
        "updated": updated,
        "errors": errors,
        "summary": library_summary(
            data_root,
            explicit_path=explicit_path,
            official_path=official_path,
            include_official=include_official,
            include_templates=False,
        ),
    }


def publish_templates_to_repo(
    data_root: Path | None,
    *,
    template_ids: list[str] | None = None,
    batch_ids: list[str] | None = None,
    include_disabled: bool = False,
    official_path: Path | None = None,
) -> dict[str, Any]:
    """Publish selected (or all unpublished) local MicroTemplates into the official in-repo JSON file.

    - Re-validates every selected spec against the current deterministic engine.
    - Stores templates sorted by `id` with fresh previews for clean, reproducible git diffs.
    - Never writes raw transcripts, cookies, or local host config to the repo file.
    """
    local_path = library_file(data_root)
    off_file = official_library_file(explicit_path=official_path)

    with _library_lock:
        local_raw = _read_raw_library(local_path)
        off_raw = _read_raw_library(off_file)

        local_entries = [
            e for e in local_raw.get("templates", []) if isinstance(e, dict) and e.get("id") and isinstance(e.get("spec"), dict)
        ]
        off_by_id: dict[str, dict[str, Any]] = {
            e["id"]: e for e in off_raw.get("templates", []) if isinstance(e, dict) and e.get("id") and isinstance(e.get("spec"), dict)
        }

        if template_ids is not None:
            requested = [str(tid).strip() for tid in template_ids if str(tid).strip()]
            requested_set = set(requested)
            candidates = [e for e in local_entries if e["id"] in requested_set]
            missing = sorted(requested_set - {e["id"] for e in candidates})
        else:
            batch_filter = set(batch_ids) if batch_ids else None
            candidates = []
            for e in local_entries:
                if batch_filter is not None and e.get("source_batch_id") not in batch_filter:
                    continue
                if not include_disabled and not e.get("enabled", True):
                    continue
                off = off_by_id.get(e["id"])
                if off is not None and _spec_digest(e["spec"]) == _spec_digest(off["spec"]):
                    continue
                candidates.append(e)
            missing = []

        added = 0
        updated = 0
        published_ids: list[str] = []
        errors: list[dict[str, str]] = []
        now = _now_iso()

        for entry in candidates:
            tid = entry["id"]
            spec = entry["spec"]
            try:
                validated = _build_entry(
                    spec,
                    source_batch_id=str(entry.get("source_batch_id") or "manual"),
                    enabled=True,
                    existing_added_at=entry.get("added_at"),
                )
            except Exception as exc:
                errors.append({"template_id": tid, "error": str(exc)})
                continue

            official_entry = {
                "id": validated["id"],
                "archetype_id": validated["archetype_id"],
                "covered_usages": validated["covered_usages"],
                "category": validated["category"],
                "track": validated["track"],
                "source_batch_id": validated["source_batch_id"],
                "inspiration_summary": validated["inspiration_summary"],
                "num_count": validated["num_count"],
                "published_at": now,
                "preview": validated["preview"],
                "spec": validated["spec"],
            }
            if tid in off_by_id:
                updated += 1
            else:
                added += 1
            off_by_id[tid] = official_entry
            published_ids.append(tid)

            # Ensure published templates are also marked enabled in local overlay so status is consistent.
            entry["enabled"] = True

        if published_ids or not off_file.is_file():
            off_raw["templates"] = [off_by_id[tid] for tid in sorted(off_by_id)]
            _write_raw_library(off_file, off_raw)
        if published_ids and local_path.is_file():
            _write_raw_library(local_path, local_raw)

    return {
        "published_count": len(published_ids),
        "added": added,
        "updated": updated,
        "published_ids": published_ids,
        "missing_ids": missing,
        "errors": errors,
        "official_path": str(off_file),
        "total_official_templates": len(off_by_id),
        "summary": library_summary(
            data_root,
            official_path=off_file,
            include_official=True,
            include_templates=False,
        ),
    }


def unpublish_template_from_repo(
    data_root: Path | None,
    template_id: str,
    *,
    official_path: Path | None = None,
) -> bool:
    """Remove a single template from the official in-repo JSON file."""
    off_file = official_library_file(explicit_path=official_path)
    with _library_lock:
        if not off_file.is_file():
            return False
        raw = _read_raw_library(off_file)
        before = len(raw.get("templates", []))
        raw["templates"] = [e for e in raw.get("templates", []) if e.get("id") != template_id]
        if len(raw["templates"]) == before:
            return False
        _write_raw_library(off_file, raw)
    return True


def sync_library_from_batches(
    data_root: Path | None = None,
    *,
    batch_ids: list[str] | None = None,
    only_multi_number: bool = False,
    disable_single_number_batches: bool = False,
    explicit_path: Path | None = None,
    official_path: Path | None = None,
    include_official: bool = True,
) -> dict[str, Any]:
    """Import approved MicroTemplates from saved pipeline batches into the local library."""
    root = Path(data_root) if data_root is not None else default_data_root()
    batches_dir = root / "pipeline" / "batches"
    if not batches_dir.is_dir():
        return {
            "scanned_batches": 0,
            "added": 0,
            "updated": 0,
            "errors": [],
            "summary": library_summary(
                root,
                explicit_path=explicit_path,
                official_path=official_path,
                include_official=include_official,
                include_templates=False,
            ),
        }

    if batch_ids:
        selected = set(batch_ids)
        paths = [
            p for p in sorted(batches_dir.glob("b_*.json"), key=lambda x: x.stat().st_mtime)
            if p.stem in selected
        ]
    else:
        paths = sorted(batches_dir.glob("b_*.json"), key=lambda x: x.stat().st_mtime)

    total_added = 0
    total_updated = 0
    all_errors: list[dict[str, str]] = []
    scanned = 0

    for p in paths:
        try:
            batch = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        bid = batch.get("id") or p.stem
        approved = [
            t["spec"]
            for t in (batch.get("templates") or [])
            if isinstance(t, dict)
            and (t.get("verdict") or {}).get("approved")
            and isinstance(t.get("spec"), dict)
        ]
        if not approved:
            continue
        scanned += 1
        multi_ratio = (
            sum(
                1
                for spec in approved
                if len([n for n in (spec.get("nodes") or []) if isinstance(n, dict) and "num" in n]) >= 2
            )
            / len(approved)
        )
        if only_multi_number:
            approved = [
                spec
                for spec in approved
                if len([n for n in (spec.get("nodes") or []) if isinstance(n, dict) and "num" in n]) >= 2
            ]
            if not approved:
                continue

        batch_enabled = not (disable_single_number_batches and multi_ratio < 0.5)
        res = promote_specs_to_library(
            root,
            approved,
            source_batch_id=bid,
            enabled=batch_enabled,
            explicit_path=explicit_path,
            preserve_existing_enabled=True,
            official_path=official_path,
            include_official=include_official,
        )
        total_added += res["added"]
        total_updated += res["updated"]
        all_errors.extend(res["errors"])

    return {
        "scanned_batches": scanned,
        "added": total_added,
        "updated": total_updated,
        "errors": all_errors,
        "summary": library_summary(
            root,
            explicit_path=explicit_path,
            official_path=official_path,
            include_official=include_official,
            include_templates=False,
        ),
    }


def set_template_enabled(
    data_root: Path | None,
    template_id: str,
    enabled: bool,
    *,
    explicit_path: Path | None = None,
    official_path: Path | None = None,
    include_official: bool = True,
) -> dict[str, Any] | None:
    """Toggle `enabled` in the local overlay (materializing an official-only entry locally if needed)."""
    path = library_file(data_root, explicit_path=explicit_path)
    with _library_lock:
        raw = _read_raw_library(path)
        found = None
        for entry in raw.get("templates", []):
            if entry.get("id") == template_id:
                entry["enabled"] = bool(enabled)
                found = entry
                break
        if found is None and include_official and explicit_path is None:
            off_raw = _read_raw_library(official_library_file(explicit_path=official_path))
            for entry in off_raw.get("templates", []):
                if entry.get("id") == template_id:
                    cloned = {**entry, "enabled": bool(enabled)}
                    raw.setdefault("templates", []).append(cloned)
                    found = cloned
                    break
        if found is None:
            return None
        _write_raw_library(path, raw)
    return found


def set_batch_enabled(
    data_root: Path | None,
    batch_id: str,
    enabled: bool,
    *,
    explicit_path: Path | None = None,
    official_path: Path | None = None,
    include_official: bool = True,
) -> int:
    path = library_file(data_root, explicit_path=explicit_path)
    changed = 0
    with _library_lock:
        raw = _read_raw_library(path)
        local_ids = {e.get("id") for e in raw.get("templates", []) if isinstance(e, dict)}
        for entry in raw.get("templates", []):
            if entry.get("source_batch_id") == batch_id:
                entry["enabled"] = bool(enabled)
                changed += 1
        if include_official and explicit_path is None:
            off_raw = _read_raw_library(official_library_file(explicit_path=official_path))
            for entry in off_raw.get("templates", []):
                if entry.get("source_batch_id") == batch_id and entry.get("id") not in local_ids:
                    raw.setdefault("templates", []).append({**entry, "enabled": bool(enabled)})
                    changed += 1
        if changed > 0:
            _write_raw_library(path, raw)
    return changed


def delete_template(
    data_root: Path | None,
    template_id: str,
    *,
    explicit_path: Path | None = None,
) -> bool:
    path = library_file(data_root, explicit_path=explicit_path)
    with _library_lock:
        raw = _read_raw_library(path)
        before = len(raw.get("templates", []))
        raw["templates"] = [e for e in raw.get("templates", []) if e.get("id") != template_id]
        if len(raw["templates"]) == before:
            return False
        _write_raw_library(path, raw)
    return True


def _eligible_micro_specs(
    entries: list[dict[str, Any]],
    archetypes: list[str] | None,
) -> list[dict[str, Any]]:
    allowed = set(archetypes) if archetypes is not None else None
    specs: list[dict[str, Any]] = []
    for entry in entries:
        if not entry.get("enabled", True):
            continue
        spec = entry.get("spec")
        if not isinstance(spec, dict):
            continue
        if allowed is not None:
            usages = set(entry.get("covered_usages") or template_covered_usages(spec))
            if not (usages & allowed):
                continue
        specs.append(spec)
    return specs


def generate_mixed_dataset(
    seed: int,
    count: int,
    *,
    micro_templates: list[dict[str, Any]] | None = None,
    micro_template_ratio: float = DEFAULT_MICRO_TEMPLATE_RATIO,
    archetypes: list[str] | None = None,
    address_lengths: tuple[int, ...] = (1, 2, 3),
    boundary_weight: float = 0.25,
    variant_weights: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Deterministically synthesize a mixed dataset of MicroTemplates + Tier-1 pairs.

    Default mix is 80% MicroTemplates / 20% Tier-1 (`micro_template_ratio=0.8`).
    When `micro_template_ratio == 0.0` or no eligible MicroTemplates exist for the
    requested archetypes, gracefully falls back to pure Tier-1 generation without
    mutating Tier-1 pair payloads.
    """
    if type(seed) is not int or type(count) is not int or not (1 <= count <= 100_000):
        raise ValueError("Seed must be an integer and count must be between 1 and 100,000")
    if isinstance(micro_template_ratio, bool) or not isinstance(micro_template_ratio, (int, float)):
        raise ValueError("micro_template_ratio must be a float between 0.0 and 1.0")
    ratio = float(micro_template_ratio)
    if not (0.0 <= ratio <= 1.0):
        raise ValueError("micro_template_ratio must be between 0.0 and 1.0")

    entries = list(micro_templates or [])
    eligible_specs = _eligible_micro_specs(entries, archetypes) if ratio > 0.0 else []
    fingerprint = _library_fingerprint(entries) if eligible_specs else "none"

    if not eligible_specs or ratio == 0.0:
        tier1_pairs = generate_tier1(
            seed,
            count,
            archetypes,
            address_lengths=address_lengths,
            boundary_weight=boundary_weight,
            variant_weights=variant_weights,
        )
        meta = {
            "requested_micro_template_ratio": ratio,
            "actual_micro_template_ratio": 0.0,
            "micro_template_count": 0,
            "tier1_count": len(tier1_pairs),
            "eligible_micro_templates": 0,
            "unique_micro_templates_used": 0,
            "library_fingerprint": fingerprint,
            "fallback_to_tier1": ratio > 0.0 and not eligible_specs,
        }
        return tier1_pairs, meta

    micro_target = count if ratio == 1.0 else round(count * ratio)
    tier1_target = count - micro_target

    micro_pairs: list[dict[str, Any]] = []
    if micro_target > 0:
        raw_micro = generate_from_templates(eligible_specs, micro_target, seed=seed)
        spec_usages = {s["id"]: template_covered_usages(s) for s in eligible_specs}
        for pair in raw_micro:
            enriched = {
                **pair,
                "source_tier": "micro_template",
                "covered_usages": spec_usages.get(pair["micro_template_id"], [pair["archetype_id"]]),
            }
            validate_pair(enriched)
            micro_pairs.append(enriched)

    tier1_pairs: list[dict[str, Any]] = []
    if tier1_target > 0:
        raw_t1 = generate_tier1(
            seed,
            tier1_target,
            archetypes,
            address_lengths=address_lengths,
            boundary_weight=boundary_weight,
            variant_weights=variant_weights,
        )
        for pair in raw_t1:
            enriched = {**pair, "source_tier": "tier1"}
            validate_pair(enriched)
            tier1_pairs.append(enriched)

    combined = micro_pairs + tier1_pairs
    if micro_pairs and tier1_pairs:
        rng = random.Random(f"mixed-order:{seed}:{count}:{ratio:.4f}:{fingerprint}")
        rng.shuffle(combined)
        for idx, pair in enumerate(combined):
            pair["index"] = idx

    unique_tpls = len({p["micro_template_id"] for p in micro_pairs if p.get("micro_template_id")})
    meta = {
        "requested_micro_template_ratio": ratio,
        "actual_micro_template_ratio": round(len(micro_pairs) / len(combined), 4),
        "micro_template_count": len(micro_pairs),
        "tier1_count": len(tier1_pairs),
        "eligible_micro_templates": len(eligible_specs),
        "unique_micro_templates_used": unique_tpls,
        "library_fingerprint": fingerprint,
        "fallback_to_tier1": False,
    }
    return combined, meta
