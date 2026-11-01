"""Wind: a rose of 16 directions by speed class from ten full years of hourly wind at 10 m (Open-Meteo archive, ERA5).

python wind.py --site SITE_DIR --out CLIMATE_DIR [--years 10]
"""
import argparse
import csv
import datetime as dt
from pathlib import Path

import numpy as np
import requests

from common import UA, Site, write_json

NAMES = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
CLASSES = [(0.5, 2), (2, 4), (4, 6), (6, 99)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--years", type=int, default=10)
    a = ap.parse_args()
    S, out = Site(a.site), Path(a.out)
    y = dt.date.today().year
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", headers=UA, timeout=300, params=dict(
        latitude=S.lat, longitude=S.lon, start_date=f"{y - a.years}-01-01", end_date=f"{y - 1}-12-31",
        hourly="wind_speed_10m,wind_direction_10m", wind_speed_unit="ms", timezone="auto"))
    r.raise_for_status()
    h = r.json()["hourly"]
    t = np.array(h["time"])
    v = np.array(h["wind_speed_10m"], float)
    d = np.array(h["wind_direction_10m"], float)
    ok = ~(np.isnan(v) | np.isnan(d))
    t, v, d = t[ok], v[ok], d[ok]
    month = np.array([int(s[5:7]) for s in t])
    sec = ((d + 11.25) // 22.5).astype(int) % 16
    south = S.lat < 0
    seasons = {"year": month > 0,
               "winter": np.isin(month, [6, 7, 8] if south else [12, 1, 2]),
               "summer": np.isin(month, [12, 1, 2] if south else [6, 7, 8])}
    rows, summary = [], {}
    for s, sel in seasons.items():
        n = sel.sum()
        tot = []
        for i, nm in enumerate(NAMES):
            row = {"season": s, "direction": nm}
            for lo, hi in CLASSES:
                lab = f"{lo:g}-{hi} m/s" if hi < 99 else f"{lo}+ m/s"
                row[lab] = round(100 * float(((sec[sel] == i) & (v[sel] >= lo) & (v[sel] < hi)).sum()) / n, 2)
            row["total %"] = round(sum(x for k, x in row.items() if k.endswith("m/s")), 2)
            rows.append(row)
            tot.append(row["total %"])
        o = np.argsort(tot)[::-1]
        summary[s] = dict(prevailing=NAMES[o[0]], prevailing_pct=tot[o[0]], second=NAMES[o[1]], second_pct=tot[o[1]],
                          calm_pct=round(100 * float((v[sel] < 0.5).mean()), 1), mean_ms=round(float(v[sel].mean()), 1),
                          strong_pct=round(100 * float((v[sel] >= 6).mean()), 1), hours=int(n))
    with open(out / "wind.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summary["sources"] = [f"Open-Meteo Historical Weather API, ERA5 reanalysis (about 25 km grid), hourly wind at 10 m, "
                          f"{y - a.years}-{y - 1}, CC BY 4.0", "Winter and summer are the three coldest and warmest months; calm is below 0.5 m/s"]
    write_json(out / "wind.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
