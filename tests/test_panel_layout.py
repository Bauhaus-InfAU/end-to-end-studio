"""Panel text: never below 12 px (9 pt) on the printed panel, and wide text set in columns."""
import importlib.util, re
from pathlib import Path
from conftest import REPO

spec = importlib.util.spec_from_file_location("panels", REPO / "plugins/delivery/skills/panel-layout/scripts/panels.py")
panels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panels)

STYLE = {"font": "sans-serif", "text": "#000", "background": "#fff", "accent": "#c00",
         "line_mm": 0.25, "heading_pt": 6, "body_pt": 7}


def page(items=(), marks=()):
    placed = [(it, {"x": 0, "y": 0, "w": 400, "h": 100}) for it in items]
    return panels.panel_html(1, 1, placed, {"width_mm": 594, "height_mm": 841}, [], list(marks), STYLE, {}, Path("."))


def test_no_font_below_12_px():
    h = page([{"id": "t", "type": "text", "text": "a", "pt": 5},
              {"id": "f", "type": "figures", "rows": [["a", "1", "src"]]}], [{"text": "x", "x": 0, "y": 0, "pt": 4}])
    sizes = [float(v) for v in re.findall(r"font-size:\s*([\d.]+)pt", h)]
    assert sizes and min(sizes) >= 9, sorted(sizes)[:3]
    assert not re.search(r"font-size:\s*\.\d+em", h)          # relative sizes get a 12 px floor too


def test_big_number_with_its_source_in_one_line(tmp_path):
    """A key number is big type with its source in one line; its fonts keep the 12 px floor; no source is a problem."""
    num = {"id": "n", "type": "number", "value": "1,000", "text": "homes", "source": "massing, summary", "pt": 5}
    h = page([num])
    sizes = [float(v) for v in re.findall(r"font-size:\s*([\d.]+)pt", h)]
    assert min(sizes) >= 9 and 'class="big"' in h and "1,000" in h and "massing, summary" in h
    assert re.search(r"\.box\.number \.src \{[^}]*white-space:\s*nowrap", h)
    bare = {"id": "m", "type": "number", "value": "1/3", "text": "sealed"}
    results = [{"n": 1, "placed": [(num, {"x": 15, "y": 15, "w": 90, "h": 30}), (bare, {"x": 15, "y": 50, "w": 90, "h": 30})],
                "unplaced": [], "checks": [], "story": "", "paths": []}]
    text = panels.write_report(tmp_path, {}, {"width_mm": 594, "height_mm": 841}, results, [], {"n", "m"}, [], {"missing": []}, None, 96)
    assert text.count("a number without its source") == 1 and "Problems: 1." in text


def test_wide_text_in_columns():
    h = page([{"id": "t", "type": "text", "text": "a"}])
    assert re.search(r"\.box\.text > div \{[^}]*column-width:\s*\d+em", h)


def drawing(tmp_path, name, w_mm, h_mm, font_mm=None):
    """An SVG drawing of w_mm x h_mm, in mm user units, with one label of font_mm if given."""
    label = f'<text x="1" y="5" font-size="{font_mm}">a</text>' if font_mm else ""
    (tmp_path / name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm}mm" height="{h_mm}mm" '
                                 f'viewBox="0 0 {w_mm} {h_mm}"><rect width="{w_mm}" height="{h_mm}"/>{label}</svg>', encoding="utf-8")
    return name


def measured(tmp_path, item):
    notes = []
    panels.measure(item, tmp_path, {}, STYLE, notes, (564, 780))
    return item


def test_auto_picks_largest_usual_scale_that_fits(tmp_path):
    f = drawing(tmp_path, "plan_1-1000.svg", 600, 400, font_mm=6.4)
    it = measured(tmp_path, {"id": "p", "type": "drawing", "file": f, "scale": "auto", "frame": {"w": 300, "h": 300}})
    assert it["_print_scale"] == 2000 and abs(it["_img_w"] - 300) < 0.01 and it["_hidden"] < 1e-6
    assert panels.choose_scale(1000, (600, 400), (300, 300), None) == 2000


def test_fixed_scale_crops_instead(tmp_path):
    f = drawing(tmp_path, "plan_1-1000.svg", 600, 400, font_mm=3.2)
    it = measured(tmp_path, {"id": "p", "type": "drawing", "file": f, "scale": "1:1000", "frame": {"w": 300, "h": 300},
                             "crop": {"focus": [0, 0]}})
    assert it["_print_scale"] == 1000 and it["_factor"] == 1
    assert (it["_img_w"], it["_img_h"], it["_ox"], it["_oy"]) == (300, 300, 0, 0)
    assert abs(it["_hidden"] - (1 - 300 * 300 / (600 * 400))) < 1e-6


def test_text_never_shrinks_under_12_px(tmp_path):
    f = drawing(tmp_path, "plan_1-1000.svg", 600, 400, font_mm=3.2)   # 12.1 px printed at 1:1,000
    it = measured(tmp_path, {"id": "p", "type": "drawing", "file": f, "scale": "auto", "frame": {"w": 300, "h": 300}})
    assert it["_print_scale"] == 1000 and it["_hidden"] > 0           # 1:2,000 would fit, but its text would be 6 px
    it = measured(tmp_path, {"id": "q", "type": "drawing", "file": f, "scale": "1:2000"})
    assert "_unfit" in it and "12 px" in it["_unfit"]                 # a fixed scale that would shrink text is refused


def test_caption_holds_the_printed_scale_once(tmp_path):
    f = drawing(tmp_path, "plan_1-1000.svg", 300, 200, font_mm=3.2)
    it = measured(tmp_path, {"id": "p", "type": "drawing", "file": f, "scale": "1:1000", "caption": "Plan, 1:1,000"})
    h = panels.item_html(it, {"x": 0, "y": 0, "w": 300, "h": 210}, STYLE, tmp_path)
    assert h.count("1:1,000") == 1, h
    assert panels.printed_caption("Plan", 3000) == "Plan · 1:3,000"
    assert panels.printed_caption("Plan, 1:2000", 3000) == "Plan, 1:3,000"   # after a rescale, the printed one


def test_scale_bars_all_only_where_a_scaled_drawing_has_none(tmp_path):
    plain = drawing(tmp_path, "iso_1-1000.svg", 200, 100, font_mm=3.2)
    (tmp_path / "plan_1-1000.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="100mm" viewBox="0 0 200 100">'
        '<text font-size="3.2">0</text><text font-size="3.2">100 m</text></svg>', encoding="utf-8")
    (tmp_path / "perspective").mkdir()
    view = "perspective/" + drawing(tmp_path / "perspective", "view_1-1000.svg", 200, 100, font_mm=3.2)
    assert panels.svg_size(tmp_path / plain)["scale_bar"] is False
    assert panels.svg_size(tmp_path / "plan_1-1000.svg")["scale_bar"] is True

    def bar(file, **kw):
        it = {"id": "d", "type": "drawing", "file": file, **kw}
        panels.measure(it, tmp_path, {}, STYLE, [], (564, 780), scale_bars="all")
        return it["_bar"]
    assert bar(plain, scale="1:1000")                                  # at a scale, no bar of its own: one added
    assert not bar("plan_1-1000.svg", scale="1:1000")                  # it has its own
    assert not bar(plain, w=100)                                       # no scale, no bar
    assert not bar(view, scale="1:1000")                               # never on a perspective
    assert not bar(plain, scale="1:1000", scale_bar=False)             # kept off by hand


def test_sources_in_words_not_paths(tmp_path):
    (tmp_path / "open-space").mkdir()
    (tmp_path / "open-space" / "sealing.csv").write_text("a,b\n", encoding="utf-8")
    words = panels.source_words
    assert words("Soil sealing (open-space/sealing.csv)", tmp_path) == "Soil sealing (open-space, sealing table)"
    assert words("sealing.csv", tmp_path) == "open-space, sealing table"
    assert words("brief p. 33", tmp_path) == "brief p. 33"
    placed = [({"id": "f", "type": "figures", "heading": "Sealing (open-space/sealing.csv)",
                "rows": [["a", "1", "sealing.csv"]]}, {}), ({"id": "g", "heading": "From elsewhere/x.csv"}, {})]
    assert panels.paths_left(placed, tmp_path) == ["`g` heading: elsewhere/x.csv"]


def test_planned_frame_without_its_drawing_is_an_empty_frame(tmp_path):
    """On the first run no drawing exists: a drawing with a frame prints as a grey labelled frame, not dropped."""
    it = measured(tmp_path, {"id": "p", "type": "drawing", "file": "plans/site-plan_1-3000.svg", "scale": "1:3000",
                             "frame": {"w": 300, "h": 200}, "shows": "the whole district", "caption": "Site plan"})
    assert it.get("_empty") and "_error" not in it and (it["_img_w"], it["_img_h"]) == (300, 200)
    h = panels.item_html(it, {"x": 15, "y": 15, "w": it["w"], "h": it["h"]}, STYLE, tmp_path)
    assert 'class="empty"' in h and "1:3,000" in h and "the whole district" in h and "<img" not in h
    assert "_error" in measured(tmp_path, {"id": "q", "type": "drawing", "file": "x.svg", "scale": "1:3000"})  # no frame: missing

    results = [{"n": 1, "placed": [(it, {"x": 15, "y": 15, "w": it["w"], "h": it["h"]})], "unplaced": [], "checks": [],
                "story": "", "paths": []}]
    text = panels.write_report(tmp_path, {"required": [{"what": "site plan", "id": "p"}]}, {"width_mm": 594, "height_mm": 841},
                               results, [], {"p"}, [], {"missing": []}, None, 96)
    assert "EMPTY FRAME" in text and "Required items missing: 1 of 1" in text


def test_planned_item_left_out_is_named(tmp_path):
    """The second run keeps the first run's plan: a planned drawing it left out, or that didn't fit, is a problem."""
    it = {"id": "plan", "type": "drawing", "file": "plans/site-plan_1-3000.svg", "_img_w": 100, "_img_h": 100}
    big = {"id": "iso", "type": "drawing", "file": "isometric/iso_1-1000.svg"}
    results = [{"n": 1, "placed": [(it, {"x": 15, "y": 15, "w": 100, "h": 100})], "unplaced": [(big, "would cover plan")],
                "checks": [], "story": "", "paths": []}]
    plan = {"panels": [{"items": [{"id": "plan", "type": "drawing", "file": it["file"]},
                                  {"id": "section", "type": "drawing", "file": "site-section/section_1-3000.svg"},
                                  {"id": "iso", "type": "drawing", "file": "isometric/iso_1-5000.svg"}]}]}
    report = lambda plan: panels.write_report(tmp_path, {}, {"width_mm": 594, "height_mm": 841}, results, [], {"plan"}, [],
                                              {"missing": []}, None, 96, plan)
    text = report(plan)
    assert "`section`** (site-section/section_1-3000.svg): left out of layout.json" in text
    assert "`iso`** (isometric/iso_1-5000.svg): not placed, would cover plan" in text and "`plan`**" not in text
    assert "Problems: 2." in text                                     # the one that did not fit is counted once
    assert "Planned items not on the panels" not in report(None)


def test_drawing_smaller_than_its_frame_is_named(tmp_path):
    f = drawing(tmp_path, "plan_1-1000.svg", 150, 100, font_mm=3.2)
    it = measured(tmp_path, {"id": "p", "type": "drawing", "file": f, "scale": "1:1000", "frame": {"w": 300, "h": 200}})
    results = [{"n": 1, "placed": [(it, {"x": 15, "y": 15, "w": it["w"], "h": it["h"]})], "unplaced": [], "checks": [],
                "story": "", "paths": []}]
    text = panels.write_report(tmp_path, {}, {"width_mm": 594, "height_mm": 841}, results, [], {"p"}, [], {"missing": []}, None, 96)
    assert "fills 25 % of its frame" in text


def test_added_scale_bar_keeps_the_drawing_in_place():
    """A drawing that gets a scale bar keeps its position and size on the panel."""
    it = {"id": "d", "type": "drawing", "file": "x.svg", "scale": "1:3000",
          "_img_w": 200, "_img_h": 100, "_bar": True, "_scale_held": True}
    h = panels.item_html(it, {"x": 15, "y": 93, "w": 200, "h": 110}, STYLE, Path("."))
    assert 'style="left:15.00mm;top:93.00mm;width:200.00mm;height:110.00mm"' in h, h[:200]
    assert 'class="bar"' in h
