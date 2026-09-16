"""
Builds notebook_data_prep.ipynb via raw nbformat v4 JSON (no nbformat package needed).
Run once to (re)generate the .ipynb template; edit the resulting notebook directly afterward.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent.parent / "outputs_staging" / "notebook_data_prep.ipynb"

def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}

def code(src):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src.splitlines(keepends=True)}

cells = []

cells.append(md("""# Lawrence-Douglas County Public Health
## Respiratory Surveillance Dashboard — Data Prep & Site Build

This notebook is the **data pipeline half** of the static dashboard. It is responsible for:

1. Downloading / loading your raw ED visit and wastewater data
2. Transforming each into the small JSON schema the website's JavaScript expects
3. Writing a short **narrative summary** (with limited HTML formatting) for the "Current
   Situation" section
4. Writing all three JSON files into the site's `assets/data/` folder
5. Stamping a "generated" date so the page can show *Data updated: ...*

The **site template itself** (`index.html`, `assets/css/styles.css`, `assets/js/main.js`,
and the vendored `assets/js/vendor/chart.min.js`) does **not** need to be regenerated each
run — you only overwrite the three JSON files and re-push to GitHub Pages.

> ⚠️ **Before you run this for real, read the "A note on ED counts vs. rates" cell below** —
> it affects whether your previous-year ED comparison is apples-to-apples.
"""))

cells.append(code("""import json
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
import numpy as np

# Path to the static site folder (the one you will push to GitHub Pages).
# Adjust this to wherever you keep the site repo checked out.
SITE_DIR = Path("../ldcph-site")            # <-- EDIT ME
DATA_DIR = SITE_DIR / "assets" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TODAY = date.today()
print("Writing data as of:", TODAY.isoformat())
"""))

cells.append(md("""## A note on ED counts vs. rates (please read)

You mentioned that for **ED visits** you can provide the *current* period as a **rate**
(e.g., per 100,000 visits) but for the **prior year** you may only have raw **counts**.
Rates and counts are not directly comparable — a season with more total ED visits could
show a higher *count* than the current year while actually having a *lower rate*.

Before overlaying "current" and "previous" on the same axis, pick one:

1. **Best: convert prior-year counts to a rate** using the same denominator logic you use
   for the current period (e.g., `rate = count / total_ed_visits_that_week * 100000`).
   This keeps the chart's dual-line comparison honest and is what the site template below
   assumes (`current` and `previous` arrays share one `unit`).
2. **If you truly cannot get a comparable denominator for last year**, don't force it onto
   one axis. Options, roughly in order of preference:
   - Plot prior year as a *separate* small chart/stat ("year-ago count") rather than an
     overlay, with its own clearly labeled units.
   - Convert both series to an index (e.g., "% of that pathogen's peak week") purely to
     compare *shape/timing*, and say so explicitly in a caption — never imply the
     magnitudes are equivalent.
   - Only as a last resort, use a dual-axis chart (rate on the left, count on the right).
     Dual-axis charts are easy to misread, so if you go this route, label both axes boldly
     and consider adding a one-line disclaimer under the chart.

The transform functions below assume option 1 (both series already the same unit). If you
need option 2 or 3, flag it and the JS/CSS can be extended with a second y-axis or an
index-mode toggle — it's a small change, just not the default.
"""))

cells.append(md("""## A note on the shared ED / wastewater x-axis

The site automatically gives each pathogen's ED chart and wastewater chart the **same
date range and the same tick marks**, so the two charts line up visually. This is handled
entirely in `assets/js/main.js` (`computeSharedXAxis`) — you don't need to do anything
special in this notebook beyond providing real calendar dates for both series:

- **ED visits**: always weekly, plotted on the **Sunday** of each week. Use actual ISO
  dates (`YYYY-MM-DD`), not just week numbers or formatted label strings.
- **Wastewater**: irregular sample days (commonly 2–3 per week). Use the actual sample
  collection date for each observation.

As long as both series use real calendar dates that cover roughly the same period, the
two charts for a given pathogen will automatically share an aligned x-axis.
"""))

cells.append(md("""## Step 1 — Load your raw data

Replace the two loader functions below with however you actually pull this data today
(local CSV/Excel export, a database query, an API call, etc.). The only requirement is
that you end up with a pandas DataFrame in roughly the shape shown.
"""))

cells.append(code("""def load_ed_visits() -> pd.DataFrame:
    \"\"\"
    TODO: replace with your real ED-visit data source.

    Expected shape — one row per week (Sunday-dated), wide format:
        week_end_date | covid_rate | covid_rate_prior | flu_rate | flu_rate_prior | rsv_rate | rsv_rate_prior

    'week_end_date' = the Sunday for that week (an actual date, not a label string)
    'covid_rate' etc. = current period rate (per 100,000 ED visits)
    'covid_rate_prior' etc. = same calendar week, PRIOR year (rate — see note above)
    \"\"\"
    # Example of reading a local export:
    # return pd.read_csv("raw/ed_visits_weekly.csv", parse_dates=["week_end_date"])
    raise NotImplementedError("Wire this up to your real ED visits source.")


def load_wastewater() -> pd.DataFrame:
    \"\"\"
    TODO: replace with your real wastewater data source.

    Expected shape — one row per sample date (irregular, ~2-3x/week), wide format:
        sample_date | covid_level | flu_level | rsv_level

    No prior-year columns needed here (wastewater side has no year-over-year requirement).
    \"\"\"
    # return pd.read_csv("raw/wastewater_results.csv", parse_dates=["sample_date"])
    raise NotImplementedError("Wire this up to your real wastewater source.")
"""))

cells.append(md("""## Step 2 — Transform to the site's JSON schema

These two functions are generic — you shouldn't need to touch them, just the
`PATHOGEN_ED_CONFIG` / `PATHOGEN_WW_CONFIG` dictionaries that map each pathogen to your
actual column names.
"""))

cells.append(code("""def build_ed_json(df: pd.DataFrame, date_col: str, pathogen_config: dict,
                   unit: str = "Rate per 100,000 ED visits") -> dict:
    df = df.sort_values(date_col).reset_index(drop=True)
    dates = pd.to_datetime(df[date_col])

    # Sanity check: ED dates should all be Sundays (weekday() == 6)
    non_sundays = dates[dates.dt.weekday != 6]
    if len(non_sundays):
        print(f"WARNING: {len(non_sundays)} ED date(s) are not Sundays — check your source data.")

    current_label = f"Current ({dates.min():%b %Y}\u2013{dates.max():%b %Y})"
    prev_start = dates.min() - pd.DateOffset(years=1)
    prev_end = dates.max() - pd.DateOffset(years=1)
    previous_label = f"Prior year ({prev_start:%b %Y}\u2013{prev_end:%b %Y})"

    payload = {"generated": TODAY.isoformat(), "unit": unit, "pathogens": []}
    for key, cfg in pathogen_config.items():
        payload["pathogens"].append({
            "key": key,
            "label": cfg["label"],
            "current_label": cfg.get("current_label", current_label),
            "previous_label": cfg.get("previous_label", previous_label),
            "dates": [d.date().isoformat() for d in dates],
            "current": [None if pd.isna(v) else round(float(v), 1) for v in df[cfg["current_col"]]],
            "previous": [None if pd.isna(v) else round(float(v), 1) for v in df[cfg["previous_col"]]],
        })
    return payload


def build_wastewater_json(df: pd.DataFrame, date_col: str, pathogen_config: dict,
                           unit: str = "Viral gene copies / L (7-day trend)") -> dict:
    df = df.sort_values(date_col).reset_index(drop=True)
    payload = {"generated": TODAY.isoformat(), "unit": unit, "pathogens": []}
    for key, cfg in pathogen_config.items():
        sub = df[[date_col, cfg["value_col"]]].dropna()
        points = [
            {"date": pd.to_datetime(d).date().isoformat(), "value": round(float(v), 1)}
            for d, v in zip(sub[date_col], sub[cfg["value_col"]])
        ]
        payload["pathogens"].append({"key": key, "label": cfg["label"], "points": points})
    return payload
"""))

cells.append(code("""PATHOGEN_ED_CONFIG = {
    "covid":     {"label": "COVID-19",   "current_col": "covid_rate", "previous_col": "covid_rate_prior"},
    "influenza": {"label": "Influenza",  "current_col": "flu_rate",   "previous_col": "flu_rate_prior"},
    "rsv":       {"label": "RSV",        "current_col": "rsv_rate",   "previous_col": "rsv_rate_prior"},
}

PATHOGEN_WW_CONFIG = {
    "covid":     {"label": "COVID-19",  "value_col": "covid_level"},
    "influenza": {"label": "Influenza", "value_col": "flu_level"},
    "rsv":       {"label": "RSV",       "value_col": "rsv_level"},
}
"""))

cells.append(md("""## Step 3 — Write the "Current Situation" narrative

Enter your short status update directly below as an HTML string. This replaces the old
"At a Glance" stat tiles with a single free-text summary that appears at the top of the
site.

**Allowed HTML tags:** `<b>` `<i>` `<hr>` `<br>` (plus `<strong>`, `<em>`, `<u>`, `<p>` as
equivalents/conveniences). Anything else — including any `<script>`, `<div>`, inline
styles, or `onclick`-style attributes — is stripped out by the site's built-in sanitizer
before it's displayed, so pasting in something unexpected won't break the page or expose
it to injected code. If you want to allow additional tags later, that's a one-line change
in `assets/js/main.js` (`ALLOWED_NARRATIVE_TAGS`).
"""))

cells.append(code('''NARRATIVE_HTML = """
<b>Respiratory illness activity remains at seasonal-expected levels</b> across
Lawrence and Douglas County.<br>
Influenza continues to account for the largest share of ED visits this season, with
wastewater signal <i>trending slightly upward</i> over the past two weeks.<hr>
COVID-19 activity is stable and below last year's levels at this point in the season.
RSV activity has passed its seasonal peak and is <i>declining</i>.<br><br>
<b>Recommendation:</b> Residents who are eligible are encouraged to stay up to date on
vaccinations. Testing and vaccination information is available at ldchealth.org.
"""

narrative_payload = {"generated": TODAY.isoformat(), "html": NARRATIVE_HTML.strip()}
'''))

cells.append(md("## Step 4 — Run the pipeline and write all three JSON files"))

cells.append(code("""ed_df = load_ed_visits()
ww_df = load_wastewater()

ed_payload = build_ed_json(ed_df, date_col="week_end_date", pathogen_config=PATHOGEN_ED_CONFIG)
ww_payload = build_wastewater_json(ww_df, date_col="sample_date", pathogen_config=PATHOGEN_WW_CONFIG)

with open(DATA_DIR / "ed_visits.json", "w") as f:
    json.dump(ed_payload, f, indent=2)

with open(DATA_DIR / "wastewater.json", "w") as f:
    json.dump(ww_payload, f, indent=2)

with open(DATA_DIR / "narrative.json", "w") as f:
    json.dump(narrative_payload, f, indent=2)

print("Wrote", DATA_DIR / "ed_visits.json")
print("Wrote", DATA_DIR / "wastewater.json")
print("Wrote", DATA_DIR / "narrative.json")
"""))

cells.append(md("""## Step 5 — Push to GitHub Pages

Once the three JSON files are refreshed, commit and push the whole `ldcph-site/` folder
(or just the changed JSON files) to your GitHub Pages repo:

```bash
cd ldcph-site
git add assets/data/ed_visits.json assets/data/wastewater.json assets/data/narrative.json
git commit -m "Data refresh: $(date +%F)"
git push
```

If you want this fully hands-off, wrap Steps 1–5 in a scheduled job (cron, GitHub Actions
on a schedule, Task Scheduler, etc.) that runs this notebook (e.g., via `papermill` or
`jupyter nbconvert --execute`) and then runs the git commands above — though you'll likely
want to keep writing the narrative by hand each time, since it's meant to be a human's
short interpretation of the data, not an auto-generated one.
"""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.x"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w") as f:
    json.dump(nb, f, indent=1)
print("Wrote", OUT)
