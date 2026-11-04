"""The checks panels.py adds before export: planned drawings kept, required drawings not cropped away,
a scale mismatch named, figures that disagree named, and --check without a browser.
Run: python -m pytest <this file> -q"""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("panels", Path(__file__).with_name("panels.py"))
panels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panels)

STYLE = {"font": "sans-serif", "text": "#000", "background": "#fff", "accent": "#c00",
         "line_mm": 0.25, "heading_pt": 20, "body_pt": 11}
FMT = {"width_mm": 594, "height_mm": 841}


def drawing(folder, name, w_mm, h_mm):
    (folder / name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm}mm" height="{h_mm}mm" '
                               f'viewBox="0 0 {w_mm} {h_mm}"><rect width="{w_mm}" height="{h_mm}"/><g id="scale-bar"/></svg>',
                               encoding="utf-8")  # its own scale bar, so a missing one isn't counted here
    return name


def report(folder, L, items):
    """The report for one panel holding items (measured if they are drawings)."""
    for it in items:
        if it.get("type") == "drawing":
            panels.measure(it, folder, {}, STYLE, [], (564, 780))
    results = [{"n": 1, "placed": [(it, {"x": 15, "y": 15, "w": it.get("w") or 100, "h": it.get("h") or 50}) for it in items],
                "unplaced": [], "checks": [], "story": "", "paths": []}]
    ids = {it["id"] for it in items}
    return panels.write_report(folder, L, FMT, results, [], ids, [], {"missing": []}, None, 96)


def problems(text):
    return int(text.split("Problems: ")[1].split(".")[0])


def test_a_planned_drawing_that_is_gone_is_named(tmp_path):
    first = {"panels": [{"items": [{"id": "section", "type": "drawing", "file": "site-section/section_1-1000.svg",
                                    "scale": "1:1000", "frame": {"w": 560, "h": 120}},
                                   {"id": "plan", "type": "drawing", "file": "plans/plan_1-3000.svg", "scale": "1:3000"}]}]}
    (tmp_path / "plan.json").write_text(json.dumps({"drawings": panels.planned(first)}), encoding="utf-8")
    second = {"panels": [{"items": [{"id": "plan", "type": "drawing", "file": "plans/plan_1-3000.svg", "scale": "1:2000"}]}]}
    text = report(tmp_path, second, [])
    assert "**DROPPED: planned `section` (site-section/section_1-1000.svg) is no longer in layout.json**" in text
    assert "`plan`: scale planned as 1:3000, now 1:2000" in text          # a change is named, not counted
    assert problems(text) == 1 and "Planned drawings dropped: 1." in text


def test_a_required_drawing_cropped_over_25_percent_is_not_on_the_panels(tmp_path):
    f = drawing(tmp_path, "detail_1-1000.svg", 300, 200)
    crop = {"type": "drawing", "file": f, "scale": "1:1000", "frame": {"w": 300, "h": 140}}   # hides 30 %
    L = {"required": [{"what": "detail area 2", "id": "d2"}]}
    text = report(tmp_path, L, [{"id": "d2", **crop}])
    assert "**CROPPED 30 %: `d2` is placed, but its frame hides more than 25 %**" in text
    assert "on the panels, `d2`" not in text and "cropped over 25 %: 1." in text
    assert "Required items missing: 0 of 1" in text                     # cropped is its own count, not missing
    text = report(tmp_path, {}, [{"id": "other", **crop}])               # not required: under the 50 % warning
    assert "CROPPED" not in text and problems(text) == 0
    it = {"id": "d2", **crop}                                             # the limit can be set in format
    panels.measure(it, tmp_path, {}, STYLE, [], (564, 780))
    res = [{"n": 1, "placed": [(it, {"x": 15, "y": 15, "w": 300, "h": 140})], "unplaced": [], "checks": [], "story": "", "paths": []}]
    text = panels.write_report(tmp_path, L, {**FMT, "max_crop_required": 0.4}, res, [], {"d2"}, [], {"missing": []}, None, 96)
    assert "CROPPED" not in text


def test_a_drawing_at_another_scale_than_fixed_is_named(tmp_path):
    f = drawing(tmp_path, "detail_1-500.svg", 300, 200)
    text = report(tmp_path, {}, [{"id": "d2", "type": "drawing", "file": f, "scale": "1:1000"}])
    assert "drawn at 1:500, printed at 1:1,000, the scale layout.json fixes: ask its skill to draw it at 1:1,000" in text
    assert problems(text) == 1
    f = drawing(tmp_path, "site_1-1000.svg", 300, 200)
    assert "drawn at" not in report(tmp_path, {}, [{"id": "s", "type": "drawing", "file": f, "scale": "1:1000"}])


def test_figures_with_one_label_and_two_values_are_named(tmp_path):
    a = {"id": "f1", "type": "figures", "rows": [["Homes", "2,950", "massing"], ["Sealed", "38 %", "open-space"]]}
    b = {"id": "f2", "type": "figures", "rows": [["homes ", "3,100", "analysis"], ["Sealed", "38 %", "analysis"],
                                                 ["Residents", "5000", "x"]]}
    c = {"id": "f3", "type": "figures", "rows": [["Residents", "5,000", "y"]]}   # the same number, written two ways
    text = report(tmp_path, {}, [a, b, c])
    assert "- **homes: 2,950 (panel 1, massing); 3,100 (panel 1, analysis)**" in text
    assert "sealed:" not in text and "residents:" not in text and problems(text) == 1
    text = report(tmp_path, {"notes": ["Homes: massing says 2,950, analysis 3,100"]}, [a, b, c])
    assert "(named in notes)" in text and problems(text) == 0


def test_check_runs_without_a_browser(tmp_path, monkeypatch):
    monkeypatch.setattr(panels, "find_browser", lambda: pytest.fail("--check started a browser"))
    out = tmp_path / "panel-layout"
    out.mkdir()
    layout = {"format": {"width_mm": 594, "height_mm": 841, "panels": 1},
              "panels": [{"items": [{"id": "t", "type": "text", "text": "a"},
                                    {"id": "p", "type": "drawing", "file": "plans/p_1-1000.svg", "scale": "1:1000",
                                     "frame": {"w": 200, "h": 100}}]}]}
    (out / "layout.json").write_text(json.dumps(layout), encoding="utf-8")
    panels.render(out / "layout.json", 96, check=True)
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "Check only" in text and not (out / "panel-1.pdf").exists() and (out / "panel-1.html").exists()
    assert (out / "issues.md").exists()                                  # the lead's report comes with every check
    assert json.loads((out / "plan.json").read_text(encoding="utf-8"))["drawings"][0]["id"] == "p"


def test_missing_is_told_apart_from_available_but_not_placed(tmp_path):
    (tmp_path / "proposal" / "plans").mkdir(parents=True)
    folder, out = tmp_path / "proposal", tmp_path / "proposal" / "panel-layout"
    out.mkdir()
    drawing(folder / "plans", "detail-1_1-1000.svg", 200, 100)
    (folder / "plans" / "summary.md").write_text("detail-1_1-1000.svg at 1:1,000\nTwo of three\nUnsure\n", encoding="utf-8")
    L = {"required": [{"what": "detail area 1", "file": "plans/detail-1_1-1000.svg"},
                      {"what": "detail area 2", "file": "plans/detail-2_1-1000.svg"},
                      {"what": "long section", "file": "site-section/section_1-1000.svg"},
                      {"what": "isometry"}]}
    text = panels.write_report(out, L, FMT, [], [], set(), [], {"missing": [], "skills": {"plans": {"summary": "detail-1_1-1000.svg at 1:1,000"}}}, None, 96)
    assert "detail area 1 (): **AVAILABLE, NOT PLACED: plans/detail-1_1-1000.svg exists but is not on the panels**" in text
    assert "detail area 2 (): **MISSING: no input**" in text
    assert "Required items missing: 4 of 4 (3 without input, 0 did not fit, 1 available but not placed)" in text
    issues = (out / "issues.md").read_text(encoding="utf-8")
    here, up = issues.split("## Fix in panel-layout")[1], issues.split("## Fix in panel-layout")[0]
    assert "required drawing available but not on the panels" in here and "detail area 1" in here
    assert "detail area 1" not in up                                   # ours to fix, not the lead's


def test_the_responsible_skill_is_named_or_unknown(tmp_path):
    assert panels.skill_of("plans/site-plan_1-3000.svg") == "plans"     # the folder it is written to
    assert panels.skill_of("plans/x.svg", "plans") == "plans"
    assert panels.skill_of(None, "isometric") == "isometric"            # `by`, from the studio's list
    assert panels.skill_of("x.svg") == "unknown" and panels.skill_of(None) == "unknown"
    assert panels.skill_of("massing/x.svg", "plans").startswith("unknown")   # they disagree: no guess
    assert panels.skill_of("panel-layout/x.svg") == "unknown"
    assert panels.missing_skill("checklist.md (brief-reader): read the format from the brief itself") == "brief-reader"
    assert panels.missing_skill("analysis/summary.md") == "analysis"
    assert panels.missing_skill("something else") == "unknown"
    (tmp_path / "massing").mkdir()
    assert panels.source_skills(["massing/areas.csv", "brief p. 33"], tmp_path) == "massing, unknown"


def test_issues_md_is_a_report_for_the_lead_by_skill(tmp_path):
    (tmp_path / "proposal" / "plans").mkdir(parents=True)
    (tmp_path / "proposal" / "analysis").mkdir()
    (tmp_path / "proposal" / "massing").mkdir()
    folder, out = tmp_path / "proposal", tmp_path / "proposal" / "panel-layout"
    out.mkdir()
    f = "plans/" + drawing(folder / "plans", "detail-2_1-500.svg", 300, 200)
    d2 = {"id": "d2", "type": "drawing", "file": f, "scale": "1:1000", "frame": {"w": 150, "h": 60}}  # 1:500 drawn, cropped
    panels.measure(d2, folder, {}, STYLE, [], (564, 780))
    figs = {"id": "f", "type": "figures", "rows": [["Homes", "2,950", "massing/areas.csv"], ["Homes", "3,100", "analysis/metrics.csv"]]}
    res = [{"n": 2, "placed": [(d2, {"x": 15, "y": 15, "w": 150, "h": 60}), (figs, {"x": 15, "y": 90, "w": 200, "h": 40})],
            "unplaced": [], "checks": [], "story": "", "paths": []}]
    L = {"required": [{"what": "detail area 2", "id": "d2"},
                      {"what": "long section", "by": "site-section"},
                      {"what": "sealing statement"}]}
    panels.write_report(out, L, FMT, res, [], {"d2", "f"}, [], {"missing": [], "skills": {}}, None, 96)
    issues = (out / "issues.md").read_text(encoding="utf-8")
    up, here = issues.split("## Fix in panel-layout")
    assert "| Severity | Issue | Affected | Evidence | Recommended fix |" in up
    plans = up.split("### plans")[1].split("###")[0]
    assert "| medium | drawn at another scale than its frame |" in plans and "draw it at 1:1,000" in plans
    section = up.split("### site-section")[1].split("###")[0]
    assert "| high | required item missing | long section |" in section and "the skill has not run" in section
    assert "### analysis, massing" in up and "2,950" in up              # sources that disagree: both skills
    assert "### unknown" in up and "sealing statement" in up.split("### unknown")[1]
    assert up.index("### unknown") > up.index("### site-section")       # unknown comes last
    assert "| high | required drawing cropped over the limit |" in here   # the frame is ours
    assert "| medium | disagreeing figures not named |" in here
    assert "For the studio lead: " in issues and "Fix in panel-layout: " in issues
