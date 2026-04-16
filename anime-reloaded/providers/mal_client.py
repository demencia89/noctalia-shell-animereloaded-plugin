from __future__ import annotations

import base64
import json
import secrets
import string
import time
import urllib.error
import urllib.parse
import urllib.request


AUTH_BASE = "https://myanimelist.net/v1/oauth2"
API_BASE = "https://api.myanimelist.net/v2"
AGENT = "AnimeReloaded/2.2"
_VERIFIER_ALPHABET = string.ascii_letters + string.digits + "-._~"


def generate_code_verifier(length=64):
    size = max(43, min(128, int(length or 64)))
    return "".join(secrets.choice(_VERIFIER_ALPHABET) for _ in range(size))


def build_authorize_url(client_id, code_verifier, redirect_uri=""):
    client_id = str(client_id or "").strip()
    code_verifier = str(code_verifier or "").strip()
    redirect_uri = str(redirect_uri or "").strip()
    if not client_id:
        raise RuntimeError("MyAnimeList client id is required.")
    if len(code_verifier) < 43:
        raise RuntimeError("MyAnimeList PKCE code verifier is missing or too short.")

    params = {
        "response_type": "code",
        "client_id": client_id,
        "code_challenge": code_verifier,
        "code_challenge_method": "plain",
    }
    if redirect_uri:
        params["redirect_uri"] = redirect_uri
    return AUTH_BASE + "/authorize?" + urllib.parse.urlencode(params)


def _auth_header(client_id, client_secret):
    client_id = str(client_id or "").strip()
    client_secret = str(client_secret or "").strip()
    if not client_id or not client_secret:
        return ""
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _token_request(client_id, client_secret, payload):
    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": AGENT,
    }
    auth = _auth_header(client_id, client_secret)
    if auth:
        headers["Authorization"] = auth
    request = urllib.request.Request(
        AUTH_BASE + "/token",
        data=encoded,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def exchange_code(client_id, client_secret, code, code_verifier, redirect_uri=""):
    payload = {
        "client_id": str(client_id or "").strip(),
        "grant_type": "authorization_code",
        "code": str(code or "").strip(),
        "code_verifier": str(code_verifier or "").strip(),
    }
    redirect_uri = str(redirect_uri or "").strip()
    if redirect_uri:
        payload["redirect_uri"] = redirect_uri
    return _token_request(client_id, client_secret, payload)


def refresh_access_token(client_id, client_secret, refresh_token):
    payload = {
        "client_id": str(client_id or "").strip(),
        "grant_type": "refresh_token",
        "refresh_token": str(refresh_token or "").strip(),
    }
    return _token_request(client_id, client_secret, payload)


def api_request(method, path, access_token, *, params=None, data=None):
    token = str(access_token or "").strip()
    if not token:
        raise RuntimeError("MyAnimeList access token is missing.")

    query_string = urllib.parse.urlencode(params or {}, doseq=True)
    url = API_BASE + path
    if query_string:
        url += "?" + query_string

    headers = {
        "Accept": "application/json",
        "User-Agent": AGENT,
        "Authorization": "Bearer " + token,
    }
    encoded_data = None
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")

    request = urllib.request.Request(url, data=encoded_data, headers=headers, method=method.upper())
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def get_me(access_token):
    return api_request("GET", "/users/@me", access_token, params={"fields": "picture"})


def get_anime_status(access_token, anime_id):
    return api_request(
        "GET",
        f"/anime/{int(anime_id)}",
        access_token,
        params={
            "fields": ",".join([
                "id",
                "title",
                "num_episodes",
                "status",
                "my_list_status",
                "alternative_titles",
                "start_season",
            ]),
        },
    )


def update_anime_list_status(access_token, anime_id, *, status="", num_watched_episodes=None):
    payload = {}
    if status:
        payload["status"] = str(status)
    if num_watched_episodes is not None:
        payload["num_watched_episodes"] = str(max(0, int(num_watched_episodes)))
    if not payload:
        raise RuntimeError("No MyAnimeList list fields were provided to update.")
    return api_request("PUT", f"/anime/{int(anime_id)}/my_list_status", access_token, data=payload)


def token_expiry_timestamp(token_payload):
    expires_in = int((token_payload or {}).get("expires_in") or 0)
    if expires_in <= 0:
        return 0
    return int(time.time()) + expires_in
