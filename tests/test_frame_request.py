"""Issue #39: a drawing says the frame it needs at its scale, and panel-layout's second run gives it that frame."""
import importlib.util, json, re
from conftest import REPO
from test_building_types import draw, massed  # noqa: F401  (massed is a fixture)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, REPO / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


panels = load("panels", "plugins/delivery/skills/panel-layout/scripts/panels.py")
frames = load("frames", "plugins/studio/skills/competition-proposal/scripts/frames.py")
FORMAT = {"width_mm": 594, "height_mm": 841, "margin_mm": 15, "content_top_mm": 52}


def plan(w, h, scale="1:1000", file="building-types/building-types_1-1000.svg"):
    item = {"id": "building-types", "type": "drawing", "file": file, "x": 300, "y": 60, "scale": scale,
            "frame": {"w": w, "h": h}, "crop": {"focus": [0.5, 0.5]}}
    return {"format": FORMAT, "panels": [{"items": [item]}]}


def asking(folder, w, h, scale="1:1000", name="plans/plan_1-1000"):
    (folder / name).parent.mkdir(parents=True, exist_ok=True)
    (folder / (name + ".frame.json")).write_text(json.dumps({"scale": scale, "needs_mm": {"w": w, "h": h}}), encoding="utf-8")


def layout_file(folder, layout):
    (folder / "panel-layout").mkdir(parents=True, exist_ok=True)
    p = folder / "panel-layout/layout.json"
    p.write_text(json.dumps(layout), encoding="utf-8")
    return p


def test_building_types_asks_for_what_it_draws_and_keeps_the_scale(massed, tmp_path):
    draw(massed, tmp_path / "small", layout=plan(100, 40))                 # a first guess far too small
    d = tmp_path / "small/building-types"
    req = json.loads((d / "building-types_1-1000.frame.json").read_text(encoding="utf-8"))
    assert req["scale"] == "1:1000" and req["planned_frame_mm"] == {"w": 100, "h": 40} and req["by"] == "building-types"
    root = (d / "building-types_1-1000.svg").read_text(encoding="utf-8")[:200]
    w, h = (float(v) for v in re.search(r'width="([\d.]+)mm" height="([\d.]+)mm"', root).groups())
    assert w - 1 <= req["needs_mm"]["w"] and req["needs_mm"]["w"] <= w + 1 and h - 1 <= req["needs_mm"]["h"] <= h + 1
    assert w <= 564 and h <= 774                                            # within the panel's content area, not the guess
    assert int(req["why"].split()[0]) > 1                                   # the small guess no longer cuts it to one type
    assert "1:1,000" in (d / "summary.md").read_text(encoding="utf-8")


def test_the_first_guess_no_longer_decides_what_is_drawn(massed, tmp_path):
    draw(massed, tmp_path / "a", layout=plan(100, 40))
    draw(massed, tmp_path / "b", layout=plan(564, 700))
    read = lambda f: json.loads((tmp_path / f / "building-types/building-types_1-1000.frame.json").read_text(encoding="utf-8"))
    assert read("a")["needs_mm"] == read("b")["needs_mm"]


def test_the_second_run_gives_the_frame_at_the_same_scale(tmp_path):
    p = layout_file(tmp_path, plan(279, 140, file="plans/plan_1-1000.svg"))
    asking(tmp_path, 454, 386)
    said = panels.give_frames(p)
    it = json.loads(p.read_text(encoding="utf-8"))["panels"][0]["items"][0]
    assert it["frame"] == {"w": 454, "h": 386} and it["scale"] == "1:1000" and "crop" not in it
    assert it["x"] == 15                                                    # it ran past the right margin
    assert "`building-types`" in said[0]
    assert panels.give_frames(p) == ["No drawing asks for another frame."]  # asked and given: nothing left to do


def test_at_most_the_full_panel_width(tmp_path):
    p = layout_file(tmp_path, plan(279, 140, file="plans/plan_1-1000.svg"))
    asking(tmp_path, 700, 300)
    said = panels.give_frames(p)
    assert json.loads(p.read_text(encoding="utf-8"))["panels"][0]["items"][0]["frame"] == {"w": 564, "h": 300}
    assert "the panel has 564" in said[0]


def test_a_request_at_another_scale_changes_nothing(tmp_path):
    p = layout_file(tmp_path, plan(279, 140, file="plans/plan_1-1000.svg"))
    asking(tmp_path, 454, 386, scale="1:4000")
    before = p.read_text(encoding="utf-8")
    assert "no frame given" in panels.give_frames(p)[0]
    assert p.read_text(encoding="utf-8") == before


def test_a_broken_request_is_ignored(tmp_path):
    p = layout_file(tmp_path, plan(279, 140, file="plans/plan_1-1000.svg"))
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans/plan_1-1000.frame.json").write_text("{not json", encoding="utf-8")
    assert panels.give_frames(p) == ["No drawing asks for another frame."]


def test_frames_sends_no_rerun_to_a_drawing_that_asks(tmp_path):
    """The rerun that followed a miss is what changed the scale, so a drawing that asks gets its frame instead."""
    v = tmp_path / "v"
    (v / "plans").mkdir(parents=True)
    (v / "plans/plan_1-1000.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="454mm" height="386mm"/>', encoding="utf-8")
    item = {"id": "p", "type": "drawing", "file": "plans/plan_1-1000.svg", "scale": "1:1000", "frame": {"w": 279, "h": 140}}
    (v / "panel-layout").mkdir()
    (v / "panel-layout/layout-plan.json").write_text(json.dumps({"panels": [{"items": [item]}]}), encoding="utf-8")
    _, res = frames.check(v)
    assert res[0]["problems"]                                               # without a request, a miss
    asking(v, 454, 386)
    _, res = frames.check(v)
    assert not res[0]["problems"] and res[0]["asks"] == {"w": 454, "h": 386}


def test_the_format_is_written_for_every_drawing_skill():
    topic = (REPO / "plugins/drawings/TOPIC.md").read_text(encoding="utf-8")
    assert "<drawing>.frame.json" in topic and "needs_mm" in topic and "scale never changes" in topic
