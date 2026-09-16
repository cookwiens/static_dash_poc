"""
generate_sample_data.py
-----------------------
Produces DEMO data files (ed_visits.json, wastewater.json, narrative.json) so the
static site has something to render out of the box. This is placeholder/synthetic
data only -- swap this logic out for your real data pipeline (see notebook/ for the
JSON schema each file must follow).

Both ED and wastewater demo series intentionally span the SAME ~52-week window so you
can see the "shared x-axis" behavior working: ED points fall on Sundays (weekly
aggregation), wastewater points fall on irregular days, ~2-3 per week.

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

# Anchor date for the demo, chosen (arbitrarily) to land mid-flu-season so the sample
# charts show a full seasonal ramp-up/peak/decline. Not tied to the real calendar date --
# your real notebook run should use `date.today()`.
TODAY = date(2026, 3, 1)


def sunday_of_week(d: date) -> date:
    """Return the Sunday on/before date d (ED weeks are always labeled by their Sunday)."""
    offset = (d.weekday() + 1) % 7  # Python: Monday=0 ... Sunday=6
    return d - timedelta(days=offset)


def seasonal_curve(day_index, peak_day, peak_height, base, width_days=45, cycle=364):
    """Bell-shaped seasonal curve over a `cycle`-day year."""
    dist = min(abs(day_index - peak_day), cycle - abs(day_index - peak_day))
    return base + peak_height * math.exp(-(dist ** 2) / (2 * width_days ** 2))


# ---------------------------------------------------------------------------
# Shared 52-week window used by BOTH ed_visits.json and wastewater.json
# ---------------------------------------------------------------------------
WINDOW_END = sunday_of_week(TODAY)
WINDOW_START = WINDOW_END - timedelta(weeks=51)  # 52 Sundays total, inclusive

PATHOGEN_ED_CONFIG = {
    "covid": dict(peak_week=40, peak_height=28, base=4, noise=1.4, prev_scale=0.8),
    "influenza": dict(peak_week=43, peak_height=42, base=2, noise=1.8, prev_scale=1.15),
    "rsv": dict(peak_week=37, peak_height=20, base=1.5, noise=1.1, prev_scale=0.9),
}


def build_ed_series(peak_week, peak_height, base, noise, prev_scale):
    weeks = [WINDOW_START + timedelta(weeks=i) for i in range(52)]
    dates_iso = [w.isoformat() for w in weeks]

    current, previous = [], []
    for i, w in enumerate(weeks):
        day_idx = i * 7
        val = seasonal_curve(day_idx, peak_week * 7, peak_height, base) + random.gauss(0, noise)
        current.append(None if w > TODAY else round(max(val, 0), 1))
        pval = seasonal_curve(day_idx, peak_week * 7, peak_height * prev_scale, base) + random.gauss(0, noise)
        previous.append(round(max(pval, 0), 1))
    return dates_iso, current, previous


ed_payload = {"generated": TODAY.isoformat(), "unit": "Rate per 100,000 ED visits", "pathogens": []}

for key, cfg in PATHOGEN_ED_CONFIG.items():
    dates_iso, current, previous = build_ed_series(**cfg)
    prev_start = WINDOW_START.replace(year=WINDOW_START.year - 1)
    prev_end = WINDOW_END.replace(year=WINDOW_END.year - 1)
    ed_payload["pathogens"].append(
        {
            "key": key,
            "label": "COVID-19" if key == "covid" else ("RSV" if key == "rsv" else "Influenza"),
            "current_label": f"Current ({WINDOW_START.strftime('%b %Y')}\u2013{WINDOW_END.strftime('%b %Y')})",
            "previous_label": f"Prior year ({prev_start.strftime('%b %Y')}\u2013{prev_end.strftime('%b %Y')})",
            "dates": dates_iso,
            "current": current,
            "previous": previous,
        }
    )

with open(OUT_DIR / "ed_visits.json", "w") as f:
    json.dump(ed_payload, f, indent=2)


# ---------------------------------------------------------------------------
# Wastewater: same 52-week window, irregular sample days, ~2-3 samples/week
# ---------------------------------------------------------------------------
WW_CONFIG = {
    "covid": dict(peak_week=40, peak_height=1800, base=150, noise=90),
    "influenza": dict(peak_week=43, peak_height=2600, base=60, noise=120),
    "rsv": dict(peak_week=37, peak_height=1200, base=40, noise=70),
}

# irregular sample days across the same 364-day window (~2-3x/week)
sample_offsets = []
day = 0
while WINDOW_START + timedelta(days=day) <= WINDOW_END:
    sample_offsets.append(day)
    day += random.choice([2, 3, 4])

ww_payload = {"generated": TODAY.isoformat(), "unit": "Viral gene copies / L (7-day trend)", "pathogens": []}

for key, cfg in WW_CONFIG.items():
    points = []
    for off in sample_offsets:
        d = WINDOW_START + timedelta(days=off)
        val = seasonal_curve(off, cfg["peak_week"] * 7, cfg["peak_height"], cfg["base"])
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


# ---------------------------------------------------------------------------
# Narrative summary — demonstrates the allowed HTML tags: <b> <i> <hr> <br>
# ---------------------------------------------------------------------------
narrative_html = (
    "<b>Respiratory illness activity remains at seasonal-expected levels</b> across "
    "Lawrence and Douglas County as of late February.<br>"
    "Influenza continues to account for the largest share of ED visits this season, "
    "with wastewater signal <i>trending slightly upward</i> over the past two weeks.<hr>"
    "COVID-19 activity is stable and below last year's levels at this point in the season. "
    "RSV activity has passed its seasonal peak and is <i>declining</i>.<br><br>"
    "<b>Recommendation:</b> Residents who are eligible are encouraged to stay up to date on "
    "vaccinations. Testing and vaccination information is available at ldchealth.org."
)

narrative_payload = {"generated": TODAY.isoformat(), "html": narrative_html}

with open(OUT_DIR / "narrative.json", "w") as f:
    json.dump(narrative_payload, f, indent=2)

print("Wrote:", OUT_DIR / "ed_visits.json")
print("Wrote:", OUT_DIR / "wastewater.json")
print("Wrote:", OUT_DIR / "narrative.json")
