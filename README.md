# AnimeReloaded for Noctalia

AnimeReloaded is the next-generation continuation of the original Noctalia Anime plugin.

Version `3.0.0` is the first major AnimeReloaded release baseline.

It now runs as a hybrid provider plugin:

- AniList for metadata, search, relations, airing data, and feed decisions
- AllAnime for episode lists, stream resolution, and playback
- a local mapping/cache layer between AniList media ids and AllAnime show ids
- MyAnimeList as an optional account sync target for library progress

## Release Status

- Plugin id: `anime-reloaded`
- Plugin name: `AnimeReloaded`
- Runtime folder: `anime-reloaded/`
- Current metadata provider: `anilist`
- Current stream provider: `allanime`
- Current playback path: Noctalia QML -> `provider_cli.py` -> AniList metadata -> AllAnime resolver -> `mpv`
- Intended repository name: `noctalia-shell-animereloaded-plugin`
- Current version: `3.0.0`

## What 3.0.0 Includes

- AniList-backed browse, search, detail, seasons, relations, and airing-aware feed decisions
- AllAnime playback preserved for episode resolution and streaming
- local AniList <-> AllAnime mapping/cache infrastructure for season-safe playback resolution
- smoother browse and library interactions with polished chip/button behavior
- feed groundwork oriented around followed airing shows and newly relevant episode events
- optional MyAnimeList sync with browser login, pull, push, auto-push, badges, and per-title sync state

## Current Focus

- keep playback stable while metadata and feed evolve independently
- keep the UI behavior cohesive without redesigning the plugin away from Noctalia patterns
- keep the codebase easy to extend for future metadata and notification work

## Why This Repo Exists

- The original Anime plugin is still the stable baseline.
- AnimeReloaded is the branch for the next refactor phase.
- Playback stays on AllAnime so the working player flow is preserved.
- Metadata has been moved to AniList so search, show detail, and feed logic can evolve independently from the stream backend.
- The provider split is now concrete enough for future metadata improvements without rewriting playback again.

## Hybrid Architecture

- `anime-reloaded/providers/anilist.py`
  AniList-backed metadata provider for browse/search/detail/feed metadata.
- `anime-reloaded/providers/allanime.py`
  AllAnime metadata compatibility layer plus the active stream resolver.
- `anime-reloaded/providers/anilist_allanime_mapper.py`
  Lazy AniList -> AllAnime resolver used when detail or playback needs stream episodes.
- `anime-reloaded/providers/allanime_anilist_mapper.py`
  Pragmatic legacy AllAnime -> AniList mapper used to keep old library entries feed-compatible.
- `anime-reloaded/providers/mapping_cache.py`
  Local cache for cross-provider id mappings and mapping debug data.

## Feed Behavior

- Feed now uses AniList airing metadata instead of relying only on AllAnime episode snapshots.
- Feed is limited to followed shows with a clear next-airing context and a recent watched position.
- Legacy library entries that still point at AllAnime metadata are reverse-mapped into AniList when the mapping is confident.
- Uncertain mappings are skipped instead of guessing.
- The current goal is a practical startup notification list for followed airing titles, not a noisy activity feed.

## MyAnimeList Sync

- AniList remains the canonical metadata source inside the plugin UI.
- MyAnimeList is now an optional account sync target for the local library.
- The current MAL sync pass is intentionally scoped:
  - browser auth with automatic localhost callback capture from Settings
  - manual code exchange remains available as a fallback in Advanced
  - explicit `Pull From MAL` and `Push To MAL` actions
  - optional auto-push after local library changes
  - per-show MAL status badges in Library and Detail based on mapping presence and the latest sync result
  - pull can import MAL-only titles when they resolve cleanly to AniList metadata
  - playback for imported titles still resolves lazily through the AniList -> AllAnime mapping layer
  - settings now present a practical sync overview centered on attention-required titles, ready-to-push titles, and recently synced titles

This keeps the metadata/playback split intact:

- AniList for search, detail, seasons, relations, airing data, and feed logic
- AllAnime for episode lists, stream resolution, and playback
- MyAnimeList for account-side watch progress synchronization

## Current Limitations

- Playback still depends on AllAnime mappings existing or being resolved during detail fetch.
- Legacy library entries are feed-compatible, but they are not fully migrated in-place to AniList ids yet.
- Feed remains a pragmatic release alert list, not a full notification system yet.
- MyAnimeList pull skips titles that do not map confidently back to AniList metadata.
- Imported MAL titles still need a resolvable AniList -> AllAnime mapping before playback can start.
- Some remaining UI/runtime warnings are still being polished outside the core metadata, playback, and sync flows.

## Repository Layout

```text
.
├── anime-reloaded/         # plugin runtime for catalog installs
│   ├── provider_cli.py     # provider-aware command bridge used by QML
│   ├── providers/          # metadata, stream, and mapping layers
│   ├── Main.qml
│   ├── Panel.qml
│   ├── BarWidget.qml
│   └── manifest.json
├── manifest.json           # local-install compatibility manifest
├── registry.json
└── README.md
```

## Local Install

Clone this repository into your Noctalia plugins directory, then enable `AnimeReloaded` from the Plugins view.

```text
~/.config/noctalia/plugins/
└── AnimeReloaded/
```

The root manifest keeps local checkouts loadable, while the actual plugin runtime stays in `anime-reloaded/`.

## Requirements

- `python3` in `$PATH`
- `mpv` in `$PATH`
- Network access to `graphql.anilist.co`, `api.allanime.day`, and resolved stream hosts

## Notes

- `allanime.py` is still the playback backend.
- Runtime feed/cache files now use `anime-reloaded-*` names inside the plugin directory.
- Mapping cache entries are stored locally in `anime-reloaded-provider-map.json`.
- local MAL auth/session data is stored in `anime-reloaded-mal-config.json` and should stay untracked
- `registry.json` is generated from the runtime manifest.

## License

MIT. See `LICENSE`.
