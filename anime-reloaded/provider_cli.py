#!/usr/bin/env python3
"""
provider_cli.py — provider-aware metadata/stream bridge for AnimeReloaded.

New usage:
  python3 provider_cli.py metadata <provider> genres
  python3 provider_cli.py metadata <provider> popular <page> <sub|dub> [genre] [mapping_cache] [stream_provider]
  python3 provider_cli.py metadata <provider> recent <page> <sub|dub> <country> [mapping_cache] [stream_provider]
  python3 provider_cli.py metadata <provider> latest <page> <sub|dub> <country> [mapping_cache] [stream_provider]
  python3 provider_cli.py metadata <provider> search <query> <sub|dub> <page> [genre] [mapping_cache] [stream_provider]
  python3 provider_cli.py metadata <provider> episodes <show_id> <sub|dub> [mapping_cache] [stream_provider]
  python3 provider_cli.py metadata <provider> feed <library_json_path> <sub|dub> [cache_json_path] [mapping_cache] [stream_provider]
  python3 provider_cli.py stream <provider> resolve <show_id> <episode_number> <sub|dub> [mirror_pref] [quality_pref] [mapping_cache] [metadata_provider]
  python3 provider_cli.py sync myanimelist auth-url <config_json_path>
  python3 provider_cli.py sync myanimelist listen-exchange <config_json_path> [timeout_seconds]
  python3 provider_cli.py sync myanimelist refresh <config_json_path>
  python3 provider_cli.py sync myanimelist delete-entry <config_json_path> <mal_id> [title]
  python3 provider_cli.py sync myanimelist push <config_json_path> <library_json_path>
  python3 provider_cli.py sync myanimelist pull <config_json_path> <library_json_path>

Legacy usage remains supported for the current AllAnime flow:
  python3 provider_cli.py search <query> [sub|dub] [page]
  python3 provider_cli.py popular [page] [sub|dub]
  python3 provider_cli.py recent [page] [sub|dub] [country]
  python3 provider_cli.py latest [page] [sub|dub] [country]
  python3 provider_cli.py episodes <show_id> [sub|dub]
  python3 provider_cli.py feed <library_json_path> [sub|dub] [cache_json_path]
  python3 provider_cli.py stream <show_id> <episode_number> [sub|dub] [mirror_pref] [quality_pref]
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

from providers.allanime import AllAnimeMetadataProvider, AllAnimeStreamProvider
from providers.anilist import AniListMetadataProvider
from providers.mapping_cache import ProviderMappingCache
from providers import mal_sync


METADATA_PROVIDERS = {
    "anilist": AniListMetadataProvider(),
    "allanime": AllAnimeMetadataProvider(),
}

STREAM_PROVIDERS = {
    "allanime": AllAnimeStreamProvider(),
}


def _print_json(payload, exit_code=0):
    print(json.dumps(payload))
    if exit_code:
        sys.exit(exit_code)


def _metadata_provider(provider_id):
    provider = METADATA_PROVIDERS.get(provider_id)
    if provider is None:
        raise RuntimeError(f"Unknown metadata provider: {provider_id}")
    return provider


def _stream_provider(provider_id):
    provider = STREAM_PROVIDERS.get(provider_id)
    if provider is None:
        raise RuntimeError(f"Unknown stream provider: {provider_id}")
    return provider


def _cache(path):
    return ProviderMappingCache(path or "")


def _read_json_file(path, default):
    file_path = Path(path)
    if not file_path.exists():
        return default
    with file_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, type(default)) else default


def _run_metadata_command(args):
    provider_id = args[1]
    command = args[2]
    provider = _metadata_provider(provider_id)

    if command == "genres":
        _print_json(provider.list_genres())

    elif command == "popular":
        page = int(args[3]) if len(args) > 3 else 1
        mode = args[4] if len(args) > 4 else "sub"
        genre = args[5] if len(args) > 5 else ""
        mapping_cache = _cache(args[6] if len(args) > 6 else "")
        stream_provider_id = args[7] if len(args) > 7 else provider_id
        result = provider.popular(page, mode, genre or None, mapping_cache, stream_provider_id)
        mapping_cache.save()
        _print_json(result)

    elif command == "recent":
        page = int(args[3]) if len(args) > 3 else 1
        mode = args[4] if len(args) > 4 else "sub"
        country = args[5] if len(args) > 5 else "ALL"
        mapping_cache = _cache(args[6] if len(args) > 6 else "")
        stream_provider_id = args[7] if len(args) > 7 else provider_id
        result = provider.recent(page, mode, country, mapping_cache, stream_provider_id)
        mapping_cache.save()
        _print_json(result)

    elif command == "latest":
        page = int(args[3]) if len(args) > 3 else 1
        mode = args[4] if len(args) > 4 else "sub"
        country = args[5] if len(args) > 5 else "ALL"
        mapping_cache = _cache(args[6] if len(args) > 6 else "")
        stream_provider_id = args[7] if len(args) > 7 else provider_id
        result = provider.latest(page, mode, country, mapping_cache, stream_provider_id)
        mapping_cache.save()
        _print_json(result)

    elif command == "search":
        query = args[3] if len(args) > 3 else ""
        mode = args[4] if len(args) > 4 else "sub"
        page = int(args[5]) if len(args) > 5 else 1
        genre = args[6] if len(args) > 6 else ""
        mapping_cache = _cache(args[7] if len(args) > 7 else "")
        stream_provider_id = args[8] if len(args) > 8 else provider_id
        result = provider.search(query, mode, page, genre or None, mapping_cache, stream_provider_id)
        mapping_cache.save()
        _print_json(result)

    elif command == "episodes":
        show_id = args[3]
        mode = args[4] if len(args) > 4 else "sub"
        mapping_cache = _cache(args[5] if len(args) > 5 else "")
        stream_provider_id = args[6] if len(args) > 6 else provider_id
        result = provider.episodes(show_id, mode, mapping_cache, stream_provider_id)
        mapping_cache.save()
        _print_json(result)

    elif command == "feed":
        library_path = args[3]
        mode = args[4] if len(args) > 4 else "sub"
        cache_path = args[5] if len(args) > 5 else ""
        mapping_cache = _cache(args[6] if len(args) > 6 else "")
        stream_provider_id = args[7] if len(args) > 7 else provider_id
        with open(library_path, "r", encoding="utf-8") as handle:
            library_entries = json.load(handle)
        if not isinstance(library_entries, list):
            raise RuntimeError("Invalid library file format")
        result = provider.feed(library_entries, mode, cache_path, mapping_cache, stream_provider_id)
        mapping_cache.save()
        _print_json(result)

    else:
        raise RuntimeError(f"Unknown metadata command: {command}")


def _run_stream_command(args):
    provider_id = args[1]
    command = args[2]
    if command != "resolve":
        raise RuntimeError(f"Unknown stream command: {command}")
    provider = _stream_provider(provider_id)
    show_id = args[3]
    episode_number = args[4]
    mode = args[5] if len(args) > 5 else "sub"
    mirror_pref = args[6] if len(args) > 6 else "auto"
    quality_pref = args[7] if len(args) > 7 else "best"
    mapping_cache = _cache(args[8] if len(args) > 8 else "")
    metadata_provider_id = args[9] if len(args) > 9 else provider_id
    result = provider.resolve_episode_stream(
        show_id,
        episode_number,
        mode,
        mirror_pref,
        quality_pref,
        mapping_cache,
        metadata_provider_id,
    )
    mapping_cache.save()
    _print_json(result, 1 if "error" in result else 0)


def _run_sync_command(args):
    provider_id = args[1]
    command = args[2]
    if provider_id != "myanimelist":
        raise RuntimeError(f"Unknown sync provider: {provider_id}")

    config_path = args[3] if len(args) > 3 else ""
    config = _read_json_file(config_path, {})

    if command == "auth-url":
        _print_json(mal_sync.build_auth_url(config))
        return

    if command == "listen-exchange":
        timeout_seconds = int(args[4]) if len(args) > 4 else 240
        _print_json(mal_sync.await_browser_login(config, timeout_seconds))
        return

    if command == "refresh":
        _print_json(mal_sync.refresh_session(config))
        return

    if command == "delete-entry":
        mal_id = args[4] if len(args) > 4 else ""
        title = args[5] if len(args) > 5 else ""
        _print_json(mal_sync.remove_anime_entry(config, mal_id, title))
        return

    library_path = args[4] if len(args) > 4 else ""
    library = _read_json_file(library_path, [])

    if command == "push":
        _print_json(mal_sync.push_library(config, library))
        return

    if command == "pull":
        _print_json(mal_sync.pull_library(config, library))
        return

    raise RuntimeError(f"Unknown sync command: {command}")


def _run_legacy_command(args):
    command = args[0]
    if command == "genres":
        return _run_metadata_command(["metadata", "allanime", "genres"])
    if command == "search":
        query = args[1] if len(args) > 1 else ""
        mode = args[2] if len(args) > 2 else "sub"
        page = args[3] if len(args) > 3 else "1"
        genre = args[4] if len(args) > 4 else ""
        return _run_metadata_command(["metadata", "allanime", "search", query, mode, page, genre])
    if command == "popular":
        page = args[1] if len(args) > 1 else "1"
        mode = args[2] if len(args) > 2 else "sub"
        genre = args[3] if len(args) > 3 else ""
        return _run_metadata_command(["metadata", "allanime", "popular", page, mode, genre])
    if command == "recent":
        page = args[1] if len(args) > 1 else "1"
        mode = args[2] if len(args) > 2 else "sub"
        country = args[3] if len(args) > 3 else "ALL"
        return _run_metadata_command(["metadata", "allanime", "recent", page, mode, country])
    if command == "latest":
        page = args[1] if len(args) > 1 else "1"
        mode = args[2] if len(args) > 2 else "sub"
        country = args[3] if len(args) > 3 else "ALL"
        return _run_metadata_command(["metadata", "allanime", "latest", page, mode, country])
    if command == "episodes":
        show_id = args[1]
        mode = args[2] if len(args) > 2 else "sub"
        return _run_metadata_command(["metadata", "allanime", "episodes", show_id, mode])
    if command == "feed":
        library_path = args[1]
        mode = args[2] if len(args) > 2 else "sub"
        cache_path = args[3] if len(args) > 3 else ""
        return _run_metadata_command(["metadata", "allanime", "feed", library_path, mode, cache_path])
    if command == "stream":
        show_id = args[1]
        episode_number = args[2]
        mode = args[3] if len(args) > 3 else "sub"
        mirror_pref = args[4] if len(args) > 4 else "auto"
        quality_pref = args[5] if len(args) > 5 else "best"
        return _run_stream_command(["stream", "allanime", "resolve", show_id, episode_number, mode, mirror_pref, quality_pref])
    raise RuntimeError(f"Unknown command: {command}")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        _print_json({"error": "No command given"}, 1)

    try:
        if args[0] == "metadata":
            _run_metadata_command(args)
        elif args[0] == "stream" and len(args) > 2 and args[2] == "resolve":
            _run_stream_command(args)
        elif args[0] == "sync":
            _run_sync_command(args)
        else:
            _run_legacy_command(args)
    except IndexError:
        _print_json({"error": f"Missing argument for: {args[0]}"}, 1)
    except urllib.error.HTTPError as exc:
        _print_json({"error": f"HTTP Error {exc.code}: {exc.reason}"}, 1)
    except urllib.error.URLError as exc:
        _print_json({"error": f"Network error: {exc}"}, 1)
    except Exception as exc:
        _print_json({"error": str(exc)}, 1)


if __name__ == "__main__":
    main()
