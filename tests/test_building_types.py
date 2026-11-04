"""building-types draws one block per type as an ensemble: its yard, trees, roofs, windows, street and three to five notes."""
import csv, json, os, re, shutil, subprocess, sys
from collections import Counter
import pytest
from conftest import REPO
from synthetic import make_proposal

BT = REPO / "plugins/drawings/skills/building-types/scripts/building_types.py"
MASSING = REPO / "plugins/design/skills/massing/scripts/massing.py"
FORBIDDEN = re.compile(r"Regensburg|Europan|Pilsenallee|Chamer|Brandlberg|Haslbach|Wutzlhofen|run-3|25832"
                       r"|\b49\.0\d{3}|\b12\.\d{4}|\b[A-Z]:[\\/](?:Users|Work)", re.I)


def run(script, *args):
    r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode == 0, r.stderr[-2000:]
    return r


@pytest.fixture(scope="module")
def massed(tmp_path_factory):
    """The synthetic proposal with its massing (blocks with block, part, roof and ground_floor)."""
    root = tmp_path_factory.mktemp("bt") / "with space"
    out = make_proposal(root)
    run(MASSING, "--proposal", out, "--site", root / "site", "--config", out / "massing/config.json")
    return out


def draw(src, dest, notes=None, layout=None):
    shutil.copytree(src, dest)
    if notes is not None:
        (dest / "building-types").mkdir(exist_ok=True)
        (dest / "building-types/notes.json").write_text(json.dumps(notes), encoding="utf-8")
    if layout is not None:
        (dest / "panel-layout").mkdir(exist_ok=True)
        (dest / "panel-layout/layout.json").write_text(json.dumps(layout), encoding="utf-8")
    run(BT, "--proposal", dest)
    rows = list(csv.DictReader((dest / "building-types/types.csv").open(encoding="utf-8")))
    svg = next((dest / "building-types").glob("*.svg")).read_text(encoding="utf-8")
    return rows, svg


def test_names_no_site():
    assert not FORBIDDEN.findall(BT.read_text(encoding="utf-8"))


def test_one_whole_block_per_type(massed, tmp_path):
    rows, svg = draw(massed, tmp_path / "p")
    F = json.loads((massed / "massing/massing.geojson").read_text(encoding="utf-8"))["features"]
    new = [f["properties"] for f in F if f["properties"].get("kind") == "building" and not f["properties"].get("existing")]
    assert {r["type"] for r in rows} == {p["type"] for p in new}
    for r in rows:
        per_block = Counter(p["block"] for p in new if p["type"] == r["type"])
        assert int(r["block"]) in per_block and per_block[int(r["block"])] == max(per_block.values()), r   # the most complete block
        assert int(r["block_buildings"]) == sum(p["block"] == int(r["block"]) for p in new)
        assert int(r["blocks"]) == len(per_block)
    assert svg.count('class="ensemble"') == sum(r["drawn"] == "True" for r in rows)


def test_ensembles_carry_yard_trees_roofs_windows_and_notes(massed, tmp_path):
    rows, svg = draw(massed, tmp_path / "p")
    style = json.loads((massed / "drawing-graphics/style.json").read_text(encoding="utf-8"))
    assert '<circle' in svg                                  # trees
    assert 'fill="%s"' % style["meadow"] in svg              # the massing's green roofs
    assert 'fill="%s" fill-rule="evenodd"' % style["lawn"] in svg   # a courtyard garden
    assert 'fill="%s"' % style["street"] in svg              # the street in front
    for r in rows:
        notes = r["notes"].split(" | ")
        assert 2 <= len(notes) <= 5, r                      # three to five where the layers offer them
        assert all(re.search(r"\((massing|open-space|programme)[^)]*\)$", n) for n in notes), notes
    full = max(rows, key=lambda r: int(r["block_buildings"]))
    assert len(full["notes"].split(" | ")) >= 3, full
    assert "courtyard garden" in full["notes"] and "green roofs" in full["notes"]
    lines = (tmp_path / "p/building-types/summary.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3 and "illustrative: windows" in lines[1]


def test_notes_from_the_narrative_come_first_with_their_source(massed, tmp_path):
    rows, _ = draw(massed, tmp_path / "p")
    typ = max(rows, key=lambda r: int(r["block_buildings"]))["type"]
    given = [{"text": "homes along a shared yard", "source": "narrative, principle 1", "at": "yard"},
             {"text": "the main street as its front", "source": "narrative, principle 2", "at": "street"}]
    rows, svg = draw(massed, tmp_path / "q", notes={typ: given})
    notes = next(r for r in rows if r["type"] == typ)["notes"].split(" | ")
    assert notes[:2] == ["homes along a shared yard (narrative, principle 1)", "the main street as its front (narrative, principle 2)"]
    assert 3 <= len(notes) <= 5
    assert "homes along a shared yard" in svg and "(narrative, principle 1)" in svg


def test_frame_from_a_panel_of_the_layout(massed, tmp_path):
    item = {"id": "building-types", "type": "drawing", "file": "building-types/building-types_1-1000.svg",
            "scale": "1:1000", "frame": {"w": 300, "h": 120}}
    draw(massed, tmp_path / "p", layout={"format": {}, "panels": [{"items": [item]}]})
    summary = (tmp_path / "p/building-types/summary.md").read_text(encoding="utf-8")
    assert "1:1,000 (panel-layout/layout.json)" in summary
    assert (tmp_path / "p/building-types/building-types_1-1000.svg").exists()
    svg = (tmp_path / "p/building-types/building-types_1-1000.svg").read_text(encoding="utf-8")
    assert (mm(svg, "width") <= 300.5 and mm(svg, "height") <= 120.5) or "not even one type fits" in summary


def mm(svg, attr):
    return float(re.search(r'<svg[^>]*\b%s="([\d.]+)mm"' % attr, svg).group(1))


def test_draws_only_what_the_frame_holds_the_most_built_first(massed, tmp_path):
    big = {"id": "building-types", "file": "building-types/building-types_1-2000.svg", "scale": "1:2000", "frame": {"w": 5000, "h": 5000}}
    rows, svg = draw(massed, tmp_path / "p", layout={"panels": [{"items": [big]}]})
    assert len(rows) == 2 and all(r["drawn"] == "True" for r in rows)       # side by side in one row
    W, H = mm(svg, "width"), mm(svg, "height")
    rows, svg = draw(massed, tmp_path / "q", layout={"panels": [{"items": [dict(big, frame={"w": W - 5, "h": H + 15})]}]})
    drawn = [r for r in rows if r["drawn"] == "True"]
    assert len(rows) == 2 and len(drawn) == 1                                # types.csv keeps both
    assert drawn[0]["type"] == max(rows, key=lambda r: int(r["buildings"]))["type"]
    assert mm(svg, "width") <= W - 4.5 and mm(svg, "height") <= H + 15.5
    summary = (tmp_path / "q/building-types/summary.md").read_text(encoding="utf-8")
    assert "Left out, to fit the frame" in summary and next(r["type"] for r in rows if r["drawn"] != "True") in summary
