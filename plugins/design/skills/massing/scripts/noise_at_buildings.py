"""The noise at each new building with the design standing: the new buildings and the city around them screen it.

    python noise_at_buildings.py --proposal <proposal folder> --site <site folder>

Reads the noise sources and emission levels the climate skill wrote (climate/noise-sources.geojson, climate/noise.json),
massing/massing.geojson and the site's buildings. Writes massing/noise-design.geojson: each new building's footprint with
noise_day_db and noise_night_db, the loudest point around its facades, at the height the climate map used and at its top floor.
Method as the climate map: RLS-90 partial sources, screening over the highest roof on each path, flat ground, no reflections.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
import pyproj
import shapely
from shapely.geometry import mapping, shape
from shapely.ops import transform

HS = 0.5        # source height, m
OFFSET = 3.0    # receivers this far outside the facade, m
STEP = 15.0     # one receiver every so many metres around the building
RAISED = 1.5    # the top floor's window below the roof, m
REACH = 1500.0  # beyond, a source's share is below what matters


def load(path):
    return json.load(open(path, encoding='utf8'))['features']


def height(p):
    return p.get('height_m') or p.get('height') or (3.0 * float(p['floors']) if p.get('floors') else None)


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument('--proposal', required=True)
    a.add_argument('--site', required=True)
    a.add_argument('--seg', type=float, default=25)
    a.add_argument('--raster', type=float, default=5)
    args = a.parse_args()
    climate, R = os.path.join(args.proposal, 'climate'), args.raster
    for name in ('noise-sources.geojson', 'noise.json'):
        if not os.path.exists(os.path.join(climate, name)):
            sys.exit('no climate/%s: run the climate skill first' % name)
    summary = json.load(open(os.path.join(climate, 'noise.json'), encoding='utf8'))
    lme = {u['name']: u for u in summary['sources_used']}
    h0 = float(summary.get('receiver_height_m', 4))

    site_ll = shape(load(os.path.join(args.site, 'site.geojson'))[0]['geometry'])
    c = site_ll.centroid
    to_m = pyproj.Transformer.from_crs(4326, (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1, always_xy=True).transform
    m = lambda f: transform(to_m, shape(f['geometry']))
    site = transform(to_m, site_ll)

    massing = [f for f in load(os.path.join(args.proposal, 'massing', 'massing.geojson')) if f['properties'].get('kind') == 'building']
    new = [f for f in massing if not f['properties'].get('existing')]
    solid = [(m(f).buffer(0), height(f['properties'])) for f in massing]
    around = os.path.join(args.site, 'buildings.geojson')   # massing.geojson holds only what stands on the site
    if os.path.exists(around):
        for f in load(around):
            g = m(f)
            if not site.contains(g.representative_point()):
                solid.append((g.buffer(0), height(f['properties'])))
    solid = [(g, float(H)) for g, H in solid if H and not g.is_empty]
    G, H = np.array([g for g, _ in solid], dtype=object), np.array([h for _, h in solid], float)

    # receivers around each new building, low and at its top floor
    xy, owner, hr = [], [], []
    for i, f in enumerate(new):
        ring = m(f).buffer(OFFSET).exterior
        top = max(h0, (height(f['properties']) or h0) - RAISED)
        n = max(4, int(ring.length / STEP))
        for k in range(n):
            p = ring.interpolate(k / n, normalized=True)
            for z in {h0, top}:
                xy.append((p.x, p.y)); owner.append(i); hr.append(z)
    xy, owner, hr = np.array(xy), np.array(owner), np.array(hr)
    tree = shapely.STRtree(G)
    inside = np.zeros(len(xy), bool)
    inside[tree.query(shapely.points(xy[:, 0], xy[:, 1]), predicate='within')[0]] = True
    xy, owner, hr = xy[~inside], owner[~inside], hr[~inside]

    # building heights on a raster, sampled along each sound path
    rx0, ry0 = xy.min(0) - REACH
    rx1, ry1 = xy.max(0) + REACH
    nx, ny = int((rx1 - rx0) / R) + 1, int((ry1 - ry0) / R) + 1
    gx, gy = np.meshgrid(rx0 + (np.arange(nx) + .5) * R, ry0 + (np.arange(ny) + .5) * R)
    hgrid = np.zeros(gx.size, np.float32)
    thin = 2 * shapely.area(G) / np.maximum(shapely.length(G), 1e-6) < R   # a wall thinner than a cell would fall between cell centres
    pi, bi = shapely.STRtree(np.where(thin, shapely.buffer(G, R / 2, cap_style='flat', join_style='mitre'), G)).query(shapely.points(gx.ravel(), gy.ravel()), predicate='within')
    np.maximum.at(hgrid, pi, H[bi].astype(np.float32))
    hgrid = hgrid.reshape(gx.shape)

    E = {'day': np.zeros(len(xy)), 'night': np.zeros(len(xy))}
    for src in load(os.path.join(climate, 'noise-sources.geojson')):
        level = lme.get(src['properties']['name'])
        if not level:
            continue
        fine = shapely.segmentize(m(src), args.seg)
        for part in getattr(fine, 'geoms', [fine]):
            q = np.asarray(part.coords)[:, :2]
            for mid, l in zip((q[:-1] + q[1:]) / 2, np.hypot(*(q[1:] - q[:-1]).T)):
                if l < 0.5:
                    continue
                s = np.maximum(np.hypot(*(xy - mid).T), 2.0)
                idx = np.nonzero(s < REACH)[0]
                if not len(idx):
                    continue
                si, z_r = s[idx], hr[idx]
                K = int(np.ceil(si.max() / R))
                t = ((np.arange(K) + 0.5) / K).astype(np.float32)
                ix = np.clip(((mid[0] + (xy[idx, 0, None] - mid[0]) * t - rx0) / R).astype(int), 0, nx - 1)
                iy = np.clip(((mid[1] + (xy[idx, 1, None] - mid[1]) * t - ry0) / R).astype(int), 0, ny - 1)
                h = hgrid[iy, ix]
                A, B = si[:, None] * t, si[:, None] * (1 - t)
                z = np.where(h > HS + (z_r[:, None] - HS) * t,   # only a roof above the line of sight screens
                             np.sqrt(A ** 2 + (h - HS) ** 2) + np.sqrt(B ** 2 + (h - z_r[:, None]) ** 2) - np.sqrt(si ** 2 + (z_r - HS) ** 2)[:, None], 0)
                k = z.argmax(1)
                r_ = np.arange(len(idx))
                z, A, B = z[r_, k], A[r_, k], B[r_, k]
                Kw = np.exp(-np.sqrt(A * B * si / (2 * np.maximum(z, 1e-6))) / 2000)
                Dz = np.where(z > 0, np.minimum(7 * np.log10(np.maximum(5 + (70 + 0.25 * si) / (1 + 0.2 * z) * z * Kw, 1)), 20), 0)
                Ds = 11.2 - 20 * np.log10(si) - si / 200
                Dbm = np.where(Dz > 0, 0, np.minimum(0, ((HS + z_r) / 2 / si) * (34 + 600 / si) - 4.8))
                path = 10 * math.log10(l) + Ds + Dbm - Dz
                for per in E:
                    E[per][idx] += 10 ** ((level['lme_' + per] + path) / 10)

    loudest = {}
    for per, v in E.items():
        loudest[per] = np.full(len(new), np.nan)
        L = 10 * np.log10(np.maximum(v, 1e-3))
        for i in np.unique(owner):
            loudest[per][i] = L[owner == i].max()
    out = [{'type': 'Feature', 'geometry': f['geometry'],
            'properties': {'kind': 'noise-at-building', 'noise_day_db': round(float(loudest['day'][i]), 1), 'noise_night_db': round(float(loudest['night'][i]), 1)}}
           for i, f in enumerate(new) if not np.isnan(loudest['day'][i])]
    json.dump({'type': 'FeatureCollection', 'features': out}, open(os.path.join(args.proposal, 'massing', 'noise-design.geojson'), 'w', encoding='utf8'))
    print('%d of %d new buildings measured' % (len(out), len(new)))


if __name__ == '__main__':
    main()
