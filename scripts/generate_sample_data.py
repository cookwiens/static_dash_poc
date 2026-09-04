"""
generate_sample_data.py
-----------------------
Produces DEMO data files (assets/data/ed_visits.json and wastewater.json) so the
static site has something to render out of the box. This is placeholder/synthetic
data only -- swap this logic out for your real data pipeline (see the
notebook_data_prep.ipynb template for the JSON schema each file must follow).

Run from the repo root:  python scripts/generate_sample_data.py
"""
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(7)

OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TODAY = date(2026, 9, 4)  # anchor date for the demo


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday-start weeks


def seasonal_curve(week_index, peak_week, peak_height, base, width=7):
    """Bell-shaped seasonal curve for 52 weekly points (week_index 0..51)."""
    dist = min(abs(week_index - peak_week), 52 - abs(week_index - peak_week))
    return base + peak_height * math.exp(-(dist ** 2) / (2 * width ** 2))


def build_season(peak_week, peak_height, base, noise, prev_scale):
    """Return (week_labels, current[52], previous[52]) ending at 'today'."""
    current_start = week_start(TODAY) - timedelta(weeks=51)
    weeks = [current_start + timedelta(weeks=i) for i in range(52)]
    week_labels = [w.strftime("%b %-d") if hasattr(w, "strftime") else str(w) for w in weeks]

    current, previous = [], []
    for i, w in enumerate(weeks):
        val = seasonal_curve(i, peak_week, peak_height, base) + random.gauss(0, noise)
        current.append(round(max(val, 0), 1))
        pval = seasonal_curve(i, peak_week, peak_height * prev_scale, base) + random.gauss(0, noise)
        previous.append(round(max(pval, 0), 1))

    # Truncate "current" so it doesn't extend into the future beyond today
    for i, w in enumerate(weeks):
        if w > TODAY:
            current[i] = None
    return week_labels, current, previous, current_start


PATHOGEN_ED_CONFIG = {
    "covid": dict(peak_week=14, peak_height=28, base=4, noise=1.4, prev_scale=0.8),   # ~mid-Dec peak
    "influenza": dict(peak_week=17, peak_height=42, base=2, noise=1.8, prev_scale=1.15),  # ~early-Jan peak
    "rsv": dict(peak_week=11, peak_height=20, base=1.5, noise=1.1, prev_scale=0.9),   # ~late-Nov peak
}

ed_payload = {
    "generated": TODAY.isoformat(),
    "unit": "Rate per 100,000 ED visits",
    "pathogens": [],
}

labels_for_prev = {}
for key, cfg in PATHOGEN_ED_CONFIG.items():
    week_labels, current, previous, current_start = build_season(**cfg)
    prev_label_start = current_start.replace(year=current_start.year - 1)
    ed_payload["pathogens"].append(
        {
            "key": key,
            "label": key.upper() if key == "rsv" else key.capitalize() if key != "covid" else "COVID-19",
            "current_label": f"Current ({current_start.strftime('%b %Y')}\u2013{TODAY.strftime('%b %Y')})",
            "previous_label": f"Prior year ({prev_label_start.strftime('%b %Y')}\u2013{prev_label_start.strftime('%Y')})",
            "week_labels": week_labels,
            "current": current,
            "previous": previous,
        }
    )

with open(OUT_DIR / "ed_visits.json", "w") as f:
    json.dump(ed_payload, f, indent=2)


# ---- Wastewater: irregular sampling dates, ~2x/week, last 6 months ----
WW_CONFIG = {
    "covid": dict(peak_day=75, peak_height=1800, base=150, noise=90),
    "influenza": dict(peak_day=110, peak_height=2600, base=60, noise=120),
    "rsv": dict(peak_day=45, peak_height=1200, base=40, noise=70),
}

ww_start = TODAY - timedelta(days=182)

ww_payload = {
    "generated": TODAY.isoformat(),
    "unit": "Viral gene copies / L (7-day trend)",
    "pathogens": [],
}

# irregular sample days (roughly twice a week, skips holidays/missed samples)
sample_offsets = []
day = 0
while ww_start + timedelta(days=day) <= TODAY:
    sample_offsets.append(day)
    day += random.choice([3, 4])

for key, cfg in WW_CONFIG.items():
    points = []
    for off in sample_offsets:
        d = ww_start + timedelta(days=off)
        dist = min(abs(off - cfg["peak_day"]), 365 - abs(off - cfg["peak_day"]))
        val = cfg["base"] + cfg["peak_height"] * math.exp(-(dist ** 2) / (2 * 30 ** 2))
        val += random.gauss(0, cfg["noise"])
        points.append({"date": d.isoformat(), "value": round(max(val, 0))})
    ww_payload["pathogens"].append(
        {
            "key": key,
            "label": "COVID-19" if key == "covid" else ("RSV" if key == "rsv" else "Influenza"),
            "points": points,
        }
    )

with open(OUT_DIR / "wastewater.json", "w") as f:
    json.dump(ww_payload, f, indent=2)

print("Wrote:", OUT_DIR / "ed_visits.json")
print("Wrote:", OUT_DIR / "wastewater.json")
