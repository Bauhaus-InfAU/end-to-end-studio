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


A1 = {"width_mm": 594, "height_mm": 841, "margin_mm": 15, "gutter_mm": 6}


def report(tmp_path, placed, required=()):
    results = [{"n": 1, "placed": placed, "unplaced": [], "checks": [], "story": "", "paths": []}]
    return panels.write_report(tmp_path, {"required": list(required)}, A1, results, [], {it["id"] for it, _ in placed},
                               [], {"missing": []}, None, 96)


def test_table_only_where_the_brief_asks_for_it(tmp_path):
    """Issue #44: a table is a problem unless a required item of the brief points to it."""
    full = {"x": 15, "y": 21, "w": 564, "h": 805}
    rows = [["homes", "1,000", "massing, summary"]]
    asked = {"id": "mix", "type": "figures", "rows": rows}
    extra = {"id": "sealing", "type": "figures", "rows": rows}
    text = report(tmp_path, [(asked, dict(full, h=400)), (extra, dict(full, y=427, h=399))],
                  [{"what": "housing mix", "source": "brief, p. 1", "id": "mix"}])
    assert text.count("a table the brief doesn't ask for") == 1 and "`sealing`" in text


def test_blank_block_where_a_drawing_would_fit(tmp_path):
    """Issue #44: the largest blank block is reported, and flagged when a drawing of the panel fits in it."""
    hero = {"id": "plan", "type": "drawing", "file": "plan.svg"}
    small = {"id": "dia", "type": "drawing", "file": "dia.svg"}
    gap = report(tmp_path, [(hero, {"x": 15, "y": 21, "w": 564, "h": 500}), (small, {"x": 15, "y": 527, "w": 180, "h": 120})])
    assert "largest blank block: 384 x 305 mm at (195, 521) mm" in gap   # beside the small drawing, under the hero
    assert gap.count("would fit in it (`dia`") == 1
    full = report(tmp_path, [(hero, {"x": 15, "y": 21, "w": 564, "h": 680}), (small, {"x": 15, "y": 707, "w": 564, "h": 119})])
    assert "would fit in it" not in full and "largest blank block" in full


def test_largest_blank_ignores_gutters():
    """Thin gaps between frames are never the largest blank block of a full panel."""
    boxes = [{"x": 15, "y": 21, "w": 279, "h": 805}, {"x": 300, "y": 21, "w": 279, "h": 805}]
    x, y, w, h = panels.largest_blank(boxes, A1)
    assert w * h <= 6 * 805 + 1


FIX = REPO / "tests/fixtures/panels"
CODE_BOX = [{"x": 0, "y": 0, "w": 60, "h": 40}]


def test_blank_seen_finds_the_space_run10_left_on_panel_1():
    """Issue #44, sticky 53: run-10's panel 1 (its own end layout, rendered about 2 mm a pixel) has blank paper
    beside the title, above the pictograms. Between the boxes only 366 x 40 mm is free; on the print it is larger."""
    fmt = dict(A1, content_top_mm=52)
    x, y, w, h = panels.largest_blank_seen(FIX / "run10-panel-1_small.png", fmt, CODE_BOX)
    assert h > 2 * 40 and w * h > 1.5 * 366 * 40 and x > 250 and y < 100, (x, y, w, h)


def test_blank_seen_inside_a_text_box_is_flagged(tmp_path):
    """Issue #44: the first after-run's panel 1 left the foot white under a short idea text; it lies in the text box,
    and a drawing of the panel would fit in it."""
    fmt = dict(A1, content_top_mm=46)
    seen = panels.largest_blank_seen(FIX / "issue44-after-panel-1_small.png", fmt, CODE_BOX)
    x, y, w, h = seen
    assert y > 700 and w > 500 and h > 80, seen
    idea = {"id": "idea", "type": "text", "text": "short"}
    dia = {"id": "dia", "type": "drawing", "file": "dia.svg"}
    results = [{"n": 1, "placed": [(idea, {"x": 15, "y": 707, "w": 564, "h": 119}), (dia, {"x": 15, "y": 298, "w": 89, "h": 80})],
                "unplaced": [], "checks": [], "story": "", "paths": [], "blank_seen": seen}]
    text = panels.write_report(tmp_path, {}, fmt, results, [], {"idea", "dia"}, [], {"missing": []}, None, 96)
    assert "largest blank block seen" in text and "inside `idea`" in text and "would fit in it (`dia`" in text


def test_png_rows_undoes_every_filter(tmp_path):
    """The PNG reader needs no library: rows filtered None, Sub, Up, Average and Paeth come back as written."""
    import struct, zlib
    w, rows = 4, [bytes([10 * i + y, 200 - i, 255 * (i % 2)]) for y in range(5) for i in range(4)]
    rows = [b"".join(rows[y * w:(y + 1) * w]) for y in range(5)]
    prev, raw = bytes(3 * w), b""
    for f, line in enumerate(rows):
        out = bytearray()
        for i, v in enumerate(line):
            a, b, c = (line[i - 3] if i >= 3 else 0), prev[i], (prev[i - 3] if i >= 3 else 0)
            p = a + b - c
            pr = a if abs(p - a) <= abs(p - b) and abs(p - a) <= abs(p - c) else b if abs(p - b) <= abs(p - c) else c
            out.append((v - (0, a, b, (a + b) // 2, pr)[f]) & 255)
        raw += bytes([f]) + bytes(out)
        prev = line
    chunk = lambda k, d: struct.pack(">I", len(d)) + k + d + struct.pack(">I", zlib.crc32(k + d))
    png = tmp_path / "t.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, 5, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    assert panels.png_rows(png) == (w, 5, rows)


def test_caption_repeating_the_drawings_own_title(tmp_path):
    """A caption that repeats the title the drawing prints is named, unless the frame crops that title away."""
    (tmp_path / "fg.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                                     '<text x="5" y="90">Figure-ground, <tspan>1:15,000</tspan></text></svg>', encoding="utf-8")
    it = {"id": "fg", "type": "drawing", "file": "fg.svg", "caption": "Figure-ground", "_draw_h": 200, "_oy": 0, "_img_h": 200}
    assert panels.caption_repeats_title(it, tmp_path) == "Figure-ground, 1:15,000"
    assert panels.caption_repeats_title(dict(it, _img_h=150), tmp_path) is None      # title at 180 mm, below the frame
    assert panels.caption_repeats_title(dict(it, caption="Figure-ground plan of the district"), tmp_path) is None


def test_issues_name_who_fixes_the_blank_and_the_table(tmp_path):
    """Issue #44 in issues.md: the blank at the foot of the after-run's panel 1 covers the planned frame of an analysis
    map that didn't fit (drawn at 1:3,000 for a 1:15,000 band), so it goes to analysis; a table the brief doesn't ask
    for is panel-layout's own to fix. Neither changes the problem count, like "panel mostly empty"."""
    fmt = dict(A1, content_top_mm=46)
    seen = panels.largest_blank_seen(FIX / "issue44-after-panel-1_small.png", fmt, CODE_BOX)
    dia = {"id": "dia", "type": "drawing", "file": "concept-diagrams/03_one-field.svg"}
    table = {"id": "counted", "type": "figures", "rows": [["Site", "112.8 ha", "analysis, summary"]]}
    slot = {"id": "sealing-today", "type": "drawing", "file": "analysis/sealing_today.svg", "scale": "1:15000",
            "x": 15, "y": 780, "frame": {"w": 108, "h": 105}}
    results = [{"n": 1, "placed": [(dia, {"x": 15, "y": 298, "w": 89, "h": 80}), (table, {"x": 300, "y": 298, "w": 200, "h": 60})],
                "unplaced": [(slot, "at 1:15,000 its smallest text would be 2.4 px")], "checks": [], "story": "", "paths": [],
                "blank_seen": seen}]
    text = panels.write_report(tmp_path, {}, fmt, results, [], {"dia", "counted"}, [], {"missing": []}, None, 96)
    issues = (tmp_path / "issues.md").read_text(encoding="utf-8")
    up, here = issues.split("## Fix in panel-layout")
    assert "### analysis" in up and "blank space left where a planned drawing didn't fit" in up and "`sealing-today`" in up
    assert "a table the brief doesn't ask for" in here and "`counted`" in here
    assert "Problems: 1." in text                     # only the drawing that did not fit


def panel2_after(tmp_path, seen):
    """The after-run's panel 2 as it was placed: two plans and three numbers on top, a text box, the site plan, the section."""
    box = lambda x, y, w, h: {"x": x, "y": y, "w": w, "h": h}
    items = [({"id": "open-space", "type": "drawing", "file": "open-space/open-space_1-10000.svg"}, box(15, 46, 178, 152)),
             ({"id": "mobility", "type": "drawing", "file": "mobility/mobility_1-15000.svg"}, box(199, 46, 114, 146)),
             ({"id": "sealing-0", "type": "number", "value": "32.3 %", "source": "open-space, sealing table"}, box(319, 46, 83, 60)),
             ({"id": "whole", "type": "text", "text": "A tight city on the field line"}, box(319, 112, 260, 94)),
             ({"id": "site-plan", "type": "drawing", "file": "plans/site-plan_1-3000.svg"}, box(28, 212, 537, 530)),
             ({"id": "site-section", "type": "drawing", "file": "site-section/site-section_design_1-3000.svg"}, box(15, 756, 564, 68))]
    results = [{"n": 2, "placed": items, "unplaced": [], "checks": [], "story": "", "paths": [], "blank_seen": seen}]
    text = panels.write_report(tmp_path, {}, dict(A1, content_top_mm=46), results, [], {it["id"] for it, _ in items},
                               [], {"missing": []}, None, 96)
    return text, (tmp_path / "issues.md").read_text(encoding="utf-8")


def test_a_large_blank_no_drawing_fits_is_still_named(tmp_path):
    """Issue #44: on the after-run's panel 2, 266 x 78 mm of the text box `whole` stayed paper (measured on the render).
    No drawing of the panel is small enough to fit in it, but it is large: panel-layout's to fix, low, not counted."""
    text, issues = panel2_after(tmp_path, (312, 134, 266, 78))
    assert "266 x 78 mm at (312, 134) mm, 207 cm², inside `whole`  **a large blank" in text
    here = issues.split("## Fix in panel-layout")[1]
    assert "| low | large blank space | panel 2 |" in here and "at least 60 mm each way and 150 cm²" in here
    assert "Problems: 0." in text


def test_thin_blank_strips_are_not_named(tmp_path):
    """The gutters and strips the after-run left (564 x 14 mm on panel 2, 478 x 32 mm on panel 3) are under 60 mm
    one way: listed in the report, never flagged."""
    for seen in ((15, 742, 564, 14), (100, 619, 478, 32)):
        text, issues = panel2_after(tmp_path, seen)
        assert "large blank" not in text and "blank space" not in issues


def hierarchy(tmp_path, placed, paper=None, section_ink=None):
    results = [{"n": 1, "placed": placed, "unplaced": [], "checks": [], "story": "", "paths": [], "paper_seen": paper,
                "section_ink": section_ink}]
    text = panels.write_report(tmp_path, {}, dict(A1, content_top_mm=46), results, [], {it["id"] for it, _ in placed},
                               [], {"missing": []}, None, 96)
    return text, (tmp_path / "issues.md").read_text(encoding="utf-8").split("## Fix in panel-layout")[1]


def test_a_panel_without_a_dominant_drawing_is_named(tmp_path):
    """Issue #44: the after-run's panel 1 led with a 360 x 240 mm perspective, 20 % of the content area, beside
    a site plan of 537 x 530 mm that would take 65 %; a panel led by such a site plan is fine."""
    view = {"id": "view-1", "type": "drawing", "file": "perspective/view-1.png", "_img_w": 360, "_img_h": 240}
    plan = {"id": "site-plan", "type": "drawing", "file": "plans/site-plan_1-3000.svg", "_img_w": 537, "_img_h": 530,
            "_draw_w": 537, "_draw_h": 530, "_print_scale": 3000, "_own": 3000, "_factor": 1.0,
            "_auto": False, "_hidden": 0.0, "_own_bar": True}
    text, here = hierarchy(tmp_path, [(view, {"x": 15, "y": 46, "w": 360, "h": 246})])
    assert "dominant drawing: `view-1`, 20 %" in text and "| low | no dominant drawing | panel 1 |" in here
    text, here = hierarchy(tmp_path, [(plan, {"x": 28, "y": 280, "w": 537, "h": 536}), (view, {"x": 15, "y": 46, "w": 300, "h": 200})])
    assert "dominant drawing: `site-plan`, 65 %" in text and "no dominant drawing" not in here
    assert "Problems: 0." in text


def test_a_detail_area_its_scale_holds_small_is_not_an_issue(tmp_path):
    """A fixed-scale drawing shown whole can't grow: 478 x 384 mm at 1:1,000 is named in the report, not in issues.md."""
    detail = {"id": "detail-1", "type": "drawing", "file": "plans/detail-area-1_1-1000.svg", "_img_w": 478, "_img_h": 384,
              "_draw_w": 478, "_draw_h": 384, "_print_scale": 1000, "_own": 1000, "_factor": 1.0,
              "_auto": False, "_hidden": 0.0, "_own_bar": True}
    text, here = hierarchy(tmp_path, [(detail, {"x": 15, "y": 46, "w": 478, "h": 390})])
    assert "but its scale fixes its size" in text and "no dominant drawing" not in here


def test_paper_share_of_the_rendered_panel():
    """The after-run's first panel 1 left more than half its content area as paper; the winners' boards leave 12 to 56 %."""
    share = panels.paper_share_seen(FIX / "issue44-after-panel-1_small.png", dict(A1, content_top_mm=46), CODE_BOX)
    assert 0.5 < share < 0.65, share


def test_section_ratio_counts_the_drawing_not_the_frame(tmp_path):
    """Issue #44: what counts is how high the section shows, not its frame. Without a render only the frame is known:
    564 x 54 mm (0.10) is named. The after-runs gave the section an 89 mm frame (0.16), but at 1:3,000 its ground,
    buildings and notes showed only 46 mm high (0.08), the rest empty sky: named. A drawing 90 mm high (0.16) is not."""
    sec = lambda h: {"id": "site-section", "type": "drawing", "file": "site-section/site-section_design_1-3000.svg",
                     "_img_w": 564, "_img_h": h}
    text, here = hierarchy(tmp_path, [(sec(54), {"x": 15, "y": 760, "w": 564, "h": 60})], paper=0.7)
    assert "frame 564 x 54 mm, drawing not measured (no render), 0.10 high for its width  **under 0.15**" in text
    assert "| low | section drawing too low |" in here and "a taller frame alone adds only sky" in here
    assert "paper seen: 70 %" in text and "much of the panel left as paper" in here
    text, here = hierarchy(tmp_path, [(sec(89), {"x": 15, "y": 725, "w": 564, "h": 95})], section_ink={"site-section": 46})
    assert "frame 564 x 89 mm, drawing seen 46 mm high, 0.08 high for its width  **under 0.15**" in text
    assert "| low | section drawing too low |" in here and "the drawing in it 46 mm high" in here
    text, here = hierarchy(tmp_path, [(sec(90), {"x": 15, "y": 730, "w": 564, "h": 96})], paper=0.3, section_ink={"site-section": 90})
    assert "section drawing too low" not in here and "left as paper" not in here
    assert "Problems: 0." in text


def test_ink_height_seen_ignores_empty_sky(tmp_path):
    """The section's visible height is measured from its ink, not its frame: on a page about 2 mm a pixel, a frame
    40 px high holding ink only in its lower 12 px reads about 12 px (24 mm), not 40; a frame of paper reads None."""
    import struct, zlib
    w, h = 297, 421
    white, ink = bytes([255, 255, 255]), bytes([64, 64, 64])
    rows = [bytes([0]) + (white * 20 + ink * 250 + white * 27 if 300 <= y < 312 else white * w) for y in range(h)]
    chunk = lambda k, d: struct.pack(">I", len(d)) + k + d + struct.pack(">I", zlib.crc32(k + d))
    signature = bytes([137, 80, 78, 71, 13, 10, 26, 10])
    png = tmp_path / "band.png"
    png.write_bytes(signature + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
    mm = 841 / h
    fmt = dict(A1, content_top_mm=46)
    seen = panels.ink_height_seen(png, fmt, CODE_BOX, "#ffffff", (15, 272 * mm, 564, 40 * mm))
    assert abs(seen - 12 * mm) < 2 * mm, seen
    assert panels.ink_height_seen(png, fmt, CODE_BOX, "#ffffff", (15, 100, 564, 40)) is None
