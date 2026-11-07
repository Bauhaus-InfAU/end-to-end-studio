"""The plans skill draws the site plan, a detail area and the figure-ground from the design layers, fitted to the panel."""
import json, os, re, shutil, subprocess, sys
import pytest
import pyproj
from shapely.geometry import shape, mapping, box
from shapely.ops import transform
from conftest import REPO
from synthetic import make_proposal

PLANS = REPO / "plugins/drawings/skills/plans/scripts/plans.py"
MASSING = REPO / "plugins/design/skills/massing/scripts/massing.py"
CONFIG = {"site_plan_scale": 3000, "figure_ground_scale": 15000, "storeys_on_site_plan": True,
          "panel_width_mm": 594, "panel_height_mm": 841, "margin_mm": 15,
          "detail_areas": [{"name": "detail-area-1", "scale": 1000, "at": "Square"}]}
FILES = ["site-plan_1-3000", "detail-area-1_1-1000", "figure-ground_1-15000"]


def run(script, *args, check=True):
    r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONUTF8": "1"})   # the scripts write their text as UTF-8 on Windows too
    if check and r.returncode:
        raise AssertionError(r.stderr[-2000:])
    return r


def write_config(out, cfg):
    path = out / "plans/config.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({k: {"value": v, "source": "test"} for k, v in cfg.items()}), encoding="utf-8")
    return path


def draw(out, site_dir, cfg=CONFIG, check=True):
    return run(PLANS, "--proposal", out, "--site", site_dir, "--config", write_config(out, cfg),
               "--style", out / "drawing-graphics/style.json", check=check)


@pytest.fixture(scope="module")
def drawn(tmp_path_factory):
    """The synthetic proposal with its massing and plans drawn: (proposal, site folder). No streets/ or open-space/."""
    root = tmp_path_factory.mktemp("plans") / "with space"
    out = make_proposal(root)
    site_dir = root / "site"
    run(MASSING, "--proposal", out, "--site", site_dir, "--config", out / "massing/config.json")
    draw(out, site_dir)
    return out, site_dir


def mm(svg, attr):
    return float(re.search(r'<svg[^>]*\b%s="([\d.]+)mm"' % attr, svg).group(1))


def test_plans_draws_the_three_kinds(drawn):
    out, _ = drawn
    for f in FILES:
        for ext in (".svg", ".png"):
            assert (out / "plans" / (f + ext)).exists(), f + ext
    made = json.loads((out / "plans/drawings.json").read_text(encoding="utf-8"))
    assert len(made) == 3
    assert all(e["fits"] for e in made), made
    assert "streets" not in made[0]["layers_used"] and any("streets" in m for m in made[0]["layers_missing"])


def test_plans_fit_the_panel(drawn):
    out, _ = drawn
    made = {e["file"]: e for e in json.loads((out / "plans/drawings.json").read_text(encoding="utf-8"))}
    for f in FILES:
        svg = (out / "plans" / (f + ".svg")).read_text(encoding="utf-8")
        assert mm(svg, "width") <= 594 - 2 * 15 + 0.5, f
        assert mm(svg, "height") <= 841 - 2 * 15 + 0.5, f                 # the map with its legend strip
        assert made[f + ".svg"]["map_height_mm"] <= 841 - 2 * 15 - 60 + 0.5, f   # the map leaves room for a caption


def test_plans_text_floor(drawn):
    out, _ = drawn
    for f, scale in zip(FILES, (3000, 1000, 15000)):
        svg = (out / "plans" / (f + ".svg")).read_text(encoding="utf-8")
        sizes = [float(v) for v in re.findall(r'font-size="([\d.]+)"', svg)]
        assert sizes, f
        assert min(sizes) / scale * 1000 >= 3.2 - 1e-6, (f, min(sizes))


def test_plans_white_buildings_shadow_and_public_ground(drawn):
    out, _ = drawn
    style = json.loads((out / "drawing-graphics/style.json").read_text(encoding="utf-8"))
    site_plan = (out / "plans/site-plan_1-3000.svg").read_text(encoding="utf-8")
    assert 'mix-blend-mode:multiply' in site_plan                     # the cast shadow
    assert 'fill="%s"' % style["public"] in site_plan                 # the massing's square in the public tone
    assert 'fill="%s"' % style["accent"] not in site_plan              # the accent is off the buildings
    assert 'mix-blend-mode' not in (out / "plans/figure-ground_1-15000.svg").read_text(encoding="utf-8")


def test_plans_reads_streets_when_present(drawn, tmp_path):
    out, site_dir = drawn
    g = shape(json.loads((site_dir / "site.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
    c = g.centroid
    epsg = (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform
    p = transform(to_m, g).representative_point()
    streets = out / "streets/streets.geojson"
    streets.parent.mkdir(exist_ok=True)
    streets.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"kind": "street", "use": "street", "existing": False, "source": "test"},
         "geometry": mapping(transform(to_ll, box(p.x - 100, p.y - 5, p.x + 100, p.y + 5)))}]}), encoding="utf-8")
    try:
        draw(out, site_dir)
        made = json.loads((out / "plans/drawings.json").read_text(encoding="utf-8"))
        assert "streets" in made[0]["layers_used"]
    finally:
        streets.unlink()
        draw(out, site_dir)   # leave the module's drawings as the other tests expect them


def test_plans_take_their_frames_and_roman_storeys(drawn):
    """A plan the panels' plan frames takes the frame's scale and is drawn to its size, its legend strip included."""
    out, site_dir = drawn
    frames = {"site-plan": ("plans/site-plan_1-3000.svg", "1:3000", 400, 300),
              "detail-area-1": ("plans/detail-area-1_1-500.svg", "1:500", 300, 180)}
    plan = out / "panel-layout/layout-plan.json"
    plan.parent.mkdir(exist_ok=True)
    plan.write_text(json.dumps({"panels": [{"items": [{"id": k, "type": "drawing", "file": f, "scale": s, "frame": {"w": w, "h": h}}
                                                      for k, (f, s, w, h) in frames.items()]}]}), encoding="utf-8")
    style = out / "drawing-graphics/style.json"
    keep = style.read_text(encoding="utf-8")
    style.write_text(json.dumps({**json.loads(keep), "storey_labels": "roman"}), encoding="utf-8")
    try:
        draw(out, site_dir)
        for f, s, w, h in frames.values():
            svg = (out / f).read_text(encoding="utf-8")
            assert abs(mm(svg, "width") - w) <= 0.5 and abs(mm(svg, "height") - h) <= 0.5, (f, mm(svg, "width"), mm(svg, "height"))
        storeys = re.findall(r'text-anchor="middle" fill="[^"]+">([^<]+)</text>', (out / frames["detail-area-1"][0]).read_text(encoding="utf-8"))
        assert storeys and all(re.fullmatch(r"[IVXL]+", s) for s in storeys), storeys
    finally:
        plan.unlink()
        style.write_text(keep, encoding="utf-8")
        draw(out, site_dir)   # leave the module's drawings as the other tests expect them


def test_plans_draw_ground_floors_in_detail_areas_only(drawn):
    """With ground-floor/detail.geojson, a detail area shows the doors and bike stands; the site plan doesn't."""
    out, site_dir = drawn
    gf = out / "ground-floor"
    gf.mkdir()
    (gf / "config.json").write_text(json.dumps({k: {"value": v, "source": "test"} for k, v in
                                                {"bike_stands_per_entrance": 4, "play_m2": 100, "centre_uses": [], "hubs": []}.items()}),
                                    encoding="utf-8")
    try:
        run(REPO / "plugins/design/skills/ground-floor/scripts/ground_floor.py", "--proposal", out, "--config", gf / "config.json")
        draw(out, site_dir)
        made = {e["name"]: e for e in json.loads((out / "plans/drawings.json").read_text(encoding="utf-8"))}
        detail = (out / "plans/detail-area-1_1-1000.svg").read_text(encoding="utf-8")
        assert "ground-floor" in made["detail-area-1"]["layers_used"] and ">Entrances</text>" in detail
        assert "entrances (ground-floor)" not in made["detail-area-1"]["not_shown"]   # now it has them
        assert "ground-floor" not in made["site-plan"]["layers_used"]
        assert ">Entrances</text>" not in (out / "plans/site-plan_1-3000.svg").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(gf)
        draw(out, site_dir)   # leave the module's drawings as the other tests expect them


def made_of(out):
    return {e["name"]: e for e in json.loads((out / "plans/drawings.json").read_text(encoding="utf-8"))}


def test_plans_name_places_streets_and_detail_areas(drawn):
    """Every plan names its squares; a detail area also its streets; each name once, on a halo."""
    out, _ = drawn
    detail = (out / "plans/detail-area-1_1-1000.svg").read_text(encoding="utf-8")
    site = (out / "plans/site-plan_1-3000.svg").read_text(encoding="utf-8")
    assert re.search(r'font-weight="bold"[^>]*>Square</text>', detail)
    assert ">Main road</text>" in detail                                # the massing's street, by its name
    assert ">Square</text>" in site
    names = re.findall(r'paint-order="stroke">([^<]+)</text>', detail)
    assert len(names) == len(set(names)), names
    assert re.search(r'paint-order="stroke">Detail area 1</text>', site)   # the window's name, on a halo


def test_plans_flag_overlapping_detail_areas(drawn):
    out, site_dir = drawn
    assert "overlaps" not in made_of(out)["detail-area-1"]
    two = {**CONFIG, "detail_areas": CONFIG["detail_areas"] + [{"name": "detail-area-2", "scale": 1000, "at": "Corner"}]}
    try:
        r = draw(out, site_dir, two)
        made = made_of(out)
        assert made["detail-area-2"]["overlaps"][0]["with"] == "detail-area-1"
        assert made["detail-area-1"]["overlaps"][0]["with"] == "detail-area-2"
        assert "another `at`" in r.stderr
    finally:
        for f in (out / "plans").glob("detail-area-2_*"):
            f.unlink()
        draw(out, site_dir)   # leave the module's drawings as the other tests expect them


def test_plans_hatch_public_ground_floors_in_detail_areas_only(drawn):
    out, _ = drawn
    mass = json.loads((out / "massing/massing.geojson").read_text(encoding="utf-8"))["features"]
    assert any(str(f["properties"].get("ground_floor", "housing")) != "housing" for f in mass
               if f["properties"].get("kind") == "building")             # the synthetic massing has some
    detail = (out / "plans/detail-area-1_1-1000.svg").read_text(encoding="utf-8")
    assert 'fill="url(#gf-detail-area-1)"' in detail and ">Ground floors open to the public</text>" in detail
    assert 'fill="url(#gf-site-plan)"' not in (out / "plans/site-plan_1-3000.svg").read_text(encoding="utf-8")


def test_plans_draw_the_idea_or_say_it_is_missing(drawn):
    out, site_dir = drawn
    accent = json.loads((out / "drawing-graphics/style.json").read_text(encoding="utf-8"))["accent"]
    try:
        draw(out, site_dir, {**CONFIG, "idea": {"label": "The green strip", "names": ["Strip"]}})
        site = (out / "plans/site-plan_1-3000.svg").read_text(encoding="utf-8")
        assert made_of(out)["site-plan"]["idea"].startswith("drawn")
        assert ">The green strip</text>" in site and 'stroke="%s"' % accent in site
        assert ">Strip</text>" not in site                                 # named once, as the idea
        draw(out, site_dir, {**CONFIG, "idea": {"label": "Nothing", "names": ["Nowhere"]}})
        assert made_of(out)["site-plan"]["idea"].startswith("missing")
        assert ">Nothing</text>" not in (out / "plans/site-plan_1-3000.svg").read_text(encoding="utf-8")
    finally:
        draw(out, site_dir)   # leave the module's drawings as the other tests expect them


def test_plans_say_what_a_detail_area_cannot_show(drawn):
    """Without ground-floor/, the detail area names the entrances as missing instead of inventing them."""
    out, _ = drawn
    assert "entrances (ground-floor)" in made_of(out)["detail-area-1"]["not_shown"]


def test_plans_missing_required_stops(drawn):
    out, site_dir = drawn
    cfg = {k: v for k, v in CONFIG.items() if k != "site_plan_scale"}
    r = draw(out, site_dir, cfg, check=False)
    assert r.returncode != 0
    assert "site_plan_scale" in r.stderr
    write_config(out, CONFIG)
