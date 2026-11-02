"""Massing on a structure plan, checked against the brief's programme.

    python massing.py --proposal <proposal folder> --site <site folder> --config <proposal>/massing/config.json

config.json holds the brief's values, each as {"value": ..., "source": "<file> p. N" or "assumption: ..."}:
every key in BRIEF. DEFAULTS are the skill's own and config.json may override them. `density` maps each
structure-plan neighbourhood name to low, medium, high, urban or commercial; `phase1` lists the first
phase's neighbourhoods. Writes massing.geojson, areas.csv, stats.json and assumptions.md into <proposal>/massing/.
"""
import argparse, json, math, sys, csv, os
from shapely.geometry import shape, mapping, Polygon, LineString, Point, box, MultiPolygon
from shapely.ops import transform, unary_union
from shapely import affinity
import pyproj


def utm_epsg(lon, lat):
    """The UTM zone of a point, as an EPSG code."""
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


def read_config(path, required=()):
    """config.json: {key: {"value": ..., "source": ...}} or {key: value}. Stops on a missing key."""
    raw = json.load(open(path, encoding='utf8'))
    # a value left empty (null) or a source still in <angle brackets> counts as not filled in
    raw = {k: v for k, v in raw.items() if not (isinstance(v, dict) and (v.get('value') is None
           or str(v.get('source', '')).startswith('<')))}
    missing = [k for k in required if k not in raw]
    if missing:
        sys.exit('missing in config.json: ' + ', '.join(missing) + ' (from the brief, with its page)')
    values = {k: (v['value'] if isinstance(v, dict) and 'value' in v else v) for k, v in raw.items()}
    sources = {k: (v.get('source', '') if isinstance(v, dict) else '') for k, v in raw.items()}
    return values, sources


A = argparse.ArgumentParser(description='Massing on a structure plan.')
A.add_argument('--proposal', required=True)
A.add_argument('--site', required=True, help='the folder with site.geojson and its layers')
A.add_argument('--config', required=True)
ARGS = A.parse_args()
RUN = os.path.join(ARGS.proposal, '')
OUT = os.path.join(RUN, 'massing', '')
SITE = ARGS.site
BRIEF = ['height_limit_m', 'landmark_floors', 'm2_per_home', 'homes_target', 'commerce_target',
         'green_target', 'density', 'phase1']
# community uses: built only when the brief asks for them (absent or null: none)
OPTIONAL = {'school_gfa': 0, 'school_yard': 0, 'school_sports': 0, 'pool_gfa': 0, 'pool_plot': 0,
            'daycare_gfa': 0, 'daycares': 0, 'food_market': ''}
DEFAULTS = {'floor_h': 3.0, 'street_w': 16.0, 'sec_street_w': 10.0, 'path_w': 4.0, 'keep_buffer': 4.0,
            'tree_step': 12.0, 'tree_off': 4.0, 'square': 30.0, 'route_bonus_m': 40.0,
            'centre_bonus_m': 150.0, 'green_minus_m': 15.0, 'epsg': None,
            'setback_h_factor': 0.0, 'setback_min_m': 0.0}
_values, SOURCE = read_config(ARGS.config, BRIEF)
CONFIG = {**OPTIONAL, **DEFAULTS, **_values}
_c = shape(json.load(open(os.path.join(SITE, 'site.geojson'), encoding='utf8'))['features'][0]['geometry']).centroid
EPSG = CONFIG['epsg'] or utm_epsg(_c.x, _c.y)
TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
TO_LL = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform

# skill defaults per density: block length, block depth, building depth, base floors, use, type
TYPES = {
    'low':        dict(L=90, D=40, d=10, fl=3, use='housing', type='row houses', gap=6, short=0),
    'medium':     dict(L=90, D=70, d=13, fl=4, use='housing', type='open courtyard block', gap=6, short=1),
    'high':       dict(L=100, D=80, d=14, fl=5, use='mixed', type='courtyard block', gap=6, short=2),
    'urban':      dict(L=100, D=80, d=14, fl=6, use='mixed', type='courtyard block', gap=6, short=2),
    'commercial': dict(L=100, D=60, d=25, fl=3, use='commerce', type='hall', gap=7, short=0),
}
FH = CONFIG['floor_h']
CAP = int((CONFIG['height_limit_m'] - 0.001) // FH)   # floors below the limit


def load(p):
    return json.load(open(p, encoding='utf8'))['features']


def load_if(p):
    """A layer another skill or the site may not have: empty when the file is missing."""
    return load(p) if os.path.exists(p) else []


def m(g):
    return transform(TO_M, shape(g))


site = m(load(os.path.join(SITE, 'site.geojson'))[0]['geometry'])
SP = load(RUN + 'structure-plan/structure-plan.geojson')
nbh = [(f['properties'], m(f['geometry'])) for f in SP if f['properties']['kind'] == 'neighbourhood']
centres = [(f['properties'], m(f['geometry'])) for f in SP if f['properties']['kind'] == 'centre']
greens = [(f['properties'], m(f['geometry'])) for f in SP if f['properties']['kind'] == 'green']
routes = [(f['properties'], m(f['geometry'])) for f in SP if f['properties']['kind'] == 'route']
_main = [g for p, g in centres if p.get('level') == 'main']
if not _main:
    sys.exit('no main centre in structure-plan.geojson: a feature with kind "centre" and level "main"')
main_centre = _main[0]
green_u = unary_union([g for _, g in greens])
water = [m(f['geometry']) for f in load_if(os.path.join(SITE, 'water.geojson')) if f['geometry']['type'] in ('Polygon', 'MultiPolygon')]
water = [w.intersection(site) for w in water if w.intersects(site)]
noise = load_if(RUN + 'climate/noise.geojson')   # without climate: no loud or quiet land
loud = unary_union([m(f['geometry']) for f in noise if f['properties']['period'] == 'day' and f['properties']['db_min'] >= 65])
quiet = unary_union([m(f['geometry']) for f in noise if f['properties']['period'] == 'day' and f['properties']['db_max'] <= 55])

allb = [(f['properties'], m(f['geometry'])) for f in load(os.path.join(SITE, 'buildings.geojson'))]
kept = [(p, g) for p, g in allb if site.contains(g.representative_point())]

street_routes = [(p, g) for p, g in routes if p['level'] in ('main', 'local')]
path_routes = [(p, g) for p, g in routes if p['level'] == 'landscape']
main_routes = unary_union([g for p, g in routes if p['level'] == 'main'])
street_area = unary_union([g.buffer(CONFIG['street_w'] / 2, cap_style=2) for _, g in street_routes])
excl = unary_union([green_u, street_area, *[g for _, g in centres], *water,
                    *[g.buffer(CONFIG['keep_buffer']) for _, g in kept]])


def segs(S, gap, lo=30, hi=50):
    """split a side of length S into buildings of lo..hi m with gaps"""
    if S < lo:
        return []
    n = max(1, math.ceil((S + gap) / (hi + gap)))
    b = (S - (n - 1) * gap) / n
    return [(i * (b + gap), i * (b + gap) + b) for i in range(n)]


def block_buildings(t):
    T = TYPES[t]; L, D, d, g = T['L'], T['D'], T['d'], T['gap']
    out = []
    for a, b in segs(L, g):
        out.append(box(a, 0, b, d)); out.append(box(a, D - d, b, D))
    inner = D - 2 * d - 2 * g
    if T['short'] and inner >= 30:
        out.append(box(0, d + g, d, D - d - g))
        if T['short'] == 2:
            out.append(box(L - d, d + g, L, D - d - g))
    court = box(d, d, L - d, D - d) if T['short'] else box(0, d, L, D - d)
    return out, court


def setback(t):
    """the brief's distance to the street: at least setback_h_factor x H and setback_min_m, counted to the
    street's middle; front strip added to half the secondary street. Without them, no setback."""
    H = CAP * FH
    return max(0.0, max(CONFIG['setback_min_m'], CONFIG['setback_h_factor'] * H) - CONFIG['sec_street_w'] / 2)


buildings, courts, sec_streets = [], [], []
for p, g in nbh:
    if p['action'] == 'keep' or p['name'] not in CONFIG['density']:
        continue
    t = CONFIG['density'][p['name']]; T = TYPES[t]
    land = g.intersection(site).difference(excl)
    pieces = [land] if land.geom_type == 'Polygon' else list(getattr(land, 'geoms', []))
    for piece in pieces:
        if piece.geom_type != 'Polygon' or piece.area < T['L'] * T['D'] / 3:
            continue
        r = piece.minimum_rotated_rectangle
        c = list(r.exterior.coords)
        e = max([(c[i], c[i + 1]) for i in range(4)], key=lambda s: math.dist(*s))
        ang = math.degrees(math.atan2(e[1][1] - e[0][1], e[1][0] - e[0][0]))
        o = piece.centroid
        loc = affinity.rotate(piece, -ang, origin=o)
        x0, y0, x1, y1 = loc.bounds
        sb = setback(t)
        pitchx, pitchy = T['L'] + CONFIG['sec_street_w'] + 2 * sb, T['D'] + CONFIG['sec_street_w'] + 2 * sb
        best = None
        for ox in range(0, int(pitchx), 10):
            for oy in range(0, int(pitchy), 10):
                bl = []
                x = x0 - ox
                while x < x1:
                    y = y0 - oy
                    while y < y1:
                        rect = box(x, y, x + T['L'], y + T['D'])
                        if loc.intersection(rect).area >= rect.area / 3:
                            bl.append((x, y))
                        y += pitchy
                    x += pitchx
                if best is None or len(bl) > len(best[0]):
                    best = (bl, ox, oy)
        bl, ox, oy = best
        for x, y in bl:
            blds, court = block_buildings(t)
            got = []
            for b in blds:
                bb = affinity.translate(b, x, y)
                cl = bb.intersection(loc)
                if cl.geom_type == 'MultiPolygon':
                    cl = max(cl.geoms, key=lambda q: q.area)
                if cl.geom_type == 'Polygon' and cl.area >= 0.6 * bb.area and cl.area >= 150:
                    got.append(cl)
            if not got:
                continue
            for cl in got:
                buildings.append(dict(geom=affinity.rotate(cl, ang, origin=o), t=t, nb=p['name'],
                                      phase=1 if p['name'] in CONFIG['phase1'] else None))
            cc = affinity.translate(court, x, y).intersection(loc)
            if cc.area > 200:
                courts.append(affinity.rotate(cc, ang, origin=o).difference(unary_union([affinity.rotate(q, ang, origin=o) for q in got])))
        # secondary streets: grid lines between kept blocks
        xs = sorted({x for x, _ in bl}); ys = sorted({y for _, y in bl})
        lines = []
        for x in xs[1:]:
            lines.append(LineString([(x - CONFIG['sec_street_w'] / 2 - sb, y0 - 50), (x - CONFIG['sec_street_w'] / 2 - sb, y1 + 50)]))
        for y in ys[1:]:
            lines.append(LineString([(x0 - 50, y - CONFIG['sec_street_w'] / 2 - sb), (x1 + 50, y - CONFIG['sec_street_w'] / 2 - sb)]))
        for ln in lines:
            cl = ln.intersection(loc)
            for q in ([cl] if cl.geom_type == 'LineString' else list(getattr(cl, 'geoms', []))):
                if q.geom_type == 'LineString' and q.length > 20:
                    sec_streets.append(affinity.rotate(q, ang, origin=o))

# ---------- community: school, pool, daycares ----------
def blocks_by_centre_dist(cands):
    return sorted(cands, key=lambda b: b['geom'].distance(main_centre))

community = []
# school: the housing block nearest the main centre, not in the 65 dB(A) strip, quiet (<55 dB day) if one is;
# its ring buildings give way to the school building, the yard and the sports ground
need = CONFIG['school_yard'] + CONFIG['school_sports']
def ring_of(c): return [b for b in buildings if b['geom'].distance(c) < 1.0 and not b.get('fixed')]
def plot_of(c): return unary_union([c, *[b['geom'] for b in ring_of(c)]])
ok = [c for c in courts if ring_of(c) and all(b['t'] != 'commercial' for b in ring_of(c))
      and plot_of(c).area >= need + 1000 and not plot_of(c).intersects(loud)]
cand = [c for c in ok if c.centroid.within(quiet)] or ok
school_court = min(cand, key=lambda c: c.distance(main_centre)) if cand and CONFIG['school_gfa'] > 0 else None
if school_court is not None:
    courts.remove(school_court)
    ring = sorted(ring_of(school_court), key=lambda b: b['geom'].distance(main_centre))
    plot = plot_of(school_court)
    for b in ring:
        buildings.remove(b)
    # school: 3 storeys (own assumption), 14 m deep along the plot side nearest the centre
    sfl = 3; depth = TYPES['high']['d']
    rr = plot.minimum_rotated_rectangle; cs = list(rr.exterior.coords)
    edges = sorted([(cs[i], cs[i + 1]) for i in range(4)], key=lambda e: -math.dist(*e))[:2]
    (ax, ay), (bx_, by_) = min(edges, key=lambda e: LineString(e).distance(main_centre))
    ln = math.dist((ax, ay), (bx_, by_)); ux, uy = (bx_ - ax) / ln, (by_ - ay) / ln
    cx_, cy_ = rr.centroid.x, rr.centroid.y
    nx_, ny_ = -uy, ux
    if (cx_ - ax) * nx_ + (cy_ - ay) * ny_ < 0: nx_, ny_ = -nx_, -ny_
    L_ = min(ln - 10, CONFIG['school_gfa'] / sfl / depth)
    a0 = (ln - L_) / 2
    sg = Polygon([(ax + ux * a0, ay + uy * a0), (ax + ux * (a0 + L_), ay + uy * (a0 + L_)),
                  (ax + ux * (a0 + L_) + nx_ * depth, ay + uy * (a0 + L_) + ny_ * depth), (ax + ux * a0 + nx_ * depth, ay + uy * a0 + ny_ * depth)]).intersection(plot)
    s = dict(geom=sg, t='community', nb=ring[0]['nb'], fixed=True, use='school', type='school',
             floors=max(sfl, math.ceil(CONFIG['school_gfa'] / sg.area)), phase=ring[0].get('phase'))
    buildings.append(s)
    rest = plot.difference(s['geom'])
    r_ = 5.0
    while True:
        yard = rest.intersection(s['geom'].buffer(r_))
        if yard.area >= CONFIG['school_yard'] or r_ > 200: break
        r_ += 2.0
    sports = rest.difference(yard)
    community += [('square', 'schoolyard', yard), ('park', 'school sports', sports)]
# pool: the next courtyard block nearest the centre, its ring buildings replaced by one hall
cand = [c for c in courts if c.area >= max(CONFIG['pool_plot'], 1) * 0.75]
pool_court = min(cand, key=lambda c: c.distance(main_centre)) if cand and CONFIG['pool_gfa'] > 0 else None
pool = None
if pool_court is not None:
    courts.remove(pool_court)
    ring = [b for b in buildings if b['geom'].distance(pool_court) < 1.0 and not b.get('fixed')]
    for b in ring:
        buildings.remove(b)
    plot = unary_union([pool_court, *[b['geom'] for b in ring]])
    rr = plot.minimum_rotated_rectangle
    hall_fp = CONFIG['pool_gfa'] / 2  # own: two storeys of hall height
    hall = affinity.scale(rr, math.sqrt(hall_fp / rr.area), math.sqrt(hall_fp / rr.area)).intersection(plot)
    pool = dict(geom=hall, t='community', nb='pool', fixed=True, use='indoor pool', type='hall', floors=2, phase=None)
    buildings.append(pool)
    community.append(('park', 'pool grounds', plot.difference(hall)))

# ---------- heights ----------
for b in buildings:
    if b.get('fixed'):
        continue
    T = TYPES[b['t']]
    f = T['fl']
    if b['geom'].distance(main_routes) <= CONFIG['route_bonus_m']: f += 1
    if b['geom'].distance(main_centre) <= CONFIG['centre_bonus_m']: f += 1
    if b['geom'].distance(green_u) <= CONFIG['green_minus_m']: f -= 1
    b['base'] = max(1, f)
    b['use'] = T['use']; b['type'] = T['type']
    if b['geom'].representative_point().within(loud):
        b['use'] = 'commerce'   # climate/rules.json: no homes at 65 dB(A) or more by day

free = [b for b in buildings if not b.get('fixed')]
landmarks = sorted([b for b in free if b['use'] == 'mixed'], key=lambda b: b['geom'].distance(main_centre))[:2]
for b in landmarks: b['landmark'] = True


def apply(group, f):
    for b in group:
        cap = CONFIG['landmark_floors'] if b.get('landmark') else CAP
        b['floors'] = int(min(cap, max(1, round(b['base'] * f))))
        if b.get('landmark'): b['floors'] = cap


def gfa(b): return b['geom'].area * b['floors']
def res_gfa(b): return b['geom'].area * (b['floors'] - (1 if b['use'] == 'mixed' else 0)) if b['use'] in ('housing', 'mixed') else 0.0
def com_gfa(b): return gfa(b) if b['use'] == 'commerce' else (b['geom'].area if b['use'] == 'mixed' else 0.0)


def solve(group, fn, target):
    lo, hi = 0.2, 4.0
    for _ in range(40):
        mid = (lo + hi) / 2; apply(group, mid)
        if sum(fn(b) for b in buildings) < target: lo = mid
        else: hi = mid
    best = min([lo, hi], key=lambda f: (apply(group, f), abs(sum(fn(b) for b in buildings) - target))[1])
    apply(group, best); return best

home_grp = [b for b in free if b['use'] in ('housing', 'mixed')]
com_grp = [b for b in free if b['use'] == 'commerce']
apply(com_grp, 1.0)
res_target = CONFIG['homes_target'] * CONFIG['m2_per_home']
f_res = solve(home_grp, res_gfa, res_target)
# daycares: housing building nearest the centre, then those furthest from each other (in quiet-ish, not loud land)
dc_cand = [b for b in home_grp if not b['geom'].intersects(loud)]
day = []
if dc_cand and CONFIG['daycares'] > 0:
    day.append(min(dc_cand, key=lambda b: b['geom'].distance(main_centre)))
    while len(day) < CONFIG['daycares']:
        day.append(max([b for b in dc_cand if b not in day], key=lambda b: min(b['geom'].distance(d['geom']) for d in day)))
for b in day:
    b['daycare_floors'] = math.ceil(CONFIG['daycare_gfa'] / b['geom'].area)
    b['use'] = 'housing + daycare' if b['use'] == 'housing' else 'mixed + daycare'


def homes_m2(b):
    if b['use'] in ('housing', 'mixed'):
        return res_gfa(b)
    if b['use'].endswith('daycare'):
        nonres = b.get('daycare_floors', 0) + (1 if b['use'].startswith('mixed') else 0)
        return max(0.0, b['geom'].area * (b['floors'] - nonres))
    return 0.0


def commerce_m2(b):
    if b['use'] == 'commerce': return gfa(b)
    if b['use'].startswith('mixed'): return b['geom'].area
    return 0.0

# re-solve homes with the daycares in place
lo, hi = 0.2, 4.0
for _ in range(40):
    mid = (lo + hi) / 2; apply(home_grp, mid)
    if sum(homes_m2(b) for b in buildings) < res_target: lo = mid
    else: hi = mid
f_res = min([lo, hi], key=lambda f: (apply(home_grp, f), abs(sum(homes_m2(b) for b in buildings) - res_target))[1]); apply(home_grp, f_res)
lo, hi = 0.2, 4.0
for _ in range(40):
    mid = (lo + hi) / 2; apply(com_grp, mid)
    if sum(commerce_m2(b) for b in buildings) < CONFIG['commerce_target']: lo = mid
    else: hi = mid
f_com = min([lo, hi], key=lambda f: (apply(com_grp, f), abs(sum(commerce_m2(b) for b in buildings) - CONFIG['commerce_target']))[1]); apply(com_grp, f_com)
for b in day:  # enough floors for the daycare
    b['floors'] = max(b['floors'], b['daycare_floors'] + 1)

# a shop the brief asks for (config `food_market`, a note), in the ground floor of the mixed building nearest the centre
if CONFIG.get('food_market'):
    mk = min([b for b in buildings if b['use'] == 'mixed'], key=lambda b: b['geom'].distance(main_centre))
    mk['note'] = '%s (%s)' % (CONFIG['food_market'], SOURCE.get('food_market', ''))

# ---------- streets, open space, trees ----------
feats = []


def add(kind, geom, **props):
    props = {'kind': kind, **props}
    feats.append({'type': 'Feature', 'properties': props, 'geometry': mapping(transform(TO_LL, geom))})


for b in buildings:
    pr = dict(floors=b['floors'], height_m=round(b['floors'] * FH, 1), use=b['use'], type=b['type'], existing=False,
              footprint_m2=round(b['geom'].area), gfa_m2=round(gfa(b)), neighbourhood=b['nb'])
    if b.get('phase'): pr['phase'] = b['phase']
    if b.get('landmark'): pr['landmark'] = True
    if b.get('daycare_floors'): pr['daycare_floors'] = b['daycare_floors']
    if b.get('note'): pr['note'] = b['note']
    add('building', b['geom'], **pr)
for p, g in kept:
    fl = p.get('floors') or 1
    add('building', g, floors=fl, height_m=p.get('height'), use=p.get('use'), type=p.get('building'), existing=True,
        height_source=p.get('height_source'), osm_id=p.get('id'))
for p, g in street_routes:
    add('street', g.intersection(site.buffer(5)) if g.intersects(site) else g, width=CONFIG['street_w'], name=p['name'], level=p['level'])
for p, g in path_routes:
    add('street', g, width=CONFIG['path_w'], name=p['name'], level='path')
for g in sec_streets:
    add('street', g, width=CONFIG['sec_street_w'], level='secondary', note='greened secondary street')
for p, g in greens:
    add('open-space', g.intersection(site), use='park', name=p['name'])
for w in water:
    add('open-space', w, use='water')
sq_all = []
for p, g in centres:
    c = g.representative_point()
    sq = box(c.x - CONFIG['square'] / 2, c.y - CONFIG['square'] / 2, c.x + CONFIG['square'] / 2, c.y + CONFIG['square'] / 2)
    sq_all.append(sq)
    add('open-space', sq, use='square', name=p['name'])
    rest = g.difference(sq)
    if rest.area > 50: add('open-space', rest, use='park', name=p['name'] + ' (centre ground)')
for c in courts:
    if c.area > 100: add('open-space', c, use='garden', type='courtyard')
for u, t, g in community:
    if g.area > 50: add('open-space', g, use=u, type=t)

bu = unary_union([b['geom'] for b in buildings] + [g for _, g in kept])
trees = []
all_streets = [g for _, g in street_routes] + sec_streets
for g in all_streets:
    g = g.intersection(site)
    for ln in ([g] if g.geom_type == 'LineString' else list(getattr(g, 'geoms', []))):
        if ln.geom_type != 'LineString' or ln.length < CONFIG['tree_step']: continue
        for side in (-1, 1):
            off = ln.parallel_offset(CONFIG['tree_off'], 'left' if side > 0 else 'right')
            for q in ([off] if off.geom_type == 'LineString' else list(getattr(off, 'geoms', []))):
                dd = CONFIG['tree_step'] / 2
                while dd < q.length:
                    pt = q.interpolate(dd)
                    if not bu.buffer(1).contains(pt) and not any(s.contains(pt) for s in sq_all):
                        trees.append(pt)
                    dd += CONFIG['tree_step']
for t in trees:
    add('tree', t)

json.dump({'type': 'FeatureCollection', 'name': 'massing',
           'note': 'WGS84, longitude first; areas measured in EPSG:%d' % EPSG, 'features': feats},
          open(OUT + 'massing.geojson', 'w', encoding='utf8'), ensure_ascii=False)

# ---------- areas ----------
new = [b for b in buildings]
H_m2 = sum(homes_m2(b) for b in new)
homes = H_m2 / CONFIG['m2_per_home']
C_m2 = sum(commerce_m2(b) for b in new)
school = sum(gfa(b) for b in new if b['use'] == 'school')
poolg = sum(gfa(b) for b in new if b['use'] == 'indoor pool')
dcm = sum(b['geom'].area * b['daycare_floors'] for b in day)
yard = sum(g.area for u, t, g in community if t == 'schoolyard')
spt = sum(g.area for u, t, g in community if t == 'school sports')
green_land = green_u.intersection(site).area + sum(g.difference(s).area for (_, g), s in zip(centres, sq_all))
total = sum(gfa(b) for b in new)
rows = [
    ('homes (count)', CONFIG['homes_target'], round(homes), '%s; design homes = housing floor area / %d m2 per home (%s)' % (SOURCE.get('homes_target', 'not in the brief'), CONFIG['m2_per_home'], SOURCE.get('m2_per_home', 'not in the brief'))),
    ('housing floor area', round(res_target), round(H_m2), '%d homes x %d m2 (%s)' % (CONFIG['homes_target'], CONFIG['m2_per_home'], SOURCE.get('m2_per_home', 'not in the brief'))),
    ('commerce floor area', round(CONFIG['commerce_target']), round(C_m2), SOURCE.get('commerce_target', 'not in the brief') + '; halls, buildings in the 65 dB(A) strip, ground floors of mixed blocks'),
    ('daycare floor area', round(CONFIG['daycare_gfa'] * CONFIG['daycares']), round(dcm), '%s, %d x %d m2' % (SOURCE.get('daycare_gfa', 'not in the brief'), CONFIG['daycares'], CONFIG['daycare_gfa'])),
    ('primary school floor area', round(CONFIG['school_gfa']), round(school), SOURCE.get('school_gfa', 'not in the brief')),
    ('schoolyard (land)', round(CONFIG['school_yard']), round(yard), SOURCE.get('school_yard', 'not in the brief')),
    ('school sports (land)', round(CONFIG['school_sports']), round(spt), SOURCE.get('school_sports', 'not in the brief')),
    ('indoor pool floor area', round(CONFIG['pool_gfa']), round(poolg), SOURCE.get('pool_gfa', 'not in the brief')),
    ('public green (land)', round(CONFIG['green_target']), round(green_land), SOURCE.get('green_target', 'not in the brief') + '; structure plan greens inside the site plus centre grounds, courtyards not counted'),
]
with open(OUT + 'areas.csv', 'w', newline='', encoding='utf8') as fh:
    w = csv.writer(fh); w.writerow(['use', 'programme_m2', 'design_m2', 'difference_m2', 'source'])
    for u, a, b_, s in rows: w.writerow([u, a, b_, b_ - a, s])

stats = dict(n_new=len(new), n_kept=len(kept), total_gfa=round(total), far_site=round(total / site.area, 2),
             site_ha=round(site.area / 1e4, 1), new_land_ha=round(sum(g.intersection(site).area for p, g in nbh if p['action'] != 'keep') / 1e4, 1),
             homes=round(homes), H_m2=round(H_m2), C_m2=round(C_m2), f_res=round(f_res, 3), f_com=round(f_com, 3),
             floors={k: sum(1 for b in new if b['floors'] == k) for k in range(1, 10)}, trees=len(trees),
             at_cap=sum(1 for b in home_grp if b['floors'] >= CAP and not b.get('landmark')), n_home=len(home_grp),
             com_at_cap=sum(1 for b in com_grp if b['floors'] >= CAP), n_com=len(com_grp),
             green_ha=round(green_land / 1e4, 2), cap=CAP, school_court=school_court is not None, pool=pool is not None,
             loud_commerce=sum(1 for b in new if b['use'] == 'commerce' and b['t'] != 'commercial'))
stats['far_new'] = round(total / (stats['new_land_ha'] * 1e4), 2)
json.dump(stats, open(OUT + 'stats.json', 'w'), indent=1)
print(json.dumps(stats, indent=1))

with open(OUT + 'assumptions.md', 'w', encoding='utf8') as fh:
    fh.write('# Massing: values and assumptions\n\n## From config.json\n\n')
    for k in sorted(_values):
        fh.write('- %s: %s (%s)\n' % (k, json.dumps(_values[k], ensure_ascii=False), SOURCE.get(k) or 'no source given'))
    fh.write('\n## Skill defaults used\n\n')
    for k, v in DEFAULTS.items():
        if k not in _values:
            fh.write('- %s: %s (skill default)\n' % (k, 'UTM zone of the site, EPSG %d' % EPSG if k == 'epsg' else v))
