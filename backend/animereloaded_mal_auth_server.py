#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from providers import mal_client  # noqa: E402


HOST = os.environ.get("ANIMERELOADED_MAL_BIND", "0.0.0.0").strip() or "0.0.0.0"
PORT = int(os.environ.get("ANIMERELOADED_MAL_PORT", "18787") or 18787)
CLIENT_ID = os.environ.get("ANIMERELOADED_MAL_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("ANIMERELOADED_MAL_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.environ.get("ANIMERELOADED_MAL_REDIRECT_URI", "").strip()
DB_PATH = Path(
    os.environ.get(
        "ANIMERELOADED_MAL_DB",
        str(Path.home() / ".local" / "share" / "animereloaded-mal-auth" / "sessions.db"),
    )
)
AUTH_TTL_SECONDS = int(os.environ.get("ANIMERELOADED_MAL_AUTH_TTL", "900") or 900)


def _now():
    return int(time.time())


def _json_response(handler, status_code, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(int(status_code))
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler, status_code, title, message):
    body = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<style>"
        "body{font-family:system-ui,sans-serif;background:#0f1115;color:#f5f7fb;margin:0;padding:32px;}"
        ".card{max-width:640px;margin:0 auto;padding:28px;border-radius:20px;"
        "background:linear-gradient(180deg,#1a1f29,#131821);border:1px solid rgba(255,255,255,.08);}"
        "h1{margin:0 0 12px;font-size:24px;}p{margin:0;color:rgba(245,247,251,.78);line-height:1.6;}"
        "</style></head><body><div class='card'>"
        f"<h1>{title}</h1><p>{message}</p>"
        "</div></body></html>"
    ).encode("utf-8")
    handler.send_response(int(status_code))
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler):
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    if not raw.strip():
        return {}
    return json.loads(raw)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        self._harden_permissions()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists auth_sessions (
                    auth_id text primary key,
                    state text not null unique,
                    verifier text not null,
                    status text not null,
                    error text not null default '',
                    session_token text not null default '',
                    access_token text not null default '',
                    token_type text not null default 'Bearer',
                    expires_at integer not null default 0,
                    user_name text not null default '',
                    user_picture text not null default '',
                    created_at integer not null,
                    updated_at integer not null
                );

                create table if not exists sessions (
                    session_token text primary key,
                    refresh_token text not null,
                    user_name text not null default '',
                    user_picture text not null default '',
                    created_at integer not null,
                    updated_at integer not null
                );
                """
            )

    def _harden_permissions(self):
        try:
            self.path.parent.chmod(0o700)
        except Exception:
            pass
        try:
            if self.path.exists():
                self.path.chmod(0o600)
        except Exception:
            pass

    def cleanup(self):
        threshold = _now() - max(300, AUTH_TTL_SECONDS)
        with self._lock, self._connect() as conn:
            conn.execute(
                "delete from auth_sessions where updated_at < ?",
                (threshold,),
            )

    def create_auth_session(self):
        auth_id = secrets.token_urlsafe(24)
        state = secrets.token_urlsafe(24)
        verifier = mal_client.generate_code_verifier()
        now = _now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                insert into auth_sessions (
                    auth_id, state, verifier, status, created_at, updated_at
                ) values (?, ?, ?, 'pending', ?, ?)
                """,
                (auth_id, state, verifier, now, now),
            )
        return {
            "auth_id": auth_id,
            "state": state,
            "verifier": verifier,
            "created_at": now,
        }

    def get_auth_session(self, *, auth_id="", state=""):
        clause = ""
        value = ""
        if auth_id:
            clause = "auth_id = ?"
            value = str(auth_id)
        elif state:
            clause = "state = ?"
            value = str(state)
        else:
            return None
        with self._lock, self._connect() as conn:
            row = conn.execute(
                f"select * from auth_sessions where {clause} limit 1",
                (value,),
            ).fetchone()
        return dict(row) if row else None

    def consume_completed_auth_session(self, auth_id):
        token = str(auth_id or "").strip()
        if not token:
            return None

        with self._lock, self._connect() as conn:
            row = conn.execute(
                "select * from auth_sessions where auth_id = ? and status = 'complete' limit 1",
                (token,),
            ).fetchone()
            if not row:
                return None
            session = dict(row)
            conn.execute(
                """
                update auth_sessions
                set status = 'claimed',
                    session_token = '',
                    access_token = '',
                    updated_at = ?
                where auth_id = ?
                """,
                (_now(), token),
            )
        return session

    def fail_auth_session(self, auth_id, error):
        now = _now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                update auth_sessions
                set status = 'error', error = ?, updated_at = ?
                where auth_id = ?
                """,
                (str(error or "").strip(), now, str(auth_id)),
            )

    def complete_auth_session(self, auth_id, token_payload, user_payload):
        now = _now()
        session_token = secrets.token_urlsafe(32)
        refresh_token = str((token_payload or {}).get("refresh_token") or "").strip()
        access_token = str((token_payload or {}).get("access_token") or "").strip()
        token_type = str((token_payload or {}).get("token_type") or "Bearer").strip() or "Bearer"
        expires_at = mal_client.token_expiry_timestamp(token_payload)
        user_name = str((user_payload or {}).get("name") or "").strip()
        user_picture = str((user_payload or {}).get("picture") or "").strip()

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                insert into sessions (
                    session_token, refresh_token, user_name, user_picture, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (session_token, refresh_token, user_name, user_picture, now, now),
            )
            conn.execute(
                """
                update auth_sessions
                set status = 'complete',
                    error = '',
                    session_token = ?,
                    access_token = ?,
                    token_type = ?,
                    expires_at = ?,
                    user_name = ?,
                    user_picture = ?,
                    updated_at = ?
                where auth_id = ?
                """,
                (
                    session_token,
                    access_token,
                    token_type,
                    expires_at,
                    user_name,
                    user_picture,
                    now,
                    str(auth_id),
                ),
            )

        return {
            "sessionToken": session_token,
            "accessToken": access_token,
            "tokenType": token_type,
            "expiresAt": expires_at,
            "user": {
                "name": user_name,
                "picture": user_picture,
            },
        }

    def refresh_session(self, session_token):
        token = str(session_token or "").strip()
        if not token:
            raise RuntimeError("MyAnimeList backend session token is missing.")

        with self._lock, self._connect() as conn:
            row = conn.execute(
                "select * from sessions where session_token = ? limit 1",
                (token,),
            ).fetchone()
        if not row:
            raise RuntimeError("Unknown AnimeReloaded MyAnimeList backend session.")

        session = dict(row)
        token_payload = mal_client.refresh_access_token(
            CLIENT_ID,
            CLIENT_SECRET,
            session.get("refresh_token"),
        )
        refresh_token = str((token_payload or {}).get("refresh_token") or session.get("refresh_token") or "").strip()
        access_token = str((token_payload or {}).get("access_token") or "").strip()
        token_type = str((token_payload or {}).get("token_type") or "Bearer").strip() or "Bearer"
        expires_at = mal_client.token_expiry_timestamp(token_payload)
        now = _now()

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                update sessions
                set refresh_token = ?, updated_at = ?
                where session_token = ?
                """,
                (refresh_token, now, token),
            )

        return {
            "sessionToken": token,
            "accessToken": access_token,
            "tokenType": token_type,
            "expiresAt": expires_at,
            "user": {
                "name": str(session.get("user_name") or ""),
                "picture": str(session.get("user_picture") or ""),
            },
        }


STORE = Store(DB_PATH)


class Handler(BaseHTTPRequestHandler):
    server_version = "AnimeReloadedMalAuth/1.0"

    def do_GET(self):
        STORE.cleanup()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path or "/"

        if path == "/healthz":
            _json_response(self, 200, {"ok": True, "service": "animereloaded-mal-auth"})
            return

        if path.startswith("/api/v1/mal/auth/session/"):
            auth_id = path.rsplit("/", 1)[-1]
            session = STORE.get_auth_session(auth_id=auth_id)
            if not session:
                _json_response(self, 404, {"status": "error", "error": "Unknown MyAnimeList auth session."})
                return

            status = str(session.get("status") or "").strip().lower()
            if status == "complete":
                claimed = STORE.consume_completed_auth_session(auth_id)
                if not claimed:
                    _json_response(
                        self,
                        410,
                        {
                            "status": "claimed",
                            "error": "This MyAnimeList auth session was already claimed.",
                        },
                    )
                    return
                session = claimed
                _json_response(
                    self,
                    200,
                    {
                        "status": "complete",
                        "sessionToken": str(session.get("session_token") or ""),
                        "accessToken": str(session.get("access_token") or ""),
                        "tokenType": str(session.get("token_type") or "Bearer"),
                        "expiresAt": int(session.get("expires_at") or 0),
                        "user": {
                            "name": str(session.get("user_name") or ""),
                            "picture": str(session.get("user_picture") or ""),
                        },
                    },
                )
                return

            if status == "claimed":
                _json_response(
                    self,
                    410,
                    {
                        "status": "claimed",
                        "error": "This MyAnimeList auth session was already claimed.",
                    },
                )
                return

            if status == "error":
                _json_response(
                    self,
                    200,
                    {
                        "status": "error",
                        "error": str(session.get("error") or "MyAnimeList login failed."),
                    },
                )
                return

            _json_response(self, 200, {"status": "pending"})
            return

        if path == "/api/v1/mal/auth/callback":
            params = urllib.parse.parse_qs(parsed.query or "", keep_blank_values=True)
            state = str((params.get("state") or [""])[0] or "").strip()
            code = str((params.get("code") or [""])[0] or "").strip()
            error = str((params.get("error") or [""])[0] or "").strip()
            error_description = str((params.get("error_description") or [""])[0] or "").strip()

            session = STORE.get_auth_session(state=state)
            if not session:
                _html_response(
                    self,
                    400,
                    "AnimeReloaded Login Failed",
                    "This MyAnimeList login session is not valid anymore. Return to AnimeReloaded and try again.",
                )
                return

            session_status = str(session.get("status") or "").strip().lower()
            if session_status != "pending":
                _html_response(
                    self,
                    409,
                    "AnimeReloaded Login Failed",
                    "This MyAnimeList login session was already used or is no longer pending. Return to AnimeReloaded and start a new login.",
                )
                return

            if error:
                message = error_description or error
                STORE.fail_auth_session(session["auth_id"], message)
                _html_response(
                    self,
                    400,
                    "AnimeReloaded Login Failed",
                    "MyAnimeList did not complete the login. Return to AnimeReloaded and try again.",
                )
                return

            try:
                token_payload = mal_client.exchange_code(
                    CLIENT_ID,
                    CLIENT_SECRET,
                    code,
                    session["verifier"],
                    REDIRECT_URI,
                )
                user_payload = mal_client.get_me(str(token_payload.get("access_token") or ""))
                STORE.complete_auth_session(session["auth_id"], token_payload, user_payload)
            except Exception as exc:
                STORE.fail_auth_session(session["auth_id"], str(exc))
                _html_response(
                    self,
                    500,
                    "AnimeReloaded Login Failed",
                    "AnimeReloaded could not finish the MyAnimeList login on the server. Return to the app and try again.",
                )
                return

            _html_response(
                self,
                200,
                "AnimeReloaded Connected",
                "MyAnimeList is now connected to AnimeReloaded. You can close this window and return to the app.",
            )
            return

        _json_response(self, 404, {"error": "Not found."})

    def do_POST(self):
        STORE.cleanup()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path or "/"

        if path == "/api/v1/mal/auth/start":
            if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
                _json_response(
                    self,
                    500,
                    {"error": "Server is missing MyAnimeList client configuration."},
                )
                return
            session = STORE.create_auth_session()
            auth_url = mal_client.build_authorize_url(
                CLIENT_ID,
                session["verifier"],
                REDIRECT_URI,
                session["state"],
            )
            _json_response(
                self,
                200,
                {
                    "authSessionId": session["auth_id"],
                    "authUrl": auth_url,
                    "expiresIn": AUTH_TTL_SECONDS,
                },
            )
            return

        if path == "/api/v1/mal/auth/refresh":
            try:
                payload = _read_json(self)
            except Exception:
                _json_response(self, 400, {"error": "Invalid JSON body."})
                return
            try:
                result = STORE.refresh_session((payload or {}).get("sessionToken"))
            except Exception as exc:
                _json_response(self, 400, {"error": str(exc)})
                return
            _json_response(self, 200, result)
            return

        _json_response(self, 404, {"error": "Not found."})

    def log_message(self, fmt, *args):
        return


def main():
    if not CLIENT_ID:
        raise SystemExit("ANIMERELOADED_MAL_CLIENT_ID is required.")
    if not CLIENT_SECRET:
        raise SystemExit("ANIMERELOADED_MAL_CLIENT_SECRET is required.")
    if not REDIRECT_URI:
        raise SystemExit("ANIMERELOADED_MAL_REDIRECT_URI is required.")

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"AnimeReloaded MAL auth server listening on http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
