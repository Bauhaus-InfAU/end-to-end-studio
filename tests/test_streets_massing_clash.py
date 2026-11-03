"""No building stands on the street surface: the massing keeps its streets off the buildings it keeps, and the streets
skill adds nothing (a link, a turning head, a rounded corner) that reaches into a building. Synthetic data."""
import json, os, subprocess, sys
import pytest
import pyproj
from shapely.geometry import shape, mapping, box, LineString
from shapely.ops import transform, unary_union
from conftest import REPO

try:
    from synthetic import make_proposal
except ImportError:
    make_proposal = None

MASSING = REPO / "plugins/design/skills/massing/scripts/massing.py"
STREETS = REPO / "plugins/design/skills/streets/scripts/streets.py"
EPSG = 32633
TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
TO_LL = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform


def run(script, *args):
    r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONUTF8": "1", "CHROME_PATH": os.devnull + "-none"})   # no PNG needed
    assert r.returncode == 0, r.stderr[-2000:]
    return r


def write_fc(path, feats):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": p, "geometry": mapping(transform(TO_LL, g))} for g, p in feats]}), encoding="utf-8")


def read_m(path):
    return [(transform(TO_M, shape(f["geometry"])), f["properties"])
            for f in json.loads(path.read_text(encoding="utf-8"))["features"]]


def test_streets_adds_nothing_into_buildings(tmp_path):
    """A 10 m street that ends in a field gets a turning head; the rows beside its end stand 2 m off its kerb."""
    x, y = 500000.0, 5430000.0
    site = box(x, y, x + 400, y + 400)
    write_fc(tmp_path / "site/site.geojson", [(site, {})])
    write_fc(tmp_path / "site/streets.geojson", [(LineString([(x - 100, y - 10), (x + 500, y - 10)]),
                                                 {"highway": "residential"})])
    end = (x + 200, y + 200)
    rows = [box(end[0] + 7, end[1] - 40, end[0] + 20, end[1] + 5), box(end[0] - 20, end[1] - 40, end[0] - 7, end[1] + 5)]
    write_fc(tmp_path / "massing.geojson",
             [(LineString([(end[0], y - 10), end]), {"kind": "street", "width": 10, "level": "secondary"})] +
             [(b, {"kind": "building", "floors": 4, "existing": False}) for b in rows])
    run(STREETS, "--layers", tmp_path / "site", "--out", tmp_path / "streets", "--massing", tmp_path / "massing.geojson")
    feats = read_m(tmp_path / "streets/streets.geojson")
    new = unary_union([g for g, p in feats if p.get("kind") == "street" and not p.get("existing")])
    assert any(p.get("type") == "turning head" for g, p in feats if p.get("kind") == "street-end")
    assert all(b.intersection(new).area < 1 for b in rows)


@pytest.mark.skipif(make_proposal is None, reason="needs tests/synthetic.py")
def test_massing_lays_streets_off_kept_buildings(tmp_path):
    """A kept building 3 m beside the structure plan's main road: the street stops short of it and a path goes on."""
    out = make_proposal(tmp_path)
    site_dir = tmp_path / "site"
    sp = out / "structure-plan/structure-plan.geojson"
    fc = json.loads(sp.read_text(encoding="utf-8"))
    c = shape(fc["features"][0]["geometry"]).centroid
    to_m = pyproj.Transformer.from_crs(4326, (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1, always_xy=True)
    road = next(transform(to_m.transform, shape(f["geometry"])) for f in fc["features"] if f["properties"].get("name") == "Main road")
    mid = road.interpolate(0.7, normalized=True)
    shed = box(mid.x - 10, mid.y + 3, mid.x + 10, mid.y + 15)
    bf = site_dir / "buildings.geojson"
    blds = json.loads(bf.read_text(encoding="utf-8"))
    blds["features"].append({"type": "Feature", "properties": {"id": "test-shed", "building": "yes", "height": 4},
                             "geometry": mapping(transform(lambda *a: to_m.transform(*a, direction="INVERSE"), shed))})
    bf.write_text(json.dumps(blds), encoding="utf-8")
    run(MASSING, "--proposal", out, "--site", site_dir, "--config", out / "massing/config.json")
    feats = [(transform(to_m.transform, shape(f["geometry"])), f["properties"])
             for f in json.loads((out / "massing/massing.geojson").read_text(encoding="utf-8"))["features"]]
    kept = [g for g, p in feats if p.get("kind") == "building" and p.get("existing")]
    streets = [(g, p) for g, p in feats if p.get("kind") == "street" and p.get("level") in ("main", "local")]
    assert any(p.get("name") == "Main road" for g, p in streets)
    for g, p in streets:
        area = g.buffer(p["width"] / 2, cap_style="flat")
        assert all(b.intersection(area).area < 1 for b in kept), p.get("name")
    assert any(p.get("name") == "Main road" and p.get("level") == "path" for g, p in feats if p.get("kind") == "street")
