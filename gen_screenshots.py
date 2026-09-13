"""
Generate README screenshots from real activity data.
Run once: python gen_screenshots.py
"""
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

from src import config, process_data
from src.charts import make_equity_annual_chart

OUT_DIR = 'docs/screenshots'
os.makedirs(OUT_DIR, exist_ok=True)

# --- Load data ---
with open(config.ACTIVITIES_FILE) as f:
    all_activities = json.load(f)

# Merge per-year files for years not in archive
present_years = {int(a.get('start_date', a.get('start_date_local', ''))[:4])
                 for a in all_activities if a.get('start_date') or a.get('start_date_local')}
for fname in os.listdir(config.RAW_DIR):
    stem = fname[:-5]
    if fname.endswith('.json') and stem.isdigit() and int(stem) not in present_years:
        with open(os.path.join(config.RAW_DIR, fname)) as f:
            extra = json.load(f)
        if isinstance(extra, list):
            all_activities.extend(extra)

df = process_data.process_activities(all_activities)
print(f"Loaded {len(df)} activities, years {sorted(df['year'].unique().tolist())}")

current_year = date.today().year

with open(config.SETTINGS_FILE) as f:
    settings = json.load(f)

# --- Combined / equity annual (thin) ---
equity_yearly = process_data.aggregate_equity_by_year(df, settings)
fig = make_equity_annual_chart(equity_yearly, current_year, height=300)
fig.write_image(os.path.join(OUT_DIR, 'combined_annual.png'), width=1200, height=300)
print("wrote combined_annual.png")

print("Done.")
