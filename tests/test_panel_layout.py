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


def test_wide_text_in_columns():
    h = page([{"id": "t", "type": "text", "text": "a"}])
    assert re.search(r"\.box\.text > div \{[^}]*column-width:\s*\d+em", h)
