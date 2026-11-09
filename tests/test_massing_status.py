"""Every existing building says what the design does with it: changed where a new building stands within
integrate_m of it or a centre lies around it, else kept, each with its reason. Synthetic data."""
import json, os, subprocess, sys
import pyproj
from shapely.geometry import shape
from shapely.ops import transform, unary_union
from conftest import REPO
from synthetic import make_proposal, utm_epsg

MASSING = REPO / "plugins/design/skills/massing/scripts/massing.py"


def test_every_existing_building_has_a_status(tmp_path):
    prop = make_proposal(tmp_path)
    r = subprocess.run([sys.executable, str(MASSING), "--proposal", str(prop), "--site", str(tmp_path / "site"),
                        "--config", str(prop / "massing/config.json")], capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode == 0, r.stderr[-2000:]

    feats = json.loads((prop / "massing/massing.geojson").read_text(encoding="utf-8"))["features"]
    blds = [f for f in feats if f["properties"]["kind"] == "building"]
    old = [f for f in blds if f["properties"]["existing"]]
    assert old, "the site has existing buildings"
    c = shape(old[0]["geometry"]).centroid
    to_m = pyproj.Transformer.from_crs(4326, utm_epsg(c.x, c.y), always_xy=True).transform
    new = unary_union([transform(to_m, shape(f["geometry"])) for f in blds if not f["properties"]["existing"]])
    sp = json.loads((prop / "structure-plan/structure-plan.geojson").read_text(encoding="utf-8"))["features"]
    centres = unary_union([transform(to_m, shape(f["geometry"])) for f in sp if f["properties"]["kind"] == "centre"])

    for f in old:
        p = f["properties"]
        assert p["status"] in ("kept", "changed") and p["status_reason"]
        g = transform(to_m, shape(f["geometry"]))
        taken_in = new.distance(g) <= 6.0 or g.intersects(centres)
        assert (p["status"] == "changed") == taken_in, p

    stats = json.loads((prop / "massing/stats.json").read_text(encoding="utf-8"))
    assert sum(stats["existing"].values()) == len(old)
