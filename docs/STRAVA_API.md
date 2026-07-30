# Strava API notes

What this app actually calls, how it paginates and syncs incrementally, and
the gaps worth knowing about before extending it. For OAuth/token details
specifically, see [AUTH.md](AUTH.md) — this doc assumes you already have a
valid access token in hand.

## Endpoints this app actually uses

All calls go through one shared `_strava_request()` helper against Strava's
REST v3 API (`https://www.strava.com/api/v3/...`) — no SDK, no wrapper
library, just `Authorization: Bearer <access_token>` headers plus retry and
error handling (see "Rate limits and error handling" below). Everything
lives in `src/fetch_data.py`.

| Endpoint | Used for | Called from |
|---|---|---|
| `POST /oauth/token` | Refreshing an expired access token | `get_access_token()` |
| `GET /athlete` | Both the athlete's profile *and* their bikes/shoes — one response, two different extraction functions | `fetch_athlete_profile()`, `fetch_active_gear()` |
| `GET /athletes/{id}/stats` | Strava's own all-time/YTD/recent totals (shown alongside this app's own computed stats, not used to derive them) | `fetch_athlete_stats()` |
| `GET /athlete/activities` | The actual activity list — the one endpoint that matters most | `_fetch_pages()` |

Notably *not* used: activity detail endpoints (streams, laps, segments,
photos), webhooks/push subscriptions, or anything write-side (this app is
read-only against Strava — it never creates, updates, or deletes anything
on your Strava account).

## Pagination & the incremental-sync strategy

`GET /athlete/activities` is paginated, `per_page` capped at **200** (Strava's
max) and `page`-indexed. `_fetch_pages()` just keeps requesting pages and
extending a list until a page comes back genuinely empty — including one
guaranteed extra request past the real last page, just to confirm there's
nothing left. Simple and correct, at the cost of one always-wasted request
per fetch.

A failed page (rate limit, server error) is deliberately **not** treated the
same as an empty page — `_strava_request()` raises rather than returning a
falsy result, so a mid-sync failure can never look identical to "that's
everything." See "Rate limits and error handling" below.

The interesting part is `maintain_archive()`'s per-year strategy, since it's
what keeps ongoing syncs cheap:

- **Past years** (fully elapsed, already in the archive): skipped entirely —
  zero API calls. Past activity history is treated as immutable once synced.
- **Missing years** (not yet in the archive, past or current): fetched in
  full, via `after`/`before` Unix-timestamp bounds spanning the whole
  calendar year.
- **The current year specifically**: never re-fetched in full. Instead, the
  archive's own latest `start_date` for that year becomes the `after`
  timestamp for a narrow follow-up query — so a routine sync only ever asks
  Strava for "anything since my last known activity," not "everything this
  year again."

This is why a routine Sync Now click is fast regardless of how much history
is already archived — the request volume scales with *new* activities, not
total archive size.

**Overlap dedup:** `after`/`before` bounds are timestamps, not IDs, so it's
possible (activities logged out of order, clock skew, near-simultaneous
activities) to refetch an activity you already have. `maintain_archive()`
dedupes by activity `id` before extending the in-memory list, so this is
handled — but it's worth knowing the boundary isn't guaranteed
non-overlapping by construction.

## Rate limits and error handling

Strava's API enforces both a 15-minute and a daily request cap per
application (the exact numbers have changed over time and depend on your
app's approval tier — check your app's settings at
[strava.com/settings/api](https://www.strava.com/settings/api) and the
[current developer docs](https://developers.strava.com/docs/rate-limits/)
for your actual limits, don't hardcode a number here as gospel).

**Every call goes through `_strava_request()`**, a shared wrapper that
retries and raises typed exceptions instead of the old behavior (a bare
non-200 check that silently stopped or returned `{}`/`[]` with no
indication anything had gone wrong):

| Response | Behavior |
|---|---|
| `429` (rate limited) | Retries with backoff (10s, then 40s by default), reading `X-RateLimit-Usage`/`X-RateLimit-Limit` into the log message. Raises `StravaRateLimitError` if still failing after retries. |
| `401` (bad token) | Raises `StravaAuthError` immediately — no retry, since retrying with the same rejected token can't help. Points at re-running `src/setup_tokens.py`. |
| `5xx` (server error) | Retries with a short backoff (2s, 4s, …), then raises `StravaAPIError`. |
| Network exception (timeout, DNS, …) | Same short-backoff retry, then raises `StravaAPIError`. |
| Anything else (`400`, `403`, `404`, …) | Not retried — raises `StravaAPIError` immediately with the response body included. |

All three exception classes (`StravaRateLimitError`, `StravaAuthError`,
`StravaAPIError` — the first two subclass the third) live in
`src/fetch_data.py`. `app.py`'s Sync Now button catches them specifically to
show a clear status message instead of a raw traceback; `run_pipeline.py`
catches the base class around both the profile/gear/stats setup step and the
archive sync step for the same reason on the CLI side.

**Two different failure postures, by design:**
- `fetch_athlete_profile()`, `fetch_active_gear()`, and `fetch_athlete_stats()`
  are supplementary — they catch `StravaAPIError` locally and soft-fail back
  to `{}` (after retries), printing a `[WARN]` line, rather than aborting the
  whole sync over secondary data.
- `_fetch_pages()` — the activity archive itself — does **not** catch
  anything. An unrecoverable failure propagates all the way up, because a
  partial, silently-truncated archive is worse than a sync that visibly
  failed and can just be retried. One consequence worth knowing:
  `maintain_archive()` only writes the archive file once, after every
  requested year succeeds — a failure partway through a large multi-year
  backfill discards that run's progress rather than saving a partial
  result. Safe (nothing corrupts), but not resumable mid-run; just retry the
  whole sync.

Retry waits are intentionally short (tens of seconds, not the full 15-minute
window) — this is called from an interactive Streamlit button as well as the
CLI, and a routine sync blocking for minutes would look broken to a user
even though it's technically "working as designed."

What's still *not* handled: proactive throttling ahead of hitting a 429 (no
read of rate-limit headers on a *successful* response to slow down before
the limit is hit), and there's no queuing if multiple syncs somehow overlap.
Fine for today's single-user, click-Sync-Now-occasionally usage; would need
revisiting for anything higher-volume (see
[FUTURE_MULTI_TENANT.md](FUTURE_MULTI_TENANT.md)'s note on rate limits
becoming a genuinely shared, contended resource in a hosted multi-tenant
setup).

## Data model quirks worth knowing

- **`distance` is meters, `total_elevation_gain` is meters** — the raw API
  response is metric regardless of the athlete's Strava display-unit
  preference. All mile/foot conversion happens in this app's own processing
  layer (`process_data.py`), not from Strava.
- **`type` vs `sport_type`** — Strava has two overlapping activity-type
  fields; `sport_type` is the newer, more granular one (distinguishes e.g.
  `MountainBikeRide` from `Ride`), `type` is the older, coarser one this app
  actually keys most of its sport-bucketing logic on (see `BIKE_TYPES`,
  `SKI_TYPES`, etc. in `src/config.py`). Worth checking both fields exist on
  whatever record you're inspecting before assuming one or the other.
- **Gear IDs can go stale.** A bike or shoe deleted/retired in Strava stops
  appearing in the `/athlete` response's `bikes`/`shoes` arrays, but old
  activities still reference its `gear_id`. This app papers over that with a
  hardcoded `GEAR_FALLBACKS` dict in `src/config.py` — if you retire gear on
  Strava, you'll need to add it there manually or its name will stop
  resolving.
- **No pagination cursor beyond `page`/`per_page`** — unlike some APIs with
  opaque cursor tokens, Strava's activities endpoint is plain numeric paging
  on top of a time-window filter, which is why the `after`/`before` +
  incremental-year strategy above is necessary to keep syncs cheap at all.

## Where to go deeper

- Official API reference: <https://developers.strava.com/docs/reference/>
- Rate limit specifics: <https://developers.strava.com/docs/rate-limits/>
- Your app's own registered rate-limit tier:
  <https://www.strava.com/settings/api>
