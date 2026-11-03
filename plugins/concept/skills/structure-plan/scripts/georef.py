"""Places a plan picture from a brief on the site and pulls its colours out as polygons.

    python georef.py --site <site folder> --image <png> --points <points.json> --out <proposal>/structure-plan/traced.geojson
                     [--colours colours.json]

points.json: at least three places you can name in the picture and on the map,
    [{"px": [x, y], "lonlat": [lon, lat], "what": "the underpass under the rail"}, ...]
with px in the picture's pixels (x to the right, y down). A similarity (scale, rotation, shift) is fitted by least
squares in the UTM zone of the site; the residual of each point is printed, and the script stops when the largest
is more than max_residual_m.

colours.json: {"name": {"min": [r, g, b], "max": [r, g, b]}, ...}. The pixels of each range are closed, contoured
and written as polygons with their colour and area. Without it only the picture's outline is written.
Writes the GeoJSON in WGS84 and georef.md next to it: the fit, the residuals, the colours and their areas.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np
import pyproj
from shapely.geometry import shape, mapping, Polygon
from shapely.ops import transform, unary_union

DEFAULTS = {
    'max_residual_m': 40,       # the fit is refused when a point lands farther than this from where it is named
    'close_px': 15,             # gaps in a colour smaller than this (pixels) are closed before contouring
    'min_px': 50,               # colour patches smaller than this many pixels are dropped
    'simplify_px': 1.5,         # contours are simplified by this many pixels
}
C = DEFAULTS

try:
    import cv2
except ImportError:
    sys.exit('georef.py needs OpenCV: pip install opencv-python-headless')


def utm_epsg(lon, lat):
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


ap = argparse.ArgumentParser(description='Places a plan picture on the site and pulls its colours out as polygons.')
ap.add_argument('--site', required=True, help='the folder with site.geojson')
ap.add_argument('--image', required=True)
ap.add_argument('--points', required=True, help='points.json: px, lonlat and what, at least three')
ap.add_argument('--out', required=True, help='the GeoJSON to write, e.g. <proposal>/structure-plan/traced.geojson')
ap.add_argument('--colours', help='colours.json: {"name": {"min": [r, g, b], "max": [r, g, b]}}')
A = ap.parse_args()

site_p = Path(A.site) / 'site.geojson'
if not site_p.exists():
    sys.exit(f'no site.geojson in {A.site}')
site = unary_union([shape(f['geometry']) for f in json.loads(site_p.read_text(encoding='utf-8'))['features']
                    if f.get('geometry')])
EPSG = utm_epsg(site.centroid.x, site.centroid.y)
TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
TO_LL = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform

img = cv2.imdecode(np.fromfile(A.image, dtype=np.uint8), cv2.IMREAD_COLOR)
if img is None:
    sys.exit(f'cannot read the picture {A.image}')
h, w = img.shape[:2]

pts = json.loads(Path(A.points).read_text(encoding='utf-8'))
if len(pts) < 3:
    sys.exit(f'points.json holds {len(pts)} points: name at least three')
# similarity: X = a x - b y + tx, Y = b x + a y + ty, with the picture's y turned up
M, b = [], []
for q in pts:
    x, y = float(q['px'][0]), -float(q['px'][1])
    X, Y = TO_M(*q['lonlat'])
    M += [[x, -y, 1, 0], [y, x, 0, 1]]
    b += [X, Y]
p, *_ = np.linalg.lstsq(np.array(M, float), np.array(b, float), rcond=None)


def to_m(px, py):
    x, y = np.asarray(px, float), -np.asarray(py, float)
    return p[0] * x - p[1] * y + p[2], p[1] * x + p[0] * y + p[3]


res = []
for q in pts:
    X, Y = TO_M(*q['lonlat'])
    fx, fy = to_m(*q['px'])
    res.append(float(np.hypot(fx - X, fy - Y)))
scale = float(np.hypot(p[0], p[1]))
rot = float(np.degrees(np.arctan2(p[1], p[0])))
for q, r in zip(pts, res):
    print(f"  {q.get('what', q['px'])}: {r:.1f} m")
if max(res) > C['max_residual_m']:
    sys.exit(f"the fit misses by up to {max(res):.0f} m (more than {C['max_residual_m']} m): check the points")


def to_ll_poly(rings):
    ll = [[TO_LL(*map(float, to_m(x, y))) for x, y in ring] for ring in rings]
    return Polygon(ll[0], ll[1:])


feats = []
outline_m = Polygon([tuple(map(float, to_m(x, y))) for x, y in ((0, 0), (w, 0), (w, h), (0, h))])
feats.append({'type': 'Feature', 'properties': {'kind': 'picture outline', 'image': Path(A.image).name,
                                                'area_m2': round(outline_m.area)},
              'geometry': mapping(transform(TO_LL, outline_m))})

found = {}
if A.colours:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    kernel = np.ones((C['close_px'], C['close_px']), np.uint8)
    for name, rng in json.loads(Path(A.colours).read_text(encoding='utf-8')).items():
        mask = cv2.inRange(rgb, np.array(rng['min'], np.uint8), np.array(rng['max'], np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        found[name] = []
        if hier is None:
            continue
        for i, c in enumerate(cs):
            if hier[0][i][3] != -1 or cv2.contourArea(c) < C['min_px']:
                continue                          # holes are taken with their outer ring below
            rings = [cv2.approxPolyDP(c, C['simplify_px'], True).reshape(-1, 2)]
            j = hier[0][i][2]
            while j != -1:
                if cv2.contourArea(cs[j]) >= C['min_px']:
                    rings.append(cv2.approxPolyDP(cs[j], C['simplify_px'], True).reshape(-1, 2))
                j = hier[0][j][0]
            if len(rings[0]) < 3:
                continue
            g = to_ll_poly([r.tolist() for r in rings if len(r) >= 3])
            g = g if g.is_valid else g.buffer(0)
            a = transform(TO_M, g).area
            found[name].append(a)
            feats.append({'type': 'Feature', 'properties': {'kind': 'traced', 'colour': name, 'area_m2': round(a)},
                          'geometry': mapping(g)})

out = Path(A.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({'type': 'FeatureCollection', 'crs_note': 'WGS84, longitude first', 'features': feats},
                          ensure_ascii=False), encoding='utf-8')
md = [f'# Georeference of {Path(A.image).name}', '',
      f'A similarity fitted by least squares from {len(pts)} points, in EPSG:{EPSG}: {scale:.3f} m per pixel, '
      f'rotation {rot:.2f} degrees, picture {w} x {h} px.', '', '## Residuals', '']
md += [f"- {q.get('what', q['px'])}: {r:.1f} m" for q, r in zip(pts, res)]
md += ['', f'Largest {max(res):.1f} m (limit {C["max_residual_m"]} m).', '', '## Colours', '']
if found:
    md += [f'- {n}: {len(a)} polygons, {sum(a) / 1e4:.2f} ha' for n, a in found.items()]
else:
    md += ['- none asked for: only the picture outline is written.']
out.with_name('georef.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
print(f'{out}: {len(feats)} features; fit {scale:.3f} m/px, largest residual {max(res):.1f} m')
