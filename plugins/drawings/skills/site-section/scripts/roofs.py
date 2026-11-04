"""Roofs from a site's 3D building models, for the section: cut along the line, or seen from it.

models(path, to_m, bounds) reads a GeoJSON of surfaces (Polygon or MultiPolygon, [lon, lat, z]) and returns
    {key: dict(faces=[(n, 3) arrays, metric], zmin=lowest z of any of its surfaces, foot=roofs seen from above)}.
    A surface belongs to the building named by the first of KEYS it has. It is a roof when a property says
    'roof', not one when a property says wall, ground, floor or closure, and without either when it slopes
    and stands above the model's foot.
cut(faces, A, e, V, lo, hi)                     the roof's profile in the vertical plane through A along e.
silhouette(faces, A, e, V, lo, hi, front=None)  the upper outline of the faces seen along V (only u >= front).
Both return [(t, z)] from lo to hi, t along e from A, or [] when the faces do not reach the line.
"""
import json

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

KEYS = ('building_id', 'parent_id', 'id', 'gml_id')
NOT_ROOF = ('wall', 'ground', 'floor', 'closure')


def _kind(props):
    vals = [str(v).lower() for v in props.values() if isinstance(v, str)]
    if any('roof' in v for v in vals):
        return True
    if any(w in v for v in vals for w in NOT_ROOF):
        return False
    return None


def _slopes(q):
    n = np.cross(q - q.mean(axis=0), np.roll(q, -1, axis=0) - q.mean(axis=0)).sum(axis=0)   # Newell's normal
    return np.linalg.norm(n) > 0 and abs(n[2]) > 0.1 * np.linalg.norm(n)


def models(path, to_m, bounds=None):
    feats = json.load(open(path, encoding='utf-8')).get('features') or []
    rings, meta = [], []
    for i, f in enumerate(feats):
        g = f.get('geometry') or {}
        polys = {'Polygon': [g.get('coordinates')], 'MultiPolygon': g.get('coordinates')}.get(g.get('type')) or []
        p = f.get('properties') or {}
        key = next((str(p[k]) for k in KEYS if p.get(k) not in (None, '')), str(f.get('id', i)))
        for poly in polys:
            r = poly[0] if poly else []
            if len(r) >= 4 and all(len(c) >= 3 for c in r):
                rings.append(np.asarray([c[:3] for c in r], float))
                meta.append((key, _kind(p)))
    if not rings:
        return {}
    allc = np.concatenate(rings)
    x, y = to_m(allc[:, 0], allc[:, 1])
    xyz = np.column_stack([x, y, allc[:, 2]])
    out, k0 = {}, 0
    for r, (key, kind) in zip(rings, meta):
        q = xyz[k0:k0 + len(r)][:-1]   # the ring without its closing point
        k0 += len(r)
        m = out.setdefault(key, dict(faces=[], todo=[], zmin=np.inf))
        m['zmin'] = min(m['zmin'], float(q[:, 2].min()))
        if bounds is not None and (q[:, 0].max() < bounds[0] or q[:, 0].min() > bounds[2]
                                   or q[:, 1].max() < bounds[1] or q[:, 1].min() > bounds[3]):
            continue
        if kind is True:
            m['faces'].append(q)
        elif kind is None:
            m['todo'].append(q)
    for key in list(out):
        m = out[key]
        m['faces'] += [q for q in m.pop('todo') if _slopes(q) and q[:, 2].mean() > m['zmin'] + 0.5]
        foot = [Polygon(q[:, :2]).buffer(0) for q in m['faces'] if len(q) >= 3]
        foot = unary_union([f for f in foot if f.area > 0.01]) if foot else None
        if not m['faces'] or foot is None or foot.is_empty:
            del out[key]
        else:
            m['foot'] = foot
    return out


def _tuz(faces, A, e, V):
    for q in faces:
        d = q[:, :2] - A
        yield np.column_stack([d @ e, d @ V, q[:, 2]])


def _edges(q):
    return zip(q, np.roll(q, -1, axis=0))


def _clip(q, front):
    """The part of a polygon (t, u, z) with u >= front."""
    out = []
    for a, b in _edges(q):
        ia, ib = a[1] >= front, b[1] >= front
        if ia:
            out.append(a)
        if ia != ib:
            out.append(a + (b - a) * (front - a[1]) / (b[1] - a[1]))
    return np.array(out)


def envelope(segs, lo, hi):
    """The upper outline of segments (t0, z0, t1, z1) between lo and hi, exact: a polyline [(t, z)]."""
    S = np.array([s if s[0] <= s[2] else (s[2], s[3], s[0], s[1]) for s in segs], float).reshape(-1, 4)
    S = S[(S[:, 2] - S[:, 0] > 1e-6) & (S[:, 2] > lo) & (S[:, 0] < hi)]
    if not len(S):
        return []
    ta, za, tb, zb = S.T
    k = (zb - za) / (tb - ta)
    b0 = za - k * ta
    with np.errstate(divide='ignore', invalid='ignore'):   # where two segments cross
        tx = (b0[None, :] - b0[:, None]) / (k[:, None] - k[None, :])
    ok = np.isfinite(tx) & (tx > np.maximum(ta[:, None], ta[None, :])) & (tx < np.minimum(tb[:, None], tb[None, :]))
    br = np.unique(np.clip(np.concatenate([[lo, hi], ta, tb, tx[ok]]), lo, hi))
    a, b = br[:-1], br[1:]
    keep = b - a > 1e-6
    a, b = a[keep], b[keep]
    mid = (a + b) / 2
    act = (ta[None, :] <= mid[:, None]) & (tb[None, :] >= mid[:, None])
    val = np.where(act, k[None, :] * mid[:, None] + b0[None, :], -np.inf)
    top = val.argmax(axis=1)
    has = act.any(axis=1)
    pts = []
    for ai, bi, i in zip(a[has], b[has], top[has]):
        pts += [(float(ai), float(k[i] * ai + b0[i])), (float(bi), float(k[i] * bi + b0[i]))]
    if not pts:
        return []
    if pts[0][0] > lo:     # the model is shorter than the footprint: its edge height holds to the wall
        pts.insert(0, (lo, pts[0][1]))
    if pts[-1][0] < hi:
        pts.append((hi, pts[-1][1]))
    clean = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - clean[-1][0]) > 1e-6 or abs(p[1] - clean[-1][1]) > 1e-6:
            clean.append(p)
    out = [clean[0]]
    for p, q in zip(clean[1:-1], clean[2:]):   # drop points on a straight run
        o = out[-1]
        if abs((p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])) > 1e-6:
            out.append(p)
    return out + clean[-1:] if len(clean) > 1 else out


def cut(faces, A, e, V, lo, hi):
    segs = []
    for q in _tuz(faces, A, e, V):
        xs = sorted((a[0] + (b[0] - a[0]) * a[1] / (a[1] - b[1]), a[2] + (b[2] - a[2]) * a[1] / (a[1] - b[1]))
                    for a, b in _edges(q) if (a[1] <= 0 < b[1]) or (b[1] <= 0 < a[1]))
        segs += [(*xs[i], *xs[i + 1]) for i in range(0, len(xs) - 1, 2)]
    return envelope(segs, lo, hi)


def silhouette(faces, A, e, V, lo, hi, front=None):
    segs = []
    for q in _tuz(faces, A, e, V):
        if front is not None:
            q = _clip(q, front)
        if len(q) >= 2:
            segs += [(a[0], a[2], b[0], b[2]) for a, b in _edges(q)]
    return envelope(segs, lo, hi)


def pitched(pts, min_run=0.3, slope=0.09):
    """True when the outline has a sloping run (more than about 5 degrees)."""
    return any(q[0] - p[0] > min_run and abs(q[1] - p[1]) > slope * (q[0] - p[0]) for p, q in zip(pts, pts[1:]))
