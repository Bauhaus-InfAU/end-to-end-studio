"""The structure plan's scripts: the frame builds a design file, stops on bad values, warns on a centre that holds
nothing, and the tracer places a picture on the site."""
import json, math, os, subprocess, sys
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
    assert {"neighbourhood", "centre", "green", "route", "gateway"} <= kinds <= {"neighbourhood", "centre", "green", "route", "gateway", "existing"}
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


# ---------------------------------------------------------------- the checks that warn, on a made-up site
UTM, E0, N0 = 32633, 500000.0, 5430000.0          # the made-up site: 600 x 600 m, its south-west corner at (E0, N0)
TO_LL = pyproj.Transformer.from_crs(UTM, 4326, always_xy=True).transform


def fc(feats):
    return json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": p, "geometry": transform(lambda x, y, z=None: TO_LL(x + E0, y + N0), g).__geo_interface__}
        for p, g in feats]})


def made_site(d, buildings=(), streets=(), rail=(), terrain=None):
    """A site folder in local metres: a 600 m square, its layers, and a terrain.csv from a function z(x, y)."""
    from shapely.geometry import box as sbox
    d.mkdir(parents=True)
    (d / "site.geojson").write_text(fc([({"name": "site"}, sbox(0, 0, 600, 600))]), encoding="utf-8")
    for name, feats in (("buildings", buildings), ("streets", streets), ("rail", rail), ("plots", ()), ("water", ())):
        (d / f"{name}.geojson").write_text(fc(feats), encoding="utf-8")
    if terrain:
        rows = ["lon,lat,ele"]
        for x in range(-150, 751, 25):
            for y in range(-150, 751, 25):
                lon, lat = TO_LL(x + E0, y + N0)
                rows.append(f"{lon:.7f},{lat:.7f},{terrain(x, y):.2f}")
        (d / "terrain.csv").write_text("\n".join(rows), encoding="utf-8")
    return d


def checks_of(tmp_path, design_text, **site):
    site_dir = made_site(tmp_path / "site", **site)
    prop = tmp_path / "proposal"
    prop.mkdir()
    design = prop / "design.py"
    design.write_text(design_text, encoding="utf-8")
    r = run(SCRIPTS / "build.py", design, "--site", site_dir, "--proposal", prop)
    assert r.returncode == 0, r.stderr[-2000:]
    return prop, (prop / "structure-plan" / "checks.txt").read_text(encoding="utf-8")


PLAN = """
F.add('neighbourhood', 'North', F.box(0, 300, 600, 600), 'new', 'hypothesis', 'test')
F.add('centre', 'Square', F.box(280, 280, 320, 320), 'new', 'hypothesis', 'test', level='main', holds='shops')
"""


def test_first_phase_too_small_warns(tmp_path):
    design = PLAN + "F.add('neighbourhood', 'South', F.box(0, 0, 100, 250), 'new', 'hypothesis', 'test', phase=1)\n"
    prop = tmp_path / "proposal"
    (prop / "programme").mkdir(parents=True)
    (prop / "programme" / "programme.csv").write_text(
        "use,homes,source\nHousing,2000,p. 3\nHousing phase 1 (minimum),1000,p. 4\n", encoding="utf-8")
    site_dir = made_site(tmp_path / "site")
    (prop / "design.py").write_text(design, encoding="utf-8")
    r = run(SCRIPTS / "build.py", prop / "design.py", "--site", site_dir, "--proposal", prop)
    assert r.returncode == 0, r.stderr[-2000:]
    checks = (prop / "structure-plan" / "checks.txt").read_text(encoding="utf-8")
    assert "1,000 of 2,000 homes in the first phase = 50 %" in checks
    assert "warning: the first phase has 12 % of the land" in checks     # 2.5 ha of 20.5 ha


def test_route_over_kept_building_warns(tmp_path):
    from shapely.geometry import box as sbox, LineString as L
    design = PLAN + ("F.add('route', 'Spine', F.line([(150, 0), (150, 600)]), 'new', 'hypothesis', 'test', level='main')\n"
                     "F.add('route', 'Old lane', F.line([(450, 0), (450, 280)]), 'keep', 'mapped', 'test', level='local')\n")
    prop, checks = checks_of(tmp_path, design,
                             buildings=[({"id": "b1", "building": "sports_centre"}, sbox(140, 100, 170, 130)),
                                        ({"id": "b2", "building": "house"}, sbox(456, 100, 470, 115)),
                                        ({"id": "b3", "building": "house"}, sbox(140, 400, 170, 430))],
                             streets=[({"id": "s1", "highway": "residential", "name": "Old lane"}, L([(450, -10), (450, 280)]))])
    line = next(l for l in checks.splitlines() if "warning: Spine" in l)
    assert "b1 sports_centre" in line and "b3" not in line      # b3 stands on a new neighbourhood: not kept
    assert "warning: Old lane" not in checks                    # b2 is beside an existing street: left out


def test_route_on_footway_warns(tmp_path):
    from shapely.geometry import LineString as L
    design = PLAN + ("F.add('route', 'Underpass', F.line([(100, 50), (100, 250)]), 'keep', 'mapped', 'test', level='local')\n"
                     "F.add('route', 'Crossing', F.line([(400, 50), (400, 250)]), 'new', 'hypothesis', 'test', level='main')\n")
    prop, checks = checks_of(tmp_path, design,
                             streets=[({"id": "f1", "highway": "footway", "name": ""}, L([(100, 40), (100, 260)])),
                                      ({"id": "s1", "highway": "residential", "name": "Bridge road"}, L([(410, 100), (410, 200)]))],
                             rail=[({"id": "r1", "railway": "rail"}, L([(-10, 150), (610, 150)]))])
    assert "routes on foot or cycle ways (along them, or through a crossing that is not a street): 1" in checks
    line = next(l for l in checks.splitlines() if "warning: Underpass" in l)
    assert "runs along existing foot or cycle ways" in line and "only crossing is a footway" in line
    assert "landscape" in line


def test_green_on_low_ground(tmp_path):
    design = PLAN + ("F.add('green', 'Valley', F.box(280, 0, 320, 250), 'new', 'hypothesis', 'test', roles=['water'])\n"
                     "F.add('green', 'Ridge', F.box(0, 0, 40, 250), 'new', 'hypothesis', 'test', roles=['rain', 'ecology'])\n"
                     "F.add('green', 'Lawn', F.box(500, 0, 540, 250), 'new', 'hypothesis', 'test', roles=['recreation'])\n")
    prop, checks = checks_of(tmp_path, design, terrain=lambda x, y: 300 - 20 * math.cos(2 * math.pi * (x - 300) / 560))   # valley at x 300, hill at 20
    lines = checks.splitlines()
    valley = next(l for l in lines if l.strip().startswith("Valley") and "low ground" in l)
    ridge = next(l for l in lines if l.strip().startswith("Ridge") and "low ground" in l)
    assert "warning" not in valley and "warning" in ridge
    assert not any(l.strip().startswith("Lawn") and "low ground" in l for l in lines)
    prop, checks = checks_of(tmp_path / "flat", design)
    assert "no terrain model in the site folder" in checks


def test_loose_route_end_is_short(tmp_path):
    design = PLAN + ("F.add('route', 'Stub', F.line([(100, 600), (100, 420)]), 'new', 'hypothesis', 'test', level='local')\n"
                     "F.add('route', 'Through', F.line([(300, 300), (300, 600)]), 'new', 'hypothesis', 'test', level='main')\n")
    prop, checks = checks_of(tmp_path, design)
    line = next(l for l in checks.splitlines() if "loose ends" in l)
    assert line.rstrip().endswith("SHORT: lead each on to a street, a centre or the site edge") and ": 1" in line
    assert "Stub ends at (100,420)" in checks and "Through ends" not in checks   # Through runs from the square to the edge


def test_existing_buildings_need_a_decision(tmp_path):
    from shapely.geometry import box as sbox, LineString as L
    houses = [({"id": "b1", "building": "farm"}, sbox(100, 400, 120, 420)),
              ({"id": "b2", "building": "barn"}, sbox(500, 500, 530, 530)),
              ({"id": "b3", "building": "house"}, sbox(100, 100, 120, 120))]     # b3 is not on new land
    prop, checks = checks_of(tmp_path, PLAN, buildings=houses)
    assert "on changed land: 2; kept: 0; demolished: 0" in checks
    line = next(l for l in checks.splitlines() if "undecided" in l)
    assert ": 2" in line and "SHORT" in line
    design = PLAN + ("F.add('existing', 'Farm', F.box(95, 395, 125, 425), 'keep', 'mapped', 'test', reason='a use worth keeping')\n"
                     "F.add('existing', 'Barn', F.box(495, 495, 535, 535), 'demolish', 'mapped', 'test', reason='in the way')\n")
    prop, checks = checks_of(tmp_path / "decided", design, buildings=houses)
    assert "on changed land: 2; kept: 1; demolished: 1" in checks
    assert "undecided: 0" in checks and "Barn: demolish 1 building(s), because in the way" in checks
    line = next(l for l in checks.splitlines() if "kept but more than" in l)
    assert ": 1" in line and "SHORT" in line and "b1" in checks          # no street or route reaches the farm
    reached = design + "F.add('route', 'Farm lane', F.line([(110, 600), (110, 425)]), 'new', 'hypothesis', 'test', level='local')\n"
    prop, checks = checks_of(tmp_path / "reached", reached, buildings=houses)
    line = next(l for l in checks.splitlines() if "kept but more than" in l)
    assert line.rstrip().endswith(": 0")


def test_demolish_without_reason_stops(tmp_path):
    design = PLAN + "F.add('existing', 'Barn', F.box(495, 495, 535, 535), 'demolish', 'mapped', 'test')\n"
    site_dir = made_site(tmp_path / "site")
    prop = tmp_path / "proposal"; prop.mkdir()
    (prop / "design.py").write_text(design, encoding="utf-8")
    r = run(SCRIPTS / "build.py", prop / "design.py", "--site", site_dir, "--proposal", prop)
    assert r.returncode != 0 and "say why" in r.stderr
    (prop / "design.py").write_text(PLAN + "F.add('existing', 'Barn', F.box(495, 495, 535, 535), 'new', 'mapped', 'test', reason='x')\n",
                                    encoding="utf-8")
    r = run(SCRIPTS / "build.py", prop / "design.py", "--site", site_dir, "--proposal", prop)
    assert r.returncode != 0 and "keep, demolish" in r.stderr


def test_demolishing_what_the_analysis_keeps_is_short(tmp_path):
    from shapely.geometry import box as sbox
    barn = sbox(500, 500, 530, 530)
    design = PLAN + "F.add('existing', 'Barn', F.box(495, 495, 535, 535), 'demolish', 'mapped', 'test', reason='in the way')\n"
    prop, checks = checks_of(tmp_path, design, buildings=[({"id": "b2", "building": "barn"}, barn)])
    assert "the analysis keeps them" not in checks                  # no keep list: nothing to compare with
    (prop / "analysis").mkdir()
    (prop / "analysis/keep.geojson").write_text(fc([({"layer": "buildings", "reason": "third parties' property"}, barn)]), encoding="utf-8")
    r = run(SCRIPTS / "build.py", prop / "design.py", "--site", tmp_path / "site", "--proposal", prop)
    assert r.returncode == 0, r.stderr[-2000:]
    line = next(l for l in (prop / "structure-plan/checks.txt").read_text(encoding="utf-8").splitlines() if "the analysis keeps them" in l)
    assert ": 1" in line and "SHORT" in line and "third parties' property" in line
