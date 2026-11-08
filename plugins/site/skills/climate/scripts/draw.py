"""Draw the climate layers as maps: SVG with a PNG next to each, with legend, north arrow, scale bar and sources.
The look comes from a style JSON made from drawing-graphics/standard.md; without one, black on white with one accent.

python draw.py --site SITE_DIR --out CLIMATE_DIR [--style style.json] [--scale 5000] [--margin 300] [--frame W H] [--centre LON LAT]

style.json keys (all optional): paper, ink, accent, context, existing (the buildings, else context), cool (else the
standard's park, kept or grove green), water, font, thin, mid, thick (mm), text, title (mm), ramp (list of colours, light to dark); its `diagram` line weights and text sizes (px) replace thin, mid, thick, text, title.
A frame of a climate map in the panels' plan (<proposal>/panel-layout/layout-plan.json, else layout.json; else --frame)
gives every map its size in mm, its scale and centre (`frame.centre`, else the site's): the map fills the frame, its
title, short legend, north arrow and scale bar in a box inside it.
"""
import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

import shapely
import shapely.ops
from shapely.geometry import box

from common import Site, read

FALLBACK = dict(paper="#ffffff", ink="#000000", accent="#d7263d", context="#c9c9c9", existing="#c9c9c9", water="#e4e4e4",
                font="Helvetica, Arial, sans-serif", thin=0.1, mid=0.25, thick=0.6, text=3.2, title=5.0)
MIN_TEXT = 3.2  # mm; no text is smaller than 12 px printed (9 pt, 3.17 mm), source lines and scale bars included
SCALES = [500, 1000, 2000, 2500, 5000, 7500, 10000, 15000, 20000, 25000, 50000]


def hex2rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def mix(a, b, t):
    a, b = hex2rgb(a), hex2rgb(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def ramp(n, st):
    """n colours light to dark: the standard's ramp, else paper -> accent -> towards ink."""
    if st.get("ramp") and len(st["ramp"]) >= 2:
        r = st["ramp"]
        return [r[round(i * (len(r) - 1) / max(n - 1, 1))] for i in range(n)]
    out = []
    for i in range(n):
        t = i / max(n - 1, 1)
        out.append(mix(st["paper"], st["accent"], 0.15 + 0.85 * t / 0.75) if t <= 0.75 else mix(st["accent"], st["ink"], (t - 0.75) * 1.6))
    return out


def axis(g):
    """A shape's long axis: its length, its width (area over length) and a unit vector along it."""
    r = list(g.minimum_rotated_rectangle.exterior.coords)
    e = max(((r[i + 1][0] - r[i][0], r[i + 1][1] - r[i][1]) for i in range(2)), key=lambda v: math.hypot(*v))
    L = math.hypot(*e) or 1
    return L, g.area / L, (e[0] / L, e[1] / L)


def soft(g, n=3):
    """A soft edge that never leaves the outline: the shape and n-1 copies shrunk inward, drawn one over the other."""
    w = axis(g)[1]
    return [p for p in [g] + [g.buffer(-w * 0.15 * i) for i in range(1, n)] if not p.is_empty]


def midline(g, c, e, a, b, n=12):
    """The middle of shape g from a to b metres along direction e from c: the centre of its cross-section at n steps,
    so a line along it follows its curve; a straight line where g has no section."""
    pts = []
    for i in range(n):
        t = a + (b - a) * i / (n - 1)
        x, y, big = c.x + e[0] * t, c.y + e[1] * t, 1e5
        cut = shapely.LineString([(x - e[1] * big, y + e[0] * big), (x + e[1] * big, y - e[0] * big)]).intersection(g)
        if not cut.is_empty:
            cut = max(getattr(cut, "geoms", [cut]), key=lambda s: s.length)
            m = cut.interpolate(0.5, normalized=True)
            pts.append((m.x, m.y))
    for _ in range(3):  # smoothed, so a jagged traced outline gives a calm curve
        pts = pts[:1] + [((a[0] + 2 * p[0] + b[0]) / 4, (a[1] + 2 * p[1] + b[1]) / 4) for a, p, b in zip(pts, pts[1:], pts[2:])] + pts[-1:]
    return shapely.LineString(pts) if len(pts) >= 2 else shapely.LineString([(c.x + e[0] * a, c.y + e[1] * a), (c.x + e[0] * b, c.y + e[1] * b)])


def wavy(line, amp, waves=2.5, tail=0.15, n=48):
    """A line drawn as a gentle wave across it (amp metres), flat at both ends; its last `tail` straight, so an
    arrowhead keeps the line's own direction."""
    L, run = line.length, line.length * (1 - tail)
    pts = []
    for i in range(n + 1):
        d = run * i / n
        p, q = line.interpolate(max(d - 1, 0)), line.interpolate(min(d + 1, L))
        dx, dy = q.x - p.x, q.y - p.y
        k = math.hypot(dx, dy) or 1
        o = amp * math.sin(math.pi * i / n) * math.sin(2 * math.pi * waves * i / n)
        c = line.interpolate(d)
        pts.append((c.x - dy / k * o, c.y + dx / k * o))
    pts += [(line.interpolate(run + (L - run) * i / 4).x, line.interpolate(run + (L - run) * i / 4).y) for i in range(1, 5)]
    return shapely.LineString(pts)


def heading(line):
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    L = math.hypot(x1 - x0, y1 - y0) or 1
    return (x1 - x0) / L, (y1 - y0) / L


def group(lines, cell):
    """Traced arrows grouped into one per square of `cell` metres: (centre, unit vector of their average direction).
    A square whose arrows disagree (they cancel out) gets none."""
    cells = {}
    for ln in lines:
        c = ln.interpolate(0.5, normalized=True)
        cells.setdefault((math.floor(c.x / cell), math.floor(c.y / cell)), []).append((c, heading(ln)))
    out = []
    for v in cells.values():
        sx, sy = sum(u[0] for _, u in v), sum(u[1] for _, u in v)
        r = math.hypot(sx, sy)
        if r / len(v) >= 0.3:
            out.append(((sum(c.x for c, _ in v) / len(v), sum(c.y for c, _ in v) / len(v)), (sx / r, sy / r)))
    return out


def mark(x, y, fill, op, st, look=None, marker="arrow"):
    """A short legend's mark, 6 x 3.2 mm with its top at y: a swatch, or an arrow ("arrow"). An optional `look` dresses it
    like the map: stroke, width, dash, marker (its own arrowhead), wave; soft (a swatch with a soft edge, no outline)."""
    look = look or {}
    if fill == "arrow":
        yc = y + 1.6
        d = (f"M{x:.2f} {yc:.2f}q0.75 -0.7 1.5 0t1.5 0t1.5 0L{x + 6:.2f} {yc:.2f}" if look.get("wave")
             else f"M{x:.2f} {yc:.2f}L{x + 6:.2f} {yc:.2f}")
        dash = f' stroke-dasharray="{look["dash"]}"' if look.get("dash") else ""
        return (f'<path d="{d}" fill="none" stroke="{look.get("stroke", st["ink"])}" stroke-width="{look.get("width", st["mid"])}"{dash} '
                f'stroke-linecap="round" marker-end="url(#{look.get("marker", marker)})"/>')
    if look.get("soft"):
        return "".join(f'<rect x="{x + i * 0.6:.2f}" y="{y + i * 0.6:.2f}" width="{6 - i * 1.2:.2f}" height="{3.2 - i * 1.2:.2f}" '
                       f'fill="{fill}" fill-opacity="{op}"/>' for i in range(3))
    return (f'<rect x="{x:.2f}" y="{y:.2f}" width="6" height="3.2" fill="{fill}" fill-opacity="{op}" '
            f'stroke="{st["ink"]}" stroke-width="{st["thin"]}"/>')


def browser():
    cands = [os.environ.get("BROWSER"), shutil.which("chrome"), shutil.which("google-chrome"), shutil.which("chromium"),
             shutil.which("chromium-browser"), shutil.which("msedge"), shutil.which("microsoft-edge"),
             r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    return next((c for c in cands if c and Path(c).exists()), None)


def png(svg, w_mm, h_mm):
    exe = browser()
    if not exe:
        return False
    out = svg.with_suffix(".png").resolve()
    px = lambda mm: math.ceil(mm * 96 / 25.4)
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    f"--window-size={px(w_mm)},{px(h_mm)}", f"--screenshot={out}", svg.resolve().as_uri()],
                   capture_output=True, timeout=180)
    return out.exists()


def nice(x):
    p = 10 ** math.floor(math.log10(x))
    return max(m * p for m in (1, 2, 5) if m * p <= x)


class Map:
    SIDE, PAD, HEAD, FOOT = 78, 10, 16, 24

    def __init__(self, S, st, extent, scale, title, subtitle, framed=False):
        self.S, self.st, self.scale = S, st, scale
        self.x0, self.y0, self.x1, self.y1 = extent.bounds
        self.k = 1000 / scale
        self.mw, self.mh = (self.x1 - self.x0) * self.k, (self.y1 - self.y0) * self.k
        self.W = self.PAD * 3 + self.mw + self.SIDE
        self.H = self.PAD * 2 + self.HEAD + max(self.mh, 150) + self.FOOT
        self.ox, self.oy = self.PAD, self.PAD + self.HEAD
        self.title, self.subtitle = title, subtitle
        self.body, self.defs, self.legend = [], [], []
        self.compact = None  # the legend in short, for the sheet: {"bar": [...], "low", "high", "unit", "rows": [[fill, opacity, label]]}
        self.extent = extent
        self.framed = framed
        if framed:  # the map is the whole frame
            self.W, self.H, self.ox, self.oy = self.mw, self.mh, 0, 0

    def P(self, x, y):
        return self.ox + (x - self.x0) * self.k, self.oy + (self.y1 - y) * self.k

    def d(self, g):
        out = []
        for part in getattr(g, "geoms", [g]):
            if part.geom_type == "Polygon":
                rings = [part.exterior, *part.interiors]
                out += ["M" + "L".join("%.2f %.2f" % self.P(x, y) for x, y in r.coords) + "Z" for r in rings]
            elif part.geom_type == "LineString":
                out.append("M" + "L".join("%.2f %.2f" % self.P(x, y) for x, y in part.coords))
            elif part.geom_type in ("MultiPolygon", "MultiLineString", "GeometryCollection"):
                out.append(self.d(part))
        return "".join(out)

    def add(self, g, **a):
        g = shapely.make_valid(g).intersection(self.extent) if not g.is_empty else g
        if g.is_empty:
            return
        if "marker_end" in a and hasattr(g, "geoms"):  # a marker sits only at the end of a path: one path per arrow
            for part in g.geoms:
                self.add(part, **a)
            return
        attrs = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in a.items())
        self.body.append(f'<path d="{self.d(g)}" fill-rule="evenodd" {attrs}/>')

    def hatch(self, name, color, gap=1.6, angle=45, w=None, bg=None):
        back = f'<rect width="{gap}" height="{gap}" fill="{bg}"/>' if bg else ""
        self.defs.append(f'<pattern id="{name}" width="{gap}" height="{gap}" patternUnits="userSpaceOnUse" patternTransform="rotate({angle})">{back}'
                         f'<line x1="0" y1="0" x2="0" y2="{gap}" stroke="{color}" stroke-width="{w or self.st["mid"]}"/></pattern>')
        return f"url(#{name})"

    def dots(self, name, color, gap=1.6, r=0.3):
        self.defs.append(f'<pattern id="{name}" width="{gap}" height="{gap}" patternUnits="userSpaceOnUse">'
                         f'<circle cx="{gap / 2}" cy="{gap / 2}" r="{r}" fill="{color}"/></pattern>')
        return f"url(#{name})"

    def context(self, buildings=True):
        st, S = self.st, self.S
        for g, _ in S.layer("water"):
            self.add(g, fill=st["water"] if g.geom_type.endswith("Polygon") else "none", stroke=st["water"], stroke_width=st["mid"])
        for g, _ in S.layer("streets"):
            self.add(g, fill="none", stroke=st["context"], stroke_width=st["thin"])
        for g, _ in S.layer("rail"):
            self.add(g, fill="none", stroke=st["ink"], stroke_width=st["thin"], stroke_dasharray="1.2 0.8")
        if buildings:
            self.buildings()

    def buildings(self):
        """The site's existing buildings, the same on every map: the standard's existing grey."""
        S = self.S
        self.add(shapely.union_all([g for g, _ in S.layer(S.buildings_path.stem, S.buildings_path.parent)]), fill=self.st["existing"], stroke="none")

    def site(self):
        self.add(self.S.poly, fill="none", stroke=self.st["ink"], stroke_width=self.st["mid"], stroke_dasharray="3 1.5")
        self.legend.append(("line", self.st["ink"], "Project site", dict(dash="3 1.5", w=self.st["mid"])))

    def key(self, kind, color, label, **o):
        self.legend.append((kind, color, label, o))

    def text(self, x, y, s, size=None, weight="normal", anchor="start", fill=None):
        st = self.st
        return (f'<text x="{x:.2f}" y="{y:.2f}" font-family="{escape(st["font"])}" font-size="{max(size or st["text"], MIN_TEXT)}" '
                f'font-weight="{weight}" text-anchor="{anchor}" fill="{fill or st["ink"]}">{escape(str(s))}</text>')

    def save(self, path, sources):
        st = self.st
        o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.W:.1f}mm" height="{self.H:.1f}mm" viewBox="0 0 {self.W:.1f} {self.H:.1f}">',
             f'<defs>{"".join(self.defs)}<clipPath id="frame"><rect x="{self.ox}" y="{self.oy}" width="{self.mw:.2f}" height="{self.mh:.2f}"/></clipPath>'
             f'<marker id="arrow" viewBox="0 0 6 6" refX="5" refY="3" markerUnits="userSpaceOnUse" markerWidth="2.4" markerHeight="2.4" orient="auto">'
             f'<path d="M0 0L6 3L0 6z" fill="{st["ink"]}"/></marker></defs>',
             f'<rect width="100%" height="100%" fill="{st["paper"]}"/>',
             f'<g clip-path="url(#frame)">{"".join(self.body)}</g>']
        if self.framed:
            o += self.boxed() + ["</svg>"]
            path.write_text("\n".join(o), encoding="utf-8")
            png(path, self.W, self.H)
            frame(path, self.W, self.H, (0, 0, self.mw, self.mh), self.title, compact=self.compact, defs="".join(self.defs), hide=self.box)
            return path.name
        o += [f'<rect x="{self.ox}" y="{self.oy}" width="{self.mw:.2f}" height="{self.mh:.2f}" fill="none" stroke="{st["ink"]}" stroke-width="{st["mid"]}"/>',
             self.text(self.ox, self.PAD + st["title"], self.title, st["title"], "bold"),
             self.text(self.ox, self.PAD + st["title"] + 5, self.subtitle)]
        # legend
        x, y = self.ox + self.mw + self.PAD, self.oy + 4
        o.append(self.text(x, y, "Legend", st["text"] * 1.2, "bold"))
        y += 6
        for kind, color, label, opt in self.legend:
            lines = textwrap.wrap(label, int((self.SIDE - 9) / (max(st["text"], MIN_TEXT) * 0.5))) or [""]  # fits the legend column at the text size
            if kind == "fill":
                o.append(f'<rect x="{x}" y="{y - 3}" width="7" height="4" fill="{color}" fill-opacity="{opt.get("opacity", 1)}" stroke="{st["ink"]}" stroke-width="{st["thin"]}"/>')
            elif kind == "line":
                o.append(f'<line x1="{x}" y1="{y - 1}" x2="{x + 7}" y2="{y - 1}" stroke="{color}" stroke-width="{opt.get("w", st["mid"])}" stroke-dasharray="{opt.get("dash", "none")}"/>')
            elif kind == "arrow":
                o.append(f'<line x1="{x}" y1="{y - 1}" x2="{x + 7}" y2="{y - 1}" stroke="{color}" stroke-width="{st["mid"]}" marker-end="url(#{opt.get("marker", "arrow")})"/>')
            for i, ln in enumerate(lines):
                o.append(self.text(x + 9, y + i * st["text"] * 1.25, ln))
            y += max(len(lines), 1) * st["text"] * 1.25 + 2.5
        # north arrow and scale bar in one row under the map's bottom-right corner
        L = nice((self.SIDE - 12) / self.k)
        n = next(n for n in ((4, 2, 1) if f"{L:g}"[0] == "2" else (5, 2, 1))
                 if L * self.k / n >= (len(f"{L:g}") + 1) * 0.6 * st["text"] + 1 or n == 1)
        s = L * self.k / n
        ry = self.oy + self.mh + 5
        sx = self.ox + self.mw - L * self.k - len(f"{L:g} m") * 0.3 * st["text"]  # the last number ends at the map's edge
        # north: a circle in outline, a line from its centre to the circle, pointing north
        nx = sx - 9
        o.append(f'<circle cx="{nx}" cy="{ry + 3}" r="3" fill="none" stroke="{st["ink"]}" stroke-width="{st["mid"]}"/>'
                 f'<line x1="{nx}" y1="{ry + 3}" x2="{nx}" y2="{ry}" stroke="{st["ink"]}" stroke-width="{st["mid"]}"/>')
        # scale bar: a line that steps up and down, a tick and a number at every step
        by = ry + 1
        o.append(f'<path d="{"".join(f"M{sx + i * s:.2f},{by + 1.6 * (i % 2)}h{s:.2f}" for i in range(n))}'
                 f'{"".join(f"M{sx + i * s:.2f},{by}v1.6" for i in range(n + 1))}" fill="none" stroke="{st["ink"]}" stroke-width="{st["thin"]}"/>')
        for i in range(n + 1):
            o.append(self.text(sx + i * s, by + 5, f"{L * i / n:g}" + (" m" if i == n else ""), anchor="middle"))
        # sources, below that row; the sheet grows to hold them and the legend, so nothing is cut
        src = sources + [f"Base map: the project's site folder (see its SOURCES.md). Projection {self.S.crs.name}."]
        lines = textwrap.wrap("  ·  ".join(src), int(self.mw / (st["text"] * 0.5)))
        fy = by + 9.5 + st["text"] * 1.6
        self.H = max(self.H, y + self.PAD, fy + (len(lines) + 1) * st["text"] * 1.3 + self.PAD)
        o[0] = f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.W:.1f}mm" height="{self.H:.1f}mm" viewBox="0 0 {self.W:.1f} {self.H:.1f}">'
        o.append(self.text(self.ox + self.mw, by + 9.5, f"1:{self.scale:,} at {self.W:.0f} x {self.H:.0f} mm".replace(",", " "), anchor="end"))
        o.append(self.text(self.ox, fy, "Sources", weight="bold"))
        for ln in lines:
            fy += st["text"] * 1.3
            o.append(self.text(self.ox, fy, ln, st["text"] * 0.9))
        o.append("</svg>")
        path.write_text("\n".join(o), encoding="utf-8")
        png(path, self.W, self.H)
        frame(path, self.W, self.H, (self.ox, self.oy, self.mw, self.mh), self.title, compact=self.compact, defs="".join(self.defs))
        return path.name

    def boxed(self, bw=70):
        """A framed map's title, short legend (its compact one), scale bar and north arrow, in a box in the corner where it
        hides least of the site; the full sources are in climate.md."""
        st, c = self.st, self.compact or {}
        tx = max(st["text"], MIN_TEXT)
        lh, wrap = tx * 1.3, int((bw - 16) / (tx * 0.5))
        heads = textwrap.wrap(f"{self.title}, 1:{self.scale:,}", int((bw - 8) / (st["title"] * 0.55)))
        e = [self.text(4, 3 + st["title"] * 1.2 * (i + 1), ln, st["title"], "bold") for i, ln in enumerate(heads)]
        y = 5 + st["title"] * 1.2 * len(heads)
        if c.get("bar"):
            n = len(c["bar"])
            e += [f'<rect x="{4 + i * 20 / n:.2f}" y="{y:.2f}" width="{20 / n + 0.05:.2f}" height="3.2" fill="{col}" fill-opacity="{c.get("opacity", 1)}"/>'
                  for i, col in enumerate(c["bar"])]
            e += [f'<rect x="4" y="{y:.2f}" width="20" height="3.2" fill="none" stroke="{st["ink"]}" stroke-width="{st["thin"]}"/>',
                  self.text(26, y + 2.8, f'{c["low"]} → {c["high"]} {c.get("unit", "")}'.strip())]
            y += lh + 0.8
        for fill, op, label, *look in c.get("rows", []):
            word, _, rest = label.partition(": ")   # a short legend: a rule up to its first colon or bracket
            lines = textwrap.wrap(f"{word}: {re.split(r': | [(]', rest)[0]}" if rest else label, wrap) or [""]
            e.append(mark(4, y, fill, op, st, *look))
            e += [self.text(12, y + 2.8 + j * lh, ln) for j, ln in enumerate(lines)]
            y += len(lines) * lh + 0.8
        # scale bar: a line stepping up and down, a tick at every step, 0 and the length under its ends; north beside it
        L = nice(30 / self.k)
        n, by = (4 if f"{L:g}"[0] == "2" else 5), y + 3
        s = L * self.k / n
        e.append(f'<path d="{"".join(f"M{4 + i * s:.2f},{by + 1.6 * (i % 2):.2f}h{s:.2f}" for i in range(n))}'
                 f'{"".join(f"M{4 + i * s:.2f},{by:.2f}v1.6" for i in range(n + 1))}" fill="none" stroke="{st["ink"]}" stroke-width="{st["thin"]}"/>')
        e += [self.text(4, by + 6, "0", anchor="middle"), self.text(4 + L * self.k, by + 6, f"{L:g} m", anchor="middle")]
        nx = 4 + L * self.k + 12
        e.append(f'<circle cx="{nx:.2f}" cy="{by + 1:.2f}" r="3" fill="none" stroke="{st["ink"]}" stroke-width="{st["mid"]}"/>'
                 f'<line x1="{nx:.2f}" y1="{by + 1:.2f}" x2="{nx:.2f}" y2="{by - 2:.2f}" stroke="{st["ink"]}" stroke-width="{st["mid"]}"/>')
        y = by + 6
        for ln in textwrap.wrap("Sources: climate.md; base map: the site folder (its SOURCES.md).", int((bw - 8) / (tx * 0.5))):
            y += lh
            e.append(self.text(4, y, ln))
        bh = y + 2.5
        site = shapely.affinity.affine_transform(self.S.poly, [self.k, 0, 0, -self.k, -self.x0 * self.k, self.y1 * self.k])
        bx, by = min(((x, y_) for y_ in (self.mh - bh, 0) for x in (0, self.mw - bw)),
                     key=lambda q: box(q[0], q[1], q[0] + bw, q[1] + bh).intersection(site).area)
        self.box = [round(bx, 2), round(by, 2), bw, round(bh, 2)]  # the sheet covers it: its own legend is under the map
        return [f'<g transform="translate({bx:.2f},{by:.2f})"><rect width="{bw}" height="{bh:.2f}" fill="{st["paper"]}"/>', *e, "</g>"]


KEYS = {"paper": ("paper", "background"), "ink": ("ink", "line", "lines", "text colour", "text color"), "accent": ("accent", "highlight", "new"),
        "existing": ("existing",), "context": ("context", "grey", "gray"), "water": ("water",), "cool": ("cool", "green", "vegetation", "park")}


def standard(out, given):
    """The look: --style, else drawing-graphics/style.json or the colours named in drawing-graphics/standard.md
    in the proposal folder, else the fallback. Returns (values, what was used)."""
    if given:
        return read(given), f"the drawing standard ({given})"
    dg = out.resolve().parent / "drawing-graphics"
    if (dg / "style.json").exists():
        return read(dg / "style.json"), "the drawing standard (drawing-graphics/style.json)"
    if (dg / "standard.md").exists():
        import re
        st = {}
        for line in (dg / "standard.md").read_text(encoding="utf-8").splitlines():
            low = line.lower()
            hexes = re.findall(r"#[0-9a-fA-F]{6}\b", line)
            if hexes:
                for k, words in KEYS.items():
                    if k not in st and any(w in low for w in words):
                        st[k] = hexes[0]
                        break
            m = re.search(r"font[^:|]*[:|]\s*`?([A-Za-z][^`|,]+)", line, re.I)
            if m and "font" not in st:
                st["font"] = m.group(1).strip() + ", Helvetica, Arial, sans-serif"
        return st, f"the drawing standard (drawing-graphics/standard.md: {', '.join(st) or 'no colours found, fallback used'})"
    return {}, "fallback look (no drawing standard): black on white, one accent"


def short_rule(label):
    """A rule's first sentence, for the sheet: "DON'T: No homes, schools ... 65 dB(A) or more by day"."""
    word, _, text = label.partition(": ")
    first = re.split(r"(?<=[a-z0-9)])\. ", text, maxsplit=1)[0].rstrip(".")
    return f"{word}: {first}" if text else label


def frame(path, W, H, box, title, bare=None, compact=None, defs="", hide=None):
    """Note in frames.json where the map sits in its drawing, so the sheet can show the map alone with its title."""
    f = path.parent / "frames.json"
    d = read(f) if f.exists() else {}
    d[path.name] = dict(W=round(W, 2), H=round(H, 2), frame=[round(v, 2) for v in box], title=title, compact=compact, defs=defs,
                        **({"bare": bare} if bare else {}), **({"hide": hide} if hide else {}))
    f.write_text(json.dumps(d, indent=1), encoding="utf-8")


def plan_frame(proposal):
    """(w, h mm, centre [lon, lat] or None, scale or None) of the first climate map's frame in the panels' plan, else None."""
    p = next((q for q in (proposal / "panel-layout" / n for n in ("layout-plan.json", "layout.json")) if q.exists()), None)
    for it in [it for q in (read(p).get("panels", []) if p else []) for it in q.get("items", [])]:
        fr, m = it.get("frame") or {}, re.search(r"1\s*:\s*([\d,. ]+)", str(it.get("scale") or ""))
        if str(it.get("file") or "").replace("\\", "/").startswith("climate/") and fr.get("w") and fr.get("h"):
            return float(fr["w"]), float(fr["h"]), fr.get("centre"), int(re.sub(r"\D", "", m.group(1))) if m else None


def meta(out, name):
    p = out / f"{name}.json"
    return read(p) if p.exists() else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--style")
    ap.add_argument("--scale", type=int)
    ap.add_argument("--margin", type=float, default=300)
    ap.add_argument("--buildings")
    ap.add_argument("--frame", nargs=2, type=float, metavar=("W", "H"), help="without a frame in the panels' plan: the maps' frame, mm")
    ap.add_argument("--centre", nargs=2, type=float, metavar=("LON", "LAT"), help="the frame's centre (default: the site's)")
    ap.add_argument("--sheet", action="store_true", help="only remake climate_sheet from the drawings made, e.g. after writing summary.md")
    a = ap.parse_args()
    S, out = Site(a.site, a.buildings), Path(a.out)
    found, look = standard(out, a.style)
    st = dict(FALLBACK, **found)
    if "existing" not in found:  # a standard from before C6/C7 has only context
        st["existing"] = st["context"]
    if "cool" not in found:  # since C6/C7 the standard's green is park (or kept, grove)
        st["cool"] = next((found[k] for k in ("park", "kept", "grove", "green") if k in found), mix(st["paper"], st["ink"], 0.35))
    dg = found.get("diagram") if isinstance(found.get("diagram"), dict) else {}  # a thematic plan's weights and text sizes, px
    st.update({k: dg[d] * 25.4 / 96 for k, d in (("thin", "line"), ("mid", "outline"), ("thick", "heavy"),
                                                 ("text", "label_size"), ("title", "title_size")) if d in dg})
    if a.sheet:  # only the sheet, from the drawings already made
        lines = (out / "drawings.txt").read_text(encoding="utf-8").splitlines()[1:]
        print(sheet(out, st, [n for n in lines if n and n != "climate_sheet.svg"]))
        return
    fr = plan_frame(out.resolve().parent) or ((*a.frame, a.centre, None) if a.frame else None)
    ext = box(*S.poly.buffer(a.margin).bounds)
    w, h = ext.bounds[2] - ext.bounds[0], ext.bounds[3] - ext.bounds[1]
    fw, fh = fr[:2] if fr else (280, 300)
    scale = (fr and fr[3]) or a.scale or next((s for s in SCALES if w * 1000 / s <= fw and h * 1000 / s <= fh), SCALES[-1])
    if fr:  # every map fills the one frame at its scale, around its centre, else the site's
        c = S.to_m(shapely.Point(fr[2])) if fr[2] else ext.centroid
        ext = box(c.x - fw * scale / 2000, c.y - fh * scale / 2000, c.x + fw * scale / 2000, c.y + fh * scale / 2000)
    made = []

    def new(title, sub):
        return Map(S, st, ext, scale, title, sub, bool(fr))

    if (out / "fresh-air.geojson").exists():
        m = new("Fresh air", "Air corridors and flow as they are today")
        m.context()
        F = S.layer("fresh-air", out)
        # one soft corridor in the cool colour, a few large arrows, its name along it (the winners' way), never wider than traced
        cool = st["cool"] if any(k in found for k in ("cool", "park", "kept", "grove", "green")) else st["water"]
        deep, soft_ink = mix(cool, st["ink"], 0.65), mix(cool, st["ink"], 0.5)  # the corridor's arrow darkest, the others lighter
        cell = min(m.mw, m.mh) / 6 / m.k  # one arrow per square of a sixth of the map's short side, in metres at its scale
        for i, (big, col) in enumerate(((5, deep), (3, soft_ink))):
            m.defs.append(f'<marker id="fa{i}" viewBox="0 0 6 6" refX="5" refY="3" markerUnits="userSpaceOnUse" markerWidth="{big}" '
                          f'markerHeight="{big}" orient="auto"><path d="M0 0L6 3L0 6z" fill="{col}"/></marker>')
        cors = [(g, p) for g, p in F if p.get("kind") == "corridor"]
        flows = [g for g, p in F if p.get("kind") == "flow"]
        named = {}
        for g, p in cors:
            for layer in soft(g):
                m.add(layer, fill=cool, fill_opacity=0.42, stroke="none")
            L, w, e = axis(g)
            inside = [heading(f) for f in flows if f.intersects(g)]
            if inside and sum(u[0] for u in inside) * e[0] + sum(u[1] for u in inside) * e[1] < 0:
                e = (-e[0], -e[1])  # along the corridor, the way its arrows go
            c, n = g.centroid, max(1, min(3, round(L / (2 * cell))))
            for j in range(n):  # along the corridor's own curve, gently wavy
                t, h = ((j + 0.5) / n - 0.5) * L, 0.3 * L / n
                m.add(wavy(midline(g, c, e, t - h, t + h), 1.2 / m.k), fill="none", stroke=deep, stroke_width=st["thick"] * 2,
                      stroke_linecap="round", stroke_linejoin="round", marker_end="url(#fa0)")
            name = p.get("label", "corridor").split(" (")[0].strip().upper()
            if g.area > named.get(name, (0,))[0]:
                named[name] = (g.area, c, L, w, e)
        for k, (name, (_, c, L, w, e)) in enumerate(named.items()):
            off = w / 2 + 3 / m.k  # beside the corridor, not on its arrows
            a = (c.x - e[0] * L * 0.4 + e[1] * off, c.y - e[1] * L * 0.4 - e[0] * off)
            b = (c.x + e[0] * L * 0.4 + e[1] * off, c.y + e[1] * L * 0.4 - e[0] * off)
            (ax, ay), (bx, by) = m.P(*a), m.P(*b)
            if bx < ax - 0.2 * abs(by - ay) or (abs(bx - ax) <= 0.2 * abs(by - ay) and by > ay):
                (ax, ay), (bx, by) = (bx, by), (ax, ay)  # reads left to right, or bottom to top
            m.defs.append(f'<path id="fa-name{k}" d="M{ax:.2f} {ay:.2f}L{bx:.2f} {by:.2f}"/>')
            m.body.append(f'<text font-family="{escape(st["font"])}" font-size="{max(st["text"] * 1.6, MIN_TEXT)}" font-weight="bold" '
                          f'letter-spacing="{st["text"] * 0.5:.2f}" fill="{deep}"><textPath href="#fa-name{k}" startOffset="50%" '
                          f'text-anchor="middle">{escape(name)}</textPath></text>')
        outside = [f for f in flows if not any(f.intersects(g) for g, _ in cors)]
        for (x, y), (ux, uy) in group(outside, cell):
            h = 0.28 * cell
            m.add(wavy(shapely.LineString([(x - ux * h, y - uy * h), (x + ux * h, y + uy * h)]), 0.8 / m.k), fill="none",
                  stroke=soft_ink, stroke_width=st["mid"] * 2, stroke_dasharray="1 0.7", stroke_linecap="round", marker_end="url(#fa1)")
        m.site()
        for lab in sorted({p.get("label", "corridor") for _, p in cors}):
            m.key("fill", cool, lab, opacity=0.6)
        if flows:
            m.key("arrow", soft_ink, "Air flow, direction of movement", marker="fa1")
        m.compact = dict(rows=[[cool, 0.42, "Air path", {"soft": True}],  # the short legend dressed like the map
                               ["arrow", 1, "Air flow, the way it moves", {"stroke": soft_ink, "width": st["mid"] * 2, "dash": "1 0.7",
                                                                           "marker": "fa1", "wave": True}]])
        made.append(m.save(out / "fresh-air.svg", meta(out, "fresh-air").get("sources", [])))

    sun = meta(out, "sun")
    for name, title, sub, rev in [("sun-hours", "Sun hours", "Hours of direct sun per year on open ground, from the weather file, clouds and the existing buildings' shade included", True),
                                  ("radiation", "Solar radiation", "Direct and diffuse sun energy per year on open ground, kWh/m2", False)]:
        if not (out / f"{name}.geojson").exists():
            continue
        m = new(title, sub)
        m.context(buildings=False)
        F = S.layer(name, out)
        cols = ramp(len(F), st)
        if rev:
            cols = cols[::-1]
        # outside the grid nothing was computed: a neutral hatch, so it isn't read as the lowest class
        mg = sun.get("grid_margin_m")
        done = S.poly.buffer(mg) if mg is not None else shapely.union_all([g for g, _ in F]).buffer(15)
        nc = m.hatch("notcomputed", st["context"], 1.6, 45, st["mid"])
        nc_label = f"Not computed (outside the site and its {mg:g} m margin)" if mg is not None else "Not computed (outside the computed area)"
        m.add(m.extent.difference(done), fill=nc, stroke="none")
        for (g, p), c in zip(F, cols):
            m.add(g, fill=c, stroke="none")
        m.buildings()
        m.site()
        for (g, p), c in zip(F, cols):
            m.key("fill", c, p["label"])
        m.key("fill", nc, nc_label)
        m.key("fill", st["existing"], "Existing buildings")
        lo_k, hi_k, unit = ("hours_min", "hours_max", "h of sun a year") if name == "sun-hours" else ("kwh_min", "kwh_max", "kWh/m² a year")
        m.compact = dict(bar=cols, low=f"{F[0][1][lo_k]:g}", high=f"{F[-1][1][hi_k]:g}", unit=unit, rows=[["url(#notcomputed)", 1, nc_label]])
        made.append(m.save(out / f"{name}.svg", sun.get("sources", [])))

    if (out / "shadows.geojson").exists():
        F = S.layer("shadows", out)
        for day in dict.fromkeys(p["day"] for _, p in F):
            m = new(f"Shadows, {day}", "Shadows of the existing buildings at three times of day")
            m.context(buildings=False)
            G = [(g, p) for g, p in F if p["day"] == day]
            cols = ramp(len(G) + 1, st)[1:]
            for (g, p), c in zip(G, cols):
                m.add(g, fill=c, fill_opacity=0.6, stroke="none")
            m.buildings()
            m.site()
            for (g, p), c in zip(G, cols):
                m.key("fill", c, f'{p["local_time"]}, sun {p["sun_altitude_deg"]:.0f}° high from {p["sun_azimuth_deg"]:.0f}°', opacity=0.6)
            m.key("fill", st["existing"], "Existing buildings")
            m.compact = dict(bar=cols, low=G[0][1]["local_time"], high=G[-1][1]["local_time"], unit="", opacity=0.6)
            made.append(m.save(out / f"shadows_{day.lower().replace(' ', '-')}.svg", sun.get("sources", [])))

    if (out / "noise.geojson").exists():
        F = S.layer("noise", out)
        for period in dict.fromkeys(p["period"] for _, p in F):
            G = [(g, p) for g, p in F if p["period"] == period]
            r = meta(out, "noise").get("rail", {})
            sub = "Estimated level at about 4 m above ground, existing buildings screening"
            if r.get("included") and "assumed" in r.get("label", "").lower():
                sub += ". RAIL TRAFFIC ASSUMED, NOT FROM DATA"
            nj = meta(out, "noise")
            if nj.get("traffic_ranges"):
                sub += ". At the high end of the traffic range"
            if nj.get("speeds_assumed"):  # entries read "<road> <speed> km/h"
                roads = [x.rsplit(" ", 2)[0] for x in nj["speeds_assumed"]]
                sub += f". SPEED{'S' if len(roads) > 1 else ''} ASSUMED: {', '.join(roads)}"
            m = new(f"{'Road and rail' if r.get('included') else 'Road'} noise, {period}", sub)
            m.context(buildings=False)
            cols = ramp(len(G), st)
            for (g, p), c in zip(G, cols):
                m.add(g, fill=c, stroke="none", fill_opacity=0.85)
            m.buildings()
            srcs = S.layer("noise-sources", out)
            for g, p in srcs:
                m.add(g, fill="none", stroke=st["ink"], stroke_width=st["thick"], **({"stroke_dasharray": "2 1"} if p.get("kind") == "rail" else {}))
            m.site()
            for (g, p), c in zip(G, cols):
                m.key("fill", c, p["label"], opacity=0.85)
            m.key("line", st["ink"], "Roads counted as noise sources", w=st["thick"])
            rail = meta(out, "noise").get("rail", {"label": "Railway not assessed: no train numbers"})
            if rail.get("included"):
                m.key("line", st["ink"], f'Railway counted as noise source. {rail["label"]}', w=st["thick"], dash="2 1")
            else:
                m.key("line", st["accent"], rail["label"].upper(), w=st["thick"], dash="0.6 0.9")
            m.compact = dict(bar=cols, low=f'{G[0][1]["db_min"]:g}', high=f'{G[-1][1]["db_min"]:g}+', unit="dB(A)", opacity=0.85)
            made.append(m.save(out / f"noise_{period}.svg", meta(out, "noise").get("sources", [])))

    if (out / "heat.geojson").exists():
        m = new("Heat island", "How much each place heats up today, from what covers the ground")
        F = S.layer("heat", out)
        idx = [(g, p) for g, p in F if p["kind"] == "index"]
        cool = st["cool"]
        cols = [mix(st["paper"], cool, 0.55), mix(st["paper"], cool, 0.2)] + ramp(4, st)[1:]
        for (g, p), c in zip(idx, cols):
            m.add(g, fill=c, stroke="none")
        for g, p in F:
            if p["kind"] == "unknown":
                m.add(g, fill=m.hatch("unknown", st["ink"], 1.2, 45, st["thin"]), fill_opacity=0.5, stroke="none")
        # the cool class is green now, so the buildings' grey can't be mistaken for it
        m.context()
        m.site()
        for (g, p), c in zip(idx, cols):
            m.key("fill", c, p["label"].capitalize())
        if any(p["kind"] == "unknown" for _, p in F):
            m.key("fill", "url(#unknown)", "Too little land-use data to say", opacity=0.5)
        m.key("fill", st["existing"], "Existing buildings (roofs count as very hot)")
        m.compact = dict(bar=cols[:len(idx)], low="cool", high="very hot", unit="(relative)",
                         rows=[["url(#unknown)", 0.5, "No land-use data"]] if any(p["kind"] == "unknown" for _, p in F) else [])
        made.append(m.save(out / "heat.svg", meta(out, "heat").get("sources", [])))

    if (out / "rules.geojson").exists():
        R = meta(out, "rules")
        m = new("Climate rules for the design", "Where the climate of the place asks the design to do or avoid something")
        m.context()
        # one look per rule, the same on the map and in the legend: don't = solid or dense accent, careful = light accent tint, do = grey
        F = S.layer("rules", out)
        order = {"do": 0, "careful": 1, "dont": 2}
        looks, n = {}, {"dont": 0, "careful": 0, "do": 0}
        for g, p in sorted(F, key=lambda f: -order.get(f[1]["kind"], 0)):
            k = p["kind"]
            if p["rule"] in looks or g.geom_type.endswith("LineString"):
                continue
            i = n[k]
            n[k] += 1
            if k == "dont":
                looks[p["rule"]] = (st["accent"], 0.85) if i == 0 else (m.hatch(f"dont{i}", st["paper"], 1.4, 45, st["mid"], bg=st["accent"]), 0.85)
            elif k == "careful":
                looks[p["rule"]] = (st["accent"], 0.3) if i == 0 else (m.hatch(f"careful{i}", st["accent"], 2.4, 45, st["thin"]), 1)
            else:
                looks[p["rule"]] = (st["context"], 0.35) if i == 0 else (m.hatch(f"do{i}", st["context"], 2.2, -45, st["mid"]), 1)
        for g, p in sorted(F, key=lambda f: order.get(f[1]["kind"], 0)):
            if g.geom_type.endswith("LineString"):
                m.add(g, fill="none", stroke=st["ink"], stroke_width=st["mid"], marker_end="url(#arrow)")
            else:
                fill, op = looks[p["rule"]]
                edge = {"dont": dict(stroke=st["accent"], stroke_width=st["mid"]),
                        "careful": dict(stroke=st["accent"], stroke_width=st["mid"], stroke_dasharray="1.2 0.8")}.get(p["kind"], dict(stroke="none"))
                m.add(g, fill=fill, fill_opacity=op, **edge)
        m.site()
        seen = set()
        for g, p in sorted(F, key=lambda f: -order.get(f[1]["kind"], 0)):
            if p["rule"] in seen:
                continue
            seen.add(p["rule"])
            word = {"dont": "DON'T", "careful": "CAREFUL", "do": "DO"}[p["kind"]]
            if g.geom_type.endswith("LineString"):
                m.key("arrow", st["ink"], f"{word}: {p['rule']}")
            else:
                m.key("fill", looks[p["rule"]][0], f"{word}: {p['rule']}", opacity=looks[p["rule"]][1])
        for n in R.get("notes", []):
            m.key("line", st["paper"], n)
        m.compact = dict(rows=[[("arrow" if kind == "arrow" else color), opt.get("opacity", 1), short_rule(label)]
                               for kind, color, label, opt in m.legend if kind in ("fill", "arrow")])
        made.append(m.save(out / "rules.svg", R.get("sources", [])))

    if (out / "wind.csv").exists():
        made.append(wind_rose(out, st, meta(out, "wind")))
    made.append(sheet(out, st, made))
    (out / "drawings.txt").write_text(f"Scale 1:{scale}. {look}.\n" + "\n".join(made) + "\n", encoding="utf-8")
    print(f"1:{scale}", look, made)


def sheet(out, st, names, W=420, H=297):
    """Every map on one A3 landscape sheet: the map alone, its title and a compact legend, no text below the floor.
    The rules map takes two cells with all its rows; the wind roses sit two by two. Run draw.py --sheet again after summary.md."""
    pad, head = 10, 16
    cols, rows = 4, 3
    cw, ch = (W - 2 * pad) / cols, (H - head - 2 * pad) / rows
    tx = max(st["text"], MIN_TEXT)
    lh = tx * 1.3  # one line of text
    t = lambda x, y, s, size=tx, w="normal", a="start": (f'<text x="{x:.2f}" y="{y:.2f}" font-family="{escape(st["font"])}" font-size="{max(size, MIN_TEXT)}" '
                                                       f'font-weight="{w}" text-anchor="{a}" fill="{st["ink"]}">{escape(str(s))}</text>')
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">',
         f'<rect width="100%" height="100%" fill="{st["paper"]}"/>', t(pad, pad + st["title"], "Climate of the site", st["title"] * 1.3, "bold")]
    defs = [f'<marker id="sheet-arrow" viewBox="0 0 6 6" refX="5" refY="3" markerUnits="userSpaceOnUse" markerWidth="2.4" markerHeight="2.4" orient="auto">'
            f'<path d="M0 0L6 3L0 6z" fill="{st["ink"]}"/></marker>']
    frames = meta(out, "frames")

    def own(k, text):  # a map's patterns, renamed so two maps' patterns never clash
        return re.sub(r'(id="|url\(#)([\w-]+)', lambda g: f"{g.group(1)}m{k}-{g.group(2)}", text)

    def swatch(x, y, fill, op, k, look=None):  # a 6 x 3.2 mm swatch with its top at y, its own arrowhead renamed like its map's
        look = dict(look, marker=f'm{k}-{look["marker"]}') if look and "marker" in look else look
        return mark(x, y, fill, op, st, look, "sheet-arrow")

    def legend(x, y, w, c, k):
        """A compact legend with its top at (x, y), w wide; returns its elements and its height."""
        e, y0 = [], y
        if c.get("bar"):
            bw = min(36, w * 0.45)
            n = len(c["bar"])
            e += [f'<rect x="{x + i * bw / n:.2f}" y="{y:.2f}" width="{bw / n + 0.05:.2f}" height="3.2" fill="{col}" fill-opacity="{c.get("opacity", 1)}"/>'
                  for i, col in enumerate(c["bar"])]
            e.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bw:.2f}" height="3.2" fill="none" stroke="{st["ink"]}" stroke-width="{st["thin"]}"/>')
            e.append(t(x + bw + 2, y + 2.8, f'{c["low"]} → {c["high"]} {c.get("unit", "")}'.strip()))
            y += lh + 0.8
        for fill, op, label, *look in c.get("rows", []):
            fill = own(k, fill) if fill.startswith("url(") else fill
            lines = textwrap.wrap(label, int((w - 8) / (tx * 0.5))) or [""]
            e.append(swatch(x, y, fill, op, k, *look))
            for j, ln in enumerate(lines):
                e.append(t(x + 8, y + 2.8 + j * lh, ln))
            y += len(lines) * lh + 0.8
        return e, y - y0

    # the cells: the rules map takes two, every other map one; what is left is for the summary
    plan, used = [], 0
    for n in names:
        if not (out / n.replace(".svg", ".png")).exists():
            continue
        span = 2 if n == "rules.svg" else 1
        if used % cols + span > cols:
            used += cols - used % cols
        plan.append((n, used, span))
        used += span
    for k, (n, cell, span) in enumerate(plan):
        x, y = pad + (cell % cols) * cw, pad + head + (cell // cols) * ch
        f = frames.get(n)
        if not f:  # a drawing made before frames.json: placed whole, with its small text
            print(f"WARNING climate_sheet: no frame for {n}; it is placed whole, so its legend and sources are below 12 px. Run draw.py again.")
            o.append(f'<image x="{x + 1:.1f}" y="{y + 1:.1f}" width="{cw * span - 2:.1f}" height="{ch - 2:.1f}" '
                     f'href="{n.replace(".svg", ".png")}" preserveAspectRatio="xMidYMid meet"/>')
            continue
        if f.get("defs"):
            defs.append(own(k, f["defs"]))
        o.append(t(x + 1, y + tx, f["title"], tx, "bold"))
        top, bottom = y + tx + 1.5, y + ch - 2
        c = f.get("compact") or {}
        fx, fy, fw, fh = f["frame"]
        img = f'<image x="0" y="0" width="{f["W"]}" height="{f["H"]}" href="{n.replace(".svg", ".png")}"/>'
        if f.get("hide"):  # a framed map's own legend box, too small here
            img += f'<rect x="{f["hide"][0]}" y="{f["hide"][1]}" width="{f["hide"][2]}" height="{f["hide"][3]}" fill="{st["paper"]}"/>'
        if isinstance(f.get("bare"), list):  # the wind roses, two by two, the speed colours in the fourth place
            q = min((cw - 4) / 2, (bottom - top) / 2)
            d = q - lh - 2
            for i, r in enumerate(f["bare"][:3]):
                qx, qy = x + 1 + (i % 2) * q, top + (i // 2) * q
                o.append(f'<svg x="{qx + (q - d) / 2:.2f}" y="{qy:.2f}" width="{d:.2f}" height="{d:.2f}" '
                         f'viewBox="{r["cx"] - r["r"]} {r["cy"] - r["r"]} {2 * r["r"]} {2 * r["r"]}" overflow="hidden">{r["frag"]}</svg>')
                o.append(t(qx + q / 2, qy + d + tx + 0.5, r["season"], a="middle"))
            le, _ = legend(x + 1 + q + 4, top + q + 4, q - 4, c, k)
            o += le
            continue
        wbox = cw * span - 2
        if span > 1:  # the rules: the map on the left, every row of its legend beside it
            s_ = min(cw - 2, bottom - top) / max(fw, fh)
            o.append(f'<svg x="{x + 1:.2f}" y="{top:.2f}" width="{fw * s_:.2f}" height="{fh * s_:.2f}" viewBox="{fx} {fy} {fw} {fh}" overflow="hidden">{img}</svg>')
            lx = x + 1 + fw * s_ + 4
            le, hgt = legend(lx, top + 1, x + wbox - lx, c, k)
            if top + 1 + hgt > bottom:
                print(f"WARNING climate_sheet: the legend of {n} is taller than its cell ({hgt:.0f} of {bottom - top:.0f} mm)")
            o += le
            continue
        _, hgt = legend(x + 1, 0, wbox, c, k)  # measure the legend first, then fit the map above it
        s_ = min(wbox / fw, (bottom - top - hgt - 1.5) / fh)
        mx = x + 1 + (wbox - fw * s_) / 2
        o.append(f'<svg x="{mx:.2f}" y="{top:.2f}" width="{fw * s_:.2f}" height="{fh * s_:.2f}" viewBox="{fx} {fy} {fw} {fh}" overflow="hidden">{img}</svg>')
        le, _ = legend(mx, top + fh * s_ + 1.5, max(fw * s_, 60), c, k)
        o += le
    o.insert(2, f'<defs>{"".join(defs)}</defs>')

    # the summary in what is left
    x, y = pad + (used % cols) * cw + 3, pad + head + (used // cols) * ch + tx
    width = int(((cols - used % cols) * cw - 6) / (tx * 0.5))
    text = (out / "summary.md").read_text(encoding="utf-8").split("\n") if (out / "summary.md").exists() else []
    c = meta(out, "climate")
    if not text and c.get("key_numbers"):
        text = [f"{k.replace('_', ' ')}: {v}" for k, v in c["key_numbers"].items() if not isinstance(v, dict)]
    o.append(t(x, y, "Summary", tx * 1.3, "bold"))
    shown = [ln for para in text if para.strip() for ln in textwrap.wrap(para, width)]
    room = int((H - 4 - lh - y) // (tx * 1.35))  # lines that fit above the note at the bottom
    if len(shown) > room:  # the sheet is fixed at A3: cut, end with an ellipsis, and say so
        print(f"WARNING climate_sheet: the summary has {len(shown)} lines, {room} fit on the sheet; the rest is cut. Shorten summary.md.")
        shown = shown[:room]
        shown[-1] = shown[-1].rstrip(" .,;:") + " …"
    for ln in shown:
        y += tx * 1.35
        o.append(t(x, y, ln))
    o.append(t(pad, H - 4, "Full legends, scales and sources are in each map's own file in this folder. North is up; maps not to scale."))
    o.append("</svg>")
    path = out / "climate_sheet.svg"
    path.write_text("\n".join(o), encoding="utf-8")
    png(path, W, H)
    return path.name


def wind_rose(out, st, wm):
    rows = list(csv.DictReader(open(out / "wind.csv", encoding="utf-8")))
    seasons = list(dict.fromkeys(r["season"] for r in rows))
    classes = [k for k in rows[0] if k.endswith("m/s")]
    cols = ramp(len(classes), st)
    R, gap = 38, 24
    W, H = 10 + len(seasons) * (2 * R + gap) + 10, 2 * R + 70
    vmax = max(float(r["total %"]) for r in rows)
    ring = nice(vmax / 2)
    t = lambda x, y, s, size=st["text"], w="normal", a="middle": (f'<text x="{x:.2f}" y="{y:.2f}" font-family="{escape(st["font"])}" font-size="{max(size, MIN_TEXT)}" '
                                                                   f'font-weight="{w}" text-anchor="{a}" fill="{st["ink"]}">{escape(s)}</text>')
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="{st["paper"]}"/>',
         t(10, 12, "Wind", st["title"], "bold", "start"), t(10, 18, "Share of hours the wind blows from each direction, by speed", a="start")]
    bars = []
    for i, s in enumerate(seasons):
        labels = []
        n0 = len(o)
        cx, cy = 10 + R + i * (2 * R + gap), 26 + R
        for k in range(1, int(vmax // ring) + 2):
            r = R * k * ring / vmax * 0.95
            if r <= R:
                o.append(f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" stroke="{st["context"]}" stroke-width="{st["thin"]}"/>')
                labels.append(t(cx + 1, cy - r - 0.6, f"{k * ring:g}%", st["text"] * 0.8, a="start")
                              .replace("<text ", f'<text stroke="{st["paper"]}" stroke-width="0.8" paint-order="stroke" ', 1))  # drawn after the bars, with a halo
        sec = [r for r in rows if r["season"] == s]
        for j, r in enumerate(sec):
            a0, a1 = math.radians(j * 22.5 - 9), math.radians(j * 22.5 + 9)
            acc = 0
            for c, col in zip(classes, cols):
                v = float(r[c])
                r0, r1 = R * acc / vmax * 0.95, R * (acc + v) / vmax * 0.95
                acc += v
                if r1 - r0 < 0.05:
                    continue
                pts = [(cx + rr * math.sin(aa), cy - rr * math.cos(aa)) for rr, aa in ((r0, a0), (r1, a0), (r1, a1), (r0, a1))]
                o.append(f'<path d="M{pts[0][0]:.2f} {pts[0][1]:.2f}L{pts[1][0]:.2f} {pts[1][1]:.2f}A{r1:.2f} {r1:.2f} 0 0 1 {pts[2][0]:.2f} {pts[2][1]:.2f}'
                         f'L{pts[3][0]:.2f} {pts[3][1]:.2f}A{r0:.2f} {r0:.2f} 0 0 0 {pts[0][0]:.2f} {pts[0][1]:.2f}Z" fill="{col}" stroke="{st["paper"]}" stroke-width="0.1"/>')
        bars.append(dict(season=s, cx=cx, cy=cy, r=R, frag="".join(e for e in o[n0:] if not e.startswith("<text"))))
        o += labels
        for lab, ang in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
            o.append(t(cx + (R + 3) * math.sin(math.radians(ang)), cy - (R + 3) * math.cos(math.radians(ang)) + 1, lab, w="bold"))
        o.append(t(cx, cy + R + 9, s, st["text"] * 1.1, "bold"))
    y = H - 20
    for i, (c, col) in enumerate(zip(classes, cols)):
        o.append(f'<rect x="{10 + i * 28}" y="{y}" width="6" height="3.5" fill="{col}"/>' + t(18 + i * 28, y + 3, c, a="start"))
    o.append(t(10, H - 8, "Sources: " + "; ".join(wm.get("sources", [])), st["text"] * 0.85, a="start"))
    o.append("</svg>")
    p = out / "wind.svg"
    p.write_text("\n".join(o), encoding="utf-8")
    png(p, W, H)
    frame(p, W, H, (8, 24, len(seasons) * (2 * R + gap) - gap + 4, 2 * R + 4), "Wind", bare=bars,
          compact=dict(rows=[[col, 1, c] for c, col in zip(classes, cols)]))
    return p.name


if __name__ == "__main__":
    main()
