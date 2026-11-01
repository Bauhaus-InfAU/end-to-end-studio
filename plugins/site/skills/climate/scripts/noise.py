"""Road noise on a grid, day and night, with buildings screening it (simplified RLS-90, partial-source method).

python noise.py --site SITE_DIR --out CLIMATE_DIR --sources sources.json [--buildings FILE] [--cell 15] [--margin 300]

sources.json: what makes the noise, each with where its number comes from. Nothing here is a default for a place.
{"receiver_height_m": 4,
 "sources": [{"name": "Main road", "match": {"name": "Main Road"}, "aadt": 15000, "aadt_source": "brief p. 24",
              "speed_kmh": 80, "speed_source": "assumed", "road_class": "federal"},
             {"name": "Railway", "match": {"railway": "rail"}, "layer": "rail", "lme_day": 60, "lme_night": 58,
              "lme_source": "noise study p. 3"}]}
match: properties a line in the site folder's streets layer (or `layer`) must have; a list allows several values.
road_class sets the RLS-90 shares of day/night traffic and heavy vehicles: motorway, federal, state, local.
lme_day / lme_night: an emission level at 25 m from a study, used instead of aadt (any source, rail included).

Railway (optional, off without train numbers): a source with "trains_per_day" (or "trains_day" 6-22 h and "trains_night"
22-6 h) and "trains_source", or --rail-trains N on the command line. Simplified Schall 03 (1990):
L = 51 + 10 lg(5 - 0.04 p) + 10 lg(0.01 l) + 20 lg(0.01 v) + D_track, with p % disc-braked, l metres of train per hour,
v km/h; train_length_m, disc_brake_pct, speed_kmh, track ("concrete" +2, "wood" 0) default to the values in RAIL and
are listed as assumptions. Without train numbers the maps say: Railway not included: no train data.
"""
import argparse
import csv
import math
from pathlib import Path

import numpy as np
import shapely

from common import Site, bands, grid, read, write_json

CLASSES = {"motorway": (0.14, 0.022, 25, 45), "federal": (0.06, 0.011, 20, 20), "state": (0.06, 0.008, 20, 10), "local": (0.06, 0.011, 10, 3)}
HS = 0.5  # source height, m


def emission(M, p, v):
    """RLS-90 emission level at 25 m for M vehicles/h with p % heavy vehicles at v km/h."""
    Lc = 27.7 + 10 * math.log10(1 + (0.02 * v) ** 3)
    Lt = 23.1 + 12.5 * math.log10(v)
    Dv = Lc - 37.3 + 10 * math.log10((100 + (10 ** (0.1 * (Lt - Lc)) - 1) * p) / (100 + 8.23 * p))
    return 37.3 + 10 * math.log10(M * (1 + 0.082 * p)) + Dv


RAIL = dict(speed_kmh=100, train_length_m=200, disc_brake_pct=100, track="concrete", night_share=0.15)


def rail_emission(src):
    """Simplified Schall 03 emission level at 25 m, day and night, and the assumptions made."""
    assumed = [f"{k} {RAIL[k]}" for k in ("speed_kmh", "train_length_m", "disc_brake_pct", "track") if k not in src]
    g = lambda k: src.get(k, RAIL[k])
    if "trains_day" in src:
        nd, nn = float(src["trains_day"]), float(src.get("trains_night", 0))
    else:
        nn = float(src["trains_per_day"]) * RAIL["night_share"]
        nd = float(src["trains_per_day"]) - nn
        assumed.append(f"{round(100 * RAIL['night_share'])} % of trains at night")
    base = 51 + 10 * math.log10(5 - 0.04 * float(g("disc_brake_pct"))) + 20 * math.log10(0.01 * float(g("speed_kmh"))) + (2 if g("track") == "concrete" else 0)
    lme = lambda n, hours: base + 10 * math.log10(max(0.01 * n / hours * float(g("train_length_m")), 1e-6))
    return {"day": lme(nd, 16), "night": lme(nn, 8)}, assumed


def matches(props, match):
    return all((props.get(k) in v) if isinstance(v, list) else props.get(k) == v for k, v in match.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--buildings")
    ap.add_argument("--cell", type=float, default=15)
    ap.add_argument("--margin", type=float, default=300)
    ap.add_argument("--seg", type=float, default=25)
    ap.add_argument("--raster", type=float, default=5)
    ap.add_argument("--rail-trains", type=float, help="trains per 24 h on the railway lines; off when not given")
    ap.add_argument("--rail-source", default="given on the command line", help="where the train number comes from, or ASSUMED")
    ap.add_argument("--rail-speed", type=float)
    ap.add_argument("--rail-match", default="railway=rail", help="key=value a line in the site folder's rail layer must have")
    a = ap.parse_args()
    S, out = Site(a.site, a.buildings), Path(a.out)
    cfg = read(a.sources)
    if a.rail_trains:
        k, v = a.rail_match.split("=", 1)
        cfg["sources"].append(dict(name="Railway", layer="rail", match={k: v}, trains_per_day=a.rail_trains, trains_source=a.rail_source,
                                   **({"speed_kmh": a.rail_speed, "speed_source": a.rail_source} if a.rail_speed else {})))
    hr = float(cfg.get("receiver_height_m", 4))
    zone = S.poly.buffer(a.margin)
    G, H, n_def, _ = S.buildings(zone.buffer(500))
    fp = shapely.union_all(G)
    # building heights on a raster, sampled along each sound path
    rx0, ry0, rx1, ry1 = zone.buffer(500).bounds
    R = a.raster
    nx, ny = int((rx1 - rx0) / R) + 1, int((ry1 - ry0) / R) + 1
    gx, gy = np.meshgrid(rx0 + (np.arange(nx) + .5) * R, ry0 + (np.arange(ny) + .5) * R)
    hgrid = np.zeros(gx.size, np.float32)
    if len(G):
        pi, bi = shapely.STRtree(G).query(shapely.points(gx.ravel(), gy.ravel()), predicate="within")
        np.maximum.at(hgrid, pi, H[bi].astype(np.float32))
    hgrid = hgrid.reshape(gx.shape)
    xs, ys = grid(zone, a.cell)
    keep = ~shapely.contains(fp, shapely.points(xs, ys))
    xs, ys = xs[keep], ys[keep]
    rcv = np.c_[xs, ys]
    E = {"day": np.zeros(len(xs)), "night": np.zeros(len(xs))}
    used, notes, lines_out = [], [], []
    rail = dict(included=False, label="Railway not included: no train data")
    for src in cfg["sources"]:
        lines = [g for g, p in S.layer(src.get("layer", "streets")) if matches(p, src["match"])]
        if not lines:
            notes.append(f'{src["name"]}: no line in the site data matches {src["match"]}, left out')
            continue
        geom = shapely.union_all(lines)
        lines_out.append((geom, {"name": src["name"], "kind": "rail" if src.get("layer") == "rail" else "road"}))
        assumed = []
        if "lme_day" in src:
            lme = {"day": src["lme_day"], "night": src.get("lme_night", src["lme_day"] - 8)}
        elif "trains_per_day" in src or "trains_day" in src:
            lme, assumed = rail_emission(src)
            n = src.get("trains_per_day", src.get("trains_day", 0) + src.get("trains_night", 0))
            rail = dict(included=True, label=f'{src["name"]}: {n:g} trains/day ({src.get("trains_source", "no source given")})',
                        assumptions=assumed)
        else:
            md, mn, pd, pn = CLASSES[src.get("road_class", "local")]
            v = float(src.get("speed_kmh", 50))
            lme = {"day": emission(md * src["aadt"], pd, v), "night": emission(mn * src["aadt"], pn, v)}
        used.append(dict(name=src["name"], lme_day=round(lme["day"], 1), lme_night=round(lme["night"], 1),
                         **{k: src[k] for k in src if k.endswith("source") or k in ("aadt", "speed_kmh", "road_class", "trains_per_day", "trains_day", "trains_night")},
                         **({"assumed": "; ".join(assumed)} if assumed else {})))
        # partial sources along the line
        segs, fine = [], shapely.segmentize(geom, a.seg)
        for part in getattr(fine, "geoms", [fine]):
            q = np.asarray(part.coords)[:, :2]
            segs += [((q[i] + q[i + 1]) / 2, float(np.hypot(*(q[i + 1] - q[i])))) for i in range(len(q) - 1)]
        for mid, l in segs:
            if l < 0.5:
                continue
            s = np.maximum(np.hypot(*(rcv - mid).T), 2.0)
            near = s < 1500  # beyond, a road's share is below the classes drawn
            idx = np.nonzero(near)[0]
            si = s[idx]
            # sample each path every raster cell; the highest path difference over a roof gives the screening
            K = int(np.ceil(si.max() / R))
            t = ((np.arange(K) + 0.5) / K).astype(np.float32)
            px = mid[0] + (rcv[idx, 0, None] - mid[0]) * t
            py = mid[1] + (rcv[idx, 1, None] - mid[1]) * t
            ix = np.clip(((px - rx0) / R).astype(int), 0, nx - 1)
            iy = np.clip(((py - ry0) / R).astype(int), 0, ny - 1)
            h = hgrid[iy, ix]
            A = si[:, None] * t
            B = si[:, None] - A
            z = np.where(h > 0, np.sqrt(A ** 2 + (h - HS) ** 2) + np.sqrt(B ** 2 + (h - hr) ** 2) - np.sqrt(si ** 2 + (hr - HS) ** 2)[:, None], 0)
            k = z.argmax(1)
            r_ = np.arange(len(idx))
            z, A, B = z[r_, k], A[r_, k], B[r_, k]
            Kw = np.exp(-np.sqrt(A * B * si / (2 * np.maximum(z, 1e-6))) / 2000)
            Dz = np.where(z > 0, np.minimum(7 * np.log10(np.maximum(5 + (70 + 0.25 * si) / (1 + 0.2 * z) * z * Kw, 1)), 20), 0)
            Ds = 11.2 - 20 * np.log10(si) - si / 200
            hm = (HS + hr) / 2
            Dbm = np.where(Dz > 0, 0, np.minimum(0, (hm / si) * (34 + 600 / si) - 4.8))
            for per in E:
                E[per][idx] += 10 ** ((lme[per] + 10 * math.log10(l) + Ds + Dbm - Dz) / 10)
    L = {k: 10 * np.log10(np.maximum(v, 1e-3)) for k, v in E.items()}

    feats, share = [], {}
    clip = zone.difference(fp)
    pts = shapely.points(xs, ys)
    in_site = shapely.contains(S.poly, pts)
    for per, edges in (("day", [45, 50, 55, 60, 65, 70, 75, 200]), ("night", [35, 40, 45, 50, 55, 60, 65, 200])):
        for lo, hi, g in bands(xs, ys, L[per], a.cell, edges, clip):
            feats.append((g, {"period": per, "db_min": lo, "db_max": hi, "label": f"{lo}-{hi} dB(A)" if hi < 200 else f"{lo} dB(A) and more"}))
        share[per] = {f">={t}": round(100 * float((L[per][in_site] >= t).mean()), 1) for t in edges[:-1]}
    S.write_geojson(out / "noise.geojson", feats)
    S.write_geojson(out / "noise-sources.geojson", lines_out)
    ll = S.to_ll(pts)
    with open(out / "noise_grid.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lon", "lat", "l_day_db", "l_night_db"])
        w.writerows([[round(p.x, 6), round(p.y, 6), round(d, 1), round(n, 1)] for p, d, n in zip(ll, L["day"], L["night"])])
    rail_line = ("Railway: simplified Schall 03 (1990), propagated as the roads" + (f'; assumed {", ".join(rail["assumptions"])}' if rail["assumptions"] else "")
                 if rail["included"] else rail["label"])
    summary = dict(sources_used=used, notes=notes, rail=rail, receiver_height_m=hr, share_of_site_pct=share,
                   buildings=dict(used=len(G), heights_defaulted=n_def),
                   sources=[f'{u["name"]}: ' + ", ".join(f"{k} {v}" for k, v in u.items() if k.endswith("source")) for u in used] + [rail_line] +
                   [f"Method: RLS-90 partial sources, screening by the existing buildings (single diffraction over the highest roof on each path, heights on a {a.raster:g} m raster), "
                    "flat ground, no reflections; an estimate, not a noise study",
                    f"Buildings: site data, {n_def} of {len(G)} heights are defaults"])
    write_json(out / "noise.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
