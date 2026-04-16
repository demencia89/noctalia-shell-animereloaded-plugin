## AnimeReloaded MAL Auth Backend

This backend exists only to handle the MyAnimeList OAuth steps that require a confidential client.

What it does:

- starts a browser auth session for AnimeReloaded
- receives the MAL callback on a server-owned redirect URI
- exchanges the authorization code using the MAL client secret
- stores the refresh token server-side
- returns short-lived access tokens back to the plugin

Minimal deployment shape:

1. Copy the contents of `backend/` into a dedicated app directory such as `/DATA/AppData/animereloaded-mal-auth`.
2. Create `animereloaded-mal-auth.env` from `animereloaded-mal-auth.env.example`.
3. Fill in the MAL client id, client secret, and public redirect URI.
4. Bring the stack up from that app directory with Docker Compose.
5. Expose it through a public HTTPS URL and set MAL's redirect URI to:

`https://<your-public-domain>:8443/api/v1/mal/auth/callback`

Recommended hostname:

`auth.<your-domain>`

That is cleaner than reusing a generic content subdomain like `ani.<your-domain>`, because this service is only the MAL auth bridge.

Current working deployment in this repo:

- public base URL: `https://dns.bogglemind.top:8443`
- callback URL: `https://dns.bogglemind.top:8443/api/v1/mal/auth/callback`
- backend container: `127.0.0.1:18787`
- local TLS proxy: `:8443`

CasaOS / Docker details:

- backend listens on container port `18787`
- the compose file publishes `127.0.0.1:18787:18787` so it stays isolated on the Pi
- persistent session storage lives in `./data/sessions.db` inside the app directory
- health check endpoint: `GET /healthz`

Important networking note:

- your Pi already has existing services on `80` and `443`
- so this container is intentionally isolated and does not try to take over those ports
- the safest local exposure on a Pi that already uses `80` and `443` is a separate HTTPS proxy on `8443`
- that proxy should forward `https://auth.<your-domain>:8443` to `http://127.0.0.1:18787`
- this repository currently uses `dns.bogglemind.top:8443` in practice because that hostname already had a valid certificate on the Pi

Local reverse proxy next step:

1. Issue a certificate for `auth.<your-domain>` using DNS challenge.
2. Start the example stack from `backend/local-proxy/`.
3. Forward router TCP `8443` to the Pi TCP `8443`.
4. Point `auth.<your-domain>` at the Pi public IP.
5. Set the MAL app redirect URI to `https://auth.<your-domain>:8443/api/v1/mal/auth/callback`.

Health check:

`GET /healthz`

Plugin-side expectation:

- `backendUrl` points to the backend base URL
- auth start: `POST /api/v1/mal/auth/start`
- auth poll: `GET /api/v1/mal/auth/session/<authSessionId>`
- refresh: `POST /api/v1/mal/auth/refresh`
