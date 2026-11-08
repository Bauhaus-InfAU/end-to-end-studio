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
