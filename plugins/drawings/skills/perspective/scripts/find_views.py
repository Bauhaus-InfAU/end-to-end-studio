"""Chooses pedestrian-level viewpoints from the design's streets and public spaces.

Four situations are looked for. Candidates stand on public ground and are scored by casting
rays through the frame in plan: how much new building, public space, landscape, depth and
tree they show, and whether anything blocks the eye. The narrative sets the situations' order,
by the English words in WORDS; with none of them, the order stays as in WORDS, with a warning.
"""
import math
import re

import numpy as np
import shapely
from shapely.geometry import Point
from shapely.ops import unary_union

from draw_view import H, HORIZON, W

EYE = 1.65                                  # the usual eye height: frame_new is an estimate for ranking
RAYS, REACH, MIN_APART = 41, 220.0, 120.0
WORDS = {
    "square": ["square", "plaza", "piazza", "centre", "center", "hub", "station", "stop", "market", "mobility"],
    "green": ["green", "corridor", "park", "landscape", "meadow", "garden", "forest", "wood", "planted"],
    "street": ["street", "shared", "lane", "boulevard", "avenue", "walk"],
    "edge": ["edge", "settlement", "neighbour", "existing", "field", "transition", "context"],
}
FOR_WHAT = {
    "square": "a public square with the buildings around it",
    "green": "open green space with the buildings at its edge",
    "street": "everyday street life between the buildings",
    "edge": "where the new buildings meet what was already there",
}


def narrative_order(scene):
    """The situations, most talked about first, with the line that speaks for each."""
    path = scene.proposal / "narrative" / "narrative.md"
    if not path.exists():
        scene.warn("No narrative/narrative.md: the views follow the geometry alone.")
        return list(WORDS), {}
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln.strip(" -*#") for ln in text.splitlines() if len(ln.strip()) > 20]
    counts, evidence = {}, {}
    for k, words in WORDS.items():
        pattern = re.compile(r"\b(" + "|".join(words) + r")\w*", re.I)
        counts[k] = len(pattern.findall(text))
        best = max(lines, key=lambda ln: len(pattern.findall(ln)), default=None)
        if best and pattern.search(best):
            evidence[k] = best[:160]
    scene.used.append("narrative/narrative.md")
    if not any(counts.values()):
        scene.warn("narrative/narrative.md has none of the English words the views are ordered by: the views follow the geometry alone. Read it, edit views.json to fit, and redraw with --views.")
    return sorted(WORDS, key=lambda k: -counts[k]), evidence


def segments(scene):
    """Everything that stops the eye in plan: (x1, y1, x2, y2), kind, height."""
    seg, kind, height = [], [], []
    codes = {"new": 0, "kept": 1, "context": 2}
    area = scene.site.buffer(REACH + 100)
    for b in scene.buildings:
        if not b["geom"].intersects(area):
            continue
        for part in getattr(b["geom"], "geoms", [b["geom"]]):
            if part.geom_type != "Polygon":
                continue
            c = np.array(part.exterior.coords)[:, :2]
            for a, e in zip(c, c[1:]):
                seg.append((*a, *e)), kind.append(codes[b["group"]]), height.append(b["height"])
    for g, h, _ in scene.tall:
        for part in getattr(g.intersection(area), "geoms", [g.intersection(area)]):
            if part.geom_type != "Polygon":
                continue
            c = np.array(part.exterior.coords)[:, :2]
            for a, e in zip(c, c[1:]):
                seg.append((*a, *e)), kind.append(3), height.append(h)
    r = scene.assumed["tree_crown_radius"]
    for x, y, h in scene.trees:
        seg.append((x - r, y, x + r, y)), kind.append(4), height.append(h)
        seg.append((x, y - r, x, y + r)), kind.append(4), height.append(h)
    if not seg:
        return np.zeros((0, 4)), np.zeros(0, int), np.zeros(0)
    return np.array(seg), np.array(kind), np.array(height)


def candidates(scene):
    """(situation, x, y, heading in degrees)."""
    out = []
    # along streets, on the pavement, looking along the street
    for g, w in scene.streets:
        for line in getattr(g, "geoms", [g]):
            for s in np.arange(10, max(line.length, 11), 35):
                p, q = line.interpolate(s), line.interpolate(min(s + 1, line.length))
                dx, dy = q.x - p.x, q.y - p.y
                n = math.hypot(dx, dy) or 1
                off = max(w / 2 - 1.5, 0)
                for side in (1, -1):
                    x, y = p.x - dy / n * off * side, p.y + dx / n * off * side
                    base = math.degrees(math.atan2(dx, dy))
                    for turn in (-18, 18, 162, 198):
                        out.append(("street", x, y, base + turn))
    for g, use in scene.open_spaces:
        if use not in ("square", "park"):
            continue
        for part in getattr(g, "geoms", [g]):
            if part.geom_type != "Polygon" or part.area < 100:
                continue
            c = part.centroid
            ring = part.exterior
            inner = part.buffer(-3)
            step = max(ring.length / 12, 25)
            for s in np.arange(0, ring.length, step):
                p = ring.interpolate(s)
                near = inner.boundary.interpolate(inner.boundary.project(p)) if not inner.is_empty else p
                base = math.degrees(math.atan2(c.x - near.x, c.y - near.y))
                for turn in (-60, -30, 0, 30, 60):
                    out.append(("square" if use == "square" else "green", near.x, near.y, base + turn))
    # on public ground near landscape or context, looking towards it
    others = [g for g, _, _ in scene.tall] + [b["geom"] for b in scene.buildings if b["group"] != "new"]
    if others and scene.public is not None:
        edge_of = unary_union([g.buffer(0) for g in others])
        for kind, x, y, _ in out[::3]:
            d = edge_of.distance(Point(x, y))
            if 8 < d < 70:
                near = shapely.ops.nearest_points(Point(x, y), edge_of)[1]
                base = math.degrees(math.atan2(near.x - x, near.y - y))
                for turn in (-30, 30):
                    out.append(("edge", x, y, base + turn))
    return out


def score(scene, seg, kind, tall, x, y, heading, hfov):
    """The share of the frame's rays that show each thing, and one score. Tree crowns stand above the eye, so they hide nothing here."""
    mid = np.hypot((seg[:, 0] + seg[:, 2]) / 2 - x, (seg[:, 1] + seg[:, 3]) / 2 - y)
    near = mid < REACH + 60
    s, k, up = seg[near], kind[near], tall[near]
    angles = np.radians(heading + np.linspace(-hfov / 2, hfov / 2, RAYS))
    dx, dy = np.sin(angles)[:, None], np.cos(angles)[:, None]
    ex, ey = s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]
    ax, ay = s[:, 0] - x, s[:, 1] - y
    den = dx * ey - dy * ex
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (ax * ey - ay * ex) / den
        u = (ax * dy - ay * dx) / den
    t = np.where((t > 0.2) & (u >= 0) & (u <= 1), t, np.inf)
    solid = k != 4
    if t.size and solid.any():
        ts = t[:, solid]
        first = ts.argmin(axis=1)
        dist = np.minimum(ts.min(axis=1), REACH)
        hit = np.where(np.isfinite(ts.min(axis=1)), k[solid][first], -1)
        wall = up[solid][first]
        rise = np.degrees(np.arctan2(wall, dist))     # how high it stands in the frame
    else:
        dist, hit, rise, wall = np.full(RAYS, REACH), np.full(RAYS, -1), np.zeros(RAYS), np.zeros(RAYS)
    tree = t[:, ~solid].min(axis=1) if (~solid).any() and t.size else np.full(RAYS, np.inf)
    m = {
        "new": float(np.mean(hit == 0)),
        "presence": float(np.mean(np.minimum(rise, 30) * (hit == 0)) / 30),
        "kept_context": float(np.mean((hit == 1) | (hit == 2))),
        "vegetation": float(np.mean(hit == 3)),
        "trees": float(np.mean(tree < dist)),
        "open": float(np.mean(dist > 20)),
        "blocked": float(np.mean(dist < 5)),
        "tree_near": float(np.mean(tree < 12)),
        "green_wall": float(np.mean((hit == 3) & (dist < 40))),   # woodland close in front: a grey slab in the view
        "depth": float(np.std(np.log(np.maximum(dist, 1)))),
        "void": float(np.mean(dist > 80)),          # the eye runs out with nothing to stop it
        "framed": min(float(np.mean(dist[:RAYS // 3] < 60)), float(np.mean(dist[-(RAYS // 3):] < 60))),   # held on both sides
    }
    spread = np.radians(np.linspace(-hfov / 2, hfov / 2, RAYS))
    f, z, width = W / 2 / np.tan(np.radians(hfov) / 2), dist * np.cos(spread), 1 / np.cos(spread) ** 2   # rays are even in angle, pixels in its tangent
    top, foot = np.clip(H * HORIZON - f * (wall - EYE) / z, 0, H), np.clip(H * HORIZON + f * EYE / z, 0, H)
    m["frame_new"] = float(np.sum(width / width.sum() * (foot - top) / H * (hit == 0)))   # share of the picture that is new building
    samples = np.outer(np.array([12.0, 25, 45]), np.sin(angles[::4])) + x, np.outer(np.array([12.0, 25, 45]), np.cos(angles[::4])) + y
    m["public"] = float(np.mean(shapely.contains_xy(scene.public, samples[0], samples[1]))) if scene.public is not None else 0.0
    green = getattr(scene, "green_union", None)
    m["green"] = float(np.mean(shapely.contains_xy(green, samples[0], samples[1]))) if green is not None else 0.0
    landscape = min(1, (m["green"] + m["vegetation"]) / 0.3)
    m["score"] = round(
        0.6 * (1 - abs(m["new"] - 0.45) / 0.55)     # buildings carry the frame without walling it
        + 1.0 * min(1, m["presence"] / 0.2)         # close enough to read as architecture
        + 0.5 * min(1, m["public"] / 0.5)           # public space in front of them
        + 0.5 * landscape                           # landscape in the picture
        + 0.4 * min(1, m["open"] / 0.5)             # room in the foreground, for people
        + 0.4 * min(1, m["depth"] / 0.8)            # near and far
        + 0.2 * min(1, m["trees"] / 0.15)
        + 0.5 * min(1, m["framed"] / 0.5)           # a space, not a block beside a field
        - 0.8 * m["void"]
        - 2.0 * m["blocked"] - 1.5 * m["tree_near"] - 1.5 * min(1, m["green_wall"] / 0.25), 3)
    return m


def choose(scene, count, hfov):
    """The views, in order, and all scored candidates."""
    order, evidence = narrative_order(scene)
    if scene.public is None:
        scene.warn("The massing has no streets, parks or squares, so no pedestrian viewpoint can be chosen.")
        return [], []
    scene.green_union = unary_union([g for _, g, tone in scene.flats if tone in ("green", "park", "garden")] or [Point(0, 0).buffer(0.1)])
    seg, kind, tall = segments(scene)
    bad = unary_union([b["geom"].buffer(1.5) for b in scene.buildings] + [g for g, _, _ in scene.tall]
                      + [g for _, g, tone in scene.flats if tone == "water"])
    raw = candidates(scene)
    stride = max(1, len(raw) // 2500)
    scored = []
    for sit, x, y, heading in raw[::stride]:
        if not shapely.contains_xy(scene.public, x, y) or shapely.contains_xy(bad, x, y):
            continue
        m = score(scene, seg, kind, tall, x, y, heading, hfov)
        if m["frame_new"] >= 0.1:
            scored.append({"situation": sit, "x": x, "y": y, "heading": heading % 360, **m})
    scored.sort(key=lambda c: -c["score"])
    picks = []
    for sit in order * count:
        if len(picks) >= count:
            break
        pool = [c for c in scored if c["situation"] == sit
                and all(math.hypot(c["x"] - p["x"], c["y"] - p["y"]) >= MIN_APART for p in picks)]
        if pool:
            picks.append(dict(pool[0], why=FOR_WHAT[sit], narrative=evidence.get(sit, "")))
    missing = [s for s in order if not any(c["situation"] == s for c in scored)]
    if missing:
        scene.warn("No usable viewpoint for: " + ", ".join(missing) + ".")
    if len(picks) < count:
        scene.warn(f"Only {len(picks)} of {count} views could be placed {MIN_APART:.0f} m apart.")
    return picks, scored
