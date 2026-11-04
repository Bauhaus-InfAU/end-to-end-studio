"""The climate skill's draw.py: without a frame each map fits the site at a usual scale; with one in the panels' plan,
every map is that frame at that scale, its title, short legend, scale bar and north inside, no text under 12 px."""
import json, os, re, subprocess, sys

import pyproj
from shapely.geometry import box, mapping
from shapely.ops import transform

from conftest import REPO

DRAW = REPO / "plugins/site/skills/climate/scripts/draw.py"
STYLE = REPO / "plugins/drawings/skills/drawing-graphics/base.json"
to_ll = pyproj.Transformer.from_crs(32632, 4326, always_xy=True).transform
X0, Y0 = 500000.0, 5540000.0


def write(path, feats):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": p, "geometry": mapping(transform(to_ll, g))} for g, p in feats]}), encoding="utf-8")


def draw(tmp_path, plan=None):
    b = lambda x0, y0, x1, y1: box(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1)
    site, out = tmp_path / "site", tmp_path / "proposal/climate"
    write(site / "site.geojson", [(b(0, 0, 600, 400), {"name": "test"})])
    write(site / "buildings.geojson", [(b(100, 100, 140, 130), {"height": 12})])
    write(out / "rules.geojson", [(b(0, 0, 200, 400), {"kind": "dont", "rule": "No homes by the road. Too loud."}),
                                  (b(200, 0, 300, 400), {"kind": "careful", "rule": "Homes behind a shielding edge."})])
    (out / "rules.json").write_text(json.dumps({"sources": ["test"]}), encoding="utf-8")
    if plan:
        (tmp_path / "proposal/panel-layout").mkdir(parents=True)
        (tmp_path / "proposal/panel-layout/layout-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    r = subprocess.run([sys.executable, str(DRAW), "--site", str(site), "--out", str(out), "--style", str(STYLE)],
                       capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode == 0, r.stderr[-2000:]
    return (out / "rules.svg").read_text(encoding="utf-8")


def test_rules_map_fits_the_site(tmp_path):
    svg = draw(tmp_path)
    w, h = (float(v) for v in re.search(r'width="([\d.]+)mm" height="([\d.]+)mm"', svg).groups())
    assert w > 150 and h > 150   # the map, its legend column and its sources


def test_rules_map_fills_its_frame(tmp_path):
    svg = draw(tmp_path, {"panels": [{"items": [{"file": "climate/rules.svg", "scale": "1:5000", "frame": {"w": 160, "h": 120}}]}]})
    assert 'width="160.0mm" height="120.0mm" viewBox="0 0 160.0 120.0"' in svg
    assert min(float(s) for s in re.findall(r'font-size="([\d.]+)"', svg)) >= 3.2 - 1e-6
    assert "1:5,000" in svg and "Sources" in svg
