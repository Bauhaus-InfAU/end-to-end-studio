"""open-space's pedestrian layer on synthetic shapes: a street end at a park reaches the park path, a footbridge is
built only over a real barrier and joins two path nodes, wide water is not crossed, and two parks are joined by one
promenade, not a fan of lines."""
import importlib.util, json

from shapely.geometry import LineString, Point, Polygon, box, mapping
from shapely.ops import unary_union

from conftest import REPO

spec = importlib.util.spec_from_file_location("open_space", REPO / "plugins/design/skills/open-space/scripts/open_space.py")
OS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OS)
CFG = {k: v[0] for k, v in OS.DEFAULTS.items()}
SITE = box(0, 0, 1000, 1000)
NONE = Polygon()


def streets(tmp_path, feats):
    """a streets.geojson in local metres (the test's m() leaves them as they are)"""
    p = tmp_path / "streets.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": pr, "geometry": mapping(g)} for g, pr in feats]}), encoding="utf-8")
    return str(p)


def walk(tmp_path, feats, loops, parks, water=NONE, rail=NONE, wet=NONE, buildings=NONE, keep_free=None):
    return OS.walk_network(CFG, streets(tmp_path, feats), lambda g: g, loops, [], parks, buildings, water, rail, wet,
                           SITE, keep_free)


PARK = box(300, 300, 700, 700)
LOOP = LineString(box(320, 320, 680, 680).exterior.coords)


def test_street_end_at_a_park_reaches_the_park_path(tmp_path):
    end = Point(500, 290)                                    # a street ends 10 m short of the park, 30 m from its loop
    street = LineString([(500, 100), (500, 290)]).buffer(5, cap_style=2)
    out = walk(tmp_path, [(street, {"kind": "street"}), (end, {"kind": "street-end", "type": "turning head"})],
               [LOOP], [PARK])
    assert out["entrances"] == [(end, True)]
    assert len(out["connections"]) == 1 and not out["bridges"]
    piece = out["connections"][0][0]
    assert piece.distance(end) < 0.01 and piece.distance(LOOP) < 0.01   # it really joins the end to the loop


def test_footbridge_only_over_water_and_joining_two_path_nodes(tmp_path):
    path = LineString([(500, 150), (500, 275)])              # a loose path end at (500, 275), near the park
    water = box(250, 280, 750, 300)                          # 20 m of water between it and the park's loop at y 320
    out = walk(tmp_path, [(path, {"kind": "path"})], [LOOP], [PARK], water=water)
    assert len(out["bridges"]) == 1 and out["bridges"][0][1] == "water"
    bridge = out["bridges"][0][0]
    assert abs(bridge.length - 20) < 0.5
    rest = unary_union([path, LOOP] + [g for g, _ in out["connections"]])
    assert all(rest.distance(Point(c)) < 0.5 for c in (bridge.coords[0], bridge.coords[-1]))   # both ends on paths
    out = walk(tmp_path, [(path, {"kind": "path"})], [LOOP], [PARK])                           # no water, no bridge
    assert not out["bridges"] and len(out["connections"]) == 1


def test_wide_water_is_not_crossed(tmp_path):
    path = LineString([(500, 150), (500, 275)])
    water = box(250, 280, 750, 318)                          # 38 m: wider than bridge_max_m
    out = walk(tmp_path, [(path, {"kind": "path"})], [LOOP], [PARK], water=water)
    assert not out["bridges"] and not out["connections"]


def test_footbridge_over_the_railway_and_not_through_a_building(tmp_path):
    path = LineString([(500, 200), (500, 275)])
    rail = LineString([(0, 290), (1000, 290)])
    out = walk(tmp_path, [(path, {"kind": "path"})], [LOOP], [PARK], rail=rail)
    assert [c for _, c in out["bridges"]] == ["railway"]
    out = walk(tmp_path, [(path, {"kind": "path"})], [LOOP], [PARK], rail=rail, buildings=box(490, 280, 510, 300))
    assert not out["bridges"] and not out["connections"]


def test_two_parks_get_one_promenade_not_a_fan(tmp_path):
    west, east = box(100, 300, 400, 700), box(440, 300, 740, 700)      # 40 m apart, a street between
    lw, le = LineString(box(120, 320, 380, 680).exterior.coords), LineString(box(460, 320, 720, 680).exterior.coords)
    halves = [LineString(list(lw.coords)[:3]), LineString(list(lw.coords)[2:])]   # a loop cut in two pieces
    out = walk(tmp_path, [], halves + [le], [west, east])
    assert len(out["promenades"]) == 1
    assert abs(out["promenades"][0][0].length - 80) < 1                           # the shortest join, 380 -> 460
