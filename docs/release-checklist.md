# Release Checklist

## Automated Checks

- Run `python3 -m compileall anime-reloaded backend`
- Run `node .github/workflows/update-registry.js` and confirm `registry.json` stays clean
- Run `git diff --check`

## Manual Plugin Checks

- Open the panel from the bar widget and confirm it resumes on the last open tab
- Right-click the bar widget and confirm `Widget Settings` opens from the panel edge, not as a detached floating dialog
- Change widget icon, label, and icon color, then use `Revert to Default`
- Open Browse, Library, Feed, Settings, and Player paths and confirm the blurred/translucent panel styling remains consistent
- Open a show from Browse and from Library and confirm the detail view has no blank top gap in either path
- Hover long season chips and confirm overflowing text cycles cleanly inside the chip bounds
- Confirm hidden genres such as `Ecchi` and `Hentai` do not appear in browse filters or detail chips

## Settings Checks

- Open Settings and confirm the layout reads as one coherent surface, including the Auto Push controls inside the same structured container
- In `Runtime Health`, run `Refresh Checks` and confirm Python, mpv, cryptography, and MAL backend status populate
- In `Playback Mapping Repair`, confirm unresolved mappings count appears and `Repair Mappings` updates library entries when mappings are recoverable
- In `MyAnimeList`, confirm the top-row connect/reconnect/disconnect controls align cleanly with the account identity row

## MAL Sync Checks

- Connect through the browser flow and confirm the plugin shows the resolved MAL username and avatar
- Pull from MAL and verify existing mapped entries update while confident AniList imports are added
- Push local progress to MAL and verify watched episode counts and statuses match expectations
- Disconnect and confirm session state is cleared without leaving stale username or enabled state behind
- Reconnect after disconnect and confirm backend-only auth still succeeds without any manual OAuth fields

## Playback Checks

- Start playback from an AniList-backed title that already has an AllAnime mapping
- Start playback from a title that requires cached mapping repair and confirm the episode resolves after repair
- Confirm watched progress updates local library status and, when enabled, auto-push queues after a local change

## Release Gate

- Confirm no unexpected files are staged, especially local runtime state such as `anime-reloaded-mal-config.json` or library/cache files
- Confirm README limitation notes still match the current shipped behavior
- Tag only after the checks above pass on a clean `main`
