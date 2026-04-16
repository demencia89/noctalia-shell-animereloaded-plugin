from __future__ import annotations

import re
from difflib import SequenceMatcher

from .allanime import AllAnimeMetadataProvider


def _clean_title(value):
    text = str(value or "").lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _title_variants(media):
    title = media.get("title") or {}
    values = [
        title.get("english"),
        title.get("romaji"),
        title.get("native"),
    ]
    values.extend(media.get("synonyms") or [])

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


def _candidate_titles(candidate):
    return [
        candidate.get("englishName") or "",
        candidate.get("name") or "",
        candidate.get("nativeName") or "",
    ]


def _max_episode_count(candidate):
    avail = candidate.get("availableEpisodes") or {}
    try:
        values = [int(avail.get("sub") or 0), int(avail.get("dub") or 0), int(avail.get("raw") or 0)]
    except Exception:
        values = [0, 0, 0]
    return max(values)


def _format_group(anilist_format):
    value = str(anilist_format or "").upper()
    if value in ("TV", "TV_SHORT"):
        return "TV"
    if value in ("MOVIE",):
        return "MOVIE"
    if value in ("ONA",):
        return "ONA"
    if value in ("OVA",):
        return "OVA"
    if value in ("SPECIAL",):
        return "SPECIAL"
    return value


def _candidate_format(candidate):
    value = str(candidate.get("type") or "").upper().replace(" ", "_")
    if value == "MOVIE":
        return "MOVIE"
    if value == "SPECIAL":
        return "SPECIAL"
    if value == "OVA":
        return "OVA"
    if value == "ONA":
        return "ONA"
    if value == "TV":
        return "TV"
    return value


def _episode_hint(media):
    if media.get("status") == "RELEASING":
        next_airing = media.get("nextAiringEpisode") or {}
        next_ep = int(next_airing.get("episode") or 0)
        if next_ep > 1:
            return next_ep - 1
    try:
        return int(media.get("episodes") or 0)
    except Exception:
        return 0


class AniListAllAnimeMapper:
    def __init__(self):
        self.allanime = AllAnimeMetadataProvider()

    def _search_candidates(self, media, mode="sub"):
        queries = _title_variants(media)
        merged = {}
        for query in queries[:6]:
            results = self.allanime.search(query, mode=mode, page=1, mapping_cache=None, stream_provider_id="allanime")
            for item in results.get("results") or []:
                merged[str(item.get("id") or "")] = item
            if len(merged) >= 20:
                break
        return list(merged.values())

    def _score_candidate(self, media, candidate):
        reasons = []
        score = 0.0

        variants = [_clean_title(value) for value in _title_variants(media)]
        variants = [value for value in variants if value]
        candidate_titles = [_clean_title(value) for value in _candidate_titles(candidate)]
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

        media_year = int(media.get("seasonYear") or 0)
        candidate_year = int(((candidate.get("season") or {}).get("year")) or 0)
        if media_year and candidate_year:
            if media_year == candidate_year:
                score += 18
                reasons.append("same year")
            elif abs(media_year - candidate_year) == 1:
                score += 8
                reasons.append("near year")
            else:
                score -= 12
                reasons.append("year mismatch")

        media_quarter = str(media.get("season") or "").strip().title()
        candidate_quarter = str(((candidate.get("season") or {}).get("quarter")) or "").strip().title()
        if media_quarter and candidate_quarter:
            if media_quarter == candidate_quarter:
                score += 6
                reasons.append("same season")
            else:
                score -= 2

        wanted_format = _format_group(media.get("format"))
        candidate_format = _candidate_format(candidate)
        if wanted_format and candidate_format:
            if wanted_format == candidate_format:
                score += 15
                reasons.append("format match")
            else:
                score -= 12
                reasons.append("format mismatch")

        wanted_episodes = _episode_hint(media)
        candidate_episodes = _max_episode_count(candidate)
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

        return {
            "candidate": candidate,
            "score": round(score, 2),
            "exactTitle": exact_title,
            "titleRatio": round(best_ratio, 3),
            "reasons": reasons,
        }

    def resolve(self, media, mapping_cache=None, mode="sub"):
        metadata_id = str(media.get("id") or "").strip()
        if mapping_cache is not None:
            cached = mapping_cache.get_mapping_record("anilist", metadata_id, "allanime")
            if cached.get("status") == "mapped" and cached.get("streamId"):
                return {
                    "status": "mapped",
                    "streamId": cached.get("streamId"),
                    "confidence": cached.get("confidence") or 1,
                    "reason": cached.get("reason") or "cached mapping",
                    "candidates": cached.get("candidates") or [],
                    "cached": True,
                }

        candidates = self._search_candidates(media, mode=mode)
        if not candidates:
            result = {
                "status": "unmapped",
                "streamId": "",
                "confidence": 0,
                "reason": "No AllAnime candidates were found for this AniList entry.",
                "candidates": [],
            }
            if mapping_cache is not None:
                mapping_cache.remember_mapping_result(
                    "anilist",
                    metadata_id,
                    "allanime",
                    status=result["status"],
                    stream_id=result["streamId"],
                    confidence=result["confidence"],
                    reason=result["reason"],
                    candidates=result["candidates"],
                )
            return result

        ranked = [self._score_candidate(media, candidate) for candidate in candidates]
        ranked.sort(key=lambda item: item["score"], reverse=True)
        top = ranked[0]
        second_score = ranked[1]["score"] if len(ranked) > 1 else -999
        margin = top["score"] - second_score

        candidate_debug = []
        for item in ranked[:5]:
            candidate = item["candidate"]
            candidate_debug.append({
                "id": candidate.get("id"),
                "title": candidate.get("englishName") or candidate.get("name") or "",
                "year": ((candidate.get("season") or {}).get("year")) or None,
                "type": candidate.get("type"),
                "episodes": _max_episode_count(candidate),
                "score": item["score"],
                "reasons": item["reasons"][:4],
            })

        accept = top["score"] >= 68 and (margin >= 10 or top["exactTitle"] or top["titleRatio"] >= 0.94)
        if accept:
            result = {
                "status": "mapped",
                "streamId": top["candidate"].get("id") or "",
                "confidence": min(1.0, round(max(0.0, top["score"]) / 100.0, 3)),
                "reason": "Matched AniList entry to AllAnime using title/season heuristics.",
                "candidates": candidate_debug,
            }
        else:
            result = {
                "status": "uncertain",
                "streamId": "",
                "confidence": min(1.0, round(max(0.0, top["score"]) / 100.0, 3)),
                "reason": "Multiple AllAnime candidates were too close to choose safely.",
                "candidates": candidate_debug,
            }

        if mapping_cache is not None:
            mapping_cache.remember_mapping_result(
                "anilist",
                metadata_id,
                "allanime",
                status=result["status"],
                stream_id=result["streamId"],
                confidence=result["confidence"],
                reason=result["reason"],
                candidates=result["candidates"],
            )
        return result
