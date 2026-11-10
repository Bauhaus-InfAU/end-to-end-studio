"""noise_at_buildings.py: the noise at each new building with the design standing."""
import json
import math
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "plugins/design/skills/massing/scripts/noise_at_buildings.py"
LON0, LAT0 = 12.0, 49.0


def ll(x, y):
    return [LON0 + x / (111320 * math.cos(math.radians(LAT0))), LAT0 + y / 111320]


def box(x0, y0, x1, y1):
    return {"type": "Polygon", "coordinates": [[ll(x0, y0), ll(x1, y0), ll(x1, y1), ll(x0, y1), ll(x0, y0)]]}


def fc(*feats):
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": g, "properties": p} for g, p in feats]}


def levels(tmp_path, *buildings):
    """Runs the script on a road along y = 0 and the buildings given as (box, floors); returns the day levels."""
    site, proposal = tmp_path / "site", tmp_path / "run"
    for d in (site, proposal / "climate", proposal / "massing"):
        d.mkdir(parents=True, exist_ok=True)
    (site / "site.geojson").write_text(json.dumps(fc((box(-400, -100, 400, 300), {}))), encoding="utf-8")
    road = {"type": "MultiLineString", "coordinates": [[ll(-800, 0), ll(800, 0)]]}
    (proposal / "climate/noise-sources.geojson").write_text(json.dumps(fc((road, {"name": "Road", "kind": "road"}))), encoding="utf-8")
    (proposal / "climate/noise.json").write_text(json.dumps({"receiver_height_m": 4, "sources_used": [{"name": "Road", "lme_day": 72, "lme_night": 64}]}), encoding="utf-8")
    feats = [(box(*b), {"kind": "building", "floors": fl, "height_m": fl * 3.0, "existing": False}) for b, fl in buildings]
    (proposal / "massing/massing.geojson").write_text(json.dumps(fc(*feats)), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), "--proposal", str(proposal), "--site", str(site)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads((proposal / "massing/noise-design.geojson").read_text(encoding="utf-8"))["features"]
    assert len(out) == len(buildings)
    return [f["properties"]["noise_day_db"] for f in out]


FRONT, BACK = (-150, 20, 150, 34), (-60, 60, 60, 74)


def test_a_front_row_shields_what_stands_behind_it(tmp_path):
    alone = levels(tmp_path, (BACK, 3))[0]
    front, behind = levels(tmp_path, (FRONT, 6), (BACK, 3))
    assert front > behind + 5
    assert behind < alone - 5


def test_the_top_floor_hears_over_a_low_front_row(tmp_path):
    low = levels(tmp_path, (FRONT, 2), (BACK, 2))[1]
    tall = levels(tmp_path, (FRONT, 2), (BACK, 10))[1]
    assert tall > low + 3
