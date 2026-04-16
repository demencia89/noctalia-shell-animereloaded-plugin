from __future__ import annotations

import re
from difflib import SequenceMatcher

from .anilist_client import gql

_Q_SEARCH = """
query($page:Int,$perPage:Int,$search:String){
  Page(page:$page, perPage:$perPage){
    media(type:ANIME, search:$search, sort:[SEARCH_MATCH,POPULARITY_DESC], isAdult:false){
      id
      title{romaji english native}
      synonyms
      season
      seasonYear
      status
      episodes
      format
      averageScore
    }
  }
}
""".strip()
def _clean_title(value):
    text = str(value or "").lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _title_variants(entry):
    values = [
        entry.get("englishName"),
        entry.get("name"),
        entry.get("nativeName"),
    ]
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


def _candidate_titles(media):
    title = media.get("title") or {}
    values = [
        title.get("english"),
        title.get("romaji"),
        title.get("native"),
    ]
    values.extend((media.get("synonyms") or [])[:6])

    seen = set()
    candidates = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = _clean_title(text)
        if not key or key in seen:
            continue
        seen.add(key)
        candidates.append(text)
    return candidates


def _max_episode_count(entry):
    avail = entry.get("availableEpisodes") or {}
    values = []
    for key in ("sub", "dub", "raw"):
        try:
            values.append(int(avail.get(key) or 0))
        except Exception:
            values.append(0)
    return max(values or [0])


def _entry_format(entry):
    value = str(entry.get("type") or "").upper().replace(" ", "_")
    if value in ("TV", "TV_SHORT"):
        return "TV"
    if value in ("MOVIE", "OVA", "ONA", "SPECIAL"):
        return value
    return value


def _media_format(media):
    value = str(media.get("format") or "").upper()
    if value in ("TV", "TV_SHORT"):
        return "TV"
    if value in ("MOVIE", "OVA", "ONA", "SPECIAL"):
        return value
    return value


class AllAnimeAniListMapper:
    def _search_candidates(self, entry):
        queries = _title_variants(entry)
        merged = {}
        for query in queries[:6]:
            data = gql(
                _Q_SEARCH,
                {"page": 1, "perPage": 10, "search": query},
                cache_scope="reverse-search",
                ttl_seconds=21600,
            )
            media_list = ((data.get("Page") or {}).get("media")) or []
            for media in media_list:
                merged[str(media.get("id") or "")] = media
            if len(merged) >= 20:
                break
        return list(merged.values())

    def _score_candidate(self, entry, media):
        reasons = []
        score = 0.0

        variants = [_clean_title(value) for value in _title_variants(entry)]
        variants = [value for value in variants if value]
        candidate_titles = [_clean_title(value) for value in _candidate_titles(media)]
        candidate_titles = [value for value in candidate_titles if value]

        best_ratio = 0.0
        exact_title = False
        partial_title = False
        for source in variants:
            for target in candidate_titles:
                if not source or not target:
                    continue
                ratio = SequenceMatcher(None, source, target).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                if source == target:
                    exact_title = True
                elif source in target or target in source:
                    partial_title = True

        if exact_title:
            score += 65
            reasons.append("exact title")
        elif partial_title:
            score += 38
            reasons.append("partial title")
        score += best_ratio * 30
        reasons.append(f"title ratio {best_ratio:.2f}")

        entry_year = int(((entry.get("season") or {}).get("year")) or 0)
        media_year = int(media.get("seasonYear") or 0)
        if entry_year and media_year:
            if entry_year == media_year:
                score += 18
                reasons.append("same year")
            elif abs(entry_year - media_year) == 1:
                score += 8
                reasons.append("near year")
            else:
                score -= 12
                reasons.append("year mismatch")

        entry_quarter = str(((entry.get("season") or {}).get("quarter")) or "").strip().title()
        media_quarter = str(media.get("season") or "").strip().title()
        if entry_quarter and media_quarter:
            if entry_quarter == media_quarter:
                score += 6
                reasons.append("same season")
            else:
                score -= 2

        wanted_format = _entry_format(entry)
        candidate_format = _media_format(media)
        if wanted_format and candidate_format:
            if wanted_format == candidate_format:
                score += 15
                reasons.append("format match")
            else:
                score -= 12
                reasons.append("format mismatch")

        wanted_episodes = _max_episode_count(entry)
        try:
            candidate_episodes = int(media.get("episodes") or 0)
        except Exception:
            candidate_episodes = 0
        if wanted_episodes > 0 and candidate_episodes > 0:
            diff = abs(wanted_episodes - candidate_episodes)
            if diff == 0:
                score += 16
                reasons.append("episode exact")
            elif diff <= 2:
                score += 9
                reasons.append("episode near")
            elif diff <= 6:
                score += 3
            else:
                score -= min(10, diff / 10)
                reasons.append("episode mismatch")

        if str(media.get("status") or "").upper() == "NOT_YET_RELEASED" and wanted_episodes > 0:
            score -= 30
            reasons.append("not released")

        return {
            "candidate": media,
            "score": round(score, 2),
            "exactTitle": exact_title,
            "titleRatio": round(best_ratio, 3),
            "reasons": reasons,
        }

    def resolve(self, entry, mapping_cache=None, mode="sub"):
        source_id = str(entry.get("id") or "").strip()
        if mapping_cache is not None:
            cached = mapping_cache.get_mapping_record("allanime", source_id, "anilist")
            if cached.get("status") == "mapped" and cached.get("targetId"):
                return {
                    "status": "mapped",
                    "mediaId": cached.get("targetId"),
                    "confidence": cached.get("confidence") or 1,
                    "reason": cached.get("reason") or "cached mapping",
                    "candidates": cached.get("candidates") or [],
                    "cached": True,
                }

        candidates = self._search_candidates(entry)
        if not candidates:
            result = {
                "status": "unmapped",
                "mediaId": "",
                "confidence": 0,
                "reason": "No AniList candidates were found for this AllAnime entry.",
                "candidates": [],
            }
            if mapping_cache is not None:
                mapping_cache.remember_provider_mapping(
                    "allanime",
                    source_id,
                    "anilist",
                    "",
                    status=result["status"],
                    confidence=result["confidence"],
                    reason=result["reason"],
                    candidates=result["candidates"],
                )
            return result

        ranked = [self._score_candidate(entry, media) for media in candidates]
        ranked.sort(key=lambda item: item["score"], reverse=True)
        top = ranked[0]
        second_score = ranked[1]["score"] if len(ranked) > 1 else -999
        margin = top["score"] - second_score

        candidate_debug = []
        for item in ranked[:5]:
            candidate = item["candidate"]
            title = candidate.get("title") or {}
            candidate_debug.append({
                "id": str(candidate.get("id") or ""),
                "title": title.get("english") or title.get("romaji") or title.get("native") or "",
                "year": candidate.get("seasonYear") or None,
                "type": candidate.get("format") or "",
                "episodes": candidate.get("episodes") or 0,
                "score": item["score"],
                "reasons": item["reasons"][:4],
            })

        accept = top["score"] >= 68 and (margin >= 10 or top["exactTitle"] or top["titleRatio"] >= 0.94)
        if accept:
            result = {
                "status": "mapped",
                "mediaId": str(top["candidate"].get("id") or ""),
                "confidence": min(1.0, round(max(0.0, top["score"]) / 100.0, 3)),
                "reason": "Matched AllAnime entry to AniList using title/season heuristics.",
                "candidates": candidate_debug,
            }
        else:
            result = {
                "status": "uncertain",
                "mediaId": "",
                "confidence": min(1.0, round(max(0.0, top["score"]) / 100.0, 3)),
                "reason": "Multiple AniList candidates were too close to choose safely.",
                "candidates": candidate_debug,
            }

        if mapping_cache is not None:
            mapping_cache.remember_provider_mapping(
                "allanime",
                source_id,
                "anilist",
                result.get("mediaId") or "",
                status=result["status"],
                confidence=result["confidence"],
                reason=result["reason"],
                candidates=result["candidates"],
            )
        return result
