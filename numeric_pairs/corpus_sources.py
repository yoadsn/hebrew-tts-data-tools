"""Configurable external corpus sources (local or remote SSH text files).

Source definitions live outside the repository in the local data directory
(`corpus_sources.json`, or `NUMERIC_PAIRS_CORPUS_SOURCES` env override) so
hostnames, file paths, and private datasets never live in source code.
"""

from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from threading import Lock
from typing import Any

from .candidates import _SENSITIVE

_sources_lock = Lock()

VALID_SOURCE_TYPES = ("text_file",)
VALID_LOCATIONS = ("local", "ssh")
VALID_SEARCH_MODES = ("regex", "fixed", "ere")

_SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_SSH_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@:-]{0,127}$")
_GREP_LINE_RE = re.compile(r"^(\d+)([:-])(.*)$")


class CorpusSourceError(RuntimeError):
    """Raised when querying a configured corpus source fails (SSH, I/O, grep)."""


def sources_file(data_root: Path) -> Path:
    env_path = os.environ.get("NUMERIC_PAIRS_CORPUS_SOURCES", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return Path(data_root) / "corpus_sources.json"


def _clean_text(raw: str) -> str:
    collapsed = re.sub(r"\s+", " ", raw).strip()
    return _SENSITIVE.sub("[מזהה מוסתר]", collapsed)


def validate_source_spec(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a corpus source configuration entry."""
    if not isinstance(raw, dict):
        raise ValueError("Source config must be a JSON object")

    source_id = str(raw.get("id") or "").strip()
    if not _SOURCE_ID_RE.fullmatch(source_id):
        raise ValueError(
            "Source 'id' must be 1–48 lowercase ASCII letters, digits, '_' or '-' starting with a letter/digit"
        )

    name = str(raw.get("name") or source_id).strip()
    if not name or len(name) > 120:
        raise ValueError("Source 'name' must be 1–120 characters")

    source_type = str(raw.get("type") or "text_file").strip()
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(f"Unsupported source type {source_type!r}; expected one of {VALID_SOURCE_TYPES}")

    location = str(raw.get("location") or "").strip().lower()
    if not location:
        location = "ssh" if str(raw.get("ssh_host") or "").strip() else "local"
    if location not in VALID_LOCATIONS:
        raise ValueError(f"Unsupported location {location!r}; expected 'local' or 'ssh'")

    path = str(raw.get("path") or "").strip()
    if not path or len(path) > 500 or "\x00" in path or "\n" in path or "\r" in path:
        raise ValueError("Source 'path' must be a non-empty single-line path (<= 500 chars)")

    ssh_host = str(raw.get("ssh_host") or "").strip()
    ssh_port_raw = raw.get("ssh_port")
    ssh_port: int | None = None
    if location == "ssh":
        if not ssh_host or not _SSH_HOST_RE.fullmatch(ssh_host):
            raise ValueError(
                "SSH source requires a valid 'ssh_host' (alphanumeric, '.', '_', '-', '@', ':'; must not start with '-')"
            )
        if ssh_port_raw is not None and str(ssh_port_raw).strip() != "":
            try:
                ssh_port = int(ssh_port_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError("'ssh_port' must be an integer between 1 and 65535") from exc
            if not (1 <= ssh_port <= 65535):
                raise ValueError("'ssh_port' must be between 1 and 65535")
    else:
        ssh_host = ""
        ssh_port = None

    description = str(raw.get("description") or "").strip()[:300]
    enabled = bool(raw.get("enabled", True))

    spec: dict[str, Any] = {
        "id": source_id,
        "name": name,
        "type": source_type,
        "location": location,
        "path": path,
        "description": description,
        "enabled": enabled,
    }
    if location == "ssh":
        spec["ssh_host"] = ssh_host
        if ssh_port is not None:
            spec["ssh_port"] = ssh_port
    return spec


def load_corpus_sources(data_root: Path, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    """Read configured corpus sources lazily (never creates files or directories)."""
    path = sources_file(data_root)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    entries = raw.get("sources", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in entries:
        try:
            spec = validate_source_spec(item)
        except ValueError:
            continue
        if spec["id"] in seen:
            continue
        seen.add(spec["id"])
        if enabled_only and not spec.get("enabled", True):
            continue
        sources.append(spec)
    return sources


def get_corpus_source(data_root: Path, source_id: str) -> dict[str, Any] | None:
    for src in load_corpus_sources(data_root):
        if src["id"] == source_id:
            return src
    return None


def _write_sources_unlocked(path: Path, sources: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"sources": sources}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)


def save_corpus_source(data_root: Path, raw_spec: dict[str, Any]) -> dict[str, Any]:
    """Validate and upsert a corpus source entry in local config."""
    spec = validate_source_spec(raw_spec)
    path = sources_file(data_root)
    with _sources_lock:
        existing = load_corpus_sources(data_root)
        updated = [s for s in existing if s["id"] != spec["id"]]
        updated.append(spec)
        _write_sources_unlocked(path, updated)
    return spec


def delete_corpus_source(data_root: Path, source_id: str) -> bool:
    """Remove a configured corpus source by id."""
    path = sources_file(data_root)
    with _sources_lock:
        existing = load_corpus_sources(data_root)
        remaining = [s for s in existing if s["id"] != source_id]
        if len(remaining) == len(existing):
            return False
        _write_sources_unlocked(path, remaining)
    return True


def _translate_pcre_shorthands_to_ere(pattern: str) -> str:
    """Best-effort fallback translating common PCRE shorthands for POSIX grep -E."""
    out = pattern.replace(r"\d", "[0-9]").replace(r"\s", "[[:space:]]")
    return out


def _parse_grep_output(
    stdout: str,
    *,
    limit: int,
    context_lines: int,
    line_offset: int,
) -> list[dict[str, Any]]:
    """Parse `grep -n [-C N]` output into structured matches with before/after context."""
    line_map: dict[int, str] = {}
    match_line_nos: list[int] = []
    seen_matches: set[int] = set()

    for raw_line in stdout.splitlines():
        if raw_line == "--":
            continue
        m = _GREP_LINE_RE.match(raw_line)
        if not m:
            continue
        rel_no = int(m.group(1))
        sep = m.group(2)
        text = m.group(3)
        abs_no = rel_no + line_offset
        line_map[abs_no] = text
        if sep == ":" and abs_no not in seen_matches:
            seen_matches.add(abs_no)
            match_line_nos.append(abs_no)

    results: list[dict[str, Any]] = []
    for m_no in match_line_nos[:limit]:
        before = [
            _clean_text(line_map[k])
            for k in range(m_no - context_lines, m_no)
            if k in line_map and line_map[k].strip()
        ]
        after = [
            _clean_text(line_map[k])
            for k in range(m_no + 1, m_no + context_lines + 1)
            if k in line_map and line_map[k].strip()
        ]
        hit_text = _clean_text(line_map.get(m_no, ""))
        window = _clean_text(" ".join([*before, hit_text, *after]))
        results.append(
            {
                "line_number": m_no,
                "text": hit_text,
                "context_before": before,
                "context_after": after,
                "context_window": window[:900],
            }
        )
    return results


def _search_local_text_file(
    source: dict[str, Any],
    *,
    query: str,
    mode: str,
    limit: int,
    context_lines: int,
    ignore_case: bool,
    start_line: int,
) -> tuple[list[dict[str, Any]], bool]:
    path = Path(source["path"]).expanduser()
    if not path.is_file():
        raise CorpusSourceError(f"Local text file not found: {path}")

    compiled: re.Pattern[str] | None = None
    needle = query.lower() if ignore_case else query
    if mode in ("regex", "ere"):
        flags = re.IGNORECASE if ignore_case else 0
        try:
            compiled = re.compile(query, flags)
        except re.error as exc:
            raise ValueError(f"Invalid regular expression {query!r}: {exc}") from exc

    def _matches(line: str) -> bool:
        if compiled is not None:
            return compiled.search(line) is not None
        hay = line.lower() if ignore_case else line
        return needle in hay

    # Keep a sliding window of prior lines and collect trailing context for matched lines.
    before_buf: deque[tuple[int, str]] = deque(maxlen=max(1, context_lines))
    pending: list[dict[str, Any]] = []
    finished: list[dict[str, Any]] = []
    truncated = False

    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for lineno, raw_line in enumerate(fh, start=1):
                line = raw_line.rstrip("\r\n")
                # Feed trailing context to already-matched entries
                if pending:
                    still_pending: list[dict[str, Any]] = []
                    for item in pending:
                        if lineno <= item["line_number"] + context_lines:
                            cleaned = _clean_text(line)
                            if cleaned:
                                item["context_after"].append(cleaned)
                        if lineno >= item["line_number"] + context_lines:
                            item["context_window"] = _clean_text(
                                " ".join([*item["context_before"], item["text"], *item["context_after"]])
                            )[:900]
                            finished.append(item)
                        else:
                            still_pending.append(item)
                    pending = still_pending

                if lineno >= start_line and _matches(line):
                    if len(finished) + len(pending) >= limit:
                        truncated = True
                        if not pending:
                            break
                    else:
                        before = [
                            _clean_text(txt)
                            for ln, txt in before_buf
                            if ln >= lineno - context_lines and txt.strip()
                        ] if context_lines > 0 else []
                        hit_text = _clean_text(line)
                        entry = {
                            "line_number": lineno,
                            "text": hit_text,
                            "context_before": before,
                            "context_after": [],
                            "context_window": hit_text[:900],
                        }
                        if context_lines == 0:
                            finished.append(entry)
                        else:
                            pending.append(entry)
                elif truncated and not pending:
                    break

                if context_lines > 0:
                    before_buf.append((lineno, line))
    except OSError as exc:
        raise CorpusSourceError(f"Failed reading local file {path}: {exc}") from exc

    for item in pending:
        item["context_window"] = _clean_text(
            " ".join([*item["context_before"], item["text"], *item["context_after"]])
        )[:900]
        finished.append(item)

    return finished[:limit], truncated


def _build_remote_grep_command(
    *,
    remote_path: str,
    query: str,
    grep_flag: str,
    limit: int,
    context_lines: int,
    ignore_case: bool,
    start_line: int,
) -> str:
    grep_parts = ["grep", "-n", grep_flag]
    if ignore_case:
        grep_parts.append("-i")
    if context_lines > 0:
        grep_parts.extend(["-C", str(context_lines)])
    grep_parts.extend(["-m", str(limit + 1), "-e", shlex.quote(query)])

    q_path = shlex.quote(remote_path)
    if start_line > 1:
        grep_cmd = " ".join(grep_parts)
        return (
            f"if [ ! -r {q_path} ]; then echo 'Source file not found or unreadable' >&2; exit 2; fi; "
            f"tail -n +{start_line} -- {q_path} | {grep_cmd}"
        )
    grep_parts.extend(["--", q_path])
    return " ".join(grep_parts)


def _run_ssh_command(
    ssh_host: str,
    remote_cmd: str,
    *,
    ssh_port: int | None = None,
    timeout: float = 20.0,
) -> subprocess.CompletedProcess[str]:
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
    if ssh_port is not None:
        cmd.extend(["-p", str(ssh_port)])
    cmd.extend(["--", ssh_host, remote_cmd])
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CorpusSourceError(f"SSH search on {ssh_host!r} timed out after {timeout:.0f}s") from exc
    except OSError as exc:
        raise CorpusSourceError(f"Failed to invoke ssh for {ssh_host!r}: {exc}") from exc


def _search_ssh_text_file(
    source: dict[str, Any],
    *,
    query: str,
    mode: str,
    limit: int,
    context_lines: int,
    ignore_case: bool,
    start_line: int,
    timeout: float,
) -> tuple[list[dict[str, Any]], bool, str]:
    ssh_host = source["ssh_host"]
    ssh_port = source.get("ssh_port")
    remote_path = source["path"]

    if mode == "fixed":
        flag = "-F"
        effective_query = query
        used_mode = "fixed"
    elif mode == "ere":
        flag = "-E"
        effective_query = query
        used_mode = "ere"
    else:
        flag = "-P"
        effective_query = query
        used_mode = "regex"

    remote_cmd = _build_remote_grep_command(
        remote_path=remote_path,
        query=effective_query,
        grep_flag=flag,
        limit=limit,
        context_lines=context_lines,
        ignore_case=ignore_case,
        start_line=start_line,
    )
    proc = _run_ssh_command(ssh_host, remote_cmd, ssh_port=ssh_port, timeout=timeout)

    # Automatic fallback if remote grep lacks PCRE (-P) support (e.g., BSD/macOS/BusyBox).
    if proc.returncode == 2 and flag == "-P":
        err_lower = (proc.stderr or "").lower()
        if any(tok in err_lower for tok in ("invalid option", "unrecognized", "not supported", "usage:", "pcre")):
            fallback_cmd = _build_remote_grep_command(
                remote_path=remote_path,
                query=_translate_pcre_shorthands_to_ere(query),
                grep_flag="-E",
                limit=limit,
                context_lines=context_lines,
                ignore_case=ignore_case,
                start_line=start_line,
            )
            proc = _run_ssh_command(ssh_host, fallback_cmd, ssh_port=ssh_port, timeout=timeout)
            used_mode = "ere_fallback"

    if proc.returncode == 1:
        return [], False, used_mode
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or f"exit code {proc.returncode}").strip()
        raise CorpusSourceError(f"SSH grep failed on {ssh_host} (exit {proc.returncode}): {detail[:400]}")

    parsed = _parse_grep_output(
        proc.stdout,
        limit=limit + 1,
        context_lines=context_lines,
        line_offset=start_line - 1,
    )
    truncated = len(parsed) > limit
    return parsed[:limit], truncated, used_mode


def search_text_file_source(
    source: dict[str, Any],
    *,
    query: str,
    mode: str = "regex",
    limit: int = 20,
    context_lines: int = 0,
    ignore_case: bool = False,
    start_line: int = 1,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Search a configured `text_file` source (local or remote SSH) by regex or literal string."""
    spec = validate_source_spec(source)
    if not query or len(query) > 500 or "\x00" in query or "\n" in query or "\r" in query:
        raise ValueError("Search 'query' must be a non-empty single-line string (<= 500 chars)")
    if mode not in VALID_SEARCH_MODES:
        raise ValueError(f"Unsupported search mode {mode!r}; expected one of {VALID_SEARCH_MODES}")

    clamped_limit = max(1, min(100, int(limit)))
    clamped_ctx = max(0, min(5, int(context_lines)))
    clamped_start = max(1, int(start_line))

    if spec["location"] == "local":
        matches, truncated = _search_local_text_file(
            spec,
            query=query,
            mode=mode,
            limit=clamped_limit,
            context_lines=clamped_ctx,
            ignore_case=ignore_case,
            start_line=clamped_start,
        )
        used_mode = mode
    else:
        matches, truncated, used_mode = _search_ssh_text_file(
            spec,
            query=query,
            mode=mode,
            limit=clamped_limit,
            context_lines=clamped_ctx,
            ignore_case=ignore_case,
            start_line=clamped_start,
            timeout=timeout,
        )

    return {
        "source_id": spec["id"],
        "source_name": spec["name"],
        "type": spec["type"],
        "location": spec["location"],
        "query": query,
        "mode": used_mode,
        "limit": clamped_limit,
        "context_lines": clamped_ctx,
        "start_line": clamped_start,
        "ignore_case": bool(ignore_case),
        "match_count": len(matches),
        "truncated": truncated,
        "matches": matches,
    }


def search_configured_source(
    data_root: Path,
    source_id: str,
    *,
    query: str,
    mode: str = "regex",
    limit: int = 20,
    context_lines: int = 0,
    ignore_case: bool = False,
    start_line: int = 1,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Look up a configured source by id and execute a search on it."""
    source = get_corpus_source(data_root, source_id)
    if source is None:
        available = [s["id"] for s in load_corpus_sources(data_root)]
        raise ValueError(
            f"Unknown corpus source {source_id!r}. Configured sources: {available}"
        )
    if not source.get("enabled", True):
        raise ValueError(f"Corpus source {source_id!r} is disabled")
    return search_text_file_source(
        source,
        query=query,
        mode=mode,
        limit=limit,
        context_lines=context_lines,
        ignore_case=ignore_case,
        start_line=start_line,
        timeout=timeout,
    )
