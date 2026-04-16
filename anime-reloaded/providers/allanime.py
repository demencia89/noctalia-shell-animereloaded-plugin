from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.request
from base64 import b64decode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .contracts import MetadataProvider, StreamProvider

API = "https://api.allanime.day/api"
REFERER = "https://allmanga.to"
AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
BASE = "allanime.day"

_Q_SHOWS = "query($search:SearchInput $limit:Int $page:Int $translationType:VaildTranslationTypeEnumType $countryOrigin:VaildCountryOriginEnumType){shows(search:$search limit:$limit page:$page translationType:$translationType countryOrigin:$countryOrigin){edges{_id name englishName nativeName thumbnail score type season availableEpisodes}}}"
_Q_EPISODES = "query($showId:String!){show(_id:$showId){_id name englishName description thumbnail availableEpisodesDetail lastEpisodeDate status}}"
_Q_STREAM = "query($showId:String! $translationType:VaildTranslationTypeEnumType! $episodeString:String!){episode(showId:$showId translationType:$translationType episodeString:$episodeString){episodeString sourceUrls}}"

_GENRES = [
    "Action", "Adventure", "Comedy", "Drama", "Ecchi", "Fantasy", "Horror",
    "Mahou Shoujo", "Mecha", "Music", "Mystery", "Psychological", "Romance",
    "Sci-Fi", "Slice of Life", "Sports", "Supernatural", "Thriller",
]

_PROVIDER_PRIORITY = {
    "auto": ["Default", "S-mp4", "Luf-Mp4", "Yt-mp4"],
    "default": ["Default", "S-mp4", "Luf-Mp4", "Yt-mp4"],
    "sharepoint": ["S-mp4", "Default", "Luf-Mp4", "Yt-mp4"],
    "hianime": ["Luf-Mp4", "Default", "S-mp4", "Yt-mp4"],
    "youtube": ["Yt-mp4", "Default", "S-mp4", "Luf-Mp4"],
}

_HEX = {
    "79": "A", "7a": "B", "7b": "C", "7c": "D", "7d": "E", "7e": "F", "7f": "G", "70": "H",
    "71": "I", "72": "J", "73": "K", "74": "L", "75": "M", "76": "N", "77": "O", "68": "P",
    "69": "Q", "6a": "R", "6b": "S", "6c": "T", "6d": "U", "6e": "V", "6f": "W", "60": "X",
    "61": "Y", "62": "Z", "59": "a", "5a": "b", "5b": "c", "5c": "d", "5d": "e", "5e": "f",
    "5f": "g", "50": "h", "51": "i", "52": "j", "53": "k", "54": "l", "55": "m", "56": "n",
    "57": "o", "48": "p", "49": "q", "4a": "r", "4b": "s", "4c": "t", "4d": "u", "4e": "v",
    "4f": "w", "40": "x", "41": "y", "42": "z", "08": "0", "09": "1", "0a": "2", "0b": "3",
    "0c": "4", "0d": "5", "0e": "6", "0f": "7", "00": "8", "01": "9", "15": "-", "16": ".",
    "67": "_", "46": "~", "02": ":", "17": "/", "07": "?", "1b": "#", "63": "[", "65": "]",
    "78": "@", "19": "!", "1c": "$", "1e": "&", "10": "(", "11": ")", "12": "*", "13": "+",
    "14": ",", "03": ";", "05": "=", "1d": "%",
}


def _decode_url(encoded):
    pairs = [encoded[i:i + 2] for i in range(0, len(encoded), 2)]
    return "".join(_HEX.get(pair, pair) for pair in pairs).replace("/clock", "/clock.json")


def _decode_tobeparsed_payload(payload):
    text = str(payload or "").strip()
    if not text:
        return None

    raw = b64decode(text)
    iv = raw[:12]
    encrypted = raw[12:]
    secret = "P7K2RGbFgauVtmiS"[::-1].encode("utf-8")
    key = sha256(secret).digest()
    decrypted = AESGCM(key).decrypt(iv, encrypted, None)
    return json.loads(decrypted.decode("utf-8"))


def _gql(variables, query):
    body = json.dumps({"variables": variables, "query": query}, separators=(",", ":")).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Referer": REFERER,
            "User-Agent": AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        parsed = json.loads(response.read().decode())

    data = parsed.get("data")
    if isinstance(data, dict) and isinstance(data.get("tobeparsed"), str):
        decoded = _decode_tobeparsed_payload(data.get("tobeparsed"))
        if decoded is not None:
            parsed["data"] = decoded
    return parsed



def _fetch(url):
    req = urllib.request.Request(
        url,
        headers={
            "Referer": REFERER,
            "User-Agent": AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.read().decode(errors="replace")


def _normalise(edge):
    thumb = edge.get("thumbnail") or ""
    avail = edge.get("availableEpisodes") or {}
    return {
        "id": edge.get("_id", ""),
        "name": edge.get("name", ""),
        "englishName": edge.get("englishName") or edge.get("name", ""),
        "nativeName": edge.get("nativeName", ""),
        "thumbnail": thumb,
        "score": edge.get("score"),
        "type": edge.get("type", ""),
        "availableEpisodes": {
            "sub": avail.get("sub", 0),
            "dub": avail.get("dub", 0),
            "raw": avail.get("raw", 0),
        },
        "season": edge.get("season"),
    }


def _parse_episode_number(value):
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _format_episode_number(value):
    number = _parse_episode_number(value)
    if number is None:
        return str(value or "").strip()
    if number.is_integer():
        return str(int(number))
    return ("%s" % number).rstrip("0").rstrip(".")


def _episode_sort_key(value):
    number = _parse_episode_number(value)
    if number is None:
        return -1
    return number


def _load_json_file(path, default):
    if not path:
        return default
    file_path = Path(path)
    if not file_path.exists():
        return default
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json_file(path, data):
    if not path:
        return
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _extract_episode_numbers(show_detail, mode):
    detail = (show_detail or {}).get("availableEpisodesDetail") or {}
    episodes = detail.get(mode) or []
    cleaned = []
    for episode in episodes:
        text = _format_episode_number(episode)
        if text:
            cleaned.append(text)
    return sorted(set(cleaned), key=_episode_sort_key)


def _extract_last_episode_date(show_detail, mode):
    detail = (show_detail or {}).get("lastEpisodeDate") or {}
    mode_value = detail.get(mode) or {}
    if not isinstance(mode_value, dict):
        return ""
    year = mode_value.get("year")
    month = mode_value.get("month")
    day = mode_value.get("date")
    hour = mode_value.get("hour", 0) or 0
    minute = mode_value.get("minute", 0) or 0
    if not year or not month or not day:
        return ""
    try:
        dt = datetime(int(year), int(month), int(day), int(hour), int(minute), tzinfo=timezone.utc)
    except Exception:
        return ""
    return dt.isoformat()


def _episode_cache_key(show_id, mode):
    return f"{show_id}:{mode}"


def _get_cached_episode_numbers(cache, show_id, mode, now_ts, ttl_seconds):
    entry = (cache or {}).get(_episode_cache_key(show_id, mode)) or {}
    fetched_at = float(entry.get("fetchedAt") or 0)
    if fetched_at <= 0 or (now_ts - fetched_at) > ttl_seconds:
        return None
    episodes = entry.get("episodes") or []
    last_episode_date = entry.get("lastEpisodeDate") or ""
    if not isinstance(episodes, list) or not episodes or not last_episode_date:
        return None
    return {
        "episodes": [_format_episode_number(ep) for ep in episodes if _format_episode_number(ep)],
        "thumbnail": entry.get("thumbnail") or "",
        "lastEpisodeDate": last_episode_date,
    }


def _store_cached_episode_numbers(cache, show_id, mode, episodes, thumbnail, last_episode_date, now_ts):
    cache[_episode_cache_key(show_id, mode)] = {
        "episodes": [_format_episode_number(ep) for ep in episodes if _format_episode_number(ep)],
        "thumbnail": thumbnail or "",
        "lastEpisodeDate": last_episode_date or "",
        "fetchedAt": now_ts,
    }


def _fetch_show_detail(show_id):
    data = _gql({"showId": show_id}, _Q_EPISODES)
    return (data.get("data") or {}).get("show") or {}


def _has_consistent_recent_history(entry, episode_numbers):
    watched_numbers = {
        _format_episode_number(value)
        for value in (entry.get("watchedEpisodes") or [])
        if _format_episode_number(value)
    }
    last_watched = _parse_episode_number(entry.get("lastWatchedEpNum"))
    if last_watched is None or last_watched <= 0:
        return False

    start = max(1, int(last_watched) - 4)
    end = int(last_watched)
    available_set = {_format_episode_number(ep) for ep in episode_numbers}

    for current in range(start, end + 1):
        label = str(current)
        if label not in available_set or label not in watched_numbers:
            return False
    return True


def _parse_iso_datetime(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_recent_enough(last_episode_date, days=90):
    dt = _parse_iso_datetime(last_episode_date)
    if dt is None:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return dt >= cutoff


def build_feed_items(library_entries, episode_map):
    items = []
    for entry in library_entries or []:
        show_id = entry.get("id") or ""
        if not show_id:
            continue
        last_watched = _parse_episode_number(entry.get("lastWatchedEpNum"))
        if last_watched is None or last_watched <= 0:
            continue

        episode_numbers = [
            _format_episode_number(ep)
            for ep in (episode_map.get(show_id) or {}).get("episodes", [])
            if _format_episode_number(ep)
        ]
        episode_numbers = sorted(set(episode_numbers), key=_episode_sort_key)
        if not episode_numbers:
            continue

        last_episode_date = (episode_map.get(show_id) or {}).get("lastEpisodeDate") or ""
        if not _is_recent_enough(last_episode_date):
            continue

        latest_available = _parse_episode_number(episode_numbers[-1])
        if latest_available is None or latest_available <= last_watched:
            continue

        gap = latest_available - last_watched
        if gap <= 0 or gap > 3:
            continue

        if not _has_consistent_recent_history(entry, episode_numbers):
            continue

        new_episodes = []
        for episode in episode_numbers:
            parsed = _parse_episode_number(episode)
            if parsed is not None and parsed > last_watched:
                new_episodes.append(episode)
        if not new_episodes:
            continue

        title = entry.get("englishName") or entry.get("name") or ""
        poster = entry.get("thumbnail") or (episode_map.get(show_id) or {}).get("thumbnail") or ""
        items.append({
            "id": show_id,
            "title": title,
            "poster": poster,
            "nextEpisode": _format_episode_number(new_episodes[0]),
            "newCount": len(new_episodes),
            "_sortGap": gap,
            "_sortLatest": latest_available,
        })

    items.sort(key=lambda item: (item["_sortGap"], -item["_sortLatest"], item["title"].lower()))
    for item in items:
        item.pop("_sortGap", None)
        item.pop("_sortLatest", None)
    return items


def _resolution_value(value):
    text = str(value or "").strip().lower()
    match = re.search(r"(\d+)", text)
    if match:
        try:
            return int(match.group(1))
        except Exception:
            return 0
    return 0


def _pick_quality(links, quality_pref):
    links = sorted(links, key=lambda pair: _resolution_value(pair[1]), reverse=True)
    if quality_pref == "best":
        return links[0]
    try:
        target = int(str(quality_pref).rstrip("p"))
    except Exception:
        return links[0]
    at_or_below = [pair for pair in links if _resolution_value(pair[1]) <= target]
    if at_or_below:
        return at_or_below[0]
    return links[-1]


def _json_unescape(value):
    text = str(value or "")
    try:
        return json.loads('"' + text.replace('"', '\\"') + '"')
    except Exception:
        return text.replace("\\/", "/").replace("\\u0026", "&")


def _normalise_variant_label(label, stream_type="mp4"):
    text = str(label or "").strip()
    lowered = text.lower()
    if stream_type == "hls" or lowered in ("hls", "m3u8", "auto"):
        return "Auto"
    return text or "Auto"


def _build_quality_variants(links):
    variants = []
    seen = set()
    for url, res in sorted(links, key=lambda pair: _resolution_value(pair[1]), reverse=True):
        url = _json_unescape(url)
        if "repackager.wixmp.com" in url:
            url = re.sub(r"repackager\.wixmp\.com/", "", url)
            url = re.sub(r"\.urlset.*", "", url)
        label = _normalise_variant_label(res, "mp4")
        key = (url, label)
        if key in seen:
            continue
        seen.add(key)
        variants.append({
            "url": url,
            "quality": label,
            "label": label,
            "type": "mp4",
        })
    return variants


def _is_direct_mp4_quality(label):
    text = str(label or "").strip().lower()
    return _resolution_value(text) > 0 or text in ("source", "default", "original")


def _stringify_error(exc):
    text = str(exc).strip()
    return text or exc.__class__.__name__


def _normalise_provider_failure(provider, reason):
    return {"provider": provider, "reason": reason}


def _summarise_provider_failures(failures):
    if not failures:
        return "No playable stream was available for this episode."
    summary = [f"{failure['provider']}: {failure['reason']}" for failure in failures[:3]]
    detail = "; ".join(summary)
    if len(failures) > 3:
        detail += f"; +{len(failures) - 3} more"
    if all(failure["reason"] == "source unavailable" for failure in failures):
        return "No compatible providers were available for this episode."
    return f"No playable stream was available for this episode. {detail}"


class AllAnimeMetadataProvider(MetadataProvider):
    provider_id = "allanime"

    def _decorate_show(self, show, mapping_cache, stream_provider_id):
        if mapping_cache is None:
            return show
        return mapping_cache.decorate_show(
            show,
            metadata_provider=self.provider_id,
            stream_provider=stream_provider_id or self.provider_id,
            stream_id=show.get("id") or "",
        )

    def _shows(self, search_obj, page, mode, country="ALL", mapping_cache=None, stream_provider_id=""):
        data = _gql(
            {
                "search": search_obj,
                "limit": 40,
                "page": page,
                "translationType": mode,
                "countryOrigin": country,
            },
            _Q_SHOWS,
        )
        edges = (data.get("data") or {}).get("shows", {}).get("edges") or []
        results = [
            self._decorate_show(_normalise(edge), mapping_cache, stream_provider_id or self.provider_id)
            for edge in edges
        ]
        return {"results": results, "hasNextPage": len(results) == 40}

    def _shows_with_fallbacks(self, search_variants, page, mode, country="ALL", mapping_cache=None, stream_provider_id=""):
        last_error = None
        for search_obj in search_variants:
            try:
                return self._shows(search_obj, page, mode, country, mapping_cache, stream_provider_id)
            except urllib.error.HTTPError as exc:
                if exc.code not in (400, 500):
                    raise
                last_error = exc
        if last_error:
            raise last_error
        raise RuntimeError("No working feed query variant found")

    def list_genres(self):
        return list(_GENRES)

    def popular(self, page=1, mode="sub", genre=None, mapping_cache=None, stream_provider_id=""):
        search = {"allowAdult": False, "allowUnknown": False}
        if genre:
            search["genres"] = [genre]
        return self._shows_with_fallbacks(
            [
                dict(search, sortBy="Top"),
                dict(search, sortBy="Popular"),
                dict(search, sortBy="Trending"),
                search,
            ],
            page,
            mode,
            mapping_cache=mapping_cache,
            stream_provider_id=stream_provider_id or self.provider_id,
        )

    def recent(self, page=1, mode="sub", country="ALL", mapping_cache=None, stream_provider_id=""):
        search = {"allowAdult": False, "allowUnknown": False}
        return self._shows_with_fallbacks(
            [
                dict(search, sortBy="Recent"),
                dict(search, sortBy="Latest_Update"),
                dict(search, sortBy="Trending"),
                search,
            ],
            page,
            mode,
            country,
            mapping_cache=mapping_cache,
            stream_provider_id=stream_provider_id or self.provider_id,
        )

    def latest(self, page=1, mode="sub", country="ALL", mapping_cache=None, stream_provider_id=""):
        return self.recent(page, mode, country, mapping_cache, stream_provider_id)

    def search(self, query, mode="sub", page=1, genre=None, mapping_cache=None, stream_provider_id=""):
        search = {"allowAdult": False, "allowUnknown": False, "query": query}
        if genre:
            search["genres"] = [genre]
        return self._shows(search, page, mode, mapping_cache=mapping_cache, stream_provider_id=stream_provider_id or self.provider_id)

    def episodes(self, show_id, mode="sub", mapping_cache=None, stream_provider_id=""):
        data = _gql({"showId": show_id}, _Q_EPISODES)
        show = (data.get("data") or {}).get("show") or {}
        detail = show.get("availableEpisodesDetail") or {}
        episodes = [{"id": f"{show_id}-episode-{ep}", "number": ep} for ep in detail.get(mode) or []]
        description = html.unescape(show.get("description") or "")
        description = re.sub(r"<[^>]+>", " ", description).strip()
        description = re.sub(r" {2,}", " ", description)
        payload = {
            "episodes": episodes,
            "episodeDetail": detail,
            "description": description,
            "thumbnail": show.get("thumbnail") or "",
        }
        if mapping_cache is not None:
            payload["providerRefs"] = mapping_cache.decorate_show(
                {"id": show_id},
                metadata_provider=self.provider_id,
                stream_provider=stream_provider_id or self.provider_id,
                stream_id=show_id,
            ).get("providerRefs", {})
        return payload

    def feed(self, library_entries, mode="sub", cache_path="", mapping_cache=None, stream_provider_id=""):
        cache = _load_json_file(cache_path, {}) if cache_path else {}
        if not isinstance(cache, dict):
            cache = {}

        now_ts = time.time()
        ttl_seconds = 300
        episode_map = {}

        for entry in library_entries or []:
            show_id = entry.get("id") or ""
            if not show_id:
                continue
            if mapping_cache is not None:
                mapping_cache.remember_show_mapping(self.provider_id, show_id, stream_provider_id or self.provider_id, show_id)

            cached_episodes = _get_cached_episode_numbers(cache, show_id, mode, now_ts, ttl_seconds)
            if cached_episodes is not None:
                episode_map[show_id] = {
                    "episodes": cached_episodes.get("episodes") or [],
                    "thumbnail": entry.get("thumbnail") or cached_episodes.get("thumbnail") or "",
                    "lastEpisodeDate": cached_episodes.get("lastEpisodeDate") or "",
                }
                continue

            show = _fetch_show_detail(show_id)
            episodes = _extract_episode_numbers(show, mode)
            thumbnail = show.get("thumbnail") or entry.get("thumbnail") or ""
            last_episode_date = _extract_last_episode_date(show, mode)
            _store_cached_episode_numbers(cache, show_id, mode, episodes, thumbnail, last_episode_date, now_ts)
            episode_map[show_id] = {
                "episodes": episodes,
                "thumbnail": thumbnail,
                "lastEpisodeDate": last_episode_date,
            }

        if cache_path:
            _save_json_file(cache_path, cache)
        return {"results": build_feed_items(library_entries, episode_map)}


class AllAnimeStreamProvider(StreamProvider):
    provider_id = "allanime"

    def resolve_episode_stream(
        self,
        show_id,
        ep_num,
        mode="sub",
        provider_pref="auto",
        quality_pref="best",
        mapping_cache=None,
        metadata_provider_id="",
    ):
        metadata_provider_id = metadata_provider_id or self.provider_id
        resolved_show_id = str(show_id or "")
        if mapping_cache is not None:
            resolved_show_id = mapping_cache.get_stream_show_id(
                metadata_provider_id,
                show_id,
                self.provider_id,
            )
        if not resolved_show_id:
            return {
                "error": f"No cached show mapping exists from {metadata_provider_id} to {self.provider_id}.",
                "code": "missing_provider_mapping",
                "providerFailures": [],
            }

        data = _gql(
            {
                "showId": resolved_show_id,
                "translationType": mode,
                "episodeString": ep_num,
            },
            _Q_STREAM,
        )

        episode = ((data.get("data") or {}).get("episode")) or {}
        source_urls = episode.get("sourceUrls") or []
        if not source_urls:
            return {
                "error": "This episode did not return any stream sources.",
                "code": "no_sources",
                "providerFailures": [],
            }

        sources = {}
        for source in source_urls:
            name = source.get("sourceName", "")
            url = source.get("sourceUrl", "")
            if name and url:
                sources[name] = url

        show_data = _gql({"showId": resolved_show_id}, _Q_EPISODES)
        show = (show_data.get("data") or {}).get("show") or {}
        title = show.get("englishName") or show.get("name") or "Unknown"
        metadata = {
            "title": title,
            "episode": ep_num,
            "showId": resolved_show_id,
            "requestedShowId": show_id,
            "metadataProvider": metadata_provider_id,
            "streamProvider": self.provider_id,
        }

        if mapping_cache is not None:
            mapping_cache.remember_show_mapping(metadata_provider_id, show_id, self.provider_id, resolved_show_id)

        provider_failures = []
        for provider in _PROVIDER_PRIORITY.get(provider_pref, _PROVIDER_PRIORITY["auto"]):
            raw = sources.get(provider)
            if not raw:
                provider_failures.append(_normalise_provider_failure(provider, "source unavailable"))
                continue
            if not raw.startswith("--"):
                provider_failures.append(_normalise_provider_failure(provider, "unsupported source format"))
                continue
            decoded = _decode_url(raw[2:])
            if not decoded:
                provider_failures.append(_normalise_provider_failure(provider, "failed to decode source"))
                continue
            provider_url = f"https://{BASE}{decoded}"

            try:
                response = _fetch(provider_url)
            except urllib.error.HTTPError as exc:
                provider_failures.append(_normalise_provider_failure(provider, f"HTTP {exc.code}"))
                continue
            except urllib.error.URLError as exc:
                provider_failures.append(
                    _normalise_provider_failure(provider, f"network error ({_stringify_error(exc.reason)})")
                )
                continue
            except Exception as exc:
                provider_failures.append(_normalise_provider_failure(provider, _stringify_error(exc)))
                continue

            headers = {
                "User-Agent": AGENT,
                "Referer": REFERER,
            }

            links = re.findall(r'"link":"([^"]+)"[^}]*"resolutionStr":"([^"]+)"', response)
            direct_mp4_links = [(url, res) for url, res in links if _is_direct_mp4_quality(res)]
            if direct_mp4_links:
                variants = _build_quality_variants(direct_mp4_links)
                url, res = _pick_quality([(item["url"], item["quality"]) for item in variants], quality_pref)
                return {
                    "url": url,
                    "referer": REFERER,
                    "type": "mp4",
                    "provider": provider,
                    "http_headers": headers,
                    "metadata": metadata,
                }

            if '"error"' in response.lower():
                provider_failures.append(_normalise_provider_failure(provider, "provider returned an error response"))
                continue

            hls = re.search(r'"url":"(https?://[^"]+master\.m3u8[^"]*)"', response)
            if hls:
                ref_match = re.search(r'"Referer":"([^"]+)"', response)
                final_url = _json_unescape(hls.group(1))
                final_referer = _json_unescape(ref_match.group(1)) if ref_match else REFERER
                headers["Referer"] = final_referer
                return {
                    "url": final_url,
                    "referer": final_referer,
                    "type": "hls",
                    "provider": provider,
                    "http_headers": headers,
                    "metadata": metadata,
                }

            provider_failures.append(_normalise_provider_failure(provider, "no playable links returned"))

        return {
            "error": _summarise_provider_failures(provider_failures),
            "code": "no_playable_stream",
            "providerFailures": provider_failures,
        }
