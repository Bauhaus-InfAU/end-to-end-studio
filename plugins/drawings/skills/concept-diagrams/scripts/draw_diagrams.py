"""Concept pictograms from a JSON spec: SVG, a PNG next to each, and a sheet of all frames.

  python draw_diagrams.py info --site site.geojson [--layer name=path.geojson ...]
  python draw_diagrams.py render spec.json out_dir/

The spec format is in ../spec.md. Coordinates in a spec are metres, x east and y north of the
site's centre (what `info` prints), unless an element gives a GeoJSON file instead.
Needs shapely and pyproj; PNGs need Chrome or Edge (or Chromium) for a headless screenshot.
"""
import json, math, os, re, shutil, subprocess, sys
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, box as rect, shape
from shapely.ops import linemerge, substring, unary_union

# The look is not this script's to choose: it comes from the drawing standard (drawing-graphics/style.json next to the
# spec's folder, see from_standard), and any key can be set in the spec's `style`.
# These values are only the studio's fallback when there is none: black lines on white, one accent colour.
FALLBACK_STYLE = {
    "ink": "#000", "paper": "#fff", "accent": "#d0312d", "font": "Helvetica, Arial, sans-serif",
    # line weights, px at the drawing's size
    "outline": 1.3, "line": 0.8, "heavy": 3.2, "box": 0.6, "thin": 0.7, "hatch": 0.5, "rule": 0.5,
    "sign": 1.5, "sign_old": 0.9, "ghost": 0.9, "leader": 0.6, "tee": 2.5, "halo": 3,
    "dash": "5 3", "ghost_dash": "3 2", "tint_opacity": 0.2, "solid_opacity": 0.85,
    "min_width": 3,  # px: the narrowest a strip is drawn, so it never vanishes small
    # signs, px: the line of people, trees and things; a person's height; an icon's diameter; a vignette's radius
    "glyph": 1.0, "figure": 22, "icon": 24, "vignette": 46,
    # text sizes, px
    "label_size": 11, "small_size": 9, "title_size": 16, "title_weight": "bold",
    "caption_size": 11.5, "footer_size": 8.5, "footer_style": "italic",
}


def from_standard(spec_path):
    """The look of <proposal>/drawing-graphics/style.json, next to the spec's folder, mapped, never merged: its colours
    and font by name, and its `diagram` keys this script has (px); its own `thin` or `line` are mm on a plan."""
    try:
        s = json.loads((spec_path.parent.parent / "drawing-graphics" / "style.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    d = s.get("diagram") if isinstance(s.get("diagram"), dict) else {}
    return {**{k: s[k] for k in ("ink", "paper", "accent", "font") if isinstance(s.get(k), str)},
            **{k: v for k, v in d.items() if k in FALLBACK_STYLE}}


MM = 25.4 / 96  # mm per CSS px


def frame_mm(spec_path, sp):
    """The print width to draw to: the spec's `width_mm`, else the narrowest frame the panels' first plan
    (panel-layout's layout-plan.json, else layout.json) gives these pictograms, else None (the spec's `size`)."""
    if sp.get("width_mm"):
        return float(sp["width_mm"])
    names = {f.get("file") for f in sp.get("frames", [])}
    for name in ("layout-plan.json", "layout.json"):
        try:
            L = json.loads((spec_path.parent.parent / "panel-layout" / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ws = [(it.get("frame") or {}).get("w") or it.get("w") for p in L.get("panels", []) for it in p.get("items", [])
              if Path(str(it.get("file", ""))).parent.name == spec_path.parent.name and Path(str(it.get("file", ""))).stem in names]
        ws = [float(w) for w in ws if w]
        if ws:
            return min(ws)
    return None


# ---------- data ----------

def read_features(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d["features"] if "features" in d else [d if d.get("type") == "Feature" else {"geometry": d, "properties": {}}]


def make_projection(site_path):
    geoms = [shape(f["geometry"]) for f in read_features(site_path)]
    c = unary_union(geoms).centroid
    t = Transformer.from_crs("EPSG:4326", f"+proj=aeqd +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", always_xy=True)
    return lambda g: shapely.transform(g, lambda a: np.column_stack(t.transform(a[:, 0], a[:, 1]))), unary_union(geoms)


def matches(props, where):
    for k, v in (where or {}).items():
        val = props.get(k)
        if isinstance(v, str) and v.startswith("~"):
            if val is None or not re.search(v[1:], str(val)):
                return False
        elif val != v:
            return False
    return True


def load_layer(path, where, project):
    gs = [project(shape(f["geometry"])) for f in read_features(path) if f.get("geometry") and matches(f.get("properties") or {}, where)]
    return unary_union(gs) if gs else None


def parts(g):  # every simple part: multi-geometries and collections opened all the way down
    if g is None or g.is_empty:
        return []
    return [q for p in g.geoms for q in parts(p)] if hasattr(g, "geoms") else [g]


def polygons(g):  # every polygon of g, each with its holes; none dropped for being small
    return [p for p in parts(g) if p.geom_type == "Polygon"]


def rings_of(g):  # the outline and holes of every polygon
    return [r for p in polygons(g) for r in (p.exterior, *p.interiors)]


def areal(g, what):
    """The polygons of g as one geometry (a Polygon or MultiPolygon, holes kept), saying what isn't an area."""
    ps = polygons(g)
    other = len(parts(g)) - len(ps)
    if other:
        print(f"{what}: {other} part(s) that are not areas (lines, points) left out of it", file=sys.stderr)
    return None if not ps else ps[0] if len(ps) == 1 else shapely.MultiPolygon(ps)


# ---------- info ----------

def info(args):
    site_path = args[args.index("--site") + 1]
    project, _ = make_projection(site_path)
    site = areal(project(unary_union([shape(f["geometry"]) for f in read_features(site_path)])), "site")
    x0, y0, x1, y1 = site.bounds
    ps = polygons(site)
    nh = sum(len(p.interiors) for p in ps)
    print(f"site: {site.area / 1e4:.2f} ha, {len(ps)} polygon{'s' * (len(ps) != 1)}, {nh} hole{'s' * (nh != 1)}, "
          f"x {x0:.0f}..{x1:.0f} m, y {y0:.0f}..{y1:.0f} m (0,0 = centre)")
    for i, p in enumerate((q.simplify(30) if q.simplify(30).geom_type == "Polygon" and not q.simplify(30).is_empty else q for q in ps), 1):  # every part, smallest included
        print(f"outline {i}, simplified 30 m:", " ".join(f"{x:.0f},{y:.0f}" for x, y in p.exterior.coords))
        for h in p.interiors:
            print(f"  hole:", " ".join(f"{x:.0f},{y:.0f}" for x, y in h.coords))
    for spec in [a for i, a in enumerate(args) if i and args[i - 1] == "--layer"]:
        name, path = spec.split("=", 1)
        near = site.buffer(100)
        names = {}
        for f in read_features(path):
            g = project(shape(f["geometry"]))
            if g.intersects(near):
                p = f.get("properties") or {}
                key = " | ".join(str(p[k]) for k in ("name", "highway", "railway", "waterway", "landuse", "kind", "use") if p.get(k))
                names.setdefault(key or "(no name)", []).append(g)
        print(f"\n{name}: features within 100 m of the site")
        for key, gs in sorted(names.items(), key=lambda kv: -len(kv[1]))[:25]:
            u = unary_union(gs)
            print(f"  {key}: {len(gs)}, x {u.bounds[0]:.0f}..{u.bounds[2]:.0f}, y {u.bounds[1]:.0f}..{u.bounds[3]:.0f}")


# ---------- view ----------

class View:
    composed = None  # a frame drawn whole, not as a view of the site: "layers" or "metaphor"

    def __init__(self, v, width, height, extent, top):
        self.plan = v.get("type", "iso") == "plan"
        self.cut_z = v.get("cut_height") if self.plan else None  # a floor plan: cut at this height
        self.sec = v.get("type") == "section" and v.get("cut")   # a section: cut along a line, looking to its left
        self.elev = v.get("type") == "elevation" or bool(self.sec)  # seen level: heights only, on a ground line
        self.th = math.radians(v.get("rotation", 0 if self.plan or self.elev else 30))
        if self.sec:
            (ax, ay), (bx, by) = self.sec
            a = math.atan2(by - ay, bx - ax)
            self.th = -a  # the cut runs across the drawing
            d, nrm, F = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a)), 1e5
            self.cut = LineString([(ax - F * d[0], ay - F * d[1]), (bx + F * d[0], by + F * d[1])])
            self.behind = Polygon([(ax - F * d[0], ay - F * d[1]), (bx + F * d[0], by + F * d[1]),
                                   (bx + F * d[0] + F * nrm[0], by + F * d[1] + F * nrm[1]), (ax - F * d[0] + F * nrm[0], ay - F * d[1] + F * nrm[1])])
            extent = [c for c in extent if Point(c).within(self.behind.buffer(1))] or extent
        self.sq = 1.0 if self.plan else 0.0 if self.elev else v.get("tilt", 0.55)
        self.ex = 0.0 if self.plan else v.get("exaggerate", 3)
        self.focus = v.get("focus")  # [x0, y0, x1, y1]: a close-up of part of the site
        if self.focus:
            x0, y0, x1, y1 = self.focus
            extent = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        pts = [self.raw((x, y), z) for x, y in extent for z in (0, top)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        pad = 16
        self.s = min((width - 2 * pad) / (max(xs) - min(xs) or 1), (height - 2 * pad) / (max(ys) - min(ys) or 1))
        self.content_h = self.s * (max(ys) - min(ys)) + 2 * pad  # what the drawing needs; the rest of the height is empty
        self.ox = width / 2 - self.s * (min(xs) + max(xs)) / 2
        self.oy = height / 2 - self.s * (min(ys) + max(ys)) / 2

    def depth(self, p):
        return p[0] * math.sin(self.th) + p[1] * math.cos(self.th)

    def raw(self, p, z=0):
        x, y = p[0], p[1]
        return x * math.cos(self.th) - y * math.sin(self.th), -self.depth(p) * self.sq - z * self.ex

    def __call__(self, p, z=0):
        x, y = self.raw(p, z)
        return self.ox + self.s * x, self.oy + self.s * y

    def pts(self, coords, z=0):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in (self(c, z) for c in coords))


# ---------- elements ----------

def element_geom(e, base, project):
    k = e["kind"]
    if e.get("geojson"):
        g = load_layer(e["geojson"], e.get("where"), project)
        if g is not None and k == "strip":
            e["axis"] = g
            return g.buffer(e.get("width", 30) / 2, cap_style=2)
        if g is not None and k == "tree":
            return spaced(g, e.get("spacing", 20))
        return areal(g, f"{k} from {e['geojson']}") if g is not None and k in ("area", "volume") else g
    if k == "tree":  # one at `at`, several at `coords`, or spaced along a line
        along = e.get("along")
        return spaced(base[along]["geom"] if isinstance(along, str) else LineString(along) if along else
                      Point(e["at"]) if e.get("at") else shapely.MultiPoint([c[:2] for c in e["coords"]]), e.get("spacing", 20))
    if k == "person" and e.get("coords"):
        return shapely.MultiPoint([c[:2] for c in e["coords"]])
    if k in ("person", "icon", "vignette"):
        return Point(e["at"])
    if k in ("area", "volume"):
        return Polygon(e["coords"], e.get("holes"))
    if k == "strip":
        e["axis"] = LineString(e["coords"])
        return e["axis"].buffer(e.get("width", 30) / 2, cap_style=2)
    if k == "point":
        return Point(e["at"]).buffer(e.get("radius", 40))
    if k in ("arrow", "flow"):
        return LineString(e["coords"])
    if k in ("label", "rays"):
        return Point(e["at"])
    if k in ("row", "layers", "metaphor"):  # a row is cut into volumes; layers and a metaphor are whole frames
        return None
    raise ValueError(f"unknown element kind: {k}")


def spaced(g, step):
    """Tree positions: every point of g, and one every `step` metres along its lines and outlines."""
    pts = [p for p in parts(g) if p.geom_type == "Point"]
    for l in [l for l in parts(g) if l.geom_type in ("LineString", "LinearRing")] + rings_of(g):
        pts += [l.interpolate(d) for d in np.arange(min(step, l.length) / 2, l.length, step)]
    return shapely.MultiPoint(pts) if pts else None


SIDES = {"west": (True, 1), "east": (True, -1), "north": (False, 1), "south": (False, -1)}  # name: (line runs N-S, sign)


def oriented(line):
    """Turn the line to run south to north (west to east if it runs more east-west), whatever order its data has,
    so that side 1 is always its left: west of a north-south line, north of an east-west one."""
    (ax, ay), (bx, by) = line.coords[0], line.coords[-1]
    ns = abs(by - ay) >= abs(bx - ax)
    if (ns and by < ay) or (not ns and bx < ax):
        line = LineString(list(line.coords)[::-1])
    return line, ns


def row_segments(e, base, site, project):
    if isinstance(e["along"], str):
        line = base[e["along"]]["geom"]
    else:
        line = LineString(e["along"])
    merged = linemerge(line) if line.geom_type == "MultiLineString" else line
    line, ns = oriented(max(parts(merged), key=lambda l: l.length))
    out = []
    for side in e.get("sides", [1, -1]):
        if isinstance(side, str):
            if side not in SIDES or SIDES[side][0] != ns:
                raise ValueError(f"row along {e['along']}: side '{side}' doesn't fit a line that runs {'north-south' if ns else 'east-west'}")
            side = SIDES[side][1]
        d = side * (e.get("offset", 20) + e.get("depth", 30) / 2)
        curve = line.offset_curve(d) if hasattr(line, "offset_curve") else line.parallel_offset(abs(d), "left" if d > 0 else "right")
        for c in parts(curve):
            seg, gap, a = e.get("segment", 100), e.get("gap", 12), 0.0
            while a + seg * 0.4 < c.length:
                piece = substring(c, a, min(a + seg, c.length)).buffer(e.get("depth", 30) / 2, cap_style=2)
                if site is None or site.buffer(1).contains(piece):
                    out.append(piece)
                a += seg + gap
    return out


# ---------- svg ----------

def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def frame_defs(v, site, n, W, DH):  # per frame, as frames can differ in view
    clip = f'<clipPath id="site{n}"><path d="{rings_d(v, site)}" clip-rule="evenodd"/></clipPath>' if site is not None else ""
    return f'<defs>{clip}<clipPath id="frame{n}"><rect width="{W}" height="{DH}"/></clipPath></defs>'


def defs(st):
    mk = lambda i, c: (f'<marker id="{i}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" '
                       f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
    return (f'<defs><pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            f'<line x1="0" y1="0" x2="0" y2="5" stroke="{st["ink"]}" stroke-width="{st["hatch"]}"/></pattern>'
            f'{mk("ahK", st["ink"])}{mk("ahA", st["accent"])}'
            f'<marker id="tee" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">'
            f'<path d="M9,0 L9,10" stroke="{st["ink"]}" stroke-width="{st["tee"]}"/></marker></defs>')


def box(v, st, g, h, fill, z0=0):
    H = h if callable(h) else (lambda p: h)
    rings = [list(r.coords)[:-1] for r in rings_of(g)]
    attrs = f'fill="{fill}" stroke="{st["ink"]}" stroke-width="{st["box"]}" stroke-linejoin="round"'
    top = lambda zf: "".join("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in (v(p, zf(p)) for p in q)) + "Z" for q in rings)
    if v.plan:
        return f'<path d="{top(lambda p: 0)}" fill-rule="evenodd" {attrs}/>'
    sides = sorted([s for q in rings for s in zip(q, q[1:] + q[:1])], key=lambda s: -v.depth(((s[0][0] + s[1][0]) / 2, (s[0][1] + s[1][1]) / 2)))
    face = lambda f: f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in f)}" {attrs}/>'
    return "".join(face([v(a, z0), v(b, z0), v(b, H(b)), v(a, H(a))]) for a, b in sides) + f'<path d="{top(H)}" fill-rule="evenodd" {attrs}/>'


def section_faces(v, st, e, attrs):
    """Where a section's cut passes through a volume: one face per cut segment, from its base to its top."""
    H = top_of(e)
    H = H if callable(H) else (lambda p, h=H: h)
    z0 = e.get("base", 0) + e.get("lift", 0)
    out = ""
    for seg in parts(e["geom"].intersection(v.cut)):
        if seg.geom_type == "LineString" and seg.length > 0.01:
            a, b = seg.coords[0], seg.coords[-1]
            out += f'<polygon points="{v.pts([a, b], z0)} {" ".join(f"{x:.1f},{y:.1f}" for x, y in (v(b, H(b)), v(a, H(a))))}" {attrs}/>'
    return out


def ghost(v, e, attrs):
    """A removed volume, dashed where it was: its cut in a section, its footprint in a plan, its edges in 3D."""
    if v.sec:
        return section_faces(v, None, e, attrs)
    if v.plan:
        return poly(v, e["geom"], attrs)
    H = top_of(e)
    H = H if callable(H) else (lambda p, h=H: h)
    z0 = e.get("base", 0) + e.get("lift", 0)
    out = ""
    for r in rings_of(e["geom"]):
        q = list(r.coords)
        for zf in (lambda p: z0, H):
            out += f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in (v(p, zf(p)) for p in q))}" {attrs}/>'
        for p in q[:-1]:
            out += f'<polyline points="{v.pts([p], z0)} {" ".join(f"{x:.1f},{y:.1f}" for x, y in [v(p, H(p))])}" {attrs}/>'
    return out


def top_of(e):
    """A volume's top: its height, or a slope from h0 at (x0, y0) to h1 at (x1, y1), even between, held beyond. Lift raises it."""
    lift = e.get("lift", 0)
    if not e.get("slope"):
        return e.get("height", 10) + lift
    (x0, y0, h0), (x1, y1, h1) = e["slope"]
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy or 1
    return lambda p: h0 + (h1 - h0) * min(1, max(0, ((p[0] - x0) * dx + (p[1] - y0) * dy) / L2)) + lift


def guides(v, st, e):
    """Dashed lines from a lifted element's outline down to where it belongs: an exploded view."""
    if not e.get("lift"):
        return ""
    z0 = e.get("base", 0)
    pick = [p for pg in polygons(e["geom"]) for q in [list(pg.exterior.coords)[:-1]] for p in (q if len(q) <= 8 else q[::max(1, len(q) // 8)])]
    return "".join(f'<line x1="{v(p, z0)[0]:.1f}" y1="{v(p, z0)[1]:.1f}" x2="{v(p, z0 + e["lift"])[0]:.1f}" y2="{v(p, z0 + e["lift"])[1]:.1f}" '
                   f'stroke="{st["ink"]}" stroke-width="{st["thin"]}" stroke-dasharray="{st["ghost_dash"]}"/>' for p in pick)


def rings_d(v, g, z=0, to=None):  # an SVG path of every polygon's outline and holes; `to` moves screen points (an inset)
    to = to or (lambda p: p)
    return "".join("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in (to(v(c, z)) for c in r.coords)) + "Z" for r in rings_of(g))


def poly(v, g, attrs, z=0):
    return "".join(f'<path d="{rings_d(v, p, z)}" fill-rule="evenodd" {attrs}/>' for p in polygons(g))


def line(v, g, attrs, z=0):  # lines, and the outlines of a layer's polygons
    ls = [l for l in parts(g) if l.geom_type in ("LineString", "LinearRing")] + rings_of(g)
    return "".join(f'<polyline points="{v.pts(l.coords, z)}" fill="none" {attrs}/>' for l in ls)


def place_labels(st, reqs, obstacles, W, DH, n):
    """Put each label where it covers the least drawing and no other label; a leader line goes back to its place
    if it had to move. reqs: ((x, y) on screen, text, colour); obstacles: (screen geometry, weight)."""
    out, placed = [], []
    frame = rect(4, 4, W - 4, DH - 4)
    for (ax, ay), text, color in reqs:
        w, h = 0.56 * st["label_size"] * len(str(text)) + 4, 1.2 * st["label_size"]
        best = None
        for r in (0, 18, 32, 50, 75):
            for k in range(8 if r else 1):
                a = math.pi / 4 * k + math.pi / 4  # starts above right
                ca, sa = math.cos(a), math.sin(a)
                x = ax + 6 if not r else ax + r * ca + (2 if ca > 0.1 else -w - 2 if ca < -0.1 else -w / 2)
                y = ay - 4 if not r else ay - r * sa + (-2 if sa > 0.1 else h + 2 if sa < -0.1 else h / 2)
                b = rect(x, y - h, x + w, y)  # y is the baseline
                cover = sum(wt * b.intersection(g).area for g, wt in obstacles)
                clash = sum(b.intersection(p).area for p in placed)
                score = cover + 40 * clash + 40 * (b.area - b.intersection(frame).area) + 0.8 * r
                if best is None or score < best[0]:
                    best = (score, b, r, clash, cover)
        _, b, r, clash, cover = best
        placed.append(b)
        if clash > 1 or cover > 0.25 * b.area:
            print(f"frame {n}: label '{text}' still overlaps the drawing or another label; move its label_at", file=sys.stderr)
        if r:
            p = b.exterior.interpolate(b.exterior.project(Point(ax, ay)))
            out.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{p.x:.1f}" y2="{p.y:.1f}" stroke="{color}" stroke-width="{st["leader"]}"/>')
        x0, _, _, y1 = b.bounds
        out.append(f'<text x="{x0 + 2:.1f}" y="{y1 - 3:.1f}" font-family="{esc(st["font"])}" font-size="{st["label_size"]}" fill="{color}" '
                   f'stroke="{st["paper"]}" stroke-width="{st["halo"]}" paint-order="stroke">{esc(text)}</text>')
    return "".join(out)


def wrap(text, n):
    out = [""]
    for w in str(text).split():
        if len(out[-1]) + len(w) + 1 > n and out[-1]:
            out.append(w)
        else:
            out[-1] = (out[-1] + " " + w).strip()
    return out


# ---------- signs: people, trees and things as line drawings ----------
# Each sign: its width, its height (a person is 1 high) and its parts in those units, x to the right and y up from
# its foot at the left: ("l", points) a line, ("p", points) a closed shape, ("c", x, y, r) a circle.

def _figure(x0=0.0, k=1.0, arms="down"):  # a standing person, k high, its left foot at x0
    c = x0 + 0.22 * k
    hands = [(c - 0.18 * k, 0.46 * k), (c, 0.7 * k), (c + 0.18 * k, 0.46 * k)] if arms == "down" else \
            [(c - 0.2 * k, 1.04 * k), (c, 0.7 * k), (c + 0.2 * k, 1.04 * k)]
    return [("c", c, 0.89 * k, 0.1 * k), ("l", [(c, 0.79 * k), (c, 0.42 * k)]), ("l", hands),
            ("l", [(c - 0.14 * k, 0), (c, 0.42 * k), (c + 0.14 * k, 0)])]


def _wave(y, w=0.9, n=9, a=0.04):
    return ("l", [(w * i / (n - 1), y + a * math.sin(i * math.pi / 2)) for i in range(n)])


def _heart(cx, cy, s):
    ts = [i * math.pi / 12 for i in range(24)]
    return ("p", [(cx + s * 16 * math.sin(t) ** 3 / 17, cy + s * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 17) for t in ts])


def _sprout(x, y, h):  # a stem and a pair of leaves
    return [("l", [(x, y), (x, y + h)]), ("l", [(x - 0.1, y + 0.9 * h), (x, y + 0.5 * h), (x + 0.1, y + 0.9 * h)])]


def _box(x0, y0, x1, y1):
    return ("p", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


GLYPHS = {
    "person": (0.44, 1.0, _figure()),
    "child": (0.29, 0.65, _figure(0, 0.65)),
    "cheer": (0.44, 1.04, _figure(arms="up")),
    "people": (1.02, 1.0, _figure(0) + _figure(0.34, 0.65) + _figure(0.58)),
    "walker": (0.5, 1.0, [("c", 0.28, 0.89, 0.1), ("l", [(0.27, 0.79), (0.24, 0.42)]), ("l", [(0.1, 0.52), (0.27, 0.7), (0.42, 0.56)]),
                          ("l", [(0.04, 0), (0.24, 0.42), (0.46, 0)])]),
    "sitter": (0.72, 0.92, [("l", [(0, 0.38), (0.7, 0.38)]), ("l", [(0.05, 0.38), (0.05, 0)]), ("l", [(0.66, 0), (0.66, 0.66)]),
                            ("c", 0.5, 0.82, 0.1), ("l", [(0.5, 0.72), (0.52, 0.42), (0.26, 0.42), (0.22, 0)]), ("l", [(0.5, 0.66), (0.34, 0.5)])]),
    "cyclist": (1.0, 1.0, [("c", 0.2, 0.18, 0.18), ("c", 0.8, 0.18, 0.18), ("l", [(0.2, 0.18), (0.46, 0.18), (0.7, 0.44), (0.8, 0.18)]),
                           ("l", [(0.46, 0.18), (0.38, 0.46)]), ("c", 0.62, 0.92, 0.09), ("l", [(0.58, 0.83), (0.38, 0.5)]),
                           ("l", [(0.54, 0.76), (0.7, 0.5)]), ("l", [(0.38, 0.48), (0.54, 0.32), (0.48, 0.18)])]),
    "tree": (0.62, 1.45, [("l", [(0.31, 0), (0.31, 0.82)]), ("c", 0.31, 1.13, 0.31)]),
    "conifer": (0.5, 1.5, [("l", [(0.25, 0), (0.25, 0.3)]), ("p", [(0.25, 1.5), (0.5, 0.3), (0, 0.3)])]),
    "bench": (0.6, 0.45, [("l", [(0, 0.45), (0.6, 0.45)]), ("l", [(0, 0.25), (0.6, 0.25)]), ("l", [(0.06, 0.45), (0.06, 0)]), ("l", [(0.54, 0.45), (0.54, 0)])]),
    "table": (0.6, 0.4, [("l", [(0, 0.4), (0.6, 0.4)]), ("l", [(0.1, 0.4), (0.1, 0)]), ("l", [(0.5, 0.4), (0.5, 0)])]),
    "ball": (0.2, 0.2, [("c", 0.1, 0.1, 0.09)]),
    "house": (0.8, 1.0, [("p", [(0, 0), (0.8, 0), (0.8, 0.6), (0.4, 1.0), (0, 0.6)]), _box(0.32, 0, 0.48, 0.3)]),
    "block": (0.9, 1.4, [_box(0, 0, 0.9, 1.4)] + [_box(x, y, x + 0.12, y + 0.14) for x in (0.15, 0.39, 0.63) for y in (0.3, 0.65, 1.0)]),
    "tower": (0.5, 2.9, [_box(0, 0, 0.5, 2.3), ("p", [(0, 2.3), (0.25, 2.9), (0.5, 2.3)]), _box(0.19, 1.8, 0.31, 2.05)]),
    "stall": (0.9, 1.0, [("p", [(0, 0.72), (0.9, 0.72), (0.8, 1.0), (0.1, 1.0)]), ("l", [(0.1, 0.72), (0.1, 0)]), ("l", [(0.8, 0.72), (0.8, 0)]),
                         _box(0.1, 0, 0.8, 0.36)]),
    "bed": (0.8, 0.5, [_box(0, 0, 0.8, 0.16)] + [p for x in (0.16, 0.4, 0.64) for p in _sprout(x, 0.16, 0.34)]),
    "crop": (0.9, 0.44, [("l", [(0, 0), (0.9, 0)])] + [p for x in (0.1, 0.33, 0.56, 0.79) for p in _sprout(x, 0, 0.44)]),
    "water": (0.9, 0.3, [_wave(0.08), _wave(0.22)]),
    "sun": (0.6, 1.8, [("c", 0.3, 1.5, 0.13)] + [("l", [(0.3 + 0.19 * math.cos(a), 1.5 + 0.19 * math.sin(a)), (0.3 + 0.28 * math.cos(a), 1.5 + 0.28 * math.sin(a))])
                                                  for a in (i * math.pi / 4 for i in range(8))]),
    "wind": (0.9, 1.2, [("l", [(0, 1.0), (0.62, 1.0), (0.74, 1.06), (0.74, 1.15), (0.64, 1.16)]), ("l", [(0.1, 0.84), (0.82, 0.84), (0.9, 0.78), (0.86, 0.7), (0.78, 0.71)]),
                        ("l", [(0.05, 0.68), (0.5, 0.68)])]),
    "heart": (0.5, 1.35, [_heart(0.25, 1.1, 0.24)]),
    "bus": (1.4, 0.7, [_box(0, 0.1, 1.4, 0.68)] + [_box(x, 0.4, x + 0.22, 0.6) for x in (0.1, 0.42, 0.74, 1.06)] + [("c", 0.3, 0.1, 0.1), ("c", 1.1, 0.1, 0.1)]),
}
ALIASES = {"home": "house", "homes": "house", "market": "stall", "shop": "stall", "garden": "bed", "farm": "crop", "walk": "walker",
           "bike": "cyclist", "sit": "sitter", "play": ["child", "ball"], "community": "people", "group": "people"}


def glyphs_of(names, what):
    """The signs for a list of names, aliases opened; `what` names the element in the warning for an unknown one."""
    out = []
    for nm in names:
        g = ALIASES.get(nm, nm)
        for x in (g if isinstance(g, list) else [g]):
            if x in GLYPHS:
                out.append(GLYPHS[x])
            elif what:
                print(f"{what}: no sign '{nm}', left out; signs: {', '.join(sorted(GLYPHS))}; also {', '.join(sorted(ALIASES))}", file=sys.stderr)
    return out


def scene(gs, cx, gy, w, h, col, st, u=None, gap=0.12):
    """Signs side by side on one ground line at gy, centred on cx, fitting w by h px (or u px to a person's height).
    Their line thickens with their size, from the standard's `glyph` up to `heavy`. Returns the svg and the box it fills."""
    if not gs:
        return "", rect(cx, gy, cx, gy)
    tw = sum(g[0] for g in gs) + gap * (len(gs) - 1)
    u = u or min(w / tw, h / max(g[1] for g in gs))
    a = (f'stroke="{col}" stroke-width="{min(st["heavy"], max(st["glyph"], 0.018 * u)):.2f}" stroke-linecap="round" '
         f'stroke-linejoin="round"')
    x0 = x = cx - tw * u / 2
    out = []
    for gw, _, ps in gs:
        P = lambda pts: " ".join(f"{x + p * u:.1f},{gy - q * u:.1f}" for p, q in pts)
        for p in ps:
            if p[0] == "c":
                out.append(f'<circle cx="{x + p[1] * u:.1f}" cy="{gy - p[2] * u:.1f}" r="{p[3] * u:.1f}" fill="{st["paper"]}" {a}/>')
            else:
                out.append(f'<{"polygon" if p[0] == "p" else "polyline"} points="{P(p[1])}" fill="{st["paper"] if p[0] == "p" else "none"}" {a}/>')
        x += (gw + gap) * u
    return "".join(out), rect(x0, gy - max(g[1] for g in gs) * u, x0 + tw * u, gy)


def text_lines(st, lines, cx, y, col, size=None):  # centred lines of text from baseline y down, on a paper halo
    size = size or st["label_size"]
    return "".join(f'<text x="{cx:.1f}" y="{y + i * 1.2 * size:.1f}" text-anchor="middle" font-family="{esc(st["font"])}" font-size="{size}" '
                   f'fill="{col}" stroke="{st["paper"]}" stroke-width="{st["halo"]}" paint-order="stroke">{esc(l)}</text>' for i, l in enumerate(lines))


def tree_svg(v, st, p, e, col, hot):
    """A tree: a crown in plan with its trunk as a dot; seen from the side, a trunk and a round crown. Never smaller
    than the standard lets a person read, so it stays a tree at any scale. Returns the svg and its box on screen."""
    r = max(e.get("crown", 8) / 2 * v.s, 0.16 * st["figure"])
    x, y = v(p, 0)
    a = f'stroke="{col}" stroke-width="{st["glyph"]}"'
    tint = f'<circle cx="{x:.1f}" cy="{{0:.1f}}" r="{r:.1f}" fill="{st["accent"]}" fill-opacity="{st["tint_opacity"]}" stroke="none"/>' if hot else ""
    crown = lambda cy: f'<circle cx="{x:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{st["paper"]}" {a}/>' + tint.format(cy)
    if v.plan:
        return crown(y) + f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{max(0.7, r / 6):.1f}" fill="{col}"/>', Point(x, y).buffer(r)
    H = max(y - v(p, e.get("height", 12))[1], 2.6 * r)
    return f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y - H + 2 * r:.1f}" {a}/>' + crown(y - H + r), rect(x - r, y - H, x + r, y)


def icon_svg(st, sign, x, y, col):
    """A use or activity as a sign in a circle; a name the signs don't have is written as its first two letters."""
    r = st["icon"] / 2
    out = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{st["paper"]}" stroke="{col}" stroke-width="{st["glyph"]}"/>'
    gs = glyphs_of([sign], None)
    if gs:
        return out + scene(gs, x, y + 0.58 * r, 1.3 * r, 1.25 * r, col, st)[0]
    size = max(st["label_size"], round(r * 1.05))
    return out + (f'<text x="{x:.1f}" y="{y + 0.36 * size:.1f}" text-anchor="middle" font-family="{esc(st["font"])}" font-size="{size}" '
                  f'font-weight="bold" fill="{col}">{esc(str(sign)[:2])}</text>')


def vignette_svg(st, e, at, hot, obstacles, W, DH):
    """What people do at a place: a small round scene, set beside the place where it covers the least of `obstacles`,
    joined to it by a leader. Returns the svg and the shape it takes on screen."""
    R, ls = st["vignette"], st["label_size"]
    A, K = st["accent"], st["ink"]
    col = A if hot else K
    ax, ay = at
    lab = wrap(e.get("label", ""), max(6, int(2.6 * R / (0.56 * ls))))[:2] if e.get("label") else []
    shape_at = lambda cx, cy: Point(cx, cy).buffer(R).union(rect(cx - 1.3 * R, cy + R, cx + 1.3 * R, cy + R + 1.2 * ls * len(lab) + 4))
    frame = rect(4, 4, W - 4, DH - 4)
    if e.get("offset"):
        cx, cy = ax + e["offset"][0], ay + e["offset"][1]
    else:
        best = None
        for d in (R + 18, R + 45, R + 80):
            for k in range(8):
                a = math.pi / 4 * k + math.pi / 4
                cx, cy = ax + d * math.cos(a), ay - d * math.sin(a)
                b = shape_at(cx, cy)
                score = sum(wt * b.intersection(g).area for g, wt in obstacles) + 40 * (b.area - b.intersection(frame).area) + 0.5 * d
                if best is None or score < best[0]:
                    best = (score, cx, cy)
        _, cx, cy = best
    gs = glyphs_of(e.get("scene", ["people"]), "vignette")
    tw, th = (sum(g[0] for g in gs) + 0.12 * (len(gs) - 1), max(g[1] for g in gs)) if gs else (1, 1)
    t = 0.42  # the ground, as a share of R below the centre, raised until a low scene sits in the middle of its circle
    for _ in range(2):
        u = min(1.45 * math.sqrt(1 - t * t) * R / tw, (0.73 + t) * R / th)
        t = min(0.42, u * th / (2 * R) + 0.06)
    gy, half = cy + t * R, math.sqrt(1 - t * t) * R
    d = math.hypot(cx - ax, cy - ay) or 1
    lead = (f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{cx - R * (cx - ax) / d:.1f}" y2="{cy - R * (cy - ay) / d:.1f}" stroke="{col}" '
            f'stroke-width="{st["leader"]}"/><circle cx="{ax:.1f}" cy="{ay:.1f}" r="2" fill="{col}"/>') if d > R else ""
    disc = (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R}" fill="{st["paper"]}"/><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R}" '
            f'fill="{A if hot else st["paper"]}" fill-opacity="{st["tint_opacity"] if hot else 1}" stroke="{col}" stroke-width="{st["thin"]}"/>')
    ground = f'<line x1="{cx - half:.1f}" y1="{gy:.1f}" x2="{cx + half:.1f}" y2="{gy:.1f}" stroke="{col}" stroke-width="{st["glyph"]}"/>'
    return (lead + disc + ground + scene(gs, cx, gy, 0, 0, col, st, u)[0]
            + text_lines(st, lab, cx, cy + R + 1.1 * ls, col)), shape_at(cx, cy)


def metaphor_svg(st, e, hot, W, DH):
    """The idea as an image, without the site: two or three scenes side by side on one ground line, joined by arrows
    (or plus signs), all at one size so a person is as tall in each; the last one, the idea, in the accent."""
    ps = e.get("parts", [])
    k, ls = max(1, len(ps)), st["label_size"]
    pad, J = 16, 54
    pw = (W - 2 * pad - J * (k - 1)) / k
    gy = DH - pad - 2 * 1.2 * ls - 10
    H = gy - pad - 6
    gs = [glyphs_of(p.get("draw", []), "metaphor") for p in ps]
    u = min([min(0.85 * pw / (sum(g[0] for g in q) + 0.12 * (len(q) - 1)), H / max(g[1] for g in q)) for q in gs if q] or [H])
    tall = max([g[1] for q in gs for g in q] or [1]) * u
    gy = min(gy, (DH + tall - 2.6 * 1.2 * ls) / 2)  # the scenes and their words centred in the frame
    out = []
    for i, (p, q) in enumerate(zip(ps, gs)):
        cx = pad + pw / 2 + i * (pw + J)
        col = st["accent"] if hot and i == k - 1 else st["ink"]
        svg, b = scene(q, cx, gy, pw, H, col, st, u)
        w = max(b.bounds[2] - b.bounds[0], 0.3 * pw) / 2 + 10
        out.append(f'<line x1="{cx - w:.1f}" y1="{gy:.1f}" x2="{cx + w:.1f}" y2="{gy:.1f}" stroke="{col}" stroke-width="{st["line"]}"/>' + svg)
        out.append(text_lines(st, wrap(p.get("label", ""), int(pw / (0.56 * ls)))[:2], cx, gy + 1.6 * ls, col))
        if i:
            x, y = pad + i * (pw + J) - J / 2, gy - 0.45 * tall
            if e.get("join", "arrow") == "plus":
                out.append(f'<path d="M{x - 9:.1f},{y:.1f}h18M{x:.1f},{y - 9:.1f}v18" stroke="{st["ink"]}" stroke-width="{st["sign"]}"/>')
            else:
                out.append(f'<line x1="{x - J / 2 + 8:.1f}" y1="{y:.1f}" x2="{x + J / 2 - 10:.1f}" y2="{y:.1f}" stroke="{st["ink"]}" '
                           f'stroke-width="{st["sign"]}" marker-end="url(#ahK)"/>')
    return "".join(out)


# ---------- render ----------

def render(spec_path, out_dir):
    spec_path, out_dir = Path(os.path.abspath(spec_path)), Path(os.path.abspath(out_dir))
    sp = json.loads(spec_path.read_text(encoding="utf-8"))
    os.chdir(spec_path.parent)  # relative paths in the spec are relative to it
    st = {**FALLBACK_STYLE, **from_standard(spec_path), **sp.get("style", {})}   # the spec's `style` has the last word
    W, DH = sp.get("size", [600, 560])
    if (mm := frame_mm(spec_path, sp)):  # drawn to its frame: the drawing shrinks, the text keeps its size
        W, DH = round(mm / MM), round(DH * mm / MM / W)
    # the text under the drawing: title, a caption of up to two lines, a footer of up to two lines; it grows with the standard's sizes
    y1, y2, y3 = 0, 0, 0
    CAP = 0
    sequence = sp.get("mode", "sequence") == "sequence"

    project, site = (lambda g: g), None
    if sp.get("site"):
        project, site_ll = make_projection(sp["site"])
        whole = areal(project(site_ll), "site")
        site = areal(whole.simplify(sp.get("simplify", 30)), "site") if whole is not None else None
        if site is None or len(polygons(site)) != len(polygons(whole)) or len(rings_of(site)) != len(rings_of(whole)):
            print(f"site: simplify {sp.get('simplify', 30)} m loses polygons or holes; drawn unsimplified, lower `simplify`", file=sys.stderr)
            site = whole
    base = {}
    for b in sp.get("base", []):
        g = load_layer(b["geojson"], b.get("where"), project)
        if g is None:
            print(f"base layer '{b['name']}': nothing matched, left out", file=sys.stderr)
            continue
        g = g.simplify(b.get("simplify", 10))
        base[b["name"]] = dict(b, geom=g, shown=g.intersection(site.buffer(b.get("margin", 0))) if site is not None else g)

    # elements, numbered by the frame that introduces them
    els = []
    for n, fr in enumerate(sp["frames"], 1):
        for j, e in enumerate(fr.get("elements", [])):
            e = dict(e, frame=n)
            if e["kind"] == "tree":
                e.setdefault("height", 12)
            if e.get("slope"):
                e["height"] = max(e["slope"][0][2], e["slope"][1][2])
            if e["kind"] == "row":
                for g in row_segments(e, base, site, project):
                    els.append(dict(e, kind="volume", geom=g, row=f"{n}.{j}"))  # the label goes on the first piece left standing
            else:
                e["geom"] = element_geom(e, base, project)
                if e["geom"] is not None:
                    els.append(e)

    # a row stops where an earlier move cleared the ground
    clearing = lambda e: e["geom"] if "Line" not in e["geom"].geom_type else e["geom"].buffer(e.get("width", 20) / 2)
    els = [e for e in els if not (e.get("row") and any(c.get("clears") and c["frame"] < e["frame"] and
                                                          e["geom"].intersects(clearing(c)) for c in els))]

    # placeholder field: neutral blocks for moves to act on; not a design
    field = []
    fd = sp.get("field")
    if fd and site is not None:
        x0, y0, x1, y1 = site.bounds
        cell, half = fd.get("cell", 100), fd.get("size", 60) / 2
        keep_off = unary_union([base[k]["geom"] for k in fd.get("keep_off", []) if k in base]) if fd.get("keep_off") else None
        y = y0 + cell / 2
        while y < y1:
            x = x0 + cell / 2
            while x < x1:
                q = Polygon([(x - half, y - half), (x + half, y - half), (x + half, y + half), (x - half, y + half)])
                if site.contains(q) and (keep_off is None or q.distance(keep_off) > fd.get("keep_off_distance", 20)):
                    field.append(dict(kind="volume", geom=q, height=fd.get("height", 10), frame=0, placeholder=True))
                x += cell
            y += cell

    # which frame removes what: a 'clears' element takes away field blocks and earlier volumes it overlaps
    volumes = field + [e for e in els if e["kind"] == "volume"]
    for e in els:
        if not e.get("clears"):
            continue
        fp = clearing(e)
        for vol in volumes:
            zr = e["clears"] if isinstance(e["clears"], list) else None  # only what lies in this height range
            if zr and not (vol.get("base", 0) < zr[1] and vol.get("height", 10) > zr[0]):
                continue
            if vol is not e and vol["frame"] < e["frame"] + (0 if sequence else 1) and vol["geom"].intersection(fp).area > 1:
                if sequence or vol.get("placeholder"):
                    vol.setdefault("removed", {})
                    vol["removed"][e["frame"]] = True

    def top_of_set(es):  # the highest point drawn; separate frames fit their own, so one lifted frame does not shrink the others
        return max([e.get("height", e.get("z", 0)) + e.get("lift", 0) for e in es] +
                   [max((c[2] for c in e.get("coords", []) if len(c) > 2), default=0) for e in es if e["kind"] in ("arrow", "flow")] +
                   [fd.get("height", 10) if fd else 0])
    top = top_of_set(els)
    if site is not None:
        x0, y0, x1, y1 = site.bounds
        extent = [c for p in polygons(site.buffer(0.02 * max(x1 - x0, y1 - y0))) for c in p.exterior.coords]
    else:
        extent = [c for e in els for b in [e["geom"].bounds] for c in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))] or \
                 [(-50, -50), (50, -50), (50, 50), (-50, 50)]  # only whole-frame drawings (a metaphor): any square
    DH = min(DH, math.ceil(View(sp.get("view", {}), W, DH, extent, top).content_h))  # size is the most; no empty bands
    ts, cs, fz = st["title_size"], st["caption_size"], st["footer_size"]
    y1 = DH + 1.4 * ts
    y2 = y1 + 1.65 * cs
    y3 = y2 + 1.3 * cs + 2.7 * fz  # room for a caption of two lines
    CAP = math.ceil(y3 - DH + 1.9 * fz)

    W_, DH_ = W, DH  # a frame's size; a layer in a row of layers is drawn smaller

    def gone(vol, n):
        r = vol.get("removed", {})
        return any(m <= n for m in r) if sequence else (n in r)

    def frame_svg(n, fr, alone=None, size=None, tag=None):
        """One frame's drawing. With `alone` (frame numbers) only those frames' own moves, all as new, without people,
        signs or labels, at `size`: one layer in a row of layers."""
        comp = next((e for e in fr.get("elements", []) if e["kind"] in ("layers", "metaphor")), None)
        if comp and not alone:
            return composed(n, fr, comp)
        W, DH = size or (W_, DH_)
        tag = tag or n
        v = View(dict(sp.get("view", {}), **fr.get("view", {})), W, DH, extent,
                 top if sequence else top_of_set([e for e in els if e["frame"] in (alone or {n})]))  # a sequence keeps one view
        A, K = st["accent"], st["ink"]
        if alone:
            live = [e for e in els if e["frame"] in alone and e["kind"] not in ("person", "icon", "vignette")]
        else:
            live = [e for e in els if (e["frame"] == n) or (sequence and e["frame"] < n and
                                                             not e.get("only_here", e["kind"] in ("flow", "person", "icon", "vignette")))]
        live = [e for e in live if not (e["kind"] == "volume" and gone(e, max(alone or {n})))]
        new = (lambda e: e["frame"] in alone) if alone else (lambda e: e["frame"] == n)
        hot = lambda e: new(e) and e.get("accent", True)  # accent: false draws a new element in ink
        ground, vols, signs, labels, elabels, labelled = [], [], [], [], [], set()
        sl = lambda coords, z=0: LineString([v(c, z) for c in coords])  # on screen, to keep labels off the drawing
        obstacles = [(rect(W - 52, 14, W - 4, 72), 1)] if site is not None else []
        if site is not None:
            ground.append(poly(v, site, f'fill="{st["paper"]}" stroke="{K}" stroke-width="{st["outline"]}"'))
            for r in rings_of(site):
                obstacles.append((sl(r.coords).buffer(1.5), 0.3))
        clip = f' clip-path="url(#site{tag})"' if site is not None else ""
        surfaces = [e for e in live if e["kind"] in ("area", "strip", "point") and e.get("fill") != "none"]
        is_solid = lambda e: e.get("fill", "tint") == "solid" or e["kind"] == "point"
        drawn = {}
        for e in surfaces:  # a strip too narrow to see at this size is drawn at the standard's narrowest width
            drawn[id(e)] = e["geom"]
            if e.get("axis") is not None and e.get("width", 30) * v.s < st["min_width"]:
                drawn[id(e)] = e["axis"].buffer(st["min_width"] / v.s / 2, cap_style=2)
                if new(e) and not alone:
                    print(f"frame {n}: '{e.get('label') or e['kind']}' is {e.get('width', 30) * v.s:.1f} px wide here, drawn at min_width "
                          f"({st['min_width']} px); fewer, wider strips read better small", file=sys.stderr)
        for e in sorted(surfaces, key=lambda e: not is_solid(e)):  # solids first: a pale strip is never beneath one
            solid = is_solid(e)
            # an opening, or a pale strip over a solid, cuts its gap through the surfaces laid before it: the void reads as paper
            cut = [drawn[id(c)] for c in surfaces if c is not e and c["frame"] >= e["frame"] and
                   (c.get("clears") or (solid and c["kind"] == "strip" and not is_solid(c)))]
            g = drawn[id(e)].difference(unary_union(cut)) if cut else drawn[id(e)]
            if solid:
                for p in polygons(g):
                    obstacles.append((Polygon([v(c) for c in p.exterior.coords]), 1))
            if hot(e):  # a new tint keeps a thin edge, so a narrow one still reads small
                edge = "none" if solid else A
                attrs = f'fill="{A}" fill-opacity="{st["solid_opacity"] if solid else st["tint_opacity"]}" stroke="{edge}" stroke-width="{st["thin"]}"'
            else:
                edge = f'stroke="{K}" stroke-width="{st["hatch"]}"' if e["kind"] == "strip" else 'stroke="none"'
                attrs = f'fill="{K if e["kind"] == "point" else st["paper"]}" stroke="{K}" stroke-width="{st["thin"]}"' if solid else f'fill="url(#hatch)" {edge}'
            ground.append(f'<g{clip}>{poly(v, g, attrs, e.get("lift", 0))}</g>' + guides(v, st, e))
        for name, b in ({} if alone else base).items():
            hl = name in fr.get("highlight", [])
            w = st["heavy"] if b.get("weight") == "heavy" else st["line"] * 1.6
            dash = f' stroke-dasharray="{st["dash"]}"' if b.get("dashed") else ""
            if b.get("only_in") and n not in b["only_in"]:
                continue
            ground.append(line(v, b["shown"], f'stroke="{A if hl else K}" stroke-width="{w * (1.15 if hl else 0.65)}"{dash}'))
            for l in [l for l in parts(b["shown"]) if l.geom_type == "LineString"] + rings_of(b["shown"]):
                obstacles.append((sl(l.coords).buffer(w / 2 + 2), 1))
            if hl and b.get("label"):
                c = b["shown"].interpolate(0.5, normalized=True) if b["shown"].geom_type == "LineString" else b["shown"].representative_point()
                labels.append((v((c.x, c.y)), b["label"], A))
        ghost_attrs = f'fill="none" stroke="{A}" stroke-width="{st["ghost"]}" stroke-dasharray="{st["ghost_dash"]}"'
        for vol in volumes:  # ghosts of what this frame removes, drawn where they were
            if any(vol.get("removed", {}).get(m) for m in (alone or [n])):
                vols.append((-1e9, ghost(v, vol, ghost_attrs)))
        marked = unary_union([e["geom"] for e in live if new(e) and e.get("marks")] or [Polygon()])
        for vol in [f for f in field if not alone and not gone(f, n)] + [e for e in live if e["kind"] == "volume"]:
            fill = A if hot(vol) or marked.contains(vol["geom"].centroid) else st["paper"]
            z0 = vol.get("base", 0) + vol.get("lift", 0)
            cut_fill = fill if fill != st["paper"] else K  # what the cut passes through is solid: ink, or the accent if new
            if v.cut_z is not None:  # floor plan: above the cut dashed, cut solid, below outlined
                if z0 >= v.cut_z:
                    vols.append((-1e7, poly(v, vol["geom"], f'fill="none" stroke="{K}" stroke-width="{st["thin"]}" stroke-dasharray="{st["dash"]}"')))
                else:
                    cut = vol.get("height", 10) + vol.get("lift", 0) > v.cut_z
                    vols.append((-z0 if cut else 1e6 - z0, poly(v, vol["geom"], f'fill="{cut_fill if cut else fill}" stroke="{K}" stroke-width="{st["box"]}"')))
            elif v.sec:  # section: in front removed, cut solid, behind in elevation
                for part in parts(vol["geom"].intersection(v.behind)):
                    if part.geom_type == "Polygon" and part.area > 0.01:
                        vols.append((v.depth((part.centroid.x, part.centroid.y)) - z0 * 10, box(v, st, part, top_of(vol), fill, z0)))
                vols.append((-1e8, section_faces(v, st, vol, f'fill="{cut_fill}" stroke="{K}" stroke-width="{st["box"]}"')))
            else:
                for p in polygons(vol["geom"]):  # each part by its own depth, so a near one is drawn over a far one
                    vols.append((v.depth((p.centroid.x, p.centroid.y)) - z0 * 10, box(v, st, p, top_of(vol), fill, z0)))
            ground.append(guides(v, st, vol))
            for p in polygons(vol["geom"]):
                obstacles.append((shapely.MultiPoint([v(q, z) for q in p.exterior.coords for z in (z0, vol.get("height", 10) + vol.get("lift", 0))]).convex_hull, 1))
        for e in live:
            col = A if hot(e) else K
            if e["kind"] in ("arrow", "flow"):
                coords = [list(l.coords) for l in parts(e["geom"]) if l.geom_type == "LineString"]
                coords, more = coords[0], coords[1:]
                ends = e.get("ends", "end")
                mid = "tee" if ends == "stop" else ("ahA" if new(e) else "ahK")
                mk = f' marker-end="url(#{mid})"' + (f' marker-start="url(#{mid})"' if ends == "both" else "")
                lines = [coords] + more
                if e["kind"] == "flow":
                    (ax, ay), (bx, by) = coords[0][:2], coords[-1][:2]
                    L = math.hypot(bx - ax, by - ay) or 1
                    px, py = -(by - ay) / L, (bx - ax) / L
                    cnt, spr = e.get("count", 3), e.get("spread", 60)
                    offs = [spr * (i / (cnt - 1) - 0.5) for i in range(cnt)] if cnt > 1 else [0]
                    lines = [[(c[0] + px * o, c[1] + py * o, *c[2:]) for c in coords] for o in offs]
                z = e.get("z", 0)
                for l in lines:
                    scr = [v(c[:2], c[2] if len(c) > 2 else z) for c in l]
                    signs.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in scr)}" fill="none" stroke="{K if ends == "stop" else col}" '
                                 f'stroke-width="{st["sign"] if new(e) else st["sign_old"]}" stroke-linejoin="round"{mk}/>')
                    obstacles.append((LineString(scr).buffer(3), 1))
            elif e["kind"] == "rays" and new(e):
                x, y = v(e["at"], e.get("z", 0))
                obstacles.append((Point(x, y).buffer(30), 1))
                for i in range(7):
                    a = math.pi * (1.1 + i * 0.13)
                    signs.append(f'<line x1="{x + 16 * math.cos(a):.1f}" y1="{y + 12 * math.sin(a):.1f}" x2="{x + 28 * math.cos(a):.1f}" '
                                 f'y2="{y + 21 * math.sin(a):.1f}" stroke="{A}" stroke-width="{st["sign"]}"/>')
            elif e["kind"] == "tree":  # standing among the volumes, so a near building hides a far tree
                for p in parts(e["geom"]):
                    svg, b = tree_svg(v, st, (p.x, p.y), e, col, hot(e))
                    vols.append((v.depth((p.x, p.y)), svg))
                    obstacles.append((b, 1))
            elif e["kind"] == "person":  # upright at any view, a person tall as the standard's `figure`
                g = glyphs_of([e.get("pose", "person")], f"frame {n}: person")
                for p in parts(e["geom"]):
                    svg, b = scene(g, *v((p.x, p.y), e.get("z", 0)), 0, 0, col, st, st["figure"])
                    signs.append(svg)
                    obstacles.append((b, 1))
            elif e["kind"] == "icon":
                x, y = v(e["at"], e.get("z", 0))
                signs.append(icon_svg(st, e.get("sign", ""), x, y, col))
                obstacles.append((Point(x, y).buffer(st["icon"] / 2 + 1), 1))
            if e.get("row") and e.get("label") and new(e):  # a row is labelled once
                if e["row"] in labelled:
                    continue
                labelled.add(e["row"])
            if new(e) and e["kind"] != "vignette" and (e.get("label") or e["kind"] == "label"):
                at = e.get("label_at") or e.get("at") or (lambda c: (c.x, c.y))(e["geom"].representative_point())
                z = e.get("label_z", (e.get("height", 10) if e["kind"] == "volume" else e.get("z", 0)) + e.get("lift", 0))
                if e["kind"] in ("arrow", "flow") and e.get("coords") and len(e["coords"][0]) > 2 and not e.get("label_at"):  # a rising arrow: label its middle
                    mid = e["coords"][len(e["coords"]) // 2] if len(e["coords"]) > 2 else [(a + b) / 2 for a, b in zip(e["coords"][0], e["coords"][-1])]
                    at, z = mid[:2], e.get("label_z", mid[2])
                elabels.append((v(at, z), e.get("label") or e.get("text"), col if e["kind"] != "label" else e.get("color") == "accent" and A or K))
        vols.sort(key=lambda t: -t[0])
        if v.focus:
            obstacles.append((rect(W - 130, DH - 94, W, DH), 1))
        vigs = [e for e in live if e["kind"] == "vignette"]
        avoid = obstacles + ([(unary_union([Polygon([v(c) for c in p.exterior.coords]) for p in polygons(site)]), 0.15)]
                             if vigs and site is not None else [])  # a vignette prefers the paper around the site
        for e in vigs:  # set aside last, where the drawing is known
            svg, b = vignette_svg(st, e, v(e["at"], e.get("z", 0)), hot(e), avoid, W, DH)
            signs.append(svg)
            obstacles.append((b, 1))  # labels keep off it
            avoid.append((b, 1))
        txt = "" if alone else place_labels(st, elabels + labels, obstacles, W, DH, n)  # the move's labels first: they get the best places
        if v.elev:  # the ground the elevation stands on
            xs = [v(p)[0] for p in extent]
            ground.insert(0, f'<line x1="{min(xs) - 10:.1f}" y1="{v(extent[0])[1]:.1f}" x2="{max(xs) + 10:.1f}" y2="{v(extent[0])[1]:.1f}" '
                             f'stroke="{K}" stroke-width="{st["outline"] * 1.5}"/>')
        drawing = "".join(ground) + "".join(s for _, s in vols) + "".join(signs) + ("" if alone else locator(v, n))
        return v, f'{frame_defs(v, site, tag, W, DH)}<g clip-path="url(#frame{tag})">{drawing}{txt}</g>'

    def composed(n, fr, e):
        """A frame drawn whole: a metaphor without the site, or a row of layers, each of some frames' own move alone
        on the site, joined by plus signs, with an equals sign and all of them together if `sum` asks."""
        v = View(dict(sp.get("view", {}), **fr.get("view", {})), W, DH, extent, top)
        v.composed, hot = e["kind"], e.get("accent", True)
        if len(fr.get("elements", [])) > 1:
            print(f"frame {n}: a {e['kind']} frame shows only itself; its other elements are left out", file=sys.stderr)
        if e["kind"] == "metaphor":
            return v, f'{frame_defs(v, None, n, W, DH)}<g clip-path="url(#frame{n})">{metaphor_svg(st, e, hot, W, DH)}</g>'
        whole = lambda m: any(x["kind"] in ("layers", "metaphor") for x in sp["frames"][m - 1].get("elements", []))
        of = [m for m in e.get("of", range(1, n)) if 1 <= m <= len(sp["frames"]) and m != n and not whole(m)]
        names = e.get("labels") or [sp["frames"][m - 1].get("title", "") for m in of]
        cells = [({m}, names[i] if i < len(names) else "") for i, m in enumerate(of)]
        if e.get("sum") and of:
            cells.append((set(of), e["sum"] if isinstance(e["sum"], str) else ""))
        k, ls, J, pad = max(1, len(cells)), st["label_size"], 26, 10
        tw = (W - 2 * pad - J * (k - 1)) / k
        if tw < 90:
            print(f"frame {n}: {k} layers are {tw:.0f} px wide each; fewer layers, or a wider `size`", file=sys.stderr)
        lab_h, P = 2 * 1.2 * ls + 8, 16  # P: a view's own margin, which the row of layers lets overlap
        th = min(DH - lab_h - 2 * pad, math.ceil(View(sp.get("view", {}), tw + 2 * P, 10 * DH, extent, top).content_h) - 2 * P)
        y0 = (DH - th - lab_h) / 2
        out = []
        for i, (ms, name) in enumerate(cells):
            x = pad + i * (tw + J)
            m = max(ms)
            layer = frame_svg(m, sp["frames"][m - 1], ms, (tw + 2 * P, th + 2 * P), f"{n}l{i}")[1]
            out.append(f'<g transform="translate({x - P:.1f},{y0 - P:.1f})">{layer}</g>')
            out.append(text_lines(st, wrap(name, max(4, int(tw / (0.56 * ls))))[:2], x + tw / 2, y0 + th + 4 + ls, st["accent"] if hot else st["ink"]))
            if i:
                out.append(text_lines(st, ["=" if e.get("sum") and i == k - 1 else "+"], x - J / 2, y0 + th / 2 + 0.5 * ls, st["ink"], round(1.8 * ls)))
        return v, f'{frame_defs(v, None, n, W, DH)}<g clip-path="url(#frame{n})">{"".join(out)}</g>'

    def locator(v, n):  # a close-up shows where it is on the whole site
        if not v.focus or site is None:
            return ""
        lw, lh = 120, 84
        lv = View(dict(sp.get("view", {}), exaggerate=0), lw, lh, extent, 0)
        x0, y0, x1, y1 = v.focus
        tr = lambda pts: " ".join(f"{W - lw - 6 + x:.1f},{DH - lh - 6 + y:.1f}" for x, y in (lv(c) for c in pts))
        inset = lambda p: (W - lw - 6 + p[0], DH - lh - 6 + p[1])
        return (f'<rect x="{W - lw - 6}" y="{DH - lh - 6}" width="{lw}" height="{lh}" fill="{st["paper"]}" stroke="{st["ink"]}" stroke-width="{st["rule"]}"/>'
                f'<path d="{rings_d(lv, site, to=inset)}" fill="none" stroke="{st["ink"]}" stroke-width="{st["thin"]}" data-locator="site"/>'
                f'<polygon points="{tr([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])}" fill="none" stroke="{st["accent"]}" stroke-width="{st["sign"]}"/>')

    def footer(v, n):
        kinds = {e["kind"] for e in sp["frames"][n - 1].get("elements", [])}
        ill = " People and signs: illustrative." if kinds & {"person", "icon", "vignette", "metaphor"} else ""
        if sp.get("footer"):
            return sp["footer"] + ill
        if v.composed == "metaphor":
            return "A metaphor of the idea, not a drawing of the site." + ill
        shown = [b.get("label") or k for k, b in base.items() if not b.get("only_in") or n in b["only_in"]]
        data = (["site outline"] if site is not None else []) + list(dict.fromkeys(shown))
        src = sorted({Path(e["geojson"]).parent.name or Path(e["geojson"]).stem for e in els if e.get("geojson")})
        s = (f"Site data: {', '.join(data)}. " if data else "No site data: schematic. ")
        s += (f"From {', '.join(src)}: its GeoJSON. " if src else "")
        s += "Everything else: concept, positions and sizes assumed." + ill
        s += " Close-up, located in the inset." if v.focus else ""
        s += (" Section." if v.sec else " Elevation." if v.elev else " Plan." if v.cut_z is not None else "") + (" Not to scale" + (f", heights ×{v.ex:g}." if v.ex and top else ".") if not v.plan or site is None or v.composed else "")
        return s

    def scalebar(v):
        if not v.plan or site is None or v.composed:  # a schematic has no true size: no numbers on it
            return ""
        m = max([x for x in (50, 100, 200, 250, 500, 1000, 2000, 5000) if x * v.s < W / 4] or [50])
        x, y, L = 20 + st["small_size"], DH - 12 - 2 * st["small_size"], m * v.s
        t = f'font-family="{esc(st["font"])}" font-size="{st["small_size"]}" fill="{st["ink"]}" text-anchor="middle"'
        # a line that steps up and down, a tick and a number at every step
        n = next(n for n in ((4, 2, 1) if str(m)[0] == "2" else (5, 2, 1)) if L / n >= (len(f"{m:g}") + 1) * 0.6 * st["small_size"] + 3 or n == 1)
        s = L / n
        return (f'<path d="{"".join(f"M{x + i * s:.1f},{y + 4 * (i % 2)}h{s:.1f}" for i in range(n))}{"".join(f"M{x + i * s:.1f},{y}v4" for i in range(n + 1))}" '
                f'fill="none" stroke="{st["ink"]}" stroke-width="{st["rule"]}"/>'
                + "".join(f'<text x="{x + i * s:.1f}" y="{y + 6 + st["small_size"]}" {t}>{m * i / n:g}{" m" if i == n else ""}</text>' for i in range(n + 1)))

    def north(v):  # a circle in outline, a line from its centre to the circle, pointing north
        x, y = W - 26, 48
        dx, dy = (v(( 0, 120))[0] - v((0, 0))[0]), (v((0, 120))[1] - v((0, 0))[1])
        L = math.hypot(dx, dy) or 1
        return (f'<circle cx="{x}" cy="{y}" r="14" fill="none" stroke="{st["ink"]}" stroke-width="{st["sign_old"]}"/>'
                f'<line x1="{x}" y1="{y}" x2="{x + 14 * dx / L:.1f}" y2="{y + 14 * dy / L:.1f}" stroke="{st["ink"]}" stroke-width="{st["sign_old"]}"/>')

    def body(n, fr):
        v, drawing = frame_svg(n, fr)
        t = f'font-family="{esc(st["font"])}" fill="{st["ink"]}"'
        cap = fr.get("caption", "")
        lines = wrap(cap, min(90, int((W - 40) / (0.5 * st["caption_size"]))))
        if len(lines) > 2:  # two lines at most, so it never runs into the footer
            print(f"frame {n}: caption runs to {len(lines)} lines at this width; shorten it to two", file=sys.stderr)
        cap = "".join(f'<tspan x="20" dy="{1.3 * st["caption_size"] if i else 0}">{esc(l)}</tspan>' for i, l in enumerate(lines[:2]))
        fs = st["footer_size"]
        foot = "".join(f'<tspan x="20" dy="{1.3 * fs if i else 0}">{esc(l)}</tspan>' for i, l in enumerate(wrap(footer(v, n), int((W - 40) / (0.5 * fs)))[:2]))
        return v, (f'<rect width="{W}" height="{DH + CAP}" fill="{st["paper"]}"/>{drawing}{north(v) if site is not None and not v.elev and not v.composed else ""}{scalebar(v)}'
                   f'<line x1="20" y1="{DH}" x2="{W - 20}" y2="{DH}" stroke="{st["ink"]}" stroke-width="{st["rule"]}"/>'
                   f'<text x="20" y="{y1}" {t} font-size="{st["title_size"]}" font-weight="{st["title_weight"]}"><tspan fill="{st["accent"]}">{n}</tspan>  {esc(fr["title"])}</text>'
                   f'<text x="20" y="{y2}" {t} font-size="{st["caption_size"]}">{cap}</text>'
                   f'<text y="{y3}" {t} font-size="{fs}" font-style="{st["footer_style"]}">{foot}</text>')

    def doc(w, h, v, inner):  # print size in mm (CSS px at 96 dpi), so the panels place it at that size
        return (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="{w * MM:.2f}mm" height="{h * MM:.2f}mm" '
                f'viewBox="0 0 {w} {h}">\n{defs(st)}\n{inner}\n</svg>\n')

    out_dir.mkdir(parents=True, exist_ok=True)
    H = DH + CAP
    frames = sp["frames"]
    made, cells, first_v = [], [], None
    for n, fr in enumerate(frames, 1):
        v, inner = body(n, fr)
        first_v = first_v or v
        name = fr.get("file") or f"{n:02d}"
        if Path(name).name != name or name.startswith("."):  # never written outside the output folder
            sys.exit(f"frame {n}: file '{name}' must be a plain name, not a path")
        svg = out_dir / f"{name}.svg"
        svg.write_text(doc(W, H, v, inner), encoding="utf-8")
        made.append(svg)
        cells.append(inner)
    if len(frames) > 1:  # sheet: all frames at once, to read them as a set (only valid when they share one view)
        cols = 3 if len(frames) > 4 else len(frames)
        rows = math.ceil(len(frames) / cols)
        inner = f'<rect width="{cols * W}" height="{rows * H}" fill="{st["paper"]}"/>' + "".join(f'<g transform="translate({(i % cols) * W},{(i // cols) * H})">{c}</g>' for i, c in enumerate(cells))
        sheet = out_dir / "00_sheet.svg"
        sheet.write_text(doc(cols * W, rows * H, first_v, inner), encoding="utf-8")
        made.append(sheet)
    browser = find_browser()
    for svg in made:
        w, h = (W, H) if svg.name != "00_sheet.svg" else (cols * W, rows * H)
        if browser:
            try:
                subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                                f"--window-size={w},{h}", f"--screenshot={svg.with_suffix('.png')}", svg.as_uri()],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            except subprocess.TimeoutExpired:
                print(f"{svg.name}: the browser took too long, no PNG; the SVG is written", file=sys.stderr)
    if not browser:
        print("No Chrome, Edge or Chromium found: SVG only. Set CHROME_PATH to its executable.", file=sys.stderr)
    print(f"{len(frames)} frames ({'sequence' if sequence else 'separate'}), {len(field)} placeholder blocks, "
          f"{len([e for e in els if e['kind'] == 'volume'])} volumes, written to {out_dir}")


def find_browser():
    for p in [os.environ.get("CHROME_PATH")] + [shutil.which(n) for n in ("chrome", "google-chrome", "chromium", "chromium-browser", "msedge")] + [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]:
        if p and Path(p).exists():
            return p
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("info", "render"):
        sys.exit(__doc__)
    if sys.argv[1] == "info":
        info(sys.argv[2:])
    else:
        render(sys.argv[2], sys.argv[3])
