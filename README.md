# AnimeReloaded for Noctalia

Standalone repository for the AnimeReloaded plugin. The actual plugin code lives in `anime-reloaded/`, while the root `manifest.json` is kept as a compatibility wrapper for local Noctalia installs.

## Features

- Browse, search, and show details with AniList metadata
- Season navigation and relation traversal
- AllAnime stream resolution with provider priority
- Local library tracking with MAL-style statuses
- Release feed and continue-watching flow
- AniList account sync with browser login, pull, push, imports, and optional auto-push
- MyAnimeList sync with browser-based login, pull, push, and auto-push
- Sync result inspection in settings, with per-title status and failure reasons
- Manual sync notifications now appear both as shell toasts and in Noctalia notification history
- Bar widget, panel, and settings integration

## Screenshots

Desktop integration preview:

![AnimeReloaded desktop integration](docs/screenshots/top-bar-integration.png)

Library panel:

![AnimeReloaded library panel](docs/screenshots/panel-library.png)

## Install

Clone this repository into your Noctalia plugins directory, then enable `AnimeReloaded` from the Plugins view.

```text
~/.config/noctalia/plugins/
└── AnimeReloaded/
```

## Architecture

All provider logic runs in-process via QML JavaScript. No Python runtime is required.

```text
anime-reloaded/js/
  crypto-helper.js         node-forge loading and AES/SHA helpers
  allanime-provider.js     AllAnime GraphQL and stream resolution
  anilist-provider.js      AniList GraphQL with cache and rate limiting
  anilist-sync-provider.js AniList account sync and library import/push logic
  mal-provider.js          MAL auth and library sync
  mapping-cache.js         AniList-to-AllAnime ID mapping
  providers.js             unified dispatcher
```

## Requirements

- Noctalia Shell >= 3.6.0
- `mpv` in `$PATH`
- `curl` in `$PATH` for crypto library caching
- a browser for AniList and MyAnimeList login flows
- network access to AniList, AllAnime, MyAnimeList, and resolved stream hosts

## Notes

- Current library, feed, AniList sync, and MAL sync state are persisted through Noctalia plugin settings.
- Runtime files still used from the plugin directory include `progress/` playback state files and `anime-reloaded/js/forge.cache.js`.
- Legacy JSON files from older revisions may still exist in local installs, but the active sync workflow is now JavaScript-only and no longer depends on the removed Python providers.
- The maintained unofficial catalog copy lives in `rukh-debug/noctalia-unofficial-plugins` under `anime-reloaded/`.

## License

MIT. See `LICENSE`.
