"""The open-space skill's script on a synthetic sloped site: with the site folder's terrain the hollow sits at the
park's low end and the rain runs downhill to it; without terrain it keeps its old placement and says so."""
import csv, json, os, subprocess, sys

import numpy as np
import pyproj
import pytest
from shapely.geometry import LineString, box, mapping, shape
from shapely.ops import transform

from conftest import REPO

SCRIPT = REPO / "plugins/design/skills/open-space/scripts/open_space.py"
EPSG = 32632                          # a UTM zone, metres
to_ll = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform
to_m = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
X0, Y0 = 500000.0, 5540000.0          # the site's south-west corner
SLOPE = 0.02                          # the ground falls 2 % towards the east


def fc(geoms_props):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": p, "geometry": mapping(transform(to_ll, g))} for g, p in geoms_props]}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture(scope="module")
def sloped(tmp_path_factory):
    """A 500 x 200 m site split by a wall of buildings into a west park and an east park, and a house in the west
    park near the wall: its nearest park is the west one, but its rain runs east, downhill."""
    root = tmp_path_factory.mktemp("open-space")
    b = lambda x0, y0, x1, y1: box(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1)
    site = b(0, 0, 500, 200)
    site_dir = root / "site"
    write(site_dir / "site.geojson", fc([(site, {"name": "test"})]))
    with open(site_dir / "terrain.csv", "w", newline="", encoding="utf-8") as f:   # a regular lon/lat grid
        w = csv.writer(f)
        w.writerow(["lon", "lat", "ele"])
        lo0, la0 = to_ll(X0 - 150, Y0 - 150)
        lo1, la1 = to_ll(X0 + 650, Y0 + 350)
        for lon in np.linspace(lo0, lo1, 60):
            for lat in np.linspace(la0, la1, 40):
                x, _ = to_m(lon, lat)
                w.writerow([f"{lon:.7f}", f"{lat:.7f}", f"{300 - SLOPE * (x - X0):.3f}"])
    bld = {"kind": "building", "floors": 4, "use": "residential"}
    write(root / "massing.geojson", fc([(b(200, 0, 250, 200), bld), (b(160, 80, 190, 120), bld)]))
    write(root / "config.json", {"residents": 100, "green_m2_per_resident": 10, "play_m2_per_resident": 1.5,
                                 "play_min_m2": 100, "scale": 3000, "sources": {"residents": "test"}})
    flat_dir = root / "site-flat"
    write(flat_dir / "site.geojson", fc([(site, {"name": "test"})]))
    return root, site_dir, flat_dir


def run(root, site_dir, out):
    r = subprocess.run([sys.executable, str(SCRIPT), "--site", str(site_dir / "site.geojson"), "--layers", str(site_dir),
                        "--massing", str(root / "massing.geojson"), "--config", str(root / "config.json"),
                        "--out", str(out)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode == 0, r.stderr[-2000:]
    feats = json.loads((out / "open-space.geojson").read_text(encoding="utf-8"))["features"]
    basins = [(transform(to_m, shape(f["geometry"])), f["properties"]) for f in feats
              if f["properties"]["kind"] == "retention" and "needed_m3" in f["properties"]]
    return json.loads(r.stdout), basins, (out / "assumptions.md").read_text(encoding="utf-8")


def test_hollow_sits_at_the_low_end(sloped, tmp_path):
    root, site_dir, _ = sloped
    stats, basins, notes = run(root, site_dir, tmp_path / "terrain")
    assert stats["terrain"] and "terrain.csv" in stats["terrain"]
    assert "Terrain: terrain.csv" in notes
    assert basins, "no retention at all"
    east = [(g, p) for g, p in basins if g.centroid.x > X0 + 250]
    # all the new rain runs east, downhill, past the wall into the east park
    assert sum(p["catchment_m2"] for _, p in east) >= 0.9 * sum(p["catchment_m2"] for _, p in basins)
    g, p = max(east, key=lambda gp: gp[1]["needed_m3"])
    assert g.centroid.x > X0 + 450, g.centroid.x - X0      # the east park runs from 250 to 500 m: its low end
    assert p["volume_m3"] >= 0.95 * p["needed_m3"]


def test_trees_keep_off_open_land(tmp_path):
    """Trees in the shared schema: canopy over a kept wood, planted trees in the park and the courtyard, and none on a
    kept-free strip, water, a playground, a field the plan keeps or a green the plan gives to energy."""
    b = lambda x0, y0, x1, y1: box(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1)
    site_dir = tmp_path / "site"
    write(site_dir / "site.geojson", fc([(b(0, 0, 600, 300), {"name": "test"})]))
    write(site_dir / "plots.geojson", fc([(b(0, 0, 600, 300), {"landuse": "farmland"}),
                                          (b(480, 200, 580, 290), {"landuse": "forest"})]))
    write(site_dir / "water.geojson", fc([(b(520, 10, 590, 60), {"natural": "water"})]))
    plan = {"field": (b(300, 0, 450, 150), {"kind": "green", "action": "keep", "roles": ["ecology"]}),
            "solar": (b(0, 200, 120, 300), {"kind": "green", "action": "keep", "roles": ["Energy"]})}
    write(tmp_path / "plan.geojson", fc(list(plan.values()) + [(b(0, 0, 120, 120), {"kind": "green", "action": "change",
                                                                                  "roles": ["recreation"]})]))
    write(tmp_path / "strips.geojson", fc([(LineString([(X0 + 200, Y0), (X0 + 200, Y0 + 300)]), {"width_m": 20})]))
    home = {"kind": "building", "floors": 4, "use": "residential"}
    write(tmp_path / "massing.geojson", fc([(b(140, 140, 190, 190).difference(b(150, 150, 180, 180)), home),
                                            (b(150, 150, 180, 180), {"kind": "open-space", "use": "garden", "type": "courtyard"})]))
    write(tmp_path / "config.json", {"residents": 100, "green_m2_per_resident": 10, "play_m2_per_resident": 1.5,
                                     "play_min_m2": 100, "sources": {"residents": "test"}})
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(SCRIPT), "--site", str(site_dir / "site.geojson"), "--layers", str(site_dir),
                        "--massing", str(tmp_path / "massing.geojson"), "--config", str(tmp_path / "config.json"),
                        "--out", str(out), "--structure", str(tmp_path / "plan.geojson"),
                        "--keep-free", str(tmp_path / "strips.geojson")],
                       capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode == 0, r.stderr[-2000:]
    stats = json.loads(r.stdout)
    feats = [(transform(to_m, shape(f["geometry"])), f["properties"])
             for f in json.loads((out / "open-space.geojson").read_text(encoding="utf-8"))["features"]]
    trees = [(g, p) for g, p in feats if p["kind"] == "tree"]
    assert stats["trees"] == {k: sum(1 for _, p in trees if p["group"] == k) for k in stats["trees"]}
    assert all(g.geom_type == "Point" and p["crown_m"] > 0 and p["height_m"] > 0 for g, p in trees)
    assert {p["group"] for _, p in trees} >= {"wood", "park", "courtyard"}
    assert all(p["existing"] == (p["group"] == "wood") for _, p in trees)    # planted trees are never kept wood
    assert all(b(480, 200, 580, 290).contains(g) for g, p in trees if p["group"] == "wood")
    no = [b(190, 0, 210, 300), b(520, 10, 590, 60), plan["field"][0], plan["solar"][0]] + \
         [g for g, p in feats if p["kind"] == "retention" or p.get("use") == "playground"]
    for g, p in trees:
        assert not any(z.intersects(g.buffer(p["crown_m"] / 2 - 0.5)) for z in no), (p, g.x - X0, g.y - Y0)


def test_plan_fills_its_frame(sloped, tmp_path):
    """A frame in the panels' plan: the plan is that size at that scale, its legend inside, and stdout stays JSON."""
    root, _, flat_dir = sloped
    write(tmp_path / "panel-layout/layout-plan.json", {"panels": [{"items": [
        {"file": "open-space/open-space_1-5000.svg", "scale": "1:5000", "frame": {"w": 150, "h": 100}}]}]})
    run(root, flat_dir, tmp_path / "open-space")
    svg = (tmp_path / "open-space/open-space_1-5000.svg").read_text(encoding="utf-8")
    assert 'width="150.0mm" height="100.0mm"' in svg and 'viewBox="0 0 750.0 500.0"' in svg


def test_without_terrain_says_so(sloped, tmp_path):
    root, _, flat_dir = sloped
    stats, basins, notes = run(root, flat_dir, tmp_path / "flat")
    assert stats["terrain"] is None
    assert "No terrain model in the site folder" in notes
    west = [p for g, p in basins if g.centroid.x < X0 + 200]
    assert west, "without terrain the house's rain goes to its nearest park, the west one"
