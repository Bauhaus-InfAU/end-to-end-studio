"""Fresh air: trace corridors and air flow from a climate map in the brief, or derive likely cold air flow from terrain.

  python fresh_air.py page BRIEF.pdf PAGE --out DIR
      the page as PNG and every picture on it at full size (needs: pip install pymupdf)
  python fresh_air.py crossing --site SITE_DIR "Street A" "Street B"
      where two streets (name or ref) cross, from OpenStreetMap: control points for the fit
  python fresh_air.py fit MAP.png points.json --site SITE_DIR --out DIR
      points.json: [{"px": [x, y], "lonlat": [lon, lat], "what": "Street A x Street B"}, ...], two or more.
      Writes transform.json (residuals in m) and fit-check.png: the site and its streets drawn over the map. Look at it.
  python fresh_air.py trace MAP.png --transform transform.json --classes classes.json --site SITE_DIR --out DIR
      classes.json: {"source": "brief p. N, Fig. M, author", "classes": [
          {"kind": "corridor", "label": "...", "hue_deg": 330},
          {"kind": "flow", "label": "...", "rgb_min": [r, g, b], "rgb_max": [r, g, b], "sense_deg": 180}]}
      A class is a hue (hue_deg, or at_px [x, y]: a pixel on it whose hue is read; hue_tol 30, only strong colour: sat_min 0.5, val_min 0.35, so pale tints of the same hue
      are left out) or an RGB box (rgb_min, rgb_max). Corridors: close_px 4 closes gaps, open_m 10 drops strands narrower
      than 20 m (roads), min_area_m2 10000. The output gives the site share at half and double close_px and warns when they
      differ by more than 5 points; trace-check.png shows what was taken. sense_deg is the way the arrows point, read by eye
      on the map: a blurred raster doesn't show the heads reliably.
  python fresh_air.py derive --site SITE_DIR --out DIR
      no map: downhill flow over open, unsealed land from terrain (Open-Meteo elevation, about 90 m), marked derived.
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import requests
import shapely
from shapely.geometry import LineString, box

from common import UA, Site, overpass, read, write_json

OPEN_LAND = {"farmland", "meadow", "grass", "grassland", "orchard", "forest", "wood", "scrub", "heath", "park",
             "recreation_ground", "allotments", "cemetery", "village_green", "vineyard", "wetland", "greenfield"}


def page(a):
    import pymupdf
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(a.pdf)
    pg = doc[a.page - 1]
    pg.get_pixmap(dpi=110).save(out / f"page-{a.page}.png")
    print("page", out / f"page-{a.page}.png")
    for k, im in enumerate(pg.get_images(full=True)):
        pix = pymupdf.Pixmap(doc, im[0])
        if pix.n - pix.alpha > 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        if min(pix.width, pix.height) >= 300:
            p = out / f"page-{a.page}-img{k + 1}.png"
            pix.save(p)
            print("picture", p, pix.width, "x", pix.height)


def crossing(a):
    S = Site(a.site)
    d = a.km / 111
    bb = f"({S.lat - d},{S.lon - d * 1.6},{S.lat + d},{S.lon + d * 1.6})"
    q = "[out:json][timeout:90];(" + "".join(f'way["highway"]["{k}"="{n}"]{bb};' for n in (a.a, a.b) for k in ("name", "ref")) + ");out geom;"
    lines = {a.a: [], a.b: []}
    for w in overpass(q)["elements"]:
        for n in lines:
            if n in (w["tags"].get("name"), w["tags"].get("ref")):
                lines[n].append(LineString([(p["lon"], p["lat"]) for p in w["geometry"]]))
    if not all(lines.values()):
        sys.exit(f"not found: {[n for n, v in lines.items() if not v]}")
    x = shapely.union_all(lines[a.a]).intersection(shapely.union_all(lines[a.b]))
    if x.is_empty:
        sys.exit("they don't cross; pick another pair")
    c = x.centroid
    print(f"centre {c.x:.6f} {c.y:.6f}  ({len(getattr(x, 'geoms', [x]))} crossing points, e.g. an interchange)")


def fit(a):
    from PIL import Image, ImageDraw
    S = Site(a.site)
    P = read(a.points)
    px = np.array([p["px"] for p in P], float)
    E = np.array([S.to_m(shapely.points(*p["lonlat"])).coords[0] for p in P])
    # similarity transform (scale, rotation, shift), image y pointing down
    z = px[:, 0] - 1j * px[:, 1]
    w = E[:, 0] + 1j * E[:, 1]
    (k, t), *_ = np.linalg.lstsq(np.c_[z, np.ones(len(z))], w, rcond=None)
    M = np.array([[k.real, k.imag], [k.imag, -k.real], [t.real, t.imag]])
    res = np.hypot(*((np.c_[px, np.ones(len(px))] @ M) - E).T)
    write_json(Path(a.out) / "transform.json", dict(matrix=M.tolist(), crs=S.crs.to_string(), m_per_px=round(abs(k), 2),
                                                   residual_m=res.round(1).tolist(), points=P))
    inv = np.linalg.inv(np.r_[M.T, [[0, 0, 1]]])
    to_px = lambda x, y: tuple((inv @ [x, y, 1])[:2])
    im = Image.open(a.map).convert("RGB")
    dr = ImageDraw.Draw(im)
    for g, _ in S.layer("streets"):
        for part in getattr(g, "geoms", [g]):
            dr.line([to_px(*c) for c in part.coords], fill=(0, 0, 0), width=1)
    dr.line([to_px(*c) for c in S.poly.exterior.coords], fill=(0, 200, 0), width=3)
    for p in px:
        dr.ellipse([p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5], outline=(255, 0, 0), width=2)
    im.save(Path(a.out) / "fit-check.png")
    print(f"{abs(k):.2f} m per pixel, residuals {res.round(0)} m, check {Path(a.out) / 'fit-check.png'}")


def mask_geom(m):
    boxes = []
    for y in range(m.shape[0]):
        row = np.r_[0, m[y].astype(np.int8), 0]
        d = np.diff(row)
        boxes += [box(s, y, e, y + 1) for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0])]
    return shapely.union_all(boxes)


def hue_of(rgb):
    r, g, b = np.asarray(rgb, float) / 255
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:
        return 0.0
    d = mx - mn
    return float((((g - b) / d) % 6 if mx == r else (b - r) / d + 2 if mx == g else (r - g) / d + 4) * 60)


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r and (dx or dy):
                out[max(0, dy):m.shape[0] + min(0, dy), max(0, dx):m.shape[1] + min(0, dx)] |= \
                    m[max(0, -dy):m.shape[0] - max(0, dy), max(0, -dx):m.shape[1] - max(0, dx)]
    return out


def erode(m, r):
    return ~dilate(~m, r)


def circ_mean(degs):
    """Average of directions in degrees (so 350 and 10 give 0), or None."""
    if not len(degs):
        return None
    d = np.radians(degs)
    return round(float(np.degrees(np.arctan2(np.sin(d).mean(), np.cos(d).mean())) % 360))


def flow_direction(feats, S):
    """The one air direction every file uses: the average of all flow arrows that touch the site."""
    d = [p["direction_deg"] for g, p in feats if p["kind"] == "flow" and g.intersects(S.poly)]
    return dict(flow_towards_deg=circ_mean(d), flow_basis=f"average direction of the {len(d)} flow arrows that touch the site")


def colour_mask(im, c):
    """Pixels of a class: by hue (hue_deg +- hue_tol, strong colour only), or by an RGB box (rgb_min, rgb_max)."""
    if "hue_deg" not in c:
        return np.all((im >= np.array(c["rgb_min"])) & (im <= np.array(c["rgb_max"])), axis=2)
    f = im / 255.0
    mx, mn = f.max(2), f.min(2)
    d = np.where(mx > mn, mx - mn, 1)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    hue = np.where(mx == r, (g - b) / d % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    off = np.abs((hue - c["hue_deg"] + 180) % 360 - 180)
    return (off <= c.get("hue_tol", 30)) & (sat >= c.get("sat_min", 0.5)) & (mx >= c.get("val_min", 0.35)) & (mx > mn)


def trace(a):
    from PIL import Image
    S = Site(a.site)
    T = read(a.transform)
    M = np.array(T["matrix"])
    C = read(a.classes)
    im = np.asarray(Image.open(a.map).convert("RGB")).astype(int)
    to_m = lambda g: shapely.transform(g, lambda xy: np.c_[xy, np.ones(len(xy))] @ M)
    reach = S.poly.buffer(a.reach)
    acc = f"traced from the map, about {max(T['residual_m'] + [2 * T['m_per_px']]):.0f} m"
    feats, info = [], []
    for c in C["classes"]:
        if "at_px" in c:  # the hue of the pixels around a point the reader picked on the corridor
            x, y = c["at_px"]
            patch = im[max(0, y - 3):y + 4, max(0, x - 3):x + 4].reshape(-1, 3)
            c = dict(c, hue_deg=hue_of(np.median(patch, 0)))
            rgb = np.median(patch, 0)
            print(f'{c["label"]}: hue {c["hue_deg"]:.0f} deg read at pixel {x}, {y} (colour {rgb.astype(int).tolist()})'
                  + ("; WARNING: a pale or grey pixel, pick one in the strong colour" if (rgb.max() - rgb.min()) / max(rgb.max(), 1) < 0.5 else ""))
        m = colour_mask(im, c)
        if c["kind"] == "corridor":
            op = max(1, round(c.get("open_m", 10) / T["m_per_px"]))

            def corridor(close_px):
                mm = erode(dilate(m, close_px), close_px)  # close gaps
                mm = dilate(erode(mm, op), op)             # drop strands narrower than 2 x open_m, such as roads
                h = to_m(mask_geom(mm).simplify(1.5)).intersection(reach)
                return [p for p in getattr(h, "geoms", [h]) if p.area >= c.get("min_area_m2", 10000)]
            close = c.get("close_px", 4)
            parts = corridor(close)
            spread = {k: round(100 * sum(p.intersection(S.poly).area for p in corridor(k)) / S.poly.area, 1) for k in (max(1, close // 2), close, close * 2)}
            for p in parts:
                feats.append((p.simplify(5), {"kind": "corridor", "label": c["label"], "area_ha": round(p.area / 1e4, 1),
                                              "in_site_ha": round(p.intersection(S.poly).area / 1e4, 1), "source": f'{C["source"]}; {acc}'}))
            info.append(dict(label=c["label"], parts=len(parts), in_site_ha=round(sum(p.intersection(S.poly).area for p in parts) / 1e4, 1),
                             site_share_pct_by_close_px=spread))
            if not parts:
                print(f"WARNING {c['label']}: no corridor found with this colour. Look at trace-check.png and pick a pixel on the corridor.")
            if max(spread.values()) - min(spread.values()) > 5:
                print(f"WARNING {c['label']}: the share of the site changes from {min(spread.values())} to {max(spread.values())} % with close_px; "
                      "the colour range likely catches more than the corridor. Look at trace-check.png.")
        else:
            g = mask_geom(m)
            n, dirs = 0, []
            sense = np.radians(c["sense_deg"])
            for blob in getattr(g, "geoms", [g]):
                if blob.area < c.get("min_px", 25):
                    continue
                q = shapely.get_coordinates(blob)
                ctr = q.mean(0)
                ax = np.linalg.svd(q - ctr, full_matrices=False)[2][0]
                t = (q - ctr) @ ax
                line = to_m(LineString([ctr + ax * t.min(), ctr + ax * t.max()]))
                (x0, y0), (x1, y1) = line.coords
                if np.sin(sense) * (x1 - x0) + np.cos(sense) * (y1 - y0) < 0:
                    line = LineString(line.coords[::-1])
                    (x0, y0), (x1, y1) = line.coords
                if not line.intersects(reach):
                    continue
                brg = float(np.degrees(np.arctan2(x1 - x0, y1 - y0)) % 360)
                dirs.append(brg)
                n += 1
                feats.append((line, {"kind": "flow", "label": c["label"], "direction_deg": round(brg),
                                     "source": f'{C["source"]}; axis {acc}, sense read by eye'}))
            in_site = [p["direction_deg"] for g_, p in feats[-n:] if g_.intersects(S.poly)] if n else []
            info.append(dict(label=c["label"], arrows=n, arrows_in_site=len(in_site), towards_deg_in_site=circ_mean(in_site)))
    S.write_geojson(Path(a.out) / "fresh-air.geojson", feats)
    # trace-check.png: the map with what was taken as corridor (green outline) and as flow (black), to compare by eye
    from PIL import ImageDraw
    pic = Image.open(a.map).convert("RGB")
    dr = ImageDraw.Draw(pic)
    inv = np.linalg.inv(np.r_[M.T, [[0, 0, 1]]])
    to_px = lambda x, y: tuple((inv @ [x, y, 1])[:2])
    for g_, p in feats:
        for part in getattr(g_, "geoms", [g_]):
            ring = part.exterior.coords if part.geom_type == "Polygon" else part.coords
            dr.line([to_px(*xy) for xy in ring], fill=(0, 170, 0) if p["kind"] == "corridor" else (0, 0, 0), width=3 if p["kind"] == "corridor" else 1)
    dr.line([to_px(*xy) for xy in S.poly.exterior.coords], fill=(0, 0, 255), width=2)
    pic.save(Path(a.out) / "trace-check.png")
    corr = shapely.union_all([g for g, p in feats if p["kind"] == "corridor"])
    summary = dict(method="traced", classes=info, site_share_in_corridor_pct=round(100 * corr.intersection(S.poly).area / S.poly.area, 1),
                   **flow_direction(feats, S),
                   fit_m_per_px=T["m_per_px"], fit_residual_m=T["residual_m"], sources=[C["source"], f"Georeferenced on OpenStreetMap streets, {acc}"])
    write_json(Path(a.out) / "fresh-air.json", summary)
    print(summary)


def derive(a):
    S = Site(a.site)
    reach = S.poly.buffer(a.reach)
    x0, y0, x1, y1 = reach.bounds
    xs, ys = np.meshgrid(np.arange(x0, x1 + a.step, a.step), np.arange(y0, y1 + a.step, a.step))
    ll = shapely.get_coordinates(S.to_ll(shapely.points(xs.ravel(), ys.ravel())))
    z = []
    for i in range(0, len(ll), 100):
        for wait in (2, 10, 30, 60, 0):  # the free API limits requests per minute
            r = requests.get("https://api.open-meteo.com/v1/elevation", headers=UA, timeout=60,
                             params=dict(latitude=",".join(f"{v:.5f}" for v in ll[i:i + 100, 1]), longitude=",".join(f"{v:.5f}" for v in ll[i:i + 100, 0])))
            if r.status_code != 429:
                break
            time.sleep(wait)
        r.raise_for_status()
        z += r.json()["elevation"]
    Z = np.array(z, float).reshape(xs.shape)
    gy, gx = np.gradient(Z, a.step)
    slope = np.hypot(gx, gy)
    open_land = shapely.union_all([g for g, p in S.layer("plots") if str(p.get("landuse")) in OPEN_LAND] or [shapely.Polygon()])
    feats = []
    for i, j in zip(*np.nonzero(slope > 0.01)):
        p = shapely.points(xs[i, j], ys[i, j])
        if not open_land.contains(p) or not reach.contains(p):
            continue
        u = -np.array([gx[i, j], gy[i, j]]) / slope[i, j]
        line = LineString([(xs[i, j], ys[i, j]), (xs[i, j] + u[0] * a.step * 0.6, ys[i, j] + u[1] * a.step * 0.6)])
        feats.append((line, {"kind": "flow", "label": "likely cold air flow, downhill over open land", "slope_pct": round(100 * float(slope[i, j]), 1),
                             "direction_deg": round(float(np.degrees(np.arctan2(u[0], u[1])) % 360)), "source": "derived"}))
    S.write_geojson(Path(a.out) / "fresh-air.geojson", feats)
    write_json(Path(a.out) / "fresh-air.json", dict(method="derived", flows=len(feats), **flow_direction(feats, S), sources=[
        "Derived: Open-Meteo elevation (Copernicus DEM GLO-90), downhill direction over open land from the site folder's plots; no climate study"]))
    print(len(feats), "flow arrows derived")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("page"); p.add_argument("pdf"); p.add_argument("page", type=int); p.add_argument("--out", required=True)
    p = sp.add_parser("crossing"); p.add_argument("--site", required=True); p.add_argument("a"); p.add_argument("b"); p.add_argument("--km", type=float, default=4)
    p = sp.add_parser("fit"); p.add_argument("map"); p.add_argument("points"); p.add_argument("--site", required=True); p.add_argument("--out", required=True)
    p = sp.add_parser("trace"); p.add_argument("map"); p.add_argument("--transform", required=True); p.add_argument("--classes", required=True)
    p.add_argument("--site", required=True); p.add_argument("--out", required=True); p.add_argument("--reach", type=float, default=1000)
    p = sp.add_parser("derive"); p.add_argument("--site", required=True); p.add_argument("--out", required=True)
    p.add_argument("--reach", type=float, default=1000); p.add_argument("--step", type=float, default=100)
    a = ap.parse_args()
    {"page": page, "crossing": crossing, "fit": fit, "trace": trace, "derive": derive}[a.cmd](a)


if __name__ == "__main__":
    main()
