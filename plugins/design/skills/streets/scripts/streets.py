"""One clean street surface for every drawing: the existing streets and the design's new ones.

  python streets.py --layers SITE_DIR --out OUT_DIR [--massing massing.geojson] [--config config.json]
                    [--style style.json] [--scale 5000]

SITE_DIR holds site.geojson and the layers. With street-land.geojson (street, square and path areas from a
cadastre) the existing streets are those areas as they are; without it they are built from the street lines
of streets.geojson. With a massing, its new streets join them, and existing streets under its new buildings go.
Every number is a default in DEFAULTS that config.json overrides; assumptions.md lists the ones used.
Needs shapely, pyproj and numpy; the PNG needs Chrome or Edge (or Chromium) for a headless screenshot.
"""
import argparse, json, math, os, shutil, subprocess, sys
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, MultiPolygon, box, mapping, shape
import shapely.ops
from shapely.ops import nearest_points, unary_union

DEFAULTS = {
    "lane_m": (3.25, "width of one traffic lane, m"),
    "footway_m": (2.5, "width of the footway on each side of a street with a lanes tag, m"),
    "shoulder_m": (1.0, "width of the shoulder on each side of a motorway or trunk road with a lanes tag, m"),
    "width_m": ({"motorway": 12, "trunk": 10, "primary": 15, "secondary": 14, "tertiary": 12, "unclassified": 7,
                 "residential": 10, "living_street": 7, "pedestrian": 8, "service": 5, "link": 7, "road": 8},
                "whole width of a street of each type without a width or lanes tag, kerb to kerb with footways, m"),
    "service_dead_end_m": (40, "a service way that ends nowhere and is shorter than this is a driveway, left out, m"),
    "sidewalk_share": (0.8, "a footway lying this share of its length beside a street is its pavement, left out"),
    "kerb_radius_m": (6, "the corners where streets meet are rounded to this radius, m"),
    "hole_min_m2": (400, "gaps between streets smaller than this are filled, m2"),
    "sliver_m": (1.0, "pieces of street narrower than twice this are dropped, m"),
    "join_m": (60, "a new street that ends this close to another street is led into it, straight ahead if it can, m"),
    "follow_m": (12, "a new street within this of an existing street, and running its way, is that street, m"),
    "follow_deg": (25, "how far a new street may turn from an existing one and still run its way, degrees"),
    "stub_m": (50, "a street that ends nowhere more than this from its last crossing gets a turning head, m"),
    "turning_head_m": (18, "diameter of a turning head, m"),
    "path_link_m": (100, "a street that ends nowhere is joined by a path to the nearest path or street this close, m"),
    "clearance_m": (2, "existing street land this close to a new building gives way to it, m"),
    "new_sliver_m": (2.5, "strips of new street narrower than twice this, beside an existing street, are dropped, m"),
    "fragment_m2":(300, "a piece of existing street left inside the site smaller than this goes, m2"),
    "street_width_m": (16, "width of a new street without a width in the massing, m"),
    "margin_m": (300, "the check plan shows this much around the site when the site folder gives no frame, m"),
}
MAIN = {"motorway", "trunk", "primary", "secondary"}
LOCAL = {"tertiary", "unclassified", "residential", "living_street", "pedestrian", "road"}
PATHS = {"footway", "path", "cycleway", "steps", "bridleway", "track", "corridor"}
FALLBACK_STYLE = {"paper": "#ffffff", "ink": "#000000", "existing": "#d9d9d9", "new": "#e8442e", "path": "#9a9a9a",
                  "building": "#bdbdbd", "font": "Arial, Helvetica, sans-serif", "line_mm": 0.18}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["features"]


def utm_for(lon, lat):
    epsg = (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1
    return Transformer.from_crs(4326, epsg, always_xy=True), Transformer.from_crs(epsg, 4326, always_xy=True)


def transform(tr, g):
    return shapely.transform(g, lambda c: np.column_stack(tr.transform(c[:, 0], c[:, 1])))


def polys(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return list(g.geoms)
    return [p for p in getattr(g, "geoms", []) if isinstance(p, (Polygon, MultiPolygon)) for p in polys(p)]


def fill_holes(g, min_area):
    out = []
    for p in polys(g):
        out.append(Polygon(p.exterior, [r for r in p.interiors if Polygon(r).area >= min_area]))
    return unary_union(out) if out else Polygon()


def clean(g, cfg):
    s = cfg["sliver_m"]
    g = open_square(g, s) if s else g  # drops slivers and hairlines
    return fill_holes(g.buffer(0), cfg["hole_min_m2"])


def open_square(g, r):
    """Drops what is narrower than 2 r and keeps square corners square."""
    return g.buffer(-r, join_style="mitre").buffer(r, join_style="mitre")


def reach(pt, before, target, limit, barrier):
    """The point where a street ending at pt meets target: straight ahead first, else the nearest, within limit,
    crossing no barrier. None if there is none."""
    tries = []
    if before is not None and pt.distance(before) > 0:
        dx, dy = pt.x - before.x, pt.y - before.y
        n = math.hypot(dx, dy)
        ray = LineString([pt, (pt.x + dx / n * limit, pt.y + dy / n * limit)])
        hit = ray.intersection(target)
        if not hit.is_empty:
            tries.append(nearest_points(pt, hit)[1])
    near = nearest_points(pt, target)[1]
    if pt.distance(near) <= limit:
        if before is None or pt.distance(near) < 0.5:
            tries.append(near)
        else:  # a street goes on ahead, never sideways into its neighbour
            a = math.degrees(math.atan2(near.y - pt.y, near.x - pt.x) - math.atan2(pt.y - before.y, pt.x - before.x))
            if abs((a + 180) % 360 - 180) <= 45:
                tries.append(near)
    for q in tries:
        seg = LineString([pt, q])
        if q.distance(pt) > 0.5 and not seg.crosses(barrier) and not seg.within(barrier):
            return (q.x, q.y)
    return None


def beside(line, band, old_lines, cfg, step=10.0):
    """The parts of a new street that don't run along an existing one, longer than one step."""
    if not old_lines or line.length < step:
        return [line]
    tree = shapely.STRtree(old_lines)
    n = max(1, round(line.length / step))
    keep = []
    for k in range(n):
        seg = shapely.ops.substring(line, k * line.length / n, (k + 1) * line.length / n)
        along = False
        if seg.within(band):
            mid = seg.interpolate(0.5, normalized=True)
            old = old_lines[tree.nearest(mid)]
            t = old.project(mid)
            a, b = old.interpolate(max(t - 5, 0)), old.interpolate(min(t + 5, old.length))
            (x0, y0), (x1, y1) = seg.coords[0], seg.coords[-1]
            ang = math.degrees(math.atan2(y1 - y0, x1 - x0) - math.atan2(b.y - a.y, b.x - a.x)) % 180
            along = min(ang, 180 - ang) <= cfg["follow_deg"]
        keep.append(not along)
    out, run = [], []
    for k, ok in enumerate(keep + [False]):
        if ok:
            run.append(k)
        elif run:
            part = shapely.ops.substring(line, run[0] * line.length / n, (run[-1] + 1) * line.length / n)
            if part.length >= step * 1.5 or len(run) == n:
                out.append(part)
            run = []
    return out


def round_corners(g, r):
    return g.buffer(r, join_style="round").buffer(-r, join_style="round") if r else g


def osm_width(p, cfg):
    hw = p.get("highway") or "road"
    kind = "link" if hw.endswith("_link") else hw
    w = p.get("width")
    try:
        if w is not None and float(str(w).split()[0]) > 0:
            return float(str(w).split()[0]), "osm width tag"
    except ValueError:
        pass
    try:
        lanes = int(str(p.get("lanes")).split(";")[0])
        side = cfg["shoulder_m"] if kind in ("motorway", "trunk", "link") else cfg["footway_m"]
        return lanes * cfg["lane_m"] + 2 * side, "osm lanes tag"
    except (TypeError, ValueError):
        pass
    return float(cfg["width_m"].get(kind, cfg["width_m"]["road"])), f"default for {kind}"


def level_of(hw):
    hw = (hw or "road").replace("_link", "")
    return "main" if hw in MAIN else "service" if hw == "service" else "local"


def dead_end_service(line, others):
    a, b = Point(line.coords[0]), Point(line.coords[-1])
    return not any(o.distance(a) < 1 for o in others) or not any(o.distance(b) < 1 for o in others)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layers", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--massing")
    ap.add_argument("--config")
    ap.add_argument("--style")
    ap.add_argument("--scale", type=int, default=5000)
    a = ap.parse_args()

    layers, out = Path(a.layers), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    given = json.loads(Path(a.config).read_text(encoding="utf-8")) if a.config else {}
    cfg = {k: given.get(k, v[0]) for k, v in DEFAULTS.items()}
    used = set()
    style = dict(FALLBACK_STYLE, **(json.loads(Path(a.style).read_text(encoding="utf-8")) if a.style else {}))

    site_ll = shape(load(layers / "site.geojson")[0]["geometry"])
    c = site_ll.centroid
    to_m, to_ll = utm_for(c.x, c.y)
    site = transform(to_m, site_ll)
    kit = layers / "kit.json"
    if kit.exists() and "bbox" in json.loads(kit.read_text(encoding="utf-8")):
        frame = transform(to_m, box(*json.loads(kit.read_text(encoding="utf-8"))["bbox"]))
    else:
        frame = site.buffer(cfg["margin_m"]).envelope
        used.add("margin_m")

    feats = []  # (geometry in metres, properties)
    centre, paths_l, paths_a = [], [], []

    # 1. The existing streets.
    land = layers / "street-land.geojson"
    lines = []
    if (layers / "streets.geojson").exists():
        for f in load(layers / "streets.geojson"):
            g = transform(to_m, shape(f["geometry"])).intersection(frame)
            if not g.is_empty:
                lines.append((g, f["properties"]))
    if land.exists():
        source = "street-land"
        land_f = [(transform(to_m, shape(f["geometry"])), f["properties"]) for f in load(land)]
        surf = unary_union([g for g, p in land_f if p.get("use") in ("street", "square")]).intersection(frame)
        surf = fill_holes(surf.buffer(0.05).buffer(-0.05), 1)  # joins plots that only touch
        paths_a = [(g.intersection(frame), p) for g, p in land_f if p.get("use") == "path"]
        squares = unary_union([g for g, p in land_f if p.get("use") == "square"])
        for g, p in lines:
            if p.get("highway") in PATHS and g.difference(surf.buffer(2)).length > 1:
                paths_l.append((g.difference(surf.buffer(2)), {"existing": True, "type": p.get("highway")}))
            elif p.get("highway") not in PATHS and g.intersection(surf).length > 0.5 * g.length:
                w, ws = osm_width(p, cfg)
                centre.append((g, {"level": level_of(p.get("highway")), "width": round(w, 1), "width_source": ws,
                                   "name": p.get("name") or p.get("ref"), "existing": True, "source": "osm"}))
    else:
        source = "osm"
        roads = [(g, p) for g, p in lines if p.get("highway") and p.get("highway") not in PATHS]
        others = [g for g, _ in roads]
        bufs = []
        for g, p in roads:
            if p.get("highway") == "service" and g.length < cfg["service_dead_end_m"] and dead_end_service(g, [o for o in others if o is not g]):
                used.add("service_dead_end_m")
                continue
            w, ws = osm_width(p, cfg)
            used.update(["width_m"] if ws.startswith("default") else ["lane_m", "footway_m", "shoulder_m"] if "lanes" in ws else [])
            bufs.append(g.buffer(w / 2, cap_style="flat", join_style="round"))
            centre.append((g, {"level": level_of(p.get("highway")), "width": round(w, 1), "width_source": ws,
                               "name": p.get("name") or p.get("ref"), "existing": True, "source": "osm"}))
        # The ends of every way, round, so that ways meeting at an angle leave no notch.
        ends = [Point(pt).buffer(cp["width"] / 2) for g, cp in centre for ln in getattr(g, "geoms", [g]) for pt in (ln.coords[0], ln.coords[-1])]
        surf = unary_union(bufs + ends)
        surf = clean(round_corners(surf, cfg["kerb_radius_m"]), cfg).intersection(frame)
        used.update(["kerb_radius_m", "hole_min_m2", "sliver_m"])
        squares = Polygon()
        for g, p in lines:
            if p.get("highway") in PATHS:
                along = g.intersection(surf.buffer(3)).length
                if g.length and along / g.length >= cfg["sidewalk_share"]:
                    used.add("sidewalk_share")
                    continue
                rest = g.difference(surf)
                if rest.length > 1:
                    paths_l.append((rest, {"existing": True, "type": p.get("highway")}))

    # 2. The design: new streets join the existing ones, existing land under new buildings gives way.
    new_surf, removed, crossed = Polygon(), 0.0, 0
    if a.massing:
        m = [(transform(to_m, shape(f["geometry"])), f["properties"]) for f in load(a.massing)]
        new_b = unary_union([g for g, p in m if p.get("kind") == "building" and not p.get("existing")])
        streets_n = [(g, p) for g, p in m if p.get("kind") == "street" and p.get("level") != "path"]
        paths_n = [(g, p) for g, p in m if p.get("kind") == "street" and p.get("level") == "path"]
        if not new_b.is_empty:
            used.update(["clearance_m", "fragment_m2"])
            block = new_b.buffer(cfg["clearance_m"])
            inside = surf.intersection(site)
            kept_in = [q for q in polys(inside.difference(block)) if q.area >= cfg["fragment_m2"] or not q.within(site.buffer(-1))]
            before = surf.area
            surf = clean(unary_union([surf.difference(site)] + kept_in), cfg)
            removed = before - surf.area
            paths_a = [(g.difference(block), p) for g, p in paths_a]
            paths_a = [(g.difference(site) if g.intersection(site).intersects(new_b) else g, p) for g, p in paths_a]
            paths_l = [(g, p) for g, p in paths_l if not g.intersection(site).intersects(new_b)]
            centre = [(g, p) for g, p in centre if g.intersection(surf).length > 0.5 * g.length]
        lines_n, on_old = [], 0.0
        old_lines = [g for g, q in centre if q["existing"]]
        for g, p in streets_n:
            w = float(p.get("width") or cfg["street_width_m"])
            if not p.get("width"):
                used.add("street_width_m")
            # Where a new street runs along an existing one, the existing one carries it: that piece goes.
            pieces = beside(g, surf.buffer(cfg["follow_m"]), old_lines, cfg)
            used.update(["follow_m", "follow_deg"])
            on_old += g.length - sum(h.length for h in pieces)
            lines_n += [(h, p, w) for h in pieces]
        # Barriers a link may not cross: buildings, rail and water.
        barrier = [g for g, p in m if p.get("kind") == "building"]
        for name in ("rail.geojson", "water.geojson"):
            if (layers / name).exists():
                barrier += [transform(to_m, shape(f["geometry"])).buffer(3) for f in load(layers / name)]
        barrier = unary_union(barrier).intersection(frame)
        other_paths = unary_union([g for g, _ in paths_l] + [g for g, _ in paths_a])
        joined, ends = [], []
        for i, (g, p, w) in enumerate(lines_n):
            coords = list(g.coords)
            rest = unary_union([surf] + [h.buffer(v / 2) for j, (h, _, v) in enumerate(lines_n) if j != i])
            for end in (0, -1):
                pt = Point(coords[end])
                if rest.distance(pt) < 0.5:
                    continue
                link = reach(pt, Point(coords[1 if end == 0 else -2]), rest, cfg["join_m"], barrier)
                used.add("join_m")
                if link is not None:
                    if end == 0:
                        coords.insert(0, link)
                    else:
                        coords.append(link)
                else:
                    ends.append((i, end))
            lines_n[i] = (LineString(coords), p, w)
        for i, (g, p, w) in enumerate(lines_n):
            joined.append(g.buffer(w / 2, cap_style="flat", join_style="round"))
            centre.append((g, {"level": "main" if p.get("level") == "main" else "local", "width": w,
                               "width_source": "massing" if p.get("width") else "default", "name": p.get("name"),
                               "existing": False, "source": "massing"}))
        # Every street that still ends in nothing gets an end: a square end at the site edge, kept for a later link;
        # inside, a turning head on a long stub, else a square end; and from each, a path to the nearest path or street.
        heads = []
        for i, end in ends:
            g, p, w = lines_n[i]
            pt = Point(g.coords[end])
            others = unary_union([surf] + [h.buffer(v / 2) for j, (h, _, v) in enumerate(lines_n) if j != i])
            if site.exterior.distance(pt) < w or not site.contains(pt):
                kind = "future link"
            else:
                meets = g.intersection(others.buffer(1))
                at = g.project(pt)
                stub = min((abs(g.project(Point(c)) - at) for part in getattr(meets, "geoms", [meets]) if not part.is_empty
                            for c in part.coords), default=g.length) if not meets.is_empty else g.length
                kind = "turning head" if stub > cfg["stub_m"] else "square end"
                used.add("stub_m")
                if kind == "turning head":
                    used.add("turning_head_m")
                    heads.append(pt.buffer(cfg["turning_head_m"] / 2))
            feats.append((pt, {"kind": "street-end", "type": kind, "level": p.get("level"), "name": p.get("name")}))
            target = unary_union([other_paths, others])
            link = reach(pt, None, target, cfg["path_link_m"], barrier)
            used.add("path_link_m")
            if link is not None:
                paths_l.append((LineString([pt, link]), {"existing": False, "type": "link"}))
        if joined:
            new = unary_union(joined + heads)
            both = unary_union([surf, new])
            r = cfg["kerb_radius_m"]
            used.add("kerb_radius_m")
            rounded = round_corners(both, r).intersection(new.buffer(2 * r))
            new_surf = clean(unary_union([new, rounded]), cfg).difference(surf)
            t = cfg["new_sliver_m"]  # where a new street runs along an existing one, only the existing one is drawn
            used.add("new_sliver_m")
            new_surf = open_square(new_surf, t).intersection(new_surf) if t else new_surf
            new_surf = unary_union([q for q in polys(new_surf) if q.area > 1])
        kept = [g for g, p in m if p.get("kind") == "building" and p.get("existing")]
        crossed = sum(1 for g in kept if g.intersection(new_surf).area > 5)
        for g, p in paths_n:
            paths_l.append((g, {"existing": False, "type": "path", "width": p.get("width")}))

    # 3. Write.
    for q in polys(surf):
        sq = q.intersection(squares).area > 0.5 * q.area if not squares.is_empty else False
        feats.append((q, {"kind": "street", "use": "square" if sq else "street", "existing": True, "source": source}))
    for q in polys(new_surf):
        feats.append((q, {"kind": "street", "use": "street", "existing": False, "source": "massing"}))
    for g, p in paths_a:
        for q in polys(g):
            if q.area > 1:
                feats.append((q, {"kind": "path", "existing": True, "source": "street-land", "name": p.get("name")}))
    for g, p in paths_l:
        if not g.is_empty:
            feats.append((g, {"kind": "path", **p, "source": "massing" if not p.get("existing") else "osm"}))
    for g, p in centre:
        feats.append((g, {"kind": "centreline", **p}))

    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": p, "geometry": mapping(shapely.set_precision(transform(to_ll, g), 1e-7))}
        for g, p in feats if not g.is_empty]}
    (out / "streets.geojson").write_text(json.dumps(fc), encoding="utf-8")

    in_site = lambda g: g.intersection(site).area
    stats = {"source_of_existing": source,
             "existing_street_ha": round(surf.area / 1e4, 2),
             "new_street_ha": round(new_surf.area / 1e4, 2),
             "existing_removed_ha": round(removed / 1e4, 2),
             "street_share_of_site": round((in_site(surf) + in_site(new_surf)) / site.area, 3),
             "kept_buildings_under_new_streets": crossed,
             "new_street_on_existing_m": round(on_old) if a.massing else 0,
             "street_ends": {k: sum(1 for g, p in feats if p.get("kind") == "street-end" and p["type"] == k)
                             for k in ("future link", "turning head", "square end")},
             "main_routes_ending_nowhere": sum(1 for g, p in feats if p.get("kind") == "street-end" and p.get("level") == "main"),
             "widths_by_default": sum(1 for _, p in centre if str(p.get("width_source", "")).startswith("default"))}
    (out / "stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")

    lines_md = ["# Assumptions", "", f"Existing streets from `{source}`" + (
        " (the cadastre's street and square areas as they are)." if source == "street-land" else
        " (street lines thickened by their width and joined)."), ""]
    for k in sorted(used):
        v = cfg[k]
        lines_md.append(f"- `{k}` = {json.dumps(v)}: {DEFAULTS[k][1]}" + (" (from config.json)" if k in given else " (default)"))
    (out / "assumptions.md").write_text("\n".join(lines_md) + "\n", encoding="utf-8")

    draw(out, frame, site, layers, a.massing, to_m, surf, new_surf, paths_a, paths_l, style, a.scale)
    print(json.dumps(stats))


def draw(out, frame, site, layers, massing, to_m, surf, new_surf, paths_a, paths_l, s, scale):
    x0, y0, x1, y1 = frame.bounds
    W, H = x1 - x0, y1 - y0
    wmm, hmm = W / scale * 1000, H / scale * 1000
    k = 1000 / scale  # mm on paper per metre on the ground
    lw = s["line_mm"] / k  # line weight in metres, drawn at the plan's scale

    def d(g):
        parts = []
        for geom in getattr(g, "geoms", [g]):
            rings = [geom.exterior, *geom.interiors] if isinstance(geom, Polygon) else [geom]
            for r in rings:
                c = np.asarray(r.coords)
                if len(c) < 2:
                    continue
                parts.append("M" + "L".join(f"{x - x0:.1f},{y1 - y:.1f}" for x, y in c) + ("Z" if isinstance(geom, Polygon) else ""))
        return "".join(parts)

    def el(g, fill, stroke="none", w=0.0, extra=""):
        return "" if g.is_empty else f'<path d="{d(g)}" fill="{fill}" stroke="{stroke}" stroke-width="{w:.2f}" fill-rule="evenodd" {extra}/>'

    els = []
    if (layers / "buildings.geojson").exists():
        bl = unary_union([transform(to_m, shape(f["geometry"])) for f in load(layers / "buildings.geojson")]).intersection(frame)
        if massing:
            bl = bl.difference(site)
        els.append(el(bl, s["building"]))
    els.append(el(surf, s["existing"], s["ink"], lw))
    els.append(el(unary_union([g for g, _ in paths_a]) if paths_a else Polygon(), s["paper"], s["path"], lw))
    for g, p in paths_l:
        els.append(el(g.intersection(frame), "none", s["path"], lw * 1.5, f'stroke-dasharray="{4 / k:.1f},{2 / k:.1f}"'))
    els.append(el(new_surf, s["new"], s["ink"], lw))
    if massing:
        m = load(massing)
        for old, fill in ((True, s["building"]), (False, s["ink"])):
            nb = unary_union([transform(to_m, shape(f["geometry"])) for f in m
                              if f["properties"].get("kind") == "building" and bool(f["properties"].get("existing")) == old])
            els.append(el(nb, fill))
    els.append(el(site.exterior, "none", s["ink"], lw * 3, f'stroke-dasharray="{6 / k:.1f},{3 / k:.1f}"'))
    fs = 2.5 / k
    els.append(f'<text x="{8 / k:.1f}" y="{H - 8 / k:.1f}" font-family="{s["font"]}" font-size="{fs:.1f}" fill="{s["ink"]}">'
               f'Streets 1:{scale}. Grey existing, accent new, dashed paths.</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{wmm:.1f}mm" height="{hmm:.1f}mm" viewBox="0 0 {W:.1f} {H:.1f}">'
           f'<rect width="100%" height="100%" fill="{s["paper"]}"/>' + "".join(els) + "</svg>")
    svg_p = out / f"streets_1-{scale}.svg"
    svg_p.write_text(svg, encoding="utf-8")
    browser = find_browser()
    if not browser:
        print("No Chrome, Edge or Chromium found: SVG only. Set CHROME_PATH to its executable.", file=sys.stderr)
        return
    w_px, h_px = math.ceil(wmm * 96 / 25.4), math.ceil(hmm * 96 / 25.4)
    try:
        subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--window-size={w_px},{h_px}", f"--screenshot={svg_p.with_suffix('.png').resolve()}",
                        svg_p.resolve().as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    except subprocess.TimeoutExpired:
        print("The browser took too long, no PNG; the SVG is written", file=sys.stderr)


def find_browser():
    for p in [os.environ.get("CHROME_PATH")] + [shutil.which(n) for n in ("chrome", "google-chrome", "chromium", "chromium-browser", "msedge")] + [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]:
        if p and Path(p).exists():
            return p
    return None


if __name__ == "__main__":
    main()
