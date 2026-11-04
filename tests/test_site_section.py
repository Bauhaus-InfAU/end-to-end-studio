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
    # the ground behind the cut is drawn, so buildings behind stand on it; the far landscape only on the whole cut
    whole, part = (d / "site-section_1-3000.svg").read_text(encoding="utf-8"), (d / "site-section_excerpt_1-1000.svg").read_text(encoding="utf-8")
    assert whole.count('class="ground-behind"') == len(c["ground_behind_m"]) > 0
    assert part.count('class="ground-behind"') == len(c["ground_behind_m"])
    assert whole.count('class="landscape"') >= len(c["landscape_m"]) and 'class="landscape"' not in part


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
    assert cut(out)["landscape_m"] == []   # flat ground: no landscape lines behind


def gable(x0, y0, w=10, d=8, eaves=6, ridge=10):
    """The two roof faces of a house w wide in x and d deep in y, its ridge along y; z above its ground."""
    xm = x0 + w / 2
    return [[(x0, y0, eaves), (xm, y0, ridge), (xm, y0 + d, ridge), (x0, y0 + d, eaves)],
            [(xm, y0, ridge), (x0 + w, y0, eaves), (x0 + w, y0 + d, eaves), (xm, y0 + d, ridge)]]


def test_roof_cut_across_ridge():
    sys.path.insert(0, str(SECTION.parent))
    import numpy as np, roofs
    faces = [np.array(f, float) for f in gable(0, 0)]
    e, V = np.array([1.0, 0.0]), np.array([0.0, 1.0])
    prof = roofs.cut(faces, np.array([-5.0, 4.0]), e, V, 5, 15)   # t = x + 5
    assert prof == [(5, 6), (10, 10), (15, 6)], prof
    assert roofs.pitched(prof)
    assert not roofs.pitched(roofs.cut(faces, np.array([5.0, -5.0]), V, -e, 5, 13))   # along the ridge: flat


def test_section_pitched_roof_and_flat_top(tmp_path):
    """On a made-up flat site: a gable house with a model is cut pitched, a house without one has a flat top."""
    site_dir, out = tmp_path / "site", tmp_path / "proposals" / "2026-01-01_t"
    site_dir.mkdir(parents=True)
    to_ll = pyproj.Transformer.from_crs(32632, 4326, always_xy=True).transform
    X0, Y0 = 500000.0, 5500000.0
    ll = lambda pts: [list(to_ll(X0 + p[0], Y0 + p[1])) + list(p[2:]) for p in pts]
    ring = lambda pts: ll(list(pts) + [pts[0]])
    fc = lambda feats: json.dumps({"type": "FeatureCollection", "features": feats})
    poly = lambda pts, **p: {"type": "Feature", "properties": p, "geometry": {"type": "Polygon", "coordinates": [ring(pts)]}}
    (site_dir / "site.geojson").write_text(fc([poly([(-20, -20), (60, -20), (60, 30), (-20, 30)])]))
    (site_dir / "buildings.geojson").write_text(fc([
        poly([(0, 0), (10, 0), (10, 8), (0, 8)], id="house", height=10, floors=2),
        poly([(30, 0), (40, 0), (40, 8), (30, 8)], id="shed", height=7, floors=2)]))
    walls = [poly([(0, 0, 0), (10, 0, 0), (10, 0, 6), (0, 0, 6)], id="house", surface="wall")]
    (site_dir / "buildings-3d.geojson").write_text(
        fc(walls + [poly(f, id="house", surface="roof") for f in gable(0, 0)]))
    a, b = to_ll(X0 - 100, Y0 + 4), to_ll(X0 + 140, Y0 + 4)
    section(site_dir, out, "--line", f"{a[0]},{a[1]}", f"{b[0]},{b[1]}", env={"SECTION_NO_NETWORK": "1"})
    roofs_ = cut(out)["roofs"]
    assert roofs_["cut"] == {"from_model": 1, "pitched": 1, "flat_no_model": 1}, roofs_


def test_section_story_strip(tmp_path):
    """On a made-up flat site, the design pass in the panels' frame: the structure plan's areas as bands, the narrative's
    principles as notes on the line (one at its zone, one spread and illustrative), the drawing the frame's size."""
    site_dir, out = tmp_path / "site", tmp_path / "proposals" / "2026-01-01_t"
    for d in ("structure-plan", "massing", "narrative", "panel-layout", "site-section"):
        (out / d).mkdir(parents=True)
    site_dir.mkdir()
    to_ll = pyproj.Transformer.from_crs(32632, 4326, always_xy=True).transform
    X0, Y0 = 500000.0, 5500000.0
    ring = lambda pts: [list(to_ll(X0 + x, Y0 + y)) for x, y in list(pts) + [pts[0]]]
    fc = lambda feats: json.dumps({"type": "FeatureCollection", "features": feats})
    poly = lambda pts, **p: {"type": "Feature", "properties": p, "geometry": {"type": "Polygon", "coordinates": [ring(pts)]}}
    rect = lambda x0, x1: [(x0, -50), (x1, -50), (x1, 50), (x0, 50)]
    (site_dir / "site.geojson").write_text(fc([poly(rect(0, 600))]))
    (site_dir / "buildings.geojson").write_text(fc([]))
    (out / "structure-plan/structure-plan.geojson").write_text(fc([
        poly(rect(0, 300), kind="neighbourhood", name="Low Rows"), poly(rect(300, 600), kind="green", name="Long Field", field=True)]))
    (out / "massing/massing.geojson").write_text(fc([poly([(100, -10), (140, -10), (140, 10), (100, 10)], kind="building", floors=5)]))
    (out / "narrative/narrative.md").write_text("# N\n\n## Principles\n\n1. **The field stays open:** all of it.\n"
                                                "2. **Short ways:** everyone walks.\n\n## Storyline\n\n- not a note\n", encoding="utf-8")
    (out / "panel-layout/layout-plan.json").write_text(json.dumps({"panels": [{"items": [
        {"file": "site-section/site-section_design_1-3000.svg", "frame": {"w": 300, "h": 30}}]}]}))
    (out / "site-section/notes.json").write_text(json.dumps([{"text": "The field stays open", "zone": "Long Field"},
                                                             {"text": "Short ways"}]))
    a, b = to_ll(X0 - 50, Y0), to_ll(X0 + 650, Y0)
    line = ("--massing", "--line", f"{a[0]},{a[1]}", f"{b[0]},{b[1]}")
    section(site_dir, out, *line, "--notes", out / "site-section/notes.json", env={"SECTION_NO_NETWORK": "1"})
    c = cut(out)
    assert c["frame_mm"]["whole"] == [300, 30] and [z[2] for z in c["zones"]] == ["Low Rows", "Long Field"], c
    assert [n[1:] for n in c["notes"]] == [["The field stays open", "at its zone"], ["Short ways", "illustrative"]], c["notes"]
    assert abs(c["notes"][0][0] - (450 + c["beyond_m"])) < 0.2   # in the middle of its zone
    svg = out / "site-section/site-section_design_1-3000.svg"
    s = svg.read_text(encoding="utf-8")
    assert 'width="300.0mm" height="30.0mm"' in s and "Key plan" not in s
    assert s.count('class="zone"') == 2 and s.count('class="note"') == 2 and 'class="idea-line"' in s
    assert "Low Rows" in s and "The field stays open" in s
    ok, why = text_sizes_ok(svg)
    assert ok, why
    # by default the notes are the narrative's principles, each placed by the drawing
    section(site_dir, out, *line, env={"SECTION_NO_NETWORK": "1"})
    assert [n[1:] for n in cut(out)["notes"]] == [["The field stays open", "illustrative"], ["Short ways", "illustrative"]]
