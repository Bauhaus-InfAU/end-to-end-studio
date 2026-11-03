"""Draw the climate layers as maps: SVG with a PNG next to each, with legend, north arrow, scale bar and sources.
The look comes from a style JSON made from drawing-graphics/standard.md; without one, black on white with one accent.

python draw.py --site SITE_DIR --out CLIMATE_DIR [--style style.json] [--scale 5000] [--margin 300]

style.json keys (all optional): paper, ink, accent, context, water, font, thin, mid, thick (mm), text, title (mm),
ramp (list of colours, light to dark).
"""
import argparse
import csv
import math
import os
import shutil
import subprocess
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

import shapely
from shapely.geometry import box

from common import Site, read

FALLBACK = dict(paper="#ffffff", ink="#000000", accent="#d7263d", context="#c9c9c9", water="#e4e4e4",
                font="Helvetica, Arial, sans-serif", thin=0.1, mid=0.25, thick=0.6, text=2.4, title=5.0)
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

    def __init__(self, S, st, extent, scale, title, subtitle):
        self.S, self.st, self.scale = S, st, scale
        self.x0, self.y0, self.x1, self.y1 = extent.bounds
        self.k = 1000 / scale
        self.mw, self.mh = (self.x1 - self.x0) * self.k, (self.y1 - self.y0) * self.k
        self.W = self.PAD * 3 + self.mw + self.SIDE
        self.H = self.PAD * 2 + self.HEAD + max(self.mh, 150) + self.FOOT
        self.ox, self.oy = self.PAD, self.PAD + self.HEAD
        self.title, self.subtitle = title, subtitle
        self.body, self.defs, self.legend = [], [], []
        self.extent = extent

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
            self.add(shapely.union_all([g for g, _ in S.layer(S.buildings_path.stem, S.buildings_path.parent)]), fill=st["context"], stroke="none")

    def site(self):
        self.add(self.S.poly, fill="none", stroke=self.st["ink"], stroke_width=self.st["thick"], stroke_dasharray="3 1.2")
        self.legend.append(("line", self.st["ink"], "Project site", dict(dash="3 1.2", w=self.st["thick"])))

    def key(self, kind, color, label, **o):
        self.legend.append((kind, color, label, o))

    def text(self, x, y, s, size=None, weight="normal", anchor="start", fill=None):
        st = self.st
        return (f'<text x="{x:.2f}" y="{y:.2f}" font-family="{escape(st["font"])}" font-size="{size or st["text"]}" '
                f'font-weight="{weight}" text-anchor="{anchor}" fill="{fill or st["ink"]}">{escape(str(s))}</text>')

    def save(self, path, sources):
        st = self.st
        o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.W:.1f}mm" height="{self.H:.1f}mm" viewBox="0 0 {self.W:.1f} {self.H:.1f}">',
             f'<defs>{"".join(self.defs)}<clipPath id="frame"><rect x="{self.ox}" y="{self.oy}" width="{self.mw:.2f}" height="{self.mh:.2f}"/></clipPath>'
             f'<marker id="arrow" viewBox="0 0 6 6" refX="5" refY="3" markerUnits="userSpaceOnUse" markerWidth="2.4" markerHeight="2.4" orient="auto">'
             f'<path d="M0 0L6 3L0 6z" fill="{st["ink"]}"/></marker></defs>',
             f'<rect width="100%" height="100%" fill="{st["paper"]}"/>',
             f'<g clip-path="url(#frame)">{"".join(self.body)}</g>',
             f'<rect x="{self.ox}" y="{self.oy}" width="{self.mw:.2f}" height="{self.mh:.2f}" fill="none" stroke="{st["ink"]}" stroke-width="{st["mid"]}"/>',
             self.text(self.ox, self.PAD + st["title"], self.title, st["title"], "bold"),
             self.text(self.ox, self.PAD + st["title"] + 5, self.subtitle)]
        # legend
        x, y = self.ox + self.mw + self.PAD, self.oy + 4
        o.append(self.text(x, y, "Legend", st["text"] * 1.2, "bold"))
        y += 6
        for kind, color, label, opt in self.legend:
            lines = textwrap.wrap(label, 46) or [""]
            if kind == "fill":
                o.append(f'<rect x="{x}" y="{y - 3}" width="7" height="4" fill="{color}" fill-opacity="{opt.get("opacity", 1)}" stroke="{st["ink"]}" stroke-width="{st["thin"]}"/>')
            elif kind == "line":
                o.append(f'<line x1="{x}" y1="{y - 1}" x2="{x + 7}" y2="{y - 1}" stroke="{color}" stroke-width="{opt.get("w", st["mid"])}" stroke-dasharray="{opt.get("dash", "none")}"/>')
            elif kind == "arrow":
                o.append(f'<line x1="{x}" y1="{y - 1}" x2="{x + 7}" y2="{y - 1}" stroke="{color}" stroke-width="{st["mid"]}" marker-end="url(#arrow)"/>')
            for i, ln in enumerate(lines):
                o.append(self.text(x + 9, y + i * st["text"] * 1.25, ln))
            y += max(len(lines), 1) * st["text"] * 1.25 + 2.5
        # north arrow and scale bar, below the legend
        y = max(y + 6, self.oy + self.mh - 34)
        # north: a circle in outline, a line from its centre to the circle, pointing north
        o.append(f'<circle cx="{x + 6}" cy="{y + 6}" r="6" fill="none" stroke="{st["ink"]}" stroke-width="{st["mid"]}"/>'
                 f'<line x1="{x + 6}" y1="{y + 6}" x2="{x + 6}" y2="{y}" stroke="{st["ink"]}" stroke-width="{st["mid"]}"/>')
        L = nice((self.SIDE - 12) / self.k)
        y += 22
        # scale bar: a line that steps up and down, a tick and a number at every step
        n = next(n for n in ((4, 2, 1) if f"{L:g}"[0] == "2" else (5, 2, 1))
                 if L * self.k / n >= (len(f"{L:g}") + 1) * 0.6 * st["text"] + 1 or n == 1)
        s = L * self.k / n
        o.append(f'<path d="{"".join(f"M{x + i * s:.2f},{y + 1.6 * (i % 2)}h{s:.2f}" for i in range(n))}'
                 f'{"".join(f"M{x + i * s:.2f},{y}v1.6" for i in range(n + 1))}" fill="none" stroke="{st["ink"]}" stroke-width="{st["thin"]}"/>')
        for i in range(n + 1):
            o.append(self.text(x + i * s, y + 5, f"{L * i / n:g}" + (" m" if i == n else ""), anchor="middle"))
        o.append(self.text(x, y + 9.5, f"1:{self.scale:,} at {self.W:.0f} x {self.H:.0f} mm".replace(",", " ")))
        # sources
        fy = self.oy + max(self.mh, 150) + 6
        o.append(self.text(self.ox, fy, "Sources", weight="bold"))
        src = sources + [f"Base map: the project's site folder (see its SOURCES.md). Projection {self.S.crs.name}."]
        for ln in textwrap.wrap("  ·  ".join(src), int(self.mw / (st["text"] * 0.5)))[:6]:
            fy += st["text"] * 1.3
            o.append(self.text(self.ox, fy, ln, st["text"] * 0.9))
        o.append("</svg>")
        path.write_text("\n".join(o), encoding="utf-8")
        png(path, self.W, self.H)
        return path.name


KEYS = {"paper": ("paper", "background"), "ink": ("ink", "line", "lines", "text colour", "text color"), "accent": ("accent", "highlight", "new"),
        "context": ("context", "existing", "grey", "gray"), "water": ("water",), "cool": ("cool", "green", "vegetation")}


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
    ap.add_argument("--sheet", action="store_true", help="only remake climate_sheet from the drawings made, e.g. after writing summary.md")
    a = ap.parse_args()
    S, out = Site(a.site, a.buildings), Path(a.out)
    found, look = standard(out, a.style)
    st = dict(FALLBACK, **found)
    if a.sheet:  # only the sheet, from the drawings already made
        lines = (out / "drawings.txt").read_text(encoding="utf-8").splitlines()[1:]
        print(sheet(out, st, [n for n in lines if n and n != "climate_sheet.svg"]))
        return
    ext = box(*S.poly.buffer(a.margin).bounds)
    w, h = ext.bounds[2] - ext.bounds[0], ext.bounds[3] - ext.bounds[1]
    scale = a.scale or next((s for s in SCALES if w * 1000 / s <= 280 and h * 1000 / s <= 300), SCALES[-1])
    made = []

    def new(title, sub):
        return Map(S, st, ext, scale, title, sub)

    if (out / "fresh-air.geojson").exists():
        m = new("Fresh air", "Air corridors and flow as they are today")
        m.context()
        F = S.layer("fresh-air", out)
        for g, p in F:
            if p.get("kind") == "corridor":
                m.add(g, fill=st["accent"], fill_opacity=0.35, stroke=st["accent"], stroke_width=st["thin"])
        for g, p in F:
            if p.get("kind") == "flow":
                m.add(g, fill="none", stroke=st["ink"], stroke_width=st["mid"], marker_end="url(#arrow)")
        m.site()
        for lab in sorted({p.get("label", "corridor") for _, p in F if p.get("kind") == "corridor"}):
            m.key("fill", st["accent"], lab, opacity=0.35)
        if any(p.get("kind") == "flow" for _, p in F):
            m.key("arrow", st["ink"], "Air flow, direction of movement")
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
        for (g, p), c in zip(F, cols):
            m.add(g, fill=c, stroke="none")
        m.add(shapely.union_all([g for g, _ in S.layer(S.buildings_path.stem, S.buildings_path.parent)]), fill=st["ink"], fill_opacity=0.55)
        m.site()
        for (g, p), c in zip(F, cols):
            m.key("fill", c, p["label"])
        m.key("fill", st["ink"], "Existing buildings", opacity=0.55)
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
            m.add(shapely.union_all([g for g, _ in S.layer(S.buildings_path.stem, S.buildings_path.parent)]), fill=st["ink"])
            m.site()
            for (g, p), c in zip(G, cols):
                m.key("fill", c, f'{p["local_time"]}, sun {p["sun_altitude_deg"]:.0f}° high from {p["sun_azimuth_deg"]:.0f}°', opacity=0.6)
            m.key("fill", st["ink"], "Existing buildings")
            made.append(m.save(out / f"shadows_{day.lower().replace(' ', '-')}.svg", sun.get("sources", [])))

    if (out / "noise.geojson").exists():
        F = S.layer("noise", out)
        for period in dict.fromkeys(p["period"] for _, p in F):
            G = [(g, p) for g, p in F if p["period"] == period]
            r = meta(out, "noise").get("rail", {})
            sub = "Estimated level at about 4 m above ground, existing buildings screening"
            if r.get("included") and "assumed" in r.get("label", "").lower():
                sub += ". RAIL TRAFFIC ASSUMED, NOT FROM DATA"
            m = new(f"{'Road and rail' if r.get('included') else 'Road'} noise, {period}", sub)
            m.context(buildings=False)
            cols = ramp(len(G), st)
            for (g, p), c in zip(G, cols):
                m.add(g, fill=c, stroke="none", fill_opacity=0.85)
            m.add(shapely.union_all([g for g, _ in S.layer(S.buildings_path.stem, S.buildings_path.parent)]), fill=st["paper"], stroke=st["ink"], stroke_width=st["thin"])
            srcs = S.layer("noise-sources", out)
            for g, p in srcs:
                m.add(g, fill="none", stroke=st["ink"], stroke_width=st["thick"], **({"stroke_dasharray": "2 1"} if p.get("kind") == "rail" else {}))
            m.site()
            for (g, p), c in zip(G, cols):
                m.key("fill", c, p["label"], opacity=0.85)
            m.key("line", st["ink"], "Roads counted as noise sources", w=st["thick"])
            rail = meta(out, "noise").get("rail", {"label": "Railway not included: no train data"})
            if rail.get("included"):
                m.key("line", st["ink"], f'Railway counted as noise source. {rail["label"]}', w=st["thick"], dash="2 1")
            else:
                m.key("line", st["accent"], rail["label"].upper(), w=st["thick"], dash="0.6 0.9")
            made.append(m.save(out / f"noise_{period}.svg", meta(out, "noise").get("sources", [])))

    if (out / "heat.geojson").exists():
        m = new("Heat island", "How much each place heats up today, from what covers the ground")
        F = S.layer("heat", out)
        idx = [(g, p) for g, p in F if p["kind"] == "index"]
        cool = st.get("cool", mix(st["paper"], st["ink"], 0.35))
        cols = [mix(st["paper"], cool, 0.55), mix(st["paper"], cool, 0.2)] + ramp(4, st)[1:]
        for (g, p), c in zip(idx, cols):
            m.add(g, fill=c, stroke="none")
        for g, p in F:
            if p["kind"] == "unknown":
                m.add(g, fill=m.hatch("unknown", st["ink"], 1.2, 45, st["thin"]), fill_opacity=0.5, stroke="none")
        # buildings as outlines here, so no grey of theirs is mistaken for the cool class
        m.context(buildings=False)
        m.add(shapely.union_all([g for g, _ in S.layer(S.buildings_path.stem, S.buildings_path.parent)]), fill=st["paper"], stroke=st["ink"], stroke_width=st["thin"])
        m.site()
        for (g, p), c in zip(idx, cols):
            m.key("fill", c, p["label"].capitalize())
        if any(p["kind"] == "unknown" for _, p in F):
            m.key("fill", "url(#unknown)", "Too little land-use data to say", opacity=0.5)
        m.key("fill", st["paper"], "Existing buildings (roofs count as very hot)")
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
        made.append(m.save(out / "rules.svg", R.get("sources", [])))

    if (out / "wind.csv").exists():
        made.append(wind_rose(out, st, meta(out, "wind")))
    made.append(sheet(out, st, made))
    (out / "drawings.txt").write_text(f"Scale 1:{scale}. {look}.\n" + "\n".join(made) + "\n", encoding="utf-8")
    print(f"1:{scale}", look, made)


def sheet(out, st, names, W=420, H=297):
    """Every map small on one A3 landscape sheet, with summary.md (else the key numbers) as text. Run draw.py --sheet again after summary.md."""
    pad, head = 10, 16
    cols, rows = 4, 3
    cw, ch = (W - 2 * pad) / cols, (H - head - 2 * pad) / rows
    t = lambda x, y, s, size=st["text"], w="normal": (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{escape(st["font"])}" font-size="{size}" '
                                                     f'font-weight="{w}" fill="{st["ink"]}">{escape(s)}</text>')
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">',
         f'<rect width="100%" height="100%" fill="{st["paper"]}"/>', t(pad, pad + st["title"], "Climate of the site", st["title"] * 1.3, "bold")]
    pngs = [n.replace(".svg", ".png") for n in names if (out / n.replace(".svg", ".png")).exists()][:cols * rows - 2]
    for i, p in enumerate(pngs):
        x, y = pad + (i % cols) * cw, pad + head + (i // cols) * ch
        o.append(f'<image x="{x + 1:.1f}" y="{y + 1:.1f}" width="{cw - 2:.1f}" height="{ch - 2:.1f}" href="{p}" preserveAspectRatio="xMidYMid meet"/>')
    # text in the last two cells
    i = len(pngs)
    x, y = pad + (i % cols) * cw + 3, pad + head + (i // cols) * ch + 6
    width = int((cols - i % cols) * cw / (st["text"] * 0.5)) if i % cols else int(2 * cw / (st["text"] * 0.5))
    text = (out / "summary.md").read_text(encoding="utf-8").split("\n") if (out / "summary.md").exists() else []
    c = meta(out, "climate")
    if not text and c.get("key_numbers"):
        text = [f"{k.replace('_', ' ')}: {v}" for k, v in c["key_numbers"].items() if not isinstance(v, dict)]
    o.append(t(x, y, "Summary", st["text"] * 1.3, "bold"))
    for para in [s for s in text if s.strip()] + [""] + c.get("notes", []):
        for ln in textwrap.wrap(para, width) or [""]:
            y += st["text"] * 1.35
            o.append(t(x, y, ln))
        y += 1
    o.append(t(pad, H - 4, "Each map with its own legend, scale and sources at full size in this folder. A3, maps not to scale.", st["text"] * 0.85))
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
    t = lambda x, y, s, size=st["text"], w="normal", a="middle": (f'<text x="{x:.2f}" y="{y:.2f}" font-family="{escape(st["font"])}" font-size="{size}" '
                                                                   f'font-weight="{w}" text-anchor="{a}" fill="{st["ink"]}">{escape(s)}</text>')
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="{st["paper"]}"/>',
         t(10, 12, "Wind", st["title"], "bold", "start"), t(10, 18, "Share of hours the wind blows from each direction, by speed", a="start")]
    for i, s in enumerate(seasons):
        cx, cy = 10 + R + i * (2 * R + gap), 26 + R
        for k in range(1, int(vmax // ring) + 2):
            r = R * k * ring / vmax * 0.95
            if r <= R:
                o.append(f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" stroke="{st["context"]}" stroke-width="{st["thin"]}"/>')
                o.append(t(cx + 1, cy - r - 0.6, f"{k * ring:g}%", st["text"] * 0.8, a="start"))
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
    return p.name


if __name__ == "__main__":
    main()
