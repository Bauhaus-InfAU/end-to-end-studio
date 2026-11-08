"""No building is cut by the edge of its land: on a neighbourhood with slanted sides, every new building of the
massing stays whole (only right angles, no slanted cut) and lies inside its neighbourhood. Synthetic data."""
import json, math, os, subprocess, sys
import pyproj
from shapely.geometry import shape, mapping, Polygon
from shapely.ops import transform
from conftest import REPO
from synthetic import make_proposal, utm_epsg

MASSING = REPO / "plugins/design/skills/massing/scripts/massing.py"


def slanted_edges(poly):
    """edges longer than 1.5 m that are not at a right angle to the longest edge"""
    cs = list(poly.exterior.coords)
    edges = [(math.dist(a, b), math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))) for a, b in zip(cs, cs[1:])]
    ref = max(edges)[1]
    return [e for e in edges if e[0] > 1.5 and min((e[1] - ref) % 90, 90 - (e[1] - ref) % 90) > 3]


def test_no_building_is_cut_by_its_land(tmp_path):
    prop = make_proposal(tmp_path, split_green=False)
    sp_path = prop / "structure-plan/structure-plan.geojson"
    sp = json.loads(sp_path.read_text(encoding="utf-8"))
    nb_f = next(f for f in sp["features"] if f["properties"]["kind"] == "neighbourhood")
    c = shape(nb_f["geometry"]).centroid
    epsg = utm_epsg(c.x, c.y)
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform
    x0, y0, x1, y1 = transform(to_m, shape(nb_f["geometry"])).bounds
    nb = Polygon([(x0, y0), (x1, y0), (x1 - 120, y1), (x0 + 120, y1)])   # slanted sides the block grid must cross
    nb_f["geometry"] = mapping(transform(to_ll, nb))
    sp_path.write_text(json.dumps(sp), encoding="utf-8")

    r = subprocess.run([sys.executable, str(MASSING), "--proposal", str(prop), "--site", str(tmp_path / "site"),
                        "--config", str(prop / "massing/config.json")], capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode == 0, r.stderr[-2000:]

    feats = json.loads((prop / "massing/massing.geojson").read_text(encoding="utf-8"))["features"]
    new = [transform(to_m, shape(f["geometry"])) for f in feats
           if f["properties"].get("kind") == "building" and f["properties"].get("existing") is False
           and f["properties"].get("neighbourhood") == "Field"]
    assert len(new) >= 5, "too few buildings to test"
    cut = [b for b in new if slanted_edges(b)]
    outside = [b for b in new if b.difference(nb).area > 1]
    assert not cut, "%d of %d buildings are cut by the edge of their land" % (len(cut), len(new))
    assert not outside, "%d buildings reach outside their neighbourhood" % len(outside)
