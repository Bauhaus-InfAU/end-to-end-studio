"""Building IDs from the footprint alone, the same whatever system it was measured in.

    fingerprint(geometry) -> 'b-' + 16 hex characters, for a GeoJSON Polygon or MultiPolygon in WGS84 (lon, lat)

Every coordinate is rounded to a whole number of 1e-7 degrees, and everything after that works on whole numbers:
- a Polygon counts as a MultiPolygon with one part;
- in each ring, points repeated one after another (the closing point too) are dropped, and a ring that runs
  round itself more than once is cut to one round;
- an outer ring runs anticlockwise, an interior ring clockwise, by its signed area in whole numbers;
- each ring starts at the rotation whose whole sequence of points is smallest, so ties are decided by the points after;
- holes, then parts, are sorted by their sequences.

What one step of 1e-7 degrees is on the ground: about 1.11 cm north-south everywhere, and 1.11 cm x cos(latitude)
east-west (0.73 cm at 49 degrees, 0.19 cm at 80, nothing at the poles). So:
- the ID is exactly the same for ring direction, starting point, order of holes and parts, Polygon or one-part
  MultiPolygon, and repeated points;
- a movement of at least one step on an axis always changes the ID; a smaller one may be hidden by rounding;
- after converting to another system and back, a coordinate that lies within the conversion's error of a rounding
  boundary can round to the next number, so the ID is not guaranteed then: relink() finds the building again.
Plain Python, no libraries.
"""
import hashlib
import math

SCALE = 10 ** 7


class FingerprintError(ValueError):
    pass


def step_cm(lat):
    """The ground size of one rounding step at a latitude: (north-south cm, east-west cm)."""
    ns = 1e-7 * math.pi / 180 * 6371008.8 * 100
    return ns, ns * math.cos(math.radians(lat))


def quantise(v):
    return int(round(v * SCALE))


def _points(coords):
    pts = []
    for c in coords:
        p = (quantise(c[0]), quantise(c[1]))
        if not pts or pts[-1] != p:
            pts.append(p)
    while len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    n = len(pts)
    for period in range(1, n):   # a ring that runs round itself more than once: one round
        if n % period == 0 and pts == pts[period:] + pts[:period]:
            pts = pts[:period]
            break
    return pts


def _area2(pts):
    """Twice the signed area, exact in whole numbers; positive anticlockwise."""
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def canonical_ring(coords, exterior, who='a ring'):
    pts = _points(coords)
    if len(set(pts)) < 3:
        raise FingerprintError(f'{who}: fewer than 3 distinct points after rounding to 1e-7 degrees')
    a = _area2(pts)
    if a == 0:
        raise FingerprintError(f'{who}: zero area after rounding to 1e-7 degrees')
    if (a > 0) != exterior:
        pts.reverse()
    return min(tuple(pts[i:] + pts[:i]) for i in range(len(pts)))


def canonical(geometry, who='the footprint'):
    t = geometry.get('type')
    if t == 'Polygon':
        polys = [geometry['coordinates']]
    elif t == 'MultiPolygon':
        polys = geometry['coordinates']
    else:
        raise FingerprintError(f'{who}: a footprint is a Polygon or MultiPolygon, not {t}')
    if not polys:
        raise FingerprintError(f'{who}: empty footprint')
    parts = []
    for i, rings in enumerate(polys):
        if not rings:
            raise FingerprintError(f'{who}: part {i + 1} has no ring')
        ext = canonical_ring(rings[0], True, f'{who}, part {i + 1}, outer ring')
        holes = sorted(canonical_ring(r, False, f'{who}, part {i + 1}, hole {j + 1}') for j, r in enumerate(rings[1:]))
        parts.append((ext,) + tuple(holes))
    parts.sort()
    return '/'.join('|'.join(';'.join(f'{x},{y}' for x, y in ring) for ring in part) for part in parts)


def fingerprint(geometry, who='the footprint'):
    return 'b-' + hashlib.sha1(canonical(geometry, who).encode('ascii')).hexdigest()[:16]


def relink(decision, candidates, snap_m, area_tol=0.05):
    """A decision whose ID is no longer found: the one candidate whose centre lies within snap_m of the decision's and
    whose area is within area_tol of it. decision and candidates: {'id', 'centre': (x, y) in metres, 'area': m2}.
    Returns (candidate id or None, why)."""
    cx, cy = decision['centre']
    a = decision['area']
    hits = [c for c in candidates
            if math.hypot(c['centre'][0] - cx, c['centre'][1] - cy) <= snap_m and a > 0 and abs(c['area'] - a) <= area_tol * a]
    if len(hits) == 1:
        return hits[0]['id'], 're-linked by centre and area'
    if len(hits) > 1:
        return None, 'lost: %d buildings match its centre and area' % len(hits)
    return None, 'lost: no building matches its centre and area'
