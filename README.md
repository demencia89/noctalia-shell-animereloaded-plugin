# AnimeReloaded for Noctalia

Standalone repository for the AnimeReloaded plugin. The actual plugin code lives in `anime-reloaded/`, while the root `manifest.json` is kept as a compatibility wrapper for local Noctalia installs.

## Support

If you want to support ongoing work on AnimeReloaded and the surrounding Noctalia projects, sponsor the work through GitHub Sponsors at [@demencia89](https://github.com/sponsors/demencia89).

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

## Connect AniList

1. Open AniList developer settings and create an application for AnimeReloaded.
2. Set the application's redirect URI to `https://anilist.co/api/v2/oauth/pin`.
3. Copy the AniList client ID.
4. In Noctalia, open the AnimeReloaded settings and find the `AniList Sync` section.
5. Paste the client ID into `AniList Client ID`.
6. Click the `Redirect URI` pill if you want the plugin to copy the exact URI to your clipboard.
7. Click `Open AniList Login` and approve the app in your browser.
8. When AniList shows the callback URL or access token, paste it into `Callback URL or Access Token`.
9. Click `Finish Connect`.
10. After connection, use `Pull From AniList` to import remote progress, `Push To AniList` to send local progress, or enable `Auto Push` if you want local watch changes synced automatically.

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
