## AnimeReloaded Local TLS Proxy

This small app exposes the MAL backend on a separate public HTTPS port without touching the Pi services already using `80` and `443`.

Current working layout:

- public URL: `https://dns.bogglemind.top:8443`
- forwards to: `http://127.0.0.1:18787`
- certificate path: `/etc/letsencrypt/live/dns.bogglemind.top/`

Pi app directory:

- `/DATA/AppData/animereloaded-mal-auth-proxy`

Bring it up:

- `docker compose up -d`

Verify locally on the Pi:

- `curl --resolve dns.bogglemind.top:8443:127.0.0.1 -fsS https://dns.bogglemind.top:8443/healthz`
