"""The structure plan's scripts: the frame builds a design file, stops on bad values, warns on a centre that holds
nothing, and the tracer places a picture on the site."""
import json, os, subprocess, sys
from pathlib import Path
import pyproj
from shapely.geometry import shape
from shapely.ops import transform
from conftest import REPO

SITE = REPO / "competition/site"
SCRIPTS = REPO / "plugins/concept/skills/structure-plan/scripts"


def run(script, *args):
    return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})


def build(tmp_path, design_text):
    prop = tmp_path / "with space" / "2026-01-01_t"
    prop.mkdir(parents=True)
    design = prop / "design.py"
    design.write_text(design_text, encoding="utf-8")
    return prop, run(SCRIPTS / "build.py", design, "--site", SITE, "--proposal", prop)


BASE = """
c = F.site.representative_point()
F.add('neighbourhood', 'Field', F.box(c.x - 150, c.y - 150, c.x + 150, c.y + 150).intersection(F.site), {action!r},
      'hypothesis', 'test')
F.add('centre', 'Square', F.box(c.x - 30, c.y - 30, c.x + 30, c.y + 30), 'new', 'hypothesis', 'test',
      level={level!r}{holds})
"""


def test_example_design_builds(tmp_path):
    prop, r = build(tmp_path, (SCRIPTS / "design.example.py").read_text(encoding="utf-8"))
    assert r.returncode == 0, r.stderr[-2000:]
    out = prop / "structure-plan"
    kinds = {f["properties"]["kind"] for f in
             json.loads((out / "structure-plan.geojson").read_text(encoding="utf-8"))["features"]}
    assert kinds == {"neighbourhood", "centre", "green", "route", "gateway"}
    checks = (out / "checks.txt").read_text(encoding="utf-8")
    lines = checks.splitlines()
    for head in ("NEIGHBOURHOODS", "GREEN", "CENTRES"):
        assert head in lines, head
    assert "share" in checks
    assert (out / "check-plan.png").exists()


def test_bad_action_stops(tmp_path):
    prop, r = build(tmp_path, BASE.format(action="maybe", level="main", holds=", holds='shops'"))
    assert r.returncode != 0
    assert "maybe" in r.stderr


def test_centre_without_holds_warns(tmp_path):
    prop, r = build(tmp_path, BASE.format(action="new", level="main", holds=""))
    assert r.returncode == 0, r.stderr[-2000:]
    assert "says nothing it holds" in r.stdout


def test_no_main_centre_stops(tmp_path):
    prop, r = build(tmp_path, BASE.format(action="new", level="local", holds=", holds='shops'"))
    assert r.returncode != 0
    assert "main centre" in r.stderr


def test_georef_fit(tmp_path):
    from PIL import Image, ImageDraw
    d = tmp_path / "with space"
    d.mkdir()
    img = Image.new("RGB", (200, 200), "white")
    ImageDraw.Draw(img).rectangle([50, 50, 149, 149], fill=(220, 30, 30))
    img.save(d / "plan.png")
    site = shape(json.loads((SITE / "site.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
    c = site.centroid
    epsg = (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform
    x0, y0, x1, y1 = transform(to_m, site).bounds
    s = min(x1 - x0, y1 - y0)                           # the picture covers a square of the site's bounds, 1 px = s/200 m
    corners = [((0, 0), (x0, y0 + s)), ((200, 0), (x0 + s, y0 + s)), ((0, 200), (x0, y0))]
    pts = [{"px": list(px), "lonlat": list(to_ll(X, Y)), "what": f"corner {i}"} for i, (px, (X, Y)) in enumerate(corners)]
    (d / "points.json").write_text(json.dumps(pts), encoding="utf-8")
    (d / "colours.json").write_text(json.dumps({"red": {"min": [180, 0, 0], "max": [255, 80, 80]}}), encoding="utf-8")
    out = d / "structure-plan" / "traced.geojson"
    r = run(SCRIPTS / "georef.py", "--site", SITE, "--image", d / "plan.png", "--points", d / "points.json",
            "--out", out, "--colours", d / "colours.json")
    assert r.returncode == 0, r.stderr[-2000:]
    md = (out.parent / "georef.md").read_text(encoding="utf-8")
    res = [float(line.rsplit(": ", 1)[1].split()[0]) for line in md.splitlines() if line.startswith("- corner")]
    assert len(res) == 3 and max(res) < 1, md
    red = [f for f in json.loads(out.read_text(encoding="utf-8"))["features"] if f["properties"].get("colour") == "red"]
    assert len(red) == 1
    side = 100 * s / 200
    assert 0.9 * side ** 2 < red[0]["properties"]["area_m2"] < 1.05 * side ** 2
