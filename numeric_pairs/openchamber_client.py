"""Local OpenChamber HTTP API client for background session dispatch and cost telemetry."""

from __future__ import annotations

import http.cookiejar
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request

# Fallback per-1M-token USD rates when provider returns cost=0 while reporting tokens
DEFAULT_MODEL_PRICING_PER_1M: dict[str, dict[str, float]] = {
    "google/gemini-4-neon": {"input": 3.0, "output": 15.0, "cache_read": 0.15, "cache_write": 0.0},
    "opencode/gemini-4-neon": {"input": 3.0, "output": 15.0, "cache_read": 0.15, "cache_write": 0.0},
    "google/gemini-4-carbon": {"input": 4.0, "output": 20.0, "cache_read": 0.20, "cache_write": 0.0},
}


class OpenChamberError(RuntimeError):
    """Raised when OpenChamber connection, authentication, or session dispatch fails."""


def discover_openchamber_config(settings_path: Path | None = None) -> dict[str, Any]:
    """Resolve OpenChamber base URL and UI password from environment or ~/.config/openchamber/settings.json."""
    env_url = os.environ.get("OPENCHAMBER_URL", "").strip().rstrip("/")
    env_pw = os.environ.get("OPENCHAMBER_UI_PASSWORD", "").strip()

    # Also derive base URL from OPENCHAMBER_AGENT_TOOL_URL if running inside OpenChamber
    if not env_url:
        agent_url = os.environ.get("OPENCHAMBER_AGENT_TOOL_URL", "").strip()
        if agent_url and "/api/" in agent_url:
            parsed = urllib.parse.urlparse(agent_url)
            if parsed.scheme and parsed.netloc:
                env_url = f"{parsed.scheme}://{parsed.netloc}"

    cfg_file = Path(settings_path or (Path.home() / ".config" / "openchamber" / "settings.json"))
    disk_port = None
    disk_pw = ""
    if cfg_file.is_file():
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
            disk_port = data.get("desktopLocalPort")
            disk_pw = str(data.get("desktopUiPassword") or "")
        except (OSError, json.JSONDecodeError):
            pass

    base_url = env_url or (f"http://127.0.0.1:{disk_port}" if disk_port else "")
    password = env_pw or disk_pw
    return {
        "configured": bool(base_url),
        "base_url": base_url,
        "has_password": bool(password),
        "password": password,
    }


class OpenChamberClient:
    """Thread-safe HTTP client for OpenChamber's session, permission, and telemetry endpoints."""

    def __init__(self, base_url: str | None = None, password: str | None = None, settings_path: Path | None = None):
        self._explicit_url = base_url.rstrip("/") if base_url else None
        self._explicit_pw = password
        self._settings_path = settings_path
        self._lock = threading.Lock()
        self._cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(self._cookies),
        )
        self._authenticated_url: str | None = None
        self._pricing_cache: dict[str, dict[str, float]] = dict(DEFAULT_MODEL_PRICING_PER_1M)
        self._pricing_loaded_at = 0.0

    def connection_info(self) -> dict[str, Any]:
        cfg = discover_openchamber_config(self._settings_path)
        base_url = self._explicit_url or cfg["base_url"]
        password = self._explicit_pw if self._explicit_pw is not None else cfg["password"]
        return {
            "configured": bool(base_url),
            "base_url": base_url,
            "has_password": bool(password),
            "_password": password,
        }

    def _ensure_auth(self, base_url: str, password: str, force: bool = False) -> None:
        if not base_url:
            raise OpenChamberError("לא נמצא שרת OpenChamber פעיל (בדקו ש-OpenChamber פתוח או הגדירו OPENCHAMBER_URL).")
        with self._lock:
            if not force and self._authenticated_url == base_url:
                return
            if password:
                req = urllib.request.Request(
                    f"{base_url}/auth/session",
                    data=json.dumps({"password": password}).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    method="POST",
                )
                try:
                    with self._opener.open(req, timeout=8) as resp:
                        resp.read()
                except urllib.error.URLError as exc:
                    raise OpenChamberError(f"התחברות ל-OpenChamber בכתובת {base_url} נכשלה: {exc}") from exc
            self._authenticated_url = base_url

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        directory: str | None = None,
        timeout: float = 20.0,
    ) -> Any:
        info = self.connection_info()
        base_url = info["base_url"]
        password = info["_password"]
        self._ensure_auth(base_url, password)

        for attempt in range(2):
            headers = {"Accept": "application/json"}
            data = None
            if directory:
                headers["x-opencode-directory"] = directory
            if body is not None:
                headers["Content-Type"] = "application/json"
                data = json.dumps(body, ensure_ascii=False).encode("utf-8")

            req = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
            try:
                with self._opener.open(req, timeout=timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as exc:
                if exc.code == 401 and attempt == 0:
                    self._ensure_auth(base_url, password, force=True)
                    continue
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", errors="ignore")[:300]
                except Exception:
                    pass
                raise OpenChamberError(f"OpenChamber HTTP {exc.code} on {method} {path}: {detail or exc.reason}") from exc
            except urllib.error.URLError as exc:
                raise OpenChamberError(f"שגיאת תקשורת מול OpenChamber ({method} {path}): {exc}") from exc
        raise OpenChamberError(f"אימות מול OpenChamber נכשל ({path})")

    def _load_pricing_if_needed(self) -> None:
        now = time.time()
        if now - self._pricing_loaded_at < 600:
            return
        self._pricing_loaded_at = now
        try:
            meta = self.request_json("GET", "/api/openchamber/models-metadata", timeout=6.0)
        except OpenChamberError:
            return
        if not isinstance(meta, dict):
            return
        for prov_id, prov_block in meta.items():
            if not isinstance(prov_block, dict):
                continue
            models = prov_block.get("models")
            if not isinstance(models, dict):
                continue
            for m_id, m_info in models.items():
                if isinstance(m_info, dict) and isinstance(m_info.get("cost"), dict):
                    c = m_info["cost"]
                    self._pricing_cache[f"{prov_id}/{m_id}"] = {
                        "input": float(c.get("input", 0.0)),
                        "output": float(c.get("output", 0.0)),
                        "cache_read": float(c.get("cache_read", 0.0)),
                        "cache_write": float(c.get("cache_write", 0.0)),
                    }

    def estimate_cost_usd(self, model_key: str, tokens: dict[str, int]) -> float:
        self._load_pricing_if_needed()
        rates = self._pricing_cache.get(model_key)
        if not rates and "/" in model_key:
            _, bare = model_key.split("/", 1)
            for k, v in self._pricing_cache.items():
                if k.endswith("/" + bare):
                    rates = v
                    break
        if not rates:
            return 0.0
        # Output pricing covers output + reasoning tokens when reasoning isn't already inside output
        in_tok = tokens.get("input", 0)
        out_tok = tokens.get("output", 0)
        cache_r = tokens.get("cache_read", 0)
        cache_w = tokens.get("cache_write", 0)
        return (
            in_tok * rates.get("input", 0.0)
            + out_tok * rates.get("output", 0.0)
            + cache_r * rates.get("cache_read", 0.0)
            + cache_w * rates.get("cache_write", 0.0)
        ) / 1_000_000.0

    def create_and_start_session(
        self,
        *,
        title: str,
        prompt: str,
        directory: str,
        model_spec: str = "google/gemini-4-neon",
        variant: str | None = None,
        on_prompt_error: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Create a new OpenChamber session with auto-allow tool permissions and send its prompt asynchronously."""
        if "/" in model_spec:
            provider_id, model_id = model_spec.split("/", 1)
        else:
            provider_id, model_id = "google", model_spec

        model_obj: dict[str, str] = {"providerID": provider_id, "id": model_id}
        if variant and variant != "default":
            model_obj["variant"] = variant

        permissions = [
            {"action": "*", "resource": "*", "effect": "allow"},
        ]
        create_payload: dict[str, Any] = {
            "title": title,
            "agent": "build",
            "model": model_obj,
            "location": {"directory": directory},
            "permissions": permissions,
        }
        try:
            created = self.request_json("POST", "/api/session", body=create_payload, directory=directory, timeout=15.0)
        except OpenChamberError:
            # Retry without permissions block if server version rejects custom permissions array
            create_payload.pop("permissions", None)
            created = self.request_json("POST", "/api/session", body=create_payload, directory=directory, timeout=15.0)

        session_data = created.get("data", created) if isinstance(created, dict) else {}
        session_id = session_data.get("id")
        if not session_id:
            raise OpenChamberError(f"OpenChamber לא החזיר מזהה סשן תקין: {created!r}")

        # Register directory in OpenChamber project index (best effort)
        try:
            self.request_json(
                "POST",
                "/api/projects/session-directory",
                body={"sessionId": session_id, "directory": directory},
                directory=directory,
                timeout=6.0,
            )
        except OpenChamberError:
            pass

        def _send_prompt_bg() -> None:
            try:
                # OpenCode /prompt can hold the connection while streaming or return on completion;
                # use a generous timeout on this background thread.
                self.request_json(
                    "POST",
                    f"/api/session/{urllib.parse.quote(session_id)}/prompt",
                    body={"text": prompt},
                    directory=directory,
                    timeout=900.0,
                )
            except Exception as exc:  # noqa: BLE001
                if on_prompt_error is not None:
                    on_prompt_error(str(exc))

        thread = threading.Thread(target=_send_prompt_bg, name=f"oc-prompt-{session_id[:10]}", daemon=True)
        thread.start()

        return {
            "session_id": session_id,
            "model": f"{provider_id}/{model_id}",
            "variant": variant or "default",
            "title": title,
        }

    def _auto_approve_permissions(self, session_id: str, directory: str) -> int:
        """Ensure background pipeline sessions never block waiting for tool permission approval."""
        approved = 0
        try:
            res = self.request_json(
                "GET",
                f"/api/session/{urllib.parse.quote(session_id)}/permission",
                directory=directory,
                timeout=5.0,
            )
            items = res.get("data", res) if isinstance(res, dict) else res
            if isinstance(items, list):
                for item in items:
                    req_id = item.get("id") if isinstance(item, dict) else None
                    if req_id:
                        self.request_json(
                            "POST",
                            f"/api/session/{urllib.parse.quote(session_id)}/permission/{urllib.parse.quote(req_id)}/reply",
                            body={"decision": "allow"},
                            directory=directory,
                            timeout=5.0,
                        )
                        approved += 1
        except OpenChamberError:
            pass
        return approved

    def fetch_session_telemetry(self, session_id: str, directory: str) -> dict[str, Any]:
        """Fetch live status, token counts, exact USD cost, and latest activity for a session."""
        self._auto_approve_permissions(session_id, directory)

        sess_res = self.request_json(
            "GET",
            f"/api/session/{urllib.parse.quote(session_id)}",
            directory=directory,
            timeout=8.0,
        )
        sdata = sess_res.get("data", sess_res) if isinstance(sess_res, dict) else {}

        live_status = "unknown"
        try:
            st_res = self.request_json("GET", "/api/sessions/status", directory=directory, timeout=6.0)
            sessions_map = st_res.get("sessions", {}) if isinstance(st_res, dict) else {}
            if session_id in sessions_map and isinstance(sessions_map[session_id], dict):
                live_status = str(sessions_map[session_id].get("status", "unknown"))
        except OpenChamberError:
            pass

        if live_status == "unknown":
            t_info = sdata.get("time") or {}
            if t_info.get("busy", 0) > t_info.get("idle", 0):
                live_status = "busy"
            elif sdata.get("outcome"):
                live_status = "idle"

        raw_tok = sdata.get("tokens") or {}
        cache_tok = raw_tok.get("cache") or {}
        tokens = {
            "input": int(raw_tok.get("input", 0) or 0),
            "output": int(raw_tok.get("output", 0) or 0),
            "reasoning": int(raw_tok.get("reasoning", 0) or 0),
            "cache_read": int(cache_tok.get("read", 0) or 0),
            "cache_write": int(cache_tok.get("write", 0) or 0),
        }

        model_info = sdata.get("model") or {}
        model_key = (
            f"{model_info.get('providerID', 'google')}/{model_info.get('id', 'gemini-4-neon')}"
            if isinstance(model_info, dict)
            else "google/gemini-4-neon"
        )

        reported_cost = float(sdata.get("cost") or 0.0)
        if reported_cost > 0:
            cost_usd = reported_cost
            cost_source = "openchamber_session"
        else:
            cost_usd = self.estimate_cost_usd(model_key, tokens)
            cost_source = "pricing_table" if cost_usd > 0 else "pending"

        last_activity = ""
        assistant_turns = 0
        try:
            msg_res = self.request_json(
                "GET",
                f"/api/session/{urllib.parse.quote(session_id)}/message?limit=8",
                directory=directory,
                timeout=8.0,
            )
            msg_list = msg_res.get("data", []) if isinstance(msg_res, dict) else []
            for msg in msg_list:
                if not isinstance(msg, dict):
                    continue
                if msg.get("type") == "assistant":
                    assistant_turns += 1
                    if not last_activity:
                        for part in reversed(msg.get("content") or []):
                            if not isinstance(part, dict):
                                continue
                            ptype = part.get("type")
                            if ptype == "tool":
                                tname = part.get("name", "tool")
                                inp = part.get("input") or {}
                                cmd = inp.get("command", "") if isinstance(inp, dict) else ""
                                last_activity = f"כלי {tname}: {cmd[:90]}" if cmd else f"מפעיל כלי: {tname}"
                                break
                            if ptype == "text" and part.get("text", "").strip():
                                last_activity = part["text"].strip().splitlines()[0][:110]
                                break
        except OpenChamberError:
            pass

        return {
            "session_id": session_id,
            "model": model_key,
            "status": live_status,
            "outcome": sdata.get("outcome"),
            "cost_usd": round(cost_usd, 6),
            "cost_source": cost_source,
            "tokens": tokens,
            "assistant_turns": assistant_turns,
            "last_activity": last_activity,
            "updated_at_ms": (sdata.get("time") or {}).get("updated"),
        }

    def get_session_status(self, session_id: str, directory: str) -> str:
        """Return live status ('busy', 'idle', 'waiting', or 'unknown') for a session."""
        try:
            st_res = self.request_json("GET", "/api/sessions/status", directory=directory, timeout=6.0)
            sessions_map = st_res.get("sessions", {}) if isinstance(st_res, dict) else {}
            entry = sessions_map.get(session_id)
            if isinstance(entry, dict) and entry.get("status"):
                return str(entry["status"])
        except OpenChamberError:
            pass
        return "unknown"

    def send_prompt(
        self,
        session_id: str,
        prompt: str,
        *,
        directory: str,
        timeout: float = 900.0,
    ) -> Any:
        """Send a prompt/message to an existing OpenChamber session (e.g. wake-up callback)."""
        return self.request_json(
            "POST",
            f"/api/session/{urllib.parse.quote(session_id)}/prompt",
            body={"text": prompt},
            directory=directory,
            timeout=timeout,
        )

    def interrupt_session(self, session_id: str, directory: str) -> None:
        self.request_json(
            "POST",
            f"/api/session/{urllib.parse.quote(session_id)}/interrupt",
            directory=directory,
            timeout=8.0,
        )
