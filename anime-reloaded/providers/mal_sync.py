from __future__ import annotations

import time
import urllib.error

from . import mal_client


def _normalise_config(raw):
    config = dict(raw or {})
    config["enabled"] = config.get("enabled") is True
    config["autoPush"] = config.get("autoPush") is True
    config["clientId"] = str(config.get("clientId") or "").strip()
    config["clientSecret"] = str(config.get("clientSecret") or "").strip()
    config["redirectUri"] = str(config.get("redirectUri") or "").strip()
    config["codeVerifier"] = str(config.get("codeVerifier") or "").strip()
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
    config["codeVerifier"] = verifier
    config["authUrl"] = mal_client.build_authorize_url(
        config.get("clientId"),
        verifier,
        config.get("redirectUri"),
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
    me = _update_user_profile(config)
    return {
        "config": config,
        "user": {
            "name": str(me.get("name") or ""),
            "picture": str(me.get("picture") or ""),
        },
    }


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


def _mal_id_from_entry(entry):
    refs = (entry or {}).get("providerRefs") or {}
    sync_ref = refs.get("sync") or {}
    if str(sync_ref.get("provider") or "").strip() == "myanimelist" and sync_ref.get("id"):
        return str(sync_ref.get("id"))
    legacy = str((entry or {}).get("malId") or "").strip()
    return legacy


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
    status = (payload or {}).get("my_list_status") or {}
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


def push_library(config, library_entries):
    config = _normalise_config(config)
    results = []

    def _push(current_config):
        pushed = 0
        skipped = 0
        failed = 0
        for entry in library_entries or []:
            mal_id = _mal_id_from_entry(entry)
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
                failed += 1
                results.append({
                    "id": str((entry or {}).get("id") or ""),
                    "malId": mal_id,
                    "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                    "status": "error",
                    "reason": str(exc),
                })
        return {
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


def pull_library(config, library_entries):
    config = _normalise_config(config)
    results = []

    def _pull(current_config):
        next_library = []
        updated = 0
        skipped = 0
        failed = 0

        for entry in library_entries or []:
            mal_id = _mal_id_from_entry(entry)
            if not mal_id:
                skipped += 1
                next_library.append(dict(entry or {}))
                results.append({
                    "id": str((entry or {}).get("id") or ""),
                    "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                    "status": "skipped",
                    "reason": "No MyAnimeList mapping is available for this entry.",
                })
                continue

            try:
                remote = mal_client.get_anime_status(current_config.get("accessToken"), mal_id)
                merged, changed = _apply_remote_progress(entry, remote)
                next_library.append(merged)
                if changed:
                    updated += 1
                results.append({
                    "id": str((entry or {}).get("id") or ""),
                    "malId": mal_id,
                    "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                    "status": "updated" if changed else "unchanged",
                    "remoteStatus": str(((remote.get("my_list_status") or {}).get("status") or "")),
                    "watchedEpisodes": _remote_watched_episodes(remote),
                })
            except Exception as exc:
                failed += 1
                next_library.append(dict(entry or {}))
                results.append({
                    "id": str((entry or {}).get("id") or ""),
                    "malId": mal_id,
                    "title": str((entry or {}).get("englishName") or (entry or {}).get("name") or ""),
                    "status": "error",
                    "reason": str(exc),
                })

        return {
            "library": next_library,
            "summary": {
                "updated": updated,
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
