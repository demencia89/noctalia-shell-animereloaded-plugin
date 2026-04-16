from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request


AGENT = "AnimeReloaded/3.0"


class MalBackendError(RuntimeError):
    def __init__(self, status_code=0, message="", body=""):
        self.status_code = int(status_code or 0)
        self.message = str(message or "").strip()
        self.body = str(body or "")
        super().__init__(self.message or "AnimeReloaded MAL backend request failed.")


def _request(base_url, method, path, payload=None):
    root = str(base_url or "").strip().rstrip("/")
    if not root:
        raise RuntimeError("MyAnimeList backend URL is not configured.")

    url = root + path
    headers = {
        "Accept": "application/json",
        "User-Agent": AGENT,
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        message = ""
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            message = str(payload.get("error") or payload.get("message") or "").strip()
        raise MalBackendError(exc.code, message=message or str(exc.reason or "Backend request failed."), body=body) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach the AnimeReloaded MAL backend at {root}.") from exc


def start_auth(base_url):
    return _request(base_url, "POST", "/api/v1/mal/auth/start", {})


def await_auth_session(base_url, auth_session_id, *, timeout_seconds=240):
    auth_session_id = str(auth_session_id or "").strip()
    if not auth_session_id:
        raise RuntimeError("MyAnimeList backend auth session id is missing.")

    deadline = time.time() + max(15, int(timeout_seconds or 240))
    path = "/api/v1/mal/auth/session/" + urllib.parse.quote(auth_session_id, safe="")
    while time.time() < deadline:
        payload = _request(base_url, "GET", path)
        status = str(payload.get("status") or "").strip().lower()
        if status in {"complete", "completed", "connected"}:
            if not str(payload.get("sessionToken") or "").strip():
                raise RuntimeError("MyAnimeList backend login completed without a usable session token.")
            if not str(payload.get("accessToken") or payload.get("access_token") or "").strip():
                raise RuntimeError("MyAnimeList backend login completed without a usable access token.")
            return payload
        if status == "error":
            raise RuntimeError(str(payload.get("error") or "MyAnimeList backend login failed.").strip())
        time.sleep(1.0)
    raise RuntimeError("Timed out waiting for the AnimeReloaded MyAnimeList backend login to finish.")


def refresh_session(base_url, session_token):
    token = str(session_token or "").strip()
    if not token:
        raise RuntimeError("MyAnimeList backend session token is missing.")
    return _request(
        base_url,
        "POST",
        "/api/v1/mal/auth/refresh",
        {"sessionToken": token},
    )
