"""The scripts the lean run moved into skill folders: they reproduce run-3 and name no site."""
import json, math, re, shutil, subprocess, sys
from pathlib import Path
import pytest
from shapely.geometry import shape
from shapely.ops import transform
import pyproj
from conftest import REPO
sys.path.insert(0, str(Path(__file__).parent))
from synthetic import make_proposal

RUN3 = REPO / "competition/proposals/2026-11-02_run-3"
SITE = REPO / "competition/site"
FIX = Path(__file__).parent / "fixtures"
MASSING = REPO / "plugins/design/skills/massing/scripts"
NEW_SCRIPTS = [MASSING / "massing.py", MASSING / "draw.py"]
NEW_SCRIPTS += [REPO / "plugins/drawings/skills/plans/scripts/plans.py", REPO / "plugins/studio/skills/competition-proposal/scripts/side_by_side.py"]
NEW_SCRIPTS += [REPO / "plugins/studio/skills/competition-proposal/scripts/frames.py"]
NEW_SCRIPTS += [REPO / "plugins/drawings/skills/site-section/scripts" / f for f in ("section.py", "terrain.py")]
NEW_SCRIPTS += [REPO / "plugins/design/skills/mobility/scripts" / f for f in ("mobility.py", "config.example.json")]
NEW_SCRIPTS += [REPO / "plugins/design/skills/phasing/scripts" / f for f in ("phases.py", "phasing.py", "draw.py", "fingerprint.py", "config.example.json", "decisions.example.json")]
NEW_SCRIPTS += [REPO / "plugins/design/skills/ground-floor/scripts" / f for f in ("ground_floor.py", "config.example.json")]
NEW_SCRIPTS += [REPO / "plugins/concept/skills/structure-plan/scripts" / f
                for f in ("frame.py", "build.py", "check.py", "georef.py", "design.example.py")]
FORBIDDEN = re.compile(r"Regensburg|Europan|Pilsenallee|Chamer|Brandlberg|Haslbach|Wutzlhofen|run-3|25832"
                       r"|\b49\.0\d{3}|\b12\.\d{4}|\b[A-Z]:[\\/](?:Users|Work)", re.I)
needs_run3 = pytest.mark.skipif(not RUN3.exists(), reason="run-3 not on this computer")


def copy_run3(dest, skills):
    dest.mkdir(parents=True)
    for s in skills:
        shutil.copytree(RUN3 / s, dest / s)
    return dest


def run(script, *args, check=True):
    r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode:
        raise AssertionError(r.stderr[-2000:])
    return r


def buildings(path):
    F = json.loads(Path(path).read_text(encoding="utf-8"))["features"]
    return [f["properties"] for f in F if f["properties"].get("kind") == "building" and not f["properties"].get("existing")]


def test_no_site_in_new_scripts():
    for p in NEW_SCRIPTS:
        hits = FORBIDDEN.findall(p.read_text(encoding="utf-8"))
        assert not hits, (p.name, hits)


def massing_run(tmp_path, drop=None):
    out = copy_run3(tmp_path / "with space" / "2026-01-01_t", ["structure-plan", "climate", "programme", "narrative"])
    (out / "massing").mkdir()
    cfg = json.loads((FIX / "massing_config_run3.json").read_text(encoding="utf-8"))
    cfg.pop(drop, None)
    (out / "massing/config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return out


@needs_run3
def test_massing_runs_on_run3_inputs(tmp_path):
    out = massing_run(tmp_path)
    run(MASSING / "massing.py", "--proposal", out, "--site", SITE, "--config", out / "massing/config.json")
    run(MASSING / "draw.py", "--proposal", out, "--site", SITE)
    for f in ["areas.csv", "assumptions.md", "massing.svg", "massing.png", "massing_3d.svg", "massing_3d.png"]:
        assert (out / "massing" / f).exists(), f
    cfg = json.loads((out / "massing/config.json").read_text(encoding="utf-8"))
    stats = json.loads((out / "massing/stats.json").read_text(encoding="utf-8"))
    # the homes meet the programme, or the script reports that they don't fit at the height cap
    assert abs(stats["homes"] - cfg["homes_target"]["value"]) / cfg["homes_target"]["value"] <= 0.05 \
        or stats["at_cap"] / stats["n_home"] > 0.5


@needs_run3
def test_massing_missing_key_stops(tmp_path):
    out = massing_run(tmp_path, drop="homes_target")
    r = run(MASSING / "massing.py", "--proposal", out, "--site", SITE, "--config", out / "massing/config.json", check=False)
    assert r.returncode != 0 and "homes_target" in r.stderr


def run_massing(out):
    return run(MASSING / "massing.py", "--proposal", out, "--site", out.parent / "site", "--config", out / "massing/config.json", check=False)


def with_site(out, drop=()):
    site = out.parent / "site"
    shutil.copytree(SITE, site, ignore=shutil.ignore_patterns(*drop))
    return out


@needs_run3
def test_massing_example_config_stops(tmp_path):
    out = with_site(massing_run(tmp_path))
    shutil.copy(MASSING / "config.example.json", out / "massing/config.json")
    r = run_massing(out)
    assert r.returncode != 0 and "height_limit_m" in r.stderr and "homes_target" in r.stderr


@needs_run3
def test_massing_without_school_pool_daycare(tmp_path):
    out = with_site(massing_run(tmp_path))
    cfg = json.loads((out / "massing/config.json").read_text(encoding="utf-8"))
    for k in ["school_gfa", "school_yard", "school_sports", "pool_gfa", "pool_plot", "daycare_gfa", "daycares", "daycare_play"]:
        cfg.pop(k)
    (out / "massing/config.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = run_massing(out)
    assert r.returncode == 0, r.stderr[-1500:]
    uses = {b["use"] for b in buildings(out / "massing/massing.geojson")}
    assert not uses & {"school", "indoor pool"} and not any("daycare" in u for u in uses)


@needs_run3
def test_massing_without_climate_and_water(tmp_path):
    out = with_site(massing_run(tmp_path), drop=("water.geojson",))
    shutil.rmtree(out / "climate")
    r = run_massing(out)
    assert r.returncode == 0, r.stderr[-1500:]


@needs_run3
def test_massing_no_main_centre_stops(tmp_path):
    out = with_site(massing_run(tmp_path))
    sp = out / "structure-plan/structure-plan.geojson"
    sp.write_text(sp.read_text(encoding="utf-8").replace('"level": "main"', '"level": "local"'), encoding="utf-8")
    r = run_massing(out)
    assert r.returncode != 0 and "main centre" in r.stderr


# ---------- on the synthetic proposal: runs on any computer ----------
def synthetic_run(tmp_path, figure=None):
    out = make_proposal(tmp_path / "with space")
    if figure is not None:
        cfg = json.loads((out / "massing/config.json").read_text(encoding="utf-8"))
        cfg["figure"] = {"value": figure, "source": "test"}
        (out / "massing/config.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = run(MASSING / "massing.py", "--proposal", out, "--site", out.parent.parent / "site",
            "--config", out / "massing/config.json", check=False)
    return out, r


def new_buildings_m(out):
    """the new buildings of a run, as (properties, footprint in the projection the script measured in)"""
    G = json.loads((out / "massing/massing.geojson").read_text(encoding="utf-8"))
    B = [(f["properties"], shape(f["geometry"])) for f in G["features"]
         if f["properties"].get("kind") == "building" and not f["properties"].get("existing")]
    epsg = int(re.search(r"EPSG:(\d+)", G["note"]).group(1))   # a bearing is laid out in this grid
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    return [(p, transform(to_m, g)) for p, g in B], to_m


def housing(B):
    """the buildings of the block grid (they carry row and col), not the community buildings on a centre"""
    return [(p, g) for p, g in B if "row" in p]


def sides(g):
    """the two side lengths of a footprint's minimum rotated rectangle, and the long side's bearing (0-180)"""
    c = list(g.minimum_rotated_rectangle.exterior.coords)
    e = sorted([(c[i], c[i + 1]) for i in range(2)], key=lambda s: -math.dist(*s))
    (x0, y0), (x1, y1) = e[0]
    return math.dist(*e[0]), math.dist(*e[1]), math.degrees(math.atan2(x1 - x0, y1 - y0)) % 180


def test_massing_synthetic_default(tmp_path):
    out, r = synthetic_run(tmp_path)
    assert r.returncode == 0, r.stderr[-1500:]
    B, to_m = new_buildings_m(out)
    assert len(B) >= 4
    for i in range(len(B)):
        for j in range(i + 1, len(B)):
            assert B[i][1].intersection(B[j][1]).area < 1, (i, j)
    sp = json.loads((out / "structure-plan/structure-plan.geojson").read_text(encoding="utf-8"))["features"]
    nb = transform(to_m, shape(next(f for f in sp if f["properties"]["kind"] == "neighbourhood")["geometry"]))
    assert all(g.within(nb.buffer(1)) for _, g in B)


def test_massing_figure_rows_bearing(tmp_path):
    out, r = synthetic_run(tmp_path, {"*": {"typology": "rows", "orientation": 30}})
    assert r.returncode == 0, r.stderr[-1500:]
    B, _ = new_buildings_m(out)
    assert len(B) >= 4
    for p, g in housing(B):   # the school now fits on its centre, as the square gives way to what the centre holds
        assert p["type"] == "rows"
        brg = sides(g)[2]
        assert min(abs(brg - 30), 180 - abs(brg - 30)) <= 3, brg


def test_massing_figure_points(tmp_path):
    out, r = synthetic_run(tmp_path, {"*": {"typology": "points"}})
    assert r.returncode == 0, r.stderr[-1500:]
    B, _ = new_buildings_m(out)
    assert len(B) >= 4
    for p, g in housing(B):
        a, b, _ = sides(g)
        assert a / b < 1.6, (a, b)


def test_massing_figure_unknown_stops(tmp_path):
    out, r = synthetic_run(tmp_path, {"*": {"typology": "towers"}})
    assert r.returncode != 0 and "towers" in r.stderr


# ---------- block types made of parts ----------
PART_OF = {"perimeter": "corner", "L": "corner", "U": "wing", "ensemble": "point", "town houses": "town house",
           "tower": "tower", "hub": "garage"}


@pytest.mark.parametrize("typology", list(PART_OF))
def test_massing_block_types(tmp_path, typology):
    out, r = synthetic_run(tmp_path, {"*": {"typology": typology}})
    assert r.returncode == 0, r.stderr[-1500:]
    B, _ = new_buildings_m(out)
    for i in range(len(B)):
        for j in range(i + 1, len(B)):
            assert B[i][1].intersection(B[j][1]).area < 1, (i, j)
    assert all({"block", "part", "roof", "ground_floor"} <= set(p) for p, _ in B)
    G = housing(B)
    assert len({p["block"] for p, _ in G}) < len(G)   # a block is made of several parts
    mine = [p for p, _ in G if p["part"] == PART_OF[typology]]
    assert mine, {p["part"] for p, _ in G}
    if typology == "town houses":
        assert all(p["floors"] <= 3 and p["roof"] == "gable" for p in mine)
    if typology == "tower":
        assert any(p.get("landmark") for p in mine)
    if typology == "hub":
        assert all(p["use"] == "parking" and p["ground_floor"] == "mobility" for p in mine)


# ---------- a mix of block types per neighbourhood ----------
@pytest.mark.parametrize("mix", [["perimeter", "town houses"], {"L": 2, "U": 1}, ["L", "U"]])
def test_massing_mix(tmp_path, mix):
    out, r = synthetic_run(tmp_path, {"*": {"mix": mix}})
    assert r.returncode == 0, r.stderr[-1500:]
    gx = synthetic_layers(out)[3].centroid.x   # col and row count per piece of land: the green splits the field in two
    blocks = {p["block"]: (p["type"], p["col"], p["row"], g.centroid.x < gx) for p, g in housing(new_buildings_m(out)[0])}
    name = {"perimeter": "perimeter block", "town houses": "town houses", "L": "L blocks", "U": "U block"}
    types = [t for t, _, _, _ in blocks.values()]
    assert set(types) == {name[t] for t in mix}, types   # every type of the mix is built, and no other
    if isinstance(mix, dict):   # two L's for each U, give or take a block
        assert abs(types.count("L blocks") - 2 * types.count("U block")) <= 2, types
    at = {(s, c, r): t for t, c, r, s in blocks.values()}
    nxt = [(t, at.get((s, c + 1, r)), at.get((s, c, r + 1))) for (s, c, r), t in at.items()]
    if mix == ["L", "U"]:   # of one depth: neighbours differ
        assert all(t not in (a, b) for t, a, b in nxt), at
    if mix == ["perimeter", "town houses"]:   # of two depths: a row of blocks takes one, the next row the other
        assert all(a in (None, t) and b != t for t, a, b in nxt), at
    stats = json.loads((out / "massing/stats.json").read_text(encoding="utf-8"))
    assert sum(stats["figure"]["Field"]["blocks"].values()) == len(blocks)


def test_massing_mix_unknown_stops(tmp_path):
    out, r = synthetic_run(tmp_path, {"*": {"mix": ["perimeter", "towers"]}})
    assert r.returncode != 0 and "towers" in r.stderr


# ---------- placement: blocks follow the structure plan's routes ----------
def route_run(tmp_path, change):
    """the synthetic run with its structure plan changed by change(features, field bounds, to WGS84) in metres"""
    out = make_proposal(tmp_path / "with space")
    sp = out / "structure-plan/structure-plan.geojson"; fc = json.loads(sp.read_text(encoding="utf-8"))
    c = shape(fc["features"][0]["geometry"]).centroid
    T = pyproj.Transformer.from_crs(4326, (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1, always_xy=True)
    to_ll = lambda *a: T.transform(*a, direction="INVERSE")
    change(fc["features"], transform(T.transform, shape(fc["features"][0]["geometry"])).bounds, to_ll)
    sp.write_text(json.dumps(fc), encoding="utf-8")
    r = run(MASSING / "massing.py", "--proposal", out, "--site", out.parent.parent / "site",
            "--config", out / "massing/config.json", check=False)
    assert r.returncode == 0, r.stderr[-1500:]
    return out, to_ll


def test_massing_follows_the_route_by_default(tmp_path):
    from shapely.geometry import LineString, mapping
    def slant(F, b, to_ll):   # the main road at about 10 degrees to the field's long side
        road = next(f for f in F if f["properties"]["name"] == "Main road")
        road["geometry"] = mapping(transform(to_ll, LineString([(b[0], b[1]), (b[2], b[1] + 80)])))
    out, _ = route_run(tmp_path, slant)
    B, to_m = new_buildings_m(out)
    sp = json.loads((out / "structure-plan/structure-plan.geojson").read_text(encoding="utf-8"))["features"]
    rb = sides(transform(to_m, shape(next(f for f in sp if f["properties"]["name"] == "Main road")["geometry"])).buffer(1))[2]
    brg = [sides(g)[2] for p, g in housing(B) if sides(g)[0] > 1.5 * sides(g)[1]]
    assert brg and all(min((b - rb) % 90, 90 - (b - rb) % 90) <= 3 for b in brg), (rb, brg)   # along the road or across


def test_massing_route_ending_in_the_land_goes_on(tmp_path):
    from shapely.geometry import LineString, Point, mapping
    at = {}
    def lane(F, b, to_ll):   # a local route from the main road that stops in the field
        at["end"] = transform(to_ll, Point(b[0] + 60, b[1] + 120))
        F.append({"type": "Feature", "properties": {"kind": "route", "name": "Lane", "action": "new", "level": "local"},
                  "geometry": mapping(transform(to_ll, LineString([(b[0] + 60, b[1]), (b[0] + 60, b[1] + 120)])))})
    out, _ = route_run(tmp_path, lane)
    F = synthetic_layers(out)[0]   # in the projection the script measured in
    end = transform(new_buildings_m(out)[1], at["end"])
    on = [g for p, g in F if p["kind"] == "street" and p.get("level") == "secondary" and end.distance(g) < 1 and g.length > 40]
    assert on, "no secondary street goes on from the route's end"
    assert all(g.intersection(on[0].buffer(5, cap_style=2)).area < 1 for p, g in F if p["kind"] == "building")


# ---------- heights: a profile per neighbourhood ----------
def heights_run(tmp_path, figure=None, homes=1000, minimum=None):
    """the synthetic run with a figure and a home count; 1000 homes leave room under the cap, so a profile shows"""
    out = make_proposal(tmp_path / "with space")
    cfg = json.loads((out / "massing/config.json").read_text(encoding="utf-8"))
    if figure is not None:
        cfg["figure"] = {"value": figure, "source": "test"}
    if minimum is not None:   # homes_target a minimum (True) or the brief's maximum (False)
        cfg["homes_target_is_minimum"] = {"value": minimum, "source": "test"}
    cfg["homes_target"]["value"] = homes
    (out / "massing/config.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = run(MASSING / "massing.py", "--proposal", out, "--site", out.parent.parent / "site",
            "--config", out / "massing/config.json", check=False)
    return out, r


def centre_gap(tmp_path, figure):
    """mean floors of the third of new buildings nearest the main centre minus that of the farthest third"""
    out, r = heights_run(tmp_path, figure)
    assert r.returncode == 0, r.stderr[-1500:]
    B, to_m = new_buildings_m(out)
    assert len(B) >= 6, len(B)
    sp = json.loads((out / "structure-plan/structure-plan.geojson").read_text(encoding="utf-8"))["features"]
    c = transform(to_m, shape(next(f for f in sp if f["properties"]["kind"] == "centre"
                                   and f["properties"].get("level") == "main")["geometry"]))
    order = sorted(B, key=lambda pg: pg[1].distance(c)); n = len(order) // 3
    near = [p["floors"] for p, _ in order[:n]]; far = [p["floors"] for p, _ in order[-n:]]
    return sum(near) / n - sum(far) / n, B


def test_massing_heights_to_centre(tmp_path):
    flat, _ = centre_gap(tmp_path / "flat", None)
    prof, B = centre_gap(tmp_path / "profile", {"*": {"heights": "to centre", "floors_max": 5}})
    assert prof >= flat + 0.8, (flat, prof)
    assert max(p["floors"] for p, _ in housing(B)) <= 5


def odd_minus_even(tmp_path, figure):
    """per col, mean floors of the odd rows minus that of the even rows, averaged over the cols that have both"""
    out, r = heights_run(tmp_path, figure)
    assert r.returncode == 0, r.stderr[-1500:]
    P = [p for p, _ in housing(new_buildings_m(out)[0])]
    d = []
    for col in {p["col"] for p in P}:
        odd = [p["floors"] for p in P if p["col"] == col and p["row"] % 2]
        even = [p["floors"] for p in P if p["col"] == col and not p["row"] % 2]
        if odd and even:
            d.append(sum(odd) / len(odd) - sum(even) / len(even))
    assert d, "no col with both odd and even rows"
    return sum(d) / len(d)


def test_massing_heights_alternate(tmp_path):
    flat = odd_minus_even(tmp_path / "flat", None)
    alt = odd_minus_even(tmp_path / "profile", {"*": {"heights": "alternate"}})
    # the solver's re-scaling and rounding shrink the one-floor drop to about 0.4 on this input
    assert alt <= flat - 0.3, (flat, alt)


def test_massing_heights_unknown_stops(tmp_path):
    out, r = heights_run(tmp_path, {"*": {"heights": "wavy"}})
    assert r.returncode != 0 and "wavy" in r.stderr


def test_massing_homes_stay_within_the_maximum(tmp_path):
    out, r = heights_run(tmp_path / "min", minimum=True)   # as a minimum the solver ends at or above the target
    assert r.returncode == 0, r.stderr[-1500:]
    s = json.loads((out / "massing/stats.json").read_text(encoding="utf-8"))
    m2 = json.loads((out / "massing/config.json").read_text(encoding="utf-8"))["m2_per_home"]["value"]
    assert s["floors_off_for_max"] == 0
    top = int(s["H_m2"] / m2)   # a maximum just under that: the nearest the floors reach is above it
    out, r = heights_run(tmp_path / "max", homes=top, minimum=False)
    assert r.returncode == 0, r.stderr[-1500:]
    s = json.loads((out / "massing/stats.json").read_text(encoding="utf-8"))
    assert s["H_m2"] <= top * m2 and s["homes"] <= top and s["floors_off_for_max"] > 0, (top, s["H_m2"], s["floors_off_for_max"])
    assert "stay within the maximum" in (out / "massing/assumptions.md").read_text(encoding="utf-8")


def test_massing_assumptions_name_the_cap(tmp_path):
    cfg = json.loads((FIX / "massing_config_run3.json").read_text(encoding="utf-8"))
    out, r = heights_run(tmp_path, homes=2 * cfg["homes_target"]["value"])
    assert r.returncode == 0, r.stderr[-1500:]
    assert "stand at the cap" in (out / "massing/assumptions.md").read_text(encoding="utf-8")


# ---------- streets end on purpose, paths cross the green, trees only in the new land ----------
def synthetic_layers(out):
    """the run's features and the structure plan's, in the projection the script measured in, and the site outline"""
    from shapely.ops import unary_union
    G = json.loads((out / "massing/massing.geojson").read_text(encoding="utf-8"))
    epsg = int(re.search(r"EPSG:(\d+)", G["note"]).group(1))
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    F = [(f["properties"], transform(to_m, shape(f["geometry"]))) for f in G["features"]]
    sp = [(f["properties"], transform(to_m, shape(f["geometry"])))
          for f in json.loads((out / "structure-plan/structure-plan.geojson").read_text(encoding="utf-8"))["features"]]
    site = transform(to_m, shape(json.loads((out.parent.parent / "site/site.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"]))
    green = unary_union([g for p, g in sp if p["kind"] == "green"])
    stats = json.loads((out / "massing/stats.json").read_text(encoding="utf-8"))
    return F, sp, site, green, stats


def test_massing_streets_end_on_purpose(tmp_path):
    from shapely.geometry import Point
    out, r = synthetic_run(tmp_path)
    assert r.returncode == 0, r.stderr[-1500:]
    from shapely.ops import unary_union
    F, sp, site, green, stats = synthetic_layers(out)
    streets = [(p, g) for p, g in F if p["kind"] == "street"]
    centres = unary_union([g for p, g in sp if p["kind"] == "centre"])
    # the buildable land: the neighbourhood minus the green, centres, main and local streets (16 m), water and
    # existing buildings with 4 m around them, as the script excludes them
    nb = next(g for p, g in sp if p["kind"] == "neighbourhood")
    excl = unary_union([green, centres,
                        *[g.buffer(8, cap_style=2) for p, g in sp if p["kind"] == "route" and p["level"] in ("main", "local")],
                        *[g for p, g in F if p["kind"] == "open-space" and p.get("use") == "water"],
                        *[g.buffer(4) for p, g in F if p["kind"] == "building" and p.get("existing")]])
    land = nb.intersection(site).difference(excl)
    for i, (p, g) in enumerate(streets):
        if p.get("level") != "secondary" or p.get("dead_end"):
            continue
        for e in (Point(g.coords[0]), Point(g.coords[-1])):
            assert any(e.distance(h) <= 3 for j, (_, h) in enumerate(streets) if j != i) \
                or e.distance(site.boundary) <= 3 or e.distance(green.boundary) <= 6 \
                or e.distance(centres) <= 3 or e.distance(land.boundary) <= 3, (e.x, e.y)
    assert stats["secondary_dead_ends"] <= 3, stats["street_ends"]
    assert {"centre", "land edge"} & set(stats["street_ends"]), stats["street_ends"]


def test_massing_paths_cross_the_green(tmp_path):
    out, r = synthetic_run(tmp_path)
    assert r.returncode == 0, r.stderr[-1500:]
    F, sp, site, green, stats = synthetic_layers(out)
    assert stats["green_crossings"] >= 1
    assert any(p["kind"] == "street" and p.get("level") == "path" and p.get("note") == "path across the green"
               and g.intersects(green) for p, g in F)


def test_massing_trees_only_in_new_land(tmp_path):
    out, r = synthetic_run(tmp_path)
    assert r.returncode == 0, r.stderr[-1500:]
    F, sp, site, green, stats = synthetic_layers(out)
    nb = next(g for p, g in sp if p["kind"] == "neighbourhood")
    trees = [g for p, g in F if p["kind"] == "tree"]
    assert trees
    assert all(t.within(nb.buffer(16 + 4)) for t in trees)


# ---------- community buildings on the centre that holds them ----------
def community_run(tmp_path, add=None, holds=True):
    out = make_proposal(tmp_path / "with space", holds=holds)
    cfg = json.loads((out / "massing/config.json").read_text(encoding="utf-8"))
    cfg.update(add or {})
    (out / "massing/config.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = run(MASSING / "massing.py", "--proposal", out, "--site", out.parent.parent / "site",
            "--config", out / "massing/config.json", check=False)
    return out, r


def centre_named(sp, name):
    return next(g for p, g in sp if p["kind"] == "centre" and p["name"] == name)


def test_massing_builds_what_the_centre_holds(tmp_path):
    bus = {"use": "bus station", "gfa": 2000, "floors": 2, "ground_m2": 4000, "at": "bus station"}
    out, r = community_run(tmp_path, {"community_buildings": {"value": [bus], "source": "test"}})
    assert r.returncode == 0, r.stderr[-1500:]
    F, sp, site, green, stats = synthetic_layers(out)
    B = [(p, g) for p, g in F if p["kind"] == "building" and not p.get("existing")]
    station = [g for p, g in B if p.get("use") == "bus station"]
    assert len(station) == 1
    assert station[0].within(centre_named(sp, "Square").buffer(1))
    for i in range(len(B)):
        for j in range(i + 1, len(B)):
            assert B[i][1].intersection(B[j][1]).area < 1, (B[i][0].get("use"), B[j][0].get("use"))
    assert any(p["kind"] == "open-space" and p.get("type") == "bus station grounds" for p, g in F)
    assert stats["community"] == {"bus station": True}


def test_massing_school_on_the_centre_that_holds_it(tmp_path):
    out, r = community_run(tmp_path)
    assert r.returncode == 0, r.stderr[-1500:]
    F, sp, site, green, stats = synthetic_layers(out)
    school = [g for p, g in F if p["kind"] == "building" and p.get("use") == "school"]
    assert len(school) == 1
    assert school[0].within(centre_named(sp, "Corner").buffer(1))


def test_massing_without_holds_falls_back(tmp_path):
    # yard and sports small enough for one courtyard block of the synthetic field, so the courtyard logic can run
    small = {k: {"value": 1000, "source": "test"} for k in ("school_yard", "school_sports")}
    out, r = community_run(tmp_path, small, holds=False)
    assert r.returncode == 0, r.stderr[-1500:]
    F, sp, site, green, stats = synthetic_layers(out)
    assert any(p["kind"] == "building" and p.get("use") == "school" for p, g in F)
    assert stats["school_court"] is True
    assert isinstance(stats["warnings"], list)
