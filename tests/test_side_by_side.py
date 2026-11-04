"""side_by_side.py: references beside a version's drawings at one print size, in a dot-folder."""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "plugins/studio/skills/competition-proposal/scripts/side_by_side.py"


def img(path, size, color):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


def project(tmp_path):
    refs = tmp_path / "references"
    refs.mkdir(parents=True)
    (refs / "README.md").write_text("| Skill | Files |\n|---|---|\n| plans | `site-plan`, `detail-area-1` |\n"
                                    "| perspective | `perspective-1` to `perspective-3` |\n", encoding="utf-8")
    for n in (1, 2):
        e = refs / "winners" / f"{n}_prize_x"
        img(e / "board-1.jpg", (594, 841), "white")
        img(e / "board-1_marked.jpg", (594, 841), "red")
        img(e / "site-plan.jpg", (400, 300), "green")
        img(e / "detail-area-2.jpg", (200, 200), "blue")
        img(e / "perspective-2.jpg", (300, 200), "gray")
    v = tmp_path / "proposals" / "2026-01-01_t"
    (v / "panel-layout").mkdir(parents=True)
    (v / "panel-layout" / "layout.json").write_text(json.dumps({"format": {"width_mm": 594}}), encoding="utf-8")
    img(v / "panel-layout" / "panel-1.png", (594, 841), "white")
    img(v / "plans" / "site-plan_1-3000.png", (600, 400), "black")
    (v / "plans" / "site-plan_1-3000.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="200mm"/>')
    img(v / "perspective" / "view-1.png", (300, 200), "black")
    img(v / "perspective" / "view-1_base.png", (300, 200), "black")
    return refs, v


def run(v, refs):
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), str(v), "--references", str(refs)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_sheets_in_dot_folder(tmp_path):
    refs, v = project(tmp_path)
    out = run(v, refs)
    assert sorted(p.name for p in (v / ".compare").glob("*.jpg")) == ["boards.jpg", "perspective.jpg", "plans.jpg"]
    assert "perspective.jpg: 2 references, 1 of ours" in out  # the _base helper image is not a drawing
    assert not [p for p in v.glob("*/*.jpg") if not p.parent.name.startswith(".")]  # nothing lands in a skill's folder


def test_json_overrides_readme(tmp_path):
    refs, v = project(tmp_path)
    (refs / "references.json").write_text(json.dumps({"plans": ["winners/*/detail-area-*.jpg"]}), encoding="utf-8")
    out = run(v, refs)
    assert "plans.jpg: 2 references" in out
    assert not (v / ".compare" / "perspective.jpg").exists()
