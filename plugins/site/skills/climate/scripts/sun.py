"""Sun: positions on the key days, shadows of the buildings, and annual sun hours and radiation from an EPW weather file.

python sun.py --site SITE_DIR --out CLIMATE_DIR [--epw FILE] [--buildings FILE] [--cell 10] [--margin 50]

The weather file: --epw, else the first *.epw in the site folder, else a typical year from PVGIS (EU JRC, any place on
land, no key), saved as weather.epw. A sun hour is an hour with direct normal irradiance of 120 W/m2 or more (WMO),
so clouds count. Radiation is on open ground: direct (shaded by the buildings) plus diffuse (sky not reduced by them).
"""
import argparse
import csv
import datetime as dt
from pathlib import Path

import numpy as np
import requests
import shapely

from common import UA, Site, bands, grid, local_to_utc, shadow_hulls, sunpos, timezone, write_json

DAYS = {"21 March": (3, 21), "21 June": (6, 21), "21 December": (12, 21)}
SHADOW_DAYS, SHADOW_HOURS = ("21 March", "21 December"), (9, 12, 15)


def load_epw(site, given, out):
    p = Path(given) if given else next(iter(sorted(site.dir.glob("*.epw"))), None)
    src = f"weather file {p.name}" if p else None
    if not p:
        p = out / "weather.epw"
        for v in ("v5_3", "v5_2"):
            r = requests.get(f"https://re.jrc.ec.europa.eu/api/{v}/tmy", headers=UA, timeout=120,
                             params=dict(lat=round(site.lat, 4), lon=round(site.lon, 4), outputformat="epw"))
            if r.ok and r.text.startswith("LOCATION"):
                p.write_bytes(r.content)
                break
        else:
            raise SystemExit("No weather file: give --epw, or put an .epw in the site folder (PVGIS unreachable).")
        src = f"typical meteorological year from PVGIS {v} (EU JRC, ERA5/SARAH), saved as weather.epw"
    lines = [l for l in p.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    loc = lines[0].split(",")
    rows = [l.split(",") for l in lines[8:]]
    col = lambda i: np.array([float(r[i]) for r in rows])
    E = dict(path=p, source=src, place=loc[1], lat=float(loc[6]), lon=float(loc[7]), tz=float(loc[8]),
             month=col(1).astype(int), day=col(2).astype(int), hour=col(3).astype(int), ghi=col(13), dni=col(14), dhi=col(15))
    # some files keep UTC whatever the header says: take the offset under which the sunshine follows the sun
    best = max({E["tz"], 0.0}, key=lambda tz: np.corrcoef(np.sin(np.radians(np.maximum(sunpos(times(E, tz), E["lat"], E["lon"])[0], 0))), E["ghi"])[0, 1])
    E["tz_header"], E["tz"] = E["tz"], best
    return E


def times(E, tz):
    """UTC at the middle of each hour of a weather file whose hours are in UTC+tz."""
    base = np.array([np.datetime64(f"2023-{m:02d}-{d:02d}") for m, d in zip(E["month"], E["day"])])
    return base + ((E["hour"] - 0.5 - tz) * 3600).astype("timedelta64[s]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epw")
    ap.add_argument("--buildings")
    ap.add_argument("--cell", type=float, default=10)
    ap.add_argument("--margin", type=float, default=50)
    a = ap.parse_args()
    S, out = Site(a.site, a.buildings), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tz = timezone(S.lat, S.lon)
    year = dt.date.today().year

    # positions on the key days, clock time
    rows = []
    for name, (m, d) in DAYS.items():
        for h in range(24):
            u = np.datetime64(local_to_utc(dt.date(year, m, d), h, tz, S.lon))
            alt, az = sunpos([u], S.lat, S.lon)
            if alt[0] > 0:
                rows.append({"day": name, "local_time": f"{h:02d}:00", "altitude_deg": round(float(alt[0]), 1), "azimuth_deg": round(float(az[0]), 1)})
    with open(out / "sun.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # shadows of the existing buildings
    G, H, n_def, n_miss = S.buildings(S.poly.buffer(400))
    fp = shapely.union_all(G)
    open_site = S.poly.difference(fp)
    feats, shaded = [], {}
    for name in SHADOW_DAYS:
        m, d = DAYS[name]
        for h in SHADOW_HOURS:
            alt, az = sunpos([np.datetime64(local_to_utc(dt.date(year, m, d), h, tz, S.lon))], S.lat, S.lon)
            alt, az = float(alt[0]), float(az[0])
            if alt <= 1:
                continue
            sh = shapely.union_all(shadow_hulls(G, H, alt, az)).difference(fp)
            shaded[f"{name} {h:02d}:00"] = round(100 * sh.intersection(S.poly).area / open_site.area, 1)
            feats.append((sh.simplify(0.5), {"day": name, "local_time": f"{h:02d}:00", "sun_altitude_deg": round(alt, 1), "sun_azimuth_deg": round(az, 1)}))
    S.write_geojson(out / "shadows.geojson", feats)

    # annual sun hours and radiation on a grid, from the weather file
    E = load_epw(S, a.epw, out)
    alt, az = sunpos(times(E, E["tz"]), S.lat, S.lon)
    up = alt > 2
    sunny = up & (E["dni"] >= 120)
    direct = np.where(alt > 0, E["dni"] * np.sin(np.radians(np.maximum(alt, 0))), 0)
    xs, ys = grid(S.poly.buffer(a.margin), a.cell)
    on_open = ~shapely.contains(fp, shapely.points(xs, ys))
    xs, ys = xs[on_open], ys[on_open]
    pts = shapely.points(xs, ys)
    hours, rad = np.zeros(len(xs)), np.zeros(len(xs))
    # group the hours into sky patches (5 deg altitude x 10 deg azimuth) and cast one shadow per patch
    ka, kz = (alt // 5).astype(int), (az // 10).astype(int)
    for key in set(zip(ka[up & (direct > 0)], kz[up & (direct > 0)])):
        sel = up & (direct > 0) & (ka == key[0]) & (kz == key[1])
        wgt = direct[sel]
        a_m = float(np.average(alt[sel], weights=wgt))
        z_m = float(np.degrees(np.arctan2(np.average(np.sin(np.radians(az[sel])), weights=wgt), np.average(np.cos(np.radians(az[sel])), weights=wgt))) % 360)
        lit = np.ones(len(xs), bool)
        if len(G):
            tree = shapely.STRtree(shadow_hulls(G, H, a_m, z_m))
            lit[np.unique(tree.query(pts, predicate="within")[0])] = False
        hours[lit] += sunny[sel].sum()
        rad[lit] += wgt.sum()
    rad = (rad + E["dhi"].sum()) / 1000
    hmax, rmax = int(sunny.sum()), (direct[alt > 0].sum() + E["dhi"].sum()) / 1000

    clip = S.poly.buffer(a.margin).difference(fp)
    he = [0, round(hmax * .25), round(hmax * .5), round(hmax * .75), round(hmax * .9), hmax + 1]
    S.write_geojson(out / "sun-hours.geojson", [(g, {"hours_min": lo, "hours_max": min(hi, hmax), "label": f"{lo}-{min(hi, hmax)} h"}) for lo, hi, g in bands(xs, ys, hours, a.cell, he, clip)])
    # classes from the site's own values: full sun is one class, the shaded rest is cut into quarters of its cells
    top = float(np.quantile(rad, 0.99))
    full = rad >= top * 0.995
    q = np.unique(np.round(np.quantile(rad[~full], [0, .25, .5, .75]))) if (~full).sum() > 20 else np.array([np.floor(rad.min())])
    re = [float(q[0]) - 1] + [float(v) for v in q[1:]] + [round(top * 0.995, 1), float(np.ceil(rad.max())) + 1]
    names = ["most shaded quarter", "second quarter", "third quarter", "least shaded quarter"][-(len(re) - 2):] + ["full sun, no shade"]
    S.write_geojson(out / "radiation.geojson", [(g, {"kwh_min": round(max(lo, rad.min())), "kwh_max": round(min(hi, rad.max())), "label":
                                                     f"{max(lo, rad.min()):.0f}-{min(hi, rad.max()):.0f} kWh/m2, {n}"})
                                                for (lo, hi, g), n in zip(bands(xs, ys, rad, a.cell, re, clip), names)])
    ll = S.to_ll(shapely.points(xs, ys))
    with open(out / "sun_grid.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lon", "lat", "sun_hours", "radiation_kwh_m2"])
        w.writerows([[round(p.x, 6), round(p.y, 6), int(h), round(r)] for p, h, r in zip(ll, hours, rad)])

    in_site = shapely.contains(S.poly, pts)
    summary = dict(
        time_zone=tz or "none found; local solar time used",
        grid_margin_m=a.margin, grid_cell_m=a.cell,
        weather=dict(source=E["source"], place=E["place"], lat=E["lat"], lon=E["lon"], utc_offset_header=E["tz_header"], utc_offset_used=E["tz"], ghi_kwh_m2=round(E["ghi"].sum() / 1000),
                     sun_hours_open=hmax, possible_daylight_hours=int((alt > 0).sum())),
        noon_altitude={k: max(r["altitude_deg"] for r in rows if r["day"] == k) for k in DAYS},
        shadows_share_of_open_site_pct=shaded,
        site_mean_sun_hours=round(float(hours[in_site].mean())), site_share_below_half_sun_pct=round(100 * float((hours[in_site] < hmax / 2).mean()), 1),
        site_mean_radiation_kwh_m2=round(float(rad[in_site].mean())), radiation_open_kwh_m2=round(rmax),
        buildings=dict(used=len(G), heights_defaulted=n_def, skipped_no_height=n_miss),
        sources=[E["source"], "Sun position: NOAA solar position formulas", "Sun hour: direct normal irradiance >= 120 W/m2 (WMO)",
                 f"Shade: existing buildings within 400 m ({n_def} of {len(G)} heights are defaults), flat ground; diffuse light not reduced by buildings"])
    write_json(out / "sun.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
