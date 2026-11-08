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


def test_maps_take_the_standards_existing_grey_and_green(tmp_path):
    from importlib.util import module_from_spec, spec_from_file_location
    sys.path.insert(0, str(DRAW.parent))
    spec = spec_from_file_location("climate_draw", DRAW)
    d = module_from_spec(spec)
    spec.loader.exec_module(d)
    base = json.loads(STYLE.read_text(encoding="utf-8"))
    assert f'fill="{base["existing"]}"' in draw(tmp_path)   # the buildings in the standard's existing grey
    b = lambda x0, y0, x1, y1: box(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1)
    out = tmp_path / "proposal/climate"
    write(out / "heat.geojson", [(b(0, 0, 300, 400), {"kind": "index", "label": "cool"}),
                                 (b(300, 0, 600, 400), {"kind": "index", "label": "warm"})])
    r = subprocess.run([sys.executable, str(DRAW), "--site", str(tmp_path / "site"), "--out", str(out), "--style", str(STYLE)],
                       capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode == 0, r.stderr[-2000:]
    heat = (out / "heat.svg").read_text(encoding="utf-8")
    assert d.mix(base["paper"], base["park"], 0.55) in heat   # the cool end is the standard's park green
    assert f'fill="{base["existing"]}"' in heat


def test_fresh_air_is_one_soft_named_corridor_with_few_arrows(tmp_path):
    """The corridor in a cool colour, its edge soft but never past the traced outline, its name on the map, and the
    traced arrows grouped into a few large ones instead of drawn one by one."""
    import math
    from importlib.util import module_from_spec, spec_from_file_location
    from shapely.geometry import LineString
    sys.path.insert(0, str(DRAW.parent))
    spec = spec_from_file_location("climate_draw", DRAW)
    d = module_from_spec(spec)
    spec.loader.exec_module(d)
    b = lambda x0, y0, x1, y1: box(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1)
    ln = lambda x, y, dx, dy: LineString([(X0 + x, Y0 + y), (X0 + x + dx, Y0 + y + dy)])
    band = b(260, -200, 340, 600)
    flows = [(ln(300, 550 - 70 * i, 0, -50), {"kind": "flow", "label": "strong"}) for i in range(10)]
    flows += [(ln(-150 + 60 * (i % 15), -100 + 120 * (i // 15), -20, -40), {"kind": "flow", "label": "light"}) for i in range(30)]
    out = tmp_path / "proposal/climate"
    write(out / "fresh-air.geojson", [(band, {"kind": "corridor", "label": "cold air corridor (read from a test map)"})] + flows)
    (out / "fresh-air.json").write_text(json.dumps({"sources": ["test"]}), encoding="utf-8")
    draw(tmp_path)
    svg = (out / "fresh-air.svg").read_text(encoding="utf-8")
    base = json.loads(STYLE.read_text(encoding="utf-8"))
    assert base["accent"].lower() not in svg.lower()                  # not the pink accent
    assert "COLD AIR CORRIDOR" in svg                                    # its name, on the map
    body = svg.split('clip-path="url(#frame)">', 1)[1].split("</g>", 1)[0]
    assert 2 <= body.count("marker-end") < len(flows) / 2                # a few large arrows, not all 40
    rows = json.loads((out / "frames.json").read_text(encoding="utf-8"))["fresh-air.svg"]["compact"]["rows"]
    sheet = (out / "climate_sheet.svg").read_text(encoding="utf-8")
    for fill, op, label, look in rows:                                   # the short legend dressed like the map, not black
        if fill == "arrow":
            assert look["stroke"].lower() != base["ink"].lower() and look["wave"] and look["stroke"] in sheet
            assert "q" in d.mark(0, 0, "arrow", 1, dict(d.FALLBACK), look)
        else:
            assert fill.lower() not in (base["ink"].lower(), base["accent"].lower()) and look["soft"]
            assert "stroke=" not in d.mark(0, 0, fill, op, dict(d.FALLBACK), look)
    arrows = re.findall(r'<path d="([^"]+)"[^>]*marker-end', body)
    assert arrows and all(a.count("L") >= 10 for a in arrows)            # wavy paths, not straight lines
    for layer in d.soft(band):                                           # the soft edge stays inside the outline
        assert band.buffer(1e-6).contains(layer)
    big = d.group([g for g, p in flows if p["label"] == "light"], 300)
    assert big and all(abs(math.degrees(math.atan2(*reversed(v)))) > 90 for _, v in big)   # they keep the way the air moves
