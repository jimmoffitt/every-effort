# Strava auth notes

The terrain here is smaller than it looks — one-time manual setup, then fully
automatic — but the two phases are easy to conflate, so worth separating
clearly.

## Phase 1: one-time setup (manual, out of band, `src/setup_tokens.py`)

There's no in-app OAuth flow and no callback server. Getting the first token
pair is a deliberately manual, run-once script:

1. `python -m src.setup_tokens` prints an authorization URL built from your
   `STRAVA_CLIENT_ID` (from `.local.env`), requesting scopes
   **`activity:read_all,profile:read_all`** and
   `redirect_uri=http://localhost/exchange_token`.
2. You open that URL, approve in Strava's own consent screen
   (`approval_prompt=force` is set deliberately, so you always see the
   consent screen rather than silently reusing a stale prior grant), and get
   redirected to `http://localhost/exchange_token?code=...` — a page that
   will fail to load (nothing's listening on localhost). That's expected;
   the `code` query param is the only thing you need, copied by hand.
3. The script exchanges that code for an access/refresh token pair via
   Strava's `/oauth/token` endpoint and writes the raw response to
   `data/strava_tokens.json`.

This only ever needs to run once per Strava account — everything after this
is automatic.

## Phase 2: ongoing refresh (automatic, `fetch_data.get_access_token()`)

Every pipeline run and every Sync Now click calls `get_access_token()` first:

- Reads `data/strava_tokens.json`, checks `expires_at` against a **5-minute
  buffer** (`expires_at < time.time() + 300`).
- If still valid: returns the existing `access_token` as-is, no network call.
- If expired or about to be: POSTs a `refresh_token` grant to Strava, merges
  the response back into the token dict (Strava returns a *new* refresh token
  on each refresh too — the old one is invalidated), and rewrites the whole
  file.
- Access tokens are short-lived (Strava issues ~6-hour tokens); the refresh
  token is long-lived and is what actually makes ongoing sync "automatic" —
  as long as it's never revoked, the app never needs a human in the loop
  again.

## Where credentials live

| What | Where | Notes |
|---|---|---|
| `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` | `.local.env` | Your app's identity with Strava's API — one pair per Strava API application, not per-athlete. Loaded via `python-dotenv` in `src/config.py`. Never commit this file. |
| Access + refresh tokens | `data/strava_tokens.json` | Per-athlete. Plaintext, gitignored, no encryption at rest (see [ARCHITECTURE.md](ARCHITECTURE.md) for why that's an accepted tradeoff here). |
| Nothing | Streamlit Cloud / demo deploy | `DEMO_MODE` never calls any of this — the demo runs entirely off the committed `data/demo/activities.json`, no Strava credentials on that host at all. |

## Failure modes worth knowing before you hit them

- **Refresh token revoked** (you revoked API access in your Strava account
  settings, or Strava invalidated it) — `get_access_token()` will raise
  `ConnectionError` on the refresh POST. There's no automatic recovery; you
  re-run `src/setup_tokens.py` from scratch to get a new pair.
- **Token file missing entirely** — raises `FileNotFoundError` with an
  explicit message pointing at `setup_tokens.py`. This is the expected error
  on a genuinely fresh clone before first setup (as opposed to `DEMO_MODE`,
  which sidesteps needing a token file at all).
- **Wrong client ID/secret in `.local.env`** — the *initial* authorize URL
  will still load (client_id is just an unauthenticated query param at that
  stage), but the token exchange and every subsequent refresh will fail with
  Strava's own 4xx error body surfaced via the raised exception.
- **Scope mismatch** — the requested scopes (`activity:read_all`,
  `profile:read_all`) are baked into `setup_tokens.py`'s authorize URL. If a
  future feature needs a broader scope (e.g. write access), that requires
  re-running the authorize step with the new scope string — existing tokens
  don't retroactively gain scopes.
