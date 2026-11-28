"""CLI used by agents (including background Gemini 4 Neon sessions) to drive pipeline stages and search corpus sources."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from .corpus_sources import (
    CorpusSourceError,
    delete_corpus_source,
    load_corpus_sources,
    save_corpus_source,
    search_configured_source,
)
from .review import ReviewStore
from .template_library import library_summary, publish_templates_to_repo, sync_library_from_batches


def _api_call(server_url: str, method: str, path: str, payload: Any = None, timeout: float = 90.0) -> Any:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = f"{server_url.rstrip('/')}{path}"
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(body)
            detail = parsed.get("detail", body)
        except json.JSONDecodeError:
            detail = body or exc.reason
        raise SystemExit(f"HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Connection error calling {url}: {exc}") from exc


def _resolve_data_root(raw: Path | None) -> Path:
    if raw is not None:
        return raw.expanduser()
    return ReviewStore().root


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Drive Hebrew spoken numeric micro-template pipeline steps")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create-batch", help="Create and dispatch a new Neon pipeline batch")
    p_create.add_argument("--server-url", default="http://127.0.0.1:8766")
    p_create.add_argument("--target-count", type=int, default=300)
    p_create.add_argument("--template-count", type=int, default=None)
    p_create.add_argument("--seed", type=int, default=42)
    p_create.add_argument("--corpus-ratio", type=float, default=0.75)
    p_create.add_argument("--notes", default="")
    p_create.add_argument("--model", default="google/gemini-4-neon")
    p_create.add_argument("--variant", default="default")
    p_create.add_argument("--notify-session", default="", help="OpenChamber session ID to wake up when this batch completes")
    p_create.add_argument("--notify-me", action="store_true", help="Wake up current OPENCODE_SESSION_ID when this batch completes")
    p_create.add_argument("--notify-context", default="", help="Optional context string echoed back in the completion message")

    for name in ("status", "mine", "get-stress-pack", "finalize"):
        p = sub.add_parser(name)
        p.add_argument("--server-url", required=True)
        p.add_argument("--batch-id", required=True)

    p_tpl = sub.add_parser("submit-templates")
    p_tpl.add_argument("--server-url", required=True)
    p_tpl.add_argument("--batch-id", required=True)
    p_tpl.add_argument("--file", type=Path, required=True, help="JSON file containing a list of MicroTemplate objects")

    p_ver = sub.add_parser("submit-verdicts")
    p_ver.add_argument("--server-url", required=True)
    p_ver.add_argument("--batch-id", required=True)
    p_ver.add_argument("--file", type=Path, required=True, help="JSON file containing a list of Critic verdict objects")

    p_fail = sub.add_parser("fail")
    p_fail.add_argument("--server-url", required=True)
    p_fail.add_argument("--batch-id", required=True)
    p_fail.add_argument("--reason", required=True)

    p_sources = sub.add_parser("sources", help="List configured external corpus sources")
    p_sources.add_argument("--server-url", default="", help="Optional pipeline server URL (omit for direct local config)")
    p_sources.add_argument("--data-root", type=Path, default=None, help="Optional data directory override (standalone mode)")

    p_add_src = sub.add_parser("add-source", help="Add or update a text_file corpus source (local or remote SSH)")
    p_add_src.add_argument("--id", required=True, help="Unique slug id (e.g. knesset_committees)")
    p_add_src.add_argument("--name", required=True, help="Human-readable source label")
    p_add_src.add_argument("--type", default="text_file", choices=("text_file",))
    p_add_src.add_argument("--location", default="", choices=("", "local", "ssh"), help="local or ssh (inferred if --ssh-host is set)")
    p_add_src.add_argument("--path", required=True, help="Path to one-sentence-per-line text file")
    p_add_src.add_argument("--ssh-host", default="", help="SSH host or alias (required when --location ssh)")
    p_add_src.add_argument("--ssh-port", type=int, default=None, help="Optional SSH port")
    p_add_src.add_argument("--description", default="", help="Short description of the corpus")
    p_add_src.add_argument("--disabled", action="store_true", help="Save source in disabled state")
    p_add_src.add_argument("--server-url", default="", help="Optional pipeline server URL")
    p_add_src.add_argument("--data-root", type=Path, default=None, help="Optional data directory override")

    p_rm_src = sub.add_parser("remove-source", help="Delete a configured corpus source by id")
    p_rm_src.add_argument("--id", required=True)
    p_rm_src.add_argument("--server-url", default="", help="Optional pipeline server URL")
    p_rm_src.add_argument("--data-root", type=Path, default=None, help="Optional data directory override")

    p_search = sub.add_parser(
        "search-source",
        help="Search a configured text_file corpus source (local or remote SSH) by regexp or literal string",
    )
    p_search.add_argument("--source", required=True, help="Configured source id")
    p_search.add_argument(
        "--query",
        required=True,
        help="Regular expression (default) or literal string (with --mode fixed). Use --query='...' if pattern starts with '-'",
    )
    p_search.add_argument("--mode", default="regex", choices=("regex", "fixed", "ere"))
    p_search.add_argument("--limit", type=int, default=20, help="Max matches to return (1..100)")
    p_search.add_argument("--context", type=int, default=0, help="Adjacent context lines before/after each match (0..5)")
    p_search.add_argument("--start-line", type=int, default=1, help="1-based line number to start scanning from")
    p_search.add_argument("--ignore-case", action="store_true", help="Case-insensitive search")
    p_search.add_argument("--server-url", default="", help="Optional pipeline server URL (omit for direct search)")
    p_search.add_argument("--batch-id", default="", help="Optional batch id to attach hits to when using --server-url")
    p_search.add_argument("--data-root", type=Path, default=None, help="Optional data directory override (standalone mode)")

    p_lib = sub.add_parser("library-status", help="Inspect curated MicroTemplate library summary")
    p_lib.add_argument("--server-url", default="", help="Optional pipeline server URL")
    p_lib.add_argument("--data-root", type=Path, default=None, help="Optional data directory override")

    p_libsync = sub.add_parser("library-sync", help="Sync approved MicroTemplates from pipeline batches into micro_template_library.json")
    p_libsync.add_argument("--batch-id", action="append", dest="batch_ids", help="Limit sync to specific batch id(s)")
    p_libsync.add_argument("--only-multi-number", action="store_true", help="Import only templates with >=2 numeric nodes")
    p_libsync.add_argument(
        "--disable-single-number-batches",
        action="store_true",
        help="Import older mostly-single-number batches in disabled state",
    )
    p_libsync.add_argument("--server-url", default="", help="Optional pipeline server URL")
    p_libsync.add_argument("--data-root", type=Path, default=None, help="Optional data directory override")

    p_libpub = sub.add_parser(
        "library-publish",
        help="Publish selected (or all unpublished) local MicroTemplates into official numeric_pairs/micro_template_library.json",
    )
    p_libpub.add_argument("--id", action="append", dest="template_ids", help="Specific template id(s) to publish")
    p_libpub.add_argument("--batch-id", action="append", dest="batch_ids", help="Publish unpublished templates from specific batch id(s)")
    p_libpub.add_argument("--include-disabled", action="store_true", help="Include disabled local templates when publishing all")
    p_libpub.add_argument("--official-path", type=Path, default=None, help="Optional override for official repo library path")
    p_libpub.add_argument("--server-url", default="", help="Optional pipeline server URL")
    p_libpub.add_argument("--data-root", type=Path, default=None, help="Optional data directory override")

    args = parser.parse_args(argv)

    if args.cmd == "create-batch":
        notify_sid = args.notify_session.strip() or (os.environ.get("OPENCODE_SESSION_ID", "").strip() if args.notify_me else "")
        payload: dict[str, Any] = {
            "target_count": args.target_count,
            "seed": args.seed,
            "corpus_ratio": args.corpus_ratio,
            "notes": args.notes,
            "model": args.model,
            "variant": args.variant,
        }
        if args.template_count is not None:
            payload["template_count"] = args.template_count
        if notify_sid:
            payload["notify_session_id"] = notify_sid
        if args.notify_context:
            payload["notify_context"] = args.notify_context
        res = _api_call(args.server_url, "POST", "/api/pipeline/batches", payload)
    elif args.cmd in ("status", "mine", "get-stress-pack", "finalize", "submit-templates", "submit-verdicts", "fail"):
        bid = urllib.parse.quote(args.batch_id)
        if args.cmd == "status":
            res = _api_call(args.server_url, "GET", f"/api/pipeline/batches/{bid}")
        elif args.cmd == "mine":
            res = _api_call(args.server_url, "POST", f"/api/pipeline/batches/{bid}/mine")
        elif args.cmd == "submit-templates":
            templates = json.loads(args.file.read_text(encoding="utf-8"))
            if isinstance(templates, dict) and "templates" in templates:
                templates = templates["templates"]
            res = _api_call(args.server_url, "POST", f"/api/pipeline/batches/{bid}/templates", {"templates": templates})
        elif args.cmd == "get-stress-pack":
            res = _api_call(args.server_url, "GET", f"/api/pipeline/batches/{bid}/stress-pack")
        elif args.cmd == "submit-verdicts":
            verdicts = json.loads(args.file.read_text(encoding="utf-8"))
            if isinstance(verdicts, dict) and "verdicts" in verdicts:
                verdicts = verdicts["verdicts"]
            res = _api_call(args.server_url, "POST", f"/api/pipeline/batches/{bid}/verdicts", {"verdicts": verdicts})
        elif args.cmd == "finalize":
            res = _api_call(args.server_url, "POST", f"/api/pipeline/batches/{bid}/finalize")
        else:
            res = _api_call(args.server_url, "POST", f"/api/pipeline/batches/{bid}/fail", {"reason": args.reason})
    elif args.cmd == "sources":
        if args.server_url:
            res = _api_call(args.server_url, "GET", "/api/pipeline/sources")
        else:
            res = {"sources": load_corpus_sources(_resolve_data_root(args.data_root))}
    elif args.cmd == "add-source":
        location = args.location or ("ssh" if args.ssh_host.strip() else "local")
        payload: dict[str, Any] = {
            "id": args.id,
            "name": args.name,
            "type": args.type,
            "location": location,
            "path": args.path,
            "description": args.description,
            "enabled": not args.disabled,
        }
        if args.ssh_host.strip():
            payload["ssh_host"] = args.ssh_host.strip()
        if args.ssh_port is not None:
            payload["ssh_port"] = args.ssh_port
        if args.server_url:
            res = _api_call(args.server_url, "POST", "/api/pipeline/sources", payload)
        else:
            try:
                saved = save_corpus_source(_resolve_data_root(args.data_root), payload)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            res = {"source": saved}
    elif args.cmd == "remove-source":
        sid = urllib.parse.quote(args.id)
        if args.server_url:
            res = _api_call(args.server_url, "DELETE", f"/api/pipeline/sources/{sid}")
        else:
            deleted = delete_corpus_source(_resolve_data_root(args.data_root), args.id)
            if not deleted:
                raise SystemExit(f"Corpus source {args.id!r} not found")
            res = {"deleted": args.id}
    elif args.cmd == "search-source":
        if args.server_url:
            sid = urllib.parse.quote(args.source)
            payload = {
                "query": args.query,
                "mode": args.mode,
                "limit": args.limit,
                "context_lines": args.context,
                "start_line": args.start_line,
                "ignore_case": bool(args.ignore_case),
            }
            if args.batch_id:
                payload["batch_id"] = args.batch_id
            res = _api_call(args.server_url, "POST", f"/api/pipeline/sources/{sid}/search", payload)
        else:
            try:
                res = search_configured_source(
                    _resolve_data_root(args.data_root),
                    args.source,
                    query=args.query,
                    mode=args.mode,
                    limit=args.limit,
                    context_lines=args.context,
                    ignore_case=bool(args.ignore_case),
                    start_line=args.start_line,
                )
            except (ValueError, CorpusSourceError) as exc:
                raise SystemExit(str(exc)) from exc
    elif args.cmd == "library-status":
        if args.server_url:
            res = _api_call(args.server_url, "GET", "/api/library?include_templates=false")
        else:
            res = library_summary(_resolve_data_root(args.data_root), include_templates=False)
    elif args.cmd == "library-sync":
        if args.server_url:
            res = _api_call(
                args.server_url,
                "POST",
                "/api/library/sync",
                {
                    "batch_ids": args.batch_ids,
                    "only_multi_number": bool(args.only_multi_number),
                    "disable_single_number_batches": bool(args.disable_single_number_batches),
                },
            )
        else:
            res = sync_library_from_batches(
                _resolve_data_root(args.data_root),
                batch_ids=args.batch_ids,
                only_multi_number=bool(args.only_multi_number),
                disable_single_number_batches=bool(args.disable_single_number_batches),
            )
    elif args.cmd == "library-publish":
        if args.server_url:
            res = _api_call(
                args.server_url,
                "POST",
                "/api/library/publish",
                {
                    "template_ids": args.template_ids,
                    "batch_ids": args.batch_ids,
                    "include_disabled": bool(args.include_disabled),
                },
            )
        else:
            res = publish_templates_to_repo(
                _resolve_data_root(args.data_root),
                template_ids=args.template_ids,
                batch_ids=args.batch_ids,
                include_disabled=bool(args.include_disabled),
                official_path=args.official_path,
            )
    else:
        raise SystemExit(f"Unknown subcommand {args.cmd}")

    sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
