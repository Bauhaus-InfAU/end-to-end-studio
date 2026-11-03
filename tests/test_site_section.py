"""The site section's script: it cuts the site on its own terrain model, on the design too, on a given line,
and draws flat ground with a warning when there is no terrain at all."""
import csv, json, math, os, re, shutil, subprocess, sys
from pathlib import Path
import pytest
import pyproj
from shapely.geometry import shape, LineString, Point
from shapely.ops import transform
from conftest import REPO
sys.path.insert(0, str(Path(__file__).parent))
from synthetic import make_proposal

SITE = REPO / "competition/site"
SECTION = REPO / "plugins/drawings/skills/site-section/scripts/section.py"
MASSING = REPO / "plugins/design/skills/massing/scripts/massing.py"
STYLE = REPO / "plugins/drawings/skills/drawing-graphics/base.json"
needs_tif = pytest.mark.skipif(not (SITE / "terrain-dgm1.tif").exists(), reason="no terrain model in the site folder")


def run(script, *args, env=None, check=True):
    r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONUTF8": "1", **(env or {})})
    if check and r.returncode:
        raise AssertionError(r.stderr[-2000:])
    return r


def section(site, out, *extra, env=None):
    return run(SECTION, "--site", site, "--proposal", out, "--scale", 3000, "--detail-scale", 1000,
               "--style", STYLE, *extra, env=env)


def profile(out):
    with open(out / "site-section/profile.csv", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def cut(out):
    return json.loads((out / "site-section/cut.json").read_text(encoding="utf-8"))


def site_utm(site_dir):
    g = shape(json.loads((site_dir / "site.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
    c = g.centroid
    epsg = (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform
    return transform(to_m, g), to_m, to_ll


def text_sizes_ok(svg):
    s = svg.read_text(encoding="utf-8")
    width_mm = float(re.search(r'<svg[^>]*\bwidth="([\d.]+)mm"', s).group(1))
    view_w = float(re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) [\d.]+"', s).group(1))
    sizes = [float(v) * width_mm / view_w for v in re.findall(r'font-size="([\d.]+)"', s)]
    return sizes and min(sizes) >= 3.2 - 1e-6, (svg.name, min(sizes) if sizes else None)


@needs_tif
def test_section_site_as_is(tmp_path):
    out = tmp_path / "with space" / "2026-01-01_t"
    section(SITE, out)
    d = out / "site-section"
    for f in ["site-section_1-3000.svg", "site-section_1-3000.png",
              "site-section_excerpt_1-1000.svg", "site-section_excerpt_1-1000.png"]:
        assert (d / f).exists(), f
    rows = profile(out)
    assert len(rows) > 100
    assert all("terrain-dgm1.tif" in r["source"] for r in rows)
    c = cut(out)
    assert c["fall_m"] + c["rise_m"] > 5   # the site is not flat
    assert c["cut"] >= 1
    for svg in d.glob("*.svg"):
        ok, why = text_sizes_ok(svg)
        assert ok, why


@needs_tif
def test_section_on_design(tmp_path):
    out = make_proposal(tmp_path / "with space")
    site_dir = out.parent.parent / "site"
    run(MASSING, "--proposal", out, "--site", site_dir, "--config", out / "massing/config.json")
    feats = json.loads((out / "structure-plan/structure-plan.geojson").read_text(encoding="utf-8"))["features"]
    centre = next(shape(f["geometry"]).centroid for f in feats if f["properties"]["kind"] == "centre")
    section(site_dir, out, "--massing", "--at", f"{centre.x},{centre.y}")
    d = out / "site-section"
    for f in ["site-section_design_1-3000.svg", "site-section_design_1-3000.png",
              "site-section_design_excerpt_1-1000.svg", "site-section_design_excerpt_1-1000.png"]:
        assert (d / f).exists(), f
    c = cut(out)
    assert c["new_cut"] + c["new_behind"] >= 1, c


@needs_tif
def test_section_given_line(tmp_path):
    out = tmp_path / "with space" / "2026-01-01_t"
    site, to_m, to_ll = site_utm(SITE)
    p = site.representative_point()
    a, b = to_ll(p.x - 300, p.y), to_ll(p.x + 300, p.y)
    section(SITE, out, "--line", f"{a[0]},{a[1]}", f"{b[0]},{b[1]}")
    rows = profile(out)
    first = Point(to_m(float(rows[0]["lon"]), float(rows[0]["lat"])))
    last = Point(to_m(float(rows[-1]["lon"]), float(rows[-1]["lat"])))
    line = LineString([first, last])
    ts = [line.project(Point(c)) for q in getattr(line.intersection(site), "geoms", [line.intersection(site)])
          for c in q.coords]
    assert abs(min(ts) - 200) <= 1, min(ts)
    assert abs(line.length - max(ts) - 200) <= 1, line.length - max(ts)


def test_terrain_fallback_flat(tmp_path):
    root = tmp_path / "with space"
    site_dir = root / "site"
    shutil.copytree(SITE, site_dir, ignore=shutil.ignore_patterns("*.tif", "*.tiff", "terrain.csv"))
    kit = json.loads((site_dir / "kit.json").read_text(encoding="utf-8"))
    kit.pop("terrain", None)
    (site_dir / "kit.json").write_text(json.dumps(kit), encoding="utf-8")
    out = root / "proposals" / "2026-01-01_t"
    r = section(site_dir, out, env={"SECTION_NO_NETWORK": "1"})
    assert r.returncode == 0
    assert {row["source"] for row in profile(out)} == {"flat (no terrain found)"}
    assert "flat" in (out / "site-section/assumptions.md").read_text(encoding="utf-8")
