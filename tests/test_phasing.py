"""The phasing skill's script: one phase per building, the homes each phase holds, and every mismatch flagged."""
import csv, json, subprocess, sys
from shapely.geometry import box, mapping
from conftest import REPO

PHASES = REPO / "plugins/design/skills/phasing/scripts/phases.py"
D = 0.001   # about 100 m


def feature(geom, **props):
    return {"type": "Feature", "properties": props, "geometry": mapping(geom)}


def proposal(tmp_path, **cfg):
    out = tmp_path / "with space" / "2026-01-01_t"
    for d in ("structure-plan", "massing", "phasing"):
        (out / d).mkdir(parents=True)
    plan = [feature(box(0, 0, 2 * D, D), kind="neighbourhood", name="North", action="new", phase=1, homes=100),
            feature(box(0, -D, 2 * D, 0), kind="neighbourhood", name="South", action="new", phase=2, homes=50),
            feature(box(2 * D, 0, 3 * D, D), kind="centre", name="Square", action="new", level="main", phase=1,
                    holds="a daycare, the bus stop")]
    hb = lambda x, y: box(x, y, x + D / 4, y + D / 4)
    massing = [feature(hb(0, 0), kind="building", use="housing", floors=5, footprint_m2=1000, neighbourhood="North", phase=1),
               feature(hb(D, 0), kind="building", use="mixed", floors=3, footprint_m2=500, neighbourhood="North", phase=1),
               feature(hb(0, -D / 2), kind="building", use="housing", floors=4, footprint_m2=400, neighbourhood="South", phase=1),
               feature(hb(D, -D / 2), kind="building", use="housing", floors=2, footprint_m2=100),   # no name: it stands in South
               feature(hb(2 * D, 0), kind="building", use="daycare 1", floors=2, footprint_m2=500, neighbourhood="Square"),
               feature(hb(0, D / 2), kind="building", use="housing", floors=9, footprint_m2=900, existing=True)]
    for name, feats in (("structure-plan/structure-plan.geojson", plan), ("massing/massing.geojson", massing)):
        (out / name).write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    values = {"m2_per_home": 50, "residents_per_home": 2, "min_homes": {"1": 150},
              "first": [{"what": "daycare", "phase": 1}, {"what": "pool", "phase": 2}], **cfg}
    (out / "phasing/config.json").write_text(json.dumps({k: {"value": v, "source": "test"} for k, v in values.items()}),
                                             encoding="utf-8")
    return out


def run(out):
    return subprocess.run([sys.executable, str(PHASES), "--proposal", str(out), "--config", str(out / "phasing/config.json")],
                          capture_output=True, text=True, encoding="utf-8")


def test_phases_reconciled_and_flagged(tmp_path):
    out = proposal(tmp_path)
    r = run(out)
    assert r.returncode == 0, r.stderr[-2000:]
    stats = json.loads(r.stdout)   # prints its stats and nothing else
    one, two = stats["phases"]["1"], stats["phases"]["2"]
    # North: 1000 x 5 + 500 x (3 - 1) = 6,000 m2 of homes, 120 homes; South: 400 x 4 + 100 x 2 = 1,800 m2, 36 homes
    assert (one["homes"], one["residents"], one["homes_planned"], one["difference"]) == (120, 240, 100, 20)
    assert (two["homes"], two["homes_planned"], two["difference"]) == (36, 50, -14)
    assert "Square" in one["first"] and "daycare 1" in one["first"]
    flags = " | ".join(stats["flags"])
    assert "South: 1 buildings are phase 1 in the massing, phase 2 here" in flags
    assert "below the minimum of 150" in flags and "pool is not in phase 2" in flags and "daycare" not in flags
    rows = {r["phase"]: r for r in csv.DictReader(open(out / "phasing/phases.csv", encoding="utf-8"))}
    assert rows["total"]["homes"] == "156" and rows["1"]["neighbourhoods"] == "North"
    gj = json.loads((out / "phasing/phases.geojson").read_text(encoding="utf-8"))["features"]
    assert sorted(f["properties"]["phase"] for f in gj if f["properties"]["kind"] == "phase") == ["1", "2"]
    assert len([f for f in gj if f["properties"]["kind"] == "building"]) == 5   # the kept building is not phased


def test_phase_of_overrides_and_empty_value_stops(tmp_path):
    r = run(proposal(tmp_path / "a", phase_of={"South": 1}))
    assert r.returncode == 0 and json.loads(r.stdout)["phases"]["1"]["homes"] == 156
    r = run(proposal(tmp_path / "b", residents_per_home=None))
    assert r.returncode != 0 and "residents_per_home" in r.stderr
