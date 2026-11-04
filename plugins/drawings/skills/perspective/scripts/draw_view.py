#!/usr/bin/env python3
"""Draws one eye-level base view of a scene: a shaded massing as SVG and PNG, a depth map and a map of what each pixel is."""
import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

import numpy as np
from shapely import STRtree, box
from shapely.geometry.polygon import orient
from shapely.ops import triangulate

W, H, HORIZON = 1536, 1024, 0.58   # the horizon sits low, as with a shift lens, so verticals stay vertical
MM_W, MM_H = 300, 200              # print size; a perspective has no scale
NEAR, FAR = 0.5, 700.0
FINE, COARSE, FINE_REACH = 10.0, 40.0, 160.0
STYLE = {"sky": "#ffffff", "ground": "#e4e4e4", "field": "#dcdcdc", "green": "#c9c9c9", "park": "#c4c4c4", "garden": "#cdcdcd",
         "water": "#8f8f8f", "street": "#b4b4b4", "old_street": "#bababa", "square": "#efefef", "rail": "#9d9d9d", "line": "#000000",
         "forest": "#8c8c8c", "scrub": "#a3a3a3", "tree": "#a6a6a6", "trunk": "#6e6e6e",
         "new": (205, 250), "kept": (170, 215), "context": (140, 190),
         "edge_base": .6, "edge_top": 1.2, "floor_line": .35, "corner": 1,
         "map_paper": "#fff", "map_tall": "#d0d0d0", "map_new": "#333", "map_kept": "#777", "map_context": "#bbb",
         "map_site": "#000", "map_view": "#e0301e"}
# the drawing standard's colours mapped onto these tones (tone: style.json key), never merged: there `line` is a weight,
# `new` one colour where here it is a range of greys, `tree` may be a symbol. The buildings keep their greys.
FROM_STANDARD = {"sky": "paper", "ground": "context", "field": "meadow", "green": "lawn", "park": "park", "garden": "lawn",
                 "water": "water", "street": "street", "old_street": "street", "square": "public", "line": "ink",
                 "forest": "grove", "scrub": "kept", "tree": "grove", "map_paper": "paper", "map_site": "ink", "map_view": "accent"}
CLASSES = {"sky": 0, "ground": 1, "street": 2, "green": 3, "water": 4, "new": 5, "kept": 6, "context": 7, "forest": 8, "scrub": 9, "tree": 10}
CLASS_OF_TONE = {"street": 2, "old_street": 2, "square": 2, "rail": 2, "green": 3, "park": 3, "garden": 3, "field": 1, "water": 4}


class Camera:
    def __init__(self, scene, view):
        self.ex, self.ey = view["x"], view["y"]
        self.ground = float(scene.ground(np.array([self.ex]), np.array([self.ey]))[0])
        self.ez = self.ground + view.get("eye_height", 1.65)
        h = math.radians(view["heading"])
        self.fx, self.fy = math.sin(h), math.cos(h)
        self.hfov = view.get("hfov", 70)
        self.f = W / 2 / math.tan(math.radians(self.hfov) / 2)
        self.cx, self.cy = W / 2, H * HORIZON

    def cam(self, x, y, z):
        dx, dy = x - self.ex, y - self.ey
        return (dx * self.fy - dy * self.fx, z - self.ez, dx * self.fx + dy * self.fy)

    def px(self, c):
        return self.cx + self.f * c[0] / c[2], self.cy - self.f * c[1] / c[2]

    def faces_frame(self, x, y, margin):
        c = self.cam(x, y, 0)
        return c[2] > -margin and abs(c[0]) <= (c[2] + margin) * math.tan(math.radians(self.hfov) / 2) * 1.05 + margin


def clip_near(pts):
    out = []
    for a, b in zip(pts, pts[1:] + pts[:1]):
        if a[2] >= NEAR:
            out.append(a)
        if (a[2] >= NEAR) != (b[2] >= NEAR):
            s = (NEAR - a[2]) / (b[2] - a[2])
            out.append(tuple(a[i] + s * (b[i] - a[i]) for i in range(3)))
    return out


def path(pts, fill):
    d = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"
    return f'<path d="{d}" fill="{fill}" stroke="{fill}" stroke-width=".7"/>'


def line(a, b, col, w):
    return f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{col}" stroke-width="{w}"/>'


def grey(v):
    v = round(v)
    return f"#{v:02x}{v:02x}{v:02x}"


class Buffers:
    """The depth map, as 1/Z, and which class each pixel shows."""

    def __init__(self):
        self.depth = np.zeros((H, W))
        self.ids = np.zeros((H, W), np.uint8)

    def fill(self, pts_cam, cam, cls, over=False):
        """A convex polygon, interpolating 1/Z. With over, it wins against a surface at the same depth, as cover on the ground does."""
        pts = clip_near(pts_cam)
        if len(pts) < 3:
            return
        uv = [cam.px(p) + (1 / p[2],) for p in pts]
        for i in range(1, len(uv) - 1):
            (x0, y0, a), (x1, y1, b), (x2, y2, c) = uv[0], uv[i], uv[i + 1]
            den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(den) < 1e-6:
                continue
            l, r = max(int(min(x0, x1, x2)), 0), min(int(max(x0, x1, x2)) + 1, W)
            t, e = max(int(min(y0, y1, y2)), 0), min(int(max(y0, y1, y2)) + 1, H)
            if l >= r or t >= e:
                continue
            xs, ys = np.meshgrid(np.arange(l, r) + .5, np.arange(t, e) + .5)
            w0 = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / den
            w1 = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / den
            w2 = 1 - w0 - w1
            inv = w0 * a + w1 * b + w2 * c
            limit = self.depth[t:e, l:r] * (.999 if over else 1)
            hit = (w0 >= 0) & (w1 >= 0) & (w2 >= 0) & (inv > limit)
            self.depth[t:e, l:r][hit] = inv[hit]
            self.ids[t:e, l:r][hit] = cls

    def disc(self, cx, cy, r, inv, cls):
        l, u = max(int(cx - r), 0), max(int(cy - r), 0)
        e, b = min(int(cx + r) + 1, W), min(int(cy + r) + 1, H)
        if l >= e or u >= b:
            return
        ys, xs = np.ogrid[u:b, l:e]
        hit = ((xs + .5 - cx) ** 2 + (ys + .5 - cy) ** 2 <= r * r) & (inv > self.depth[u:b, l:e])
        self.depth[u:b, l:e][hit] = inv
        self.ids[u:b, l:e][hit] = cls


def write_gray_png(path_, a):
    raw = b"".join(b"\0" + row.tobytes() for row in a)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    Path(path_).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", a.shape[1], a.shape[0], 8, 0, 0, 0, 0))
                            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def browser():
    for c in (os.environ.get("BROWSER"), shutil.which("chrome"), shutil.which("msedge"), shutil.which("google-chrome"), shutil.which("chromium")):
        if c:
            return c
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
        for rel in (r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe"):
            if base and (Path(base) / rel).exists():
                return str(Path(base) / rel)


def to_png(svg, png, width=W, height=H):
    """Returns False, without failing, when no browser can make the PNG."""
    b = browser()
    if not b:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "v.html"
        page.write_text(f'<!doctype html><style>*{{margin:0}}svg{{display:block;width:{width}px;height:{height}px}}</style>' + svg.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            subprocess.run([b, "--headless", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={tmp}/p", "--force-device-scale-factor=1",
                            f"--window-size={width},{height}", f"--screenshot={png.resolve()}", page.as_uri()], capture_output=True, timeout=120)
        except subprocess.TimeoutExpired:
            return False
    return png.exists()


def rings_xy(part):
    part = orient(part, 1.0)
    return [list(r.coords) for r in [part.exterior, *part.interiors]]


def polys(g):
    return [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and not p.is_empty]


def draw_ground(scene, cam, style, buf, items, tree):
    """The ground, cell by cell, so a hill can hide what lies behind it."""
    def cells():
        r = int(FAR / COARSE) + 2
        i0, j0 = int(cam.ex // COARSE), int(cam.ey // COARSE)
        for i in range(i0 - r, i0 + r + 1):
            for j in range(j0 - r, j0 + r + 1):
                x, y = (i + .5) * COARSE, (j + .5) * COARSE
                d = math.hypot(x - cam.ex, y - cam.ey)
                if d > FAR or not cam.faces_frame(x, y, COARSE):
                    continue
                if d > FINE_REACH:
                    yield i * COARSE, j * COARSE, COARSE
                else:
                    n = int(COARSE / FINE)
                    for a in range(n):
                        for b in range(n):
                            yield i * COARSE + a * FINE, j * COARSE + b * FINE, FINE

    flats = scene.flats
    for x, y, size in cells():
        xs = np.array([x, x + size, x + size, x])
        ys = np.array([y, y, y + size, y + size])
        zs = scene.ground(xs, ys)
        cor = [cam.cam(float(a), float(b), float(c)) for a, b, c in zip(xs, ys, zs)]
        near = clip_near(cor)
        if len(near) < 3:
            continue
        d = "M" + "L".join("%.1f %.1f" % cam.px(c) for c in near) + "Z"
        s = f'<path d="{d}" fill="{style["ground"]}"/>'   # no stroke: a stroke would rule lines across the ground
        buf.fill(cor, cam, CLASSES["ground"])
        cell = box(x, y, x + size, y + size)
        for i in sorted(tree.query(cell)):
            _, g, tone = flats[i]
            piece = g.intersection(cell)
            if piece.area > cell.area * .999:
                s = ""                                     # fully covered: bare ground under it would show as a seam
            for part in polys(piece):
                ring = list(part.exterior.coords)[:-1]
                rz = scene.ground(np.array([p[0] for p in ring]), np.array([p[1] for p in ring]))
                pts = clip_near([cam.cam(p[0], p[1], float(z)) for p, z in zip(ring, rz)])
                if len(pts) >= 3:
                    s += path([cam.px(c) for c in pts], style[tone])
                    for tri in triangulate(part):
                        if part.contains(tri.representative_point()):
                            corners = list(tri.exterior.coords)[:-1]
                            tz = scene.ground(np.array([p[0] for p in corners]), np.array([p[1] for p in corners]))
                            buf.fill([cam.cam(p[0], p[1], float(z)) for p, z in zip(corners, tz)], cam, CLASS_OF_TONE[tone], over=True)
        items.append((math.hypot(x + size / 2 - cam.ex, y + size / 2 - cam.ey) + size + 25, s))   # painted before the walls standing on it


def draw_block(scene, cam, style, buf, items, geom, height, tone, cls, floors=None, soft=False, outline=True):
    """Walls facing the eye, in short pieces so far-to-near painting stays right; the roof when the eye is above it."""
    line_col = style["line"]
    for part in polys(geom):
        bx, by = part.exterior.xy
        rz = scene.ground(np.array(bx), np.array(by))
        base = float(rz.min())
        top = float(scene.ground(np.array([part.centroid.x]), np.array([part.centroid.y]))[0]) + height
        for ring in rings_xy(part):
            for a, b in zip(ring, ring[1:]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                n = math.hypot(dx, dy)
                if n < 0.01:
                    continue
                nx, ny = dy / n, -dx / n
                if (cam.ex - a[0]) * nx + (cam.ey - a[1]) * ny <= 0:
                    continue
                mid = math.hypot((a[0] + b[0]) / 2 - cam.ex, (a[1] + b[1]) / 2 - cam.ey)
                if mid > FAR + n / 2:
                    continue
                if isinstance(tone, (tuple, list)):       # a list when it comes from a JSON style
                    lit = .5 + .5 * (nx * .6 + ny * .8)   # only separates the faces
                    fill = grey(tone[0] + (tone[1] - tone[0]) * lit)
                else:
                    fill = tone
                pieces = max(1, math.ceil(n / max(2.0, mid / 10)))
                for i in range(pieces):
                    s0, s1 = i / pieces, (i + 1) / pieces
                    p0 = (a[0] + dx * s0, a[1] + dy * s0)
                    p1 = (a[0] + dx * s1, a[1] + dy * s1)
                    t = top
                    if soft:                              # a drawing convention for a canopy, not data
                        t = base + height * (.86 + .28 * (math.sin(p0[0] * 12.9898 + p0[1] * 78.233) * 43758.5453 % 1))
                    quad_full = [cam.cam(*p0, base), cam.cam(*p1, base), cam.cam(*p1, t), cam.cam(*p0, t)]
                    quad = clip_near(quad_full)
                    if len(quad) < 3:
                        continue
                    q = [cam.px(c) for c in quad]
                    if max(x for x, _ in q) < 0 or min(x for x, _ in q) > W:
                        continue
                    buf.fill(quad_full, cam, cls)
                    s = path(q, fill)
                    if outline:
                        def seg(z, w):
                            ends = clip_near([cam.cam(*p0, z), cam.cam(*p1, z), cam.cam(*p1, z + .001)])
                            return line(cam.px(ends[0]), cam.px(ends[1]), line_col, w) if len(ends) >= 3 else ""
                        s += seg(base, style["edge_base"]) + seg(t, style["edge_top"])
                        if floors:
                            for k in range(1, int(floors)):
                                s += seg(base + k * (t - base) / floors, style["floor_line"])
                        if i == 0 and cam.cam(*p0, 0)[2] >= NEAR:
                            s += line(cam.px(cam.cam(*p0, base)), cam.px(cam.cam(*p0, t)), line_col, style["corner"])
                        if i == pieces - 1 and cam.cam(*p1, 0)[2] >= NEAR:
                            s += line(cam.px(cam.cam(*p1, base)), cam.px(cam.cam(*p1, t)), line_col, style["corner"])
                    items.append((math.hypot((p0[0] + p1[0]) / 2 - cam.ex, (p0[1] + p1[1]) / 2 - cam.ey), s))
        if top < cam.ez:
            roof = tone if isinstance(tone, str) else grey(tone[1])
            for tri in triangulate(part):
                if part.contains(tri.representative_point()):
                    pts = [cam.cam(x, y, top) for x, y in list(tri.exterior.coords)[:-1]]
                    near = clip_near(pts)
                    if len(near) >= 3:
                        buf.fill(pts, cam, cls)
                        items.append((math.hypot(tri.centroid.x - cam.ex, tri.centroid.y - cam.ey) + 1, path([cam.px(c) for c in near], roof)))


def from_standard(scene):
    """The tones <proposal>/drawing-graphics/style.json gives, through FROM_STANDARD; {} without it."""
    try:
        s = json.loads((scene.proposal / "drawing-graphics" / "style.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    tones = {k: s[v] for k, v in FROM_STANDARD.items() if isinstance(s.get(v), str) and re.fullmatch(r"#[0-9a-fA-F]{6}", s[v])}
    if tones and "tones from drawing-graphics/style.json" not in scene.used:
        scene.used.append("tones from drawing-graphics/style.json")
    return tones


def draw_view(scene, view, out, stem, style):
    """Writes <stem>_base.svg and .png, <stem>_depth.png and <stem>_ids.png. Returns what the view can't vouch for."""
    style = {**STYLE, **from_standard(scene), **style}
    cam = Camera(scene, view)
    buf, items = Buffers(), []
    tree = STRtree([g for _, g, _ in scene.flats]) if scene.flats else None
    if tree is not None:
        draw_ground(scene, cam, style, buf, items, tree)
    for b in scene.buildings:
        if b["geom"].centroid.distance(_point(cam)) > FAR + 100:
            continue
        draw_block(scene, cam, style, buf, items, b["geom"], b["height"], style[b["group"]], CLASSES[b["group"]],
                   floors=b.get("floors") if b["group"] == "new" else None)
    for g, h, tone in scene.tall:
        if g.distance(_point(cam)) > FAR:
            continue
        draw_block(scene, cam, style, buf, items, g, h, style[tone], CLASSES[tone], soft=True, outline=False)
    r_crown, near_trees = scene.assumed["tree_crown_radius"], 0
    for x, y, height in scene.trees:
        c0 = cam.cam(x, y, 0)
        if math.hypot(x - cam.ex, y - cam.ey) > FAR or c0[2] < NEAR:
            continue
        if c0[2] < 3:
            near_trees += 1
            continue
        z = float(scene.ground(np.array([x]), np.array([y]))[0])
        base, mid = cam.px(cam.cam(x, y, z)), cam.px(cam.cam(x, y, z + height - r_crown))
        r = cam.f * r_crown / c0[2]
        s = line(base, mid, style["trunk"], max(.6, cam.f * .3 / c0[2]))
        s += f'<circle cx="{mid[0]:.1f}" cy="{mid[1]:.1f}" r="{r:.1f}" fill="{style["tree"]}" stroke="{style["line"]}" stroke-width=".6"/>'
        items.append((math.hypot(x - cam.ex, y - cam.ey), s))
        buf.disc(mid[0], mid[1], r, 1 / c0[2], CLASSES["tree"])
    items.sort(key=lambda i: -i[0])
    sky = f'<rect width="{W}" height="{H}" fill="{style["sky"]}"/>'
    land = f'<rect y="{cam.cy:.1f}" width="{W}" height="{H - cam.cy:.1f}" fill="{style["ground"]}"/>'
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{MM_W}mm" height="{MM_H}mm" viewBox="0 0 {W} {H}">'
           + sky + land + "".join(s for _, s in items) + "</svg>")
    out.mkdir(parents=True, exist_ok=True)
    svg_path = out / f"{stem}_base.svg"
    svg_path.write_text(svg, encoding="utf-8")
    made_png = to_png(svg_path, out / f"{stem}_base.png")
    d = np.where(buf.depth > 0, 1 / np.maximum(buf.depth, 1e-9), np.inf)
    g = np.clip(1 - np.log(np.maximum(d, 2) / 2) / math.log(FAR / 2), 0, 1)
    write_gray_png(out / f"{stem}_depth.png", np.nan_to_num(g * 255, posinf=0).astype(np.uint8))
    write_gray_png(out / f"{stem}_ids.png", buf.ids * 20)
    shares = {name: round(float(np.mean(buf.ids == c)), 3) for name, c in CLASSES.items()}
    return {"png": made_png, "trees_too_near": near_trees, "frame_shares": shares}


def _point(cam):
    from shapely.geometry import Point
    return Point(cam.ex, cam.ey)


def draw_map(scene, views, out, stem, style=None):
    """A plan of the site with each camera on it, to check the choice at a glance."""
    st = {**STYLE, **from_standard(scene), **(style or {})}
    x0, y0, x1, y1 = scene.site.bounds
    m = 60
    k = 1000 / max(x1 - x0 + 2 * m, y1 - y0 + 2 * m)
    w, h = (x1 - x0 + 2 * m) * k, (y1 - y0 + 2 * m) * k
    pt = lambda x, y: ((x - x0 + m) * k, h - (y - y0 + m) * k)
    d = lambda ring: "M" + "L".join("%.1f %.1f" % pt(*c[:2]) for c in ring) + "Z"
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}"><rect width="100%" height="100%" fill="{st["map_paper"]}"/>']
    for g, _, _ in scene.tall:
        for part in polys(g):
            s.append(f'<path d="{d(part.exterior.coords)}" fill="{st["map_tall"]}"/>')
    for b in scene.buildings:
        fill = st["map_" + b["group"]]
        for part in polys(b["geom"]):
            s.append(f'<path d="{d(part.exterior.coords)}" fill="{fill}"/>')
    for part in polys(scene.site):
        s.append(f'<path d="{d(part.exterior.coords)}" fill="none" stroke="{st["map_site"]}" stroke-dasharray="6 4"/>')
    for v in views:
        ex, ey = pt(v["x"], v["y"])
        for turn in (-1, 1):
            a = math.radians(v["heading"] + turn * v.get("hfov", 70) / 2)
            s.append(f'<line x1="{ex:.1f}" y1="{ey:.1f}" x2="{ex + 70 * math.sin(a):.1f}" y2="{ey - 70 * math.cos(a):.1f}" stroke="{st["map_view"]}" stroke-width="2"/>')
        s.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="6" fill="{st["map_view"]}"/><text x="{ex + 9:.1f}" y="{ey - 9:.1f}" font-family="sans-serif" font-size="18" fill="{st["map_view"]}">{v["name"]}</text>')
    s.append("</svg>")
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{stem}.svg"
    p.write_text("".join(s), encoding="utf-8")
    to_png(p, out / f"{stem}.png", round(w), round(h))
