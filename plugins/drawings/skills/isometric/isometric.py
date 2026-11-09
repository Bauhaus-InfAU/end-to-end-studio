"""Isometric of an urban design, or of the site as it is when there is no design yet.

python3 isometric.py <site folder> <proposal folder> <scale> <panel width mm> [--style style.json]
                     [--close 1000] [--close-frame W H] [--centre NAME]

Reads <site folder>/site.geojson and its layers (buildings, plots, streets, water, rail), and in <proposal folder>
massing/massing.geojson, open-space/open-space.geojson's trees and structure-plan/structure-plan.geojson's centres if
they exist. Writes into <proposal folder>/isometric/: the district at <scale>, never a smaller one (the panels crop it),
isometric_1-<scale>.svg and .png; with a design also its main centre close up at --close (1:1,000 to 1:1,500) in
--close-frame mm (else the panel's width by 0.6 of it), isometric_centre_1-<close>.svg and .png, with use labels,
people and roofs; and summary.md.
--centre: the centre or square to close in on, by its name; else the structure plan's main centre, else the largest square.
--style: the drawing standard's style.json, its keys mapped onto STYLE below.
Needs shapely and pyproj; the PNG needs a headless Chrome, Chromium or Edge.
"""
import argparse, json, math, os, random, re, shutil, subprocess, sys
from shapely.geometry import shape, Point, Polygon, LineString, box
from shapely.ops import unary_union, transform
from shapely.prepared import prep
from shapely import affinity
from pyproj import Transformer

ap = argparse.ArgumentParser()
ap.add_argument("site"); ap.add_argument("proposal")
ap.add_argument("scale", type=int, help="its frame's scale, else the brief's site plan scale, e.g. 3000")
ap.add_argument("panel_mm", type=float, help="width of the brief's panel in mm, the close view's width without --close-frame")
ap.add_argument("--style")
ap.add_argument("--close", type=int, default=1000, help="the close view's scale, 1000 to 1500")
ap.add_argument("--close-frame", type=float, nargs=2, metavar=("W", "H"), help="the close view's frame in mm")
ap.add_argument("--centre", help="the centre or square to close in on, by its name")
a = ap.parse_args()
out_dir = os.path.join(a.proposal, "isometric"); os.makedirs(out_dir, exist_ok=True)

# fallback look: black on white, white buildings with shaded walls, the accent's pale tone on the squares.
STYLE = {"accent": "#d9302b", "new_wall": "#ececec", "new_wall_shade": "#cfcfcf", "new_roof": "#ffffff",
         "new_line": "#1a1a1a", "floor_line": "#a8a8a8", "existing_line": "#c2c2c2", "existing_fill": "#ffffff",
         "ground": "#ffffff", "field": "#f4f4f1", "field_line": "#dcdcd6", "design_green": "#fafaf8",
         "design_green_hatch": "#cfcfc7", "water": "#e3e7e9", "water_line": "#9aa3a8", "street": "#fafaf8",
         "street_line": "#a0a0a0", "rail": "#444444", "tree": "#9a9a9a", "text": "#1a1a1a", "public": "#f0b8b5",
         "shadow": "#a8a8a8", "roof_green": "#e1e8d8", "font": "Arial, Helvetica, sans-serif", "label_mm": 3.2}
TREE_H, TREE_CROWN = 10.0, 6.0   # height and crown diameter of a tree without height_m or crown_m, metres
PITCH = 30.0                     # assumed pitch of a gable roof, degrees
PEOPLE_M2 = (60.0, 400.0)        # one person per this many m2 of square and of street, illustrative
mix = lambda c1, c2, t: "#%02x%02x%02x" % tuple(round(int(c1[i:i + 2], 16) * (1 - t) + int(c2[i:i + 2], 16) * t) for i in (1, 3, 5))
used_standard = False
if a.style and os.path.exists(a.style):
    s = json.load(open(a.style)); used_standard = True
    # the standard's keys mapped onto this drawing's, never merged: its `text` is a size, its `field` another layer
    nw, sh = s.get("new", STYLE["new_roof"]), s.get("shadow", STYLE["floor_line"])
    STYLE.update({k: v for k, v in {
        "accent": s.get("accent"), "public": s.get("public"), "new_roof": nw, "new_wall": mix(nw, sh, 0.25),
        "new_wall_shade": mix(nw, sh, 0.6), "new_line": s.get("ink"), "floor_line": sh, "existing_line": s.get("existing"),
        "existing_fill": s.get("paper"), "ground": s.get("paper"), "design_green": s.get("park"), "design_green_hatch": s.get("grove"),
        "water": s.get("water"), "street": s.get("street"), "street_line": s.get("path"), "rail": s.get("ink"),
        "tree": s.get("grove"), "text": s.get("ink"), "shadow": s.get("shadow"), "roof_green": s.get("lawn"),
        "font": s.get("font"), "label_mm": s.get("text") if isinstance(s.get("text"), (int, float)) else None}.items() if v})
STYLE["pv"] = mix(STYLE["new_line"], STYLE["new_roof"], 0.55)

summary = os.path.join(out_dir, "summary.md")
def load(path):
    return json.load(open(path))["features"] if os.path.exists(path) else []

site_path = os.path.join(a.site, "site.geojson")
if not os.path.exists(site_path):
    open(summary, "w").write(
        "- Nothing drawn: there is no site folder with a `site.geojson`.\n"
        "- Needed: the site outline (`site.geojson`) and next to it its buildings (with heights), streets, water, green (plots) and rail.\n"
        "- Make them (for example with a site-data skill) and run again.\n")
    print("no site.geojson in", a.site); sys.exit(1)

site_ll = shape(load(site_path)[0]["geometry"])
c = site_ll.centroid
epsg = (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1
tr = Transformer.from_crs(4326, epsg, always_xy=True).transform
site = transform(tr, site_ll)

mass = load(os.path.join(a.proposal, "massing", "massing.geojson"))
trees = [f for f in mass + load(os.path.join(a.proposal, "open-space", "open-space.geojson"))   # street trees, and open-space's
         if (f.get("properties") or {}).get("kind") == "tree" and f.get("geometry")]
new = [(f["properties"], transform(tr, shape(f["geometry"]))) for f in mass
       if f["properties"].get("kind") == "building" and not f["properties"].get("existing")]
focus = unary_union([g for _, g in new]) if new else site
MARGIN = 100 if new else 200
area = box(*focus.buffer(MARGIN * 3).bounds)

# the centre to close in on: by name, else the structure plan's main centre, else the largest square
squares = [(f["properties"], transform(tr, shape(f["geometry"]))) for f in mass
           if f["properties"].get("kind") == "open-space" and f["properties"].get("use") == "square"]
centres = [(f["properties"], transform(tr, shape(f["geometry"])))
           for f in load(os.path.join(a.proposal, "structure-plan", "structure-plan.geojson"))
           if (f.get("properties") or {}).get("kind") == "centre" and f.get("geometry")]
main = ([(p, g) for p, g in centres + squares if a.centre and p.get("name") == a.centre]
        or [(p, g) for p, g in centres if p.get("level") == "main"] or sorted(squares, key=lambda s: -s[1].area))[:1]

def layer(name):
    for f in load(os.path.join(a.site, name + ".geojson")):
        g = transform(tr, shape(f["geometry"]))
        if g.intersects(area): yield f["properties"], g

existing = list(layer("buildings"))
if new:
    newu = unary_union([g for _, g in new]).buffer(0)
    existing = [(p, g) for p, g in existing if not g.buffer(0).intersects(newu)]
# what the design does with each existing building (massing's status: kept, changed, removed); outside the site: city
STATUS = [(f["properties"].get("status") or "kept", transform(tr, shape(f["geometry"]))) for f in mass
          if f["properties"].get("kind") == "removed-building" or (f["properties"].get("kind") == "building" and f["properties"].get("existing"))]
def status_of(g):
    if not site.contains(g.representative_point()): return "city"
    return next((s for s, k in STATUS if k.contains(g.representative_point())), "kept")   # its own footprint, not a neighbour's it touches
existing = [({**p, "_status": status_of(g)}, g) for p, g in existing]

# view: the side with the least built volume standing in front of the focus
best = None
for az in (225, 135, 45, 315):
    vx, vy = math.cos(math.radians(az)), math.sin(math.radians(az))
    band, c0 = focus.buffer(MARGIN), focus.centroid
    hid = sum(g.area * float(p.get("height") or 3) for p, g in existing
              if band.contains(g.centroid) and not focus.contains(g.centroid)
              and (g.centroid.x - c0.x) * vx + (g.centroid.y - c0.y) * vy > 0)
    if best is None or hid < best[1]: best = (az, hid)
AZ = best[0]; ROT = 225 - AZ; O = focus.centroid
SIDE = {225: "south-west", 135: "south-east", 45: "north-east", 315: "north-west"}[AZ]
rot = lambda g: affinity.translate(affinity.rotate(g, ROT, origin=O), -O.x, -O.y)   # turned, about the origin: small numbers draw sharp
C30 = math.cos(math.radians(30))
iso = lambda x, y, z=0.0: ((x - y) * C30, -((x + y) * 0.5 + z))   # 1 unit = 1 m, true along the axes
plan = lambda sx, sy: ((sx / C30 - 2 * sy) / 2, (-2 * sy - sx / C30) / 2)   # a point of the view back onto the ground
ring_d = lambda cs, z=0.0: "M" + "L".join("%.1f,%.1f" % iso(x, y, z) for x, y in cs) + "Z"
def poly_d(g, z=0.0):
    return "".join(ring_d(p.exterior.coords, z) + "".join(ring_d(i.coords, z) for i in p.interiors)
                   for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and not p.is_empty)
def line_d(g, z=0.0):
    return "".join("M" + "L".join("%.1f,%.1f" % iso(x, y, z) for x, y in l.coords)
                   for l in getattr(g, "geoms", [g]) if not l.is_empty and l.geom_type == "LineString")

# the district at its frame's scale, never a smaller one: the panels crop it
top = max([float(p.get("height_m") or 0) for p, _ in new] or [0])
pts = [iso(x, y, z) for p in getattr(rot(focus), "geoms", [rot(focus)]) for x, y in p.exterior.coords for z in (0, top)]
xs, ys = zip(*pts)
fx0, fy0, fx1, fy1 = min(xs) - MARGIN, min(ys) - MARGIN, max(xs) + MARGIN, max(ys) + MARGIN
W, H = fx1 - fx0, fy1 - fy0
scale = a.scale
frame = box(fx0, fy0, fx1, fy1)
def in_frame(g, fr, h=0.0):   # g's footprint, raised by its height h, reaches into the view's frame fr
    q = Point(iso(g.x, g.y)).bounds if g.geom_type == "Point" else Polygon([iso(x, y) for x, y in g.exterior.coords]).bounds
    return fr.intersects(box(q[0], q[1] - h, q[2], q[3]))

S = STYLE
GREEN = {"grass", "meadow", "leisure:park", "forest", "natural:wood", "natural:scrub", "farmland", "allotments",
         "leisure:pitch", "leisure:playground", "leisure:sports_centre", "park", "garden", "wood", "scrub"}
plots = [rot(g) for p, g in layer("plots") if p.get("landuse") in GREEN]
waters = [rot(g) for p, g in layer("water")]
opens = [(f["properties"], rot(transform(tr, shape(f["geometry"])))) for f in mass if f["properties"].get("kind") == "open-space"]

# streets as surfaces: the streets skill's surface when it exists, else the massing's widths, else assumed by class
streets_path = os.path.join(a.proposal, "streets", "streets.geojson")
street_feats = load(streets_path)   # the streets skill's surface, when it exists
WIDTH = {"motorway": 28, "trunk": 22, "trunk_link": 9, "primary": 18, "secondary": 15, "tertiary": 13,
         "tertiary_link": 8, "residential": 10, "unclassified": 8, "living_street": 7, "service": 5,
         "pedestrian": 6, "track": 3.5, "cycleway": 3, "footway": 2.5, "path": 2, "steps": 2}
surf, assumed, paths = [], set(), []
if street_feats:
    for f in street_feats:
        p, g = f["properties"], rot(transform(tr, shape(f["geometry"])))
        if p.get("kind") == "street" and g.geom_type.endswith("Polygon"): surf.append(g)
        elif p.get("kind") == "path": paths.append(g)
else:
    for p, g in layer("streets"):
        w = None
        try: w = float(p.get("width")) if p.get("width") else float(p.get("lanes")) * 3.25 + 4
        except (TypeError, ValueError): pass
        if w is None:
            w = WIDTH.get(p.get("highway"), 6); assumed.add(p.get("highway"))
        surf.append(rot(g).buffer(w / 2, cap_style=2, join_style=2))
    for f in mass:
        p = f["properties"]
        if p.get("kind") == "street":
            g = rot(transform(tr, shape(f["geometry"])))
            surf.append(g if g.geom_type.endswith("Polygon") else g.buffer(float(p.get("width") or 16) / 2, cap_style=2))
street_u = unary_union(surf) if surf else None
rails = [rot(g) for p, g in layer("rail")]
GROUND_TEXT = lambda x, y, z=0.0: "matrix(%.4f,-0.5,%.4f,0.5,%.1f,%.1f)" % (C30, C30, *iso(x, y, z))   # text lying flat, along the view's x
def label(txt, fs, tf, halo=None, anchor="middle"):
    return ('<text transform="%s" font-family="%s" font-size="%.1f" text-anchor="%s" fill="%s"%s>%s</text>'
            % (tf, S["font"].replace('"', "'"), fs, anchor, S["text"],
               ' stroke="%s" stroke-width="%.1f" paint-order="stroke"' % (halo, fs * 0.25) if halo else "",
               str(txt).replace("&", "&amp;").replace("<", "&lt;")))

def ground(clip=None, fs=0.0):
    """The ground layers, cut to clip (view-turned metres) when given; with fs, the squares' names on the ground."""
    cut = (lambda g: (g.buffer(0) if g.geom_type.endswith("Polygon") else g).intersection(clip)) if clip is not None else (lambda g: g)
    out = []
    for g in plots:
        out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.4"/>' % (poly_d(cut(g)), S["field"], S["field_line"]))
    for g in waters:
        out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.5"/>' % (poly_d(cut(g)), S["water"], S["water_line"]))
    for p, g in opens:
        fill = {"water": S["water"], "square": S["public"]}.get(p.get("use"), "url(#hatch)")
        out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.4"/>' % (poly_d(cut(g)), fill, S["field_line"]))
    if street_u is not None:
        out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.5" fill-rule="evenodd"/>'
                   % (poly_d(cut(street_u)), S["street"], S["street_line"]))
    for g in paths:
        if g.geom_type.endswith("Polygon"):
            out.append('<path d="%s" fill="%s" stroke="none"/>' % (poly_d(cut(g)), S["street"]))
        else:
            out.append('<path d="%s" fill="none" stroke="%s" stroke-width="0.4"/>' % (line_d(cut(g)), S["street_line"]))
    for g in rails:
        for off in (-2.2, -0.8, 0.8, 2.2):
            try: out.append('<path d="%s" fill="none" stroke="%s" stroke-width="0.45"/>' % (line_d(cut(g.parallel_offset(off, "left"))), S["rail"]))
            except Exception: pass
    if not new:
        out.append('<path d="%s" fill="none" stroke="%s" stroke-width="2.4" stroke-dasharray="10 4"/>' % (poly_d(rot(site)), S["accent"]))
    for p, g in opens if fs else []:   # the squares' own names, from the massing
        q = g.representative_point()
        if p.get("use") == "square" and (p.get("name") or p.get("type")) and (clip is None or clip.contains(q)):
            out.append(label(p.get("name") or p.get("type"), fs, GROUND_TEXT(q.x, q.y), S["public"]))
    return [o for o in out if 'd=""' not in o]

# buildings and the trees, far to near
items, defaults = [], 0
for p, g in existing:
    for q in getattr(rot(g), "geoms", [rot(g)]):
        if q.geom_type == "Polygon" and in_frame(q, frame):
            items.append((q.centroid.x + q.centroid.y, "e", q, float(p.get("height") or 3), 0, None, p))
            defaults += p.get("height_source") == "default"
for p, g in new:
    fl = int(p.get("floors") or 1); h = float(p.get("height_m") or 3 * fl)
    for q in getattr(rot(g), "geoms", [rot(g)]):
        if q.geom_type == "Polygon": items.append((q.centroid.x + q.centroid.y, "n", q, h, fl, p.get("roof"), p))
for f in trees:   # at every scale; a tree's crown radius rides in the roof's place
    t, p = rot(transform(tr, shape(f["geometry"]))), f["properties"]
    if t.geom_type == "Point" and in_frame(t, frame):
        items.append((t.x + t.y, "t", t, float(p.get("height_m") or TREE_H), 0, float(p.get("crown_m") or TREE_CROWN) / 2, p))
items.sort(key=lambda i: -i[0])

def use_label(p):
    """The use a new building's label names, from the massing, and whether it is illustrative (a ground floor's use
    the massing allots inside a building of another use); None for homes."""
    u = re.sub(r"\s*\d+$", "", str(p.get("use") or ""))   # "daycare 1": the daycare
    note = re.split(r"[,(]", str(p.get("note") or ""))[0].strip()   # a use the brief asks for, which the massing notes
    if note and len(note) <= 30: return note, False
    gf = p.get("ground_floor") or u
    if gf in ("", "housing", "residential", "undefined", "None"): return None
    return gf, gf != u

def gable(g):
    """The corners of the rectangle a gable roof sits on, the long side first, or None if the footprint isn't one."""
    r = g.minimum_rotated_rectangle
    if g.interiors or r.geom_type != "Polygon" or r.area > g.area * 1.08: return None
    cs = list(r.exterior.coords)[:4]
    if not Polygon(cs).exterior.is_ccw: cs = cs[::-1]
    return cs if math.dist(cs[0], cs[1]) >= math.dist(cs[1], cs[2]) else cs[1:] + cs[:1]

def face(pts, fill, line, w=0.4):
    return '<path d="M%s Z" fill="%s" stroke="%s" stroke-width="%.2f" stroke-linejoin="round"/>' % (
        " L".join("%.1f,%.1f" % iso(*v) for v in pts), fill, line, w)

def paint(items, large, labels, fs):
    """The items far to near: trees, people, buildings with their walls, roofs and (large) floor lines and labels."""
    out = []
    for _, k, g, h, fl, roof, p in items:
        if k == "t":   # its soft shadow on the ground, the trunk, the crown at the top of its height
            r, dark = roof, mix(S["tree"], S["new_line"], 0.3); cx, cy = iso(g.x, g.y, h - r); gx, gy = iso(g.x, g.y)
            rnd = random.Random("%.0f,%.0f" % (g.x, g.y))   # each tree its own tone and outline, the same every run
            fill = [S["tree"], mix(S["tree"], S["new_line"], 0.18), mix(S["tree"], S["ground"], 0.25)][rnd.randrange(3)]
            out.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" fill-opacity="0.5"/>'
                       '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="0.35"/>'
                       % (gx + 0.4 * r, gy, 1.22 * r, 0.71 * r, S["shadow"], gx, gy, cx, cy + r, dark))
            if large:   # close: a scalloped crown, its side away from the light a shade darker
                n, rot0 = max(7, min(12, round(r * 1.4))), rnd.uniform(0, 2 * math.pi)
                pts = [(cx + rr * math.cos(t), cy + rr * math.sin(t)) for i in range(n)
                       for t, rr in [(rot0 + 2 * math.pi * i / n, r * rnd.uniform(0.86, 1.0))]]
                arcs = "".join(" A%.2f,%.2f 0 0 1 %.2f,%.2f" % (0.62 * math.dist(p, q), 0.62 * math.dist(p, q), *q)
                               for p, q in zip(pts, pts[1:] + pts[:1]))
                out.append('<path d="M%.2f,%.2f%sZ" fill="%s" stroke="%s" stroke-width="0.3" stroke-linejoin="round"/>'
                           '<path d="M%.2f,%.2f A%.2f,%.2f 0 0 0 %.2f,%.2f A%.2f,%.2f 0 0 1 %.2f,%.2f Z" fill="%s" fill-opacity="0.35"/>'
                           % (*pts[0], arcs, fill, dark, cx + 0.8 * r, cy - 0.45 * r, 0.92 * r, 0.92 * r, cx - 0.45 * r, cy + 0.8 * r,
                              1.1 * r, 1.1 * r, cx + 0.8 * r, cy - 0.45 * r, dark))
            else:
                out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity="0.9" stroke="%s" stroke-width="0.35"/>'
                           % (cx, cy, r, fill, dark))
            continue
        if k == "p":   # a person, illustrative: a body and a head, 1.75 m
            (bx, by), (tx, ty), (hx, hy) = iso(g.x, g.y, 0.1), iso(g.x, g.y, 1.2), iso(g.x, g.y, 1.5)
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.2f" stroke="%s" stroke-width="0.55" stroke-linecap="round"/>'
                       '<circle cx="%.1f" cy="%.2f" r="0.27" fill="%s"/>' % (bx, by, tx, ty, S["text"], hx, hy, S["text"]))
            continue
        st = (p or {}).get("_status", "kept")
        if k == "n": wall, top_, line = S["new_wall"], S["new_roof"], S["new_line"]
        elif st == "removed":   # only its footprint, dashed
            out.append('<path d="%s" fill="none" stroke="%s" stroke-width="0.5" stroke-dasharray="2 1.5"/>'
                       % (ring_d(list(g.exterior.coords)), S["existing_line"]))
            continue
        elif st == "changed":   # taken into the design: darker than kept, lighter than new's outline
            wall = top_ = mix(S["existing_fill"], S["existing_line"], 0.6); line = mix(S["existing_line"], S["new_line"], 0.45)
        elif st == "city":      # the city around the site fades back
            wall, top_, line = S["existing_fill"], S["existing_fill"], mix(S["existing_line"], S["ground"], 0.5)
        else: wall, top_, line = S["existing_fill"], S["existing_fill"], S["existing_line"]
        ring = list(g.exterior.coords)
        if not Polygon(ring).exterior.is_ccw: ring = ring[::-1]
        walls = sorted(((x1 + x2 + y1 + y2, (x1, y1, x2, y2)) for (x1, y1), (x2, y2) in zip(ring, ring[1:])
                        if (y2 - y1) - (x2 - x1) < 0), key=lambda w: -w[0])
        shade = lambda x1, y1, x2, y2: S["new_wall_shade"] if k == "n" and (y2 - y1) >= 0 else wall
        for _, (x1, y1, x2, y2) in walls:
            s = face([(x1, y1, 0), (x2, y2, 0), (x2, y2, h), (x1, y1, h)], shade(x1, y1, x2, y2), line)
            if k == "n" and large:
                for i in range(1, fl):
                    z = h * i / fl
                    s += '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="0.25"/>' % (
                        *iso(x1, y1, z), *iso(x2, y2, z), S["floor_line"])
            out.append(s)
        cs = gable(g) if k == "n" and roof == "gable" else None
        if cs:   # two planes up to the ridge along the long side, and the gable ends over the walls that show
            p0, p1, p2, p3 = cs; up = h + math.dist(p1, p2) / 2 * math.tan(math.radians(PITCH))
            r0, r1 = ((p3[0] + p0[0]) / 2, (p3[1] + p0[1]) / 2), ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
            for a_, b_, ra, rb in ((p0, p1, r1, r0), (p2, p3, r0, r1)):
                lit = top_ if (b_[1] - a_[1]) < 0 else S["new_wall"]
                out.append(face([(*a_, h), (*b_, h), (*ra, up), (*rb, up)], lit, line))
            for a_, b_, ra in ((p1, p2, r1), (p3, p0, r0)):
                if (b_[1] - a_[1]) - (b_[0] - a_[0]) < 0:
                    out.append(face([(*a_, h), (*b_, h), (*ra, up)], shade(*a_, *b_), line))
        else:
            fill = {"green": S["roof_green"], "pv": top_ if large else mix(top_, S["pv"], 0.3)}.get(roof, top_) if k == "n" else top_
            out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.5" stroke-linejoin="round"/>' % (ring_d(ring, h), fill, line))
            if k == "n" and large:   # a parapet; the pv's panel rows along the long side
                inner = g.buffer(-0.6 if roof != "pv" else -1.5)
                if roof == "pv" and not inner.is_empty:
                    m = g.minimum_rotated_rectangle.exterior.coords
                    (ax_, ay_), (bx_, by_), (cx_, cy_) = m[0], m[1], m[2]
                    if math.dist(m[0], m[1]) < math.dist(m[1], m[2]): (ax_, ay_), (bx_, by_), (cx_, cy_) = m[1], m[2], m[3]
                    d = math.dist((bx_, by_), (cx_, cy_)); ux, uy = (cx_ - bx_) / d, (cy_ - by_) / d
                    rows = [LineString([(ax_ + ux * t, ay_ + uy * t), (bx_ + ux * t, by_ + uy * t)]).intersection(inner)
                            for t in [2.5 * i + 1.25 for i in range(int(d / 2.5))]]
                    out.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.3"/>'
                               % ("".join(line_d(r, h) for r in rows), S["pv"]))
                elif not inner.is_empty:
                    out.append('<path d="%s" fill="none" stroke="%s" stroke-width="0.2"/>' % (poly_d(inner, h), S["floor_line"]))
        if id(g) in labels:   # its use on the longest wall that shows, the ground floor's at the ground floor; else on the roof
            txt, ill = labels[id(g)]; txt += " *" if ill else ""
            ln, w = max([(math.dist(w[:2], w[2:]), w) for _, w in walls] or [(0, None)])
            (ax_, ay_), (bx_, by_) = (iso(*w[:2]), iso(*w[2:])) if w else ((0, 0), (0, 1))
            if bx_ < ax_: (ax_, ay_), (bx_, by_) = (bx_, by_), (ax_, ay_)
            d = math.hypot(bx_ - ax_, by_ - ay_) or 1
            if w and ln >= 0.6 * fs * len(txt) and (bx_ - ax_) / d >= 0.5:   # a wall wide enough, not too steep
                own = labels[id(g)][0] == re.sub(r"\s*\d+$", "", str(p.get("use") or ""))   # the building's own use, else its ground floor's
                zb = (h - 0.7 * fs) / 2 if own and h >= 2 * fs else 0.4
                mx_, my_ = iso((w[0] + w[2]) / 2, (w[1] + w[3]) / 2, zb)
                out.append(label(txt, fs, "matrix(%.4f,%.4f,0,1,%.1f,%.1f)" % ((bx_ - ax_) / d, (by_ - ay_) / d, mx_, my_)))
            else:
                q = g.representative_point()
                out.append(label(txt, fs, GROUND_TEXT(q.x, q.y, h if not cs else up), S["new_roof"]))
    return out

def people(clip):
    """Illustrative people on the design's squares and the streets inside clip and the site, off the buildings."""
    rnd, out = random.Random(1), []
    blocked = unary_union([g for _, k, g, *_ in items if k in "ne"]).buffer(1.0)
    zones = [(g, PEOPLE_M2[0]) for p, g in opens if p.get("use") == "square"] + ([(street_u, PEOPLE_M2[1])] if street_u is not None else [])
    for g, per in zones:
        z = g.intersection(clip).intersection(rot(site).buffer(20)).difference(blocked)
        n, zp = int(z.area / per), prep(z)
        if not n: continue
        x0, y0, x1, y1 = z.bounds
        for _ in range(n * 40):
            q = Point(rnd.uniform(x0, x1), rnd.uniform(y0, y1))
            if zp.contains(q):
                out.append((q.x + q.y, "p", q, 0, 0, None, None)); n -= 1
                if not n: break
    return out

def labels_in(view):
    """The new buildings to label: one per block and use, its largest part."""
    best = {}
    for _, k, g, h, fl, roof, p in view:
        lab = use_label(p) if k == "n" else None
        key = (p.get("block"), lab) if lab else None
        if lab and (key not in best or g.area > best[key][0].area): best[key] = (g, lab)
    return {id(g): lab for g, lab in best.values()}

def north(ax, ay, r, sw):   # a circle in outline, a line from its centre to the circle, turned with the view
    n = affinity.rotate(Point(0, 50), ROT, origin=(0, 0)); nx, ny = iso(n.x, n.y); k = r / (math.hypot(nx, ny) or 1)
    return ('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-width="%.2f"/>'
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.2f"/>'
            % (ax, ay, r, S["text"], sw, ax, ay, ax + nx * k, ay + ny * k, S["text"], sw))

def fade(x0, y0, w, h, d):   # the edges fade out to the paper
    return "".join('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="url(#%s)"/>' % r for r in
                   ((x0, y0, d, h, "fl"), (x0 + w - d, y0, d, h, "fr"), (x0, y0, w, d, "ft"), (x0, y0 + h - d, w, d, "fb")))

def render(name, sc, vb, body, extra):
    """Writes name.svg at its size in mm at 1:sc and name.png from a headless browser, 3000 px wide; returns its mm and the PNG's note."""
    x0, y0, w, h, ht = vb
    stops = '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s" stop-opacity="0"/>' % (S["ground"], S["ground"])
    defs = ('<defs><pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            '<rect width="7" height="7" fill="%s"/><line x1="0" y1="0" x2="0" y2="7" stroke="%s" stroke-width="0.4"/></pattern>'
            '<clipPath id="f"><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/></clipPath>' % (S["design_green"], S["design_green_hatch"], x0, y0, w, h)
            + "".join('<linearGradient id="%s" x1="%d" y1="%d" x2="%d" y2="%d">%s</linearGradient>' % (i, *v, stops)
                      for i, v in (("fl", (0, 0, 1, 0)), ("fr", (1, 0, 0, 0)), ("ft", (0, 0, 0, 1)), ("fb", (0, 1, 0, 0)))) + "</defs>")
    def write(path, wa, ha):
        open(path, "w", encoding="utf-8").write(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.0f %.0f %.0f %.0f" width="%s" height="%s">' % (x0, y0, w, ht, wa, ha) +
            '<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="%s"/>' % (x0, y0, w, ht, S["ground"]) + defs +
            '<g clip-path="url(#f)">' + "".join(body) + "</g>" + extra + "</svg>")
    mmw, mmh = w / sc * 1000, ht / sc * 1000
    write(os.path.abspath(os.path.join(out_dir, name + ".svg")), "%.0fmm" % mmw, "%.0fmm" % mmh)
    pw = 3000; ph = int(round(pw * ht / w))
    prev = os.path.abspath(os.path.join(out_dir, "_preview.svg")); write(prev, str(pw), str(ph))
    png = os.path.abspath(os.path.join(out_dir, name + ".png"))
    browsers = [shutil.which(b) for b in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge")]
    browsers += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "/Applications/Chromium.app/Contents/MacOS/Chromium",
                 "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                 r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    browser = next((b for b in browsers if b and os.path.exists(b)), None)
    note = "PNG from headless Chrome or Edge"
    if browser:
        try:
            subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars", "--screenshot=" + png,
                            "--window-size=%d,%d" % (pw, ph), "file://" + prev], capture_output=True, timeout=180)
        except Exception as e:
            note = "PNG failed (%s)" % e
        if not os.path.exists(png): note = "PNG failed: the browser wrote no file"
    else:
        note = "no PNG: no Chrome, Chromium or Edge installed"
    os.remove(prev)
    return mmw, mmh, note

# the district
LARGE = scale <= 1500 and bool(new)            # large: floor lines, roof details, use labels and people
fs = S["label_mm"] * scale / 1000
lab = labels_in(items) if LARGE else {}
crowd = people(Polygon([plan(x, y) for x, y in frame.exterior.coords])) if LARGE else []
body = ground(fs=fs if LARGE else 0) + paint(sorted(items + crowd, key=lambda i: -i[0]), LARGE, lab, fs) + [fade(fx0, fy0, W, H, min(0.08 * min(W, H), 0.8 * MARGIN))]
HT = H + 40
note_txt = "* the ground floor's use as the massing allots it, illustrative. People illustrative."
extra = north(fx0 + 50, fy1 + 20, 14, 1.5) + (label(note_txt, fs, "translate(%.1f,%.1f)" % (fx0 + 80, fy1 + 24), anchor="start") if LARGE else "")
name = "isometric_1-%d" % scale
mmw, mmh, png_note = render(name, scale, (fx0, fy0, W, H, HT), body, extra)

# the main centre close up, in its frame, at --close
if new:
    cs_ = a.close; cw, ch = a.close_frame or (a.panel_mm, 0.6 * a.panel_mm)
    w2, h2 = cw * cs_ / 1000, ch * cs_ / 1000
    cg = rot(main[0][1] if main else focus); q = cg.representative_point() if cg.geom_type != "Point" else cg
    cx, cy = iso(q.x, q.y, 10)
    win = box(cx - w2 / 2, cy - h2 / 2, cx + w2 / 2, cy + h2 / 2)
    clip = Polygon([plan(x, y) for x, y in win.exterior.coords]).buffer(10)
    view = [i for i in items if in_frame(i[2], win, i[3] + (2 * i[5] if i[1] == "t" else 0))]
    fs2 = S["label_mm"] * cs_ / 1000; lab2 = labels_in(view); crowd2 = people(clip)
    body2 = ground(clip, fs2) + paint(sorted(view + crowd2, key=lambda i: -i[0]), cs_ <= 1500, lab2, fs2)
    x0, y0, mm = cx - w2 / 2, cy - h2 / 2, cs_ / 1000
    body2.append(fade(x0, y0, w2, h2, 0.12 * min(w2, h2)))
    extra2 = north(x0 + 12 * mm, y0 + h2 - 10 * mm, 5 * mm, 0.35 * mm) + label(
        note_txt, fs2, "translate(%.1f,%.1f)" % (x0 + 22 * mm, y0 + h2 - 8.5 * mm), anchor="start")
    mmw2, mmh2, png2 = render("isometric_centre_1-%d" % cs_, cs_, (x0, y0, w2, h2, h2), body2, extra2)
    cname = main[0][0].get("name") if main else None
    missing = " (none named %s, so this one)" % a.centre if a.centre and cname != a.centre else ""
    close_line = (", and its centre %s%s close up at 1:%d, %.0f × %.0f mm, the edges fading out"
                  % (cname or "(no centre or square in the files, so the district's middle)", missing, cs_, mmw2, mmh2))
    close_what = ("; close up %d use labels from the massing (%d of them ground floors it allots, marked * as illustrative) "
                  "and %d people, illustrative" % (len(lab2), sum(v[1] for v in lab2.values()), len(crowd2)))
    png_note += "" if png2 == png_note else "; close up: " + png2

n_new = len(new); n_exist = sum(i[1] == "e" for i in items)
what = ("The design" if new else "The site as it is (no `massing/massing.geojson` yet, so the design is missing)")
widths = ", ".join("%s %g m" % (k, WIDTH.get(k, 6)) for k in sorted(x for x in assumed if x)) or "none"
streets_note = ("streets from streets/streets.geojson" if street_feats
                else "street widths assumed by class (%s)" % widths)
roof_n = {}
for p, g in new:
    r = p.get("roof") or "flat"
    if r == "gable" and not all(gable(q) for q in getattr(rot(g), "geoms", [rot(g)]) if q.geom_type == "Polygon"): r = "gable drawn flat (not a rectangle)"
    roof_n[r] = roof_n.get(r, 0) + 1
roofs = ", ".join("%d %s" % (v, k + (" at an assumed %g° pitch" % PITCH if k == "gable" else "")) for k, v in sorted(roof_n.items()))
open(summary, "w", encoding="utf-8").write(
    "- %s, isometric seen from the %s: the district at 1:%d, %.0f × %.0f mm in print (the panels crop it)%s.\n"
    % (what, SIDE, scale, mmw, mmh, close_line if new else "") +
    "- %d new buildings%s%s; %d existing buildings, %d of them at default heights from the site data; %d trees%s.\n"
    % (n_new, " with floor lines" if LARGE else "", ", roofs as the massing names them (%s)" % roofs if new else "",
       n_exist, defaults, sum(i[1] == "t" for i in items), close_what if new else "") +
    "- Unsure: %s; %s; %s.\n"
    % (streets_note, "colours from the drawing standard" if used_standard else "no drawing standard, so the fallback look", png_note))
print(open(summary, encoding="utf-8").read())
