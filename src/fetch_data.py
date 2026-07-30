"""
src/fetch_data.py — Strava API client and activity archive manager.

Handles OAuth token refresh (get_access_token), athlete profile and gear
retrieval, and the persistent activity archive in data/raw/. The key entry
point is maintain_archive(), which fetches any missing years in full and
does an incremental update for the current year only — keeping API calls
minimal on subsequent runs. Called by run_pipeline.py and by app.py's
Sync Now button.

Every HTTP call to Strava goes through _strava_request(), which retries
rate limits (429) and transient server errors (5xx) with backoff, and
raises a typed exception (StravaRateLimitError / StravaAuthError /
StravaAPIError) rather than silently returning an empty result when a
call ultimately fails. That distinction matters most in _fetch_pages():
without it, a rate-limited page in the middle of pagination is
indistinguishable from a legitimate "no more activities" empty page, and
a sync can silently leave the archive incomplete with no indication
anything went wrong.
"""
import json
import time
import requests
import os
from datetime import datetime


class StravaAPIError(Exception):
    """Raised when a Strava API call fails after retries are exhausted."""


class StravaRateLimitError(StravaAPIError):
    """Raised when Strava's rate limit (429) is hit and retries are exhausted."""


class StravaAuthError(StravaAPIError):
    """Raised on a 401 — the access token is invalid even after refreshing,
    most likely because the refresh token itself was revoked."""


def _strava_request(method, url, *, max_retries=2, **kwargs):
    """Shared HTTP wrapper for every Strava API call. Retries 429s and 5xx
    responses with backoff (short waits — this is called from an interactive
    Streamlit button as well as the CLI pipeline, so it shouldn't block for
    minutes); raises a clear, typed exception on anything else, or once
    retries are exhausted, instead of leaving the caller to interpret a
    falsy/empty result as "nothing to do"."""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.request(method, url, timeout=30, **kwargs)
        except requests.RequestException as e:
            last_exc = e
            if attempt < max_retries:
                wait = 2 * (attempt + 1)
                print(f"   [WARN] Network error ({e}); retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise StravaAPIError(f"Network error calling {url}: {e}") from e

        if response.status_code == 200:
            return response

        if response.status_code == 429:
            usage = response.headers.get('X-RateLimit-Usage', '?')
            limit = response.headers.get('X-RateLimit-Limit', '?')
            if attempt < max_retries:
                wait = 10 * (attempt + 1) ** 2  # 10s, then 40s
                print(f"   [WARN] Strava rate limit hit (usage {usage} / "
                      f"limit {limit}). Waiting {wait}s before retry "
                      f"{attempt + 1}/{max_retries}...")
                time.sleep(wait)
                continue
            raise StravaRateLimitError(
                f"Strava rate limit exceeded (usage {usage} / limit {limit}) "
                f"after {max_retries} retries. Wait a while and try again."
            )

        if response.status_code == 401:
            raise StravaAuthError(
                "Strava rejected the access token (401), even after a "
                "refresh attempt — the refresh token itself may have been "
                "revoked. Re-run src/setup_tokens.py to re-authenticate."
            )

        if response.status_code >= 500:
            if attempt < max_retries:
                wait = 2 * (attempt + 1)
                print(f"   [WARN] Strava server error ({response.status_code}); "
                      f"retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise StravaAPIError(
                f"Strava server error {response.status_code} after "
                f"{max_retries} retries: {response.text[:200]}"
            )

        # Any other status (400, 403, 404, …) isn't retryable.
        raise StravaAPIError(
            f"Strava API error {response.status_code} calling {url}: "
            f"{response.text[:200]}"
        )

    raise StravaAPIError(f"Failed calling {url}") from last_exc


# --- Authentication ---
def get_access_token(token_file, client_id, client_secret):
    """Return a valid access token, refreshing it first if it's within 5
    minutes of expiring. Requires token_file to already exist — this app has
    no in-browser OAuth flow, so the first token pair must be created out of
    band (see src/setup_tokens.py) before anything here can run."""
    if not os.path.exists(token_file):
        raise FileNotFoundError(f"ERROR: '{token_file}' not found. Please authenticate manually first.")

    with open(token_file, 'r') as f:
        tokens = json.load(f)

    if tokens['expires_at'] < time.time() + 300:
        print("Token expired. Refreshing...")
        response = _strava_request(
            'POST', 'https://www.strava.com/api/v3/oauth/token',
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': tokens['refresh_token']
            }
        )
        tokens.update(response.json())
        with open(token_file, 'w') as f:
            json.dump(tokens, f)
    return tokens['access_token']

def fetch_active_gear(access_token):
    """Fetch the athlete's bikes and shoes and return one flat {gear_id: name}
    map covering both. Merged with config.GEAR_FALLBACKS by the caller so
    retired gear (no longer returned by this endpoint but still referenced by
    old activities) still resolves to a name. Supplementary data — soft-fails
    to {} (after retries) rather than aborting the whole sync over it."""
    url = "https://www.strava.com/api/v3/athlete"
    try:
        response = _strava_request('GET', url, headers={'Authorization': f"Bearer {access_token}"})
    except StravaAPIError as e:
        print(f"   [WARN] Could not fetch gear: {e}")
        return {}
    data = response.json()
    gear_map = {}
    for bike in data.get('bikes', []): gear_map[bike['id']] = bike['name']
    for shoe in data.get('shoes', []): gear_map[shoe['id']] = shoe['name']
    return gear_map


def fetch_athlete_profile(access_token):
    """Fetch athlete profile — id, name, location, follower/following counts.
    Supplementary data — soft-fails to {} (after retries) rather than
    aborting the whole sync over it."""
    url = "https://www.strava.com/api/v3/athlete"
    try:
        response = _strava_request('GET', url, headers={'Authorization': f"Bearer {access_token}"})
    except StravaAPIError as e:
        print(f"   [WARN] Could not fetch athlete profile: {e}")
        return {}
    data = response.json()
    return {
        'id':             data.get('id'),
        'firstname':      data.get('firstname', ''),
        'lastname':       data.get('lastname', ''),
        'city':           data.get('city', ''),
        'state':          data.get('state', ''),
        'follower_count': data.get('follower_count', 0),
        'friend_count':   data.get('friend_count', 0),
    }


def fetch_athlete_stats(access_token, athlete_id):
    """Fetch all-time, YTD, and recent totals from /athletes/{id}/stats.
    Supplementary data — soft-fails to {} (after retries) rather than
    aborting the whole sync over it."""
    url = f"https://www.strava.com/api/v3/athletes/{athlete_id}/stats"
    try:
        response = _strava_request('GET', url, headers={'Authorization': f"Bearer {access_token}"})
    except StravaAPIError as e:
        print(f"   [WARN] Could not fetch athlete stats: {e}")
        return {}
    return response.json()

# --- ARCHIVE MAINTENANCE LOGIC ---

def maintain_archive(access_token, archive_file, target_years):
    """
    Ensures the archive_file contains data for all target_years.
    - If a past year is missing: Fetches it.
    - If a past year is present: Skips it.
    - If the current year is requested: Checks for new data (incremental sync).
    """
    
    # 1. Load Existing Archive
    all_activities = []
    if os.path.exists(archive_file):
        try:
            with open(archive_file, 'r') as f:
                all_activities = json.load(f)
            print(f"Loaded archive: {len(all_activities)} activities found.")
        except json.JSONDecodeError:
            print("⚠️ Archive file was corrupt or empty. Starting fresh.")
            
    # Helper to check if we have data for a specific year
    # We create a set of years present in the data for quick lookup
    present_years = set()
    for act in all_activities:
        # Parse year safely
        start_date = act.get('start_date', '')
        if start_date:
            # ISO format: "2024-01-01T..."
            y = int(start_date[:4])
            present_years.add(y)

    current_year = datetime.now().year
    updated = False

    # 2. Iterate through requested years
    for year in target_years:
        
        # CASE A: Data exists for a PAST year
        if year in present_years and year < current_year:
            print(f"   [OK] {year} data exists in archive. Skipping.")
            continue
            
        # CASE B: Data missing for ANY year (Past or Current). Note this also
        # covers the *first* sync of the current year — it downloads the
        # whole year up front, and only subsequent runs fall through to the
        # incremental CASE C below.
        if year not in present_years:
            print(f"   [MISSING] {year} data not found. Downloading full year...")
            new_data = _fetch_year(access_token, year)
            if new_data:
                all_activities.extend(new_data)
                present_years.add(year) # Mark as done
                updated = True
            continue
            
        # CASE C: Data exists for CURRENT year (Incremental Update)
        if year == current_year:
            print(f"   [SYNC] Checking for new activities in {year}...")
            # Find the latest timestamp we have for this year
            year_acts = [a for a in all_activities if a['start_date'].startswith(str(year))]
            if not year_acts:
                # Should have been caught by Case B, but safe fallback
                last_ts = datetime(year, 1, 1).timestamp()
            else:
                # Sort to find latest
                year_acts.sort(key=lambda x: x['start_date'])
                last_iso = year_acts[-1]['start_date'].replace('Z', '+00:00')
                last_ts = datetime.fromisoformat(last_iso).timestamp()
            
            # Fetch strictly AFTER that timestamp
            new_data = _fetch_pages(access_token, after_ts=last_ts, before_ts=datetime.now().timestamp())
            
            # Deduplicate (Strava API overlap safety)
            existing_ids = {a['id'] for a in all_activities}
            real_new = [a for a in new_data if a['id'] not in existing_ids]
            
            if real_new:
                print(f"      Found {len(real_new)} new items.")
                all_activities.extend(real_new)
                updated = True
            else:
                print("      Up to date.")

    # 3. Save if changes made
    if updated:
        # Sort entire archive by date before saving
        all_activities.sort(key=lambda x: x.get('start_date', ''))
        
        with open(archive_file, 'w') as f:
            json.dump(all_activities, f, indent=4)
        print(f"✅ Archive updated. Total count: {len(all_activities)}")
    else:
        print("✅ Archive is already up to date.")
        
    # Return the data filtered to ONLY the requested years for processing
    # (The archive might hold 2015, but if we only want 2024-2025, we return those)
    filtered_data = [
        a for a in all_activities 
        if int(a.get('start_date', '')[:4]) in target_years
    ]
    return filtered_data

def _fetch_year(access_token, year):
    """Fetch every activity in the given calendar year."""
    dt_start = datetime(year, 1, 1)
    # End of year is Start of next year
    dt_end = datetime(year + 1, 1, 1)
    return _fetch_pages(access_token, dt_start.timestamp(), dt_end.timestamp())

def _fetch_pages(access_token, after_ts, before_ts):
    """Page through GET /athlete/activities for [after_ts, before_ts), 200
    per page (Strava's max) until a page comes back empty. Note this always
    issues one extra request past the last page of real data to confirm
    there's nothing left.

    Deliberately does NOT catch StravaAPIError here — a failed page (rate
    limit exhausted, server error, …) must never be treated the same as a
    legitimate empty page. Silently breaking on either would make a
    partial, incomplete fetch indistinguishable from "that's everything,"
    and the archive would end up quietly missing activities with no sign
    anything went wrong. Callers (maintain_archive, and above that
    run_pipeline.py / app.py's Sync Now) are responsible for surfacing the
    error instead."""
    activities = []
    page = 1
    while True:
        params = {'per_page': 200, 'page': page, 'after': int(after_ts), 'before': int(before_ts)}
        response = _strava_request(
            'GET', "https://www.strava.com/api/v3/athlete/activities",
            headers={'Authorization': f"Bearer {access_token}"},
            params=params
        )
        data = response.json()
        if not data: break
        activities.extend(data)
        page += 1
    return activities