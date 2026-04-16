# AnimeReloaded for Noctalia

AnimeReloaded is the next-generation continuation of the original Noctalia Anime plugin.

It now runs as a hybrid provider plugin:

- AniList for metadata, search, relations, airing data, and feed decisions
- AllAnime for episode lists, stream resolution, and playback
- a local mapping/cache layer between AniList media ids and AllAnime show ids

## Current State

- Plugin id: `anime-reloaded`
- Plugin name: `AnimeReloaded`
- Runtime folder: `anime-reloaded/`
- Current metadata provider: `anilist`
- Current stream provider: `allanime`
- Current playback path: Noctalia QML -> `provider_cli.py` -> AniList metadata -> AllAnime stream resolver -> `mpv`
- Intended repository name: `noctalia-shell-animereloaded-plugin`
- Current version: `2.2.0`

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

## MyAnimeList Sync

- AniList remains the canonical metadata source inside the plugin UI.
- MyAnimeList is now an optional account sync target for the local library.
- The first MAL sync pass is intentionally scoped:
  - browser auth + manual code exchange from Settings
  - explicit `Pull From MAL` and `Push To MAL` actions
  - optional auto-push after local library changes
  - sync only for library entries that already have a confident MAL mapping

This keeps the metadata/playback split intact:

- AniList for search, detail, seasons, relations, airing data, and feed logic
- AllAnime for episode lists, stream resolution, and playback
- MyAnimeList for account-side watch progress synchronization

## Current Limitations

- Playback still depends on AllAnime mappings existing or being resolved during detail fetch.
- Legacy library entries are feed-compatible, but they are not fully migrated in-place to AniList ids yet.
- Feed remains a pragmatic release alert list, not a full notification system yet.
- MyAnimeList sync currently reconciles the existing local library; it does not import MAL-only titles into AnimeReloaded yet.
- MAL sync skips entries that do not already expose a confident MAL id through AniList metadata.

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
- `registry.json` is generated from the runtime manifest.

## License

MIT. See `LICENSE`.
