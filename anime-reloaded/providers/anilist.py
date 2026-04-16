from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher

from .allanime import AllAnimeMetadataProvider
from .anilist_allanime_mapper import AniListAllAnimeMapper
from .anilist_client import gql
from .contracts import MetadataProvider

_Q_GENRES = "query{GenreCollection}"
_Q_PAGE_BASE = """
query($page:Int,$perPage:Int,$search:String,$sort:[MediaSort]){
  Page(page:$page, perPage:$perPage){
    pageInfo{hasNextPage}
    media(type:ANIME, search:$search, sort:$sort, isAdult:false){
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
_Q_PAGE_GENRE = """
query($page:Int,$perPage:Int,$search:String,$sort:[MediaSort],$genre:String){
  Page(page:$page, perPage:$perPage){
    pageInfo{hasNextPage}
    media(type:ANIME, search:$search, sort:$sort, genre:$genre, isAdult:false){
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
_Q_PAGE_RELEASING = """
query($page:Int,$perPage:Int,$search:String,$sort:[MediaSort]){
  Page(page:$page, perPage:$perPage){
    pageInfo{hasNextPage}
    media(type:ANIME, search:$search, sort:$sort, status:RELEASING, isAdult:false){
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
_Q_MEDIA = """
query($id:Int){
  Media(id:$id, type:ANIME){
    id
    idMal
    title{romaji english native}
    synonyms
    description(asHtml:false)
    episodes
    duration
    status
    format
    season
    seasonYear
    averageScore
    genres
    bannerImage
    coverImage{extraLarge large medium color}
    startDate{year month day}
    endDate{year month day}
    nextAiringEpisode{episode airingAt timeUntilAiring}
    relations{
      edges{relationType}
      nodes{
        id
        title{romaji english native}
        status
        format
        season
        seasonYear
      }
    }
  }
}
""".strip()
_Q_RELATION_STEP = """
query($id:Int){
  Media(id:$id, type:ANIME){
    id
    idMal
    title{romaji english native}
    status
    format
    season
    seasonYear
    coverImage{large medium}
    relations{
      edges{relationType}
      nodes{
        id
        title{romaji english native}
        status
        format
        season
        seasonYear
      }
    }
  }
}
""".strip()
_Q_FEED_BATCH = """
query($ids:[Int]){
  Page(page:1, perPage:50){
    media(id_in:$ids, type:ANIME){
      id
      idMal
      title{romaji english native}
      synonyms
      status
      episodes
      format
      averageScore
      season
      seasonYear
      nextAiringEpisode{episode airingAt timeUntilAiring}
      coverImage{large medium}
      startDate{year month day}
    }
  }
}
""".strip()
_SEASON_RELATION_TYPES = {"PREQUEL", "SEQUEL"}
_SEASON_FORMATS = {"TV", "TV_SHORT", "ONA", "OVA", "SPECIAL"}
_SEASON_ORDER = {
    "WINTER": 1,
    "SPRING": 2,
    "SUMMER": 3,
    "FALL": 4,
}


def _title_case_season(value):
    text = str(value or "").strip().title()
    return text or None


def _score_value(value):
    try:
        return round(float(value) / 10.0, 2)
    except Exception:
        return None


def _season_object(media):
    year = media.get("seasonYear")
    quarter = _title_case_season(media.get("season"))
    if not year and not quarter:
        return None
    return {"quarter": quarter, "year": year}


def _estimate_available_count(media):
    next_airing = media.get("nextAiringEpisode") or {}
    try:
        next_episode = int(next_airing.get("episode") or 0)
    except Exception:
        next_episode = 0
    if next_episode > 1:
        return next_episode - 1
    try:
        return int(media.get("episodes") or 0)
    except Exception:
        return 0


def _clean_description(value):
    text = html.unescape(str(value or "")).strip()
    return text.replace("<br>", "\n").replace("<br><br>", "\n\n")


def _normalise_relation(edge, node):
    title = node.get("title") or {}
    return {
        "id": str(node.get("id") or ""),
        "relationType": edge.get("relationType") or "",
        "name": title.get("romaji") or title.get("english") or title.get("native") or "",
        "englishName": title.get("english") or title.get("romaji") or title.get("native") or "",
        "nativeName": title.get("native") or "",
        "status": node.get("status") or "",
        "type": node.get("format") or "",
        "season": {
            "quarter": _title_case_season(node.get("season")),
            "year": node.get("seasonYear"),
        } if (node.get("season") or node.get("seasonYear")) else None,
    }


def _status_label(value):
    text = str(value or "").strip().replace("_", " ").title()
    return text or ""


def _airing_summary(media):
    next_airing = media.get("nextAiringEpisode") or {}
    try:
        next_episode = int(next_airing.get("episode") or 0)
    except Exception:
        next_episode = 0
    if media.get("status") == "RELEASING" and next_episode > 1:
        latest_episode = next_episode - 1
        return f"Episode {latest_episode} has aired"
    if media.get("status") == "RELEASING":
        return "Currently airing"
    return _status_label(media.get("status"))


def _clean_title(value):
    text = str(value or "").lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _media_title_variants(media):
    title = media.get("title") or {}
    values = [
        title.get("english"),
        title.get("romaji"),
        title.get("native"),
        media.get("englishName"),
        media.get("name"),
        media.get("nativeName"),
    ]
    values.extend((media.get("synonyms") or [])[:8])

    seen = set()
    variants = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = _clean_title(text)
        if not key or key in seen:
            continue
        seen.add(key)
        variants.append(text)
    return variants


def _search_relevance(query, media):
    query_text = _clean_title(query)
    if not query_text:
        return 0.0

    query_tokens = [token for token in query_text.split(" ") if token]
    title_scores = []
    for title in _media_title_variants(media):
        candidate = _clean_title(title)
        if not candidate:
            continue
        candidate_tokens = [token for token in candidate.split(" ") if token]
        ratio = SequenceMatcher(None, query_text, candidate).ratio()
        contains_phrase = query_text in candidate
        exact_match = query_text == candidate
        token_hits = sum(1 for token in query_tokens if token in candidate_tokens)
        token_coverage = (float(token_hits) / float(len(query_tokens))) if query_tokens else 0.0
        starts_with = candidate.startswith(query_text)

        score = ratio * 45.0
        score += token_coverage * 35.0
        if exact_match:
            score += 40.0
        if contains_phrase:
            score += 24.0
        if starts_with:
            score += 8.0
        if len(query_tokens) == 1 and query_text not in candidate_tokens and not contains_phrase:
            score -= 20.0
        title_scores.append(score)
    return max(title_scores or [0.0])


def _filter_search_results(query, media_list):
    query_text = str(query or "").strip()
    if not query_text:
        return media_list

    ranked = []
    for media in media_list or []:
        ranked.append((_search_relevance(query_text, media), media))
    ranked.sort(key=lambda item: (item[0], item[1].get("averageScore") or item[1].get("score") or 0), reverse=True)

    filtered = [media for score, media in ranked if score >= 45.0]
    return filtered if filtered else [media for _, media in ranked]


def _library_stream_ref(entry):
    refs = entry.get("providerRefs") or {}
    stream_ref = refs.get("stream") or {}
    if stream_ref.get("provider") and stream_ref.get("id"):
        return {
            "provider": str(stream_ref.get("provider")),
            "id": str(stream_ref.get("id")),
        }

    metadata_ref = refs.get("metadata") or {}
    metadata_provider = str(metadata_ref.get("provider") or "").strip()
    metadata_id = str(metadata_ref.get("id") or "").strip()
    if metadata_provider == "allanime" and metadata_id:
        return {"provider": "allanime", "id": metadata_id}

    entry_id = str(entry.get("id") or "").strip()
    if not metadata_provider and entry_id:
        return {"provider": "allanime", "id": entry_id}
    return {}


def _release_text(latest_released, next_episode, airing_at, now_ts):
    if latest_released <= 0:
        return "Currently airing"
    if airing_at and airing_at > now_ts and next_episode > latest_released:
        return f"Episode {latest_released} aired; episode {next_episode} is scheduled next."
    return f"Episode {latest_released} aired recently."


def _entry_last_watched(entry):
    try:
        return int(float(str((entry or {}).get("lastWatchedEpNum") or "0")))
    except Exception:
        return 0


def _entry_list_status(entry):
    value = str((entry or {}).get("listStatus") or "").strip().lower()
    if value in ("watching", "completed", "on_hold", "dropped", "plan_to_watch"):
        return value
    return "plan_to_watch"


def _follow_mode(entry):
    value = str((entry or {}).get("feedFollowMode") or "auto").strip().lower()
    if value in ("following", "muted"):
        return value
    return "auto"


def _feed_tracking_state(entry, latest_released, next_episode):
    last_watched = _entry_last_watched(entry)
    if last_watched <= 0:
        return {
            "eligible": False,
            "status": _entry_list_status(entry),
            "followMode": _follow_mode(entry),
            "lastWatched": last_watched,
            "releaseGap": max(0, int(latest_released) - last_watched),
            "nextGap": max(0, int(next_episode) - last_watched),
            "upcomingEligible": False,
        }

    follow_mode = _follow_mode(entry)
    status = _entry_list_status(entry)
    release_gap = max(0, int(latest_released) - last_watched)
    next_gap = max(0, int(next_episode) - last_watched)

    if follow_mode == "muted":
        return {
            "eligible": False,
            "status": status,
            "followMode": follow_mode,
            "lastWatched": last_watched,
            "releaseGap": release_gap,
            "nextGap": next_gap,
            "upcomingEligible": False,
        }

    manually_following = follow_mode == "following"
    automatically_following = status == "watching" and release_gap <= 2
    eligible = manually_following or automatically_following
    upcoming_eligible = (
        (manually_following and next_gap <= 1)
        or (status == "watching" and release_gap == 0 and next_gap == 1)
    )

    return {
        "eligible": eligible,
        "status": status,
        "followMode": follow_mode,
        "lastWatched": last_watched,
        "releaseGap": release_gap,
        "nextGap": next_gap,
        "upcomingEligible": upcoming_eligible,
    }


def _season_entry_from_media(media, relation_type=""):
    title = media.get("title") or {}
    mal_id = str(media.get("idMal") or "")
    item = {
        "id": str(media.get("id") or ""),
        "relationType": relation_type,
        "name": title.get("romaji") or title.get("english") or title.get("native") or "",
        "englishName": title.get("english") or title.get("romaji") or title.get("native") or "",
        "nativeName": title.get("native") or "",
        "status": media.get("status") or "",
        "type": media.get("format") or "",
        "season": _season_object(media),
        "thumbnail": ((media.get("coverImage") or {}).get("large")) or ((media.get("coverImage") or {}).get("medium")) or "",
    }
    refs = {
        "metadata": {
            "provider": "anilist",
            "id": item["id"],
        }
    }
    if mal_id:
        refs["sync"] = {
            "provider": "myanimelist",
            "id": mal_id,
        }
    item["providerRefs"] = refs
    return item


def _feed_reason_text(release_gap, follow_mode):
    if follow_mode == "following":
        return "Pinned to Feed"
    if release_gap <= 0:
        return "Caught up"
    if release_gap == 1:
        return "One behind"
    return "Near current"


def _is_season_relation(edge, node):
    relation_type = str((edge or {}).get("relationType") or "").upper()
    if relation_type not in _SEASON_RELATION_TYPES:
        return False
    node_id = str((node or {}).get("id") or "").strip()
    if not node_id:
        return False
    node_format = str((node or {}).get("format") or "").upper()
    if node_format and node_format not in _SEASON_FORMATS:
        return False
    return True


def _season_sort_key(entry, current_id):
    season = entry.get("season") or {}
    year = season.get("year")
    try:
        year_value = int(year or 0)
    except Exception:
        year_value = 0
    quarter = str(season.get("quarter") or "").upper()
    return (
        0 if year_value > 0 else 1,
        year_value or 9999,
        _SEASON_ORDER.get(quarter, 99),
        str(entry.get("englishName") or entry.get("name") or ""),
    )


class AniListMetadataProvider(MetadataProvider):
    provider_id = "anilist"

    def __init__(self):
        self.mapper = AniListAllAnimeMapper()
        self.allanime = AllAnimeMetadataProvider()

    def _decorate_show(self, media, mapping_cache, stream_provider_id):
        item = self._normalise_media(media)
        if mapping_cache is None:
            return item
        cached_stream_id = mapping_cache.get_stream_show_id(self.provider_id, item["id"], stream_provider_id or "allanime")
        return mapping_cache.decorate_show(
            item,
            metadata_provider=self.provider_id,
            stream_provider=stream_provider_id or "allanime",
            stream_id=cached_stream_id,
        )

    def _normalise_media(self, media):
        title = media.get("title") or {}
        available_count = _estimate_available_count(media)
        mal_id = str(media.get("idMal") or "")
        refs = {}
        if mal_id:
            refs["sync"] = {
                "provider": "myanimelist",
                "id": mal_id,
            }
        return {
            "id": str(media.get("id") or ""),
            "name": title.get("romaji") or title.get("english") or title.get("native") or "",
            "englishName": title.get("english") or title.get("romaji") or title.get("native") or "",
            "nativeName": title.get("native") or "",
            "thumbnail": ((media.get("coverImage") or {}).get("large")) or ((media.get("coverImage") or {}).get("medium")) or "",
            "score": _score_value(media.get("averageScore")),
            "type": media.get("format") or "",
            "episodeCount": media.get("episodes") or "",
            "availableEpisodes": {
                "sub": available_count,
                "dub": 0,
                "raw": available_count,
            },
            "season": _season_object(media),
            "status": media.get("status") or "",
            "statusLabel": _status_label(media.get("status")),
            "synonyms": media.get("synonyms") or [],
            "genres": media.get("genres") or [],
            "nextAiringEpisode": media.get("nextAiringEpisode") or None,
            "airingSummary": _airing_summary(media),
            "startDate": media.get("startDate") or None,
            "providerRefs": refs,
        }

    def _page(self, *, page=1, search="", genre=None, sort=None, status=None, mapping_cache=None, stream_provider_id="allanime"):
        variables = {
            "page": page,
            "perPage": 40,
            "search": search or None,
            "sort": sort or ["POPULARITY_DESC"],
        }
        if status == "RELEASING":
            query = _Q_PAGE_RELEASING
        elif genre:
            query = _Q_PAGE_GENRE
            variables["genre"] = genre
        else:
            query = _Q_PAGE_BASE
        data = gql(query, variables, cache_scope="page", ttl_seconds=600)
        page_data = data.get("Page") or {}
        media_list = page_data.get("media") or []
        return {
            "results": [self._decorate_show(media, mapping_cache, stream_provider_id) for media in media_list],
            "hasNextPage": bool(((page_data.get("pageInfo") or {}).get("hasNextPage"))),
        }

    def _media_detail(self, show_id):
        try:
            media_id = int(str(show_id))
        except Exception:
            raise RuntimeError(f"AniList metadata ids must be numeric, got: {show_id}")
        data = gql(_Q_MEDIA, {"id": media_id}, cache_scope="media-detail", ttl_seconds=21600)
        media = data.get("Media") or {}
        if not media:
            raise RuntimeError(f"No AniList media found for id {show_id}")
        return media

    def _relation_media(self, media_id):
        try:
            relation_id = int(str(media_id))
        except Exception:
            return {}
        data = gql(_Q_RELATION_STEP, {"id": relation_id}, cache_scope="relation-step", ttl_seconds=21600)
        return data.get("Media") or {}

    def _build_season_entries(self, media, mapping_cache=None, stream_provider_id="allanime"):
        current_id = str(media.get("id") or "")
        if not current_id:
            return []

        entries = {
            current_id: dict(_season_entry_from_media(media, "CURRENT"), isCurrent=True),
        }
        visited = {current_id}
        pending = []

        relation_edges = ((media.get("relations") or {}).get("edges")) or []
        relation_nodes = ((media.get("relations") or {}).get("nodes")) or []
        for edge, node in zip(relation_edges, relation_nodes):
            if not _is_season_relation(edge or {}, node or {}):
                continue
            pending.append((str(node.get("id") or ""), str((edge or {}).get("relationType") or "").upper()))

        while pending and len(entries) < 12:
            relation_id, relation_type = pending.pop(0)
            if not relation_id or relation_id in visited:
                continue
            visited.add(relation_id)

            relation_media = self._relation_media(relation_id)
            if not relation_media:
                continue

            entry = _season_entry_from_media(relation_media, relation_type)
            if not entry.get("id"):
                continue
            entry["isCurrent"] = entry["id"] == current_id
            entries[entry["id"]] = entry

            next_edges = ((relation_media.get("relations") or {}).get("edges")) or []
            next_nodes = ((relation_media.get("relations") or {}).get("nodes")) or []
            for edge, node in zip(next_edges, next_nodes):
                if not _is_season_relation(edge or {}, node or {}):
                    continue
                next_id = str(node.get("id") or "")
                if next_id and next_id not in visited:
                    pending.append((next_id, str((edge or {}).get("relationType") or "").upper()))

        ordered = sorted(entries.values(), key=lambda item: _season_sort_key(item, current_id))
        decorated = []
        for entry in ordered:
            item = dict(entry)
            if mapping_cache is not None:
                item = mapping_cache.decorate_show(
                    item,
                    metadata_provider=self.provider_id,
                    stream_provider=stream_provider_id or "allanime",
                    stream_id=mapping_cache.get_stream_show_id(
                        self.provider_id,
                        item.get("id") or "",
                        stream_provider_id or "allanime",
                    ),
                )
            decorated.append(item)
        return decorated

    def list_genres(self):
        data = gql(_Q_GENRES, {}, cache_scope="genres", ttl_seconds=86400)
        genres = data.get("GenreCollection") or []
        return [genre for genre in genres if genre]

    def popular(self, page=1, mode="sub", genre=None, mapping_cache=None, stream_provider_id=""):
        return self._page(
            page=page,
            genre=genre,
            sort=["POPULARITY_DESC", "SCORE_DESC"],
            mapping_cache=mapping_cache,
            stream_provider_id=stream_provider_id or "allanime",
        )

    def recent(self, page=1, mode="sub", country="ALL", mapping_cache=None, stream_provider_id=""):
        return self._page(
            page=page,
            sort=["UPDATED_AT_DESC", "POPULARITY_DESC"],
            status="RELEASING",
            mapping_cache=mapping_cache,
            stream_provider_id=stream_provider_id or "allanime",
        )

    def latest(self, page=1, mode="sub", country="ALL", mapping_cache=None, stream_provider_id=""):
        return self.recent(page, mode, country, mapping_cache, stream_provider_id)

    def search(self, query, mode="sub", page=1, genre=None, mapping_cache=None, stream_provider_id=""):
        result = self._page(
            page=page,
            search=query,
            genre=genre,
            sort=["SEARCH_MATCH", "POPULARITY_DESC", "SCORE_DESC"] if str(query or "").strip() else ["POPULARITY_DESC"],
            mapping_cache=mapping_cache,
            stream_provider_id=stream_provider_id or "allanime",
        )
        filtered = _filter_search_results(query, result.get("results") or [])
        return {
            "results": filtered,
            "hasNextPage": result.get("hasNextPage") or False,
        }

    def episodes(self, show_id, mode="sub", mapping_cache=None, stream_provider_id=""):
        media = self._media_detail(show_id)
        base = self._decorate_show(media, mapping_cache, stream_provider_id or "allanime")
        season_entries = self._build_season_entries(media, mapping_cache, stream_provider_id or "allanime")

        relation_edges = ((media.get("relations") or {}).get("edges")) or []
        relation_nodes = ((media.get("relations") or {}).get("nodes")) or []
        relations = []
        for edge, node in zip(relation_edges, relation_nodes):
            relations.append(_normalise_relation(edge or {}, node or {}))

        mapping = {"status": "unmapped", "streamId": "", "confidence": 0, "reason": ""}
        episodes = []
        mapping_error = ""

        if (stream_provider_id or "allanime") == "allanime":
            mapping = self.mapper.resolve(media, mapping_cache=mapping_cache, mode=mode)
            if mapping.get("status") == "mapped" and mapping.get("streamId"):
                stream_detail = self.allanime.episodes(mapping.get("streamId"), mode, mapping_cache=None, stream_provider_id="allanime")
                episodes = stream_detail.get("episodes") or []
            else:
                mapping_error = mapping.get("reason") or "No reliable AllAnime mapping is available for playback yet."

        payload = dict(base)
        payload.update({
            "description": _clean_description(media.get("description") or ""),
            "bannerImage": media.get("bannerImage") or "",
            "genres": media.get("genres") or [],
            "duration": media.get("duration") or None,
            "seasonEntries": season_entries,
            "relations": relations,
            "nextAiringEpisode": media.get("nextAiringEpisode") or None,
            "episodes": episodes,
            "providerRefs": (mapping_cache.decorate_show(
                {"id": base["id"], "providerRefs": base.get("providerRefs") or {}},
                metadata_provider=self.provider_id,
                stream_provider=stream_provider_id or "allanime",
                stream_id=mapping.get("streamId") or "",
            ).get("providerRefs") if mapping_cache is not None else base.get("providerRefs") or {}),
            "mappingStatus": mapping,
        })
        if mapping_error:
            payload["mappingError"] = mapping_error
        return payload

    def _entry_feed_context(self, entry, mapping_cache, mode="sub", stream_provider_id="allanime"):
        refs = entry.get("providerRefs") or {}
        metadata_ref = refs.get("metadata") or {}
        provider = str(metadata_ref.get("provider") or "").strip() or "allanime"
        metadata_id = str(metadata_ref.get("id") or entry.get("id") or "").strip()
        stream_ref = _library_stream_ref(entry)
        if provider == self.provider_id and metadata_id:
            return {
                "libraryId": str(entry.get("id") or metadata_id),
                "mediaId": metadata_id,
                "entry": entry,
                "streamRef": stream_ref,
            }

        if provider != "allanime":
            return None

        mapped_media_id = ""
        if mapping_cache is not None:
            mapped_media_id = mapping_cache.get_provider_show_id("allanime", metadata_id, self.provider_id)
            if not mapped_media_id:
                mapped_media_id = mapping_cache.get_source_show_id(
                    self.provider_id,
                    stream_ref.get("provider") or "allanime",
                    stream_ref.get("id") or metadata_id,
                )
            if mapped_media_id:
                mapping_cache.remember_provider_mapping(
                    "allanime",
                    metadata_id,
                    self.provider_id,
                    mapped_media_id,
                    status="mapped",
                    confidence=1,
                    reason="Derived from existing AniList to AllAnime mapping.",
                )

        # Feed should not fan out uncached reverse lookups across the whole
        # legacy library, or AniList will rate-limit the session.
        if not mapped_media_id:
            return None

        if mapping_cache is not None and stream_ref.get("provider") and stream_ref.get("id"):
            mapping_cache.remember_provider_mapping(
                self.provider_id,
                mapped_media_id,
                stream_ref["provider"],
                stream_ref["id"],
                status="mapped",
                confidence=1,
                reason="Derived from cached legacy library entry.",
            )

        return {
            "libraryId": str(entry.get("id") or ""),
            "mediaId": mapped_media_id,
            "entry": entry,
            "streamRef": stream_ref,
        }

    def feed(self, library_entries, mode="sub", cache_path="", mapping_cache=None, stream_provider_id=""):
        contexts_by_media_id = {}
        ordered_media_ids = []
        for entry in library_entries or []:
            context = self._entry_feed_context(entry, mapping_cache, mode, stream_provider_id or "allanime")
            if not context:
                continue
            media_id = str(context.get("mediaId") or "").strip()
            if not media_id:
                continue
            contexts_by_media_id.setdefault(media_id, []).append(context)
            if media_id not in ordered_media_ids:
                ordered_media_ids.append(media_id)

        if not ordered_media_ids:
            return {"results": []}

        media_lookup = {}
        for index in range(0, len(ordered_media_ids), 50):
            chunk = ordered_media_ids[index:index + 50]
            ids = [int(media_id) for media_id in chunk]
            data = gql(_Q_FEED_BATCH, {"ids": ids}, cache_scope="feed-batch", ttl_seconds=300)
            for media in (data.get("Page") or {}).get("media") or []:
                media_lookup[str(media.get("id") or "")] = media

        alerts = []
        upcoming = []
        followed_media_ids = set()
        now_ts = int(datetime.now(timezone.utc).timestamp())

        for media_id in ordered_media_ids:
            media = media_lookup.get(media_id)
            if not media or media.get("status") != "RELEASING":
                continue

            next_airing = media.get("nextAiringEpisode") or {}
            next_episode = int(next_airing.get("episode") or 0)
            latest_released = next_episode - 1 if next_episode > 1 else 0
            if latest_released <= 0:
                continue

            airing_at = int(next_airing.get("airingAt") or 0)
            time_until = int(next_airing.get("timeUntilAiring") or 0)
            base_show = self._decorate_show(media, mapping_cache, stream_provider_id or "allanime")

            for context in contexts_by_media_id.get(media_id) or []:
                entry = context.get("entry") or {}
                tracking = _feed_tracking_state(entry, latest_released, next_episode)
                if not tracking.get("eligible"):
                    continue
                last_watched = int(tracking.get("lastWatched") or 0)
                followed_media_ids.add(media_id)

                new_count = int(max(0, latest_released - last_watched))

                show_payload = dict(base_show)
                show_payload["id"] = context.get("libraryId") or base_show.get("id") or media_id
                show_payload["providerRefs"] = dict((base_show.get("providerRefs") or {}))
                show_payload["providerRefs"]["metadata"] = {
                    "provider": self.provider_id,
                    "id": media_id,
                }
                stream_ref = context.get("streamRef") or {}
                if stream_ref.get("provider") and stream_ref.get("id"):
                    show_payload["providerRefs"]["stream"] = dict(stream_ref)

                item = dict(show_payload)
                item.update({
                    "mediaId": media_id,
                    "title": show_payload.get("englishName") or show_payload.get("name") or entry.get("englishName") or entry.get("name") or "",
                    "poster": show_payload.get("thumbnail") or entry.get("thumbnail") or "",
                    "nextEpisode": str(int(last_watched) + 1),
                    "watchedThrough": str(last_watched),
                    "newCount": new_count,
                    "watchGap": int(tracking.get("releaseGap") or 0),
                    "nextGap": int(tracking.get("nextGap") or 0),
                    "nearCurrent": int(tracking.get("releaseGap") or 0) <= 1,
                    "trackingStatus": tracking.get("status") or "",
                    "latestReleasedEpisode": str(latest_released),
                    "status": media.get("status") or "",
                    "statusLabel": _status_label(media.get("status")),
                    "releaseText": _release_text(latest_released, next_episode, airing_at, now_ts),
                    "airingAt": airing_at or None,
                    "timeUntilAiring": time_until if airing_at and airing_at > now_ts else None,
                    "followMode": tracking.get("followMode") or _follow_mode(entry),
                    "feedReason": _feed_reason_text(int(tracking.get("releaseGap") or 0), tracking.get("followMode")),
                })
                if new_count > 0:
                    item["feedKind"] = "release"
                    item["eventEpisode"] = str(latest_released)
                    item["eventKey"] = f"episode_release:{media_id}:{latest_released}"
                    alerts.append(item)
                elif (
                    tracking.get("upcomingEligible")
                    and airing_at and airing_at > now_ts
                    and next_episode > last_watched
                ):
                    item["feedKind"] = "upcoming"
                    upcoming.append(item)

        alerts.sort(key=lambda item: (item.get("watchGap") or 0, (item.get("timeUntilAiring") is None), item.get("timeUntilAiring") or 0, item.get("title") or ""))
        upcoming.sort(key=lambda item: (item.get("timeUntilAiring") is None, item.get("timeUntilAiring") or 0, item.get("title") or ""))
        return {
            "results": alerts,
            "upcoming": upcoming,
            "summary": {
                "alerts": len(alerts),
                "upcoming": len(upcoming),
                "following": len(followed_media_ids),
            },
        }
