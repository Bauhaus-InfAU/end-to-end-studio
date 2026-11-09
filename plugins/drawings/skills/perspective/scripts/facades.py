"""Facades on the base views: one facade system per building, drawn in true perspective over each <stem>_base.svg.

    python facades.py <proposal folder> [--site DIR]   (the same --site as perspective.py, so the views line up)

Run after perspective.py and before render.py. The systems and which building type takes which are in the skill's
facades.json, a PROVISIONAL design proposal, not a team decision. A proposal's perspective/facades_override.json overrides
it key by key: write the team's facade instructions there. Every system is the same on every floor and bay of a
building, ground floor included; systems never mix on one building. Each system is an opening of a given width,
sill and head per 3 m bay, with an optional glass rail on the upper floors.
Keeps the plain view as <stem>_plain.svg/png (again whenever perspective.py redrew it), so a rerun starts from it; writes <stem>_base.svg/png
with the facades, and perspective/facades_drawn.json with what was drawn and where the systems came from.
Never changes footprints, heights, floors or the camera. Entrances come from ground-floor/*.geojson when there is one.
"""
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import Point, shape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scene import Scene      # noqa: E402
import draw_view as dv       # noqa: E402

GLASS, DOOR_W, DOOR_H, REVEAL = "#7d8790", 1.2, 2.4, 0.15


def config(proposal):
    cfg = json.loads((HERE.parent / "facades.json").read_text(encoding="utf-8"))
    src = ["skill facades.json (provisional proposal)"]
    path = proposal / "perspective" / "facades_override.json"
    if path.exists():
        o = json.loads(path.read_text(encoding="utf-8"))
        for k, v in o.items():
            cfg[k] = {**cfg[k], **v} if isinstance(v, dict) and isinstance(cfg.get(k), dict) else v
        src.append(str(path.relative_to(proposal)))
    return cfg, src


def main(proposal, site=None):
    out = proposal / "perspective"
    spec = json.loads((out / "views.json").read_text(encoding="utf-8"))
    cfg, sources = config(proposal)
    try:
        st = json.loads((proposal / "drawing-graphics" / "style.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    ink, shadow = st.get("ink", "#1a1a1a"), st.get("shadow", "#a8a8a8")
    bay = float(cfg.get("bay_m", 3.0))

    sc = Scene(proposal, site=site)
    terrain = out / "terrain.csv"
    if terrain.exists():
        sc.use_terrain(terrain)
    mass = []
    mj = proposal / "massing" / "massing.geojson"
    if mj.exists():
        for f in json.loads(mj.read_text(encoding="utf-8"))["features"]:
            p = f.get("properties") or {}
            if p.get("kind") == "building" and p.get("existing") is False:
                try:
                    mass.append((sc.local(shape(f["geometry"])).buffer(0), p))
                except Exception:
                    pass
    doors = []
    for gf in sorted((proposal / "ground-floor").glob("*.geojson")) if (proposal / "ground-floor").exists() else []:
        for f in json.loads(gf.read_text(encoding="utf-8")).get("features", []):
            p = f.get("properties") or {}
            if p.get("kind") == "entrance" and p.get("bearing_deg") is not None:
                doors.append((sc.local(shape(f["geometry"])), float(p["bearing_deg"])))

    def type_of(g):
        best = max(mass, key=lambda t: t[0].intersection(g).area if t[0].intersects(g) else 0, default=None)
        return str(best[1].get("type") or "") if best and best[0].intersects(g) else ""

    record = {"sources": sources, "status": cfg.get("status"), "views": []}
    for view in spec["views"]:
        stem = view.get("stem") or view["name"]
        files = view.get("files", {})
        svg, png = out / files.get("base_svg", f"{stem}_base.svg"), out / files.get("base_png", f"{stem}_base.png")
        plain_svg, plain_png = out / f"{stem}_plain.svg", out / f"{stem}_plain.png"
        if not plain_svg.exists() or '<g id="facades">' not in svg.read_text(encoding="utf-8"):   # a fresh or redrawn view
            shutil.copy(svg, plain_svg)
            shutil.copy(png, plain_png)
        depth = np.asarray(__import__("PIL.Image", fromlist=["Image"]).open(out / files.get("depth_png", f"{stem}_depth.png")).convert("L")).astype(float) / 255
        x, y = sc.to_local.transform(*view["eye"])
        cam = dv.Camera(sc, dict(x=x, y=y, heading=view["heading_deg"], hfov=view["hfov_deg"], eye_height=view["eye_height_m"]))
        logr = math.log(dv.FAR / 2)

        def g_of(z):
            return max(0.0, min(1.0, 1 - math.log(max(z, 2) / 2) / logr))

        def visible(pts, tol=0.012):
            inframe = False
            for X, Y, Z in pts:
                c = cam.cam(X, Y, Z)
                if c[2] < dv.NEAR:
                    return False
                u, v = cam.px(c)
                if not (0 <= u < dv.W and 0 <= v < dv.H):
                    continue
                inframe = True
                if depth[int(v), int(u)] > g_of(c[2]) + tol:
                    return False
            return inframe

        def P(p):
            return "%.1f,%.1f" % cam.px(cam.cam(*p))

        def poly(pts, fill, extra=""):
            return f'<polygon points="{" ".join(P(p) for p in pts)}" fill="{fill}"{extra}/>'

        layers = {"recess": [], "glass": [], "rail": [], "door": []}
        drawn = {}
        for b in sorted(sc.buildings, key=lambda b: -b["geom"].distance(Point(x, y))):
            if b["group"] != "new" or not b.get("floors") or b["geom"].centroid.distance(Point(x, y)) > 160:
                continue
            typ = type_of(b["geom"])
            name = cfg["by_type"].get(typ, cfg.get("default", "horizontal"))
            s = cfg["systems"][name]
            n = int(b["floors"])
            for part in dv.polys(b["geom"]):
                bx, by = part.exterior.xy
                base = float(sc.ground(np.array(bx), np.array(by)).min())
                top = float(sc.ground(np.array([part.centroid.x]), np.array([part.centroid.y]))[0]) + b["height"]
                fh = (top - base) / n
                for ring in dv.rings_xy(part):
                    for a, c in zip(ring, ring[1:]):
                        dx, dy = c[0] - a[0], c[1] - a[1]
                        L = math.hypot(dx, dy)
                        if L < bay:
                            continue
                        nx, ny = dy / L, -dx / L
                        mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
                        if part.contains(Point(mx + nx * 0.5, my + ny * 0.5)):
                            nx, ny = -nx, -ny
                        if (x - mx) * nx + (y - my) * ny <= 0:
                            continue
                        ux, uy = dx / L, dy / L

                        def W0(t, z, d=0.06):
                            return (a[0] + nx * d + ux * t, a[1] + ny * d + uy * t, z)
                        door_t = [(d.x - a[0]) * ux + (d.y - a[1]) * uy for d, _ in doors
                                  if abs((d.x - a[0]) * nx + (d.y - a[1]) * ny) < 1.0 and -0.5 <= (d.x - a[0]) * ux + (d.y - a[1]) * uy <= L + 0.5]
                        nb = int(L // bay)
                        o0 = (L - nb * bay) / 2
                        for k in range(n):
                            for j in range(nb):
                                if k == 0 and any(o0 + j * bay - 0.2 <= t <= o0 + (j + 1) * bay + 0.2 for t in door_t):
                                    continue
                                cx = o0 + j * bay + bay / 2
                                t0, t1 = cx - s["width_m"] / 2, cx + s["width_m"] / 2
                                z0, z1 = base + k * fh + s["sill"] * fh, base + k * fh + s["head"] * fh
                                q = [W0(t0, z0), W0(t1, z0), W0(t1, z1), W0(t0, z1)]
                                lift = min(0.35, 0.4 * (z1 - z0))
                                test = [W0(t0 + 0.12, z1 - 0.1), W0(t1 - 0.12, z1 - 0.1), W0(cx, (z0 + lift + z1) / 2)]
                                if not visible(test):          # top corners and centre: ground at the foot may cover the sill
                                    continue
                                drawn[name] = drawn.get(name, 0) + 1
                                layers["recess"].append(poly(q, shadow))
                                layers["glass"].append(poly([W0(t0, z0, -REVEAL), W0(t1, z0, -REVEAL), W0(t1, z1 - 0.06, -REVEAL), W0(t0, z1 - 0.06, -REVEAL)], GLASS))
                                if s.get("rail") and k > 0:
                                    layers["rail"].append(poly([W0(t0, z0 + 0.95, 0.04), W0(t1, z0 + 0.95, 0.04), W0(t1, z0 + 1.0, 0.04), W0(t0, z0 + 1.0, 0.04)],
                                                               "#ffffff", f' stroke="{ink}" stroke-width="0.5"'))
        for d, bearing in doors:
            bn = math.radians(bearing)
            nx, ny = math.sin(bn), math.cos(bn)
            if nx * (x - d.x) + ny * (y - d.y) <= 0 or math.hypot(x - d.x, y - d.y) > 160:
                continue
            tx, ty = ny, -nx
            z0 = float(sc.ground(np.array([d.x]), np.array([d.y]))[0])
            X, Y = d.x + nx * 0.06, d.y + ny * 0.06
            if visible([(X, Y, z0 + DOOR_H / 2)], tol=0.03):
                layers["door"].append(poly([(X - tx * DOOR_W / 2, Y - ty * DOOR_W / 2, z0), (X + tx * DOOR_W / 2, Y + ty * DOOR_W / 2, z0),
                                            (X + tx * DOOR_W / 2, Y + ty * DOOR_W / 2, z0 + DOOR_H), (X - tx * DOOR_W / 2, Y - ty * DOOR_W / 2, z0 + DOOR_H)],
                                           "#3a3a3a", ' stroke="#000" stroke-width="0.6"'))
                drawn["doors"] = drawn.get("doors", 0) + 1
        layer = '<g id="facades">' + "".join("".join(layers[k]) for k in ("recess", "glass", "rail", "door")) + "</g>"
        svg.write_text(plain_svg.read_text(encoding="utf-8").replace("</svg>", layer + "</svg>"), encoding="utf-8")
        dv.to_png(svg, png)
        record["views"].append({"name": view["name"], "drawn": drawn})
        print(view["name"], drawn)
    (out / "facades_drawn.json").write_text(json.dumps(record, indent=1), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proposal")
    ap.add_argument("--site", help="the site folder given to perspective.py")
    a = ap.parse_args()
    main(Path(a.proposal).resolve(), a.site)
