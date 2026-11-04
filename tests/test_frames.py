"""frames.py: each drawing against its frame in the panels' first plan, by scale and print size."""
import importlib.util, json, subprocess, sys
from conftest import REPO

SCRIPT = REPO / "plugins/studio/skills/competition-proposal/scripts/frames.py"
spec = importlib.util.spec_from_file_location("frames", SCRIPT)
frames = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frames)


def svg(path, w_mm, h_mm):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm}mm" height="{h_mm}mm" '
                    f'viewBox="0 0 {w_mm} {h_mm}"/>', encoding="utf-8")


def drw(id_, file, w, h, scale=None):
    return {"id": id_, "type": "drawing", "file": file, "frame": {"w": w, "h": h}, **({"scale": scale} if scale else {})}


def version(tmp_path, name="layout-plan.json"):
    v = tmp_path / "2026-01-01_t"
    svg(v / "plans/plan_1-1000.svg", 200, 100)            # fits its frame
    svg(v / "iso/iso_1-10000.svg", 150, 150)              # planned at 1:5,000 under another name
    svg(v / "section/cut_1-3000.svg", 600, 140)           # far taller than its strip
    svg(v / "plans/small_1-1000.svg", 150, 150)           # a quarter of its frame
    svg(v / "diagrams/d.svg", 100, 50)                    # no scale: fitted, half its frame
    svg(v / "diagrams/e.svg", 100, 95)                    # no scale: fitted, fills it
    items = [drw("plan", "plans/plan_1-1000.svg", 200, 100, "1:1000"), drw("iso", "iso/iso_1-5000.svg", 200, 150, "1:5000"),
             drw("cut", "section/cut_1-3000.svg", 500, 40, "1:3000"), drw("small", "plans/small_1-1000.svg", 300, 300, "1:1000"),
             drw("view", "views/view-1.png", 100, 100), drw("d", "diagrams/d.svg", 100, 100), drw("e", "diagrams/e.svg", 100, 100),
             {"id": "t", "type": "text", "text": "a"}, {"id": "u", "type": "drawing", "file": "plans/plan_1-1000.svg", "w": 50}]
    (v / "panel-layout").mkdir()
    (v / "panel-layout" / name).write_text(json.dumps({"panels": [{"items": items}]}), encoding="utf-8")
    return v


def test_names_each_drawing_that_misses_its_frame(tmp_path):
    plan, res = frames.check(version(tmp_path))
    assert plan.name == "layout-plan.json"
    by = {r["id"]: r for r in res}
    assert set(by) == {"plan", "iso", "cut", "small", "view", "d", "e"}      # only drawings with a frame
    assert not by["plan"]["problems"] and not by["e"]["problems"]
    assert by["iso"]["drawn"] == "iso/iso_1-10000.svg" and by["iso"]["drawn_at"] == 10000
    assert "not at its frame's scale" in by["iso"]["problems"] and by["iso"]["at_frame_scale_mm"] == [300, 300]
    assert abs(by["cut"]["hidden"] - (1 - 500 * 40 / (600 * 140))) < 1e-6
    assert by["small"]["fills"] == 0.25 and by["view"]["problems"] == ["not drawn"]
    assert abs(by["d"]["fills"] - 0.5) < 1e-6 and by["d"]["problems"]


def test_falls_back_to_layout_json_and_prints_the_misses(tmp_path):
    v = version(tmp_path, "layout.json")
    out = subprocess.run([sys.executable, str(SCRIPT), str(v)], capture_output=True, text=True, encoding="utf-8").stdout
    first, *rest = out.strip().splitlines()
    assert "panel-layout/layout.json: 5 of 7 drawings miss their frame" in first
    assert any(l.startswith("- `iso` (iso): planned iso/iso_1-5000.svg at 1:5,000 in 200 x 150 mm; "
                            "drawn iso/iso_1-10000.svg at 1:10,000, 150 x 150 mm") for l in rest), rest
    assert rest[-1] == "Fit their frames: `plan`, `e`."
    assert "nothing to check" in subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)], capture_output=True,
                                                text=True, encoding="utf-8").stdout
