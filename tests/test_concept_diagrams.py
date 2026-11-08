"""concept-diagrams: the pictogram vocabulary (people, trees, icons, vignettes, layers, a metaphor) renders."""
import json, subprocess, sys
from conftest import REPO

DD = REPO / "plugins/drawings/skills/concept-diagrams/scripts/draw_diagrams.py"
sys.path.insert(0, str(DD.parent))
from draw_diagrams import find_browser

SITE = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {
    "type": "Polygon", "coordinates": [[[8.0, 48.0], [8.008, 48.0], [8.008, 48.005], [8.0, 48.005], [8.0, 48.0]]]}}]}
SPEC = {"mode": "sequence", "site": "site.geojson", "view": {"type": "plan"}, "frames": [
    {"file": "01_green-link", "title": "A green link", "caption": "A green link crosses the site.",
     "elements": [{"kind": "strip", "coords": [[-250, 0], [250, 0]], "width": 40},
                  {"kind": "tree", "along": [[-220, 40], [220, 40]], "spacing": 60},
                  {"kind": "person", "coords": [[-100, -20], [60, -20]], "pose": "walker"}]},
    {"file": "02_square", "title": "A square on it", "caption": "A square opens where people meet.", "view": {"type": "iso"},
     "elements": [{"kind": "area", "coords": [[-60, -60], [60, -60], [60, 60], [-60, 60]], "fill": "solid"},
                  {"kind": "icon", "at": [0, 0], "sign": "market"},
                  {"kind": "icon", "at": [150, -100], "sign": "Kita"},
                  {"kind": "vignette", "at": [0, 0], "scene": ["tree", "sitter", "play"], "label": "meet and play"}]},
    {"file": "03_layers", "title": "The layers", "caption": "The link and the square add up.",
     "elements": [{"kind": "layers", "sum": "together"}]},
    {"file": "04_metaphor", "title": "A road becomes a room", "caption": "A road to pass becomes a room to share.",
     "elements": [{"kind": "metaphor", "parts": [{"draw": ["bus", "person"], "label": "a road to pass"},
                                                 {"draw": ["tree", "people", "bench"], "label": "a room to share"}]}]}]}


def test_vocabulary_renders(tmp_path):
    (tmp_path / "site.geojson").write_text(json.dumps(SITE), encoding="utf-8")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(SPEC), encoding="utf-8")
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(DD), "render", str(spec), str(out)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert "no sign" not in r.stderr, r.stderr
    for name in [f["file"] for f in SPEC["frames"]] + ["00_sheet"]:
        assert (out / f"{name}.svg").exists(), name
        if find_browser():
            assert (out / f"{name}.png").exists(), name
    svg = {f["file"]: (out / f"{f['file']}.svg").read_text(encoding="utf-8") for f in SPEC["frames"]}
    groups = json.loads((out / "groups.json").read_text(encoding="utf-8"))["groups"]
    assert groups[0]["name"] == "the sequence" and len(groups[0]["files"]) == 4  # a sequence is one group
    assert "illustrative" in svg["01_green-link"] and "meet and play" in svg["02_square"] and ">Ki<" in svg["02_square"]
    assert ">+<" in svg["03_layers"] and ">=<" in svg["03_layers"] and "together" in svg["03_layers"]
    assert "a room to share" in svg["04_metaphor"] and "#d0312d" in svg["04_metaphor"]   # the idea in the accent


def test_pie_charts(tmp_path):
    """A pie frame draws one slice per part and names its tables in the footer."""
    (tmp_path / "site.geojson").write_text(json.dumps(SITE), encoding="utf-8")
    pie = {"file": "05_ground", "title": "The ground, counted", "caption": "Less ground is sealed than is kept open.",
           "elements": [{"kind": "pie", "charts": [
               {"title": "today", "source": "analysis/comparison.csv",
                "parts": [{"value": 14, "label": "sealed"}, {"value": 8, "label": "partly"}, {"value": 78, "label": "open", "accent": True}]},
               {"title": "design", "source": "analysis/comparison.csv",
                "parts": [{"value": 28, "label": "sealed"}, {"value": 12, "label": "partly"}, {"value": 60, "label": "open", "accent": True}]}]}]}
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({**SPEC, "frames": SPEC["frames"][:2] + [pie]}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(DD), "render", str(spec), str(tmp_path)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    svg = (tmp_path / "05_ground.svg").read_text(encoding="utf-8")
    assert svg.count(" 0 0 1 ") + svg.count(" 0 1 1 ") == 6  # six slices
    assert "open 78 %" in svg and "Shares from analysis/comparison.csv." in svg


def test_draws_to_its_planned_frame(tmp_path):
    """The pictograms take the print width of the frame panel-layout's first plan gives them, and long captions wrap."""
    (tmp_path / "site.geojson").write_text(json.dumps(SITE), encoding="utf-8")
    cd = tmp_path / "concept-diagrams"
    cd.mkdir()
    frames = [dict(SPEC["frames"][0], caption="A green link crosses the whole site from the station to the river and the fields.")]
    (cd / "spec.json").write_text(json.dumps({**SPEC, "site": "../site.geojson", "frames": frames}), encoding="utf-8")
    (tmp_path / "panel-layout").mkdir()
    (tmp_path / "panel-layout" / "layout-plan.json").write_text(json.dumps({"panels": [{"items": [
        {"id": "dia-1", "type": "drawing", "file": "concept-diagrams/01_green-link.svg", "w": 100}]}]}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(DD), "render", str(cd / "spec.json"), str(cd)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    svg = (cd / "01_green-link.svg").read_text(encoding="utf-8")
    import re
    assert abs(float(re.search(r'width="([\d.]+)mm"', svg).group(1)) - 100) < 0.3, svg[:300]
    assert svg.count('<tspan x="20" dy=') >= 2  # the caption's second line (and the footer's)
