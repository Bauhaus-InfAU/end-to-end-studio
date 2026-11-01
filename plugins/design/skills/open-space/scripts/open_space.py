"""The open-space layer of a design: parks, kept green, playgrounds, rain retention and green links.

  python open_space.py --site site.geojson --layers SITE_DIR --massing massing.geojson \
                       --config config.json --out OUT_DIR [--structure structure.geojson] [--style style.json]

SITE_DIR holds the site's layers (buildings, plots, streets, water). Every number comes from config.json,
which the skill writes from the brief and the programme; see ../SKILL.md for its keys. Needs shapely and pyproj;
the PNG needs Chrome or Edge (or Chromium) for a headless screenshot.
"""
import argparse, csv, json, math, os, shutil, subprocess, sys
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer
from shapely import shortest_line, unary_union
from shapely.geometry import Point, mapping, shape

# Defaults for keys config.json leaves out. Each one used is written to assumptions.md with this note.
DEFAULTS = {
    "keep_landuse": (["forest", "natural:wood", "natural:scrub", "natural:wetland", "meadow", "leisure:park",
                      "leisure:nature_reserve", "allotments", "orchard"], "OSM land uses kept as existing green"),
    "street_widths_m": ({"motorway": 25, "trunk": 20, "primary": 16, "secondary": 14, "tertiary": 12,
                         "residential": 10, "unclassified": 8, "service": 6, "living_street": 8,
                         "footway": 3, "cycleway": 3, "path": 2.5, "track": 3, "pedestrian": 6, "steps": 2},
                        "width of existing streets by OSM highway type, m"),
    "private_landuse": (["residential", "commercial", "industrial", "retail", "farmyard", "railway", "construction",
                         "garages", "allotments", "cemetery"], "OSM land uses that stay as they are, never parks"),
    "new_street_width_m": (16, "width of a massing street without a width, m"),
    "min_park_width_m": (12, "free land narrower than this is street green, not a park, m"),
    "min_park_m2": (2000, "smallest piece of free land counted as a park, m²"),
    "noisy_highways": (["motorway", "trunk", "primary"], "roads whose noise playgrounds keep away from"),
    "noise_distance_m": (50, "distance of playgrounds from noisy roads, m"),
    "play_reach_m": (300, "straight-line distance from every home building to a playground, m"),
    "design_rain_mm": (30, "rain held where it falls, mm (a common sponge-city target, not from the brief)"),
    "retention_depth_m": (0.3, "mean water depth of a swale or retention hollow, m"),
    "retention_max_share": (0.3, "largest share of a park given to retention"),
    "runoff": ({"roof": 0.9, "street": 0.9, "partly_sealed": 0.5, "green": 0.1},
               "runoff coefficients (roughly DWA-A 138)"),
    "square_sealing": ("partly", "squares are partly sealed (permeable paving)"),
    "link_max_m": (400, "longest green link drawn between two parks or to the landscape, m"),
    "landscape_reach_m": (300, "outside green this close to the site gets a link, m"),
    "scale": (3000, "scale of the check plan, 1:n"),
}

FALLBACK_STYLE = {"paper": "#fff", "ink": "#000", "building": "#9a9a9a", "existing": "#d0d0d0", "street": "#f2f2f2",
                  "park": "#dcdcdc", "kept": "#b5b5b5", "water": "#7f7f7f", "accent": "#1f6fb2",
                  "font": "Helvetica, Arial, sans-serif", "line": 0.25, "outline": 0.6}

PUBLIC_USES = {"park", "square", "playground", "sports", "water"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["features"]


def utm_for(lon, lat):
    epsg = (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1
    return Transformer.from_crs(4326, epsg, always_xy=True), Transformer.from_crs(epsg, 4326, always_xy=True)


def transform(tr, g):
    return shapely.transform(g, lambda c: np.column_stack(tr(c[:, 0], c[:, 1])))


def area_of(geoms):
    return unary_union(geoms).area if geoms else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--layers", required=True)
    ap.add_argument("--massing", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--structure")
    ap.add_argument("--style")
    a = ap.parse_args()

    cfg_in = load_json(a.config)
    cfg, used_defaults = {}, []
    for k, (v, note) in DEFAULTS.items():
        if k in cfg_in:
            cfg[k] = cfg_in[k]
        else:
            cfg[k] = v
            used_defaults.append((k, v, note))
    for k in ("residents", "green_m2_per_resident", "play_m2_per_resident", "play_min_m2"):
        if k not in cfg_in:
            sys.exit(f"config.json needs '{k}', from the programme or the brief")
        cfg[k] = cfg_in[k]
    style = dict(FALLBACK_STYLE, **(load_json(a.style) if a.style else {}))

    site_ll = unary_union([shape(f["geometry"]) for f in load(a.site)])
    to_m, to_ll = utm_for(site_ll.centroid.x, site_ll.centroid.y)
    m = lambda g: transform(to_m.transform, g)
    site = m(site_ll).buffer(0)
    layers = Path(a.layers)

    def layer(name):
        p = layers / f"{name}.geojson"
        return [(f["properties"], m(shape(f["geometry"]))) for f in load(p)] if p.exists() else []

    # The massing: buildings, streets, its own open spaces.
    mass = [(f["properties"], m(shape(f["geometry"]))) for f in load(a.massing)]
    new_bld = [g for p, g in mass if p.get("kind") == "building" and not p.get("existing")]
    homes = [g for p, g in mass if p.get("kind") == "building" and not p.get("existing")
             and str(p.get("use", "")).lower() in ("residential", "housing", "mixed", "homes", "")]
    mass_streets = [g if g.geom_type.endswith("Polygon") else g.buffer((p.get("width") or cfg["new_street_width_m"]) / 2, cap_style="flat")
                    for p, g in mass if p.get("kind") == "street"]
    mass_open = [(p, g) for p, g in mass if p.get("kind") == "open-space"]
    mass_squares = [g for p, g in mass_open if p.get("use") == "square"]

    # The site today, inside the boundary.
    old_bld = [g for _, g in layer("buildings") if g.intersects(site)]
    noisy, old_streets = [], []
    for p, g in layer("streets"):
        if not g.intersects(site.buffer(cfg["noise_distance_m"])):
            continue
        hw = p.get("highway")
        if hw in cfg["noisy_highways"]:
            noisy.append(g)
        if g.intersects(site):
            old_streets.append(g.buffer(cfg["street_widths_m"].get(hw, 6) / 2, cap_style="flat"))
    plots = layer("plots")
    kept = [(p.get("landuse"), g.intersection(site)) for p, g in plots
            if p.get("landuse") in cfg["keep_landuse"] and g.intersects(site)]
    water = [g.intersection(site) for p, g in layer("water") if g.geom_type.endswith("Polygon") and g.intersects(site)]
    private = unary_union([g.intersection(site) for p, g in plots if p.get("landuse") in cfg["private_landuse"]
                           and p.get("landuse") not in cfg["keep_landuse"] and g.intersects(site)])
    near_out = unary_union([g for p, g in plots if p.get("landuse") in cfg["keep_landuse"]
                            and g.distance(site) <= cfg["landscape_reach_m"]]).difference(site.buffer(1))
    outside_green = [g for g in getattr(near_out, "geoms", [near_out]) if g.area >= cfg["min_park_m2"]]

    buildings = unary_union(new_bld + old_bld)
    streets = unary_union(mass_streets + old_streets).intersection(site)
    sealed = unary_union([buildings, streets]).intersection(site)
    kept_u = unary_union([g for _, g in kept] + water).difference(sealed)
    taken = unary_union([sealed, kept_u, private] + [g for _, g in mass_open])

    # Parks: the free land wide and big enough; corridors of the structure plan come first.
    free = site.difference(taken)
    r = cfg["min_park_width_m"] / 2
    opened = free.buffer(-r).buffer(r).intersection(free)
    parks = [g for g in getattr(opened, "geoms", [opened]) if g.area >= cfg["min_park_m2"]]
    if a.structure:
        corr = unary_union([m(shape(f["geometry"])) for f in load(a.structure)
                            if "corridor" in str(f["properties"].get("kind", "")) + str(f["properties"].get("use", ""))])
        if not corr.is_empty:
            parks = [g for g in parks if not g.intersects(corr)] + [g for g in parks if g.intersects(corr)]
    verge = free.difference(unary_union(parks)) if parks else free

    # Playgrounds: fewest places that bring every home within reach, quiet ones only.
    need_play = max(cfg["residents"] * cfg["play_m2_per_resident"], cfg["play_min_m2"])
    quiet = unary_union(parks).buffer(-5)
    if noisy:
        quiet = quiet.difference(unary_union(noisy).buffer(cfg["noise_distance_m"]))
    cands = grid_points(quiet, 25)
    demand = [h.centroid for h in homes]
    left, play_pts = set(range(len(demand))), []
    while left and cands:
        best = max(cands, key=lambda c: sum(1 for i in left if demand[i].distance(c) <= cfg["play_reach_m"]))
        hit = {i for i in left if demand[i].distance(best) <= cfg["play_reach_m"]}
        if not hit:
            break
        play_pts.append(best)
        left -= hit
    if not play_pts and not quiet.is_empty:
        play_pts = [quiet.representative_point()]
    each = need_play / len(play_pts) if play_pts else 0
    playgrounds = [grow(pt, each, unary_union(parks).buffer(-3)) for pt in play_pts]
    unreached = len(left)

    # Retention: each park holds the rain of the new roofs and streets nearest to it; what exists drains already.
    ro = cfg["runoff"]
    sq_part = cfg["square_sealing"] == "partly"
    pieces = [(g, ro["roof"]) for g in new_bld if g.intersects(site)]
    pieces += [(g, ro["street"]) for g in mass_streets]
    pieces += [(g, ro["partly_sealed"] if sq_part else ro["street"]) for g in mass_squares]
    catch = [0.0] * len(parks)
    for g, c in pieces:
        if parks and not g.is_empty:
            i = min(range(len(parks)), key=lambda j: parks[j].distance(g.centroid))
            catch[i] += g.intersection(site).area * c
    play_u = unary_union(playgrounds) if playgrounds else None
    basins = []
    for i, park in enumerate(parks):
        vol = catch[i] * cfg["design_rain_mm"] / 1000
        if vol <= 0:
            continue
        room = park.buffer(-3)
        if play_u is not None:
            room = room.difference(play_u.buffer(5))
        want = vol / cfg["retention_depth_m"]
        cap = park.area * cfg["retention_max_share"]
        seed = room.boundary.interpolate(room.boundary.project(nearest_sealed(park, sealed))) if not room.is_empty else None
        g = grow(seed, min(want, cap), room) if seed is not None else None
        if g is not None and not g.is_empty:
            basins.append((g, vol, g.area * cfg["retention_depth_m"], catch[i]))

    # Green links: a tree of the shortest links between parks, and one from each piece of landscape outside to
    # its nearest park. A link may cross a street, never a building; the parks left without one are counted.
    links = []
    ok = lambda ln: not ln.intersects(buildings)
    if len(parks) > 1:
        pairs = sorted((parks[i].distance(parks[j]), i, j) for i in range(len(parks)) for j in range(i + 1, len(parks))
                       if parks[i].distance(parks[j]) <= cfg["link_max_m"])
        group = list(range(len(parks)))
        root = lambda i: i if group[i] == i else root(group[i])
        for d, i, j in pairs:
            if root(i) == root(j):
                continue
            ln = shortest_line(parks[i], parks[j])
            if d == 0 or ok(ln):
                group[root(i)] = root(j)
                if d > 0:
                    links.append((ln, "park"))
    starts = []
    for og in outside_green:
        if parks:
            near = min(parks, key=lambda p: p.distance(og))
            ln = shortest_line(near, og)
            if 0 < ln.length <= cfg["link_max_m"] and ok(ln) and all(Point(ln.coords[0]).distance(q) > 50 for q in starts):
                links.append((ln, "landscape"))
                starts.append(Point(ln.coords[0]))
    linked = {i for i, p in enumerate(parks) for ln, _ in links if ln.distance(p) < 0.5}
    alone = sum(1 for i, p in enumerate(parks) if i not in linked and not any(p.intersects(q) for q in parks if q is not p))

    # Write.
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    feats = []

    def add(g, **props):
        if g is None or g.is_empty:
            return
        feats.append({"type": "Feature", "properties": props,
                      "geometry": mapping(transform(to_ll.transform, g.simplify(0.3)))})

    for lu, g in kept:
        add(g.difference(sealed), kind="open-space", use="park", existing=True, landuse=lu, area_m2=round(g.area))
    for g in water:
        add(g, kind="open-space", use="water", existing=True, area_m2=round(g.area))
    for k, g in enumerate(parks):
        add(g, kind="open-space", use="park", existing=False, id=f"park-{k + 1}", area_m2=round(g.area))
    for g in playgrounds:
        add(g, kind="open-space", use="playground", existing=False, area_m2=round(g.area))
    for g, vol, held, c in basins:
        add(g, kind="retention", area_m2=round(g.area), depth_m=cfg["retention_depth_m"],
            volume_m3=round(held), needed_m3=round(vol), catchment_m2=round(c))
    for g, to in links:
        add(g, kind="green-link", to=to, length_m=round(g.length),
            crosses_street=bool(g.intersects(streets)))
    with open(out / "open-space.geojson", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)

    # Areas against the brief.
    park_a = area_of(parks)
    kept_a = kept_u.area
    play_a = area_of(playgrounds)
    need_green = cfg["residents"] * cfg["green_m2_per_resident"]
    need_vol = sum(b[1] for b in basins)
    held_vol = sum(b[2] for b in basins)
    src = cfg_in.get("sources", {})
    rows = [
        ("public green (new parks)", need_green, park_a, "m2", src.get("green_m2_per_resident", "config.json")),
        ("kept green and water (not counted as public green)", "", kept_a, "m2", "site layers"),
        ("play area", need_play, play_a, "m2", src.get("play_m2_per_resident", "config.json")),
        ("homes buildings beyond play reach", 0, unreached, "buildings", f"{cfg['play_reach_m']} m reach"),
        ("parks without a green link", 0, alone, "parks", "links may cross streets, not buildings"),
        ("rain retention volume", need_vol, held_vol, "m3", f"{cfg['design_rain_mm']} mm on new roofs, streets, squares"),
    ]
    with open(out / "areas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["measure", "required", "design", "difference", "unit", "source"])
        for name, req, des, unit, s in rows:
            diff = round(des - req) if req != "" else ""
            w.writerow([name, round(req) if req != "" else "", round(des), diff, unit, s])

    site_a = site.area
    sq_a = area_of(mass_squares)
    full = sealed.area + (0 if sq_part else sq_a)
    part = (sq_a if sq_part else 0) + play_a
    with open(out / "sealing.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["surface", "area_m2", "share_pct", "counted_as"])
        w.writerow(["buildings and streets", round(sealed.area), pct(sealed.area, site_a), "fully sealed"])
        w.writerow(["squares", round(sq_a), pct(sq_a, site_a), "partly sealed" if sq_part else "fully sealed"])
        w.writerow(["playgrounds", round(play_a), pct(play_a, site_a), "partly sealed"])
        w.writerow(["fully sealed", round(full), pct(full, site_a), ""])
        w.writerow(["partly sealed", round(part), pct(part, site_a), ""])
        w.writerow(["unsealed", round(site_a - full - part), pct(site_a - full - part, site_a), ""])

    with open(out / "assumptions.md", "w", encoding="utf-8") as f:
        f.write("# Assumptions\n\nValues from config.json, with their sources:\n\n")
        for k, v in cfg_in.items():
            if k != "sources":
                f.write(f"- `{k}`: {v}" + (f" ({src[k]})" if k in src else "") + "\n")
        f.write("\nDefaults of the script, not from the brief:\n\n")
        for k, v, note in used_defaults:
            f.write(f"- `{k}` = {v}: {note}\n")
        f.write("\nGeneral:\n\n- Without a terrain model, rain is held in the nearest park, not where it flows; "
                "levels must be checked.\n- Distances are straight lines, not walking routes.\n"
                "- The massing's courtyards are private gardens and are not counted as public green.\n")

    draw(out, site, buildings, old_bld, streets, kept_u, water, parks, playgrounds, basins, links, cfg, style, to_ll)
    print(json.dumps({"parks": len(parks), "park_m2": round(park_a), "need_green_m2": round(need_green),
                      "playgrounds": len(playgrounds), "play_m2": round(play_a), "need_play_m2": round(need_play),
                      "homes_unreached": unreached, "basins": len(basins), "retention_m3": round(held_vol),
                      "need_retention_m3": round(need_vol), "links": len(links),
                      "parks_unlinked": alone,
                      "fully_sealed_pct": pct(full, site_a), "partly_sealed_pct": pct(part, site_a),
                      "verge_m2": round(verge.area)}, indent=1))


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def pct(x, total):
    return round(100 * x / total, 1) if total else 0


def grid_points(poly, step):
    if poly.is_empty:
        return []
    x0, y0, x1, y1 = poly.bounds
    pts = [Point(x0 + i * step, y0 + j * step) for i in range(int((x1 - x0) / step) + 1)
           for j in range(int((y1 - y0) / step) + 1)]
    return [p for p in pts if poly.contains(p)]


def grow(pt, target, room):
    """A round area of `target` m² around pt, inside room; grows until it reaches the target or fills its piece."""
    if pt is None or target <= 0 or room.is_empty:
        return None
    rad = math.sqrt(target / math.pi)
    g = pt.buffer(rad).intersection(room)
    for _ in range(40):
        if g.area >= target * 0.98:
            break
        rad *= min(math.sqrt(target / max(g.area, 1)) * 1.05, 2)
        nxt = pt.buffer(rad).intersection(room)
        if nxt.area <= g.area * 1.001:
            break
        g = nxt
    return g


def nearest_sealed(park, sealed):
    """The point of the park nearest to the sealed land, where its rain arrives."""
    if sealed.is_empty:
        return park.centroid
    return Point(shortest_line(park, sealed).coords[0])


def draw(out, site, buildings, old_bld, streets, kept, water, parks, playgrounds, basins, links, cfg, s, to_ll):
    x0, y0, x1, y1 = site.buffer(80).bounds
    scale = cfg["scale"]
    wmm, hmm = (x1 - x0) / scale * 1000, (y1 - y0) / scale * 1000
    head = 40 * scale / 1000  # 40 mm for the legend, in metres
    H = (y1 - y0) + head

    def path(g):
        polys = getattr(g, "geoms", [g])
        d = []
        for p in polys:
            if p.geom_type == "Polygon":
                for ring in [p.exterior, *p.interiors]:
                    d.append("M" + " L".join(f"{x - x0:.1f},{y1 - y:.1f}" for x, y in ring.coords) + "Z")
            elif p.geom_type == "LineString":
                d.append("M" + " L".join(f"{x - x0:.1f},{y1 - y:.1f}" for x, y in p.coords))
            elif hasattr(p, "geoms"):
                d.append(path(p))
        return " ".join(d)

    k = scale / 1000  # metres per mm
    lw = lambda mm: f"{mm * k:.2f}"
    els = []

    def shape_el(g, fill, stroke="none", w=0.0, extra=""):
        if g is None or g.is_empty:
            return
        els.append(f'<path d="{path(g)}" fill="{fill}" stroke="{stroke}" stroke-width="{lw(w)}" fill-rule="evenodd" {extra}/>')

    shape_el(streets, s["street"], s["ink"], s["line"] / 2)
    shape_el(unary_union(parks) if parks else None, s["park"])
    shape_el(kept, s["kept"])
    shape_el(unary_union(water) if water else None, s["water"])
    for g, *_ in basins:
        shape_el(g, s["accent"], extra='fill-opacity="0.45"')
    for g in playgrounds:
        shape_el(g, "none", s["accent"], s["outline"], extra=f'stroke-dasharray="{lw(1)} {lw(0.6)}"')
    shape_el(unary_union(old_bld).intersection(site.buffer(80)) if old_bld else None, s["existing"], s["ink"], s["line"])
    shape_el(buildings.difference(unary_union(old_bld)) if old_bld else buildings, s["building"], s["ink"], s["line"])
    for g, _ in links:
        shape_el(g, "none", s["accent"], s["outline"] * 1.5, extra=f'stroke-dasharray="{lw(2)} {lw(1.2)}"')
    shape_el(site.boundary, "none", s["ink"], s["outline"] * 1.5, extra=f'stroke-dasharray="{lw(4)} {lw(1.5)}"')

    fs = 3.2 * k
    ly = (y1 - y0) + 8 * k
    legend = [("park", s["park"], ""), ("kept green", s["kept"], ""), ("water", s["water"], ""),
              ("rain retention", s["accent"], 'fill-opacity="0.45"'), ("playground", "none", ""),
              ("green link", None, "")]
    lx = 6 * k
    for name, fill, extra in legend:
        if fill is None:
            els.append(f'<line x1="{lx}" y1="{ly + 2 * k}" x2="{lx + 8 * k}" y2="{ly + 2 * k}" stroke="{s["accent"]}" '
                       f'stroke-width="{lw(s["outline"] * 1.5)}" stroke-dasharray="{lw(2)} {lw(1.2)}"/>')
        else:
            st = s["accent"] if name == "playground" else s["ink"]
            els.append(f'<rect x="{lx}" y="{ly}" width="{8 * k}" height="{4 * k}" fill="{fill}" {extra} '
                       f'stroke="{st}" stroke-width="{lw(s["line"])}"/>')
        els.append(f'<text x="{lx + 10 * k}" y="{ly + 3.3 * k}" font-size="{fs}" font-family="{s["font"]}">{name}</text>')
        lx += (14 + len(name) * 1.9) * k
    # graphic scale: a round length near a fifth of the width
    bar = min((b for b in (50, 100, 200, 250, 500, 1000, 2000) if b >= (x1 - x0) / 6), default=1000)
    by = ly + 14 * k
    for i in range(4):
        els.append(f'<rect x="{6 * k + i * bar / 4}" y="{by}" width="{bar / 4}" height="{1.5 * k}" '
                   f'fill="{s["ink"] if i % 2 == 0 else s["paper"]}" stroke="{s["ink"]}" stroke-width="{lw(s["line"])}"/>')
    els.append(f'<text x="{6 * k}" y="{by + 6 * k}" font-size="{fs}" font-family="{s["font"]}">0</text>')
    els.append(f'<text x="{6 * k + bar}" y="{by + 6 * k}" font-size="{fs}" font-family="{s["font"]}" text-anchor="middle">{bar} m</text>')
    els.append(f'<text x="{6 * k + bar + 12 * k}" y="{by + 2 * k}" font-size="{fs}" font-family="{s["font"]}">'
               f'1:{scale}   N ↑   Map data © OpenStreetMap contributors</text>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{wmm:.1f}mm" height="{wmm * H / (x1 - x0):.1f}mm" '
           f'viewBox="0 0 {x1 - x0:.1f} {H:.1f}"><rect width="100%" height="100%" fill="{s["paper"]}"/>'
           + "".join(els) + "</svg>")
    name = f"open-space_1-{scale}"
    svg_p = out / f"{name}.svg"
    svg_p.write_text(svg, encoding="utf-8")
    browser = find_browser()
    if not browser:
        print("No Chrome, Edge or Chromium found: SVG only. Set CHROME_PATH to its executable.", file=sys.stderr)
        return
    w_px, h_px = math.ceil(wmm * 96 / 25.4), math.ceil(wmm * H / (x1 - x0) * 96 / 25.4)  # the browser draws 96 px per inch
    try:
        subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--window-size={w_px},{h_px}", f"--screenshot={svg_p.with_suffix('.png').resolve()}",
                        svg_p.resolve().as_uri()],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
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
