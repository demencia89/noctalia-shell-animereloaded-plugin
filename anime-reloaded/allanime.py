#!/usr/bin/env python3
"""
Compatibility wrapper for the legacy AllAnime CLI entrypoint.

AnimeReloaded now routes metadata and stream operations through
`provider_cli.py`, but the old filename is kept so manual invocations and
older tooling do not break during the refactor.
"""

from provider_cli import main


if __name__ == "__main__":
    main()
