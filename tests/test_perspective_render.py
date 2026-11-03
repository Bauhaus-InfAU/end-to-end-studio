"""The perspective skill's render step: no key or no package stops it with one line and no image; a fake image model
gets the base view, the depth map and a prompt that keeps the geometry, and its image is written and checked for size.
The real image API is never called."""
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from conftest import REPO

SCRIPTS = REPO / "plugins/drawings/skills/perspective/scripts"
SCRIPT = SCRIPTS / "render.py"
sys.path.insert(0, str(SCRIPTS))
import render  # noqa: E402

BASE = (300, 200)


def proposal(tmp_path, standard=True, narrative=True):
    p = tmp_path / "2030-01-01_run-1"
    out = p / "perspective"
    out.mkdir(parents=True)
    Image.new("RGB", BASE, (200, 200, 200)).save(out / "view-1_base.png")
    Image.new("L", BASE, 120).save(out / "view-1_depth.png")
    (out / "views.json").write_text(json.dumps({"views": [{
        "name": "view-1", "stem": "view-1", "situation": "square", "why": "a public square with the buildings around it",
        "files": {"base_png": "view-1_base.png", "depth_png": "view-1_depth.png"}}]}), encoding="utf-8")
    if narrative:
        (p / "narrative").mkdir()
        (p / "narrative/narrative.md").write_text(
            "# Narrative\n\n## Title and subtitle\n\n**Courtyards**\n*A subtitle*\n\n## Idea\n\n**Every block opens onto a shared yard.**\n\n"
            "More text.\n\n## Principles\n\n1. Something else.\n", encoding="utf-8")
    if standard:
        (p / "drawing-graphics").mkdir()
        (p / "drawing-graphics/standard.md").write_text(
            "# Standard\n\n## Colour\n- Accent #c8442b for the new.\n\n## Renders and perspectives\n"
            "- Overcast autumn light, brick and timber facades.\n- People at true scale.\n", encoding="utf-8")
    return p


def png_bytes(size):
    buf = io.BytesIO()
    Image.new("RGB", size, (90, 120, 150)).save(buf, format="PNG")
    return buf.getvalue()


def fake_client(size, calls):
    def generate_content(model, contents, config=None):
        calls.append({"model": model, "contents": contents})
        return SimpleNamespace(parts=[SimpleNamespace(text="Here is the image.", inline_data=None),
                                      SimpleNamespace(text=None, inline_data=SimpleNamespace(data=png_bytes(size), mime_type="image/png"))])
    return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))


def run(args, code=None, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k not in render.KEYS}
    env.update({"PYTHONUTF8": "1", **(env_extra or {})})
    cmd = [sys.executable, "-c", code, *map(str, args)] if code else [sys.executable, str(SCRIPT), *map(str, args)]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)


def test_no_key_stops_with_one_line_and_no_image(tmp_path):
    p = proposal(tmp_path)
    r = run([p, "--env", tmp_path])
    assert r.returncode == 1
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1 and "GEMINI_API_KEY" in lines[0] and "no image" in lines[0]
    assert not (p / "perspective/view-1.png").exists() and not (p / "perspective/render.json").exists()


def test_no_package_stops_with_one_line_and_no_image(tmp_path):
    p = proposal(tmp_path)
    (tmp_path / ".env").write_text("GEMINI_API_KEY=not-a-real-key\n", encoding="utf-8")
    code = ("import sys, runpy; sys.modules['google'] = None; sys.argv = ['render.py'] + sys.argv[1:]; "
            f"runpy.run_path({str(SCRIPT)!r}, run_name='__main__')")
    r = run([p, "--env", tmp_path], code=code)
    assert r.returncode == 1
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1 and "google-genai" in lines[0] and "not-a-real-key" not in r.stdout + r.stderr
    assert not (p / "perspective/view-1.png").exists()


def test_key_is_found_walking_up_and_never_written(tmp_path):
    p = proposal(tmp_path)
    (tmp_path / ".env").write_text("GOOGLE_API_KEY=not-a-real-key\n", encoding="utf-8")
    key, where = render.find_key(p, environ={})
    assert key == "not-a-real-key" and where.startswith("GOOGLE_API_KEY from")
    assert render.find_key(p, env=p, environ={}) == (None, None)
    assert render.find_key(p, env=p, environ={"GEMINI_API_KEY": "x"})[1] == "GEMINI_API_KEY from the environment"
    render.render(p, fake_client(BASE, []), dict(render.DEFAULTS), key_source=where)
    assert "not-a-real-key" not in (p / "perspective/render.json").read_text(encoding="utf-8")


def test_fake_image_is_written_with_its_prompt(tmp_path):
    p = proposal(tmp_path)
    calls = []
    record = render.render(p, fake_client(BASE, calls), dict(render.DEFAULTS))
    out = p / "perspective"
    assert Image.open(out / "view-1.png").size == BASE
    saved = json.loads((out / "render.json").read_text(encoding="utf-8"))
    v = saved["views"][0]
    assert v["model"] == render.DEFAULTS["model"] == calls[0]["model"] and v["warnings"] == [] and v["size"] == list(BASE)
    assert v["prompt"] == calls[0]["contents"][-1] and render.KEEP_GEOMETRY in v["prompt"]
    assert sum(isinstance(c, Image.Image) for c in calls[0]["contents"]) == 2   # the base view and its depth map
    assert "a public square" in v["prompt"] and '"Courtyards"' in v["prompt"] and "shared yard" in v["prompt"]
    assert "Overcast autumn light" in v["prompt"] and "c8442b" not in v["prompt"] and saved["look_source"].endswith("standard.md")
    assert record["notes"] == []


def test_other_size_is_resampled_and_other_shape_warned(tmp_path):
    p = proposal(tmp_path)
    v = render.render(p, fake_client((600, 400), []), dict(render.DEFAULTS))["views"][0]
    assert Image.open(p / "perspective/view-1.png").size == BASE and v["returned_size"] == [600, 400]
    assert "resampled" in v["warnings"][0]
    v = render.render(p, fake_client((400, 400), []), dict(render.DEFAULTS))["views"][0]
    assert Image.open(p / "perspective/view-1.png").size == (400, 400)
    assert "framing changed" in v["warnings"][0]


def test_without_standard_or_narrative_it_says_so(tmp_path):
    p = proposal(tmp_path, standard=False, narrative=False)
    record = render.render(p, fake_client(BASE, []), dict(render.DEFAULTS))
    assert record["look_source"] == "default" and len(record["notes"]) == 2
    assert render.DEFAULTS["look"] in record["views"][0]["prompt"] and render.KEEP_GEOMETRY in record["views"][0]["prompt"]


def test_no_image_back_writes_no_file(tmp_path):
    p = proposal(tmp_path)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **k: SimpleNamespace(parts=[SimpleNamespace(text="Refused.", inline_data=None)])))
    v = render.render(p, client, dict(render.DEFAULTS))["views"][0]
    assert not (p / "perspective/view-1.png").exists() and "no image" in v["warnings"][0]


def test_redrawn_base_sets_the_old_render_aside(tmp_path):
    """A render whose base view perspective.py redraws differently is moved to <stem>_stale.png; an unchanged one stays."""
    import perspective
    p = proposal(tmp_path)
    out = p / "perspective"
    base = out / "view-1_base.svg"
    base.write_text("<svg>camera A</svg>", encoding="utf-8")
    render.render(p, fake_client(BASE, []), dict(render.DEFAULTS))
    assert perspective.set_aside_stale_render(out, "view-1", base.read_bytes()) is None   # redrawn the same
    assert (out / "view-1.png").exists()
    assert perspective.set_aside_stale_render(out, "view-1", None) is None                # no earlier base to judge by
    old = base.read_bytes()
    base.write_text("<svg>camera B</svg>", encoding="utf-8")
    warning = perspective.set_aside_stale_render(out, "view-1", old)
    assert not (out / "view-1.png").exists() and (out / "view-1_stale.png").exists()
    assert "view-1_stale.png" in warning and "again" in warning
