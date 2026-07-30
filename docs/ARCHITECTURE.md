# Data architecture

This app persists two genuinely different kinds of data, and it's worth being
precise about the difference before touching either one:

- **Archive/activity data** — your actual Strava history. Large-ish, durable,
  the whole reason the app exists.
- **Session and runtime state** — everything else: UI selections, settings,
  sync bookkeeping, OAuth tokens. Small, operational, mostly invisible.

Both end up using the same underlying pattern (a JSON file on local disk,
read fully into memory, rewritten fully on save, cached process-wide via
`@st.cache_data`) — but the tradeoffs land differently for each, and that's
the point of this doc.

---

## Archive & activity data

**What it is.** Every Strava activity you've ever synced, as a flat JSON
array — `data/raw/my_strava_activities.json` (plus optional per-year
`YYYY.json` files the app auto-merges for years not already in the main
archive). One object per activity, fields mostly passed through raw from
Strava's API rather than normalized into a fixed schema.

**How it grows.** `run_pipeline.py` (or the sidebar's Sync Now button) calls
`fetch_data.maintain_archive()`, which:
1. Loads the *entire* existing archive into memory.
2. For each target year: skips it if already present (past years are
   immutable once fetched), or fetches it fresh if missing.
3. For the *current* year specifically: always re-checks Strava for anything
   new since the last sync.
4. Appends new activities to the in-memory list, then **rewrites the whole
   file** via `json.dump` — there's no append-only log or partial write.

**How it's loaded.** `app.py`'s `load_activities()` reads the archive once,
wrapped in `@st.cache_data`, and `process_data.process_activities()` turns it
into a pandas DataFrame with derived columns (`distance_miles`,
`elevation_feet`, `final_type`, `year`, `hours`, …). Every tab's render
function works off that one shared DataFrame.

### Pros
- **Zero infrastructure.** No database server, no schema migrations, no
  connection strings to leak. The whole history is one file you can `cp`,
  back up to a Dropbox folder, or open in a text editor and actually read.
- **Trivially portable.** Moving your data to a new machine is copying one
  file.
- **Cheap at this scale.** ~2,200 activities is a ~5 MB file — parses and
  loads in a fraction of a second. Every chart render after that is free,
  since `@st.cache_data` means the DataFrame is only rebuilt when the
  underlying file or code actually changes, not on every rerun.
- **Transparent.** Nothing hidden behind a query layer — what you see in the
  JSON is exactly what the app has.

### Cons
- **Whole-file rewrite on every sync.** As the archive grows, *every*
  incremental sync still reads and rewrites the entire array — O(n) I/O for
  what's conceptually an append of a handful of new rows. Fine at thousands
  of activities; would start to genuinely matter (multi-second syncs, memory
  pressure) somewhere in the tens-of-thousands range.
- **No query capability.** Any question ("rides over 30 miles in 2022") means
  loading the *whole* archive into a DataFrame first, then filtering in
  pandas. There's no way to ask the storage layer for a subset directly.
  Fine for one person's history; wouldn't scale to a much larger or
  multi-user dataset.
- **No concurrency control.** Two syncs racing, or a sync running while
  `make_demo_data.py`/`gen_screenshots.py` reads the same file, could in
  theory interleave badly — last writer wins, no file locking. Not a real
  risk today (one user, one Streamlit process), but it's a real gap if this
  ever needed to run concurrently.
- **No schema enforcement.** The shape of each record is whatever Strava's
  API happened to return at fetch time — a future API field rename or
  removal would silently propagate into new records with no compatibility
  layer to catch it.
- **`@st.cache_data` is process-wide, not per-browser-session** — an easy
  nuance to miss. (The `app.py` module docstring even says "loaded once per
  session," which slightly overstates the isolation.) In reality, one
  running Streamlit process serves *one* shared in-memory copy to every
  connected browser tab. That's actually desirable here — one person, one
  Strava account, no reason to reload per visitor — but it would be a real
  bug (one visitor seeing another's data) if this app were ever adapted to
  serve multiple distinct Strava accounts from a single process.

---

## Session & runtime state

This splits into two categories that are easy to conflate but behave very
differently.

### A. `st.session_state` — in-memory, per-browser-tab, gone on refresh

Used for things like: which gear checkboxes are ticked
(`bike_gear_<gear_id>`), the Units/Year/Season selections per tab
(`bike_unit`, `bike_year`, `ski_season_sel`, …), the Wrapped Stories
period/sport selectors, the sport-photo upload-identity guards, and the
per-URL-path theme-sync tracking set.

- **Lifetime:** tied to one browser tab's live connection to the Streamlit
  server. A hard refresh, a new tab, or a server restart all wipe it clean.
  Nothing here ever touches disk.
- **Pro:** zero-plumbing UI state — exactly what Streamlit's model is built
  for, and it can never leak stale state into an unrelated future session.
- **Con:** nothing is remembered between visits — every session starts from
  defaults. By design, not a bug, but worth knowing before assuming a
  "remember my last filter" feature would be free — it would have to move
  into `settings.json`, not stay in `session_state`.

### B. Small JSON files — durable, one file per concern

| File | Holds | Written by |
|---|---|---|
| `data/settings.json` | Goals, equity conversion rates, enabled sport tabs, season boundaries, home-heatmap location, theme, sport-photo paths | Settings pages' Save buttons; sidebar theme toggle |
| `data/last_data.json` | Timestamp + activity count from the last sync | `_run_sync()`, after every Sync Now |
| `data/gear_map.json` | Bike/shoe ID → display name | `run_pipeline.py` / Sync Now (merges live API + `GEAR_FALLBACKS`) |
| `data/athlete_profile.json` | Name, follower/following counts | `run_pipeline.py` / Sync Now |
| `data/athlete_stats.json` | Strava's own all-time/YTD totals | `run_pipeline.py` / Sync Now |
| `data/strava_tokens.json` | OAuth access/refresh token pair | `fetch_data.get_access_token()`, auto-refreshed ~every 6 hrs |
| `data/custom_images/*` | Uploaded sport-tab photos | Settings → Sports file uploader |

`DEMO_MODE` mirrors this entire set into `data/demo/` by swapping the path
constants in `src/config.py` — the app code itself doesn't know or care which
mode it's in.

### Pros
- Each file is single-purpose and human-inspectable — you can `cat` any of
  them and understand the app's entire configurable state.
- Adding a new setting is a one-line dict-key addition, no migration to write.
- `DEMO_MODE`'s mirroring is free: same code, different path constants.

### Cons
- **No encryption at rest.** `strava_tokens.json` sits on disk in plaintext.
  Mitigated only by being gitignored and living on a single-user machine (or
  a Streamlit Cloud host with no other tenants) — not by anything the app
  itself does.
- **No atomic writes.** A crash mid-`json.dump` could corrupt one of these
  files. Low-probability and low-blast-radius at these file sizes, but it's
  the same "read-modify-rewrite-whole-file" pattern as the archive, repeated
  everywhere.
- Same process-wide `@st.cache_data` caveat as the archive: these are cached
  once per server process, invalidated only by explicit `.clear()` calls
  after a save/sync.

---

## The common thread

Every persistence mechanism in this codebase — activity archive, settings,
tokens, sync records — reduces to the same thing: *a JSON file on local
disk, read fully into memory, rewritten fully on save, cached process-wide,
invalidated by explicit `.clear()` calls.* That's a deliberate, consistent
choice for a single-user personal tool. It buys inspectability, portability,
and zero infrastructure, at the cost of not scaling past roughly "one
person's lifetime of activity data" and not being safe to run multi-tenant
without real changes — a database, per-user cache keys, and file locking,
none of which exist today.

Strava OAuth/token details are split out into their own doc — see
[AUTH.md](AUTH.md).
