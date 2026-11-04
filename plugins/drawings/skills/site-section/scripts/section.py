"""A long section through a project site on its real ground.

    python section.py --site <site folder> --proposal <proposal folder> --scale <site plan scale>
                      --detail-scale <largest scale> [--massing] [--line lon,lat lon,lat]
                      [--look north|south|east|west] [--at lon,lat] [--style style.json]

Reads <site>/site.geojson and its layers (buildings, plots, streets, street-land, rail, water), the site's
terrain (terrain.py: the site folder's GeoTIFF, else terrain.csv, else a free elevation service, else flat),
its 3D building models if there are some (buildings-3d.geojson: roofs cut along the line, roofs.py), and with --massing <proposal>/massing/massing.geojson. Without --line it chooses the line itself; with
--massing and no --line it keeps the line of the earlier pass (cut.json). Writes into <proposal>/site-section/:
site-section[_design]_1-<scale>.svg/.png, site-section[_design]_excerpt_1-<detail>.svg/.png, profile.csv,
cut.json and assumptions.md. The helper writes summary.md.
"""
import argparse, csv, html, json, math, os, subprocess, sys
from pathlib import Path

import numpy as np
import pyproj
from shapely import STRtree
from shapely.geometry import shape, LineString, Point, box
from shapely.ops import transform, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain import Terrain, FLAT_SOURCE
import roofs

DEFAULTS = {
    'step_m': 10,               # metres between ground samples along the line
    'beyond_m': 200,            # the line runs this far past the site at each end, so the neighbours show
    'behind_m': 80,             # buildings up to this far behind the cut stand in elevation
    'ground_behind_m': [20, 40, 60, 80],   # the ground behind the cut, drawn along lines this far back, so buildings behind stand on it
    'landscape_m': [300, 600, 1000],       # on the whole cut, the landscape further back: ground lines this far behind, palest farthest
    'tree_h': {'forest': 16, 'wood': 16, 'park': 10, 'scrub': 4},   # assumed tree heights by land use, m
    'tree_new': [10, 6],        # height and crown diameter of a design tree without height_m or crown_m, m
    'tree_band_m': 10,          # with --massing, the design's trees whose crown reaches the line or stand this far behind it
    'person_h': 1.75,           # height of a person for scale, m
    'floor_h': 3.0,             # storey height, only for existing buildings without a height
    'default_floors': 2,        # storeys of an existing building with neither height nor storeys
    'excerpt_m': 200,           # length of the excerpt at the detail scale, m
    'key_scale': 30000,         # scale of the key plan
    'label_min_gap_m': 80,      # the same street, railway or water is labelled once within this distance
    'land_classes': {           # plots' landuse -> what grows there (built and street: nothing)
        'forest': 'forest', 'natural:wood': 'wood', 'wood': 'wood', 'natural:scrub': 'scrub', 'scrub': 'scrub',
        'leisure:park': 'park', 'park': 'park', 'grass': 'grass', 'meadow': 'grass', 'farmland': 'grass',
        'leisure:pitch': 'grass', 'leisure:playground': 'grass', 'allotments': 'grass', 'village_green': 'grass',
        'leisure:nature_reserve': 'grass', 'brownfield': 'grass', 'orchard': 'park', 'cemetery': 'park',
        'residential': 'built', 'commercial': 'built', 'industrial': 'built', 'retail': 'built',
        'railway': 'built', 'construction': 'built', 'farmyard': 'built', 'leisure:sports_centre': 'built',
        'leisure:swimming_pool': 'water', 'natural:water': 'water', 'water': 'water', 'basin': 'water',
        'reservoir': 'water', 'quarry': 'street', 'landfill': 'street', 'natural:sand': 'street',
        'natural:bare_rock': 'street', 'leisure:track': 'street'},
    'angles': 15,               # degrees between the directions tried for the automatic line
    'offsets_m': [-300, -150, 0, 150, 300],   # sideways shifts from the site's centroid tried for the line
    'main_roads': ['motorway', 'trunk', 'primary', 'secondary'],   # highway classes that count as main streets
    'at_m': 100,                # the line counts as passing the given place within this distance
    'person_gap_m': 25,         # people on open ground every this many metres in the excerpt
    'png_dpi': 150,             # resolution of the PNGs
    'models_file': 'buildings-3d.geojson',   # the site folder's 3D building models, one surface per feature
    'model_overlap': 0.3,       # a model belongs to a footprint it covers by this share of the smaller of the two
}
C = DEFAULTS

# fallback look: black on white, greys, one accent. A standard overrides it through --style.
STYLE = {'paper': '#ffffff', 'ink': '#1a1a1a', 'accent': '#c8442b', 'new': '#ffffff', 'existing': '#cfcfcf',
         'context': '#e4e4e4', 'building': '#9a9a9a', 'street': '#f2f2f2', 'path': '#bcbcbc', 'park': '#c9dcbc',
         'grove': '#8f8f8f', 'lawn': '#dddddd', 'water': '#9ec5d8', 'font': 'Arial, Helvetica, sans-serif',
         'thin': 0.13, 'mid': 0.25, 'thick': 0.5, 'text': 3.2, 'title': 5.6}

ap = argparse.ArgumentParser(description='A long section through a site on its real ground.')
ap.add_argument('--site', required=True, help='the folder with site.geojson and its layers')
ap.add_argument('--proposal', required=True)
ap.add_argument('--scale', type=int, required=True, help="the brief's site plan scale, e.g. 3000")
ap.add_argument('--detail-scale', type=int, required=True, help="the brief's largest scale, e.g. 500")
ap.add_argument('--massing', action='store_true', help='draw on the design: new buildings from massing.geojson')
ap.add_argument('--line', nargs=2, metavar='LON,LAT', help='the line through two points instead of the automatic one')
ap.add_argument('--look', choices=['north', 'south', 'east', 'west'])
ap.add_argument('--at', metavar='LON,LAT', help='a centre or detail area the line should pass and the excerpt show')
ap.add_argument('--style')
ARGS = ap.parse_args()

SITE = Path(ARGS.site)
OUT = Path(ARGS.proposal) / 'site-section'
OUT.mkdir(parents=True, exist_ok=True)
style_path = ARGS.style or Path(ARGS.proposal) / 'drawing-graphics' / 'style.json'
USED_STYLE = bool(style_path) and os.path.exists(style_path)
if USED_STYLE:
    STYLE.update(json.load(open(style_path, encoding='utf-8')))
S = STYLE
FS = max(3.2, float(S.get('text', 3.2)))                 # text height in mm, never below 3.2
FT = max(FS, float(S.get('title', FS * 1.6)))
THIN, MID, THICK = (float(S.get(k, d)) for k, d in (('thin', 0.13), ('mid', 0.25), ('thick', 0.5)))
NOTES, MISSING = [], []


def utm_epsg(lon, lat):
    """The UTM zone of a point, as an EPSG code."""
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


def read_fc(path):
    return json.load(open(path, encoding='utf-8'))['features'] if path.exists() else None


site_f = read_fc(SITE / 'site.geojson')
if not site_f:
    sys.exit(f'no site.geojson in {SITE}: nothing to cut')
site_ll = unary_union([shape(f['geometry']) for f in site_f if f.get('geometry')])
EPSG = utm_epsg(site_ll.centroid.x, site_ll.centroid.y)
TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
TO_LL_T = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True)
TO_LL = TO_LL_T.transform
SITE_G = transform(TO_M, site_ll).buffer(0)


def layer(name):
    F = read_fc(SITE / f'{name}.geojson')
    if F is None:
        MISSING.append(name)
        return []
    out = []
    for f in F:
        if not f.get('geometry'):
            continue
        g = transform(TO_M, shape(f['geometry']))
        if g.geom_type.endswith('Polygon') and not g.is_valid:
            g = g.buffer(0)
        if not g.is_empty:
            out.append((f.get('properties') or {}, g))
    return out


def parts(g):
    return list(g.geoms) if hasattr(g, 'geoms') else [g]


def ll_point(s):
    lon, lat = (float(v) for v in s.split(','))
    return np.array(TO_M(lon, lat))


# ---------------------------------------------------------------- buildings: existing, and new with --massing
B = []   # dicts: g, h, floors, new, default
for p, g in layer('buildings'):
    h, fl, dflt = p.get('height'), p.get('floors'), False
    try:
        h = float(h) if h not in (None, '') else None
    except ValueError:
        h = None
    try:
        fl = int(float(fl)) if fl not in (None, '') else None
    except ValueError:
        fl = None
    if not h or h <= 0:
        fl = fl or C['default_floors']
        h, dflt = fl * C['floor_h'], True
    B.append(dict(g=g, h=h, floors=fl or max(1, round(h / C['floor_h'])), new=False, default=dflt,
                  id=None if p.get('id') in (None, '') else str(p['id'])))
NEW = []
if ARGS.massing:
    mf = read_fc(Path(ARGS.proposal) / 'massing' / 'massing.geojson')
    if mf is None:
        NOTES.append('No massing/massing.geojson: the design pass shows the site as it is.')
        MISSING.append('massing/massing.geojson')
    for f in mf or []:
        p = f.get('properties') or {}
        if p.get('kind') != 'building' or p.get('existing') or not f.get('geometry'):
            continue
        g = transform(TO_M, shape(f['geometry'])).buffer(0)
        fl = int(p.get('floors') or 0) or None
        h = float(p.get('height_m') or 0) or (fl or 1) * C['floor_h']
        NEW.append(dict(g=g, h=h, floors=fl or max(1, round(h / C['floor_h'])), new=True, default=False))
    if NEW:   # existing buildings under new ones are gone
        nt = STRtree([b['g'] for b in NEW])
        keep = []
        for b in B:
            gone = any(b['g'].intersection(NEW[j]['g']).area > 0.2 * min(b['g'].area, NEW[j]['g'].area)
                       for j in nt.query(b['g'], predicate='intersects'))
            if not gone:
                keep.append(b)
        NOTES.append(f'{len(B) - len(keep)} existing buildings under new ones are left out.')
        B = keep
B += NEW
BTREE = STRtree([b['g'] for b in B]) if B else None
TREES = []   # with --massing, the design's trees, the massing's and open-space's: (point, height, crown, assumed)
for f in (mf or []) + (read_fc(Path(ARGS.proposal) / 'open-space' / 'open-space.geojson') or []) if ARGS.massing else []:
    p = f.get('properties') or {}
    if p.get('kind') == 'tree' and (f.get('geometry') or {}).get('type') == 'Point':
        TREES.append((transform(TO_M, shape(f['geometry'])), float(p.get('height_m') or C['tree_new'][0]),
                      float(p.get('crown_m') or C['tree_new'][1]), not (p.get('height_m') and p.get('crown_m'))))

STREETS = layer('streets')
RAIL = layer('rail')
WATER = layer('water')
PLOTS = layer('plots')
STREET_LAND = layer('street-land')

# ---------------------------------------------------------------- the line
cen = np.array(SITE_G.centroid.coords[0])
x0, y0, x1, y1 = SITE_G.bounds
R = math.hypot(x1 - x0, y1 - y0) + C['beyond_m']


def span(origin, e):
    """First entry and last exit of the site along the infinite line origin + t * e."""
    ln = LineString([origin - e * R, origin + e * R])
    ins = ln.intersection(SITE_G)
    if ins.is_empty:
        return None
    ts = [ln.project(Point(c)) - R for q in parts(ins) for c in q.coords]
    return min(ts), max(ts)


def seg(origin, e, t0, t1):
    return LineString([origin + e * t0, origin + e * t1])


def crosses(items, line, test=lambda p: True):
    return any(test(p) and g.intersects(line) for p, g in items)


AT = ll_point(ARGS.at) if ARGS.at else None
choice, best, runner, cands = None, None, None, []
prev = OUT / 'cut.json'
if ARGS.line:
    p1, p2 = ll_point(ARGS.line[0]), ll_point(ARGS.line[1])
    e = (p2 - p1) / np.linalg.norm(p2 - p1)
    origin = p1
    sp = span(origin, e)
    if sp is None:
        sp = (0.0, float(np.linalg.norm(p2 - p1)))
        NOTES.append('The given line does not cross the site: drawn between its two points.')
    choice = 'given with --line'
elif ARGS.massing and prev.exists() and 'A' in json.load(open(prev, encoding='utf-8')):
    old = json.load(open(prev, encoding='utf-8'))
    pa, pb = ll_point('%f,%f' % tuple(old['A'])), ll_point('%f,%f' % tuple(old['A_prime']))
    e = (pb - pa) / np.linalg.norm(pb - pa)
    origin = pa
    sp = span(origin, e) or (0.0, float(np.linalg.norm(pb - pa)))
    choice = 'the same line as the earlier pass (cut.json)'
else:
    main = set(C['main_roads'])
    for ang in range(0, 180, C['angles']):
        e = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
        nrm = np.array([-e[1], e[0]])
        for off in C['offsets_m']:
            o = cen + nrm * off
            sp = span(o, e)
            if sp is None:
                continue
            s = seg(o, e, *sp)
            n = len(BTREE.query(s, predicate='intersects')) if BTREE else 0
            rail = crosses(RAIL, s)
            road = crosses(STREETS, s, lambda p: p.get('highway') in main)
            water = crosses(WATER, s)
            near = AT is not None and seg(o, e, sp[0] - C['beyond_m'], sp[1] + C['beyond_m']).distance(Point(AT)) <= C['at_m']
            cands.append(dict(angle=ang, offset_m=off, length_m=round(sp[1] - sp[0], 1), buildings=n, rail=rail,
                              main_street=road, water=water, at=near, o=o, e=e, sp=sp))
    if not cands:
        sys.exit('no line through the site found')
    longest = max(c['length_m'] for c in cands)
    for c in cands:
        c['score'] = round(min(2 * c['buildings'], 20) + 5 * (c['rail'] + c['main_street'] + c['water'])
                           + 10 * c['at'] - (longest - c['length_m']) / 100, 2)
    ranked = sorted(cands, key=lambda c: -c['score'])
    best, runner = ranked[0], (ranked[1] if len(ranked) > 1 else None)
    origin, e, sp = best['o'], best['e'], best['sp']
    choice = 'automatic'
    if all(c['buildings'] == 0 for c in cands):
        NOTES.append('No line tried crosses a building: give one with --line.')

# the direction of looking: --look, else north for a line running more east-west, east for one more north-south
LOOKS = {'north': (0, 1), 'south': (0, -1), 'east': (1, 0), 'west': (-1, 0)}
want = np.array(LOOKS[ARGS.look] if ARGS.look else (LOOKS['north'] if abs(e[0]) >= abs(e[1]) else LOOKS['east']), float)
if abs(float(np.dot(e, want))) > 0.98:
    NOTES.append(f'--look {ARGS.look} runs along the line; the default direction is used.')
    want = np.array(LOOKS['north'] if abs(e[0]) >= abs(e[1]) else LOOKS['east'], float)
if np.dot(np.array([-e[1], e[0]]), want) < 0:   # A on the left: the look is the line's left normal
    e = -e
    sp = (-sp[1], -sp[0])
V = np.array([-e[1], e[0]])
A = origin + e * (sp[0] - C['beyond_m'])
A2 = origin + e * (sp[1] + C['beyond_m'])
L = float(np.linalg.norm(A2 - A))
CUT = LineString([A, A2])
look_bearing = math.degrees(math.atan2(V[0], V[1])) % 360
LOOK = min(LOOKS, key=lambda k: abs(((math.degrees(math.atan2(*LOOKS[k])) % 360) - look_bearing + 180) % 360 - 180))


def tu(x, y):
    d = np.array([x, y]) - A
    return float(d @ e), float(d @ V)


def tpos(p):   # position along A-A' of a point
    return float((np.asarray(p) - A) @ e)


DTREES = [(t, h, cr) for (t, u), h, cr in ((tu(g.x, g.y), h, cr) for g, h, cr, _ in TREES)
          if -cr / 2 <= u <= C['tree_band_m'] and 0 <= t <= L]   # (t, height, crown) of the design's trees on the line
if ARGS.massing:
    NOTES.append(f'{len(DTREES)} of the design\'s {len(TREES)} trees reach the line or stand up to {C["tree_band_m"]} m behind it, '
                 f'drawn at their height and crown; {sum(a_ for *_, a_ in TREES)} of the {len(TREES)} have an assumed '
                 f'{C["tree_new"][0]} m height or {C["tree_new"][1]} m crown.')


# ---------------------------------------------------------------- buildings cut and behind
cut, behind = [], []
for i in (BTREE.query(CUT.buffer(C['behind_m'])) if BTREE else []):
    b = B[i]
    g = b['g']
    if g.intersects(CUT):
        for q in parts(g.intersection(CUT)):
            if q.geom_type == 'LineString' and q.length >= 0.5:
                ts = sorted(tpos(c) for c in q.coords)
                cut.append(dict(b=b, t0=ts[0], t1=ts[-1]))
        continue
    cs = [tu(*c) for q in parts(g) for c in q.exterior.coords]
    ts, us = [c[0] for c in cs], [c[1] for c in cs]
    if min(us) > 0 and min(us) <= C['behind_m'] and max(ts) > 0 and min(ts) < L:
        behind.append(dict(b=b, t0=min(ts), t1=max(ts), u=min(us)))

# ---------------------------------------------------------------- the ground: one call for every point
N = max(1, math.ceil(L / C['step_m']))
TS = np.linspace(0, L, N + 1)
PX, PY = A[0] + e[0] * TS, A[1] + e[1] * TS
bpts, owner = [], []
for k, item in enumerate(cut + behind):
    g = item['b']['g']
    vs = [c for q in parts(g) for c in q.exterior.coords[:-1]]
    vs = vs[::max(1, len(vs) // 8)][:8] + [g.centroid.coords[0]]
    bpts += vs
    owner += [k] * len(vs)
TERRAIN = Terrain.find(SITE, OUT, CUT.buffer(C['behind_m'] + 20).bounds, TO_LL_T)
allx = np.concatenate([PX, np.array([p[0] for p in bpts])]) if bpts else PX
ally = np.concatenate([PY, np.array([p[1] for p in bpts])]) if bpts else PY
Z_ALL = TERRAIN.sample(allx, ally)
ZS = Z_ALL[:len(TS)]
zb = Z_ALL[len(TS):]
owner = np.array(owner, int)
for k, item in enumerate(cut + behind):
    item['base'] = float(zb[owner == k].mean())
    item['low'] = float(zb[owner == k].min())   # its lowest ground: the wall reaches down to it


def ground(t):
    return np.interp(t, TS, ZS)


def behind_profile(u, fill=True):
    """The ground along a line u m behind the cut, at the cut's samples. Without fill: None where the terrain has no
    value along half the line or more, NaN where it has none, never the nearest value (that would draw a false, flat land)."""
    xs, ys = PX + V[0] * u, PY + V[1] * u
    if fill:
        return TERRAIN.sample(xs, ys)
    z = np.asarray(TERRAIN._sampler(xs, ys), float)
    return None if TERRAIN.flat or np.isfinite(z).mean() < 0.5 else z


BANDS, LANDSCAPE = [], []   # far to near
if not TERRAIN.flat:
    BANDS = [(u, behind_profile(u)) for u in sorted(C['ground_behind_m'], reverse=True) if 0 < u <= C['behind_m']]
    for u in sorted(C['landscape_m'], reverse=True):
        z = behind_profile(u, fill=False)
        if z is None:
            NOTES.append(f'The terrain has no ground {u:g} m behind the cut along half of it or more: that landscape line is left out.')
        else:
            LANDSCAPE.append((u, z))


for c in cut:   # down to the lowest ground under it, so it never floats; the earth hides the rest
    c['bottom'] = min(c['base'], float(ground(np.linspace(c['t0'], c['t1'], 5)).min()))

# ---------------------------------------------------------------- roofs: from the 3D models, else flat at the height
MODELS = {}
if (SITE / C['models_file']).exists():
    MODELS = roofs.models(SITE / C['models_file'], TO_M, CUT.buffer(C['behind_m'] + 50).bounds)
else:
    NOTES.append(f'No {C["models_file"]} in the site folder: every roof is a flat top at its height.')
ABS_Z = False
if MODELS:
    keys = list(MODELS)
    mtree = STRtree([MODELS[k_]['foot'] for k_ in keys])
    for item in cut + behind:
        b = item['b']
        if b['new'] or 'faces' in b:
            continue
        b['faces'], zmins = [], []
        for j in mtree.query(b['g'], predicate='intersects'):
            m = MODELS[keys[j]]
            if keys[j] == b['id'] or (b['g'].intersection(m['foot']).area
                                      >= C['model_overlap'] * min(b['g'].area, m['foot'].area)):
                b['faces'] += m['faces']
                zmins.append(m['zmin'])
        b['model_zmin'] = min(zmins) if zmins else None
    # z above sea level, or above each building's lowest ground: whichever the models' feet sit closer to
    feet = [(it['b']['model_zmin'], it['low']) for it in cut + behind if it['b'].get('faces')]
    ABS_Z = bool(feet) and sum(abs(zm - lo) < abs(zm) for zm, lo in feet) > len(feet) / 2


def footprint_t(g):
    ts = [tpos(c_) for q in parts(g) for c_ in q.exterior.coords]
    return min(ts), max(ts)


for is_cut, items in ((True, cut), (False, behind)):
    for item in items:
        b = item['b']
        off = 0.0 if ABS_Z else item['low']
        pts = []
        if b.get('faces'):
            pts = (roofs.cut if is_cut else roofs.silhouette)(b['faces'], A, e, V, item['t0'], item['t1'])
        item['model'] = bool(pts)
        item['roof'] = ([(t, z + off) for t, z in pts] if pts else
                        [(item['t0'], item['base'] + b['h']), (item['t1'], item['base'] + b['h'])])
        item['top'] = max(z for _, z in item['roof'])
        if is_cut and pts:   # what of the cut building stands behind the cut, in elevation
            back = roofs.silhouette(b['faces'], A, e, V, *footprint_t(b['g']), front=0.0)
            item['back'] = [(t, z + off) for t, z in back]
            item['top'] = max([item['top']] + [z for _, z in item['back']])


def roof_count(items):
    by = {}
    for it in items:
        if not it['b']['new']:
            by.setdefault(id(it['b']), []).append(it)
    model = [v for v in by.values() if any(it['model'] for it in v)]
    return dict(from_model=len(model), pitched=sum(any(roofs.pitched(it['roof']) for it in v) for v in model),
                flat_no_model=len(by) - len(model))


ROOFS = dict(models=C['models_file'] if MODELS else None,
             z=None if not MODELS else 'above sea level' if ABS_Z else "above each building's lowest ground",
             cut=roof_count(cut), behind=roof_count(behind),
             new_flat=len({id(it['b']) for it in cut + behind if it['b']['new']}))

# fall and rise: the largest drop and the largest climb from A to A'
run_max, run_min, fall, rise = ZS[0], ZS[0], 0.0, 0.0
for z in ZS:
    fall, rise = max(fall, run_max - z), max(rise, z - run_min)
    run_max, run_min = max(run_max, z), min(run_min, z)

with open(OUT / 'profile.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['t_m_from_A', 'lon', 'lat', 'z_m_asl', 'source'])
    for t, x, y, z in zip(TS, PX, PY, ZS):
        lon, lat = TO_LL(x, y)
        w.writerow([round(float(t), 1), round(lon, 7), round(lat, 7), round(float(z), 2), TERRAIN.source])

# ---------------------------------------------------------------- land use under the line
ptree = STRtree([g for _, g in PLOTS]) if PLOTS else None
ltree = STRtree([g for _, g in STREET_LAND]) if STREET_LAND else None


def in_cut(t):
    return any(c['t0'] - 0.5 <= t <= c['t1'] + 0.5 for c in cut)


def land(t):
    if in_cut(t):
        return 'built'
    pt = Point(A + e * t)
    if ltree is not None and len(ltree.query(pt, predicate='within')):
        return 'street'
    if any(pt.within(g) for _, g in WATER if g.geom_type.endswith('Polygon')):
        return 'water'
    if ptree is None:
        return 'none'
    hits = [PLOTS[i] for i in ptree.query(pt, predicate='within')]
    if not hits:
        return 'none'
    p = min(hits, key=lambda h: h[1].area)[0]
    lu = p.get('landuse') or p.get('leisure') or p.get('natural') or ''
    return C['land_classes'].get(lu, 'none')


LAND = [land(float(t)) for t in TS]

# ---------------------------------------------------------------- crossings and labels
labels = []   # (t, text, colour)


def add_label(t, text, colour=None, gap=True):
    if gap and any(n == text and abs(t - t2) < C['label_min_gap_m'] for t2, n, _ in labels):
        return
    labels.append((t, text, colour))


def cross_ts(g):
    out = []
    for q in parts(g.intersection(CUT)):
        if q.is_empty:
            continue
        out.append(tpos(q.coords[0]) if q.geom_type == 'Point' else tpos(q.interpolate(0.5, normalized=True).coords[0]))
    return out


for p, g in STREETS:
    name = p.get('name') or p.get('ref')
    if name and g.intersects(CUT):
        for t in cross_ts(g):
            add_label(t, str(name))
rail_ts = sorted(t for _, g in RAIL if g.intersects(CUT) for t in cross_ts(g))
groups = []
for t in rail_ts:   # a double track is one label
    if groups and t - groups[-1][-1] < C['label_min_gap_m']:
        groups[-1].append(t)
    else:
        groups.append([t])
for gr in groups:
    add_label(sum(gr) / len(gr), 'Railway', gap=False)
for p, g in WATER:
    if g.intersects(CUT):
        for t in cross_ts(g):
            add_label(t, str(p.get('name') or 'Water'))
SITE_TS = sorted(tpos(q.coords[0]) for q in parts(SITE_G.boundary.intersection(CUT)) if q.geom_type == 'Point')
for t in SITE_TS:
    add_label(t, 'Site boundary', S['accent'], gap=False)
labels.sort()

# ---------------------------------------------------------------- the excerpt's place
if AT is not None:
    tc, why = tpos(AT), 'around the place given with --at'
else:
    newcut = sorted((c for c in cut if c['b']['new']), key=lambda c: c['t0'])
    edge = next((c for c in newcut if not in_cut(c['t0'] - 5)), None)
    if edge:
        tc, why = edge['t0'], 'where a new building meets open ground'
    else:
        tc, why = (SITE_TS[0] + SITE_TS[-1]) / 2 if SITE_TS else L / 2, "around the site's centre"
half = C['excerpt_m'] / 2
E0 = min(max(0.0, tc - half), max(0.0, L - C['excerpt_m']))
E1 = min(L, E0 + C['excerpt_m'])


# ---------------------------------------------------------------- drawing
def mix(c1, c2, f):
    a = [int(c1.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    return '#%02x%02x%02x' % tuple(round(x + (y - x) * f) for x, y in zip(a, b))


def esc(s):
    return html.escape(str(s), quote=True)


def text(x, y, s, size=FS, anchor='start', fill=None, weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size:.2f}" text-anchor="{anchor}" '
            f'fill="{fill or S["ink"]}"{w}>{esc(s)}</text>')


def text_w(s, size=FS):
    return len(str(s)) * size * 0.56


def nice_step(lo_mm, k):
    for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if s * k >= lo_mm:
            return s
    return 1000


def scale_bar(x, y, scale):
    k = 1000 / scale
    total = nice_step(55, k) if nice_step(55, k) * k <= 90 else nice_step(40, k)
    n = 5 if str(total)[0] in '15' else 4
    step = total / n
    d = ''.join(f'M{x + i * step * k:.2f},{y + 1.2 * (i % 2):.2f}h{step * k:.2f}' for i in range(n))
    d += ''.join(f'M{x + i * step * k:.2f},{y:.2f}v1.2' for i in range(n + 1))
    o = [f'<path d="{d}" fill="none" stroke="{S["ink"]}" stroke-width="{THIN}"/>']
    for i in range(n + 1):
        v = step * i
        o.append(text(x + i * step * k, y + 1.2 + FS * 1.2, f'{v:g}' + (' m' if i == n else ''), anchor='middle'))
    return o, total * k


def tree(x, yg, h_mm, r=None):
    r = r or h_mm * 0.28
    return (f'<line x1="{x:.2f}" y1="{yg:.2f}" x2="{x:.2f}" y2="{yg - h_mm + r:.2f}" stroke="{S["grove"]}" stroke-width="{THIN}"/>'
            f'<circle cx="{x:.2f}" cy="{yg - h_mm + r:.2f}" r="{r:.2f}" fill="{S["grove"]}" fill-opacity="0.85"/>')


def person(x, yg, h):
    hr = h * 0.09
    return (f'<g stroke="{S["ink"]}" stroke-width="{THIN}" fill="none" stroke-linecap="round">'
            f'<circle cx="{x:.2f}" cy="{yg - h + hr:.2f}" r="{hr:.2f}" fill="{S["ink"]}" stroke="none"/>'
            f'<path d="M{x:.2f},{yg - h + 2 * hr:.2f}V{yg - h * 0.45:.2f}M{x - h * 0.12:.2f},{yg:.2f}L{x:.2f},{yg - h * 0.45:.2f}'
            f'L{x + h * 0.12:.2f},{yg:.2f}M{x - h * 0.16:.2f},{yg - h * 0.62:.2f}L{x:.2f},{yg - h * 0.78:.2f}'
            f'L{x + h * 0.16:.2f},{yg - h * 0.62:.2f}"/></g>')


def key_plan(x, y):
    km = 1000 / C['key_scale']
    ext = unary_union([CUT, SITE_G]).buffer(150)
    bx0, by0, bx1, by1 = ext.bounds
    kw, kh = (bx1 - bx0) * km, (by1 - by0) * km
    P = lambda px, py: (x + (px - bx0) * km, y + (by1 - py) * km)

    def path(g):
        out = ''
        for q in parts(g):
            rings = [q.exterior, *q.interiors] if q.geom_type == 'Polygon' else [q]
            for r in rings:
                out += 'M' + 'L'.join('%.2f,%.2f' % P(*c) for c in r.coords) + ('Z' if q.geom_type == 'Polygon' else '')
        return out
    win = box(bx0, by0, bx1, by1)
    o = [f'<clipPath id="kp"><rect x="{x:.2f}" y="{y:.2f}" width="{kw:.2f}" height="{kh:.2f}"/></clipPath>',
         f'<rect x="{x:.2f}" y="{y:.2f}" width="{kw:.2f}" height="{kh:.2f}" fill="{S["paper"]}" stroke="{S["ink"]}" stroke-width="{THIN}"/>',
         '<g clip-path="url(#kp)">']
    old = ''.join(path(b['g'].simplify(1)) for b in B if not b['new'] and b['g'].intersects(win))
    new = ''.join(path(b['g'].simplify(1)) for b in B if b['new'] and b['g'].intersects(win))
    o.append(f'<path d="{old}" fill="{S["existing"]}" stroke="none"/>')
    if new:
        o.append(f'<path d="{new}" fill="{S["accent"]}" stroke="none"/>')
    rails = ''.join(path(g) for _, g in RAIL if g.intersects(win))
    if rails:
        o.append(f'<path d="{rails}" fill="none" stroke="{S["ink"]}" stroke-width="{THIN}" stroke-dasharray="1 0.6"/>')
    o.append(f'<path d="{path(SITE_G)}" fill="none" stroke="{S["accent"]}" stroke-width="{MID}"/>')
    o.append(f'<path d="{path(CUT)}" fill="none" stroke="{S["ink"]}" stroke-width="{THICK}"/>')
    o.append('</g>')
    for pt, name, anc in ((A, 'A', 'end'), (A2, 'A′', 'start')):
        px, py = P(*pt)
        o.append(text(px + (-1.2 if anc == 'end' else 1.2), py - 1, name, anchor=anc, weight='bold'))
    nx, ny, r = x + kw - 5, y + 5, 3   # north: a circle in outline and one line from its centre to the circle
    o.append(f'<circle cx="{nx:.2f}" cy="{ny:.2f}" r="{r}" fill="{S["paper"]}" stroke="{S["ink"]}" stroke-width="{THIN}"/>'
             f'<line x1="{nx:.2f}" y1="{ny:.2f}" x2="{nx:.2f}" y2="{ny - r:.2f}" stroke="{S["ink"]}" stroke-width="{THIN}"/>')
    o.append(text(x, y + kh + FS * 1.3, f'Key plan 1:{C["key_scale"]:,}'.replace(',', ' ')))
    return o, kw, kh + FS * 1.6


def draw(w0, w1, scale, detail, name):
    k = 1000 / scale
    inwin = lambda a, b: b > w0 and a < w1
    sel_cut = [c for c in cut if inwin(c['t0'], c['t1'])]
    sel_beh = sorted((c for c in behind if inwin(c['t0'], c['t1'])), key=lambda c: -c['u'])
    m = (TS >= w0 - C['step_m']) & (TS <= w1 + C['step_m'])
    zwin = np.concatenate([ground(np.array([w0, w1])), ZS[(TS >= w0) & (TS <= w1)]])
    ztops = [c['top'] for c in sel_cut + sel_beh] + [float(zwin.max()) + max([*C['tree_h'].values(), *(h for _, h, _ in DTREES)])]
    ztops += [float(np.nanmax(z[m])) for u, z in BANDS + ([] if detail else LANDSCAPE) if np.isfinite(z[m]).any()]
    zmin = float(zwin.min())
    step = nice_step(FS * 1.4, k)
    zbase = math.floor((zmin - max(4.0, 0.1 * (float(zwin.max()) - zmin))) / step) * step
    ztop = max(ztops) + 2
    gut = text_w('0000', FS) + 6
    lab_rows = []   # rows of (x0, x1)
    placed = []
    for t, s, col in labels:
        if not (w0 <= t <= w1):
            continue
        xm = gut + (t - w0) * k
        half = text_w(s) / 2 + 1
        for r, row in enumerate(lab_rows):
            if all(xm + half < a or xm - half > b for a, b in row):
                row.append((xm - half, xm + half)); placed.append((t, s, col, r)); break
        else:
            lab_rows.append([(xm - half, xm + half)]); placed.append((t, s, col, len(lab_rows) - 1))
    W = gut + (w1 - w0) * k + 12
    key = key_plan(0, 0) if not detail else None   # in the bottom-right corner, beside the caption
    top = 6
    row_h = FS * 1.5
    lab_top = top + FT
    sec_top = lab_top + len(lab_rows) * row_h + 3
    Y = lambda z: sec_top + (ztop - z) * k
    X = lambda t: gut + (t - w0) * k
    what = 'on the design' if ARGS.massing else 'the site as it is'
    part = f'excerpt, {w0:.0f}–{w1:.0f} m from A' if detail else f'{L:.0f} m'
    caption = [f'Section A–A′, {what}, {part}, looking {LOOK}, 1:{scale}, heights not exaggerated',
               f'Ground: {TERRAIN.source}' + ('' if TERRAIN.flat else
               '; trees assumed ' + ', '.join(f'{c} {h} m' for c, h in C['tree_h'].items()))]
    H = Y(zbase) + 6 + max(FS * 7.5, key[2] + 4 if key else 0)
    W = max(W, gut + max(text_w(c) for c in caption) + (key[1] + 16 if key else 6))
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" height="{H:.1f}mm" viewBox="0 0 {W:.2f} {H:.2f}" '
         f'font-family="{esc(S["font"])}">', f'<rect width="{W:.2f}" height="{H:.2f}" fill="{S["paper"]}"/>',
         f'<clipPath id="win"><rect x="{gut:.2f}" y="0" width="{(w1 - w0) * k:.2f}" height="{H:.2f}"/></clipPath>',
         '<g clip-path="url(#win)">']
    def outline(roof, bottom):   # the wall up from its ground, along the roof or the flat top, and down again
        pts = [(roof[0][0], bottom)] + roof + [(roof[-1][0], bottom)]
        return 'M' + 'L'.join(f'{X(t):.2f},{Y(z):.2f}' for t, z in pts) + 'Z'

    def floors(c, d_out, stroke):   # floor lines, inside the building's outline only
        b = c['b']
        if not (detail and b['floors'] > 1):
            return
        cid = f'f{len(o)}'
        fh = b['h'] / b['floors']
        d = ''.join(f'M{X(c["t0"]):.2f},{Y(c["base"] + i * fh):.2f}h{(c["t1"] - c["t0"]) * k:.2f}' for i in range(1, b['floors']))
        o.append(f'<clipPath id="{cid}"><path d="{d_out}"/></clipPath>'
                 f'<path d="{d}" stroke="{stroke}" stroke-width="{THIN}" clip-path="url(#{cid})"/>')

    def behind_ground(z, cls, f):   # a ground behind the cut, from its line down to the drawing's base, f of the way to paper
        r, runs = [], []
        for t, zv in zip(TS[m], np.maximum(z[m], zbase)):   # NaN stays NaN: no ground known there
            if np.isfinite(zv):
                r.append((t, zv))
            elif r:
                runs.append(r); r = []
        runs.append(r)
        for r in (r for r in runs if len(r) > 1):
            top = 'L'.join(f'{X(t):.2f},{Y(zv):.2f}' for t, zv in r)
            o.append(f'<path class="{cls}" d="M{top}L{X(r[-1][0]):.2f},{Y(zbase):.2f}L{X(r[0][0]):.2f},{Y(zbase):.2f}Z" '
                     f'fill="{mix(S["context"], S["paper"], f)}" stroke="none"/>')
            o.append(f'<path d="M{top}" fill="none" stroke="{mix(S.get("building", "#9a9a9a"), S["paper"], f)}" stroke-width="{THIN}"/>')

    def behind_building(c):   # lighter the farther, on its own ground
        b = c['b']
        fill = mix(S['new'] if b['new'] else S['existing'], S['paper'], 0.25 + 0.4 * c['u'] / C['behind_m'])
        stroke = mix(S['ink'], S['paper'], 0.3) if b['new'] else S.get('building', '#9a9a9a')   # white ones keep their outline
        d_out = outline(c['roof'], c['low'])
        o.append(f'<path d="{d_out}" fill="{fill}" stroke="{stroke}" stroke-width="{THIN}"/>')
        floors(c, d_out, stroke)

    # far to near: the landscape (whole cut only), then the ground behind the cut in bands with the buildings standing
    # on it, so a band hides the feet of the buildings behind it and none floats above the cut
    if not detail:
        for i, (u, z) in enumerate(LANDSCAPE):
            behind_ground(z, 'landscape', 0.85 - 0.25 * i / max(1, len(LANDSCAPE) - 1))
    beh = list(sel_beh)
    for i, (u, z) in enumerate(BANDS):
        while beh and beh[0]['u'] >= u:
            behind_building(beh.pop(0))
        behind_ground(z, 'ground-behind', 0.55 - 0.35 * i / max(1, len(BANDS) - 1))
    for c in beh:
        behind_building(c)
    # what of the cut buildings stands behind the cut, nearest of all
    for c in sel_cut:
        if c.get('back'):
            o.append(f'<path d="{outline(c["back"], c["low"])}" fill="{mix(S["existing"], S["paper"], 0.25)}" '
                     f'stroke="{S.get("building", "#9a9a9a")}" stroke-width="{THIN}"/>')
    # the design's trees on and just behind the line, at their height and crown, before the cut buildings
    for t, h, cr in DTREES:
        if w0 <= t <= w1:
            o.append(tree(X(t), Y(float(ground(t))), h * k, cr / 2 * k))
    # buildings cut, the strongest tone, the roof cut along the line where there is a model
    for c in sel_cut:
        b = c['b']
        fill = S['new'] if b['new'] else S['ink']
        d_out = outline(c['roof'], c['bottom'])
        o.append(f'<path d="{d_out}" fill="{fill}" stroke="{S["ink"]}" stroke-width="{MID if b["new"] else THIN}"/>')
        floors(c, d_out, mix(S['new'], S['ink'], 0.5) if b['new'] else S['paper'])
    # the earth, cut, and the ground line
    tt = np.concatenate([[w0], TS[(TS > w0) & (TS < w1)], [w1]])
    gl = 'L'.join('%.2f,%.2f' % (X(t), Y(z)) for t, z in zip(tt, ground(tt)))
    o.append(f'<path d="M{gl}L{X(w1):.2f},{Y(zbase):.2f}L{X(w0):.2f},{Y(zbase):.2f}Z" fill="{S["context"]}" stroke="none"/>')
    # plants by land use, water on the ground
    grass, water = [], []
    for t, cl in zip(TS, LAND):
        if not (w0 <= t <= w1):
            continue
        if cl in C['tree_h']:
            o.append(tree(X(t), Y(float(ground(t))), C['tree_h'][cl] * k))
        elif cl == 'grass':
            grass.append(t)
        elif cl == 'water':
            water.append(t)
    gd = ''
    for t in grass:   # grass ticks every 1.5 mm on paper over the step
        for x in np.arange(X(t - C['step_m'] / 2), X(t + C['step_m'] / 2), 1.5):
            yg = Y(float(ground(w0 + (x - gut) / k)))
            gd += f'M{x:.2f},{yg:.2f}l-0.3,-0.9M{x:.2f},{yg:.2f}l0.3,-0.8'
    if gd:
        o.append(f'<path d="{gd}" fill="none" stroke="{S["grove"]}" stroke-width="{THIN}"/>')
    for t in water:
        o.append(f'<line x1="{X(t - C["step_m"] / 2):.2f}" y1="{Y(float(ground(t))):.2f}" x2="{X(t + C["step_m"] / 2):.2f}" '
                 f'y2="{Y(float(ground(t))):.2f}" stroke="{S["water"]}" stroke-width="{THICK * 2}"/>')
    if detail:   # people on open ground every person_gap_m and beside the cut buildings' doors
        spots = [t for t in np.arange(w0 + 5, w1, C['person_gap_m']) if land(float(t)) not in ('built', 'water')]
        spots += [c['t1'] + 2 for c in sel_cut if not in_cut(c['t1'] + 2)]
        for t in spots:
            if w0 < t < w1:
                o.append(person(X(t), Y(float(ground(t))), C['person_h'] * k))
    o.append(f'<path d="M{gl}" fill="none" stroke="{S["ink"]}" stroke-width="{THICK}" stroke-linejoin="round"/>')
    o.append('</g>')
    # site boundary and labels
    for t, s, col, r in placed:
        yl = lab_top + (len(lab_rows) - 1 - r) * row_h
        x = X(t)
        colour = col or S['ink']
        dash = ' stroke-dasharray="1.2 0.8"' if col else ''
        yend = Y(zbase) if col else Y(float(ground(t)))
        o.append(f'<line x1="{x:.2f}" y1="{yl + 1:.2f}" x2="{x:.2f}" y2="{yend:.2f}" stroke="{colour}" '
                 f'stroke-width="{MID if col else THIN}"{dash}/>')
        o.append(text(min(max(x, gut + text_w(s) / 2), W - text_w(s) / 2 - 1), yl, s, anchor='middle', fill=colour))
    # A and A'
    if w0 <= 0.5:
        o.append(text(gut + 1, Y(float(ground(0.0))) - 2, 'A', FT, weight='bold'))
    if w1 >= L - 0.5:
        o.append(text(X(L) - 1, Y(float(ground(L))) - 2, 'A′', FT, anchor='end', weight='bold'))
    # heights above sea level, at the left
    hx = gut - 2
    zt = math.floor(ztop / step) * step
    o.append(f'<line x1="{hx:.2f}" y1="{Y(zbase):.2f}" x2="{hx:.2f}" y2="{Y(zt):.2f}" stroke="{S["ink"]}" stroke-width="{THIN}"/>')
    for z in np.arange(zbase, zt + 0.1, step):
        o.append(f'<line x1="{hx - 1:.2f}" y1="{Y(z):.2f}" x2="{hx:.2f}" y2="{Y(z):.2f}" stroke="{S["ink"]}" stroke-width="{THIN}"/>')
        o.append(text(hx - 1.5, Y(z) + FS * 0.35, f'{z:g}', anchor='end'))
    o.append(text(1, Y(zt) - FS * 0.9, 'm' if TERRAIN.flat else 'm a.s.l.'))
    # scale bar and caption
    yb = Y(zbase) + 5
    sb, sbw = scale_bar(gut, yb, scale)
    o += sb
    for i, c in enumerate(caption):
        o.append(text(gut, yb + 1.2 + FS * (2.8 + 1.4 * i), c))
    if key:
        kx = W - key[1] - 6
        o.append(f'<g transform="translate({kx:.2f},{Y(zbase) + 4:.2f})">')
        o += key[0]
        o.append('</g>')
    o.append('</svg>')
    svg = OUT / f'{name}.svg'
    svg.write_text('\n'.join(o), encoding='utf-8')
    shot(svg, OUT / f'{name}.png', W, H)
    return dict(svg=svg.name, width_mm=round(W, 1), height_mm=round(H, 1))


def find_browser():
    for e_ in [r'C:/Program Files/Google/Chrome/Application/chrome.exe',
               r'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
               r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
               r'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
               '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
               '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge']:
        if os.path.exists(e_):
            return e_
    import shutil
    for n in ('google-chrome', 'chromium', 'chromium-browser', 'msedge', 'chrome'):
        if shutil.which(n):
            return shutil.which(n)
    return None


BROWSER = find_browser()


def shot(svg, png, w_mm, h_mm):
    """A PNG of the SVG at png_dpi (less for a very long drawing), by a headless Chrome or Edge."""
    if not BROWSER:
        if 'no browser' not in ' '.join(NOTES):
            NOTES.append('No Chrome or Edge found: no PNGs made.')
        return
    dpi = min(C['png_dpi'], 16000 * 25.4 / max(w_mm, h_mm))
    w, h = round(w_mm / 25.4 * dpi), round(h_mm / 25.4 * dpi)
    page = svg.with_name(svg.stem + '_wrap.html')
    page.write_text(f'<html><body style="margin:0"><img src="{svg.name}" style="width:{w}px;height:{h}px"></body></html>',
                    encoding='utf-8')
    subprocess.run([BROWSER, '--headless', '--disable-gpu', '--hide-scrollbars', f'--screenshot={png.resolve()}',
                    f'--window-size={w},{h}', page.resolve().as_uri()], capture_output=True, timeout=180)
    page.unlink()
    if not png.exists():
        NOTES.append(f'{png.name} was not made: the browser failed.')


tag = '_design' if ARGS.massing else ''
whole = draw(0.0, L, ARGS.scale, False, f'site-section{tag}_1-{ARGS.scale}')
part = draw(E0, E1, ARGS.detail_scale, True, f'site-section{tag}_excerpt_1-{ARGS.detail_scale}')

n_default = sum(1 for c in cut + behind if c['b']['default'])
info = {
    'pass': 'design' if ARGS.massing else 'site as it is',
    'A': [round(v, 7) for v in TO_LL(*A)], 'A_prime': [round(v, 7) for v in TO_LL(*A2)],
    'length_m': round(L, 1), 'bearing_A_to_A_prime_deg': round(math.degrees(math.atan2(e[0], e[1])) % 360, 1),
    'look': LOOK, 'look_bearing_deg': round(look_bearing, 1), 'choice': choice,
    'score': best['score'] if best else None, 'runner_up_score': runner['score'] if runner else None,
    'chosen': {k_: v for k_, v in best.items() if k_ not in ('o', 'e', 'sp')} if best else None,
    'candidates': [[c['angle'], c['offset_m'], c['length_m'], c['buildings'], int(c['rail']), int(c['main_street']),
                    int(c['water']), int(c['at']), c['score']] for c in cands],
    'candidate_columns': ['angle_deg', 'offset_m', 'length_m', 'buildings', 'rail', 'main_street', 'water', 'at', 'score'],
    'site_boundary_t_m': [round(t, 1) for t in SITE_TS],
    'cut': len(cut), 'behind': len(behind),
    'new_cut': sum(1 for c in cut if c['b']['new']), 'new_behind': sum(1 for c in behind if c['b']['new']),
    'heights_by_default': n_default,
    'roofs': ROOFS,
    'fall_m': round(float(fall), 1), 'rise_m': round(float(rise), 1),
    'z_A': round(float(ZS[0]), 1), 'z_A_prime': round(float(ZS[-1]), 1),
    'z_min': round(float(ZS.min()), 1), 'z_max': round(float(ZS.max()), 1),
    'terrain': TERRAIN.source, 'terrain_gaps_filled': TERRAIN.gaps,
    'ground_behind_m': [u for u, _ in BANDS], 'landscape_m': [u for u, _ in LANDSCAPE],
    'excerpt_t_m': [round(E0, 1), round(E1, 1)], 'excerpt_why': why,
    'labels': [[round(t, 1), s] for t, s, _ in labels],
    'drawings': [whole, part],
}
(OUT / 'cut.json').write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding='utf-8')

lines = [f'# Site section, {info["pass"]}', '',
         f'- Line: {choice}; {L:.0f} m from A to A′, {C["beyond_m"]} m past the site at each end, looking {LOOK}.']
if best:
    lines.append(f'- Chosen of {len(cands)} lines (every {C["angles"]}°, offsets {C["offsets_m"]} m): score {best["score"]}'
                 f' (runner-up {runner["score"] if runner else "none"}); it cuts {best["buildings"]} buildings in the site'
                 + ''.join(f', crosses {n}' for n, f_ in (('the railway', best['rail']), ('a main street', best['main_street']),
                                                         ('water', best['water'])) if f_)
                 + (', passes the place given with --at' if best['at'] else '') + '.')
if TERRAIN.flat:
    lines.append('- The ground is drawn flat: no terrain was found, so the heights are relative, not above sea level.')
else:
    lines.append(f'- Ground: {TERRAIN.source}, sampled every {L / N:.1f} m; no vertical exaggeration; '
                 f'{TERRAIN.gaps} gaps filled from the nearest sample.')
lines += [f'- Ground falls up to {fall:.1f} m and rises up to {rise:.1f} m along the line ({ZS.min():.1f}–{ZS.max():.1f} m).',
          f'- {len(cut)} buildings cut, {len(behind)} behind within {C["behind_m"]} m'
          + (f' ({info["new_cut"]} and {info["new_behind"]} of them new, heights from the massing)' if ARGS.massing else '')
          + f'; {n_default} heights are defaults ({C["default_floors"]} storeys of {C["floor_h"]} m).',
          (f'- Roofs from {ROOFS["models"]} (z {ROOFS["z"]}): {ROOFS["cut"]["from_model"]} cut buildings cut along the line'
           f' ({ROOFS["cut"]["pitched"]} pitched), {ROOFS["behind"]["from_model"]} behind as their roof silhouette'
           f' ({ROOFS["behind"]["pitched"]} pitched); a flat top at the measured height where there is no model:'
           f' {ROOFS["cut"]["flat_no_model"]} cut, {ROOFS["behind"]["flat_no_model"]} behind'
           + (f'; {ROOFS["new_flat"]} new buildings flat at the massing height.' if ARGS.massing else '.')
           if ROOFS['models'] else '- Roofs: no 3D building models, every roof a flat top at its height.'),
          '- Tree heights assumed: ' + ', '.join(f'{c} {h} m' for c, h in C['tree_h'].items()) + '; person '
          + f'{C["person_h"]} m.',
          f'- Excerpt {E0:.0f}–{E1:.0f} m from A, {why}.',
          (f'- Ground behind the cut drawn at {", ".join(f"{u:g}" for u, _ in BANDS[::-1])} m; landscape lines on the whole cut at '
           + (", ".join(f"{u:g}" for u, _ in LANDSCAPE[::-1]) + ' m behind.' if LANDSCAPE else 'none (no terrain that far).')
           if BANDS else '- No ground behind the cut and no landscape lines: the ground is flat.')]
if MISSING:
    lines.append('- Missing, not drawn: ' + ', '.join(MISSING) + '.')
lines += [f'- {n}' for n in TERRAIN.notes + NOTES]
lines.append('- Look: ' + (f'drawing standard ({style_path}).' if USED_STYLE else 'fallback, black on white with one accent.'))
(OUT / 'assumptions.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(json.dumps({k_: info[k_] for k_ in ('choice', 'score', 'runner_up_score', 'cut', 'behind', 'new_cut', 'new_behind',
                                          'fall_m', 'rise_m', 'terrain', 'look', 'length_m', 'roofs')}, ensure_ascii=False))
