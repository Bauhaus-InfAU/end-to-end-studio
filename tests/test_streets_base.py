"""The drawings take the street surface from the streets skill's file when it exists, and buffer lines only without it."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
import pytest
import pyproj
from shapely.geometry import shape, mapping, box, LineString
from shapely.ops import transform, polylabel
from conftest import REPO

try:
    from synthetic import make_proposal   # plan 001's synthetic proposal
except ImportError:
    make_proposal = None

SITE = REPO / "competition/site"
ISO = REPO / "plugins/drawings/skills/isometric/isometric.py"
OPEN = REPO / "plugins/design/skills/open-space/scripts/open_space.py"
MASSING = REPO / "plugins/design/skills/massing/scripts/massing.py"


def run(script, *args, check=True):
    r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONUTF8": "1"})   # the scripts write their text as UTF-8 on Windows too
    if check and r.returncode:
        raise AssertionError(r.stderr[-2000:])
    return r


def write_fc(path, feats):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")


@pytest.fixture
def proposal(tmp_path):
    """A proposal folder with a small streets/streets.geojson inside the site: (proposal, site folder)."""
    root = tmp_path / "with space"
    if make_proposal:
        out = make_proposal(root)
        site_dir = root / "site"
    else:
        site_dir = root / "site"
        shutil.copytree(SITE, site_dir)
        out = root / "proposals" / "2026-01-01_t"
    g = shape(json.loads((site_dir / "site.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
    c = g.centroid
    epsg = (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform
    p = polylabel(transform(to_m, g), 1.0)
    feat = lambda geom, **props: {"type": "Feature", "properties": props, "geometry": mapping(transform(to_ll, geom))}
    if not make_proposal:
        write_fc(out / "massing/massing.geojson",
                 [feat(box(p.x + 20, p.y + 20, p.x + 60, p.y + 40), kind="building", floors=4, height_m=12)])
    write_fc(out / "streets/streets.geojson", [
        feat(box(p.x - 100, p.y - 5, p.x + 100, p.y + 5), kind="street", use="street", existing=True, source="test"),
        feat(box(p.x - 5, p.y + 5, p.x + 5, p.y + 105), kind="street", use="street", existing=False, source="test"),
        feat(LineString([(p.x - 100, p.y - 50), (p.x + 100, p.y - 50)]), kind="path", existing=False, type="path"),
    ])
    return out, site_dir


def test_isometric_uses_streets_file(proposal):
    out, site_dir = proposal
    streets = out / "streets/streets.geojson"
    summary = out / "isometric/summary.md"
    style = out / "drawing-graphics/style.json"
    extra = ["--style", style] if style.exists() else []
    run(ISO, site_dir, out, 3000, 594, *extra)
    assert "streets from streets/streets.geojson" in summary.read_text(encoding="utf-8")
    # without the file the skill still works alone, on its own widths
    held = streets.read_text(encoding="utf-8"); streets.unlink()
    run(ISO, site_dir, out, 3000, 594, *extra)
    assert "street widths assumed by class" in summary.read_text(encoding="utf-8")
    streets.write_text(held, encoding="utf-8")


@pytest.mark.skipif(make_proposal is None, reason="needs tests/synthetic.py (plan 001) for a massing to run on")
def test_open_space_accepts_streets(proposal):
    out, site_dir = proposal
    run(MASSING, "--proposal", out, "--site", site_dir, "--config", out / "massing/config.json")
    cfg = out / "open-space/config.json"
    cfg.parent.mkdir(exist_ok=True)
    cfg.write_text(json.dumps({"residents": 1000, "green_m2_per_resident": 12, "play_m2_per_resident": 1.5,
                               "play_min_m2": 500, "scale": 3000, "sources": {"residents": "test"}}), encoding="utf-8")
    r = run(OPEN, "--site", site_dir / "site.geojson", "--layers", site_dir, "--massing", out / "massing/massing.geojson",
            "--config", cfg, "--out", out / "open-space", "--streets", out / "streets/streets.geojson")
    assert r.returncode == 0
    text = (out / "open-space/assumptions.md").read_text(encoding="utf-8")
    assert "streets" in text and "from the streets skill" in text


def test_reads_lines_name_streets():
    for skill in ["drawings/skills/isometric", "design/skills/open-space", "drawings/skills/perspective", "design/skills/mobility"]:
        text = (REPO / "plugins" / skill / "SKILL.md").read_text(encoding="utf-8")
        reads = re.findall(r"^Reads(?: \(end\))?:(.*)$", text, re.M)
        assert any("streets" in line for line in reads), skill
