from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


API = "https://graphql.anilist.co"
AGENT = "AnimeReloaded/3.0"
_CACHE_PATH = Path(__file__).resolve().parent.parent / "anime-reloaded-anilist-cache.json"
_CACHE_VERSION = 1
_MAX_CACHE_ENTRIES = 512
_MIN_REQUEST_GAP_SECONDS = 0.35

_cache = None
_last_request_at = 0.0


def _load_cache():
    global _cache
    if _cache is not None:
        return _cache
    payload = {"version": _CACHE_VERSION, "entries": {}, "cooldownUntil": 0}
    if _CACHE_PATH.exists():
        try:
            raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload["entries"] = raw.get("entries") or {}
                payload["cooldownUntil"] = raw.get("cooldownUntil") or 0
        except Exception:
            pass
    _cache = payload
    return _cache


def _save_cache():
    if _cache is None:
        return
    try:
        _CACHE_PATH.write_text(
            json.dumps(_cache, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except Exception:
        pass


def _cache_key(scope, query, variables):
    payload = json.dumps(
        {
            "scope": str(scope or ""),
            "query": str(query or ""),
            "variables": variables or {},
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_entry(key):
    return (_load_cache().get("entries") or {}).get(key) or {}


def _get_cached_data(key, ttl_seconds, now_ts):
    entry = _get_entry(key)
    cached_at = int(entry.get("cachedAt") or 0)
    data = entry.get("data")
    if cached_at <= 0 or not isinstance(data, dict):
        return None
    if ttl_seconds > 0 and (now_ts - cached_at) > int(ttl_seconds):
        return None
    return data


def _get_stale_data(key):
    entry = _get_entry(key)
    data = entry.get("data")
    return data if isinstance(data, dict) else None


def _prune_cache(entries):
    if len(entries) <= _MAX_CACHE_ENTRIES:
        return entries
    ordered = sorted(
        entries.items(),
        key=lambda item: int((item[1] or {}).get("cachedAt") or 0),
        reverse=True,
    )
    return dict(ordered[:_MAX_CACHE_ENTRIES])


def _store_data(key, data, now_ts):
    cache = _load_cache()
    cache["entries"][key] = {
        "cachedAt": int(now_ts),
        "data": data if isinstance(data, dict) else {},
    }
    cache["entries"] = _prune_cache(cache["entries"])
    _save_cache()


def _read_retry_after(exc):
    headers = getattr(exc, "headers", None)
    if headers is None:
        return 0
    value = headers.get("Retry-After")
    try:
        return max(0, min(5, int(float(value or 0))))
    except Exception:
        return 0


def _sleep_for_rate_limit():
    global _last_request_at
    now = time.time()
    remaining = _MIN_REQUEST_GAP_SECONDS - (now - _last_request_at)
    if remaining > 0:
        time.sleep(remaining)
    _last_request_at = time.time()


def gql(query, variables=None, *, cache_scope="", ttl_seconds=300, allow_stale_on_error=True):
    key = _cache_key(cache_scope, query, variables or {})
    now_ts = int(time.time())
    cached = _get_cached_data(key, ttl_seconds, now_ts)
    if cached is not None:
        return cached

    cache = _load_cache()
    cooldown_until = int(cache.get("cooldownUntil") or 0)
    stale = _get_stale_data(key) if allow_stale_on_error else None
    if cooldown_until > now_ts and stale is not None:
        return stale

    last_error = None
    for attempt in range(2):
        try:
            _sleep_for_rate_limit()
            body = json.dumps(
                {"query": query, "variables": variables or {}},
                separators=(",", ":"),
            ).encode()
            req = urllib.request.Request(
                API,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": AGENT,
                },
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.loads(response.read().decode())
            if payload.get("errors"):
                message = "; ".join(
                    error.get("message") or "Unknown AniList error"
                    for error in payload["errors"]
                )
                raise RuntimeError(message)
            data = payload.get("data") or {}
            _store_data(key, data, time.time())
            cache["cooldownUntil"] = 0
            _save_cache()
            return data
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429:
                retry_after = _read_retry_after(exc) or (attempt + 1)
                cache["cooldownUntil"] = int(time.time()) + retry_after
                _save_cache()
                if attempt == 0:
                    time.sleep(retry_after)
                    continue
            elif 500 <= exc.code < 600 and attempt == 0:
                time.sleep(1)
                continue
            break
        except urllib.error.URLError as exc:
            last_error = exc
            break

    if stale is not None:
        return stale
    if last_error is not None:
        raise last_error
    raise RuntimeError("AniList request failed")
