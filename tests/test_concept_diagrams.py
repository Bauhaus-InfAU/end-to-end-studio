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
    assert "illustrative" in svg["01_green-link"] and "meet and play" in svg["02_square"] and ">Ki<" in svg["02_square"]
    assert ">+<" in svg["03_layers"] and ">=<" in svg["03_layers"] and "together" in svg["03_layers"]
    assert "a room to share" in svg["04_metaphor"] and "#d0312d" in svg["04_metaphor"]   # the idea in the accent
