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

# The look is not this script's to choose: every key can be set from the project's drawing standard (spec `style`).
# These values are only the studio's fallback when there is none: black lines on white, one accent colour.
FALLBACK_STYLE = {
    "ink": "#000", "paper": "#fff", "accent": "#d0312d", "font": "Helvetica, Arial, sans-serif",
    # line weights, px at the drawing's size
    "outline": 1.3, "line": 0.8, "heavy": 3.2, "box": 0.6, "thin": 0.7, "hatch": 0.5, "rule": 0.5,
    "sign": 1.5, "sign_old": 0.9, "ghost": 0.9, "leader": 0.6, "tee": 2.5, "halo": 3,
    "dash": "5 3", "ghost_dash": "3 2", "tint_opacity": 0.2, "solid_opacity": 0.85,
    # text sizes, px
    "label_size": 11, "small_size": 9, "title_size": 16, "title_weight": "bold",
    "caption_size": 11.5, "footer_size": 8.5, "footer_style": "italic",
}


MM = 25.4 / 96  # mm per CSS px


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


def parts(g):
    return list(g.geoms) if hasattr(g, "geoms") else [g]


# ---------- info ----------

def info(args):
    site_path = args[args.index("--site") + 1]
    project, _ = make_projection(site_path)
    site = project(unary_union([shape(f["geometry"]) for f in read_features(site_path)]))
    x0, y0, x1, y1 = site.bounds
    print(f"site: {site.area / 1e4:.1f} ha, x {x0:.0f}..{x1:.0f} m, y {y0:.0f}..{y1:.0f} m (0,0 = centre)")
    outline = max(parts(site.simplify(30)), key=lambda p: p.area)
    print("outline, simplified 30 m:", " ".join(f"{x:.0f},{y:.0f}" for x, y in outline.exterior.coords))
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
    def __init__(self, v, width, height, extent, top):
        self.plan = v.get("type", "iso") == "plan"
        self.th = math.radians(v.get("rotation", 0 if self.plan else 30))
        self.sq = 1.0 if self.plan else v.get("tilt", 0.55)
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
        return g.buffer(e["width"] / 2, cap_style=2) if k == "strip" and g is not None else g
    if k in ("area", "volume"):
        return Polygon(e["coords"])
    if k == "strip":
        return LineString(e["coords"]).buffer(e.get("width", 30) / 2, cap_style=2)
    if k == "point":
        return Point(e["at"]).buffer(e.get("radius", 40))
    if k in ("arrow", "flow"):
        return LineString(e["coords"])
    if k in ("label", "rays"):
        return Point(e["at"])
    if k == "row":
        return None
    raise ValueError(f"unknown element kind: {k}")


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
    clip = f'<clipPath id="site{n}"><polygon points="{v.pts(site.exterior.coords)}"/></clipPath>' if site is not None else ""
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
    q = list(g.exterior.coords)[:-1]
    if v.plan:
        return f'<polygon points="{v.pts(q)}" fill="{fill}" stroke="{st["ink"]}" stroke-width="{st["box"]}"/>'
    sides = sorted(zip(q, q[1:] + q[:1]), key=lambda s: -v.depth(((s[0][0] + s[1][0]) / 2, (s[0][1] + s[1][1]) / 2)))
    face = lambda f: (f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in f)}" fill="{fill}" '
                      f'stroke="{st["ink"]}" stroke-width="{st["box"]}" stroke-linejoin="round"/>')
    return "".join(face([v(a, z0), v(b, z0), v(b, h), v(a, h)]) for a, b in sides) + face([v(p, h) for p in q])


def poly(v, g, attrs, z=0):
    return "".join(f'<polygon points="{v.pts(p.exterior.coords, z)}" {attrs}/>' for p in parts(g) if p.geom_type == "Polygon")


def line(v, g, attrs, z=0):
    return "".join(f'<polyline points="{v.pts(l.coords, z)}" fill="none" {attrs}/>' for l in parts(g) if l.geom_type == "LineString")


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


# ---------- render ----------

def render(spec_path, out_dir):
    spec_path, out_dir = Path(os.path.abspath(spec_path)), Path(os.path.abspath(out_dir))
    sp = json.loads(spec_path.read_text(encoding="utf-8"))
    os.chdir(spec_path.parent)  # relative paths in the spec are relative to it
    st = dict(FALLBACK_STYLE, **sp.get("style", {}))
    W, DH = sp.get("size", [600, 560])
    # the text under the drawing: title, one-line caption, a footer of up to two lines; it grows with the standard's sizes
    y1, y2, y3 = 0, 0, 0
    CAP = 0
    sequence = sp.get("mode", "sequence") == "sequence"

    project, site = (lambda g: g), None
    if sp.get("site"):
        project, site_ll = make_projection(sp["site"])
        site = max(parts(project(site_ll).simplify(sp.get("simplify", 30))), key=lambda p: p.area)
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
            if e["kind"] == "row":
                for g in row_segments(e, base, site, project):
                    els.append(dict(e, kind="volume", geom=g, row=f"{n}.{j}"))  # the label goes on the first piece left standing
            else:
                e["geom"] = element_geom(e, base, project)
                if e["geom"] is not None:
                    els.append(e)

    # a row stops where an earlier move cleared the ground
    clearing = lambda e: e["geom"] if e["geom"].geom_type != "LineString" else e["geom"].buffer(e.get("width", 20) / 2)
    els = [e for e in els if not (e.get("along") and any(c.get("clears") and c["frame"] < e["frame"] and
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
            if vol is not e and vol["frame"] < e["frame"] + (0 if sequence else 1) and vol["geom"].intersection(fp).area > 1:
                if sequence or vol.get("placeholder"):
                    vol.setdefault("removed", {})
                    vol["removed"][e["frame"]] = True

    top = max([e.get("height", 0) for e in els] + [fd.get("height", 10) if fd else 0])
    if site is not None:
        x0, y0, x1, y1 = site.bounds
        extent = list(site.buffer(0.02 * max(x1 - x0, y1 - y0)).exterior.coords)
    else:
        extent = [c for e in els for c in (e["geom"].envelope.exterior.coords if e["geom"].area else e["geom"].coords)]
    DH = min(DH, math.ceil(View(sp.get("view", {}), W, DH, extent, top).content_h))  # size is the most; no empty bands
    ts, cs, fz = st["title_size"], st["caption_size"], st["footer_size"]
    y1 = DH + 1.4 * ts
    y2 = y1 + 1.65 * cs
    y3 = y2 + 2.7 * fz
    CAP = math.ceil(y3 - DH + 1.9 * fz)

    def gone(vol, n):
        r = vol.get("removed", {})
        return any(m <= n for m in r) if sequence else (n in r)

    def frame_svg(n, fr):
        v = View(dict(sp.get("view", {}), **fr.get("view", {})), W, DH, extent, top)
        A, K = st["accent"], st["ink"]
        live = [e for e in els if (e["frame"] == n) or (sequence and e["frame"] < n and not e.get("only_here", e["kind"] == "flow"))]
        live = [e for e in live if not (e["kind"] == "volume" and gone(e, n))]
        new = lambda e: e["frame"] == n
        hot = lambda e: new(e) and e.get("accent", True)  # accent: false draws a new element in ink
        ground, vols, signs, labels, elabels, labelled = [], [], [], [], [], set()
        sl = lambda coords, z=0: LineString([v(c, z) for c in coords])  # on screen, to keep labels off the drawing
        obstacles = [(rect(W - 52, 14, W - 4, 72), 1)] if site is not None else []
        if site is not None:
            ground.append(poly(v, site, f'fill="{st["paper"]}" stroke="{K}" stroke-width="{st["outline"]}"'))
            obstacles.append((sl(site.exterior.coords).buffer(1.5), 0.3))
        clip = f' clip-path="url(#site{n})"' if site is not None else ""
        for e in live:
            if e["kind"] in ("area", "strip", "point") and e.get("fill") != "none":
                solid = e.get("fill", "tint") == "solid" or e["kind"] == "point"
                if solid:
                    obstacles.append((Polygon([v(c) for c in e["geom"].exterior.coords]), 1))
                if hot(e):
                    attrs = f'fill="{A}" fill-opacity="{st["solid_opacity"] if solid else st["tint_opacity"]}" stroke="none"'
                else:
                    attrs = f'fill="{K if e["kind"] == "point" else st["paper"]}" stroke="{K}" stroke-width="{st["thin"]}"' if solid else 'fill="url(#hatch)" stroke="none"'
                ground.append(f'<g{clip}>{poly(v, e["geom"], attrs)}</g>')
        for name, b in base.items():
            hl = name in fr.get("highlight", [])
            w = st["heavy"] if b.get("weight") == "heavy" else st["line"] * 1.6
            dash = f' stroke-dasharray="{st["dash"]}"' if b.get("dashed") else ""
            if b.get("only_in") and n not in b["only_in"]:
                continue
            ground.append(line(v, b["shown"], f'stroke="{A if hl else K}" stroke-width="{w * (1.15 if hl else 0.65)}"{dash}'))
            for l in parts(b["shown"]):
                if l.geom_type == "LineString":
                    obstacles.append((sl(l.coords).buffer(w / 2 + 2), 1))
            if hl and b.get("label"):
                c = b["shown"].interpolate(0.5, normalized=True) if b["shown"].geom_type == "LineString" else b["shown"].representative_point()
                labels.append((v((c.x, c.y)), b["label"], A))
        for vol in volumes:  # ghosts of what this frame removes
            if vol.get("removed", {}).get(n):
                ground.append(poly(v, vol["geom"], f'fill="none" stroke="{A}" stroke-width="{st["ghost"]}" stroke-dasharray="{st["ghost_dash"]}"'))
        marked = unary_union([e["geom"] for e in live if new(e) and e.get("marks")] or [Polygon()])
        for vol in [f for f in field if not gone(f, n)] + [e for e in live if e["kind"] == "volume"]:
            fill = A if hot(vol) or marked.contains(vol["geom"].centroid) else st["paper"]
            c = vol["geom"].centroid
            vols.append((v.depth((c.x, c.y)) - vol.get("base", 0) * 10, box(v, st, vol["geom"], vol.get("height", 10), fill, vol.get("base", 0))))
            q = vol["geom"].exterior.coords
            obstacles.append((shapely.MultiPoint([v(p, z) for p in q for z in (vol.get("base", 0), vol.get("height", 10))]).convex_hull, 1))
        for e in live:
            col = A if hot(e) else K
            if e["kind"] in ("arrow", "flow"):
                coords = list(e["geom"].coords)
                ends = e.get("ends", "end")
                mid = "tee" if ends == "stop" else ("ahA" if new(e) else "ahK")
                mk = f' marker-end="url(#{mid})"' + (f' marker-start="url(#{mid})"' if ends == "both" else "")
                lines = [coords]
                if e["kind"] == "flow":
                    (ax, ay), (bx, by) = coords[0], coords[-1]
                    L = math.hypot(bx - ax, by - ay) or 1
                    px, py = -(by - ay) / L, (bx - ax) / L
                    cnt, spr = e.get("count", 3), e.get("spread", 60)
                    offs = [spr * (i / (cnt - 1) - 0.5) for i in range(cnt)] if cnt > 1 else [0]
                    lines = [[(x + px * o, y + py * o) for x, y in coords] for o in offs]
                for l in lines:
                    signs.append(f'<polyline points="{v.pts(l, e.get("z", 0))}" fill="none" stroke="{K if ends == "stop" else col}" '
                                 f'stroke-width="{st["sign"] if new(e) else st["sign_old"]}"{mk}/>')
                    obstacles.append((sl(l, e.get("z", 0)).buffer(3), 1))
            elif e["kind"] == "rays" and new(e):
                x, y = v(e["at"], e.get("z", 0))
                obstacles.append((Point(x, y).buffer(30), 1))
                for i in range(7):
                    a = math.pi * (1.1 + i * 0.13)
                    signs.append(f'<line x1="{x + 16 * math.cos(a):.1f}" y1="{y + 12 * math.sin(a):.1f}" x2="{x + 28 * math.cos(a):.1f}" '
                                 f'y2="{y + 21 * math.sin(a):.1f}" stroke="{A}" stroke-width="{st["sign"]}"/>')
            if e.get("row") and e.get("label") and new(e):  # a row is labelled once
                if e["row"] in labelled:
                    continue
                labelled.add(e["row"])
            if e.get("label") and new(e) or e["kind"] == "label" and new(e):
                at = e.get("label_at") or e.get("at") or (lambda c: (c.x, c.y))(e["geom"].representative_point())
                z = e.get("label_z", e.get("height", e.get("z", 0)) if e["kind"] == "volume" else e.get("z", 0))
                elabels.append((v(at, z), e.get("label") or e.get("text"), col if e["kind"] != "label" else e.get("color") == "accent" and A or K))
        vols.sort(key=lambda t: -t[0])
        if v.focus:
            obstacles.append((rect(W - 130, DH - 94, W, DH), 1))
        txt = place_labels(st, elabels + labels, obstacles, W, DH, n)  # the move's labels first: they get the best places
        drawing = "".join(ground) + "".join(s for _, s in vols) + "".join(signs) + locator(v, n)
        return v, f'{frame_defs(v, site, n, W, DH)}<g clip-path="url(#frame{n})">{drawing}{txt}</g>'

    def locator(v, n):  # a close-up shows where it is on the whole site
        if not v.focus or site is None:
            return ""
        lw, lh = 120, 84
        lv = View(dict(sp.get("view", {}), exaggerate=0), lw, lh, extent, 0)
        x0, y0, x1, y1 = v.focus
        tr = lambda pts: " ".join(f"{W - lw - 6 + x:.1f},{DH - lh - 6 + y:.1f}" for x, y in (lv(c) for c in pts))
        return (f'<rect x="{W - lw - 6}" y="{DH - lh - 6}" width="{lw}" height="{lh}" fill="{st["paper"]}" stroke="{st["ink"]}" stroke-width="{st["rule"]}"/>'
                f'<polygon points="{tr(site.exterior.coords)}" fill="none" stroke="{st["ink"]}" stroke-width="{st["thin"]}"/>'
                f'<polygon points="{tr([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])}" fill="none" stroke="{st["accent"]}" stroke-width="{st["sign"]}"/>')

    def footer(v, n):
        if sp.get("footer"):
            return sp["footer"]
        shown = [b.get("label") or k for k, b in base.items() if not b.get("only_in") or n in b["only_in"]]
        data = (["site outline"] if site is not None else []) + list(dict.fromkeys(shown))
        src = sorted({Path(e["geojson"]).parent.name or Path(e["geojson"]).stem for e in els if e.get("geojson")})
        s = (f"Site data: {', '.join(data)}. " if data else "No site data: schematic. ")
        s += (f"From {', '.join(src)}: its GeoJSON. " if src else "")
        s += "Everything else: concept, positions and sizes assumed."
        s += " Close-up, located in the inset." if v.focus else ""
        s += " Not to scale" + (f", heights ×{v.ex:g}." if v.ex and top else ".") if not v.plan else ""
        return s

    def scalebar(v):
        if not v.plan:
            return ""
        m = max([x for x in (50, 100, 200, 250, 500, 1000, 2000, 5000) if x * v.s < W / 4] or [50])
        x, y, L = 20, DH - 18, m * v.s
        t = f'font-family="{esc(st["font"])}" font-size="{st["small_size"]}" fill="{st["ink"]}"'
        return (f'<rect x="{x}" y="{y}" width="{L / 2:.1f}" height="4" fill="{st["ink"]}"/><rect x="{x + L / 2:.1f}" y="{y}" width="{L / 2:.1f}" height="4" '
                f'fill="{st["paper"]}" stroke="{st["ink"]}" stroke-width="{st["rule"]}"/><text x="{x}" y="{y - 4}" {t}>0</text><text x="{x + L:.1f}" y="{y - 4}" {t} text-anchor="end">{m} m</text>')

    def north(v):
        x, y = W - 26, 48
        dx, dy = (v(( 0, 120))[0] - v((0, 0))[0]), (v((0, 120))[1] - v((0, 0))[1])
        L = math.hypot(dx, dy) or 1
        dx, dy = 28 * dx / L, 28 * dy / L
        return (f'<line x1="{x - dx / 2:.1f}" y1="{y - dy / 2:.1f}" x2="{x + dx / 2:.1f}" y2="{y + dy / 2:.1f}" stroke="{st["ink"]}" stroke-width="{st["sign_old"]}" marker-end="url(#ahK)"/>'
                f'<text x="{x + dx / 2 + 4:.1f}" y="{y + dy / 2 - 2:.1f}" font-family="{esc(st["font"])}" font-size="{st["small_size"]}" fill="{st["ink"]}">N</text>')

    def body(n, fr):
        v, drawing = frame_svg(n, fr)
        t = f'font-family="{esc(st["font"])}" fill="{st["ink"]}"'
        cap = fr.get("caption", "")
        fits = min(90, int((W - 40) / (0.5 * st["caption_size"])))
        if len(cap) > fits:  # one line, so it never runs into the footer
            print(f"frame {n}: caption is {len(cap)} characters; keep it to one line, about {fits}", file=sys.stderr)
        fs = st["footer_size"]
        foot = "".join(f'<tspan x="20" dy="{1.3 * fs if i else 0}">{esc(l)}</tspan>' for i, l in enumerate(wrap(footer(v, n), int((W - 40) / (0.5 * fs)))[:2]))
        return v, (f'<rect width="{W}" height="{DH + CAP}" fill="{st["paper"]}"/>{drawing}{north(v) if site is not None else ""}{scalebar(v)}'
                   f'<line x1="20" y1="{DH}" x2="{W - 20}" y2="{DH}" stroke="{st["ink"]}" stroke-width="{st["rule"]}"/>'
                   f'<text x="20" y="{y1}" {t} font-size="{st["title_size"]}" font-weight="{st["title_weight"]}"><tspan fill="{st["accent"]}">{n}</tspan>  {esc(fr["title"])}</text>'
                   f'<text x="20" y="{y2}" {t} font-size="{st["caption_size"]}">{esc(cap)}</text>'
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
        svg = out_dir / f"{name}.svg"
        svg.write_text(doc(W, H, v, inner), encoding="utf-8")
        made.append(svg)
        cells.append(inner)
    if len(frames) > 1:  # sheet: all frames at once, to read them as a set (only valid when they share one view)
        cols = 3 if len(frames) > 4 else len(frames)
        rows = math.ceil(len(frames) / cols)
        inner = "".join(f'<g transform="translate({(i % cols) * W},{(i // cols) * H})">{c}</g>' for i, c in enumerate(cells))
        sheet = out_dir / "00_sheet.svg"
        sheet.write_text(doc(cols * W, rows * H, first_v, inner), encoding="utf-8")
        made.append(sheet)
    browser = find_browser()
    for svg in made:
        w, h = (W, H) if svg.name != "00_sheet.svg" else (cols * W, rows * H)
        if browser:
            subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                            f"--window-size={w},{h}", f"--screenshot={svg.with_suffix('.png')}", svg.as_uri()],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
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
