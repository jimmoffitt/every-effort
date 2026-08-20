# Every Effort

*A personal dashboard for people who ride, ski, swim, run, and hike — and want to combine every effort into an one overall measurement of workout effort and be able to set goals across a mix of activity types.*

I really enjoy biking. So a lot of my "how's this year going" questions are informed by my bike miles. I also really like to ride on snow and swim. A week of skiing or swimming doesn't produce a mileage number that means anything next to a bike ride. 

I also really like the Strava app and appreciate that their platform provides APIs for retrieving your data. 

This app's main reason for existing is one idea: **equity miles**, a common scalar that converts every sport's effort into the currency of whichever sport you actually care about, so "was this a better year than last year?" has a real answer no matter which sports made up your training.

Another seed was wanting to trigger a Wrapped story when I wanted and for any period of interest. And Strava's own "Wrapped" doesn't really focus much on "combined" measurements. 

This prototype was built on top of Streamlit. This app is sidebar-driven: 
+ **View** pages for Bike, Snow, Swim, Running, and Hiking (pick which ones show up in Settings) 
+ **Combined** cross-sport equity view 
+ **Wrapped-style summary** 
+ **Tools** for full-text activity search and data export
+ **Settings** area split into four focused sub-pages 

Data syncs directly from the Strava API and is stored locally — nothing leaves your machine.

**🚀 Live demo: [every-effort.streamlit.app](https://every-effort.streamlit.app/)** — a read-only build with a sanitized copy of the real dataset (see [How the demo works](#how-the-demo-works)). Works nicely on a phone too: open it in Safari and use Share → *Add to Home Screen*.

> **Not affiliated with, endorsed by, or sponsored by Strava.** This is an independent, unofficial project built against Strava's public API. "Strava" and the Strava logo are trademarks of Strava, Inc.

![Every Effort dashboard](docs/screenshots/app-ui.png)

---

## User guide

A tour of the app from a user's point of view — what each tab shows and how the pieces fit together. If you just want to run your own copy, skip ahead to the [Developer guide](#developer-guide).

### Multi-sport dashboard

The sidebar reads top-to-bottom: **View** (the five sport/summary pages), a Dark mode toggle, **Data Sync** (archive count, last-sync age, and the Sync Now button), **Settings**, **Tools**, and a link back to this repo at the bottom.

![Sidebar — View, Dark mode, Data Sync, Settings, Tools](docs/screenshots/main-sidebar.png)

Each entry swaps the entire main panel for that page — no page reload, since it's all one Streamlit app.

### Sport summaries

Every sport view opens the same way: an all-time stats line and a full-width overview chart.

**Bike** — all-time stats; a "top bikes" ranking by lifetime miles; an annual distance chart paired with a route-heatmap thumbnail; an all-time "which months do I ride" chart; a gear filter; and the full interactive route heatmap at the bottom.

![Bike tab — all-time stats and annual overview](docs/screenshots/bike.png)

**Snow** — all-time stats in vertical feet; a season-by-season overview chart; and a full season log.

![Snow tab — all-time stats and season-by-season overview](docs/screenshots/snow.png)

**Swim** — all-time stats and a multi-year overview chart.

![Swim tab — all-time stats and annual overview](docs/screenshots/swim.png)

### Exploring a period

Below the all-time overview, every sport tab has its own period section — pick a year (or season for Snow, with an "All time" option for Swim), and get a distance-by-month chart with goal-pace tracking, plus ranked tables for recent activities, longest efforts, and top months, all scoped to that period.

![Snow tab — season detail with goal progress and monthly vert](docs/screenshots/snow-period.png)

### Live data sync

<img src="docs/screenshots/data-sync.png" alt="Data Sync sidebar section — archive count, last sync, latest activity, Sync Now" width="220" align="right">

The sidebar shows the total archive count, how long ago the last sync ran, and a one-line summary of the most recent logged activity (date/time, sport, distance). Click **Sync Now** to pull new activities from Strava without leaving the browser — it runs an incremental fetch, clears the data cache, and reloads automatically so every chart reflects the new data immediately.

Past years are fetched once and archived. Only the current year is re-checked on each sync, so a sync stays fast no matter how much history is in the archive.

<br clear="right">

### Equity miles

Different sports aren't directly comparable by distance, so this dashboard normalizes everything to a common "bike mile" unit:

| Sport | Default conversion |
|---|---|
| Bike | 1 mile = 1 equity mile (reference) |
| Swim | 100 meters = 1 equity mile |
| Ski  | 1,000 vertical feet = 1 equity mile |

The **Combined** tab stacks equity miles by sport for each year so you can see total fitness output regardless of which sports you focused on. Conversion rates are configurable in the Settings tab.

![Combined tab — equity miles stacked by sport, per year](docs/screenshots/combined_annual.png)

Activities with equity markers in their name (`SEq`, `HEq`, `GEq`, etc.) are manual equity declarations — they're listed separately and excluded from calculated totals to avoid double-counting.

### Wrapped Stories

Pick any rolling window (last 365 days, last 30 days, a specific year or month) and a sport filter to get a period-in-review summary: hero stats, top sports, monthly rhythm, an activity calendar, and a weekly-streak card. A "Play Wrapped Slides" button opens a swipeable story-card carousel for any calendar year, with an HTML download to share it outside the app.

### Tools

![Tools nav in the sidebar](docs/screenshots/tools-nav.png)

**Explore** — full-text search across all activities, with date-range and sport-type filters. Results table with CSV download.

**Export** — annual summaries, monthly breakdowns, and a full activity table, each with PNG download and a combined ZIP.

### Settings

Settings splits into four independent pages — each has its own Save button that merges just its own slice into `data/settings.json`, so editing Goals never touches your Seasons settings, and vice versa. Theme (dark/light) lives as a toggle in the sidebar itself, not in Settings.

![Settings nav in the sidebar](docs/screenshots/settings-nav.png)

#### Sports

Which sports get a dedicated View tab — Combined and Wrapped Stories always cover every sport regardless, this only controls which sports get their own tab (Bike/Snow/Swim on by default, Running/Hiking off).

![Sports settings — Primary Sport Tabs](docs/screenshots/settings-sports-primary.png)

The reference sport that equity miles are expressed in — Bike, Run, or Hike, all distance-based sports that can serve as the common unit.

![Sports settings — Why Equity Miles and Reference Sport](docs/screenshots/settings-sports-reference.png)

The conversion rate from every other sport's native unit into that reference — miles for Run/Hike/Paddle, meters for Swim, vertical feet for Ski.

![Sports settings — Equity Mile Conversions](docs/screenshots/settings-sports-equity-miles.png)

Each tab's default photo — upload your own or point to a file path, falling back to the bundled defaults in `assets/`.

![Sports settings — Sport tab images](docs/screenshots/settings-sports-tab-images.png)

#### Goals

Annual and monthly equity-mile targets, plus two sport-specific goals: Ski's cumulative season vertical feet, and Swim's monthly meters. Bike's monthly mileage goal can be a fixed number, or "derived" — a total monthly target minus what Swim/Ski are expected to contribute that month, based on the Seasons boundaries and Sports conversion rates — with a live preview table of the resulting month-by-month bike targets.

![Goals settings page](docs/screenshots/settings-goals.png)

#### Seasons

Which months count as "in season" for Ski and Swim (Bike, Run, and Hike don't have a season concept yet — every month counts). Controls what shows in each tab's monthly chart, and feeds Goals' derived bike-target calculation.

![Seasons settings page](docs/screenshots/settings-seasons.png)

#### Map

An optional custom home location (lat/lon) so the Bike tab's route heatmap centers on home instead of the median of all your ride start points.

![Map settings page](docs/screenshots/settings-map.png)

---

## Developer guide

For coders who want to set up their own copy of Every Effort against their own Strava data.

This repository contains the code and content needed to deploy your own Every Effort app. This app was built as a Streamlit service.

### Quick start

```bash
# 1. Clone and install
git clone https://github.com/jimmoffitt/every-effort.git
cd every-effort
pip install -r requirements.txt

# 2. Add your Strava credentials
echo "STRAVA_CLIENT_ID=your_id" >> .local.env
echo "STRAVA_CLIENT_SECRET=your_secret" >> .local.env

# 3. Complete the Strava OAuth flow once to get a token
#    See: https://developers.strava.com/docs/getting-started/
#    The token file lives at data/strava_tokens.json

# 4. Fetch your activity history
python run_pipeline.py

# 5. Launch the dashboard
streamlit run app.py
```

After the first run, use the **Sync Now** button in the sidebar for incremental updates.

---

### How the demo works

The [live demo](https://every-effort.streamlit.app/) is the same app in a read-only **demo mode**, deployed on [Streamlit Community Cloud](https://share.streamlit.io) with no credentials on the host.

**Sanitized dataset.** The real activity archive is gitignored (it contains heart rate, power, device, and precise location data). `make_demo_data.py` derives a committable copy at `data/demo/activities.json` by whitelisting only the ~14 fields the app actually reads — id, name, type, dates, distance, times, elevation, gear id, and a couple of counts — plus each ride's `map.summary_polyline`, kept by choice so the bike heatmap renders with real routes in the demo. Exact start/end coordinates, heart rate, power, device names, and location strings are all dropped. A copy of the gear map rides along so bike names render.

**Automatic demo mode.** `DEMO_MODE` in `src/config.py` turns on when `EVERY_EFFORT_DEMO=1` is set, or automatically when the real archive is absent but the demo dataset is present — which is exactly the state of a fresh clone, since `data/` is gitignored. In demo mode every data path is redirected to `data/demo/`, the Sync Now button is replaced with a read-only notice, and runtime writes (settings, sync records) land in `data/demo/` where they're gitignored. Locally, with the real archive present, nothing changes.

**Deployment.** Point [share.streamlit.io](https://share.streamlit.io) at `app.py` on `main` — that's the whole setup. A fresh clone has no real archive, so demo mode enables itself; no secrets or environment configuration are needed. The app redeploys automatically on every push. Two host-friendly details: `requirements.txt` lists direct dependencies with loose version ranges (so the host's Python always gets prebuilt wheels), and the Export tab probes for PNG-rendering capability at runtime, degrading to CSV-only downloads where kaleido has no Chrome to drive.

**Refreshing the demo data.** After a sync, rerun `python make_demo_data.py`, review the printed field/name summary, and commit the updated `data/demo/activities.json`.

---

### How it's built

#### Stack

| Package | Role |
|---|---|
| [Streamlit](https://streamlit.io) | Dashboard framework and UI |
| [Plotly](https://plotly.com/python/) | Interactive charts |
| [pandas](https://pandas.pydata.org) | Data processing and aggregation |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Credentials from `.local.env` |
| [requests](https://docs.python-requests.org) | Strava API calls and token refresh |
| [kaleido](https://github.com/plotly/Kaleido) | Static PNG export (Export tab) |

#### Project structure

```
every-effort/
├── app.py                   # Streamlit dashboard — all page render functions
├── run_pipeline.py          # CLI: fetch → process → publish (static PNGs)
├── make_demo_data.py        # Builds the sanitized data/demo/ dataset for the demo
├── gen_screenshots.py       # Regenerates the chart PNGs embedded in this README
│
├── src/
│   ├── config.py            # Env vars, file paths, sport type constants, DEMO_MODE
│   ├── fetch_data.py        # Strava OAuth, token refresh, incremental archive sync
│   ├── process_data.py      # pandas aggregations: by year, season, month, week
│   ├── charts.py            # Plotly figure factories (one function per chart type)
│   └── publish_data.py      # Matplotlib figure factories (legacy static pipeline)
│
└── data/                    # Local data — not committed to git, except demo/
    ├── raw/                 # my_strava_activities.json + per-year YYYY.json files
    ├── demo/                # Sanitized dataset backing the live demo (committed)
    ├── processed/           # Intermediate outputs from pipeline
    ├── images/              # Static PNGs from pipeline (legacy)
    ├── gear_map.json        # Bike ID → name mapping
    ├── last_data.json       # Last sync timestamp and count
    └── settings.json        # Goals and equity conversion rates
```

#### Data flow

1. `fetch_data.py` pulls activities from the Strava API and appends them to `data/raw/my_strava_activities.json` (a flat JSON array).
2. `app.py` reads the archive on startup via a cached `load_activities()` call, auto-merging any per-year `data/raw/YYYY.json` files for years not already in the main archive.
3. `process_data.process_activities()` converts the raw list to a pandas DataFrame, adding derived columns (`distance_miles`, `elevation_feet`, `final_type`, `year`, `hours`).
4. Each tab's render function calls aggregation helpers (`aggregate_by_year`, `aggregate_ski_by_season`, `aggregate_equity_by_year`, etc.) and passes the results to Plotly figure factories in `charts.py`.

#### Key data fields

```json
{
    "name": "Morning ride",
    "distance": 26215.8,
    "moving_time": 5587,
    "total_elevation_gain": 141.9,
    "type": "Ride",
    "sport_type": "Ride",
    "start_date_local": "2025-06-15T08:30:00Z",
    "gear_id": "b9657721"
}
```

`distance` is meters; `total_elevation_gain` is meters. The processing layer converts to miles and feet.

#### Adding a new chart

1. Add a pure function to `src/charts.py` that accepts a DataFrame and returns a `go.Figure`.
2. Call the aggregation helper you need from `src/process_data.py` (or add one there).
3. Call `st.plotly_chart(your_fig, use_container_width=True)` inside the relevant `render_*` function in `app.py`.

---

### Configuration

#### Credentials — `.local.env`

```
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_YEARS=2024,2025          # optional: years to fetch on first run
```

#### OAuth token — `data/strava_tokens.json`

Generated by completing the Strava OAuth flow once. The pipeline refreshes it automatically every 6 hours. Never commit this file.

```json
{
    "access_token": "...",
    "refresh_token": "...",
    "expires_at": 1234567890,
    "token_type": "Bearer"
}
```

#### Goals and conversions — `data/settings.json`

Created automatically with defaults on first run. Edit via the Settings tab or directly:

```json
{
  "conversions": {
    "swim_meters_per_mile": 100,
    "ski_vert_per_mile": 1000
  },
  "goals": {
    "annual_equity_miles": 3000,
    "monthly_equity_miles": 250,
    "ski_season_vert_ft": 200000,
    "swim_monthly_meters": 10000
  }
}
```

---

## License

[MIT](LICENSE) — do what you like with it.

## Acknowledgments

This prototype was developed using a variety of AI tools. Early designs were made with both ChatGPT and Gemini. To explore Claude Code, that project content was used to kick off a fresh effort using Claude Code. That experiment led to this repository. 



