"""Every existing building says what the design does with it: changed where a new building stands within
integrate_m of it or a centre lies around it, else kept, each with its reason. Synthetic data."""
import json, os, subprocess, sys
import pyproj
from shapely.geometry import mapping, shape
from shapely.ops import transform, unary_union
from conftest import REPO
from synthetic import make_proposal, utm_epsg

MASSING = REPO / "plugins/design/skills/massing/scripts/massing.py"
ISO = REPO / "plugins/drawings/skills/isometric/isometric.py"


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


def test_a_demolished_building_is_marked_and_not_drawn_standing(tmp_path):
    """What the structure plan demolishes is a removed-building in the massing, and a dashed outline in the isometric."""
    prop = make_proposal(tmp_path)
    site = tmp_path / "site"
    path = prop / "structure-plan/structure-plan.geojson"
    plan = json.loads(path.read_text(encoding="utf-8"))
    field = shape(next(f["geometry"] for f in plan["features"] if f["properties"]["kind"] == "neighbourhood"))
    outline = shape(json.loads((site / "site.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
    near = [shape(f["geometry"]) for f in json.loads((site / "buildings.geojson").read_text(encoding="utf-8"))["features"]]
    near = [g for g in near if outline.contains(g.representative_point()) and g.disjoint(field)]
    barn = min(near, key=field.distance)
    plan["features"].append({"type": "Feature", "geometry": mapping(barn.buffer(1e-6)),
                             "properties": {"kind": "existing", "name": "Barn", "action": "demolish", "basis": "test", "source": "test", "reason": "in the way"}})
    path.write_text(json.dumps(plan), encoding="utf-8")
    env = {**os.environ, "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, str(MASSING), "--proposal", str(prop), "--site", str(site), "--config", str(prop / "massing/config.json")],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr[-2000:]

    feats = json.loads((prop / "massing/massing.geojson").read_text(encoding="utf-8"))["features"]
    gone = [f for f in feats if f["properties"]["kind"] == "removed-building"]
    assert len(gone) == 1 and gone[0]["properties"]["status_reason"] == "in the way"
    q = shape(gone[0]["geometry"]).representative_point()
    assert not any(f["properties"]["kind"] == "building" and shape(f["geometry"]).contains(q) for f in feats)
    assert json.loads((prop / "massing/stats.json").read_text(encoding="utf-8"))["existing"]["removed"] == 1

    r = subprocess.run([sys.executable, str(ISO), str(site), str(prop), "3000", "594"], capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr[-2000:]
    svg = next((prop / "isometric").glob("isometric_1-3000.svg")).read_text(encoding="utf-8")
    assert 'stroke-dasharray="2 1.5"' in svg
