"""The open-space layer of a design: parks, kept green, playgrounds, rain retention, green links and trees.

  python open_space.py --site site.geojson --layers SITE_DIR --massing massing.geojson \
                       --config config.json --out OUT_DIR [--structure corridors.geojson ...]
                       [--keep-free strips.geojson] [--style style.json]

SITE_DIR holds the site's layers (buildings, plots, streets, water) and, if there is one, its terrain: a GeoTIFF
(terrain*.tif, or the one kit.json names), else terrain.csv (lon, lat, ele). With terrain, the pools and hollows fill
the low ground and the rain runs downhill to them; without, they sit by shape and distance. Every number comes from config.json,
which the skill writes from the brief and the programme; see ../SKILL.md for its keys. Needs shapely and pyproj,
and Pillow to read a GeoTIFF; the PNG needs Chrome or Edge (or Chromium) for a headless screenshot.
"""
import argparse, csv, heapq, json, math, os, re, shutil, subprocess, sys, textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from terrain import find_terrain  # noqa: E402  (this skill's own copy)

import numpy as np
import shapely
from pyproj import Transformer
from shapely import shortest_line, unary_union
from shapely.geometry import LineString, Point, mapping, shape

# Defaults for keys config.json leaves out. Each one used is written to assumptions.md with this note.
DEFAULTS = {
    "keep_landuse": (["forest", "natural:wood", "natural:scrub", "natural:wetland", "meadow", "leisure:park",
                      "leisure:nature_reserve", "allotments", "orchard", "grass", "leisure:pitch",
                      "leisure:sports_centre", "leisure:playground"], "OSM land uses kept as existing green"),
    "street_widths_m": ({"motorway": 25, "trunk": 20, "primary": 16, "secondary": 14, "tertiary": 12,
                         "residential": 10, "unclassified": 8, "service": 6, "living_street": 8,
                         "footway": 3, "cycleway": 3, "path": 2.5, "track": 3, "pedestrian": 6, "steps": 2},
                        "width of existing streets by OSM highway type, m"),
    "private_landuse": (["residential", "commercial", "industrial", "retail", "farmyard", "railway", "construction",
                         "garages", "allotments", "cemetery"], "OSM land uses that stay as they are, never parks"),
    "other_street_width_m": (6, "width of an existing street of a type not in street_widths_m, m"),
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
    "corridor_min_length_m": (300, "a park this long and this wide is a corridor, the spine of the network, m"),
    "corridor_min_width_m": (40, "least mean width of a corridor, m"),
    "corridor_catch_m": (300, "roofs and streets this close to a corridor drain to it, m"),
    "corridor_retention_max_share": (0.35, "largest share of a corridor given to pools"),
    "pool_shallow_m": (0.25, "water depth of a pool's shallow edge, m"),
    "pool_deep_m": (0.8, "water depth of a pool's deep core, m"),
    "pool_shallow_band_m": (6, "width of a pool's shallow edge, m"),
    "pool_crossing_every_m": (120, "a dry crossing cuts a chain of pools this often along the corridor, m"),
    "pool_crossing_width_m": (10, "width of a dry crossing, m"),
    "woodland_landuse": (["forest", "natural:wood", "natural:scrub"], "kept land uses that new groves extend"),
    "lawn_band_m": (25, "lawn for play and rest this close to buildings and streets, m"),
    "wet_band_m": (10, "wet meadow this wide around a pool, m"),
    "grove_band_m": (20, "groves this wide beside kept woodland, m"),
    "path_inset_m": (12, "a park's loop path runs this far inside its edge, m"),
    "path_width_m": (3, "width of a path, partly sealed, m"),
    "min_loop_park_m2": (8000, "smallest park that gets a loop path, m²"),
    "tree_sizes": ({"avenue": [8, 14, 12], "courtyard": [7, 10, 12], "grove": [8, 15, 9], "park": [10, 15, 8]},
                   "planted trees by group: crown diameter, height, spacing, m"),
    "canopy_landuse": ({"forest": ["wood", 10, 20], "natural:wood": ["wood", 10, 20], "natural:scrub": ["wood", 5, 5],
                        "orchard": ["orchard", 6, 6]}, "kept land uses drawn as canopy: group, crown diameter, height, m"),
    "avenue_offset_m": (4, "avenue trees stand this far either side of a park path's centre line, m"),
    "cluster_every_m": (35, "in parks, a loose cluster of one to five trees about this far apart, m"),
    "treeless_roles": (["agriculture", "energy", "utility", "sport"], "structure-plan green roles whose land gets no trees"),
    "open_landuse": (["farmland", "meadow", "grass"],
                     "land uses that stay without trees where the structure plan keeps them (everywhere without one)"),
    "tree_seed": (1, "seed of the trees' jitter, so that a run repeats"),
    "terrain_cell_m": (2, "with terrain: grid on which pools and hollows fill the low ground, m"),
    "flow_cell_m": (5, "with terrain: grid on which the rain's way downhill is traced, m"),
    "flow_margin_m": (100, "with terrain: the rain's way is traced this far beyond the site, m"),
    "pool_round_m": (4, "with terrain: pools and hollows are rounded by this radius, m"),
    "scale": (3000, "scale of the check plan, 1:n"),
}

FALLBACK_STYLE = {"paper": "#fff", "ink": "#000", "building": "#9a9a9a", "existing": "#d0d0d0", "street": "#f2f2f2",
                  "park": "#dcdcdc", "kept": "#b5b5b5", "water": "#7f7f7f", "accent": "#1f6fb2",
                  "lawn": "#ececec", "meadow": "#dcdcdc", "wet-meadow": "#cfd6dc", "grove": "#bdbdbd", "path": "#fff",
                  "font": "Helvetica, Arial, sans-serif", "line": 0.25, "outline": 0.6, "text": 3.2, "title": 4.2,
                  "context": "#e4e4e4"}

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
    ap.add_argument("--structure", nargs="*", default=[])  # GeoJSONs whose corridors (structure plan, climate) are spines;
    # the structure plan's `action` and green `roles` also say which land keeps no trees
    ap.add_argument("--keep-free")  # GeoJSON of the brief's strips and protected land; lines carry `width_m`
    ap.add_argument("--style")
    ap.add_argument("--streets", help="the streets skill's streets.geojson; its surface replaces the buffered lines")
    ap.add_argument("--frame", nargs=2, type=float, metavar=("W", "H"), help="without a frame in the panels' plan: the plan's frame, mm")
    ap.add_argument("--centre", nargs=2, type=float, metavar=("LON", "LAT"), help="the frame's centre (default: the site's)")
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
    std = load_json(a.style) if a.style else {}   # the standard's keys this plan has, by name, never merged
    style = {k: std.get(k, v) for k, v in FALLBACK_STYLE.items()}
    dg = std.get("diagram") if isinstance(std.get("diagram"), dict) else {}   # a thematic plan's weights and text sizes, px
    style.update({k: dg[d] * 25.4 / 96 for k, d in (("line", "line"), ("outline", "outline"), ("text", "label_size"),
                                                    ("title", "title_size")) if d in dg})

    site_ll = unary_union([shape(f["geometry"]) for f in load(a.site)])
    to_m, to_ll = utm_for(site_ll.centroid.x, site_ll.centroid.y)
    m = lambda g: transform(to_m.transform, g)
    site = m(site_ll).buffer(0)
    layers = Path(a.layers)
    # The terrain of the site folder, if it has one: a GeoTIFF, else terrain.csv.
    ter, ter_notes = find_terrain(layers, site.buffer(cfg["flow_margin_m"]).bounds, to_ll)
    ground = Ground(ter, cfg["terrain_cell_m"]) if ter else None
    if not ter:
        used_defaults = [d for d in used_defaults if d[0] not in ("terrain_cell_m", "flow_cell_m", "flow_margin_m", "pool_round_m")]

    def layer(name):
        p = layers / f"{name}.geojson"
        return [(f["properties"], m(shape(f["geometry"]))) for f in load(p)] if p.exists() else []

    # The massing: buildings, streets, its own open spaces.
    mass = [(f["properties"], m(shape(f["geometry"]))) for f in load(a.massing)]
    new_bld = [g for p, g in mass if p.get("kind") == "building" and not p.get("existing")]
    homes = [g for p, g in mass if p.get("kind") == "building" and not p.get("existing")
             and (not p.get("use") or any(w in str(p["use"]).lower() for w in ("residential", "housing", "mixed", "home")))]
    mass_streets = [g if g.geom_type.endswith("Polygon") else g.buffer((p.get("width") or cfg["new_street_width_m"]) / 2, cap_style="flat")
                    for p, g in mass if p.get("kind") == "street"]
    mass_open = [(p, g) for p, g in mass if p.get("kind") == "open-space"]
    mass_squares = [g for p, g in mass_open if p.get("use") == "square"]

    # The site today, inside the boundary.
    kept_bld = [g for p, g in mass if p.get("kind") == "building" and p.get("existing")]
    old_bld = kept_bld or [g for _, g in layer("buildings") if g.intersects(site)]
    noisy, old_streets = [], []
    for p, g in layer("streets"):
        if not g.intersects(site.buffer(cfg["noise_distance_m"])):
            continue
        hw = p.get("highway")
        if hw in cfg["noisy_highways"]:
            noisy.append(g)
        if g.intersects(site):
            old_streets.append(g.buffer(cfg["street_widths_m"].get(hw, cfg["other_street_width_m"]) / 2, cap_style="flat"))
    streets_src = "buffered from the site's street lines and the massing's, at the widths above"
    if a.streets and os.path.exists(a.streets):
        # the streets skill's one surface: existing and new street polygons, instead of buffering lines
        surf = [(f["properties"], m(shape(f["geometry"]))) for f in load(a.streets)
                if f["properties"].get("kind") == "street" and shape(f["geometry"]).geom_type.endswith("Polygon")]
        old_streets = [g.intersection(site) for p, g in surf if p.get("existing")]
        mass_streets = [g.intersection(site) for p, g in surf if not p.get("existing")]
        streets_src = "from the streets skill (`streets.geojson`), not buffered lines"
        used_defaults = [d for d in used_defaults if d[0] not in ("street_widths_m", "other_street_width_m", "new_street_width_m")]
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
    taken = unary_union([sealed, kept_u, private] + [g for p, g in mass_open if p.get("use") != "park"])

    # Parks: the free land wide and big enough; corridors of the structure plan come first.
    free = site.difference(taken)
    r = cfg["min_park_width_m"] / 2
    opened = free.buffer(-r).buffer(r).intersection(free)
    parks = [g for g in getattr(opened, "geoms", [opened]) if g.area >= cfg["min_park_m2"]]
    corr = shapely.Polygon()
    if a.structure:
        corr = unary_union([m(shape(f["geometry"])) for src_path in a.structure for f in load(src_path)
                            if "corridor" in str(f["properties"].get("kind", "")) + str(f["properties"].get("use", ""))])
        if not corr.is_empty:
            parks = [g for g in parks if not g.intersects(corr)] + [g for g in parks if g.intersects(corr)]
    verge = free.difference(unary_union(parks)) if parks else free
    corridor = [is_corridor(g, cfg) or (not corr.is_empty and g.intersects(corr)) for g in parks]

    # The brief's strips (pipes, power lines) and protected land take no pool, playground or path.
    keep_free = shapely.Polygon()
    if a.keep_free:
        if any("width_m" not in f["properties"] for f in load(a.keep_free) if not shape(f["geometry"]).geom_type.endswith("Polygon")):
            used_defaults.append(("keep-free width_m", 1, "width of a keep-free line without width_m, m"))
        keep_free = unary_union([m(shape(f["geometry"])).buffer((f["properties"].get("width_m") or 1) / 2)
                                 if not shape(f["geometry"]).geom_type.endswith("Polygon") else m(shape(f["geometry"]))
                                 for f in load(a.keep_free)]).intersection(site)

    # Playgrounds: fewest places that bring every home within reach, quiet ones only.
    need_play = max(cfg["residents"] * cfg["play_m2_per_resident"], cfg["play_min_m2"])
    quiet = unary_union(parks).buffer(-5).difference(keep_free)
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
    playgrounds = [grow(pt, each, unary_union(parks).buffer(-3).difference(keep_free)) for pt in play_pts]
    unreached = len(left)

    # Retention: each park holds the rain of the new roofs and streets nearest to it; what exists drains already.
    ro = cfg["runoff"]
    sq_part = cfg["square_sealing"] == "partly"
    pieces = [(g, ro["roof"]) for g in new_bld if g.intersects(site)]
    pieces += [(g, ro["street"]) for g in mass_streets]
    pieces += [(g, ro["partly_sealed"] if sq_part else ro["street"]) for g in mass_squares]
    # Like a river valley, the corridors gather the rain of everything near them; the rest goes to the nearest park.
    # With terrain, the rain runs downhill: to the first corridor its way enters near it, else the first park.
    catch = [0.0] * len(parks)
    cidx = [i for i, c in enumerate(corridor) if c]
    drains = {"downhill": 0.0, "piped": 0.0, "uphill": 0.0}
    flow = drainage(ground, site.buffer(cfg["flow_margin_m"]), parks, corridor, cfg) if ground and parks else None
    to_park = flow.to_park if flow else None
    for g, c in pieces:
        if to_park and not g.is_empty:
            xs, ys = ground.points(g, cfg["flow_cell_m"])
            if not len(xs):
                p = g.representative_point()
                xs, ys = np.array([p.x]), np.array([p.y])
            share = g.intersection(site).area * c / len(xs)
            for i, how in to_park(xs, ys):
                catch[i] += share
                drains[how] += share
        elif parks and not g.is_empty:
            near_c = min(cidx, key=lambda j: parks[j].distance(g), default=None)
            if near_c is not None and parks[near_c].distance(g) <= cfg["corridor_catch_m"]:
                i = near_c
            else:
                i = min(range(len(parks)), key=lambda j: parks[j].distance(g.centroid))
            catch[i] += g.intersection(site).area * c
    play_u = unary_union(playgrounds) if playgrounds else None
    avoid = unary_union([play_u.buffer(5) if play_u is not None else shapely.Polygon(), keep_free])
    basins, pools, no_room, short = [], [], 0, 0
    # With terrain, the parks uphill go first, and what a full park can't hold runs over to the next park downhill.
    inflow = [0.0] * len(parks)
    for i in (flow.upstream_first if flow else range(len(parks))):
        park = parks[i]
        vol = catch[i] * cfg["design_rain_mm"] / 1000 + inflow[i]
        if vol <= 0:
            continue
        g, held = None, 0.0
        if corridor[i]:
            # A chain of pools following the corridor's shape (with terrain, on its low ground): a shallow edge and a deep core.
            got = pool_chain(park, vol, cfg, avoid, ground)
            if got:
                g, deep, held = got
                pools.append((g, deep))
            elif not ground:
                no_room += 1
                continue
        if g is None:   # a park, or with terrain a corridor with too little rain for a chain: one hollow
            g, held = hollow(park, vol, cfg, avoid, ground, sealed)
        over = max(vol - held, 0) if flow else 0
        nxt = flow.next_park[i] if flow else -1
        if over > 0.05 * vol and nxt >= 0:
            inflow[nxt] += over
        elif over > 0.05 * vol:
            short += 1
        if g is not None and not g.is_empty:
            basins.append((g, vol, held, catch[i], (over, f"park-{nxt + 1}" if nxt >= 0 else "off the site") if over > 0.05 * vol else None))
        elif not flow:
            no_room += 1

    # Ground cover: wet meadow round the water, lawn near the homes, groves beside the kept woods, meadow elsewhere.
    water_u = unary_union([b[0] for b in basins]) if basins else shapely.Polygon()
    woods = unary_union([g for lu, g in kept if lu in cfg["woodland_landuse"]])
    built = unary_union([buildings, streets])
    covers = {}
    rest = unary_union(parks).difference(water_u) if parks else shapely.Polygon()
    for name, zone in (("wet-meadow", water_u.buffer(cfg["wet_band_m"])), ("lawn", built.buffer(cfg["lawn_band_m"])),
                       ("grove", woods.buffer(cfg["grove_band_m"])), ("meadow", rest)):
        covers[name] = rest.intersection(zone)
        rest = rest.difference(zone)

    # Paths: a loop inside each larger park; where a loop crosses water it is a boardwalk.
    paths, boardwalks = [], []
    for park in parks:
        if park.area < cfg["min_loop_park_m2"]:
            continue
        inner = park.buffer(-cfg["path_inset_m"] - 25).buffer(25)  # a loop with rounded bends
        for piece in getattr(inner, "geoms", [inner]):
            if piece.geom_type != "Polygon" or piece.area < cfg["min_loop_park_m2"] / 4:
                continue
            loop = piece.exterior.simplify(4)
            paths.append(loop.difference(water_u).difference(keep_free))
            if loop.intersects(water_u):
                boardwalks.append(loop.intersection(water_u))

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

    # Trees: no trunk on a street, building or path; no crown over a kept-free strip, water, a pool, a playground, a
    # building, a green whose roles keep it open (fields, solar park) or land the plan keeps that is open today.
    plan = [(p, g) for src_path in a.structure for f in load(src_path)
            for p, g in [(f["properties"], m(shape(f["geometry"])))] if g.geom_type.endswith("Polygon")]
    kept_zone = unary_union([g for p, g in plan if p.get("action") == "keep"]) if any("action" in p for p, _ in plan) else site
    wood = unary_union([g for lu, g in kept if lu in cfg["canopy_landuse"]])   # a wood on a field or a meadow is wood
    treeless = unary_union([g for p, g in plan if {str(r).lower() for r in p.get("roles") or []} & set(cfg["treeless_roles"])]
                           + [unary_union([g for p, g in plots if p.get("landuse") in cfg["open_landuse"]]).intersection(kept_zone)
                              .difference(wood)])
    no_crown = unary_union([keep_free, treeless, water_u, buildings] + water + playgrounds
                           + [g for p, g in mass_open if p.get("use") == "water"])
    no_trunk = unary_union([sealed] + [g.buffer(cfg["path_width_m"] / 2 + 0.5) for g in paths + boardwalks]
                           + [unary_union([g for lu, g in kept if lu not in cfg["canopy_landuse"]]).difference(wood)])
    courts = [g.intersection(site) for p, g in mass_open if p.get("use") == "garden"]
    trees = plant(cfg, kept, covers, paths, courts, sealed, no_crown, no_trunk)
    n_old = sum(1 for t in trees if t[4])

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
        add(g, kind="open-space", use="park", existing=False, id=f"park-{k + 1}", area_m2=round(g.area),
            role="corridor" if corridor[k] else "park")
    for name, g in covers.items():
        add(g, kind="ground-cover", cover=name, area_m2=round(g.area))
    for g in playgrounds:
        add(g, kind="open-space", use="playground", existing=False, area_m2=round(g.area))
    for g, vol, held, c, over in basins:
        add(g, kind="retention", area_m2=round(g.area), depth_m=round(held / max(g.area, 1), 2),
            volume_m3=round(held), needed_m3=round(vol), catchment_m2=round(c),
            **({"overflow_m3": round(over[0]), "overflows_to": over[1]} if over else {}))
    for g, deep in pools:
        add(deep, kind="retention", part="deep core", depth_m=cfg["pool_deep_m"], area_m2=round(deep.area))
    for g in paths:
        add(g, kind="path", width_m=cfg["path_width_m"], length_m=round(g.length))
    for g in boardwalks:
        add(g, kind="path", type="boardwalk", width_m=cfg["path_width_m"], length_m=round(g.length))
    for g, to in links:
        add(g, kind="green-link", to=to, length_m=round(g.length),
            crosses_street=bool(g.intersects(streets)))
    for pt, group, crown, height, existing in trees:
        add(pt, kind="tree", group=group, crown_m=crown, height_m=height, existing=existing)
    with open(out / "open-space.geojson", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)

    # Areas against the brief.
    park_a = area_of(parks)
    kept_a = kept_u.area
    play_a = area_of(playgrounds)
    need_green = cfg["residents"] * cfg["green_m2_per_resident"]
    need_vol = sum(g.intersection(site).area * c for g, c in pieces) * cfg["design_rain_mm"] / 1000  # all new rain, held or not
    held_vol = sum(b[2] for b in basins)
    src = cfg_in.get("sources", {})
    rows = [
        ("public green (new parks)", need_green, park_a, "m2", src.get("green_m2_per_resident", "config.json")),
        ("kept green and water (not counted as public green)", "", kept_a, "m2", "site layers"),
        ("play area", need_play, play_a, "m2", src.get("play_m2_per_resident", "config.json")),
        ("homes buildings beyond play reach", 0, unreached, "buildings", f"{cfg['play_reach_m']} m reach"),
        ("parks without a green link", 0, alone, "parks", "links may cross streets, not buildings"),
        ("rain retention volume", need_vol, held_vol, "m3", f"{cfg['design_rain_mm']} mm on new roofs, streets, squares"),
        ("parks that can't hold their rain", 0, short if flow else no_room + sum(1 for b in basins if b[2] < b[1] * 0.95),
         "parks", "the massing leaves them too little room" + ("; with terrain, a full park spills to the next one downhill,"
                                                               " and counts here only when nothing below it takes the rest" if flow else "")),
        ("corridors", "", sum(1 for c in corridor if c), "parks",
         f"at least {cfg['corridor_min_length_m']} m long and {cfg['corridor_min_width_m']} m wide"),
        ("trees planted (not kept wood)", "", len(trees) - n_old, "trees", "parks, park paths, courtyards, groves"),
        ("trees drawn over kept woods (existing)", "", n_old, "trees", "the kept woods' canopy, illustrative"),
    ] + [(f"ground cover: {n}", "", g.area, "m2", "parks, by distance rules") for n, g in covers.items()]
    with open(out / "areas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["measure", "required", "design", "difference", "unit", "source"])
        for name, req, des, unit, s in rows:
            diff = round(des - req) if req != "" else ""
            w.writerow([name, round(req) if req != "" else "", round(des), diff, unit, s])

    site_a = site.area
    sq_a = area_of(mass_squares)
    full = sealed.area + (0 if sq_part else sq_a)
    path_a = sum(g.length for g in paths + boardwalks) * cfg["path_width_m"]
    part = (sq_a if sq_part else 0) + play_a + path_a
    with open(out / "sealing.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["surface", "area_m2", "share_pct", "counted_as"])
        w.writerow(["buildings and streets", round(sealed.area), pct(sealed.area, site_a), "fully sealed"])
        w.writerow(["squares", round(sq_a), pct(sq_a, site_a), "partly sealed" if sq_part else "fully sealed"])
        w.writerow(["playgrounds", round(play_a), pct(play_a, site_a), "partly sealed"])
        w.writerow(["park paths", round(path_a), pct(path_a, site_a), "partly sealed"])
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
        tot = sum(drains.values()) or 1
        terrain_md = (f"- Terrain: {ter.source}, the ground as it is today (grading may change it). Each corridor's pools fill "
                      f"the low ground of each stretch between its dry crossings, each other park's hollow its lowest ground. "
                      f"The rain of new roofs, streets and squares runs downhill on a {cfg['flow_cell_m']} m grid to the first "
                      f"corridor its way enters within {cfg['corridor_catch_m']} m, else the first park: "
                      f"{pct(drains['downhill'], tot)} % gets there on the ground, {pct(drains['piped'], tot)} % runs off "
                      f"without meeting a park and is piped to the nearest lower one, {pct(drains['uphill'], tot)} % has no "
                      f"park below it (pump or soak away).\n" if ter else
                      "- No terrain model in the site folder (no terrain*.tif, no terrain.csv): rain is held in the nearest "
                      "park, not where it flows; levels must be checked.\n")
        terrain_md += "".join(f"- {n}\n" for n in ter_notes)
        f.write(f"\nGeneral:\n\n- `streets`: {streets_src}.\n{terrain_md}- Distances are straight lines, not walking routes.\n"
                "- The massing's courtyards are private gardens and are not counted as public green.\n"
                "- Trees: planted ones (`existing: false`) are design intent; those over the kept woods (`existing: true`) only "
                "show the kept canopy and are not planting. None stands on land the plan keeps open: greens whose roles are "
                f"{', '.join(cfg['treeless_roles'])}, and {', '.join(cfg['open_landuse'])} "
                + ("that the structure plan keeps.\n" if any("action" in p for p, _ in plan) else
                   "anywhere, since no structure plan says which fields change.\n"))

    src_md = Path(a.layers) / "SOURCES.md"
    cfg["map_credit"] = next((l.lstrip("> ").split(" (")[0].strip() for l in (src_md.read_text(encoding="utf-8").splitlines() if src_md.exists() else [])
                              if "©" in l), "")
    frame = plan_frame(out.resolve().parent) or ((*a.frame, a.centre, None) if a.frame else None)
    ctx = ([g for _, g in layer("buildings") if not g.intersects(site)], [g for _, g in layer("streets")]) if frame else None
    draw(out, site, buildings, old_bld, streets, kept_u, water, parks, playgrounds, basins, links, cfg, style, to_ll,
         covers, pools, paths, boardwalks, keep_free, trees, frame, ctx)
    print(json.dumps({"parks": len(parks), "park_m2": round(park_a), "need_green_m2": round(need_green),
                      "trees": {g: sum(1 for t in trees if t[1] == g) for g in sorted({t[1] for t in trees})},
                      "trees_planted": len(trees) - n_old,
                      "playgrounds": len(playgrounds), "play_m2": round(play_a), "need_play_m2": round(need_play),
                      "homes_unreached": unreached, "basins": len(basins), "retention_m3": round(held_vol),
                      "need_retention_m3": round(need_vol), "links": len(links),
                      "parks_unlinked": alone, "corridors": sum(1 for c in corridor if c),
                      "covers_m2": {n: round(g.area) for n, g in covers.items()},
                      "paths_m": round(sum(g.length for g in paths)),
                      "boardwalks_m": round(sum(g.length for g in boardwalks)),
                      "fully_sealed_pct": pct(full, site_a), "partly_sealed_pct": pct(part, site_a),
                      "verge_m2": round(verge.area), "terrain": ter.source if ter else None,
                      "rain_drains_pct": {k: pct(v, sum(drains.values())) for k, v in drains.items()} if ter else None},
                     indent=1, ensure_ascii=False))


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


def is_corridor(park, cfg):
    r = park.minimum_rotated_rectangle
    if r.geom_type != "Polygon":
        return False
    long = max(LineString(r.exterior.coords[i:i + 2]).length for i in range(2))
    return long >= cfg["corridor_min_length_m"] and park.area / long >= cfg["corridor_min_width_m"]


class Ground:
    """The terrain on grids whose cells sit on whole multiples of their size, so that neighbouring cells meet exactly."""

    def __init__(self, ter, cell):
        self.ter, self.cell = ter, cell

    def points(self, g, cell=None):
        """The centres of the cells inside g: xs, ys."""
        c = cell or self.cell
        if g.is_empty:
            return np.zeros(0), np.zeros(0)
        x0, y0, x1, y1 = g.bounds
        X, Y = np.meshgrid(np.arange(math.floor(x0 / c), math.ceil(x1 / c)) * c + c / 2,
                           np.arange(math.floor(y0 / c), math.ceil(y1 / c)) * c + c / 2)
        X, Y = X.ravel(), Y.ravel()
        inside = shapely.contains_xy(g, X, Y)
        return X[inside], Y[inside]

    def cells(self, g):
        """The cells inside g and their heights: xs, ys, z."""
        xs, ys = self.points(g)
        return xs, ys, self.ter.sample(xs, ys)

    def poly(self, xs, ys):
        """The cells around these centres, as one shape."""
        c = self.cell
        i, j = np.floor(xs / c), np.floor(ys / c)
        return shapely.coverage_union_all(shapely.box(i * c, j * c, (i + 1) * c, (j + 1) * c)).simplify(0)


def drainage(ground, area, parks, corridor, cfg):
    """Where the rain of each point runs: from cell to cell down the terrain to the first park its way enters.
    A priority flood from the grid's edge gives each cell the lowest neighbour it spills into, hollows included.
    Returns to_park(xs, ys) -> [(park index, 'downhill' | 'piped' | 'uphill')]."""
    c = cfg["flow_cell_m"]
    x0, y0, x1, y1 = area.bounds
    nx, ny = int(math.ceil((x1 - x0) / c)), int(math.ceil((y1 - y0) / c))
    X, Y = np.meshgrid(x0 + (np.arange(nx) + 0.5) * c, y0 + (np.arange(ny) + 0.5) * c)
    X, Y = X.ravel(), Y.ravel()
    Z = ground.ter.sample(X, Y)
    park_of = np.full(nx * ny, -1)
    for i, p in enumerate(parks):
        park_of[shapely.contains_xy(p, X, Y)] = i
    low = []
    for i, p in enumerate(parks):
        inside = park_of == i
        q = p.representative_point()
        low.append(float(Z[inside].min()) if inside.any() else float(ground.ter.sample([q.x], [q.y])[0]))
    zl, n = Z.tolist(), nx * ny
    seen, down, order = bytearray(n), [-1] * n, []
    heap = [(zl[k], k) for k in range(n) if k < nx or k >= n - nx or k % nx in (0, nx - 1)]
    for _, k in heap:
        seen[k] = 1
    heapq.heapify(heap)
    while heap:
        z, k = heapq.heappop(heap)
        order.append(k)
        r, q = divmod(k, nx)
        for dr in (-1, 0, 1):
            for dq in (-1, 0, 1):
                rr, qq = r + dr, q + dq
                if 0 <= rr < ny and 0 <= qq < nx:
                    nb = rr * nx + qq
                    if not seen[nb]:
                        seen[nb], down[nb] = 1, k
                        heapq.heappush(heap, (max(zl[nb], z), nb))
    # Down the drainage tree, from the edge up: the first park on each cell's way, and the first corridor and where.
    pk = park_of.tolist()
    first, corr, at = [-1] * n, [-1] * n, [-1] * n
    for k in order:
        d, p = down[k], pk[k]
        first[k] = p if p >= 0 else (first[d] if d >= 0 else -1)
        if p >= 0 and corridor[p]:
            corr[k], at[k] = p, k
        elif d >= 0:
            corr[k], at[k] = corr[d], at[d]

    def to_park(xs, ys):
        out = []
        ks = np.clip(((ys - y0) / c).astype(int), 0, ny - 1) * nx + np.clip(((xs - x0) / c).astype(int), 0, nx - 1)
        for k, x, y in zip(ks.tolist(), xs.tolist(), ys.tolist()):
            if corr[k] >= 0 and math.hypot(X[at[k]] - x, Y[at[k]] - y) <= cfg["corridor_catch_m"]:
                out.append((corr[k], "downhill"))
            elif first[k] >= 0:
                out.append((first[k], "downhill"))
            else:   # its way leaves the land without meeting a park: a pipe to the nearest park below it
                pt = Point(x, y)
                near = sorted(range(len(parks)), key=lambda j: parks[j].distance(pt))
                below = [j for j in near if low[j] < zl[k]]
                out.append((below[0], "piped") if below else (near[0], "uphill"))
        return out
    # Each park spills where its first cell in the flood order (its lowest rim) drains to: the next park downhill.
    spill = [-1] * len(parks)
    for k in order:
        if pk[k] >= 0 and spill[pk[k]] < 0:
            spill[pk[k]] = k
    next_park = [first[down[k]] if k >= 0 and down[k] >= 0 else -1 for k in spill]
    pos = {k: n_ for n_, k in enumerate(order)}
    upstream_first = sorted(range(len(parks)), key=lambda i: -pos.get(spill[i], -1))
    return argparse.Namespace(to_park=to_park, next_park=next_park, upstream_first=upstream_first)


def fill_low(ground, room, fits, cfg, max_area, min_piece=0.0, cut=None, axis=None, one=False):
    """The room's low ground filled as water rises, from the lowest cell up, while fits(shape) holds.
    With axis (centre, unit vector, start, spacing) each stretch between crossings fills from its own lowest cell;
    with one, only the piece at the lowest cell is kept, cut to max_area m² round it if the next level overshoots.
    Returns (shape or None, lowest point)."""
    xs, ys, z = ground.cells(room)
    if not len(z):
        return None, None
    if axis:
        (cx, cy), (ux, uy), start, every = axis
        seg = np.floor(((xs - cx) * ux + (ys - cy) * uy - start) / every).astype(int)
        seg -= seg.min()
        bottom = np.full(seg.max() + 1, np.inf)
        np.minimum.at(bottom, seg, z)
        rel = z - bottom[seg]
    else:
        rel = z - z.min()
    low_pt = Point(xs[np.argmin(z)], ys[np.argmin(z)])
    r = cfg["pool_round_m"]

    def make(t):
        sel = rel <= t
        if not sel.any():
            return shapely.Polygon()
        g = ground.poly(xs[sel], ys[sel]).buffer(r).buffer(-2 * r).buffer(r).intersection(room)
        if cut is not None:
            g = g.difference(cut)
        parts = [q for q in getattr(g, "geoms", [g]) if q.geom_type == "Polygon" and q.area >= max(min_piece, 1)]
        if one and parts:
            parts = [min(parts, key=lambda q: q.distance(low_pt))]
        return unary_union(parts) if parts else shapely.Polygon()

    # the search starts below the level whose cells cover 1.5 times the largest area, and rises if that still fits
    rs, lo = np.sort(rel), 0.0
    k = max(int(1.5 * max_area / ground.cell ** 2), 1)
    while True:
        hi = float(rs[min(k, len(rs) - 1)]) + 1e-6
        if k >= len(rs) - 1 or not fits(make(hi)):
            break
        lo, k = hi, k * 2
    if fits(make(hi)):
        lo = hi
    else:
        for _ in range(20):
            mid = (lo + hi) / 2
            if fits(make(mid)):
                lo = mid
            else:
                hi = mid
    g = make(lo)
    if one and g.area < 0.95 * max_area:
        cut_g = grow(low_pt, max_area, make(hi))
        if cut_g is not None and cut_g.area > g.area:
            g = cut_g
    return (None if g.is_empty else g), low_pt


def hollow(park, vol, cfg, avoid, ground, sealed):
    """One hollow holding vol: with terrain at the park's lowest ground, filled as water rises; without, round, on
    the side its rain comes from. Returns (shape or None, held m³)."""
    room = park.buffer(-3).difference(avoid)
    if room.is_empty:
        return None, 0.0
    size = min(vol / cfg["retention_depth_m"], park.area * cfg["retention_max_share"])
    g = None
    if ground:
        g, seed = fill_low(ground, room, lambda h: h.area <= size, cfg, size, one=True)
    else:
        seed = room.boundary.interpolate(room.boundary.project(nearest_sealed(park, sealed)))
    if g is None and seed is not None:
        g = grow(seed, size, room)
    return (g, g.area * cfg["retention_depth_m"]) if g is not None and not g.is_empty else (None, 0.0)


def pool_chain(park, vol, cfg, avoid, ground=None):
    """Pools that hold vol, cut by dry crossings: with terrain they fill the low ground of each stretch, without
    they are shrunk from the park's outline; returns (pools, deep, held)."""
    room = park.buffer(-8).difference(avoid)
    if room.is_empty:
        return None
    r = park.minimum_rotated_rectangle.exterior.coords
    ax = max([(r[i + 1][0] - r[i][0], r[i + 1][1] - r[i][1]) for i in range(2)], key=lambda v: math.hypot(*v))
    n = math.hypot(*ax)
    ux, uy = ax[0] / n, ax[1] / n
    c = park.centroid
    half = n / 2 + 50
    cuts = unary_union([LineString([(c.x + t * ux - uy * half, c.y + t * uy + ux * half),
                                    (c.x + t * ux + uy * half, c.y + t * uy - ux * half)])
                        for t in np.arange(-half, half, cfg["pool_crossing_every_m"])]).buffer(cfg["pool_crossing_width_m"] / 2)
    cap = park.area * cfg["corridor_retention_max_share"]

    def held_of(g):
        deep = g.buffer(-cfg["pool_shallow_band_m"])
        return deep, (g.area - deep.area) * cfg["pool_shallow_m"] + deep.area * cfg["pool_deep_m"]

    if ground:
        g, _ = fill_low(ground, room, lambda q: q.area <= cap and held_of(q)[1] <= vol, cfg, cap, 150, cuts,
                        ((c.x, c.y), (ux, uy), -half, cfg["pool_crossing_every_m"]))
        return (g, *held_of(g)) if g is not None else None

    def make(d):
        g = room.buffer(-d - 15).buffer(15).difference(cuts)  # rounded, as water settles
        g = unary_union([q for q in getattr(g, "geoms", [g]) if q.area >= 150])
        deep = g.buffer(-cfg["pool_shallow_band_m"])
        return g, deep, (g.area - deep.area) * cfg["pool_shallow_m"] + deep.area * cfg["pool_deep_m"]

    lo, hi = 0.0, max(math.sqrt(room.area), 1)
    for _ in range(30):
        mid = (lo + hi) / 2
        g, _, held = make(mid)
        if held > vol or g.area > cap:
            lo = mid
        else:
            hi = mid
    g, deep, held = make(hi)
    return (g, deep, held) if not g.is_empty else None


def plant(cfg, kept, covers, paths, courts, sealed, no_crown, no_trunk):
    """Canopy over the kept woods, avenues along the park paths, trees in the courtyards, groves on the grove ground and
    loose clusters in the parks, in this order; a tree stands at least half its crown from those before it.
    Returns [(point, group, crown_m, height_m, existing)]."""
    rng = np.random.default_rng(cfg["tree_seed"])
    shapely.prepare(no_crown)
    shapely.prepare(no_trunk)
    out, near = [], {}

    def put(xs, ys, group, crown, height, existing=False):
        xs, ys = np.asarray(xs, float), np.asarray(ys, float)
        if not len(xs):
            return
        ok = ~shapely.dwithin(no_crown, shapely.points(xs, ys), crown / 2) & ~shapely.contains_xy(no_trunk, xs, ys)
        n = math.ceil(crown / 20)
        for x, y in zip(xs[ok].tolist(), ys[ok].tolist()):
            i, j = int(x // 10), int(y // 10)
            if any(math.hypot(x - u, y - v) < crown / 2 for di in range(-n, n + 1) for dj in range(-n, n + 1)
                   for u, v in near.get((i + di, j + dj), ())):
                continue
            near.setdefault((i, j), []).append((x, y))
            out.append((Point(x, y), group, crown, height, existing))

    for lu, g in kept:
        if lu in cfg["canopy_landuse"]:
            group, crown, height = cfg["canopy_landuse"][lu]
            put(*scatter(g.difference(sealed), 0.8 * crown, rng, 0.3 if group == "wood" else 0), group, crown, height, existing=True)
    crown, height, step = cfg["tree_sizes"]["avenue"]
    for ln in [q for g in paths for q in getattr(g, "geoms", [g])]:
        for side in (-1, 1):
            off = shapely.offset_curve(ln, side * cfg["avenue_offset_m"])
            for q in getattr(off, "geoms", [off]):
                pts = [q.interpolate(d) for d in np.arange(step / 2, q.length, step)]
                put([p.x for p in pts], [p.y for p in pts], "avenue", crown, height)
    crown, height, step = cfg["tree_sizes"]["courtyard"]
    for c in courts:
        inner = c.buffer(-crown / 2 - 1)
        xs, ys = scatter(inner, step, rng, 0.15)
        if not len(xs) and not inner.is_empty:
            q = inner.representative_point()
            xs, ys = [q.x], [q.y]
        put(xs, ys, "courtyard", crown, height)
    crown, height, step = cfg["tree_sizes"]["grove"]
    put(*scatter(covers["grove"], step, rng), "grove", crown, height)
    crown, height, step = cfg["tree_sizes"]["park"]
    ground = unary_union([covers[n] for n in ("lawn", "meadow", "wet-meadow")])
    for x, y in zip(*scatter(ground, cfg["cluster_every_m"], rng, 0.4)):
        k = int(rng.integers(1, 6))
        ang = rng.uniform(0, 2 * math.pi) + np.arange(k - 1) * 2 * math.pi / max(k - 1, 1)
        xs, ys = np.array([x, *(x + step * np.cos(ang))]), np.array([y, *(y + step * np.sin(ang))])
        inside = shapely.contains_xy(ground, xs, ys)
        put(xs[inside], ys[inside], "park", crown, height)
    return out


def scatter(area, step, rng, jitter=0.3):
    """Points about step apart inside area, on a jittered triangular grid: xs, ys."""
    if area.is_empty:
        return np.zeros(0), np.zeros(0)
    x0, y0, x1, y1 = area.bounds
    X, Y = np.meshgrid(np.arange(x0, x1 + step, step), np.arange(y0, y1 + step, step * 0.87))
    X = (X + (np.arange(X.shape[0])[:, None] % 2) * step / 2).ravel() + rng.uniform(-jitter, jitter, X.size) * step
    Y = Y.ravel() + rng.uniform(-jitter, jitter, Y.size) * step
    inside = shapely.contains_xy(area, X, Y)
    return X[inside], Y[inside]


def nearest_sealed(park, sealed):
    """The point of the park nearest to the sealed land, where its rain arrives."""
    if sealed.is_empty:
        return park.centroid
    return Point(shortest_line(park, sealed).coords[0])


def plan_frame(proposal):
    """(w, h mm, centre [lon, lat] or None, scale or None) of this plan's frame in the panels' plan, else None."""
    p = next((q for q in (proposal / "panel-layout" / n for n in ("layout-plan.json", "layout.json")) if q.exists()), None)
    for it in [it for q in (load_json(p).get("panels", []) if p else []) for it in q.get("items", [])]:
        fr, m = it.get("frame") or {}, re.search(r"1\s*:\s*([\d,. ]+)", str(it.get("scale") or ""))
        if str(it.get("file") or "").replace("\\", "/").startswith("open-space/") and fr.get("w") and fr.get("h"):
            return float(fr["w"]), float(fr["h"]), fr.get("centre"), int(re.sub(r"\D", "", m.group(1))) if m else None


def draw(out, site, buildings, old_bld, streets, kept, water, parks, playgrounds, basins, links, cfg, s, to_ll,
         covers, pools, paths, boardwalks, keep_free, trees=(), frame=None, ctx=None):
    scale = (frame and frame[3]) or cfg["scale"]
    k = scale / 1000  # metres per mm
    if frame:   # the frame's size at its scale, around its centre, else the site's; the legend inside it
        c = Point(to_ll.transform(*frame[2], direction="INVERSE")) if frame[2] else shapely.box(*site.bounds).centroid
        x0, y0, x1, y1 = c.x - frame[0] * k / 2, c.y - frame[1] * k / 2, c.x + frame[0] * k / 2, c.y + frame[1] * k / 2
    else:
        x0, y0, x1, y1 = site.buffer(80).bounds
    wmm = (x1 - x0) / k
    head = 0 if frame else 40 * k  # 40 mm for the legend, in metres
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

    lw = lambda mm: f"{mm * k:.2f}"
    els = []

    def shape_el(g, fill, stroke="none", w=0.0, extra=""):
        if g is None or g.is_empty:
            return
        els.append(f'<path d="{path(g)}" fill="{fill}" stroke="{stroke}" stroke-width="{lw(w)}" fill-rule="evenodd" {extra}/>')

    if ctx:   # in a frame, the city around the site, pale, as the other thematic plans draw it
        win = shapely.box(x0, y0, x1, y1)
        shape_el(unary_union(ctx[1]).intersection(win).difference(site), "none", s["context"], s["line"])
        shape_el(unary_union(ctx[0]).intersection(win), s["context"])
    shape_el(streets, s["street"], s["ink"], s["line"] / 2)
    shape_el(unary_union(parks) if parks else None, s["park"])
    for name, g in covers.items():
        shape_el(g, s[name])
    shape_el(kept, s["kept"])
    shape_el(unary_union(water) if water else None, s["water"])
    for g, *_ in basins:
        shape_el(g, s["accent"], extra='fill-opacity="0.35"')
    for _, deep in pools:
        shape_el(deep, s["accent"], extra='fill-opacity="0.5"')
    for g in paths:
        shape_el(g, "none", s["path"], cfg["path_width_m"] / k, extra='stroke-linejoin="round"')
    for g in boardwalks:
        shape_el(g, "none", s["ink"], cfg["path_width_m"] / k)
    for g in playgrounds:
        shape_el(g, "none", s["accent"], s["outline"], extra=f'stroke-dasharray="{lw(1)} {lw(0.6)}"')
    tree_fill = s["grove"]   # a standard's `tree` may be a symbol, not a colour
    for pt, _, crown, *_ in trees:
        els.append(f'<circle cx="{pt.x - x0:.1f}" cy="{y1 - pt.y:.1f}" r="{crown / 2:.1f}" fill="{tree_fill}" '
                   f'fill-opacity="0.8" stroke="{s["ink"]}" stroke-width="{lw(s["line"] / 2)}"/>')
    shape_el(unary_union(old_bld).intersection(site.buffer(80)) if old_bld else None, s["existing"], s["ink"], s["line"])
    shape_el(buildings.difference(unary_union(old_bld)) if old_bld else buildings, s["building"], s["ink"], s["line"])
    for g, _ in links:
        shape_el(g, "none", s["accent"], s["outline"] * 1.5, extra=f'stroke-dasharray="{lw(2)} {lw(1.2)}"')
    shape_el(keep_free, "none", s["ink"], s["line"], extra=f'stroke-dasharray="{lw(0.6)} {lw(0.6)}"')
    shape_el(site.boundary, "none", s["ink"], s["outline"], extra=f'stroke-dasharray="{lw(3)} {lw(1.5)}"')

    fs = max(3.2, s["text"]) * k
    legend = [("lawn", s["lawn"], ""), ("meadow", s["meadow"], ""), ("wet meadow", s["wet-meadow"], ""),
              ("grove", s["grove"], ""), ("kept green", s["kept"], ""), ("water", s["water"], ""),
              ("retention, shallow", s["accent"], 'fill-opacity="0.35"'),
              ("deep core", s["accent"], 'fill-opacity="0.68"'), ("playground", "none", ""),
              ("green link", None, "")] + ([("kept free", "none", "")] if not keep_free.is_empty else []) \
        + ([("tree", tree_fill, "")] if trees else [])
    credit = textwrap.wrap(cfg.get("map_credit", ""), 32) if frame else []
    if frame:   # a box in the corner where it hides least of the site: the title, one entry a row, the scale, the credit
        bw, bh = 66 * k, (s["title"] + 18 + 5.5 * len(legend) + 4.5 * len(credit)) * k
        bx, by = min(((a_, b_) for b_ in (y0, y1 - bh) for a_ in (x0, x1 - bw)),
                     key=lambda c_: shapely.box(c_[0], c_[1], c_[0] + bw, c_[1] + bh).intersection(site).area)
        lx, ly = bx - x0 + 4 * k, y1 - by - bh + (s["title"] + 7) * k
        els.append(f'<rect x="{bx - x0:.1f}" y="{y1 - by - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{s["paper"]}"/>'
                   f'<text x="{lx:.1f}" y="{y1 - by - bh + (s["title"] + 3) * k:.1f}" font-size="{max(fs, s["title"] * k):.1f}" '
                   f'font-weight="bold" font-family="{s["font"]}">Open space, 1:{scale:,}</text>')
    else:
        lx, ly = 6 * k, (y1 - y0) + 8 * k
    for name, fill, extra in legend:
        if fill is None:
            els.append(f'<line x1="{lx}" y1="{ly + 2 * k}" x2="{lx + 8 * k}" y2="{ly + 2 * k}" stroke="{s["accent"]}" '
                       f'stroke-width="{lw(s["outline"] * 1.5)}" stroke-dasharray="{lw(2)} {lw(1.2)}"/>')
        else:
            st = s["accent"] if name == "playground" else s["ink"]
            els.append(f'<rect x="{lx}" y="{ly}" width="{8 * k}" height="{4 * k}" fill="{fill}" {extra} '
                       f'stroke="{st}" stroke-width="{lw(s["line"])}"/>')
        els.append(f'<text x="{lx + 10 * k}" y="{ly + 3.3 * k}" font-size="{fs}" font-family="{s["font"]}">{name}</text>')
        lx, ly = (lx, ly + 5.5 * k) if frame else (lx + (14 + len(name) * 1.9) * k, ly)
    # graphic scale: a thin line stepping up and down, a tick at every step, the numbers under, the unit on the last
    bar = min((b for b in (50, 100, 200, 250, 500, 1000, 2000) if b >= (bw / 3 if frame else (x1 - x0) / 6)), default=1000)
    sx, sy, sg = (lx if frame else 6 * k), ly + (2 if frame else 14) * k, bar / 4
    els.append(f'<path d="{"".join(f"M{sx + i * sg:.1f},{sy + 1.5 * k * (i % 2):.1f}h{sg:.1f}" for i in range(4))}'
               f'{"".join(f"M{sx + i * sg:.1f},{sy:.1f}v{1.5 * k:.1f}" for i in range(5))}" fill="none" stroke="{s["ink"]}" stroke-width="{lw(s["line"])}"/>')
    for v, t in ((0, "0"), (bar, f"{bar} m")):
        els.append(f'<text x="{sx + v:.1f}" y="{sy + 1.5 * k + fs + 0.5 * k:.1f}" font-size="{fs}" font-family="{s["font"]}" text-anchor="middle">{t}</text>')
    nx, ny = sx + bar + 12 * k, sy + 1 * k   # north: a circle in outline, a line from its centre to the circle, pointing north
    els.append(f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="{3 * k:.1f}" fill="none" stroke="{s["ink"]}" stroke-width="{lw(s["line"])}"/>'
               f'<line x1="{nx:.1f}" y1="{ny:.1f}" x2="{nx:.1f}" y2="{ny - 3 * k:.1f}" stroke="{s["ink"]}" stroke-width="{lw(s["line"])}"/>')
    for i, t in enumerate(credit or [f'1:{scale:,}   {cfg.get("map_credit", "")}']):
        els.append(f'<text x="{sx if frame else nx + 6 * k:.1f}" y="{(sy + (10.5 + 4.5 * i) * k) if frame else ny + 1 * k:.1f}" '
                   f'font-size="{fs}" font-family="{s["font"]}">{t}</text>')

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
