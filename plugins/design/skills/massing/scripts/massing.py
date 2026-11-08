"""Massing on a structure plan, checked against the brief's programme.

    python massing.py --proposal <proposal folder> --site <site folder> --config <proposal>/massing/config.json

config.json holds the brief's values, each as {"value": ..., "source": "<file> p. N" or "assumption: ..."}:
every key in BRIEF. DEFAULTS are the skill's own and config.json may override them. `density` maps each
structure-plan neighbourhood name to low, medium, high, urban or commercial; `phase1` lists the first
phase's neighbourhoods. Writes massing.geojson, areas.csv, stats.json and assumptions.md into <proposal>/massing/.
"""
import argparse, json, math, sys, csv, os
from shapely.geometry import shape, mapping, Polygon, LineString, Point, box, MultiPolygon
from shapely.ops import transform, unary_union, nearest_points
from shapely import affinity, prepare
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
A.add_argument('--design-noise', help='the second run: noise-design.geojson from noise_at_buildings.py')
ARGS = A.parse_args()
RUN = os.path.join(ARGS.proposal, '')
OUT = os.path.join(RUN, 'massing', '')
SITE = ARGS.site
BRIEF = ['height_limit_m', 'landmark_floors', 'm2_per_home', 'homes_target', 'commerce_target',
         'green_target', 'density', 'phase1']
# community uses: built only when the brief asks for them (absent or null: none). community_buildings: a list of
# {"use", "gfa", "floors", "ground_m2", "at", "depth"}, each built on the centre whose `holds` (or name) has the word `at`
OPTIONAL = {'school_gfa': 0, 'school_yard': 0, 'school_sports': 0, 'pool_gfa': 0, 'pool_plot': 0,
            'daycare_gfa': 0, 'daycares': 0, 'food_market': '', 'figure': {}, 'homes_target_is_minimum': False,
            'community_buildings': []}
DEFAULTS = {'floor_h': 3.0, 'street_w': 16.0, 'sec_street_w': 10.0, 'path_w': 4.0, 'keep_buffer': 4.0,
            'tree_step': 12.0, 'tree_off': 4.0, 'square_main_m': 60.0, 'square_local_m': 30.0, 'route_bonus_m': 40.0,
            'centre_bonus_m': 150.0, 'green_minus_m': 15.0, 'epsg': None,
            'setback_h_factor': 0.0, 'setback_min_m': 0.0,
            'row_gap': 24.0,   # metres between the two rows of a block in the rows and points typologies
            'street_reach_m': 60.0,   # how far a secondary street that ends in nothing is led on to the next street, the green or the site edge
            'path_reach_m': 150.0,
            'acoustic_db': 65.0, 'commerce_db': 70.0,   # day, at the loudest facade with the design standing: homes from acoustic_db need better acoustic protection, from commerce_db the building is commerce
            'community_gfa_m2': 300.0}   # assumed floor area of a community building the brief names without one    # how far a path may carry a street end across the green to the next street
_values, SOURCE = read_config(ARGS.config, BRIEF)
CONFIG = {**OPTIONAL, **DEFAULTS, **_values}
_c = shape(json.load(open(os.path.join(SITE, 'site.geojson'), encoding='utf8'))['features'][0]['geometry']).centroid
EPSG = CONFIG['epsg'] or utm_epsg(_c.x, _c.y)
TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
TO_LL = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform

# skill defaults per density: block length, block depth, building depth, base floors, use, type, the part and roof
# of its buildings
TYPES = {
    'low':        dict(L=90, D=40, d=10, fl=3, use='housing', type='row houses', gap=6, short=0, part='row', roof='gable'),
    'medium':     dict(L=90, D=70, d=13, fl=4, use='housing', type='open courtyard block', gap=6, short=1, part='side', roof='green'),
    'high':       dict(L=100, D=80, d=14, fl=5, use='mixed', type='courtyard block', gap=6, short=2, part='side', roof='green'),
    'urban':      dict(L=100, D=80, d=14, fl=6, use='mixed', type='courtyard block', gap=6, short=2, part='side', roof='green'),
    'commercial': dict(L=100, D=60, d=25, fl=3, use='commerce', type='hall', gap=7, short=0, part='hall', roof='pv'),
}
# a typology changes the block of a density; the figure comes from the narrative through config `figure`.
# `form` names the parts block_buildings() makes; without it the buildings stand along the block's sides
TYPOLOGY = {
    'rows':           dict(short=0, rows=True, type='rows', part='row'),
    'open courtyard': dict(short=1, type='open courtyard block', part='side'),
    'courtyard':      dict(short=2, type='courtyard block', part='side'),
    'points':         dict(short=0, rows=True, points=True, type='point buildings', part='point'),
    'halls':          dict(short=0, d=25, gap=7, use='commerce', type='hall', part='hall', roof='pv'),
    'perimeter':      dict(form='perimeter', type='perimeter block'),
    'L':              dict(form='L', type='L blocks'),
    'U':              dict(form='U', type='U block'),
    'ensemble':       dict(form='ensemble', type='courtyard ensemble'),
    'town houses':    dict(form='houses', rows=True, d=11, fl=3, pmax=3, plot=6.5, houses_max=8, use='housing',
                           type='town houses', part='town house', roof='gable'),
    'tower':          dict(form='tower', type='block with tower', tower=20),
    'hub':            dict(form='hub', type='mobility hub', use='mixed', tower=20, garage_d=32, garage_fl=4),
}
FIGURE = CONFIG.get('figure') or {}


def figure_for(name):
    """config `figure`: {"*": {...}, "<neighbourhood>": {...}}; the named entry overrides "*", its typology a mix of "*"."""
    F, own = {**FIGURE.get('*', {}), **FIGURE.get(name, {})}, FIGURE.get(name, {})
    if 'typology' in own and 'mix' not in own: F.pop('mix', None)
    return F


def mix_of(F):
    """figure `mix`: {typology: share}, or a list the blocks take in turn; without it the one typology. As shares
    that add up to 1."""
    mx = F.get('mix') or [F.get('typology')]
    mx = dict(mx) if isinstance(mx, dict) else {ty: mx.count(ty) for ty in mx}
    return {ty: v / sum(mx.values()) for ty, v in mx.items()}


def pick(F, shares, done, count, col, row):
    """the typologies of the block at col, row among `shares` (those of its row's depth), the first to build first:
    a list's in turn along each row and column; else the one furthest below its share, counted a block further if it
    is that of the block before it in its row or column. The others follow, for a block where the first doesn't fit."""
    k, near = sum(count.values()) + 1, {done.get((col - 1, row)), done.get((col, row - 1))}
    order = sorted(shares, key=lambda ty: shares[ty] * k - count[ty] - (ty in near), reverse=True)
    if isinstance(F.get('mix'), list):
        lst = [ty for ty in F['mix'] if ty in shares]
        first = lst[(col + row) % len(lst)]; order = [first] + [ty for ty in order if ty != first]
    return order


def type_for(name, typology=None):
    """the block of a neighbourhood: its density's TYPES entry, changed by its figure or by one typology of its mix"""
    T = dict(TYPES[CONFIG['density'][name]]); F = figure_for(name); ty = typology or F.get('typology')
    if ty:
        if ty not in TYPOLOGY:
            sys.exit('figure.%s typology "%s" is not one of %s' % (name, ty, ', '.join(TYPOLOGY)))
        T.update(TYPOLOGY[ty])
    T.update(F.get('block') or {})
    if T.get('rows'):
        T['D'] = 2 * T['d'] + float(F.get('row_gap', CONFIG['row_gap']))
    return T
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
levels = [(f['properties']['noise_day_db'], m(f['geometry'])) for f in load(ARGS.design_noise)] if ARGS.design_noise else []

allb = [(f['properties'], m(f['geometry'])) for f in load(os.path.join(SITE, 'buildings.geojson'))]
kept = [(p, g) for p, g in allb if site.contains(g.representative_point())]

street_routes = [(p, g) for p, g in routes if p['level'] in ('main', 'local')]
path_routes = [(p, g) for p, g in routes if p['level'] == 'landscape']
main_routes = unary_union([g for p, g in routes if p['level'] == 'main'])


def lay_off(g, half):
    """a structure-plan street stops keep_buffer short of each kept building it would cover; a path carries it on"""
    block = unary_union([Polygon()] + [b.buffer(half + CONFIG['keep_buffer']) for _, b in kept if b.distance(g) < half])
    return g.difference(block), [q for q in getattr(g.intersection(block), 'geoms', [g.intersection(block)]) if q.length]


_laid = [(p, *lay_off(g, CONFIG['street_w'] / 2)) for p, g in street_routes]
street_routes = [(p, g) for p, g, _ in _laid if not g.is_empty]
path_routes += [(p, q) for p, _, ps in _laid for q in ps]
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


def squares(S, d, gap):
    """as many buildings d m wide as fit along a side of length S, at least gap apart, spread evenly"""
    if S < d:
        return []
    n = max(1, int((S + gap) // (d + gap)))
    step = (S - d) / (n - 1) if n > 1 else 0
    return [(i * step, i * step + d) for i in range(n)]


def block_buildings(T, col=0, row=0):
    """the parts of one block of L x D in its own frame, as (footprint, part, own keys: fl_add floors over the
    block's, use, roof, floors fixed, ground_floor), and its courtyard. Blocks in odd cols and rows are mirrored,
    so the open sides of L, U, ensemble, tower and hub blocks alternate."""
    L, D, d, g = T['L'], T['D'], T['d'], T['gap']
    form, G, out = T.get('form'), 2 * g, []
    def P(q, part=T['part'], arms=None, **kw): out.append((q, part, {**kw, 'arms': [q] if arms is None else arms}))
    def ell(lx, ly, s=(1, 1)):   # an L of arms lx along x and ly along y from the corner (0, 0), mirrored by s; and its arms
        arms = [affinity.scale(a, *s, origin=(L / 2, D / 2)) for a in (box(0, 0, lx, d), box(0, d, d, ly))]
        return unary_union(arms), 'corner', arms
    if form is None:   # along the sides; points: square buildings d x d along the long sides; otherwise 30 to 50 m long
        for a, b in (squares(L, d, g) if T.get('points') else segs(L, g)):
            P(box(a, 0, b, d)); P(box(a, D - d, b, D))
        inner = D - 2 * d - 2 * g
        if T['short'] and inner >= 30:
            P(box(0, d + g, d, D - d - g), 'end')
            if T['short'] == 2:
                P(box(L - d, d + g, L, D - d - g), 'end')
        return out, (box(d, d, L - d, D - d) if T['short'] else box(0, d, L, D - d))
    if form == 'perimeter':   # closed corners a floor higher, a gap in the middle of each short side, the long sides between
        cx, cy = max(d + 8, L / 4), (D - g) / 2
        if L - 2 * cx - 2 * g < 30: cx = (L - g) / 2
        for s in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            P(*ell(cx, cy, s), fl_add=1)
        for a, b in (segs(L - 2 * cx - 2 * g, g) if L - 2 * cx - 2 * g >= 30 else []):
            P(box(cx + g + a, 0, cx + g + b, d)); P(box(cx + g + a, D - d, cx + g + b, D))
    elif form == 'L':   # two L-shaped buildings facing each other, the courtyard open at the other two corners
        for s in (1, -1):
            P(*ell(L - d - G, D - d - G, (s, s)))
    elif form == 'U':   # one long side and both short sides joined, open on the far long side
        P(box(0, 0, L, d)); P(box(0, d, d, D), 'wing'); P(box(L - d, d, L, D), 'wing')
    elif form == 'ensemble':   # an open courtyard of an L, a bar and a point, their lengths varying from block to block
        a, b, s = [(0.6, 1.0, 0.0), (0.45, 0.6, 0.3), (0.75, 0.8, 0.15)][(2 * col + row) % 3]   # not col + row: a mix list of 3 takes turns by that
        P(*ell(a * L, b * D))
        P(box(d + g if b * D > D - d - g else 0, D - d, L - s * L, D))
        if a * L + g <= L - d - 4: P(box(L - d - 4, 0, L, d + 4), 'point')
    elif form == 'houses':   # narrow houses on their own plots, in terraces of 3 to houses_max along both long sides
        w = T['plot']
        for a, b in segs(L, g, 3 * w, T['houses_max'] * w):
            n = max(1, round((b - a) / w)); s = (b - a) / n
            for i in range(n):
                P(box(a + i * s, 0, a + i * s + s, d)); P(box(a + i * s, D - d, a + i * s + s, D))
    elif form == 'tower':   # an L along one long and one short side, a tower on the free corner, a bar between
        P(*ell(L, D - d - G))
        P(box(L - T['tower'], D - T['tower'], L, D), 'tower', fl_add=2, roof='flat')
        if L - T['tower'] - 2 * G - d >= 15: P(box(d + G, D - d, L - T['tower'] - G, D))
    elif form == 'hub':   # a garage with mobility on its ground floor and a PV roof, a tower beside it, a bar on the far side
        gd = T['garage_d']
        P(box(0, 0, min(L - T['tower'] - G, 60), gd), 'garage', use='parking', floors=int(T['garage_fl']), roof='pv',
          ground_floor='mobility', arms=[])   # a garage that doesn't fit is left out, not made into homes
        P(box(L - T['tower'], 0, L, T['tower']), 'tower', fl_add=2, roof='flat')
        if D - d - gd >= g: P(box(0, D - d, L, D))
    else:
        sys.exit('typology form "%s" is not one of perimeter, L, U, ensemble, houses, tower, hub' % form)
    keep = []   # a part that would overlap one before it (block sizes from the config) is left out
    for q, part, kw in out:
        if all(q.intersection(k[0]).area < 1 for k in keep): keep.append((q, part, kw))
    m_ = lambda q: affinity.scale(q, -1 if col % 2 else 1, -1 if row % 2 else 1, origin=(L / 2, D / 2))
    return ([(m_(q), part, {**kw, 'arms': [m_(a) for a in kw['arms']]}) for q, part, kw in keep],
            m_(box(d, d, L - d, D - d) if form != 'houses' else box(0, d, L, D - d)))


def clip(q, land):
    """a part cut to its land: the largest piece, if it keeps 60 % of the part and 150 m2 (90 % of a smaller part)"""
    cl = q.intersection(land)
    if cl.geom_type == 'MultiPolygon':
        cl = max(cl.geoms, key=lambda r: r.area)
    return cl if cl.geom_type == 'Polygon' and cl.area >= 0.6 * q.area and cl.area >= min(150, 0.9 * q.area) else None


def bars(q, g):
    """an arm (a box along the block's axes) longer than 50 m as bars of 30 to 50 m with gaps g, else the arm itself"""
    x0, y0, x1, y1 = q.bounds
    if max(x1 - x0, y1 - y0) <= 50: return [q]
    if x1 - x0 >= y1 - y0: return [box(x0 + a, y0, x0 + b, y1) for a, b in segs(x1 - x0, g)]
    return [box(x0, y0 + a, x1, y0 + b) for a, b in segs(y1 - y0, g)]


def setback(t):
    """the brief's distance to the street: at least setback_h_factor x H and setback_min_m, counted to the
    street's middle; front strip added to half the secondary street. Without them, no setback."""
    H = CAP * FH
    return max(0.0, max(CONFIG['setback_min_m'], CONFIG['setback_h_factor'] * H) - CONFIG['sec_street_w'] / 2)


def route_angle(piece):
    """the angle from east of the main or local route a piece of land lies along (the longest stretch within a
    secondary street of its edge, else the nearest route): the mean direction of that stretch, by length"""
    near = piece.buffer(CONFIG['street_w'] / 2 + CONFIG['sec_street_w'])
    g = max((g for _, g in street_routes), key=lambda g: (g.intersection(near).length, -g.distance(piece)))
    s = g.intersection(near) if g.intersects(near) else g.intersection(nearest_points(g, piece)[0].buffer(25))
    v = [0.0, 0.0]
    for ln in getattr(s, 'geoms', [s]):
        cs = list(ln.coords) if ln.geom_type == 'LineString' else []
        for (ax, ay), (bx, by) in zip(cs, cs[1:]):   # doubled angles, so a line and its reverse count alike
            a, l = 2 * math.atan2(by - ay, bx - ax), math.hypot(bx - ax, by - ay)
            v[0] += l * math.cos(a); v[1] += l * math.sin(a)
    return math.degrees(math.atan2(v[1], v[0]) / 2)


def grid(piece, ang, L, DEP, CLS, strips, sw):
    """blocks L long on a piece of land turned by -ang, in rows from the bottom that take the depths DEP in turn by
    the shares CLS (strips: the rows of each depth built so far), sw apart: the offset, in 10 m steps, that places
    the most blocks at least a third complete. Returns the blocks (x, y, row of seq), the rows' depths and the land."""
    loc = affinity.rotate(piece, -ang, origin=piece.centroid); x0, y0, x1, y1 = loc.bounds
    seq, c = [], dict(strips)
    while sum(D + sw for D in seq) < y1 - y0 + DEP[-1] + sw:
        k = sum(c.values()) + 1
        seq.append(max(DEP, key=lambda D: (sum(CLS[D].values()) * k - c[D], D))); c[seq[-1]] += 1
    best = []
    for ox in range(0, int(L + sw), 10):
        for oy in range(0, int(seq[0] + sw), 10):
            bl, x = [], x0 - ox
            while x < x1:
                y = y0 - oy
                for r, D in enumerate(seq):
                    if y >= y1: break
                    rect = box(x, y, x + L, y + D)
                    if loc.intersection(rect).area >= rect.area / 3:
                        bl.append((x, y, r))
                    y += D + sw
                x += L + sw
            if len(bl) > len(best): best = bl
    return best, seq, loc


buildings, courts, sec_streets, figures, n_block = [], [], [], {}, 0
GRID = {}   # neighbourhood name: (area, bearing) of its largest piece, for the buildings on its centres
for p, g in nbh:
    if p['action'] == 'keep' or p['name'] not in CONFIG['density']:
        continue
    t = CONFIG['density'][p['name']]; F = figure_for(p['name']); MIX = mix_of(F); count = dict.fromkeys(MIX, 0)
    TS = {ty: type_for(p['name'], ty) for ty in MIX}   # a row of blocks takes one depth of the mix, a block its own
    L_, DEP = max(x['L'] for x in TS.values()), sorted({x['D'] for x in TS.values()})
    CLS = {D: {ty: s for ty, s in MIX.items() if TS[ty]['D'] == D} for D in DEP}; strips = dict.fromkeys(DEP, 0)
    figures[p['name']] = dict(typology=' + '.join('%s %d %%' % (ty, round(100 * s)) for ty, s in MIX.items())
                              if len(MIX) > 1 else F.get('typology') or 'by density (%s)' % t,
                              orientation=F.get('orientation', 'route'),
                              row_gap=float(F.get('row_gap', CONFIG['row_gap'])))
    land = g.intersection(site).difference(excl)
    sb = setback(t); sw = CONFIG['sec_street_w'] + 2 * sb
    # a main or local route that ends inside the land goes on straight to the land's edge as a secondary street,
    # so it splits its piece of land, as the routes that cross it do
    for _, r_ in street_routes:
        for ln in getattr(r_, 'geoms', [r_]):
            cs = list(ln.coords)
            for e, q in ((cs[0], cs[1]), (cs[-1], cs[-2])):
                n = math.dist(e, q) or 1; hit =LineString([e, (e[0] + (e[0] - q[0]) / n * 2e3, e[1] + (e[1] - q[1]) / n * 2e3)]).intersection(land)
                s = [s for s in getattr(hit, 'geoms', [hit]) if s.geom_type == 'LineString' and Point(e).distance(s) < 1 and s.length > 20]
                if s:
                    s = LineString([e, max(s[0].coords, key=lambda c: math.dist(c, e))])
                    sec_streets.append(s); land = land.difference(s.buffer(sw / 2, cap_style=2))
    pieces = [land] if land.geom_type == 'Polygon' else list(getattr(land, 'geoms', []))
    for piece in pieces:
        if piece.geom_type != 'Polygon' or piece.area < L_ * DEP[0] / 3:
            continue
        r = piece.minimum_rotated_rectangle
        c = list(r.exterior.coords)
        e = max([(c[i], c[i + 1]) for i in range(4)], key=lambda s: math.dist(*s))
        ang = math.degrees(math.atan2(e[1][1] - e[0][1], e[1][0] - e[0][0]))
        lng, ori = ang, F.get('orientation', 'route')
        if isinstance(ori, (int, float)):            # a bearing from north, clockwise; long sides run along it
            ang = 90.0 - float(ori)
        elif ori == 'route' and street_routes:       # along the main or local route of the structure plan it lies on
            ang = route_angle(piece)
        elif ori not in ('long side', 'route'):      # route without routes: the long side
            sys.exit('figure.%s.orientation must be "long side", "route" or a bearing in degrees' % p['name'])
        o = piece.centroid   # route: the long side instead where it holds more blocks
        ang, (bl, seq, loc) = max(((a, grid(piece, a, L_, DEP, CLS, strips, sw)) for a in
                                   dict.fromkeys([ang, lng] if ori == 'route' else [ang])), key=lambda t: len(t[1][0]))
        x0, y0, x1, y1 = loc.bounds
        GRID[p['name']] = max(GRID.get(p['name'], (0.0, 0.0)), (piece.area, ang))
        xs = sorted({x for x, _, _ in bl}); ys = sorted({y for _, y, _ in bl}); done = {}
        for r in {r for _, _, r in bl}: strips[seq[r]] += 1
        for x, y, r in bl:
            col, row = xs.index(x), ys.index(y)   # the next typology where one builds nothing: of its row's depth, or shallower
            for ty in pick(F, CLS[seq[r]], done, count, col, row) + [ty for ty in MIX if TS[ty]['D'] < seq[r]]:
                Tb = dict(TS[ty], L=L_); blds, court = block_buildings(Tb, col, row)
                got = []
                for b, part, kw in blds:
                    cl = clip(affinity.translate(b, x, y), loc)
                    if cl is not None:
                        got.append((cl, part, kw)); continue
                    # a part that does not fit falls back to its arms, and an arm longer than 50 m to bars
                    got += [(c, 'side', {}) for a in kw['arms'] for q in bars(a, Tb['gap'])
                            for c in [clip(affinity.translate(q, x, y), loc)] if c is not None]
                if got: break
            if not got:
                continue
            n_block += 1; done[(col, row)] = ty; count[ty] += 1
            for cl, part, kw in got:
                buildings.append(dict(geom=affinity.rotate(cl, ang, origin=o), t=t, nb=p['name'],
                                      phase=1 if p['name'] in CONFIG['phase1'] else None,
                                      type=Tb['type'], use0=kw.get('use', Tb['use']), fl0=Tb['fl'] + kw.get('fl_add', 0),
                                      col=col, row=row, block=n_block, part=part,
                                      roof=kw.get('roof', Tb['roof']), pmax=Tb.get('pmax', CAP)))
                if 'floors' in kw:   # a part of fixed floors and its own use, such as a garage: not scaled to the programme
                    buildings[-1].update(fixed=True, floors=kw['floors'], use=kw['use'], gf=kw.get('ground_floor'))
            cc = affinity.translate(court, x, y).intersection(loc)
            if cc.area > 200:
                courts.append(affinity.rotate(cc, ang, origin=o).difference(unary_union([affinity.rotate(q, ang, origin=o) for q, _, _ in got])))
        # secondary streets: grid lines between kept blocks
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


# ---------- street ends: led on to the next street, across the green as a path, or counted ----------
def first_hit(start, d, reach, targets):
    """the nearest point straight on from start along the unit direction d, within reach, on a target, and its kind"""
    ray = LineString([(start.x + d[0] * 0.5, start.y + d[1] * 0.5), (start.x + d[0] * reach, start.y + d[1] * reach)])
    best = None
    for kind, t in targets:
        x = ray.intersection(t)   # points, or lines where the ray runs along a target
        for part in getattr(x, 'geoms', [x]):
            for c in ([] if part.is_empty else part.coords):
                pt = Point(c); dist = start.distance(pt)
                if best is None or dist < best[0]:
                    best = (dist, pt, kind)
    return best


green_paths = []


def end_streets(sec):
    """each end of each secondary street meets a street, the site edge, the green or a centre, is led on straight
    up to street_reach_m to the first street, site edge or green, ends at the edge of its built land when nothing
    is that near, or stays a dead end.
    Ends at the green are carried across it as a path up to path_reach_m. Returns the streets and (kind, Point),
    two per street, in order."""
    sec = list(sec); ends = []
    routes_l = [g for _, g in street_routes]
    blocked = unary_union([b['geom'] for b in buildings] + [g for _, g in kept] + water)
    edge, gedge = site.boundary, green_u.boundary
    centre_u = unary_union([g for _, g in centres])
    # the buildable land of each new neighbourhood, as in the placement loop; a street belongs to the one it runs in
    lands = [g.intersection(site).difference(excl) for p, g in nbh if p['action'] != 'keep' and p['name'] in CONFIG['density']]
    for i in range(len(sec)):
        own = max(lands, key=lambda L: sec[i].intersection(L.buffer(1)).length) if lands else Polygon()
        for at in (0, -1):
            cs = list(sec[i].coords)
            p, q = Point(cs[at]), Point(cs[1] if at == 0 else cs[-2])
            others = [g for j, g in enumerate(sec) if j != i]
            if any(p.distance(g) <= 3 for g in others + routes_l):
                ends.append(('street', p)); continue
            if p.distance(edge) <= 3:
                ends.append(('site edge', p)); continue
            if not green_u.is_empty and p.distance(gedge) <= 6:
                ends.append(('green edge', p)); continue
            if not centre_u.is_empty and p.distance(centre_u) <= 3:   # the street arrives at the square
                ends.append(('centre', p)); continue
            n = p.distance(q); d = ((p.x - q.x) / n, (p.y - q.y) / n)
            targets = [('street', g) for g in others + routes_l] + [('site edge', edge)] + \
                      ([('green edge', gedge)] if not green_u.is_empty else [])
            hit = first_hit(p, d, CONFIG['street_reach_m'], targets)
            if hit is None and p.distance(own.boundary) <= 3:   # it ends where the built land ends, like a site edge
                ends.append(('land edge', p)); continue
            if hit is None or LineString([p, hit[1]]).buffer(CONFIG['sec_street_w'] / 2 - 1).intersects(blocked):
                ends.append(('dead end', p)); continue
            cs.insert(0 if at == 0 else len(cs), (hit[1].x, hit[1].y))
            sec[i] = LineString(cs)
            ends.append((hit[2], hit[1]))
    # green crossings: on from an end at the green, through it, to the next street or path
    meet = [('street', g) for g in sec] + [('street', g) for g in routes_l] + [('path', g) for _, g in path_routes]
    for k, ((kind, p), i) in enumerate(zip(ends, [j for j in range(len(sec)) for _ in (0, 1)])):
        if kind != 'green edge':
            continue
        cs = list(sec[i].coords); q = Point(cs[1] if k % 2 == 0 else cs[-2])
        if p.distance(q) == 0:
            continue
        n = p.distance(q); d = ((p.x - q.x) / n, (p.y - q.y) / n)
        hit = first_hit(p, d, CONFIG['path_reach_m'], [(t, g) for j, (t, g) in enumerate(meet) if j != i])
        if hit is None or hit[0] < 3:
            continue
        seg = LineString([p, hit[1]])
        inner = LineString([p, seg.interpolate(hit[0] - 3)])
        if inner.within(green_u.buffer(2)) and not seg.buffer(CONFIG['path_w'] / 2).intersects(blocked):
            green_paths.append(seg)
    return sec, ends


sec_streets, street_ends = end_streets(sec_streets)

# ---------- community: school, pool, daycares ----------
def blocks_by_centre_dist(cands):
    return sorted(cands, key=lambda b: b['geom'].distance(main_centre))

community = []
# ---------- community buildings on the centre that holds them (config community_buildings, a school, a pool) ----------
WARN = []   # what could not be done as asked: into stats.json and assumptions.md


def _match(word):
    """the centre whose `holds` (text or list) names the word, else the one whose name does, else None"""
    w = str(word).lower()
    for key in ('holds', 'name'):
        for p, g in centres:
            v = p.get(key) or ''
            if w in (', '.join(map(str, v)) if isinstance(v, list) else str(v)).lower():
                return p, g
    return None


def centre_for(word):
    """the centre that holds the word; the main centre, with a warning, when none does"""
    c = _match(word)
    if c is None:
        c = next((p, g) for p, g in centres if p.get('level') == 'main')
        WARN.append('no centre holds "%s": it goes on the main centre %s' % (word, c[0].get('name')))
    return c


def centre_square(p, g):
    """the square of a centre: square_main_m on the main centre, square_local_m on a local one, kept inside the
    centre and to the land left once what it holds (community buildings, school, pool) has taken its share"""
    need = 0.0
    for e in CONFIG['community_buildings'] or []:
        m_ = _match(e.get('at') or e.get('use') or '')
        if m_ is not None and m_[0] is p:
            need += max(e.get('ground_m2') or 0, (e.get('gfa') or 0) / max(1, int(e.get('floors') or 1)))
    for key, share in (('school', CONFIG['school_gfa'] / 3 + CONFIG['school_yard'] + CONFIG['school_sports']), ('pool', CONFIG['pool_plot'])):
        m_ = _match(key) if share > 0 else None
        if m_ is not None and m_[0] is p: need += share
    side = CONFIG['square_main_m'] if p.get('level') == 'main' else CONFIG['square_local_m']
    side = min(side, math.sqrt(0.4 * g.area), math.sqrt(max(g.area - need, 0.0)))
    q = g.representative_point()
    while side > 10 and not box(q.x - side / 2, q.y - side / 2, q.x + side / 2, q.y + side / 2).within(g.buffer(1)): side -= 5
    return box(q.x - side / 2, q.y - side / 2, q.x + side / 2, q.y + side / 2)


def _bearing(c):
    """the grid bearing of the built neighbourhood the centre lies in, else 0"""
    q = c.representative_point()
    for p, g in nbh:
        if p['name'] in GRID and g.buffer(1).contains(q):
            return GRID[p['name']][1]
    return 0.0


def _centre_land(p, c):
    """a centre minus its square, the streets, the kept buildings and what community buildings already took; and its square"""
    sq = centre_square(p, c)
    used = unary_union([Polygon()] + [g for _, _, g in community] + [b['geom'].buffer(2) for b in buildings if b.get('fixed')])
    return c.difference(sq).difference(street_area).difference(
        unary_union([Polygon()] + [g.buffer(CONFIG['keep_buffer']) for _, g in kept])).difference(used), sq


def _place(R, area, depth, anchor, ang=0.0, step=4.0):
    """a rectangle of `area` m2, `depth` deep, long side along the bearing ang, inside R, nearest `anchor`"""
    if R.is_empty or area <= 0: return None
    o = R.centroid; loc = affinity.rotate(R, -ang, origin=o).buffer(0.01); an = affinity.rotate(anchor, -ang, origin=o)
    prepare(loc)
    Lr = area / depth; x0, y0, x1, y1 = loc.bounds; best = None
    for Lx, Ly in ((Lr, depth), (depth, Lr)):
        x = x0
        while x + Lx <= x1:
            y = y0
            while y + Ly <= y1:
                r = box(x, y, x + Lx, y + Ly)
                if loc.contains(r):
                    dd = r.distance(an)
                    if best is None or dd < best[0]: best = (dd, r)
                y += step
            x += step
    return affinity.rotate(best[1], ang, origin=o) if best else None


def _fit(R, area, depth, anchor, ang):
    """_place at its depth, then 10 m deep, then the largest smaller rectangle that fits; and the share of area it got"""
    for s in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2):
        for d in dict.fromkeys((depth, min(depth, 10.0))):
            g = _place(R, area * s, d, anchor, ang)
            if g is not None: return g, s
    return None, 0.0


def _grow(R, core, target):
    """a ring around core inside R, grown in 2 m steps until it holds target m2 or is 150 m wide"""
    if target <= 0: return Polygon()
    r_ = 2.0
    while True:
        g = R.intersection(core.buffer(r_)).difference(core)
        if g.area >= target or r_ > 150: return g
        r_ += 2.0


ASSUMED = []   # sizes the brief did not give, named in assumptions.md and stats.json
CB = []   # (config entry, its building or None)
for e in CONFIG['community_buildings'] or []:
    use = e.get('use') or 'community building'
    if not e.get('gfa'):
        e = {**e, 'gfa': CONFIG['community_gfa_m2'], 'assumed': True}
        ASSUMED.append('%s has no floor area in the brief: built at an assumed %d m2 (community_gfa_m2, %s)'
                       % (use, e['gfa'], SOURCE.get('community_gfa_m2') or 'skill default'))
    cp, cg = centre_for(e.get('at') or use)
    R, sq = _centre_land(cp, cg); fl = int(e.get('floors') or 1)
    g, s = _fit(R, e['gfa'] / fl, float(e.get('depth') or 14), sq, _bearing(cg))
    if g is None:
        WARN.append('no room for %s on %s' % (use, cp.get('name'))); CB.append((e, None)); continue
    if s < 1:
        WARN.append('%s on %s: only %d of %d m2 floor area fit' % (use, cp.get('name'), g.area * fl, e['gfa']))
    b = dict(geom=g, t='community', nb=cp.get('name'), fixed=True, use=use, type=e.get('type', 'community'), floors=fl, phase=None)
    buildings.append(b); CB.append((e, b))
    grounds = _grow(R, g, max(0, (e.get('ground_m2') or 0) - g.area))
    community.append(('square' if any(w in use for w in ('station', 'hub', 'market')) else 'park', use + ' grounds', grounds))

# a school or a pool that a centre holds is built on that centre's land, with its yard, sports or grounds there
SCHOOL_DONE = POOL_DONE = False
pool = None
if CONFIG['school_gfa'] > 0:
    sc = _match('school')
    if sc is None:
        WARN.append('no centre holds a school: it takes the courtyard block nearest the main centre')
    else:
        R, sq = _centre_land(*sc); sfl = 3   # own assumption, as on a courtyard block
        sg, s = _fit(R, CONFIG['school_gfa'] / sfl, TYPES['high']['d'], sq, _bearing(sc[1]))
        if sg is None:
            WARN.append('no room for the school on %s: it takes the courtyard block nearest the main centre' % sc[0].get('name'))
        else:
            yard = _grow(R, sg, CONFIG['school_yard'])
            left = R.difference(sg.buffer(2)).difference(yard); sports = None
            for dp in (40.0, 50.0, 60.0):
                if sports is None and CONFIG['school_sports'] > 0:
                    sports = _place(left, CONFIG['school_sports'], dp, yard, _bearing(sc[1]))
            if sports is None and CONFIG['school_sports'] > 0:   # no rectangle fits: the largest free piece, cut to the area
                pc = max(getattr(left, 'geoms', [left]), key=lambda q: q.area) if not left.is_empty else None
                if pc is not None and pc.geom_type == 'Polygon' and pc.area >= CONFIG['school_sports']:
                    sports = _grow(pc, pc.representative_point().buffer(1), CONFIG['school_sports'])
                else:
                    WARN.append('no room for the school sports on %s' % sc[0].get('name'))
            sfl = max(sfl, math.ceil(CONFIG['school_gfa'] / sg.area - 1e-6))   # a smaller footprint: more floors
            if s < 1:
                WARN.append('the school on %s: a footprint of %d m2 fits, so it has %d floors' % (sc[0].get('name'), sg.area, sfl))
            buildings.append(dict(geom=sg, t='community', nb=sc[0].get('name'), fixed=True, use='school', type='school',
                                  floors=sfl, phase=None))
            community.append(('square', 'schoolyard', yard))
            if sports is not None: community.append(('park', 'school sports', sports))
            SCHOOL_DONE = True
if CONFIG['pool_gfa'] > 0:
    pc_ = _match('pool')
    if pc_ is None:
        WARN.append('no centre holds a pool: it takes the courtyard block nearest the main centre')
    else:
        R, sq = _centre_land(*pc_)
        hall, s = _fit(R, CONFIG['pool_gfa'] / 2, 30.0, sq, _bearing(pc_[1]))   # own: two storeys of hall height, 30 m deep
        if hall is None:
            WARN.append('no room for the indoor pool on %s: it takes the courtyard block nearest the main centre' % pc_[0].get('name'))
        else:
            if s < 1:
                WARN.append('the indoor pool on %s: only %d of %d m2 floor area fit' % (pc_[0].get('name'), hall.area * 2, CONFIG['pool_gfa']))
            pool = dict(geom=hall, t='community', nb=pc_[0].get('name'), fixed=True, use='indoor pool', type='hall', floors=2, phase=None)
            buildings.append(pool)
            community.append(('park', 'pool grounds', _grow(R, hall, max(0.0, CONFIG['pool_plot'] - hall.area))))
            POOL_DONE = True

# school: the housing block nearest the main centre, not in the 65 dB(A) strip, quiet (<55 dB day) if one is;
# its ring buildings give way to the school building, the yard and the sports ground
need = CONFIG['school_yard'] + CONFIG['school_sports']
def ring_of(c): return [b for b in buildings if b['geom'].distance(c) < 1.0 and not b.get('fixed')]
def plot_of(c): return unary_union([c, *[b['geom'] for b in ring_of(c)]])
ok = [c for c in courts if ring_of(c) and all(b['t'] != 'commercial' for b in ring_of(c))
      and plot_of(c).area >= need + 1000 and not plot_of(c).intersects(loud)]
cand = [c for c in ok if c.centroid.within(quiet)] or ok
school_court = min(cand, key=lambda c: c.distance(main_centre)) if cand and CONFIG['school_gfa'] > 0 and not SCHOOL_DONE else None
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
    sg = max([q for q in getattr(sg, 'geoms', [sg]) if q.geom_type == 'Polygon'], key=lambda q: q.area)   # no slivers or lines from the cut
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
pool_court = min(cand, key=lambda c: c.distance(main_centre)) if cand and CONFIG['pool_gfa'] > 0 and not POOL_DONE else None
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
# the land the community buildings and their grounds take: not centre ground, not public green
COMMUNITY_LAND = unary_union([Polygon()] + [g for _, _, g in community] + [b['geom'] for b in buildings if b.get('fixed')])

# ---------- heights ----------
for b in buildings:
    if b.get('fixed'):
        continue
    f = b['fl0']
    if b['geom'].distance(main_routes) <= CONFIG['route_bonus_m']: f += 1
    if b['geom'].distance(main_centre) <= CONFIG['centre_bonus_m']: f += 1
    if b['geom'].distance(green_u) <= CONFIG['green_minus_m']: f -= 1
    b['base'] = max(1, f)
    b['use'] = b['use0']
    q = b['geom'].representative_point()
    b['db'] = next((db for db, g in levels if q.within(g)), None)
    if b['db'] is None:
        if q.within(loud):
            b['use'] = 'commerce'   # the first run, on the land as it is today: no homes at 65 dB(A) or more by day
    elif b['db'] >= CONFIG['commerce_db']:
        b['use'] = 'commerce'
    elif b['db'] >= CONFIG['acoustic_db'] and b['use'] != 'commerce':
        b['acoustic'] = True
# a height profile per neighbourhood (config figure.<name>.heights), applied to the base floors before the solver
PROFILES = ('flat', 'to centre', 'from green', 'alternate')
for name in {b['nb'] for b in buildings if not b.get('fixed')}:
    F = figure_for(name); prof = F.get('heights', 'flat')
    if prof not in PROFILES:
        sys.exit('figure.%s.heights "%s" is not one of %s' % (name, prof, ', '.join(PROFILES)))
    grp = [b for b in buildings if b['nb'] == name and not b.get('fixed')]
    if prof == 'to centre' and grp:           # the nearest third of the buildings one floor up, the farthest third one down
        order = sorted(grp, key=lambda b: b['geom'].distance(main_centre)); n = len(order)
        for b in order[:n // 3]: b['base'] += 1
        for b in order[n - n // 3:]: b['base'] -= 1
    elif prof == 'from green':                 # beside the green one down (done above), well away from it one up
        for b in grp:
            if b['geom'].distance(green_u) > 3 * CONFIG['green_minus_m']: b['base'] += 1
    elif prof == 'alternate':                  # every second row one floor lower
        for b in grp:
            if b.get('row', 0) % 2: b['base'] -= 1
    for b in grp:
        b['base'] = max(1, b['base'])
        b['fmin'] = int(F.get('floors_min', 1)); b['fmax'] = min(int(F.get('floors_max', CAP)), b.get('pmax', CAP))

free =[b for b in buildings if not b.get('fixed')]
# the landmarks: the two towers nearest the main centre, else the two mixed buildings nearest it
landmarks = sorted([b for b in free if b['use'] == 'mixed' or b.get('part') == 'tower'],
                   key=lambda b: (b.get('part') != 'tower', b['geom'].distance(main_centre)))[:2]
for b in landmarks: b['landmark'] = True


def apply(group, f):
    for b in group:
        cap = CONFIG['landmark_floors'] if b.get('landmark') else min(CAP, b.get('fmax', CAP))
        b['floors'] = int(min(cap, max(b.get('fmin', 1), round(b['base'] * f))))
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
dc_cand = [b for b in home_grp if not b['geom'].intersects(loud)
           and CONFIG['daycare_gfa'] / b['geom'].area < b.get('fmax', CAP)]   # a building that holds it under its cap
day = []
if len(dc_cand) < CONFIG['daycares']:
    WARN.append('only %d of the %d daycares find a building that holds them under its cap' % (len(dc_cand), CONFIG['daycares']))
if dc_cand and CONFIG['daycares'] > 0:
    day.append(min(dc_cand, key=lambda b: b['geom'].distance(main_centre)))
    while len(day) < min(CONFIG['daycares'], len(dc_cand)):
        day.append(max([b for b in dc_cand if b not in day], key=lambda b: min(b['geom'].distance(d['geom']) for d in day)))
for b in day:
    b['daycare_floors'] = math.ceil(CONFIG['daycare_gfa'] / b['geom'].area)
    b['use'] = 'housing + daycare' if b['use'] == 'housing' else 'mixed + daycare'


def homes_m2(b):
    if b['use'] in ('housing', 'mixed'):
        return res_gfa(b)
    if b['use'].endswith('daycare') and not b.get('fixed'):
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
f_res = hi if CONFIG['homes_target_is_minimum'] else min([lo, hi], key=lambda f: (apply(home_grp, f), abs(sum(homes_m2(b) for b in buildings) - res_target))[1])
apply(home_grp, f_res)
lo, hi = 0.2, 4.0
for _ in range(40):
    mid = (lo + hi) / 2; apply(com_grp, mid)
    if sum(commerce_m2(b) for b in buildings) < CONFIG['commerce_target']: lo = mid
    else: hi = mid
f_com = min([lo, hi], key=lambda f: (apply(com_grp, f), abs(sum(commerce_m2(b) for b in buildings) - CONFIG['commerce_target']))[1]); apply(com_grp, f_com)
for b in day:  # enough floors for the daycare
    b['floors'] = max(b['floors'], b['daycare_floors'] + 1)
# homes_target_is_minimum false: the target is the brief's maximum. Above it, one floor off the home building with
# the most floors (the smallest first), never a landmark nor below its floors_min or its daycare, until homes are within it
TRIM = 0
while 'homes_target_is_minimum' in _values and not CONFIG['homes_target_is_minimum'] and sum(homes_m2(b) for b in buildings) > res_target:
    cand = [b for b in home_grp if not b.get('landmark') and b['floors'] > max(b.get('fmin', 1), b.get('daycare_floors', 0) + 1)]
    if not cand:
        WARN.append('homes stay above the maximum of %d: no home building can lose a floor' % CONFIG['homes_target']); break
    b = max(cand, key=lambda b: (b['floors'], -b['geom'].area)); b['floors'] -= 1; TRIM += 1

# a shop the brief asks for (config `food_market`, a note), in the ground floor of the mixed building nearest the centre
if CONFIG.get('food_market') and any(b['use'] == 'mixed' for b in buildings):
    mk = min([b for b in buildings if b['use'] == 'mixed'], key=lambda b: b['geom'].distance(main_centre))
    mk['note'] = '%s (%s)' % (CONFIG['food_market'], SOURCE.get('food_market', ''))

# ---------- streets, open space, trees ----------
feats = []


def add(kind, geom, **props):
    props = {'kind': kind, **props}
    feats.append({'type': 'Feature', 'properties': props, 'geometry': mapping(transform(TO_LL, geom))})


for b in buildings:
    if 'block' not in b: n_block += 1; b['block'] = n_block   # a community building is a block of its own
    u = b['use']   # the ground floor: a part's own (a garage's mobility), the shops of a mixed building, a daycare, else the use
    gf = b.get('gf') or ('commerce' if u.startswith('mixed') else 'daycare' if 'daycare' in u else u)
    pr = dict(floors=b['floors'], height_m=round(b['floors'] * FH, 1), use=b['use'], type=b['type'], existing=False,
              footprint_m2=round(b['geom'].area), gfa_m2=round(gfa(b)), neighbourhood=b['nb'], block=b['block'],
              part=b.get('part', 'building'), roof=b.get('roof', 'flat'), ground_floor=gf)
    if b.get('phase'): pr['phase'] = b['phase']
    if b.get('landmark'): pr['landmark'] = True
    if b.get('daycare_floors'): pr['daycare_floors'] = b['daycare_floors']
    if b.get('note'): pr['note'] = b['note']
    if b.get('db') is not None: pr['noise_day_db'] = b['db']
    if b.get('acoustic'): pr['acoustic_protection'] = True
    if 'row' in b: pr['row'], pr['col'] = b['row'], b['col']   # the block's place in its land's grid
    add('building', b['geom'], **pr)
for p, g in kept:
    fl = p.get('floors') or 1
    add('building', g, floors=fl, height_m=p.get('height'), use=p.get('use'), type=p.get('building'), existing=True,
        height_source=p.get('height_source'), osm_id=p.get('id'))
for p, g in street_routes:
    add('street', g.intersection(site.buffer(5)) if g.intersects(site) else g, width=CONFIG['street_w'], name=p['name'], level=p['level'])
for p, g in path_routes:
    add('street', g, width=CONFIG['path_w'], name=p['name'], level='path')
for i, g in enumerate(sec_streets):
    dead = {'dead_end': True} if 'dead end' in (street_ends[2 * i][0], street_ends[2 * i + 1][0]) else {}
    add('street', g, width=CONFIG['sec_street_w'], level='secondary', note='greened secondary street', **dead)
for g in green_paths:
    add('street', g, width=CONFIG['path_w'], level='path', note='path across the green')
for p, g in greens:
    add('open-space', g.intersection(site), use='park', name=p['name'])
for w in water:
    add('open-space', w, use='water')
sq_all = []
for p, g in centres:
    sq = centre_square(p, g)
    sq_all.append(sq)
    add('open-space', sq, use='square', name=p['name'])
    rest = g.difference(sq).difference(COMMUNITY_LAND)
    if rest.area > 50: add('open-space', rest, use='park', name=p['name'] + ' (centre ground)')
for c in courts:
    if c.area > 100: add('open-space', c, use='garden', type='courtyard')
for u, t, g in community:
    if g.area > 50: add('open-space', g, use=u, type=t)

bu = unary_union([b['geom'] for b in buildings] + [g for _, g in kept])
trees = []
all_streets = [g for _, g in street_routes] + sec_streets
# trees only along the street stretches in or just beside the new neighbourhoods; green paths get none
new_land = unary_union([g.intersection(site) for p, g in nbh if p['action'] != 'keep' and p['name'] in CONFIG['density']])
for g in all_streets:
    g = g.intersection(new_land.buffer(CONFIG['street_w']))
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
green_land = green_u.intersection(site).difference(COMMUNITY_LAND).area + sum(g.difference(s).difference(COMMUNITY_LAND).area for (_, g), s in zip(centres, sq_all))
total = sum(gfa(b) for b in new)
rows = [
    ('homes (count)', CONFIG['homes_target'], round(homes), '%s; design homes = housing floor area / %d m2 per home (%s)' % (SOURCE.get('homes_target', 'not in the brief'), CONFIG['m2_per_home'], SOURCE.get('m2_per_home', 'not in the brief'))),
    ('housing floor area', round(res_target), round(H_m2), '%d homes x %d m2 (%s)' % (CONFIG['homes_target'], CONFIG['m2_per_home'], SOURCE.get('m2_per_home', 'not in the brief'))),
    ('commerce floor area', round(CONFIG['commerce_target']), round(C_m2), SOURCE.get('commerce_target', 'not in the brief') + '; halls, buildings too loud for homes, ground floors of mixed blocks'),
    ('daycare floor area', round(CONFIG['daycare_gfa'] * CONFIG['daycares']), round(dcm), '%s, %d x %d m2' % (SOURCE.get('daycare_gfa', 'not in the brief'), CONFIG['daycares'], CONFIG['daycare_gfa'])),
    ('primary school floor area', round(CONFIG['school_gfa']), round(school), SOURCE.get('school_gfa', 'not in the brief')),
    ('schoolyard (land)', round(CONFIG['school_yard']), round(yard), SOURCE.get('school_yard', 'not in the brief')),
    ('school sports (land)', round(CONFIG['school_sports']), round(spt), SOURCE.get('school_sports', 'not in the brief')),
    ('indoor pool floor area', round(CONFIG['pool_gfa']), round(poolg), SOURCE.get('pool_gfa', 'not in the brief')),
    *[((e.get('use') or 'community building') + ' floor area', round(e.get('gfa') or 0), round(gfa(b)) if b else 0,
       ('assumed size: ' + (SOURCE.get('community_gfa_m2') or 'skill default') if e.get('assumed') else SOURCE.get('community_buildings', ''))) for e, b in CB],
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
def mixed(n):   # the blocks of each type a neighbourhood's grid kept, once the community buildings took theirs
    G = [b for b in new if b['nb'] == n and 'row' in b]
    return {t: len({b['block'] for b in G if b['type'] == t}) for t in sorted({b['type'] for b in G})}
stats['figure'] = {n: {'typology': f['typology'], 'orientation': f['orientation'], 'blocks': mixed(n)} for n, f in figures.items()}
stats['blocks'] = {t: len({b['block'] for b in new if b['type'] == t}) for t in sorted({b['type'] for b in new})}
stats['at_cap_share'] = round(stats['at_cap'] / max(1, stats['n_home']), 2)
stats['profiles'] = {name: figure_for(name).get('heights', 'flat') for name in CONFIG['density']}
stats['street_ends'] = {k: sum(1 for kind, _ in street_ends if kind == k) for k in sorted({kind for kind, _ in street_ends})}
stats['secondary_dead_ends'] = stats['street_ends'].get('dead end', 0)
stats['green_crossings'] = len(green_paths)
stats['community'] = {(e.get('use') or 'community building'): b is not None for e, b in CB}
stats['assumed_sizes'] = ASSUMED
stats['floors_off_for_max'] = TRIM   # floors taken off so the homes stay within the brief's maximum
stats['warnings'] = WARN
stats['design_noise'] = bool(levels)
stats['acoustic_protection'] = sum(1 for b in new if b.get('acoustic'))
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
    fh.write('\n## Figure\n\n')
    for n, f in figures.items():
        o = f['orientation']
        src = (SOURCE.get('figure') or 'no source given') if 'figure' in _values else 'skill default'
        fh.write('- %s: %s (blocks: %s), orientation %s, row gap %g m (%s)\n'
                 % (n, f['typology'], ', '.join('%d %s' % (v, k) for k, v in mixed(n).items()),
                    '%g deg' % o if isinstance(o, (int, float)) else o, f['row_gap'], src))
    fh.write('\n## Heights\n\n')
    for n in CONFIG['density']:
        F = figure_for(n)
        fh.write('- %s: profile %s, floors %d to %d\n' % (n, F.get('heights', 'flat'), int(F.get('floors_min', 1)), int(F.get('floors_max', CAP))))
    if TRIM:
        fh.write('- %d floors taken off the home buildings with the most floors, so the homes (%d) stay within the '
                 'maximum of %d (homes_target, %s)\n' % (TRIM, stats['homes'], CONFIG['homes_target'], SOURCE.get('homes_target_is_minimum', '')))
    if stats['at_cap_share'] > 0.5:
        fh.write('- %d of %d home buildings stand at the cap of %d floors: the programme barely fits or does not fit '
                 'under the height limit. More land in the structure plan, a lower m2 per home, or a higher limit would be needed.\n'
                 % (stats['at_cap'], stats['n_home'], CAP))
    if WARN:
        fh.write('\n## Warnings\n\n' + ''.join('- %s\n' % w for w in WARN))
