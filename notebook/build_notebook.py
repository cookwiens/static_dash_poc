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
3. Writing those JSON files into the site's `assets/data/` folder
4. Stamping a "generated" date so the page can show *Data updated: ...*

The **site template itself** (`index.html`, `assets/css/styles.css`, `assets/js/main.js`,
and the vendored `assets/js/vendor/chart.min.js`) does **not** need to be regenerated each
run — you only overwrite the two JSON files and re-push to GitHub Pages.

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

cells.append(md("""## Step 1 — Load your raw data

Replace the two loader functions below with however you actually pull this data today
(local CSV/Excel export, a database query, an API call, etc.). The only requirement is
that you end up with a pandas DataFrame in roughly the shape shown.
"""))

cells.append(code("""def load_ed_visits() -> pd.DataFrame:
    \"\"\"
    TODO: replace with your real ED-visit data source.

    Expected shape — one row per week, wide format:
        week_end_date | covid_rate | covid_rate_prior | flu_rate | flu_rate_prior | rsv_rate | rsv_rate_prior

    'covid_rate' etc. = current period rate (per 100,000 ED visits)
    'covid_rate_prior' etc. = same calendar week, PRIOR year (rate — see note above)
    \"\"\"
    # Example of reading a local export:
    # return pd.read_csv("raw/ed_visits_weekly.csv", parse_dates=["week_end_date"])
    raise NotImplementedError("Wire this up to your real ED visits source.")


def load_wastewater() -> pd.DataFrame:
    \"\"\"
    TODO: replace with your real wastewater data source.

    Expected shape — one row per sample date, wide format:
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
    week_labels = [d.strftime("%b %-d") for d in dates]

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
            "week_labels": week_labels,
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

cells.append(md("## Step 3 — Run the pipeline and write the JSON files"))

cells.append(code("""ed_df = load_ed_visits()
ww_df = load_wastewater()

ed_payload = build_ed_json(ed_df, date_col="week_end_date", pathogen_config=PATHOGEN_ED_CONFIG)
ww_payload = build_wastewater_json(ww_df, date_col="sample_date", pathogen_config=PATHOGEN_WW_CONFIG)

with open(DATA_DIR / "ed_visits.json", "w") as f:
    json.dump(ed_payload, f, indent=2)

with open(DATA_DIR / "wastewater.json", "w") as f:
    json.dump(ww_payload, f, indent=2)

print("Wrote", DATA_DIR / "ed_visits.json")
print("Wrote", DATA_DIR / "wastewater.json")
"""))

cells.append(md("""## Step 4 — Push to GitHub Pages

Once the two JSON files are refreshed, commit and push the whole `ldcph-site/` folder
(or just the changed JSON files) to your GitHub Pages repo:

```bash
cd ldcph-site
git add assets/data/ed_visits.json assets/data/wastewater.json
git commit -m "Data refresh: $(date +%F)"
git push
```

If you want this fully hands-off, wrap Steps 1–4 in a scheduled job (cron, GitHub Actions
on a schedule, Task Scheduler, etc.) that runs this notebook (e.g., via `papermill` or
`jupyter nbconvert --execute`) and then runs the git commands above.
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
