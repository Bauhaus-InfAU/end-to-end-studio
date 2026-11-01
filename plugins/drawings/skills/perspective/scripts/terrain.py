"""Finds or downloads the ground heights around a site, as a grid CSV: lon, lat, ele, source."""
import csv
import time
from pathlib import Path

import numpy as np

URL = "https://api.opentopodata.org/v1/eudem25m,mapzen"   # EU-DEM 25 m where it covers, else a global model
STEP, MARGIN, BATCH = 50.0, 750.0, 100


def find(scene, out):
    """A terrain.csv in the site folder, else one this skill fetched before."""
    for p in ([scene.site_dir / "terrain.csv"] if scene.site_dir else []) + [Path(out) / "terrain.csv"]:
        if p.exists():
            return p
    return None


def fetch(scene, out):
    """Downloads the grid. Only coordinates are sent. Returns the file, or None if the service fails."""
    import requests
    x0, y0, x1, y1 = scene.site.bounds
    xs = np.arange(x0 - MARGIN, x1 + MARGIN + STEP, STEP)
    ys = np.arange(y0 - MARGIN, y1 + MARGIN + STEP, STEP)
    # one grid in degrees, so the CSV stays regular
    lon0, lat0 = scene.to_lonlat.transform(xs[0], ys[0])
    lon1, lat1 = scene.to_lonlat.transform(xs[-1], ys[-1])
    lons, lats = np.linspace(lon0, lon1, len(xs)), np.linspace(lat0, lat1, len(ys))
    points = [(round(float(lo), 6), round(float(la), 6)) for la in lats for lo in lons]
    rows = []
    try:
        for i in range(0, len(points), BATCH):
            part = points[i:i + BATCH]
            r = requests.post(URL, json={"locations": "|".join(f"{la},{lo}" for lo, la in part), "interpolation": "bilinear"}, timeout=60)
            r.raise_for_status()
            for (lo, la), res in zip(part, r.json()["results"]):
                rows.append((lo, la, res.get("elevation"), res.get("dataset")))
            time.sleep(1.1)
    except Exception as e:
        scene.warn(f"Terrain could not be fetched ({type(e).__name__}): the ground is drawn flat.")
        return None
    path = Path(out) / "terrain.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["lon", "lat", "ele", "source"])
        w.writerows(rows)
    return path
