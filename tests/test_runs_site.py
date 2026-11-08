"""The build that turns run folders into the runs site."""
import json
import shutil

import pytest

from conftest import make_png
from runs_site import build

JPG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


def test_build_writes_contract(fixture_project, tmp_path):
    out = tmp_path / "site"
    b = build(fixture_project, fixture_project / "proposals", out, None, None)
    assert b["references"] is False
    idx = json.loads((out / "data/index.json").read_text(encoding="utf-8"))
    assert [r["key"] for r in idx["runs"]] == ["2026-01-02_run-1"]
    assert idx["project"]["name"] == "project" and "plans" in idx["skills_all"] and idx["ledger"] == []
    run = json.loads((out / "data/runs/2026-01-02_run-1.json").read_text(encoding="utf-8"))
    assert (out / run["panels"][0]["img"]).exists() and (out / "data/geo/shared.json").exists()
    assert (out / ".nojekyll").exists() and (out / "index.html").exists() and (out / "build.json").exists()
    shared = json.loads((out / "data/geo/shared.json").read_text(encoding="utf-8"))
    assert "noise" in shared["climate"] or "climate" in shared


def test_item_image_falls_back_to_panel_crop(fixture_project, tmp_path):
    out = tmp_path / "site"; build(fixture_project, fixture_project / "proposals", out, None, None)
    run = json.loads((out / "data/runs/2026-01-02_run-1.json").read_text(encoding="utf-8"))
    it = run["panels"][0]["items"][0]          # its SVG has no PNG and the file is missing
    assert (out / it["img"]).exists()


def test_item_uses_png_beside_svg(fixture_project, tmp_path):
    make_png(fixture_project / "proposals/2026-01-02_run-1/plans/site-plan_1-3000.png", (300, 100))
    out = tmp_path / "site"; build(fixture_project, fixture_project / "proposals", out, None, None)
    from PIL import Image
    with Image.open(out / "img/2026-01-02_run-1/site-plan.jpg") as im:
        assert im.size == (300, 100)


def test_build_never_copies_compare_or_references(fixture_project, tmp_path):
    (fixture_project / "proposals/2026-01-02_run-1/.compare").mkdir()
    (fixture_project / "proposals/2026-01-02_run-1/.compare/plans.jpg").write_bytes(JPG)
    out = tmp_path / "site"; build(fixture_project, fixture_project / "proposals", out, None, None)
    assert not [p for p in out.rglob("*") if ".compare" in p.parts or "references" in p.parts]


def test_layout_pointing_into_references_stops_the_build(fixture_project, tmp_path):
    lay = fixture_project / "proposals/2026-01-02_run-1/panel-layout/layout.json"
    d = json.loads(lay.read_text(encoding="utf-8"))
    d["panels"][0]["items"].append({"id": "x", "type": "drawing", "w": 10, "h": 10,
                                    "file": "../../references/winners/x/board-1.jpg"})
    lay.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit):
        build(fixture_project, fixture_project / "proposals", tmp_path / "site", None, None)


def test_overrides_and_ledger_are_read(fixture_project, tmp_path):
    p = fixture_project / "proposals"
    (p / "runs.json").write_text(json.dumps({"2026-01-02_run-1": {"verdict": "Prize"}}), encoding="utf-8")
    (p / "ledger.json").write_text(json.dumps([{"error": "e", "kind": "data", "runs": {}, "fix": None}]), encoding="utf-8")
    out = tmp_path / "site"; build(fixture_project, p, out, None, None)
    idx = json.loads((out / "data/index.json").read_text(encoding="utf-8"))
    assert idx["runs"][0]["verdict"] == "Prize" and idx["ledger"][0]["error"] == "e"


def test_build_refuses_a_foreign_folder(fixture_project, tmp_path):
    out = tmp_path / "site"; out.mkdir(); (out / "mine.txt").write_text("keep")
    with pytest.raises(SystemExit):
        build(fixture_project, fixture_project / "proposals", out, None, None)
    assert (out / "mine.txt").exists()


def test_build_replaces_its_own_earlier_site(fixture_project, tmp_path):
    out = tmp_path / "site"
    build(fixture_project, fixture_project / "proposals", out, None, None)
    (out / "stale.txt").write_text("x")
    build(fixture_project, fixture_project / "proposals", out, None, None)
    assert not (out / "stale.txt").exists()


def _all_text(out):
    return "".join(p.read_text(encoding="utf-8") for p in out.rglob("*.json"))


def test_3d_layers_are_left_out(fixture_project, tmp_path):
    ring = [[[12.0, 49.0, 5.0], [12.01, 49.0, 5.0], [12.01, 49.01, 6.0], [12.0, 49.0, 5.0]]]
    f = {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": ring}}
    (fixture_project / "site" / "mesh.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [f]}))
    out = tmp_path / "site"; build(fixture_project, fixture_project / "proposals", out, None, None)
    shared = json.loads((out / "data/geo/shared.json").read_text(encoding="utf-8"))
    assert "mesh" not in shared.get("site", {}) and "site" in shared["site"]


def test_names_are_scrubbed_everywhere(fixture_project, tmp_path):
    refs = tmp_path / "refs"; (refs / "winners/1_copper-moth").mkdir(parents=True)
    p = fixture_project / "proposals"
    (p / "ledger.json").write_text(json.dumps([{"error": "like copper-moth", "kind": "data", "runs": {}, "fix": None}]))
    geo = {"type": "Feature", "properties": {"n": "copper-moth"}, "geometry": {"type": "Point", "coordinates": [12.0, 49.0]}}
    (p / "2026-01-02_run-1/massing").mkdir(exist_ok=True)
    (p / "2026-01-02_run-1/massing/x.geojson").write_text(json.dumps(geo))
    out = tmp_path / "site"; build(fixture_project, p, out, refs, None)
    assert "copper-moth" not in _all_text(out) and "a reference" in _all_text(out)


def test_names_file_is_read(fixture_project, tmp_path):
    refs = tmp_path / "refs"; refs.mkdir(); (refs / "names.txt").write_text("Zebra Yard\n")
    p = fixture_project / "proposals"
    (p / "ledger.json").write_text(json.dumps([{"error": "zebra yard", "kind": "data", "runs": {}, "fix": None}]))
    out = tmp_path / "site"; build(fixture_project, p, out, refs, None)
    assert "zebra" not in _all_text(out).lower()


def test_failed_build_can_be_rebuilt(fixture_project, tmp_path):
    out = tmp_path / "site"
    lay = fixture_project / "proposals/2026-01-02_run-1/panel-layout/layout.json"
    good = lay.read_text(encoding="utf-8")
    d = json.loads(good); d["panels"][0]["items"][0].update(file="../x.png"); d["panels"][0]["items"][1]["file"] = "../x.png"
    lay.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit):
        build(fixture_project, fixture_project / "proposals", out, None, None)
    lay.write_text(good, encoding="utf-8")
    assert build(fixture_project, fixture_project / "proposals", out, None, None)["built"]


def test_references_must_be_a_folder(fixture_project, tmp_path):
    with pytest.raises(SystemExit):
        build(fixture_project, fixture_project / "proposals", tmp_path / "site", tmp_path / "nope", None)


def test_references_without_names_stop_the_build(fixture_project, tmp_path, capsys):
    (tmp_path / "refs").mkdir()
    with pytest.raises(SystemExit) as e:
        build(fixture_project, fixture_project / "proposals", tmp_path / "site", tmp_path / "refs", None)
    assert "no reference names" in str(e.value)
    w = tmp_path / "refs2" / "winners" / "1_first-prize_copper-moth"
    w.mkdir(parents=True)
    build(fixture_project, fixture_project / "proposals", tmp_path / "site2", tmp_path / "refs2", None)
    out = capsys.readouterr().out
    assert "Checking for" in out and "reference names." in out and "moth" not in out.lower()


def test_ledger_marker_q_reads_present_not_reported():
    from pathlib import Path
    import runs_site
    js = (Path(runs_site.__file__).parent / "runsite/web/dash.js").read_text(encoding="utf-8")
    assert "present, not reported" in js and "probably" not in js


def test_item_id_cannot_escape(fixture_project, tmp_path):
    lay = fixture_project / "proposals/2026-01-02_run-1/panel-layout/layout.json"
    d = json.loads(lay.read_text(encoding="utf-8"))
    d["panels"][0]["items"][1]["id"] = "../../../escaped"
    lay.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit):
        build(fixture_project, fixture_project / "proposals", tmp_path / "a" / "b" / "site", None, None)
    assert not list(tmp_path.rglob("escaped*"))


def test_unreadable_panel_is_skipped(fixture_project, tmp_path):
    (fixture_project / "proposals/2026-01-02_run-1/panel-layout/panel-1.png").write_bytes(b"not a png")
    out = tmp_path / "site"; build(fixture_project, fixture_project / "proposals", out, None, None)
    assert (out / "data/runs/2026-01-02_run-1.json").exists()


def test_runs_sorted_by_date_then_number(fixture_project, tmp_path):
    p = fixture_project / "proposals"
    for name in ("2026-01-03_run-10", "2026-01-03_run-7"):
        shutil.copytree(p / "2026-01-02_run-1", p / name)
    out = tmp_path / "site"; build(fixture_project, p, out, None, None)
    idx = json.loads((out / "data/index.json").read_text(encoding="utf-8"))
    assert [r["label"] for r in idx["runs"]] == ["run-1", "run-7", "run-10"]
