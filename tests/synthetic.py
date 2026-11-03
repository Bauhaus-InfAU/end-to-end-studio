"""A small proposal folder built from the committed site, so the tests run on any computer.

make_proposal(tmp_path) copies the site, writes a structure plan with one neighbourhood and its centres,
green, routes and gateway, a massing config and a drawing style, and returns the proposal folder.
"""
import json, shutil
from pathlib import Path
from shapely.geometry import shape, mapping, box, LineString, Point
from shapely.ops import transform, polylabel
import pyproj

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "competition/site"
FIX = Path(__file__).parent / "fixtures"
STYLE = REPO / "plugins/drawings/skills/drawing-graphics/base.json"


def utm_epsg(lon, lat):
    """The UTM zone of a point, as an EPSG code."""
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


def make_proposal(tmp_path, split_green=True, holds=True):
    tmp = Path(tmp_path)
    site_dir = tmp / "site"
    shutil.copytree(SITE, site_dir)
    out = tmp / "proposals" / "2026-01-01_t"

    g = shape(json.loads((SITE / "site.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
    c = g.centroid
    epsg = utm_epsg(c.x, c.y)
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform
    shrunk = transform(to_m, g).buffer(-100)
    p = polylabel(shrunk, 1.0)   # the point deepest inside the shrunk site
    for W, H in [(400, 300), (300, 220)]:
        nb = box(p.x - W / 2, p.y - H / 2, p.x + W / 2, p.y + H / 2)
        if nb.within(shrunk):
            break
    else:
        raise RuntimeError("no room for the synthetic neighbourhood in this site")
    x0, y0, x1, y1 = nb.bounds
    cx = (x0 + x1) / 2

    base = dict(basis="test", source="synthetic test proposal")
    feats = []

    def add(geom, **props):
        feats.append({"type": "Feature", "properties": {**props, **base},
                      "geometry": mapping(transform(to_ll, geom))})

    add(nb, kind="neighbourhood", name="Field", action="new")
    sq = dict(kind="centre", name="Square", action="new", level="main")
    co = dict(kind="centre", name="Corner", action="new", level="local")
    if holds:
        sq["holds"] = "stop, bus station, shops"
        co["holds"] = "school, daycare"
    add(box(cx - 30, y0, cx + 30, y0 + 60), **sq)
    add(box(x1 - 60, y1 - 60, x1, y1), **co)
    if split_green:
        add(box(cx - 25, y0, cx + 25, y1), kind="green", name="Strip", action="new", roles=["climate"])
    add(LineString([(x0, y0), (x1, y0)]), kind="route", name="Main road", action="new", level="main")
    add(LineString([(cx, y0), (cx, y1)]), kind="route", name="Path", action="new", level="landscape")
    add(Point(x0, y0), kind="gateway", name="Gate", action="new")

    (out / "structure-plan").mkdir(parents=True)
    (out / "structure-plan/structure-plan.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")

    cfg = json.loads((FIX / "massing_config_run3.json").read_text(encoding="utf-8"))
    cfg["density"] = {"value": {"Field": "medium"}, "source": "test"}
    cfg["phase1"] = {"value": ["Field"], "source": "test"}
    cfg["site_plan_scale"] = {"value": 3000, "source": "test"}
    (out / "massing").mkdir()
    (out / "massing/config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")

    (out / "drawing-graphics").mkdir()
    shutil.copy(STYLE, out / "drawing-graphics/style.json")
    return out
