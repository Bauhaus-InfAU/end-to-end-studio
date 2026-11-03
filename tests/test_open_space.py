"""The open-space skill's script on a synthetic sloped site: with the site folder's terrain the hollow sits at the
park's low end and the rain runs downhill to it; without terrain it keeps its old placement and says so."""
import csv, json, os, subprocess, sys

import numpy as np
import pyproj
import pytest
from shapely.geometry import box, mapping, shape
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


def test_without_terrain_says_so(sloped, tmp_path):
    root, _, flat_dir = sloped
    stats, basins, notes = run(root, flat_dir, tmp_path / "flat")
    assert stats["terrain"] is None
    assert "No terrain model in the site folder" in notes
    west = [p for g, p in basins if g.centroid.x < X0 + 200]
    assert west, "without terrain the house's rain goes to its nearest park, the west one"
