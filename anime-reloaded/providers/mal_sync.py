from __future__ import annotations

import time
import urllib.error

from . import mal_backend
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
_LEGACY_DEFAULT_MAL_BACKEND_URLS = {
    "https://auth.bogglemind.top",
    "https://auth.bogglemind.top:8443",
}
_DEFAULT_MAL_BACKEND_URL = "https://dns.bogglemind.top:8443"
_BROWSER_AUTH_TIMEOUT_SECONDS = 240


def _normalise_config(raw):
    source = dict(raw or {})
    config = {
        "version": 2,
        "enabled": source.get("enabled") is True,
        "autoPush": source.get("autoPush") is True,
        "backendUrl": "",
        "backendAuthSessionId": "",
        "backendSessionToken": "",
        "userName": "",
        "userPicture": "",
        "lastSyncAt": 0,
        "lastSyncDirection": "",
    }
    backend_url = str(source.get("backendUrl") or "").strip().rstrip("/")
    if not backend_url or backend_url in _LEGACY_DEFAULT_MAL_BACKEND_URLS:
        backend_url = _DEFAULT_MAL_BACKEND_URL
    config["backendUrl"] = backend_url
    config["backendAuthSessionId"] = str(source.get("backendAuthSessionId") or "").strip()
    config["backendSessionToken"] = str(source.get("backendSessionToken") or "").strip()
    config["userName"] = str(source.get("userName") or "").strip()
    config["userPicture"] = str(source.get("userPicture") or "").strip()
    config["lastSyncAt"] = int(source.get("lastSyncAt") or 0)
    config["lastSyncDirection"] = str(source.get("lastSyncDirection") or "").strip()
    return config


def _apply_backend_token_payload(config, token_payload):
    config = dict(_normalise_config(config))
    payload = token_payload or {}
    config["accessToken"] = str(payload.get("accessToken") or payload.get("access_token") or "").strip()
    config["tokenType"] = str(payload.get("tokenType") or payload.get("token_type") or "Bearer").strip() or "Bearer"
    expires_at = int(payload.get("expiresAt") or 0)
    if expires_at <= 0:
        config["expiresAt"] = mal_client.token_expiry_timestamp({
            "expires_in": int(payload.get("expiresIn") or payload.get("expires_in") or 0),
        })
    else:
        config["expiresAt"] = expires_at
    return config


def _config_for_save(config):
    return _normalise_config(config)


def _using_backend(config):
    return bool(str((config or {}).get("backendUrl") or "").strip())


def _update_user_profile(config):
    me = mal_client.get_me(config.get("accessToken"))
    config["userName"] = str(me.get("name") or config.get("userName") or "").strip()
    config["userPicture"] = str(me.get("picture") or config.get("userPicture") or "").strip()
    return me


def _ensure_access_token(config):
    config = _normalise_config(config)
    access_token = config.get("accessToken") or ""
    backend_session_token = config.get("backendSessionToken") or ""
    expires_at = int(config.get("expiresAt") or 0)
    now_ts = int(time.time())

    if access_token and (expires_at <= 0 or expires_at > (now_ts + 90)):
        return config

    if not _using_backend(config):
        raise RuntimeError("MyAnimeList backend URL is not configured.")
    if not backend_session_token:
        raise RuntimeError("MyAnimeList backend session is missing. Connect the account first.")
    token_payload = mal_backend.refresh_session(
        config.get("backendUrl"),
        backend_session_token,
    )
    return _apply_backend_token_payload(config, token_payload)


def _authorised_call(config, fn):
    config = _ensure_access_token(config)
    try:
        return config, fn(config)
    except urllib.error.HTTPError as exc:
        if exc.code != 401 or not config.get("backendSessionToken"):
            raise
    config = _ensure_access_token(
        dict(config, accessToken="", tokenType="", expiresAt=0),
    )
    return config, fn(config)


def build_auth_url(config):
    config = _normalise_config(config)
    if not _using_backend(config):
        raise RuntimeError("MyAnimeList backend URL is not configured.")
    payload = mal_backend.start_auth(config.get("backendUrl"))
    auth_session_id = str(payload.get("authSessionId") or "").strip()
    auth_url = str(payload.get("authUrl") or "").strip()
    if not auth_session_id or not auth_url:
        raise RuntimeError("The MyAnimeList backend did not return a valid browser login session.")
    config["backendAuthSessionId"] = auth_session_id
    return {
        "config": _config_for_save(config),
        "authUrl": auth_url,
    }


def await_browser_login(config, timeout_seconds=_BROWSER_AUTH_TIMEOUT_SECONDS):
    config = _normalise_config(config)
    session_id = str(config.get("backendAuthSessionId") or "").strip()
    if not session_id:
        raise RuntimeError("Start MyAnimeList auth first so a backend browser session is available.")
    payload = mal_backend.await_auth_session(
        config.get("backendUrl"),
        session_id,
        timeout_seconds=timeout_seconds,
    )
    config = _apply_backend_token_payload(config, payload)
    backend_session_token = str(payload.get("sessionToken") or "").strip()
    if not backend_session_token:
        raise RuntimeError("MyAnimeList backend login did not return a usable session token.")
    if not config.get("accessToken"):
        raise RuntimeError("MyAnimeList backend login did not return a usable access token.")
    config["enabled"] = True
    config["backendAuthSessionId"] = ""
    config["backendSessionToken"] = backend_session_token
    user = payload.get("user") or {}
    config["userName"] = str(user.get("name") or config.get("userName") or "").strip()
    config["userPicture"] = str(user.get("picture") or config.get("userPicture") or "").strip()
    return {
        "config": _config_for_save(config),
        "user": {
            "name": config["userName"],
            "picture": config["userPicture"],
        },
    }


def refresh_session(config):
    config = _ensure_access_token(config)
    me = _update_user_profile(config)
    return {
        "config": _config_for_save(config),
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


def _normalise_list_status(value):
    status = str(value or "").strip().lower()
    if status in {"plan_to_watch", "watching", "completed", "on_hold", "dropped"}:
        return status
    return ""


def _normalise_user_action(value):
    action = str(value or "").strip().lower()
    if action in {"play", "pause", "drop", "complete"}:
        return action
    return ""


def _normalise_episode_count(value):
    parsed = _parse_int(value)
    if parsed <= 0:
        return 0
    return parsed


def _has_saved_progress(entry):
    progress = dict((entry or {}).get("episodeProgress") or {})
    for value in progress.values():
        if isinstance(value, dict):
            position = _parse_int(value.get("position"))
        else:
            position = _parse_int(value)
        if position > 0:
            return True
    return False


def _status_signal_watched_episodes(entry):
    watched = _local_watched_episodes(entry)
    if watched <= 0 and _has_saved_progress(entry):
        watched = 1
    return watched


def update_anime_status(*, watched_episodes=0, total_episodes=0, user_action=None, current_status=""):
    status = _normalise_list_status(current_status)
    watched = _normalise_episode_count(watched_episodes)
    total = _normalise_episode_count(total_episodes)
    action = _normalise_user_action(user_action)

    if total > 0 and watched > total:
        watched = total

    if action == "complete":
        if total > 0:
            watched = total
        return {
            "status": "completed",
            "watchedEpisodes": watched,
        }

    if action == "pause":
        return {
            "status": "on_hold",
            "watchedEpisodes": watched,
        }

    if action == "drop":
        return {
            "status": "dropped",
            "watchedEpisodes": watched,
        }

    if action == "play":
        if watched <= 0:
            return {
                "status": "plan_to_watch",
                "watchedEpisodes": 0,
            }
        if total > 0 and watched >= total:
            return {
                "status": "completed",
                "watchedEpisodes": total,
            }
        return {
            "status": "watching",
            "watchedEpisodes": watched,
        }

    if status in {"on_hold", "dropped"}:
        return {
            "status": status,
            "watchedEpisodes": watched,
        }

    if watched <= 0:
        return {
            "status": "plan_to_watch",
            "watchedEpisodes": 0,
        }

    if total > 0 and watched >= total:
        return {
            "status": "completed",
            "watchedEpisodes": total,
        }

    if status == "completed" and total <= 0:
        return {
            "status": "completed",
            "watchedEpisodes": watched,
        }

    return {
        "status": "watching",
        "watchedEpisodes": watched,
    }


def build_mal_payload(anime_id, status, watched_episodes):
    watched = _normalise_episode_count(watched_episodes)
    resolved_status = _normalise_list_status(status)
    if not resolved_status:
        resolved_status = "watching" if watched > 0 else "plan_to_watch"
    if resolved_status == "plan_to_watch":
        watched = 0
    return {
        "anime_id": str(anime_id or "").strip(),
        "status": resolved_status,
        "num_watched_episodes": watched,
    }


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
    resolved = update_anime_status(
        current_status=(entry or {}).get("listStatus"),
        watched_episodes=_status_signal_watched_episodes(entry),
        total_episodes=_total_episode_count(entry, remote_payload),
    )
    return resolved["status"]


def _apply_remote_progress(entry, remote_payload):
    item = dict(entry or {})
    list_status = (remote_payload or {}).get("my_list_status") or {}
    total = _total_episode_count(item, remote_payload)
    remote_status = _normalise_list_status(list_status.get("status"))
    remote_state = update_anime_status(
        current_status=remote_status,
        watched_episodes=_remote_watched_episodes(remote_payload),
        total_episodes=total,
        user_action="complete" if remote_status == "completed" else None,
    )
    original_state = update_anime_status(
        current_status=item.get("listStatus"),
        watched_episodes=_status_signal_watched_episodes(item),
        total_episodes=total,
    )
    watched = int(remote_state.get("watchedEpisodes") or 0)
    status_changed = (
        original_state.get("status") != remote_state.get("status")
        or int(original_state.get("watchedEpisodes") or 0) != watched
    )

    item["listStatus"] = remote_state.get("status") or "plan_to_watch"
    item["lastWatchedEpId"] = ""

    if watched <= 0:
        item["lastWatchedEpNum"] = ""
        item["watchedEpisodes"] = []
        item["episodeProgress"] = {}
        if status_changed:
            item["updatedAt"] = int(time.time() * 1000)
        return item, status_changed

    watched_episodes = [str(number) for number in range(1, watched + 1)]
    progress = dict(item.get("episodeProgress") or {})
    for number in list(progress.keys()):
        if _parse_int(number) <= watched:
            progress.pop(number, None)

    item["watchedEpisodes"] = watched_episodes
    item["lastWatchedEpNum"] = str(watched)
    item["episodeProgress"] = progress
    if status_changed:
        item["updatedAt"] = int(time.time() * 1000)
    return item, status_changed


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

            total = _total_episode_count(entry)
            state = update_anime_status(
                current_status=(entry or {}).get("listStatus"),
                watched_episodes=_status_signal_watched_episodes(entry),
                total_episodes=total,
            )
            payload = build_mal_payload(mal_id, state.get("status"), _local_watched_episodes(entry))
            try:
                remote = mal_client.update_anime_list_status(
                    current_config.get("accessToken"),
                    payload["anime_id"],
                    status=payload["status"],
                    num_watched_episodes=payload["num_watched_episodes"],
                )
                pushed += 1
                results.append({
                    "id": str((entry or {}).get("id") or ""),
                    "malId": mal_id,
                    "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                    "status": "updated",
                    "remoteStatus": str((remote.get("status") or payload["status"])),
                    "watchedEpisodes": payload["num_watched_episodes"],
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
    payload["config"] = _config_for_save(config)
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
    payload["config"] = _config_for_save(config)
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
    payload["config"] = _config_for_save(config)
    payload["results"] = results
    return payload
