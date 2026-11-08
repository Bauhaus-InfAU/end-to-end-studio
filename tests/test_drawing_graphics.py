"""drawing-graphics: the base standard passes its own check, and the check holds the floors."""
import json, subprocess, sys
from conftest import REPO

DG = REPO / "plugins/drawings/skills/drawing-graphics"
CHECK = DG / "scripts/check_style.py"


def check(style, tmp_path):
    p = tmp_path / "style.json"
    p.write_text(json.dumps(style), encoding="utf-8")
    return subprocess.run([sys.executable, str(CHECK), str(p)], capture_output=True, text=True, encoding="utf-8")


def base():
    return json.loads((DG / "base.json").read_text(encoding="utf-8"))


def test_base_passes(tmp_path):
    r = check(base(), tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_keys_the_scripts_read(tmp_path):
    keys = {"paper", "ink", "accent", "new", "existing", "context", "building", "street", "path", "park", "kept",
            "water", "lawn", "meadow", "wet-meadow", "grove", "font", "thin", "mid", "thick", "line", "line_mm",
            "outline", "text", "title", "ramp", "heading_pt", "body_pt", "background", "public", "shadow", "shadow_len"}
    assert keys <= set(base())


def test_white_buildings_pass(tmp_path):
    s = base(); s["new"] = "#ffffff"
    r = check(s, tmp_path)
    assert r.returncode == 0, r.stdout


def test_marks_say_who_carries_them(tmp_path):
    """Issue #34: the base places drawings on panels (marks "panel"); "drawing" is the other value, anything else fails."""
    assert base()["marks"] == "panel"
    s = base(); s["marks"] = "drawing"
    assert check(s, tmp_path).returncode == 0
    s["marks"] = "everywhere"
    r = check(s, tmp_path)
    assert r.returncode != 0 and "marks" in r.stdout
    s.pop("marks")
    assert "marks: missing" in check(s, tmp_path).stdout


def test_type_sizes_on_the_standards_scale():
    """Labels at 9 pt and a drawing's own title at the subheading's 14 pt, the sizes base.md lists (1 pt = 25.4/72 mm)."""
    pt = lambda mm: mm / 25.4 * 72
    assert round(pt(base()["text"])) == 9 and round(pt(base()["title"])) == 14


def test_small_text_fails(tmp_path):
    s = base(); s["text"] = 2.0
    r = check(s, tmp_path)
    assert r.returncode != 0 and "text" in r.stdout


def test_low_contrast_accent_fails(tmp_path):
    s = base(); s["accent"] = "#f4f0ea"
    r = check(s, tmp_path)
    assert r.returncode != 0 and "accent" in r.stdout


def test_new_keys_checked(tmp_path):
    for key, bad in (("storey_labels", "latin"), ("render_style", ""), ("diagram", {"label_size": 9})):
        s = base(); s[key] = bad
        r = check(s, tmp_path)
        assert r.returncode != 0 and key in r.stdout, (key, r.stdout)


def test_skill_reads_narrative_then_references():
    t = (DG / "SKILL.md").read_text(encoding="utf-8")
    assert "Reads: brief-reader, narrative" in t
    assert t.index("base.md") < t.index("narrative/") < t.index("references/")
