"""Checks of the building IDs. Run with pytest, or on its own: python test_fingerprint.py
The conversion checks need pyproj and are skipped without it."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fingerprint import fingerprint, canonical, relink, FingerprintError, SCALE, step_cm  # noqa: E402

try:
    from pytest import skip
except ImportError:
    class Skipped(Exception):
        pass

    def skip(why):
        raise Skipped(why)

LATS = (0.0, 49.0, 80.0)
STEP = 1.0 / SCALE


def deg_per_m(lat):
    ns, ew = step_cm(lat)
    return STEP / (ns / 100), STEP / (ew / 100)   # degrees per metre: north-south, east-west


def at(lon0, lat0, xy, f=0.25):
    """Points given in metres from (lon0, lat0), placed f of a rounding step past a whole number."""
    dlat, dlon = deg_per_m(lat0)
    out = []
    for x, y in xy:
        lon = (math.floor((lon0 + x * dlon) * SCALE) + f) / SCALE
        lat = (math.floor((lat0 + y * dlat) * SCALE) + f) / SCALE
        out.append([lon, lat])
    return out


def poly(*rings):
    return {'type': 'Polygon', 'coordinates': [r + [r[0]] for r in rings]}


def multi(*polys):
    return {'type': 'MultiPolygon', 'coordinates': [p['coordinates'] for p in polys]}


def shapes(lat):
    lon = 10.0
    outer = at(lon, lat, [(0, 0), (30, 0), (30, 20), (0, 20)])
    hole1 = at(lon, lat, [(5, 5), (5, 10), (10, 10), (10, 5)])
    hole2 = at(lon, lat, [(20, 5), (20, 10), (25, 10), (25, 5)])
    other = at(lon, lat, [(50, 0), (60, 0), (60, 10), (50, 10)])
    return outer, hole1, hole2, other


def expect_error(geom):
    try:
        fingerprint(geom)
    except FingerprintError:
        return
    raise AssertionError('expected FingerprintError')


# ---- 1. rearrangements: the same ID, exactly ----
def test_rearrangements():
    for lat in LATS:
        outer, h1, h2, other = shapes(lat)
        base = fingerprint(poly(outer, h1, h2))
        assert base.startswith('b-') and len(base) == 18
        assert fingerprint(poly(outer[::-1], h1, h2)) == base, 'reversed outer ring'
        for i in range(len(outer)):
            assert fingerprint(poly(outer[i:] + outer[:i], h1, h2)) == base, 'rotated outer ring'
        for i in range(len(h1)):
            r = (h1[i:] + h1[:i])[::-1]
            assert fingerprint(poly(outer, r, h2)) == base, 'reversed and rotated hole'
        assert fingerprint(poly(outer, h2, h1)) == base, 'swapped holes'
        assert fingerprint(multi(poly(outer), poly(other))) == fingerprint(multi(poly(other), poly(outer))), 'swapped parts'
        assert fingerprint(multi(poly(outer, h1, h2))) == base, 'Polygon against one-part MultiPolygon'
        assert fingerprint(poly(outer[:2] + [outer[1]] + outer[2:], h1, h2)) == base, 'repeated point'


def test_tie_on_smallest_point():
    # an L shape whose smallest point, once rounded, occurs twice: two vertices within one rounding step
    lat = 49.0
    dlat, dlon = deg_per_m(lat)
    lon0 = 10.0
    q = lambda x, y, f=0.25: [(math.floor((lon0 + x * dlon) * SCALE) + f) / SCALE, (math.floor((lat + y * dlat) * SCALE) + f) / SCALE]
    a = q(0, 0)
    a2 = [a[0], a[1] + 0.2 * STEP]        # 0.25 -> 0.45 of a step: rounds to the same point as a, not next to it in the ring
    ring = [a, q(20, 0), q(20, 8), q(8, 8), q(8, 20), a2, q(0, 10)]
    # a and a2 round to the same point: the smallest point occurs twice, the points after it decide
    smallest = canonical(poly(ring)).split(';')[0]
    assert canonical(poly(ring)).split(';').count(smallest) == 2, 'the tie did not happen'
    ids = set()
    for r in (ring, ring[::-1]):
        for i in range(len(r)):
            ids.add(fingerprint(poly(r[i:] + r[:i])))
    assert len(ids) == 1, ids


def test_ring_that_repeats_itself():
    outer = shapes(49.0)[0]
    assert fingerprint(poly(outer + outer)) == fingerprint(poly(outer))


# ---- 2. converting to another system and back ----
def test_conversion_round_trip():
    try:
        import pyproj
    except ImportError:
        skip('needs pyproj')
    for lat in LATS:
        outer, h1, h2, other = shapes(lat)
        g = poly(outer, h1, h2)
        zone = 32600 + int((10.0 + 180) // 6) + 1
        for epsg in (zone, 25832):
            fw = pyproj.Transformer.from_crs(4326, epsg, always_xy=True)
            bw = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True)
            back = [[list(bw.transform(*fw.transform(x, y))) for x, y in r] for r in g['coordinates']]
            err = max(abs(b - a) for r0, r1 in zip(g['coordinates'], back) for p0, p1 in zip(r0, r1) for a, b in zip(p0, p1))
            margin = min(abs(v * SCALE - math.floor(v * SCALE) - 0.5) for r in g['coordinates'] for p in r for v in p) * STEP
            assert margin >= 1000 * err, 'test shape too close to a rounding boundary for this conversion'
            assert fingerprint({'type': 'Polygon', 'coordinates': back}) == fingerprint(g), epsg


def test_boundary_case_is_relinked():
    # a coordinate right at a rounding boundary may round either way after a conversion: the ID can change,
    # and the decision is then found again by its centre and area, and reported
    # (a millionth of a step is about 1e-8 cm, far below what a conversion moves a point, but above float precision)
    outer = at(10.0, 49.0, [(0, 0), (30, 0), (30, 20), (0, 20)], f=0.5 - 1e-4)
    moved = [p[:] for p in outer]
    moved[0][0] += 2e-4 * STEP
    a, b = fingerprint(poly(outer)), fingerprint(poly(moved))
    assert a != b, 'the boundary case should change the ID'
    found, why = relink({'id': a, 'centre': (15.0, 10.0), 'area': 600.0},
                        [{'id': b, 'centre': (15.0, 10.0), 'area': 600.0}, {'id': 'b-x', 'centre': (80.0, 10.0), 'area': 600.0}], 0.5)
    assert found == b and why.startswith('re-linked')
    found, why = relink({'id': a, 'centre': (15.0, 10.0), 'area': 600.0},
                        [{'id': b, 'centre': (15.0, 10.0), 'area': 600.0}, {'id': 'b-y', 'centre': (15.1, 10.0), 'area': 601.0}], 0.5)
    assert found is None and 'match' in why


# ---- 3. small movements ----
OFFSETS = (0.01, 0.25, 0.49, 0.51, 0.75, 0.99)


def moved_id(lat, f, dx_m, dy_m):
    outer = at(10.0, lat, [(0, 0), (30, 0), (30, 20), (0, 20)], f=f)
    dlat, dlon = deg_per_m(lat)
    m = [p[:] for p in outer]
    m[1] = [m[1][0] + dx_m * dlon, m[1][1] + dy_m * dlat]
    return fingerprint(poly(outer)), fingerprint(poly(m))


def test_five_cm_always_detected():
    for lat in LATS:
        for f in OFFSETS:
            for dx, dy in ((0, 0.05), (0.05, 0), (0.05 / math.sqrt(2), 0.05 / math.sqrt(2))):
                a, b = moved_id(lat, f, dx, dy)
                assert a != b, (lat, f, dx, dy)


def test_one_step_always_detected():
    for lat in LATS:
        for f in OFFSETS:
            outer = at(10.0, lat, [(0, 0), (30, 0), (30, 20), (0, 20)], f=f)
            for axis in (0, 1):
                m = [p[:] for p in outer]
                m[1][axis] += STEP
                assert fingerprint(poly(outer)) != fingerprint(poly(m)), (lat, f, axis)


def test_movement_below_one_step():
    outer = at(10.0, 49.0, [(0, 0), (30, 0), (30, 20), (0, 20)], f=0.10)
    m = [p[:] for p in outer]
    m[1][1] += 0.3 * STEP          # 0.10 -> 0.40: no boundary crossed, the movement is hidden (documented)
    assert fingerprint(poly(outer)) == fingerprint(poly(m))
    outer = at(10.0, 49.0, [(0, 0), (30, 0), (30, 20), (0, 20)], f=0.40)
    m = [p[:] for p in outer]
    m[1][1] += 0.3 * STEP          # 0.40 -> 0.70: crosses a boundary, the movement shows
    assert fingerprint(poly(outer)) != fingerprint(poly(m))


# ---- 4. a real difference: a different ID ----
def test_real_differences():
    outer, h1, h2, other = shapes(49.0)
    base = fingerprint(poly(outer, h1))
    assert fingerprint(poly(outer)) != base, 'hole removed'
    assert fingerprint(poly(outer, h1, h2)) != base, 'hole added'
    assert fingerprint(multi(poly(outer, h1), poly(other))) != base, 'part added'
    mirrored = [[2 * 10.0 - x, y] for x, y in outer]
    assert fingerprint(poly(mirrored)) != fingerprint(poly(outer)), 'mirrored'
    mid = [(outer[0][0] + outer[1][0]) / 2, outer[0][1]]
    assert fingerprint(poly([outer[0], mid] + outer[1:])) != fingerprint(poly(outer)), 'point added along an edge'


# ---- 5. stops ----
def test_stops():
    outer = shapes(49.0)[0]
    expect_error(poly([outer[0], outer[1], outer[0]]))                            # fewer than 3 distinct points
    expect_error(poly([outer[0], outer[1], [2 * outer[1][0] - outer[0][0], outer[0][1]]]))   # zero area: one line
    near_pole = at(10.0, 89.9999999, [(0, 0), (0.0001, 0), (0.0001, 0.0001)])     # points that merge near the pole
    expect_error(poly(near_pole))
    expect_error({'type': 'LineString', 'coordinates': outer})


# ---- 6. invalid footprints get an ID ----
def test_self_crossing_gets_an_id():
    q = at(10.0, 49.0, [(0, 0), (30, 20), (30, 0), (0, 30)])   # a bowtie with uneven halves: crosses itself, area not zero
    assert fingerprint(poly(q)).startswith('b-')


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print('ok  ', t.__name__)
        except AssertionError as e:
            failed += 1
            print('FAIL', t.__name__, e)
        except Exception as e:
            if type(e).__name__ not in ('Skipped', 'Skip'):
                raise
            print('skip', t.__name__, e)
    sys.exit(1 if failed else 0)
