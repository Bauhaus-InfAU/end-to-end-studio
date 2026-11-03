"""Measures a site as it is (--state today) or a design on it (--state design), the same way both times.

    python measure.py --proposal <proposal folder> --site <site folder> --config <proposal>/analysis/config.json --state today|design

Writes into <proposal>/analysis/: metrics.csv (rows of this state replaced), layers_<state>.geojson (for draw.py),
and on today keep.geojson. Prints what the data lacks, for summary.md.
"""
import argparse, csv, json, os, sys
import networkx as nx
from shapely.geometry import shape, mapping, Point, LineString
from shapely.ops import unary_union, substring
from shapely.strtree import STRtree
sys.path.insert(0, os.path.dirname(__file__))
from common import read_config, load, projector, matches

A = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
A.add_argument('--proposal', required=True)
A.add_argument('--site', required=True)
A.add_argument('--config', required=True)
A.add_argument('--state', choices=['today', 'design'], required=True)
ARGS = A.parse_args()
OUT = os.path.join(ARGS.proposal, 'analysis')
os.makedirs(OUT, exist_ok=True)
CFG, SRC = read_config(ARGS.config, ['sealing', 'green', 'walk_radii_m', 'walk_side_m', 'destinations', 'uses_from_site'])
TO_M, TO_WGS = projector(ARGS.site, CFG.get('epsg'))
DESIGN = ARGS.state == 'design'
MISSING, ROWS = [], []


def layer(name):
    return [(f['properties'], TO_M(shape(f['geometry']))) for f in load(os.path.join(ARGS.site, name + '.geojson'))
            if f.get('geometry')]


def row(measure, value, unit, source):
    ROWS.append({'measure': measure, 'value': round(value, 2), 'unit': unit, 'state': ARGS.state, 'source': source})


SITE = layer('site')[0][1].buffer(0)
SITE_HA = SITE.area / 1e4
LAYERS = {n: layer(n) for n in ['buildings', 'street-land', 'streets', 'water', 'rail', 'plots']}
MASSING = []
if DESIGN:
    mp = os.path.join(ARGS.proposal, 'massing', 'massing.geojson')
    if not os.path.exists(mp):
        sys.exit('no massing/massing.geojson: the design run needs the massing')
    MASSING = [(f['properties'], TO_M(shape(f['geometry']))) for f in load(mp) if f.get('geometry')]


def kind(k):
    return [(p, g) for p, g in MASSING if p.get('kind') == k]


def street_poly(p, g, design=False):
    w = p.get('width') if design else CFG.get('street_widths_m', {}).get(p.get('highway'))
    return g.buffer(float(w) / 2, cap_style=2) if w and g.geom_type != 'Polygon' else (g if g.geom_type != 'LineString' else None)


# ---------- the ground cover: one class per piece of the site, top layer first ----------
def classes_today():
    out = []
    for name in CFG['uses_from_site']:
        feats = LAYERS.get(name) or layer(name)
        if name == 'street-land' and not feats:
            feats = [({'use': 'street'}, street_poly(p, g)) for p, g in LAYERS['streets']]
            feats = [(p, g) for p, g in feats if g is not None]
            MISSING.append('no street-land layer: streets are their lines at assumed widths')
        if name == 'plots':  # small patches lie on top of large ones
            feats = sorted(feats, key=lambda f: f[1].area)
            out += [(p.get('landuse') or 'plots', g) for p, g in feats if g.geom_type in ('Polygon', 'MultiPolygon')]
            continue
        cls = {'buildings': lambda p: 'building', 'street-land': lambda p: p.get('use') or 'street',
               'water': lambda p: 'water'}.get(name, lambda p: name)
        groups = {}
        for p, g in feats:
            if g.geom_type in ('Polygon', 'MultiPolygon') and g.intersects(SITE):
                groups.setdefault(cls(p), []).append(g.buffer(0))
        groups = {c: unary_union(gs) for c, gs in groups.items()}
        if name == 'street-land' and 'street' in groups and LAYERS['streets']:
            # street land often holds verges and embankments: only the roadway (lines at their widths) is street
            road = unary_union([q for q in (street_poly(p, g) for p, g in LAYERS['streets'] if g.intersects(SITE.buffer(50))) if q is not None])
            groups['street verge'] = groups['street'].difference(road)
            groups['street'] = groups['street'].intersection(road)
        out += list(groups.items())
    return out


def classes_design():
    out = [('building', unary_union([g for p, g in kind('building')]))]
    for p, g in kind('street'):
        sp = street_poly(p, g, design=True)
        if sp is not None:
            out.append(('design: path' if p.get('level') == 'path' else 'design: street', sp))
    for p, g in kind('open-space'):
        out.append(('water' if p.get('use') == 'water' else 'design: ' + str(p.get('use') or 'open space'), g))
    new = [g for p, g in kind('building') if not p.get('existing')]
    if new and CFG.get('design_plot_m'):
        out.append(('design: plot', unary_union([g.buffer(CFG['design_plot_m']) for g in new])))
    return out + classes_today()


cover, taken = [], SITE.buffer(0).difference(SITE)  # empty
for c, g in (classes_design() if DESIGN else classes_today()):
    piece = g.buffer(0).intersection(SITE).difference(taken)
    if piece.area > 1:
        cover.append((c, piece))
        taken = taken.union(piece)
rest = SITE.difference(taken)
if rest.area > 1:
    cover.append(('untagged', rest))

SEAL = CFG['sealing']
GREEN = CFG['green']


def sealing(c):
    return 'fully' if c in SEAL.get('fully', []) else 'partly' if c in SEAL.get('partly', []) else SEAL.get('default', 'unsealed')


def green_group(c):
    return next((g for g, cs in GREEN.items() if c in cs), None)


area = {}
for c, g in cover:
    area[c] = area.get(c, 0) + g.area
src_cover = 'site layers ' + ', '.join(CFG['uses_from_site']) + (' and massing.geojson' if DESIGN else '')
for c, a in sorted(area.items(), key=lambda x: -x[1]):
    row(f'use {c}', a / 1e4, 'ha', src_cover)
    row(f'use {c}', a / SITE.area * 100, '%', src_cover)
row('site area', SITE_HA, 'ha', 'site.geojson')

for s in ['fully', 'partly', 'unsealed']:
    a = sum(g.area for c, g in cover if sealing(c) == s)
    name = 'unsealed' if s == 'unsealed' else f'sealed {s}'
    row(name, a / 1e4, 'ha', src_cover + '; classes: ' + SRC.get('sealing', ''))
    row(name, a / SITE.area * 100, '%', src_cover + '; classes: ' + SRC.get('sealing', ''))
unclassed = sorted({c for c, g in cover if c not in SEAL.get('fully', []) + SEAL.get('partly', [])} - {c for cs in GREEN.values() for c in cs} - {'water', 'untagged'})
if unclassed:
    MISSING.append('counted as ' + SEAL.get('default', 'unsealed') + ' by default: ' + ', '.join(unclassed))

for grp in GREEN:
    a = sum(g.area for c, g in cover if green_group(c) == grp)
    row(f'green {grp}', a / 1e4, 'ha', src_cover + '; groups: ' + SRC.get('green', ''))
ga = sum(g.area for c, g in cover if green_group(c) and green_group(c) != 'farmland')
row('green share without farmland', ga / SITE.area * 100, '%', src_cover)
if DESIGN and CFG.get('residents'):
    park = sum(g.area for c, g in cover if c == 'design: park')
    row('green public per resident', park / float(CFG['residents']), 'm2', 'design parks / residents (' + SRC.get('residents', '') + ')')

# ---------- edges: what the boundary meets, and the crossings ----------
ring = SITE.buffer(30).difference(SITE)
MAIN = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'motorway_link', 'trunk_link', 'primary_link'}
edge_sets = [('rail', [g for p, g in LAYERS['rail']]),
             ('main road', [g for p, g in LAYERS['streets'] if p.get('highway') in MAIN]),
             ('water', [g for p, g in LAYERS['water']]),
             ('built', [g for p, g in LAYERS['buildings']])]
trees = [(n, STRtree(gs)) for n, gs in edge_sets if gs]
B = SITE.exterior
STEP = 10.0
samples = []
for i in range(int(B.length // STEP) + 1):
    p = B.interpolate(i * STEP)
    zone = p.buffer(30).intersection(ring)
    samples.append(next((n for n, t in trees if len(t.query(zone, predicate='intersects'))), 'open'))
stretches, start = [], 0
for i in range(1, len(samples) + 1):
    if i == len(samples) or samples[i] != samples[start]:
        stretches.append((samples[start], substring(B, start * STEP, min(i * STEP, B.length))))
        start = i
NOWALK = set(CFG.get('not_walkable', []))
walk_lines = [g for p, g in LAYERS['streets'] if p.get('highway') not in NOWALK and g.geom_type.endswith('LineString')]
cross_lines = list(walk_lines)
if DESIGN:
    cross_lines += [g for p, g in kind('street') if g.geom_type.endswith('LineString')]
pts = []
for ln in cross_lines:
    x = ln.intersection(B)
    for q in getattr(x, 'geoms', [x]):
        if q.geom_type == 'Point' and all(q.distance(o) > 15 for o in pts):
            pts.append(q)
crossings = [(samples[min(int(round(B.project(q) / STEP)), len(samples) - 1)], q) for q in pts]
for n in ['rail', 'main road', 'water', 'built', 'open']:
    L = sum(g.length for c, g in stretches if c == n)
    if L:
        row(f'edge {n}', L, 'm', 'site.geojson against rail, streets, water, buildings within 30 m outside')
        row(f'crossings {n}', sum(1 for c, q in crossings if c == n), 'count', 'walkable streets and paths across the boundary')
row('crossings all', len(crossings), 'count', 'walkable streets and paths across the boundary' + (', with the design streets' if DESIGN else ''))

# ---------- walking reach along the network ----------
lines = walk_lines
if DESIGN:
    blocked = unary_union([g for p, g in kind('building') if not p.get('existing')])
    lines = [ln.difference(blocked) for ln in walk_lines] + [g for p, g in kind('street') if g.geom_type.endswith('LineString')]
noded = unary_union([ln for ln in lines if not ln.is_empty])
G = nx.Graph()
key = lambda c: (round(c[0], 1), round(c[1], 1))
for seg in getattr(noded, 'geoms', [noded]):
    if seg.geom_type == 'LineString' and seg.length > 0:
        u, v = key(seg.coords[0]), key(seg.coords[-1])
        if not G.has_edge(u, v) or G[u][v]['weight'] > seg.length:
            G.add_edge(u, v, weight=seg.length, geom=seg)
nodes = list(G.nodes)
node_tree = STRtree([Point(n) for n in nodes])
SIDE = float(CFG['walk_side_m'])
radii = [float(r) for r in CFG['walk_radii_m']]
reach_polys = []
for dname, spec in CFG['destinations'].items():
    geoms = [g for p, g in (LAYERS.get(spec.get('layer')) or layer(spec.get('layer'))) if matches(p, spec.get('where'))]
    if DESIGN and spec.get('design'):
        geoms += [g for p, g in MASSING if matches(p, spec['design'])]
    if not geoms:
        MISSING.append(f'walking reach to {dname}: no {dname} in the data, not measured')
        continue
    src = '__src__'
    G.add_node(src)
    for g in geoms:
        for i in node_tree.query(g.buffer(SIDE)):
            n = nodes[i]
            d = Point(n).distance(g)
            if not G.has_edge(src, n) or G[src][n]['weight'] > d:
                G.add_edge(src, n, weight=d, geom=None)
    dist = nx.single_source_dijkstra_path_length(G, src, cutoff=max(radii), weight='weight')
    G.remove_node(src)
    for R in radii:
        parts = []
        for u, v, e in G.edges(data=True):
            du, dv, L = dist.get(u, 1e12), dist.get(v, 1e12), e['weight']
            if du >= R and dv >= R:
                continue
            ln = e['geom']
            if key(ln.coords[0]) != u:
                u, v, du, dv = v, u, dv, du
            a, b = min(L, max(0, R - du)), min(L, max(0, R - dv))
            if a + b >= L:
                parts.append(ln)
            else:
                if a > 0: parts.append(substring(ln, 0, a))
                if b > 0: parts.append(substring(ln, L - b, L))
        reached = unary_union(parts).buffer(SIDE).intersection(SITE) if parts else SITE.difference(SITE)
        row(f'reach {int(R)} m {dname}', reached.area / SITE.area * 100, '%',
            f'{len(geoms)} {dname} from {spec.get("layer")}' + (' and the design' if DESIGN and spec.get('design') else '')
            + f'; along walkable streets and paths, {SIDE:.0f} m either side; ' + SRC.get('walk_radii_m', ''))
        reach_polys.append(({'dest': dname, 'radius': int(R)}, reached))

# ---------- what to keep ----------
keep_feats = []
for k in CFG.get('keep', []):
    if not k.get('layer'):
        MISSING.append(f'keep {k.get("what")}: no layer shows it ({k.get("reason", "")})')
        continue
    found = [g.intersection(SITE) for p, g in (LAYERS.get(k['layer']) or layer(k['layer'])) if matches(p, k.get('where')) and g.intersects(SITE)]
    found = [g for g in found if not g.is_empty]
    if not found:
        MISSING.append(f'keep {k.get("what")}: none inside the site in {k["layer"]}')
        continue
    keep_feats += [({'what': k.get('what'), 'reason': k.get('reason', ''), 'layer': k['layer']}, g) for g in found]
    if not DESIGN:
        row(f'keep {k.get("what")}', len(found), 'count', f'{k["layer"]}.geojson; {k.get("reason", "")}')
        a = unary_union([g.buffer(0) for g in found]).area  # overlaps counted once
        if a > 1:
            row(f'keep {k.get("what")}', a / 1e4, 'ha', f'{k["layer"]}.geojson; {k.get("reason", "")}')
if not DESIGN and keep_feats:
    row('built over kept land', 0, 'ha', 'nothing is built over it today')
if DESIGN and keep_feats:
    new_built = unary_union([g for p, g in kind('building') if not p.get('existing')] +
                            [street_poly(p, g, True) for p, g in kind('street') if p.get('level') != 'path' and street_poly(p, g, True) is not None])
    hit = unary_union([g.buffer(0.5) if g.area == 0 else g for p, g in keep_feats]).intersection(new_built)
    row('built over kept land', hit.area / 1e4, 'ha', 'new buildings and streets over what the today run keeps')

# ---------- write ----------
def fc(items):
    return {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': p, 'geometry': mapping(TO_WGS(g))} for p, g in items if not g.is_empty]}


feats = [({'layer': 'site'}, SITE)]
feats += [({'layer': 'cover', 'class': c, 'sealing': sealing(c), 'green': green_group(c)}, g) for c, g in cover]
feats += [({'layer': 'edge', 'class': c}, g) for c, g in stretches]
feats += [({'layer': 'crossing', 'class': c}, q) for c, q in crossings]
feats += [({'layer': 'reach', **p}, g) for p, g in reach_polys]
json.dump(fc(feats), open(os.path.join(OUT, f'layers_{ARGS.state}.geojson'), 'w', encoding='utf8'))
if not DESIGN:
    json.dump(fc(keep_feats), open(os.path.join(OUT, 'keep.geojson'), 'w', encoding='utf8'))

mpath = os.path.join(OUT, 'metrics.csv')
old = [r for r in csv.DictReader(open(mpath, encoding='utf8'))] if os.path.exists(mpath) else []
old = [r for r in old if r['state'] != ARGS.state]
with open(mpath, 'w', newline='', encoding='utf8') as f:
    w = csv.DictWriter(f, fieldnames=['measure', 'value', 'unit', 'state', 'source'])
    w.writeheader()
    w.writerows(old + ROWS)

sealed = {r['measure']: r['value'] for r in ROWS if r['unit'] == '%' and r['measure'] in ('sealed fully', 'sealed partly', 'unsealed')}
print(f'{ARGS.state}: site {SITE_HA:.1f} ha; fully sealed {sealed.get("sealed fully", 0):.1f} %, partly {sealed.get("sealed partly", 0):.1f} %, '
      f'unsealed {sealed.get("unsealed", 0):.1f} %; {len(ROWS)} rows in metrics.csv')
for m in MISSING:
    print('missing:', m)
