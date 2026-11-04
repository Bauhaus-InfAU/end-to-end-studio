"""Isometric of an urban design, or of the site as it is when there is no design yet.

python3 isometric.py <site folder> <proposal folder> <site plan scale> <panel width mm> [--style style.json]

Reads <site folder>/site.geojson and its layers (buildings, plots, streets, water, rail),
and <proposal folder>/massing/massing.geojson and open-space/open-space.geojson's trees if they exist. Writes into
<proposal folder>/isometric/: isometric_1-<scale>.svg and .png, and summary.md.
--style: the drawing standard's style.json, its keys mapped onto STYLE below.
Needs shapely and pyproj; the PNG needs a headless Chrome, Chromium or Edge.
"""
import argparse, json, math, os, shutil, subprocess, sys
from shapely.geometry import shape, Point, Polygon, box
from shapely.ops import unary_union, transform
from shapely import affinity
from pyproj import Transformer

ap = argparse.ArgumentParser()
ap.add_argument("site"); ap.add_argument("proposal")
ap.add_argument("scale", type=int, help="the brief's site plan scale, e.g. 3000")
ap.add_argument("panel_mm", type=float, help="width of the brief's panel in mm")
ap.add_argument("--style")
a = ap.parse_args()
out_dir = os.path.join(a.proposal, "isometric"); os.makedirs(out_dir, exist_ok=True)

# fallback look: black on white, white buildings with shaded walls, the accent's pale tone on the squares.
STYLE = {"accent": "#d9302b", "new_wall": "#ececec", "new_wall_shade": "#cfcfcf", "new_roof": "#ffffff",
         "new_line": "#1a1a1a", "floor_line": "#a8a8a8", "existing_line": "#c2c2c2", "existing_fill": "#ffffff",
         "ground": "#ffffff", "field": "#f4f4f1", "field_line": "#dcdcd6", "design_green": "#fafaf8",
         "design_green_hatch": "#cfcfc7", "water": "#e3e7e9", "water_line": "#9aa3a8", "street": "#fafaf8",
         "street_line": "#a0a0a0", "rail": "#444444", "tree": "#9a9a9a", "text": "#1a1a1a", "public": "#f0b8b5",
         "shadow": "#a8a8a8"}
TREE_H, TREE_CROWN = 10.0, 6.0   # height and crown diameter of a tree without height_m or crown_m, metres
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
        "tree": s.get("grove"), "text": s.get("ink"), "shadow": s.get("shadow")}.items() if v})

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

def layer(name):
    for f in load(os.path.join(a.site, name + ".geojson")):
        g = transform(tr, shape(f["geometry"]))
        if g.intersects(area): yield f["properties"], g

existing = list(layer("buildings"))
if new:
    newu = unary_union([g for _, g in new]).buffer(0)
    existing = [(p, g) for p, g in existing if not g.buffer(0).intersects(newu)]

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
rot = lambda g: affinity.rotate(g, ROT, origin=O)
C30 = math.cos(math.radians(30))
iso = lambda x, y, z=0.0: ((x - y) * C30, -((x + y) * 0.5 + z))   # 1 unit = 1 m, true along the axes
ring_d = lambda cs, z=0.0: "M" + "L".join("%.1f,%.1f" % iso(x, y, z) for x, y in cs) + "Z"
def poly_d(g, z=0.0):
    return "".join(ring_d(p.exterior.coords, z) + "".join(ring_d(i.coords, z) for i in p.interiors)
                   for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and not p.is_empty)
def line_d(g):
    return "".join("M" + "L".join("%.1f,%.1f" % iso(x, y) for x, y in l.coords)
                   for l in getattr(g, "geoms", [g]) if not l.is_empty and l.geom_type == "LineString")

# frame and scale: the site plan scale, or the next smaller usual one if wider than the panel
top = max([float(p.get("height_m") or 0) for p, _ in new] or [0])
pts = [iso(x, y, z) for p in getattr(rot(focus), "geoms", [rot(focus)]) for x, y in p.exterior.coords for z in (0, top)]
xs, ys = zip(*pts)
fx0, fy0, fx1, fy1 = min(xs) - MARGIN, min(ys) - MARGIN, max(xs) + MARGIN, max(ys) + MARGIN
W, H = fx1 - fx0, fy1 - fy0
USUAL = [500, 1000, 2000, 2500, 5000, 10000, 15000, 20000, 25000, 50000]
scale = a.scale
for s_ in [a.scale] + [u for u in USUAL if u > a.scale]:
    scale = s_
    if W / s_ * 1000 <= a.panel_mm: break
LARGE = scale <= 1000                          # large: floor lines and roofs
frame = Polygon([(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)])
def in_frame(g):
    if g.geom_type == "Point": return frame.contains(Point(iso(g.x, g.y)))
    return frame.intersects(Polygon([iso(x, y) for x, y in g.exterior.coords]))

S = STYLE; svg = []
GREEN = {"grass", "meadow", "leisure:park", "forest", "natural:wood", "natural:scrub", "farmland", "allotments",
         "leisure:pitch", "leisure:playground", "leisure:sports_centre", "park", "garden", "wood", "scrub"}
for p, g in layer("plots"):
    if p.get("landuse") in GREEN:
        svg.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.4"/>' % (poly_d(rot(g)), S["field"], S["field_line"]))
for p, g in layer("water"):
    svg.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.5"/>' % (poly_d(rot(g)), S["water"], S["water_line"]))
for f in mass:
    p = f["properties"]
    if p.get("kind") == "open-space":
        fill = {"water": S["water"], "square": S["public"]}.get(p.get("use"), "url(#hatch)")
        svg.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.4"/>'
                   % (poly_d(rot(transform(tr, shape(f["geometry"])))), fill, S["field_line"]))

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
if surf:
    svg.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.5" fill-rule="evenodd"/>'
               % (poly_d(unary_union(surf)), S["street"], S["street_line"]))
for g in paths:
    if g.geom_type.endswith("Polygon"):
        svg.append('<path d="%s" fill="%s" stroke="none"/>' % (poly_d(g), S["street"]))
    else:
        svg.append('<path d="%s" fill="none" stroke="%s" stroke-width="0.4"/>' % (line_d(g), S["street_line"]))
for p, g in layer("rail"):
    g = rot(g)
    for off in (-2.2, -0.8, 0.8, 2.2):
        try: svg.append('<path d="%s" fill="none" stroke="%s" stroke-width="0.45"/>' % (line_d(g.parallel_offset(off, "left")), S["rail"]))
        except Exception: pass
if not new:
    svg.append('<path d="%s" fill="none" stroke="%s" stroke-width="2.4" stroke-dasharray="10 4"/>' % (poly_d(rot(site)), S["accent"]))

# buildings and (large only) the massing's trees, far to near
items, defaults = [], 0
for p, g in existing:
    for q in getattr(rot(g), "geoms", [rot(g)]):
        if q.geom_type == "Polygon" and in_frame(q):
            items.append((q.centroid.x + q.centroid.y, "e", q, float(p.get("height") or 3), 0, None))
            defaults += p.get("height_source") == "default"
for p, g in new:
    fl = int(p.get("floors") or 1); h = float(p.get("height_m") or 3 * fl)
    for q in getattr(rot(g), "geoms", [rot(g)]):
        if q.geom_type == "Polygon": items.append((q.centroid.x + q.centroid.y, "n", q, h, fl, p.get("roof")))
for f in trees:   # at every scale; a tree's crown radius rides in the roof's place
    t, p = rot(transform(tr, shape(f["geometry"]))), f["properties"]
    if t.geom_type == "Point" and in_frame(t):
        items.append((t.x + t.y, "t", t, float(p.get("height_m") or TREE_H), 0, float(p.get("crown_m") or TREE_CROWN) / 2))
items.sort(key=lambda i: -i[0])

for _, k, g, h, fl, roof in items:
    if k == "t":   # its soft shadow on the ground, the trunk, the crown at the top of its height
        r, dark = roof, mix(S["tree"], S["new_line"], 0.3); cx, cy = iso(g.x, g.y, h - r); gx, gy = iso(g.x, g.y)
        svg.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" fill-opacity="0.5"/>'
                   '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="0.35"/>'
                   '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity="0.9" stroke="%s" stroke-width="0.35"/>'
                   % (gx + 0.4 * r, gy, 1.22 * r, 0.71 * r, S["shadow"], gx, gy, cx, cy + r, dark, cx, cy, r, S["tree"], dark))
        continue
    if k == "n": wall, top_, line = S["new_wall"], S["new_roof"], S["new_line"]
    else: wall, top_, line = S["existing_fill"], S["existing_fill"], S["existing_line"]
    ring = list(g.exterior.coords)
    if not Polygon(ring).exterior.is_ccw: ring = ring[::-1]
    walls = sorted(((x1 + x2 + y1 + y2, (x1, y1, x2, y2)) for (x1, y1), (x2, y2) in zip(ring, ring[1:])
                    if (y2 - y1) - (x2 - x1) < 0), key=lambda w: -w[0])
    for _, (x1, y1, x2, y2) in walls:
        q = [iso(x1, y1), iso(x2, y2), iso(x2, y2, h), iso(x1, y1, h)]
        fill = S["new_wall_shade"] if k == "n" and (y2 - y1) >= 0 else wall
        s = '<path d="M%s Z" fill="%s" stroke="%s" stroke-width="0.4" stroke-linejoin="round"/>' % (
            " L".join("%.1f,%.1f" % v for v in q), fill, line)
        if k == "n" and LARGE:
            for i in range(1, fl):
                z = h * i / fl
                s += '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="0.25"/>' % (
                    *iso(x1, y1, z), *iso(x2, y2, z), S["floor_line"])
        svg.append(s)
    svg.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.5" stroke-linejoin="round"/>' % (ring_d(ring, h), top_, line))
    if roof and LARGE:
        svg.append('<path d="%s" fill="none" stroke="%s" stroke-width="0.3" stroke-dasharray="1 1"/>' % (poly_d(g.buffer(-1.5), h), line))

# north: a circle in outline, a line from its centre to the circle, turned with the view
n = affinity.rotate(Point(0, 50), ROT, origin=(0, 0)); nx, ny = iso(n.x, n.y)
r = 14 / (math.hypot(nx, ny) or 1)
ax, ay = fx0 + 50, fy1 + 20
extra = ('<circle cx="%.1f" cy="%.1f" r="14" fill="none" stroke="%s" stroke-width="1.5"/>'
         '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.5"/>'
         % (ax, ay, S["text"], ax, ay, ax + nx * r, ay + ny * r, S["text"]))
HT = H + 40
defs = ('<defs><pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        '<rect width="7" height="7" fill="%s"/><line x1="0" y1="0" x2="0" y2="7" stroke="%s" stroke-width="0.4"/></pattern>'
        '<clipPath id="f"><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/></clipPath></defs>'
        % (S["design_green"], S["design_green_hatch"], fx0, fy0, W, H))
def write(path, wa, ha):
    open(path, "w").write(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.0f %.0f %.0f %.0f" width="%s" height="%s">' % (fx0, fy0, W, HT, wa, ha) +
        '<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="%s"/>' % (fx0, fy0, W, HT, S["ground"]) + defs +
        '<g clip-path="url(#f)">' + "".join(svg) + "</g>" + extra + "</svg>")

name = "isometric_1-%d" % scale
mmw, mmh = W / scale * 1000, HT / scale * 1000
svg_path = os.path.abspath(os.path.join(out_dir, name + ".svg"))
write(svg_path, "%.0fmm" % mmw, "%.0fmm" % mmh)

# PNG: headless Chrome, Chromium or Edge, 3000 px wide
pw = 3000; ph = int(round(pw * HT / W))
prev = os.path.abspath(os.path.join(out_dir, "_preview.svg")); write(prev, str(pw), str(ph))
png = os.path.abspath(os.path.join(out_dir, name + ".png"))
browsers = [shutil.which(b) for b in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge")]
browsers += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Chromium.app/Contents/MacOS/Chromium",
             "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
browser = next((b for b in browsers if b and os.path.exists(b)), None)
png_note = "PNG from headless Chrome or Edge"
if browser:
    try:
        subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars", "--screenshot=" + png,
                        "--window-size=%d,%d" % (pw, ph), "file://" + prev], capture_output=True, timeout=180)
    except Exception as e:
        png_note = "PNG failed (%s)" % e
    if not os.path.exists(png): png_note = "PNG failed: the browser wrote no file"
else:
    png_note = "no PNG: no Chrome, Chromium or Edge installed"
os.remove(prev)

n_new = len(new); n_exist = sum(i[1] == "e" for i in items)
what = ("The design" if new else "The site as it is (no `massing/massing.geojson` yet, so the design is missing)")
why = "" if scale == a.scale else (" At the site plan scale 1:%d it would be %.0f mm wide, wider than the %.0f mm panel, so the next usual scale."
                                   % (a.scale, W / a.scale * 1000, a.panel_mm))
widths = ", ".join("%s %g m" % (k, WIDTH.get(k, 6)) for k in sorted(x for x in assumed if x)) or "none"
streets_note = ("streets from streets/streets.geojson" if street_feats
                else "street widths assumed by class (%s)" % widths)
open(summary, "w").write(
    "- %s, isometric at 1:%d, seen from the %s, %.0f × %.0f mm in print.%s\n" % (what, scale, SIDE, mmw, mmh, why) +
    "- %d new buildings%s; %d existing buildings, %d of them at default heights from the site data; %d trees.\n"
    % (n_new, " with floor lines" if LARGE and n_new else "", n_exist, defaults, sum(i[1] == "t" for i in items)) +
    "- Unsure: %s; %s; %s.\n"
    % (streets_note, "colours from the drawing standard" if used_standard else "no drawing standard, so the fallback look", png_note))
print(open(summary).read())
