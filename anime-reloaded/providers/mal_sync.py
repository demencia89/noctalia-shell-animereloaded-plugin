from __future__ import annotations

import http.server
import socketserver
import time
import urllib.error
import urllib.parse

from . import mal_client
from .anilist import AniListMetadataProvider
from .anilist_client import gql


_Q_ANILIST_MAL_ID = """
query($id:Int){
  Media(id:$id, type:ANIME){
    id
    idMal
  }
}
""".strip()
_Q_ANILIST_MEDIA_BY_MAL_ID = """
query($idMal:Int){
  Media(idMal:$idMal, type:ANIME){
    id
    idMal
    title{romaji english native}
    synonyms
    season
    seasonYear
    status
    episodes
    format
    averageScore
    genres
    nextAiringEpisode{episode airingAt timeUntilAiring}
    coverImage{large medium}
    startDate{year month day}
  }
}
""".strip()
_Q_ANILIST_MEDIA_BY_MAL_IDS = """
query($ids:[Int]){
  Page(page:1, perPage:50){
    media(idMal_in:$ids, type:ANIME){
      id
      idMal
      title{romaji english native}
      synonyms
      season
      seasonYear
      status
      episodes
      format
      averageScore
      genres
      nextAiringEpisode{episode airingAt timeUntilAiring}
      coverImage{large medium}
      startDate{year month day}
    }
  }
}
""".strip()
_ANILIST_PROVIDER = AniListMetadataProvider()
_DEFAULT_MAL_CLIENT_ID = "831f9123c7e50037ce8c395ac713fff2"
_DEFAULT_MAL_REDIRECT_URI = "http://127.0.0.1:8787/animereloaded"
_LEGACY_LOCAL_REDIRECT_URIS = {
    "https://localhost:8787/animereloaded",
    "https://127.0.0.1:8787/animereloaded",
    "http://localhost:8787/animereloaded",
}
_BROWSER_AUTH_TIMEOUT_SECONDS = 240


def _normalise_config(raw):
    config = dict(raw or {})
    config["enabled"] = config.get("enabled") is True
    config["autoPush"] = config.get("autoPush") is True
    config["clientId"] = str(config.get("clientId") or _DEFAULT_MAL_CLIENT_ID).strip()
    config["clientSecret"] = str(config.get("clientSecret") or "").strip()
    redirect_uri = str(config.get("redirectUri") or "").strip()
    if not redirect_uri or redirect_uri in _LEGACY_LOCAL_REDIRECT_URIS:
        redirect_uri = _DEFAULT_MAL_REDIRECT_URI
    config["redirectUri"] = redirect_uri
    config["codeVerifier"] = str(config.get("codeVerifier") or "").strip()
    config["authState"] = str(config.get("authState") or "").strip()
    config["authUrl"] = str(config.get("authUrl") or "").strip()
    config["accessToken"] = str(config.get("accessToken") or "").strip()
    config["refreshToken"] = str(config.get("refreshToken") or "").strip()
    config["tokenType"] = str(config.get("tokenType") or "Bearer").strip() or "Bearer"
    config["expiresAt"] = int(config.get("expiresAt") or 0)
    config["userName"] = str(config.get("userName") or "").strip()
    config["userPicture"] = str(config.get("userPicture") or "").strip()
    config["lastSyncAt"] = int(config.get("lastSyncAt") or 0)
    config["lastSyncDirection"] = str(config.get("lastSyncDirection") or "").strip()
    return config


def _apply_token_payload(config, token_payload):
    config = _normalise_config(config)
    payload = token_payload or {}
    config["accessToken"] = str(payload.get("access_token") or "").strip()
    refresh_token = str(payload.get("refresh_token") or "").strip()
    if refresh_token:
        config["refreshToken"] = refresh_token
    config["tokenType"] = str(payload.get("token_type") or "Bearer").strip() or "Bearer"
    config["expiresAt"] = mal_client.token_expiry_timestamp(payload)
    return config


def _update_user_profile(config):
    me = mal_client.get_me(config.get("accessToken"))
    config["userName"] = str(me.get("name") or config.get("userName") or "").strip()
    config["userPicture"] = str(me.get("picture") or config.get("userPicture") or "").strip()
    return me


def _ensure_access_token(config):
    config = _normalise_config(config)
    access_token = config.get("accessToken") or ""
    refresh_token = config.get("refreshToken") or ""
    expires_at = int(config.get("expiresAt") or 0)
    now_ts = int(time.time())

    if access_token and (expires_at <= 0 or expires_at > (now_ts + 90)):
        return config

    if not refresh_token:
        raise RuntimeError("MyAnimeList access token is missing. Connect the account first.")

    token_payload = mal_client.refresh_access_token(
        config.get("clientId"),
        config.get("clientSecret"),
        refresh_token,
    )
    return _apply_token_payload(config, token_payload)


def _authorised_call(config, fn):
    config = _ensure_access_token(config)
    try:
        return config, fn(config)
    except urllib.error.HTTPError as exc:
        if exc.code != 401 or not config.get("refreshToken"):
            raise
    config = _apply_token_payload(
        config,
        mal_client.refresh_access_token(
            config.get("clientId"),
            config.get("clientSecret"),
            config.get("refreshToken"),
        ),
    )
    return config, fn(config)


def build_auth_url(config):
    config = _normalise_config(config)
    verifier = mal_client.generate_code_verifier()
    state = mal_client.generate_state()
    config["codeVerifier"] = verifier
    config["authState"] = state
    config["authUrl"] = mal_client.build_authorize_url(
        config.get("clientId"),
        verifier,
        config.get("redirectUri"),
        state,
    )
    return {
        "config": config,
        "authUrl": config["authUrl"],
        "codeVerifier": verifier,
    }


def exchange_code(config, code):
    config = _normalise_config(config)
    if not config.get("codeVerifier"):
        raise RuntimeError("Start MyAnimeList auth first so a code verifier is available.")
    token_payload = mal_client.exchange_code(
        config.get("clientId"),
        config.get("clientSecret"),
        code,
        config.get("codeVerifier"),
        config.get("redirectUri"),
    )
    config = _apply_token_payload(config, token_payload)
    config["enabled"] = True
    config["codeVerifier"] = ""
    config["authState"] = ""
    config["authUrl"] = ""
    me = _update_user_profile(config)
    return {
        "config": config,
        "user": {
            "name": str(me.get("name") or ""),
            "picture": str(me.get("picture") or ""),
        },
    }


def _validate_loopback_redirect(redirect_uri):
    parsed = urllib.parse.urlparse(str(redirect_uri or "").strip())
    if parsed.scheme != "http":
        raise RuntimeError("MyAnimeList browser login requires an http://127.0.0.1 loopback redirect URI.")
    if parsed.hostname not in ("127.0.0.1", "localhost"):
        raise RuntimeError("MyAnimeList browser login requires a localhost loopback redirect URI.")
    if not parsed.port:
        raise RuntimeError("The MyAnimeList redirect URI must include an explicit localhost port.")
    return parsed


def await_browser_login(config, timeout_seconds=_BROWSER_AUTH_TIMEOUT_SECONDS):
    config = _normalise_config(config)
    redirect_uri = config.get("redirectUri") or ""
    parsed = _validate_loopback_redirect(redirect_uri)
    expected_path = parsed.path or "/"
    expected_state = str(config.get("authState") or "").strip()
    if not config.get("codeVerifier"):
        raise RuntimeError("Start MyAnimeList auth first so a PKCE code verifier is available.")
    if not expected_state:
        raise RuntimeError("Start MyAnimeList auth first so an OAuth state token is available.")

    port = int(parsed.port)
    host = parsed.hostname or "127.0.0.1"
    timeout_at = time.time() + max(15, int(timeout_seconds or _BROWSER_AUTH_TIMEOUT_SECONDS))
    result = {"code": "", "state": "", "error": "", "error_description": ""}

    class _ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    class _CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            request_url = urllib.parse.urlparse(self.path)
            if request_url.path != expected_path:
                self.send_error(404)
                return

            params = urllib.parse.parse_qs(request_url.query or "", keep_blank_values=True)
            result["code"] = str((params.get("code") or [""])[0] or "").strip()
            result["state"] = str((params.get("state") or [""])[0] or "").strip()
            result["error"] = str((params.get("error") or [""])[0] or "").strip()
            result["error_description"] = str((params.get("error_description") or [""])[0] or "").strip()

            is_ok = bool(result["code"]) and result["state"] == expected_state and not result["error"]
            title = "AnimeReloaded Connected" if is_ok else "AnimeReloaded Login Failed"
            message = (
                "MyAnimeList is now connected. You can close this window."
                if is_ok else
                "AnimeReloaded could not finish the MyAnimeList login. You can close this window and try again."
            )
            body = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                f"<title>{title}</title>"
                "<style>"
                "body{font-family:system-ui,sans-serif;background:#0f1115;color:#f5f7fb;margin:0;padding:32px;}"
                ".card{max-width:560px;margin:0 auto;padding:28px;border-radius:20px;"
                "background:linear-gradient(180deg,#1a1f29,#131821);border:1px solid rgba(255,255,255,.08);}"
                "h1{margin:0 0 12px;font-size:24px;}p{margin:0;color:rgba(245,247,251,.78);line-height:1.5;}"
                "</style></head><body><div class='card'>"
                f"<h1>{title}</h1><p>{message}</p>"
                "</div></body></html>"
            ).encode("utf-8")

            self.send_response(200 if is_ok else 400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    try:
        server = _ThreadedServer((host, port), _CallbackHandler)
    except OSError as exc:
        raise RuntimeError(f"Could not start the MyAnimeList login callback listener on {host}:{port}.") from exc

    try:
        server.timeout = 0.5
        while time.time() < timeout_at:
            server.handle_request()
            if result["code"] or result["error"]:
                break
    finally:
        server.server_close()

    if result["error"]:
        reason = result["error_description"] or result["error"]
        raise RuntimeError(f"MyAnimeList login was not completed: {reason}")
    if not result["code"]:
        raise RuntimeError("Timed out waiting for the MyAnimeList browser login to finish.")
    if result["state"] != expected_state:
        raise RuntimeError("MyAnimeList login returned an invalid state token.")
    return exchange_code(config, result["code"])


def refresh_session(config):
    config = _ensure_access_token(config)
    me = _update_user_profile(config)
    return {
        "config": config,
        "user": {
            "name": str(me.get("name") or ""),
            "picture": str(me.get("picture") or ""),
        },
    }


def _with_mal_mapping(entry, mal_id):
    item = dict(entry or {})
    refs = dict(item.get("providerRefs") or {})
    refs["sync"] = {
        "provider": "myanimelist",
        "id": str(mal_id),
    }
    item["providerRefs"] = refs
    item["malId"] = str(mal_id)
    return item


def _anilist_mal_id(metadata_id, cache):
    media_id = str(metadata_id or "").strip()
    if not media_id or not media_id.isdigit():
        return ""
    if media_id in cache:
        return cache[media_id]
    data = gql(
        _Q_ANILIST_MAL_ID,
        {"id": int(media_id)},
        cache_scope="mal-sync-idmal",
        ttl_seconds=86400,
    )
    mal_id = str((((data or {}).get("Media") or {}).get("idMal")) or "").strip()
    cache[media_id] = mal_id
    return mal_id


def _mal_id_from_entry(entry, anilist_cache=None):
    refs = (entry or {}).get("providerRefs") or {}
    sync_ref = refs.get("sync") or {}
    if str(sync_ref.get("provider") or "").strip() == "myanimelist" and sync_ref.get("id"):
        mal_id = str(sync_ref.get("id"))
        return mal_id, _with_mal_mapping(entry, mal_id)

    legacy = str((entry or {}).get("malId") or "").strip()
    if legacy:
        return legacy, _with_mal_mapping(entry, legacy)

    metadata_ref = refs.get("metadata") or {}
    if str(metadata_ref.get("provider") or "").strip() == "anilist":
        mal_id = _anilist_mal_id(metadata_ref.get("id"), anilist_cache or {})
        if mal_id:
            return mal_id, _with_mal_mapping(entry, mal_id)

    return "", dict(entry or {})


def _mal_sync_reason(exc):
    if isinstance(exc, mal_client.MalApiError):
        if exc.is_content_filter:
            return "MyAnimeList rejected this title during sync. Remove it from the local test dataset or skip it for MAL sync."
        if exc.message:
            return exc.message
        if exc.code:
            return exc.code
    return str(exc)


def _parse_int(value):
    try:
        return int(float(str(value or "0").strip()))
    except Exception:
        return 0


def _local_watched_episodes(entry):
    watched = 0
    watched = max(watched, _parse_int((entry or {}).get("lastWatchedEpNum")))
    for value in (entry or {}).get("watchedEpisodes") or []:
        watched = max(watched, _parse_int(value))
    return watched


def _remote_watched_episodes(payload):
    status = (payload or {}).get("my_list_status") or (payload or {}).get("list_status") or {}
    return max(
        _parse_int(status.get("num_episodes_watched")),
        _parse_int(status.get("num_watched_episodes")),
    )


def _total_episode_count(entry, remote_payload=None):
    total = _parse_int((entry or {}).get("episodeCount"))
    if total > 0:
        return total
    total = _parse_int(((remote_payload or {}).get("num_episodes")))
    if total > 0:
        return total
    available = (entry or {}).get("availableEpisodes") or {}
    return max(
        _parse_int(available.get("sub")),
        _parse_int(available.get("raw")),
        _parse_int(available.get("dub")),
    )


def _local_status(entry, remote_payload=None):
    watched = _local_watched_episodes(entry)
    total = _total_episode_count(entry, remote_payload)
    if watched <= 0:
        return "plan_to_watch"
    if total > 0 and watched >= total:
        return "completed"
    return "watching"


def _apply_remote_progress(entry, remote_payload):
    item = dict(entry or {})
    watched = _remote_watched_episodes(remote_payload)
    list_status = (remote_payload or {}).get("my_list_status") or {}
    total = _total_episode_count(item, remote_payload)
    remote_status = str(list_status.get("status") or "").strip().lower()
    if remote_status == "completed" and total > watched:
        watched = total
    if watched <= 0:
        return item, False

    local_watched = _local_watched_episodes(item)
    if watched <= local_watched:
        return item, False

    watched_episodes = [str(number) for number in range(1, watched + 1)]
    progress = dict(item.get("episodeProgress") or {})
    for number in watched_episodes:
        progress.pop(number, None)

    item["lastWatchedEpNum"] = str(watched)
    item["lastWatchedEpId"] = ""
    item["watchedEpisodes"] = watched_episodes
    item["episodeProgress"] = progress
    item["updatedAt"] = int(time.time() * 1000)
    return item, True


def _remote_status_payload(remote_entry):
    item = dict(remote_entry or {})
    if item.get("my_list_status"):
        return item
    node = item.get("node") or {}
    item["id"] = node.get("id") or item.get("id")
    item["title"] = node.get("title") or item.get("title")
    item["num_episodes"] = node.get("num_episodes") or item.get("num_episodes")
    item["status"] = node.get("status") or item.get("status")
    item["media_type"] = node.get("media_type") or item.get("media_type")
    item["start_season"] = node.get("start_season") or item.get("start_season")
    item["alternative_titles"] = node.get("alternative_titles") or item.get("alternative_titles")
    item["main_picture"] = node.get("main_picture") or item.get("main_picture")
    item["my_list_status"] = item.get("list_status") or item.get("my_list_status") or {}
    return item


def _entry_title(entry):
    return str((entry or {}).get("englishName") or (entry or {}).get("name") or "").strip()


def _entry_metadata_id(entry):
    refs = (entry or {}).get("providerRefs") or {}
    metadata_ref = refs.get("metadata") or {}
    metadata_id = str(metadata_ref.get("id") or "").strip()
    if metadata_id:
        return metadata_id
    return str((entry or {}).get("id") or "").strip()


def _known_library_ids(entries, anilist_cache=None):
    metadata_ids = set()
    mal_ids = set()
    for entry in entries or []:
        metadata_id = _entry_metadata_id(entry)
        if metadata_id:
            metadata_ids.add(metadata_id)
        mal_id, _ = _mal_id_from_entry(entry, anilist_cache or {})
        if mal_id:
            mal_ids.add(str(mal_id))
    return metadata_ids, mal_ids


def _anilist_media_from_mal_id(mal_id, cache):
    mal_key = str(mal_id or "").strip()
    if not mal_key or not mal_key.isdigit():
        return {}
    if mal_key in cache:
        return cache[mal_key]
    data = gql(
        _Q_ANILIST_MEDIA_BY_MAL_ID,
        {"idMal": int(mal_key)},
        cache_scope="mal-sync-anilist-media",
        ttl_seconds=86400,
    )
    media = (data or {}).get("Media") or {}
    cache[mal_key] = media
    return media


def _prime_anilist_media_cache_for_mal_ids(mal_ids, cache):
    pending = []
    seen = set()
    for mal_id in mal_ids or []:
        key = str(mal_id or "").strip()
        if not key or not key.isdigit() or key in seen or key in cache:
            continue
        seen.add(key)
        pending.append(key)

    while pending:
        batch = pending[:50]
        pending = pending[50:]
        try:
            data = gql(
                _Q_ANILIST_MEDIA_BY_MAL_IDS,
                {"ids": [int(value) for value in batch]},
                cache_scope="mal-sync-anilist-media-batch",
                ttl_seconds=86400,
            )
        except Exception:
            for key in batch:
                _anilist_media_from_mal_id(key, cache)
            continue
        media_list = (((data or {}).get("Page") or {}).get("media")) or []
        for media in media_list:
            key = str((media or {}).get("idMal") or "").strip()
            if key:
                cache[key] = media
        for key in batch:
            cache.setdefault(key, {})


def _import_remote_library_entry(remote_entry, anilist_cache):
    remote_payload = _remote_status_payload(remote_entry)
    mal_id = str((remote_payload or {}).get("id") or "").strip()
    if not mal_id:
        raise RuntimeError("MyAnimeList list entry is missing an anime id.")

    media = _anilist_media_from_mal_id(mal_id, anilist_cache)
    if not media:
        raise RuntimeError("No AniList metadata mapping is available for this MyAnimeList title.")

    item = _ANILIST_PROVIDER._normalise_media(media)
    refs = dict(item.get("providerRefs") or {})
    refs["metadata"] = {
        "provider": "anilist",
        "id": str(item.get("id") or ""),
    }
    refs["sync"] = {
        "provider": "myanimelist",
        "id": mal_id,
    }
    item["providerRefs"] = refs
    item["lastWatchedEpId"] = ""
    item["lastWatchedEpNum"] = ""
    item["watchedEpisodes"] = []
    item["episodeProgress"] = {}
    item["updatedAt"] = int(time.time() * 1000)
    item, _ = _apply_remote_progress(item, remote_payload)
    return item


def push_library(config, library_entries):
    config = _normalise_config(config)
    results = []
    anilist_cache = {}

    def _push(current_config):
        pushed = 0
        skipped = 0
        failed = 0
        next_library = []
        for entry in library_entries or []:
            mal_id, mapped_entry = _mal_id_from_entry(entry, anilist_cache)
            next_library.append(mapped_entry)
            if not mal_id:
                skipped += 1
                results.append({
                    "id": str((entry or {}).get("id") or ""),
                    "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                    "status": "skipped",
                    "reason": "No MyAnimeList mapping is available for this entry.",
                })
                continue

            watched = _local_watched_episodes(entry)
            status = _local_status(entry)
            try:
                remote = mal_client.update_anime_list_status(
                    current_config.get("accessToken"),
                    mal_id,
                    status=status,
                    num_watched_episodes=watched,
                )
                pushed += 1
                results.append({
                    "id": str((entry or {}).get("id") or ""),
                    "malId": mal_id,
                    "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                    "status": "updated",
                    "remoteStatus": str((remote.get("status") or status)),
                    "watchedEpisodes": watched,
                })
            except Exception as exc:
                if isinstance(exc, mal_client.MalApiError) and exc.is_content_filter:
                    skipped += 1
                    results.append({
                        "id": str((entry or {}).get("id") or ""),
                        "malId": mal_id,
                        "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                        "status": "skipped",
                        "reason": _mal_sync_reason(exc),
                    })
                    continue
                failed += 1
                results.append({
                    "id": str((entry or {}).get("id") or ""),
                    "malId": mal_id,
                    "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                    "status": "error",
                    "reason": _mal_sync_reason(exc),
                })
        return {
            "library": next_library,
            "summary": {
                "updated": pushed,
                "skipped": skipped,
                "failed": failed,
            }
        }

    config, payload = _authorised_call(config, _push)
    _update_user_profile(config)
    config["lastSyncAt"] = int(time.time())
    config["lastSyncDirection"] = "push"
    payload["config"] = config
    payload["results"] = results
    return payload


def remove_anime_entry(config, mal_id, title=""):
    config = _normalise_config(config)
    mal_id = str(mal_id or "").strip()
    title = str(title or "").strip()
    if not mal_id or not mal_id.isdigit():
        raise RuntimeError("No MyAnimeList mapping is available for this title.")

    def _remove(current_config):
        mal_client.delete_anime_list_status(current_config.get("accessToken"), mal_id)
        return {
            "summary": {
                "removed": 1,
                "failed": 0,
            },
            "results": [{
                "malId": mal_id,
                "title": title,
                "status": "removed",
            }],
        }

    config, payload = _authorised_call(config, _remove)
    _update_user_profile(config)
    config["lastSyncAt"] = int(time.time())
    config["lastSyncDirection"] = "delete"
    payload["config"] = config
    return payload


def pull_library(config, library_entries):
    config = _normalise_config(config)
    results = []
    anilist_cache = {}

    def _pull(current_config):
        remote_entries = mal_client.get_user_animelist(current_config.get("accessToken"), "@me", limit=100)
        remote_by_mal_id = {}
        for remote_entry in remote_entries:
            remote_payload = _remote_status_payload(remote_entry)
            remote_mal_id = str((remote_payload or {}).get("id") or "").strip()
            if remote_mal_id:
                remote_by_mal_id[remote_mal_id] = remote_payload

        next_library = []
        updated = 0
        imported = 0
        skipped = 0
        failed = 0

        for entry in library_entries or []:
            mal_id, mapped_entry = _mal_id_from_entry(entry, anilist_cache)
            if not mal_id:
                skipped += 1
                next_library.append(mapped_entry)
                results.append({
                    "id": str((entry or {}).get("id") or ""),
                    "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                    "status": "skipped",
                    "reason": "No MyAnimeList mapping is available for this entry.",
                })
                continue

            try:
                remote = remote_by_mal_id.get(mal_id)
                if remote is None:
                    next_library.append(mapped_entry)
                    results.append({
                        "id": str((entry or {}).get("id") or ""),
                        "malId": mal_id,
                        "title": _entry_title(entry),
                        "status": "unchanged",
                        "reason": "This title is not present in the connected MyAnimeList library.",
                    })
                    continue
                merged, changed = _apply_remote_progress(mapped_entry, remote)
                next_library.append(merged)
                if changed:
                    updated += 1
                results.append({
                    "id": str((entry or {}).get("id") or ""),
                    "malId": mal_id,
                    "title": _entry_title(entry),
                    "status": "updated" if changed else "unchanged",
                    "remoteStatus": str(((remote.get("my_list_status") or {}).get("status") or "")),
                    "watchedEpisodes": _remote_watched_episodes(remote),
                })
            except Exception as exc:
                if isinstance(exc, mal_client.MalApiError) and exc.is_content_filter:
                    skipped += 1
                    next_library.append(mapped_entry)
                    results.append({
                        "id": str((entry or {}).get("id") or ""),
                        "malId": mal_id,
                        "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                        "status": "skipped",
                        "reason": _mal_sync_reason(exc),
                    })
                    continue
                failed += 1
                next_library.append(dict(entry or {}))
                results.append({
                    "id": str((entry or {}).get("id") or ""),
                    "malId": mal_id,
                    "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                    "status": "error",
                    "reason": _mal_sync_reason(exc),
                })

        known_metadata_ids, known_mal_ids = _known_library_ids(next_library, anilist_cache)
        _prime_anilist_media_cache_for_mal_ids(
            [mal_id for mal_id in remote_by_mal_id.keys() if mal_id not in known_mal_ids],
            anilist_cache,
        )
        for mal_id, remote in remote_by_mal_id.items():
            if mal_id in known_mal_ids:
                continue
            try:
                imported_entry = _import_remote_library_entry(remote, anilist_cache)
                metadata_id = _entry_metadata_id(imported_entry)
                if metadata_id and metadata_id in known_metadata_ids:
                    results.append({
                        "id": metadata_id,
                        "malId": mal_id,
                        "title": _entry_title(imported_entry),
                        "status": "unchanged",
                        "reason": "This AniList media is already present in the local library.",
                    })
                    continue
                next_library.append(imported_entry)
                imported += 1
                if metadata_id:
                    known_metadata_ids.add(metadata_id)
                known_mal_ids.add(mal_id)
                results.append({
                    "id": metadata_id,
                    "malId": mal_id,
                    "title": _entry_title(imported_entry),
                    "status": "imported",
                    "remoteStatus": str(((remote.get("my_list_status") or {}).get("status") or "")),
                    "watchedEpisodes": _remote_watched_episodes(remote),
                })
            except Exception as exc:
                if isinstance(exc, mal_client.MalApiError) and exc.is_content_filter:
                    skipped += 1
                    results.append({
                        "id": "",
                        "malId": mal_id,
                        "title": str((remote.get("title") or "")),
                        "status": "skipped",
                        "reason": _mal_sync_reason(exc),
                    })
                    continue
                skipped += 1
                results.append({
                    "id": "",
                    "malId": mal_id,
                    "title": str((remote.get("title") or "")),
                    "status": "skipped",
                    "reason": _mal_sync_reason(exc),
                })

        return {
            "library": next_library,
            "summary": {
                "updated": updated,
                "imported": imported,
                "skipped": skipped,
                "failed": failed,
            }
        }

    config, payload = _authorised_call(config, _pull)
    _update_user_profile(config)
    config["lastSyncAt"] = int(time.time())
    config["lastSyncDirection"] = "pull"
    payload["config"] = config
    payload["results"] = results
    return payload
