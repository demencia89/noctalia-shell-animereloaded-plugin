# AnimeReloaded for Noctalia

AnimeReloaded is an anime plugin for Noctalia with AniList-powered browsing, AllAnime-backed playback, a season-aware details view, release-focused feed tracking, and optional MyAnimeList sync.

## Features

- AniList-backed browse, search, genres, relations, seasons, and airing data
- AllAnime-backed episode resolution and playback
- season-aware details flow so each season opens with its own episodes and metadata
- local library with MAL-style statuses: `Watching`, `Completed`, `On Hold`, `Dropped`, and `Plan To Watch`
- feed focused on currently watched releasing shows that you are still keeping up with
- MyAnimeList browser login, pull, push, optional auto-push, and per-title sync badges
- polished Noctalia-native panel UI with widget customization, panel sizing, and poster sizing controls

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

This repository is plugin-only. Regular users do not need any separate backend files in their plugin folder.

## Requirements

- `python3` in `$PATH`
- `python3-cryptography` or an equivalent Python `cryptography` package
- `mpv` in `$PATH`
- network access to AniList, AllAnime, MyAnimeList, and resolved stream hosts

## MyAnimeList Sync

AnimeReloaded keeps AniList as the in-app metadata source and uses MyAnimeList only for account sync.

- Connect from Settings through the browser flow
- `Pull From MAL` merges remote progress and imports MAL-only titles when they can be matched confidently
- `Push To MAL` sends local status and watched-episode progress outward
- optional auto-push can sync after local watch changes
- per-show MAL badges appear in Library and Details

Status handling follows MAL-style rules:

- new library entries start as `plan_to_watch`
- starting progress promotes them to `watching`
- known completions are pushed as `completed`
- `on_hold` and `dropped` stay explicit instead of being inferred

## Notes

- Playback still depends on a valid AniList to AllAnime mapping for the title you want to watch.
- AnimeReloaded stores local runtime data in the plugin directory, including `anime-reloaded-library.json`, `anime-reloaded-feed-cache.json`, `anime-reloaded-provider-map.json`, and `anime-reloaded-mal-config.json`.
- `anime-reloaded-mal-config.json` contains local MAL session data and should remain untracked.

## Related Links

- Legacy Anime plugin: [demencia89/noctalia-shell-anime-plugin](https://github.com/demencia89/noctalia-shell-anime-plugin)

## License

MIT. See `LICENSE`.
