"""The ground-floor skill's script: doors on the street side, stands beside them, play in the courtyard, the uses at
the centre with their areas, a hub's bus bays and bike parking, and the massing's file left as it was."""
import csv, json, subprocess, sys
import pyproj
from shapely.geometry import box, mapping, shape, LineString, Point
from shapely.ops import transform
from conftest import REPO

GF = REPO / "plugins/design/skills/ground-floor/scripts/ground_floor.py"
TO_LL = pyproj.Transformer.from_crs(32631, 4326, always_xy=True).transform
TO_M = pyproj.Transformer.from_crs(4326, 32631, always_xy=True).transform


def feature(geom, **props):
    return {"type": "Feature", "properties": props,
            "geometry": mapping(transform(lambda x, y: TO_LL(x + 500000, y + 4980000), geom))}


def local(g):
    return transform(lambda x, y: (x - 500000, y - 4980000), transform(TO_M, shape(g)))


A = box(10, 10, 70, 24)        # a bar 5 m from the street's edge: its doors face south
B = box(10, 60, 70, 74)        # a bar across the courtyard, far from the street: its doors face the path to the north
C = box(110, 10, 160, 40)      # a shop floor of 1,500 m2 at the centre
COURT = box(10, 24, 70, 60)
SQUARE = box(100, 45, 180, 100)
CENTRE = box(100, 6, 180, 44)


def proposal(tmp_path, **cfg):
    out = tmp_path / "with space" / "2026-01-01_t"
    for d in ("structure-plan", "massing", "mobility", "ground-floor"):
        (out / d).mkdir(parents=True)
    massing = [feature(A, kind="building", use="housing", ground_floor="housing", floors=4, footprint_m2=840, block=1),
               feature(B, kind="building", use="housing", ground_floor="housing", floors=4, footprint_m2=840, block=1),
               feature(C, kind="building", use="mixed", ground_floor="commerce", floors=5, footprint_m2=1500, block=2),
               feature(LineString([(0, 0), (200, 0)]), kind="street", width=10, level="local"),
               feature(LineString([(0, 80), (90, 80)]), kind="street", width=3, level="path"),
               feature(COURT, kind="open-space", use="garden", type="courtyard"),
               feature(SQUARE, kind="open-space", use="square", name="Square")]
    plan = [feature(CENTRE, kind="centre", name="Square", level="main")]
    mob = [feature(Point(140, 70), kind="hub", name="Square", level="main")]
    for name, feats in (("massing/massing.geojson", massing), ("structure-plan/structure-plan.geojson", plan),
                        ("mobility/mobility.geojson", mob)):
        (out / name).write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    values = {"bike_stands_per_entrance": 4, "play_m2": 100,
              "centre_uses": [{"use": "food market", "area_m2": 1200, "at": "Square", "source": "test"},
                              {"use": "pool", "area_m2": 3000, "at": "Square", "source": "test"}],
              "hubs": [{"at": "Square", "bus_bays": 2, "bike_spaces": 40, "source": "test"}], **cfg}
    (out / "ground-floor/config.json").write_text(json.dumps({k: {"value": v, "source": "test"} for k, v in values.items()}),
                                                  encoding="utf-8")
    return out


def run(out):
    return subprocess.run([sys.executable, str(GF), "--proposal", str(out), "--config", str(out / "ground-floor/config.json")],
                          capture_output=True, text=True, encoding="utf-8")


def test_ground_floor_rules(tmp_path):
    out = proposal(tmp_path)
    before = (out / "massing/massing.geojson").read_bytes()
    r = run(out)
    assert r.returncode == 0, r.stderr[-2000:]
    stats = json.loads(r.stdout)                     # prints its stats and nothing else
    F = [(f["properties"], local(f["geometry"])) for f in
         json.loads((out / "ground-floor/detail.geojson").read_text(encoding="utf-8"))["features"]]
    doors = {i: [(p, g) for p, g in F if p["kind"] == "entrance" and p["building"] == i] for i in (0, 1, 2)}
    assert len(doors[0]) == 2 and all(p["faces"] == "street" and p["bearing_deg"] == 180 for p, g in doors[0])
    assert all(A.exterior.distance(g) < 0.01 for p, g in doors[0])           # on the facade, one per 30 m of front
    assert doors[1] and all(p["faces"] == "path" and p["bearing_deg"] == 0 for p, g in doors[1])
    stands = [g for p, g in F if p["kind"] == "bike-stands" and p["at"] == "entrance"]
    assert stands and not any(g.intersects(b) for g in stands for b in (A, B, C))
    play = [g for p, g in F if p["kind"] == "play"]
    assert len(play) == 1 and play[0].within(COURT) and abs(play[0].area - 100) < 3
    labels = {p["label"]: p for p, g in F if p["kind"] == "use"}
    assert labels["food market 1,200 m²"]["building"] == 2 and labels["food market 1,200 m²"]["massing_ground_floor"] == "commerce"
    assert "pool: no shop floor at the centre \"Square\" to take it" in stats["flags"]
    bays = [g for p, g in F if p["kind"] == "bus-bay"]
    assert len(bays) == 2 and all(g.within(SQUARE.union(CENTRE).buffer(0.1)) and not g.intersects(C) for g in bays)
    assert [p["spaces"] for p, g in F if p["kind"] == "bike-parking"] == [40] and stats["hubs"][0]["bus_bays"] == 2
    assert (out / "massing/massing.geojson").read_bytes() == before            # the massing's file stays the massing's
    rows = list(csv.DictReader(open(out / "ground-floor/uses.csv", encoding="utf-8")))
    assert [r_["use"] for r_ in rows] == ["food market"] and rows[0]["area_m2"] == "1200"


def test_ground_floor_empty_value_stops(tmp_path):
    r = run(proposal(tmp_path / "a", play_m2=None))
    assert r.returncode != 0 and "play_m2" in r.stderr
    r = run(proposal(tmp_path / "b", hubs=[{"at": "<a hub>", "bus_bays": 2}]))
    assert r.returncode != 0 and "hubs[0].at" in r.stderr
