"""The mobility plan of a design: routes by mode, stops, hubs and car access, the walking distance to the main stop.

    python mobility.py --proposal <proposal folder> --site <site folder> --config <proposal>/mobility/config.json
                       [--style <proposal>/drawing-graphics/style.json]

config.json holds the brief's values, each as {"value": ..., "source": "<brief file> p. N" or "assumption: ..."}:
hub, main_stop, walk_limits_m, car_access and scale are required; main_stop_mode, no_car_link, bike_destinations,
stops, garages, modes and labels are optional, and any key of DEFAULTS may be overridden. Every name is a name in
structure-plan/structure-plan.geojson. Reads the structure plan (required), the massing, the streets skill's
surface and centrelines when they exist, and the drawing standard. Writes mobility.geojson, stats.json, walk.json,
assumptions.md and mobility_1-<scale>.svg and .png into <proposal>/mobility/.
"""
import argparse, json, math, os, re, subprocess, sys
from xml.sax.saxutils import escape
import networkx as nx
import pyproj
import shapely
from shapely.geometry import shape, mapping, Point, box
from shapely.ops import transform, unary_union, linemerge
from shapely.strtree import STRtree


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


# the skill's own numbers and words: (value, meaning)
DEFAULTS = {
    'mode_words': ({'car': ['car', 'cars', 'lorry', 'lorries'], 'bus': ['bus', 'buses'],
                    'bike': ['cycle', 'cycles', 'cycling', 'cyclist', 'cyclists', 'bike', 'bikes', 'bicycle', 'bicycles'],
                    'foot': ['foot', 'walk', 'walking', 'walkers', 'pedestrian', 'pedestrians']},
                   'the words in a route\'s `mode` text that give each mode'),
    'not_words': (['no', 'not', 'without'], 'a mode word one or two words after one of these is not counted ("no car link")'),
    'mode_by_level': ({'main': ['car', 'bus', 'bike', 'foot'], 'local': ['car', 'bike', 'foot'], 'landscape': ['bike', 'foot']},
                      'the modes of a route whose `mode` text names none, by its level'),
    'massing_modes': ({'secondary': ['bike', 'foot', 'car'], 'path': ['foot', 'bike']},
                      'the modes of the massing\'s secondary streets and paths; their car is access only, no through route'),
    'housing_words': (['housing', 'residential', 'mixed', 'home'], 'a new building whose use has one of these counts as housing'),
    'hub_words': (['station', 'hub'], 'a massing building whose use has one of these is the hub'),
    'local_hub_words': (['mobility', 'sharing'], 'a centre whose `holds` has one of these gets a local hub'),
    'node_step_m': (20.0, 'the walking network has a node at least every this many metres along a line'),
    'node_round_m': (2.0, 'line ends closer than this are one node'),
    'join_m': (15.0, 'a walking line that ends this close to another part of the network is joined to it (drawing gaps)'),
    'car_join_m': (5.0, 'the same for the car network, smaller so that a gap meant as a closure stays one'),
    'gate_snap_m': (30.0, 'a gateway this close to the car network counts as on it'),
    'site_pad_m': (40.0, 'ground shown around the site, metres'),
    'panel_w_mm': (564.0, 'the width a panel has for the plan, mm (an A1 panel less its margins); wider: cropped to the new buildings'),
    'crop_pad_m': (60.0, 'ground around the new buildings when the plan is cropped, metres'),
    'text_floor_mm': (3.2, 'no text smaller than this on paper (12 px, 9 pt)'),
    'legend_mm': (30.0, 'the least height of the strip under the map, mm'),
    'png_px_per_mm': (4, 'PNG resolution, pixels per printed mm'),
    'label_gap_mm': (1.2, 'a label sits this far from the edge of its symbol, mm on paper'),
    'leader_mm': ([7, 11, 15], 'how far out a label on a leader line may go when no place beside its symbol is free, mm'),
    'street_widths': ({'motorway': 28, 'trunk': 22, 'trunk_link': 9, 'primary': 18, 'secondary': 15, 'tertiary': 13,
                       'tertiary_link': 8, 'residential': 10, 'unclassified': 8, 'living_street': 7, 'service': 5,
                       'pedestrian': 6, 'track': 3.5, 'cycleway': 3, 'footway': 2.5, 'path': 2, 'steps': 2},
                      'street widths by class, metres, only without the streets skill\'s surface'),
    'street_w_other': (6.0, 'metres for a street class not in the table'),
    'street_w_new': (10.0, 'metres for a massing street without a width'),
}
LABELS = {'title': 'Mobility plan', 'bus': 'Bus', 'car': 'Car access street', 'car-access': 'Shared street, cars for access only',
          'bike': 'Main bike route', 'bike-local': 'Local bike route', 'foot': 'Footpath', 'stop': 'Main stop',
          'bus-stop': 'Bus stop', 'hub': 'Mobility hub', 'local-hub': 'Local mobility point', 'garage': 'Garage',
          'access': 'Car access', 'ring': 'Straight-line distance from the main stop', 'site': 'Project site',
          'new': 'New buildings', 'existing': 'Kept buildings', 'context': 'Existing buildings', 'street': 'Streets',
          'walk': 'By the street and path network, of the new housing floor area {shares} of the main stop{unreached}.',
          'within': '{p} % lies within {m} m', 'unreached': '; {p} % is not reached'}
FALLBACK_STYLE = {'paper': '#ffffff', 'ink': '#1a1a1a', 'accent': '#d9302b', 'new': '#d9302b', 'existing': '#d0d0d0',
                  'context': '#e4e4e4', 'street': '#f4f4f4', 'path': '#b0b0b0', 'font': 'Arial, Helvetica, sans-serif',
                  'thin': 0.13, 'mid': 0.25, 'thick': 0.5, 'text': 3.2, 'title': 5.6}
ORDER = ['bus', 'car', 'bike', 'foot']

A = argparse.ArgumentParser(description='The mobility plan of a design.')
A.add_argument('--proposal', required=True)
A.add_argument('--site', required=True, help='the folder with site.geojson and its layers')
A.add_argument('--config', required=True)
A.add_argument('--style', help='the drawing standard\'s style.json')
ARGS = A.parse_args()
RUN, SITE = ARGS.proposal, ARGS.site
OUT = os.path.join(RUN, 'mobility')
CFG, SOURCE = read_config(ARGS.config, ['hub', 'main_stop', 'walk_limits_m', 'car_access', 'scale'])
D = {k: CFG.get(k, v) for k, (v, _) in DEFAULTS.items()}
USED = set()
LAB = {**LABELS, **(CFG.get('labels') or {})}
os.makedirs(OUT, exist_ok=True)

style_path = ARGS.style or os.path.join(RUN, 'drawing-graphics', 'style.json')
S = dict(FALLBACK_STYLE)
if os.path.exists(style_path):
    S.update(json.load(open(style_path, encoding='utf8')))
FONT = escape(str(S['font']), {'"': "'"})
TXT = max(float(D['text_floor_mm']), float(S.get('text') or 0))
TITLE = max(TXT, float(S.get('title') or 0))

site_ll = shape(json.load(open(os.path.join(SITE, 'site.geojson'), encoding='utf8'))['features'][0]['geometry'])
EPSG = CFG.get('epsg') or utm_epsg(site_ll.centroid.x, site_ll.centroid.y)
TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
TO_LL = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform
site = transform(TO_M, site_ll)
_src = os.path.join(SITE, 'SOURCES.md')
CREDIT = ('Map data © OpenStreetMap contributors (ODbL, https://www.openstreetmap.org/copyright).'
          if os.path.exists(_src) and 'OpenStreetMap' in open(_src, encoding='utf8').read() else '')


def load(path):
    """[(properties, geometry in metres)] of a GeoJSON, or None when the file is missing."""
    if not os.path.exists(path):
        return None
    out = []
    for f in json.load(open(path, encoding='utf8'))['features']:
        if f.get('geometry'):
            g = transform(TO_M, shape(f['geometry']))
            if g.geom_type.endswith('Polygon') and not g.is_valid:
                g = g.buffer(0)
            out.append((f.get('properties') or {}, g))
    return out


def lines(g):
    """The LineStrings of a geometry."""
    if g.is_empty:
        return []
    if g.geom_type == 'LineString':
        return [g]
    return [q for p in getattr(g, 'geoms', []) for q in lines(p)]


def merged(g):
    return linemerge(g) if g.geom_type == 'MultiLineString' else g


SP = load(os.path.join(RUN, 'structure-plan', 'structure-plan.geojson'))
if SP is None:
    sys.exit('missing structure-plan/structure-plan.geojson in the proposal: run the structure plan first')
MASS = load(os.path.join(RUN, 'massing', 'massing.geojson'))
STREETS = load(os.path.join(RUN, 'streets', 'streets.geojson'))
CTX = load(os.path.join(SITE, 'buildings.geojson')) or []
SITE_STREETS = load(os.path.join(SITE, 'streets.geojson')) or []
missing = []
if MASS is None:
    missing.append('massing (no new buildings, no walking shares)')
    MASS = []
if STREETS is None:
    missing.append('streets (the site\'s street lines at assumed widths)')

lower = lambda s: str(s or '').strip().lower()
GATES = {lower(p.get('name')): g for p, g in SP if p.get('kind') == 'gateway'}
CENTRES = {lower(p.get('name')): (p, g) for p, g in SP if p.get('kind') == 'centre'}
ROUTES = [(p, merged(g)) for p, g in SP if p.get('kind') == 'route' and not g.is_empty]
not_found = []


def place(name):
    """The point of a gateway or a centre of the structure plan, or None."""
    n = lower(name)
    if n in GATES:
        return GATES[n] if GATES[n].geom_type == 'Point' else GATES[n].representative_point()
    if n in CENTRES:
        g = CENTRES[n][1]
        return g.centroid if g.contains(g.centroid) else g.representative_point()
    not_found.append(name)
    return None


def has_word(text, words):
    return any(re.search(r'\b%s\b' % re.escape(w), lower(text)) for w in words)


def modes_of(text):
    """The modes a route's `mode` text names, skipping a mode word right after a "no"."""
    words = re.findall(r'[a-z]+', lower(text))
    USED.update(['mode_words', 'not_words'])
    found = set()
    for i, w in enumerate(words):
        if any(n in words[max(0, i - 2):i] for n in D['not_words']):
            continue
        found |= {m for m, ws in D['mode_words'].items() if w in ws}
    return [m for m in ORDER if m in found]


feats = []   # (properties, geometry in metres)


def add(geom, **props):
    feats.append((props, geom))
    return geom


# ---------------- routes ----------------
hub_name, stop_name = CFG['hub'], CFG['main_stop']
if lower(hub_name) not in CENTRES:
    sys.exit('hub: no centre named "%s" in the structure plan (centres: %s)'
             % (hub_name, ', '.join(p.get('name') for p, g in CENTRES.values())))
if lower(stop_name) not in GATES and lower(stop_name) not in CENTRES:
    sys.exit('main_stop: no gateway or centre named "%s" in the structure plan' % stop_name)

dest = {lower(b.get('route')): b.get('to') for b in (CFG.get('bike_destinations') or [])}
over = {lower(k): v for k, v in (CFG.get('modes') or {}).items()}
for p, g in ROUTES:
    name, lvl = p.get('name') or 'route', lower(p.get('level'))
    if lower(name) in over:
        ms, how = [m for m in ORDER if m in over[lower(name)]], 'modes from config.json (%s)' % SOURCE.get('modes', '')
    else:
        ms, how = modes_of(p.get('mode')), 'modes from the structure plan\'s words'
        if not ms:
            USED.add('mode_by_level')
            ms, how = D['mode_by_level'].get(lvl, D['mode_by_level']['local']), 'modes assumed by the route\'s level'
    for m in ms:
        props = dict(kind='route', name=name, mode=m, level='main' if lvl == 'main' else 'local', plan_level=lvl or None,
                     source='; '.join(s for s in (p.get('source'), how) if s), basis=p.get('basis'))
        if m == 'bike' and lower(name) in dest:
            props.update(level='main', leads_to=dest[lower(name)], source=props['source'] + '; destination: ' + SOURCE.get('bike_destinations', ''))
        add(g, **props)
for b in dest:
    if b not in {lower(p.get('name')) for p, g in ROUTES}:
        not_found.append(b)

USED.add('massing_modes')
for p, g in MASS:
    lvl = p.get('level')
    if p.get('kind') == 'street' and lvl in D['massing_modes'] and not g.is_empty:
        for m in D['massing_modes'][lvl]:
            add(g, kind='route', name=p.get('name') or 'massing %s' % lvl, mode=m, level='local', access_only=(m == 'car'),
                source='massing %s street' % lvl, basis='massing')

# ---------------- stops, hubs, accesses ----------------
stop_pt = place(stop_name)
add(stop_pt, kind='stop', name=stop_name, mode=CFG.get('main_stop_mode', 'rail'), main=True, source=SOURCE.get('main_stop', ''))
bus_lines = [g for p, g in feats if p.get('kind') == 'route' and p.get('mode') == 'bus']
for s in CFG.get('stops') or []:
    at = place(s.get('at'))
    if at is None:
        continue
    if bus_lines:
        near = min(bus_lines, key=lambda l: l.distance(at))
        at = near.interpolate(near.project(at))
    add(at, kind='stop', name=s.get('name') or s.get('at'), mode=s.get('mode', 'bus'), main=False, source=SOURCE.get('stops', ''))

hub_p, hub_g = CENTRES[lower(hub_name)]
USED.add('hub_words')
hb = [g for p, g in MASS if p.get('kind') == 'building' and has_word(p.get('use'), D['hub_words'])]
if hb:
    b = min(hb, key=lambda g: g.distance(hub_g))
    hub_pt, hub_on = b.representative_point(), 'on the hub building of the massing'
else:
    hub_pt, hub_on = place(hub_name), 'at the centre\'s middle (the massing has no hub building)'
add(hub_pt, kind='hub', name=hub_name, level='main', function=hub_p.get('holds') or 'main stop', source=SOURCE.get('hub', '') + '; ' + hub_on)
USED.add('local_hub_words')
for n, (p, g) in CENTRES.items():
    if n != lower(hub_name) and has_word(p.get('holds'), D['local_hub_words']):
        add(place(n), kind='hub', name=p.get('name'), level='local', function=p.get('holds'), source='the centre holds mobility')
for gar in CFG.get('garages') or []:
    at = place(gar.get('at'))
    if at is not None:
        add(at, kind='hub', name=gar.get('what', 'garage') + ' at ' + str(gar.get('at')), level='local', function='garage',
            source=SOURCE.get('garages', ''))
for n in CFG.get('car_access') or []:
    at = place(n)
    if at is not None:
        add(at, kind='access', name=n, allowed='cars', source=SOURCE.get('car_access', ''))


# ---------------- networks ----------------
def network(ls, join):
    """A graph of these lines, noded where they cross, with a node every node_step_m; ends within `join` m of
    another part are joined to it. Returns (graph, joins made)."""
    USED.update(['node_step_m', 'node_round_m'])
    G = nx.Graph()
    ls = [l for l in ls if not l.is_empty]
    if not ls:
        return G, 0
    r = float(D['node_round_m'])
    q = lambda c: (round(c[0] / r) * r, round(c[1] / r) * r)
    for s in lines(shapely.segmentize(unary_union(ls), float(D['node_step_m']))):
        cs = [q(c) for c in s.coords]
        for u, v in zip(cs, cs[1:]):
            if u != v:
                G.add_edge(u, v, w=math.dist(u, v))
    joins = 0
    if join and G.number_of_nodes():
        comp = {n: i for i, c in enumerate(nx.connected_components(G)) for n in c}
        parent = list(range(max(comp.values()) + 1))
        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]; a = parent[a]
            return a
        nodes = list(G.nodes)
        pts = [Point(n) for n in nodes]
        tree = STRtree(pts)
        for i, n in enumerate(nodes):
            if G.degree(n) != 1:
                continue
            cand = [j for j in tree.query(pts[i].buffer(join)) if find(comp[nodes[j]]) != find(comp[n])]
            if cand:
                j = min(cand, key=lambda j: pts[i].distance(pts[j]))
                if pts[i].distance(pts[j]) <= join:
                    G.add_edge(n, nodes[j], w=pts[i].distance(pts[j]))
                    parent[find(comp[n])] = find(comp[nodes[j]])
                    joins += 1
    return G, joins


_trees = {}


def snap(G, pt):
    """(nearest node, distance to it) of a point."""
    if id(G) not in _trees:
        nodes = list(G.nodes)
        _trees[id(G)] = (nodes, STRtree([Point(n) for n in nodes]))
    nodes, tree = _trees[id(G)]
    n = nodes[tree.nearest(pt)]
    return n, pt.distance(Point(n))


stats = {'missing_layers': missing}
limits = sorted(float(x) for x in CFG['walk_limits_m'])

# cars: no car route may join the gateways of a no_car_link pair
USED.update(['car_join_m', 'gate_snap_m'])
car = [g for p, g in feats if p.get('kind') == 'route' and p.get('mode') == 'car' and not p.get('access_only')]
CG, _ = network(car, float(D['car_join_m']))
checks = []
for pair in CFG.get('no_car_link') or []:
    a, b = (place(x) for x in pair)
    if a is None or b is None or not CG.number_of_nodes():
        checks.append(dict(between=list(pair), car_link=None, why='a gateway not found or no car routes'))
        continue
    (na, da), (nb, db) = snap(CG, a), snap(CG, b)
    if da > D['gate_snap_m'] or db > D['gate_snap_m']:
        checks.append(dict(between=list(pair), car_link=False, why='a gateway is not on the car network'))
        continue
    checks.append(dict(between=list(pair), car_link=nx.has_path(CG, na, nb), source=SOURCE.get('no_car_link', '')))
stats['car_link_violations'] = sum(1 for c in checks if c['car_link'])
stats['car_link_checks'] = checks

# walking: streets centrelines (else the site's street lines), the massing's streets, the foot routes
cl = [g for p, g in (STREETS or []) if p.get('kind') == 'centreline']
walk_base = 'centrelines of streets/streets.geojson' if cl else 'street lines of the site'
if not cl:
    frame = site.buffer(max(limits) + 200)
    cl = [g for p, g in SITE_STREETS if g.intersects(frame)]
wl = cl + [g for p, g in MASS if p.get('kind') == 'street'] + [g for p, g in feats if p.get('kind') == 'route' and p.get('mode') == 'foot']
USED.add('join_m')
WG, joins = network(wl, float(D['join_m']))
USED.add('housing_words')
homes = [(p, g) for p, g in MASS if p.get('kind') == 'building' and not p.get('existing') and has_word(p.get('use'), D['housing_words'])]
gfa = lambda p, g: float(p.get('gfa_m2') or (p.get('footprint_m2') or g.area) * float(p.get('floors') or 1))
walk = dict(from_stop=stop_name, network=walk_base, limits_m=limits, buildings=len(homes), new_buildings_only=True,
            nodes=WG.number_of_nodes(), edges=WG.number_of_edges(), parts=nx.number_connected_components(WG) if WG.number_of_nodes() else 0,
            joins=joins, source=SOURCE.get('walk_limits_m', ''))
tot = sum(gfa(p, g) for p, g in homes)
walk['housing_gfa_m2'] = round(tot)
if WG.number_of_nodes() and tot:
    s0, d0 = snap(WG, stop_pt)
    dist = nx.single_source_dijkstra_path_length(WG, s0, weight='w')
    within, unreached = {L: 0.0 for L in limits}, 0.0
    for p, g in homes:
        c = g.centroid
        n, dn = snap(WG, c)
        if n not in dist:
            unreached += gfa(p, g)
            continue
        dd = d0 + dist[n] + dn
        for L in limits:
            within[L] += gfa(p, g) if dd <= L else 0
    for L in limits:
        walk['within_%dm' % L] = round(within[L] / tot, 3)
    walk['unreached'] = round(unreached / tot, 3)
    if unreached >= tot:
        print('no path from the stop to any housing: %d nodes, %d edges, %d parts' % (walk['nodes'], walk['edges'], walk['parts']), file=sys.stderr)
else:
    for L in limits:
        walk['within_%dm' % L] = None
    walk['unreached'] = None
stats['walk'] = {k: v for k, v in walk.items() if k.startswith('within') or k in ('unreached', 'housing_gfa_m2')}
stats['bike_routes_to_named_places'] = sum(1 for p, g in feats if p.get('mode') == 'bike' and p.get('level') == 'main' and p.get('leads_to'))
stats['main_bike_routes'] = sum(1 for p, g in feats if p.get('mode') == 'bike' and p.get('level') == 'main')
stats['hub'] = hub_on
stats['features'] = {k: sum(1 for p, g in feats if p['kind'] == k) for k in ('route', 'stop', 'hub', 'access')}
stats['routes_by_mode'] = {m: sum(1 for p, g in feats if p['kind'] == 'route' and p['mode'] == m) for m in ORDER}
stats['names_not_found'] = sorted(set(map(str, not_found)))


# ---------------- the plan ----------------
def tw(s, size):
    return len(s) * size * 0.56


def nice(x):
    for v in (10, 20, 40, 50, 100, 200, 400, 500, 1000, 2000, 4000, 5000, 10000):
        if v >= x:
            return v
    return 20000


def shot(svg, png, w, h):
    exe = next(e for e in [r'C:/Program Files/Google/Chrome/Application/chrome.exe',
                           r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
                           '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                           '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', 'chromium', 'google-chrome'] if os.path.exists(e) or '/' not in e)
    html = svg.replace('.svg', '_wrap.html')
    open(html, 'w', encoding='utf8').write(f'<html><body style="margin:0"><img src="{os.path.basename(svg)}" style="width:{w}px;height:{h}px"></body></html>')
    subprocess.run([exe, '--headless', '--disable-gpu', '--hide-scrollbars', f'--screenshot={os.path.abspath(png)}',
                    f'--window-size={w},{h}', 'file:///' + os.path.abspath(html).replace('\\', '/')], capture_output=True, timeout=180)
    os.remove(html)


scale = int(CFG['scale'])
k = scale / 1000.0                                     # metres per mm on paper
USED.update(['site_pad_m', 'panel_w_mm'])
win = site.buffer(float(D['site_pad_m'])).bounds
NEWB = [(p, g) for p, g in MASS if p.get('kind') == 'building' and not p.get('existing')]
room = float(D['panel_w_mm']) * k
stats['cropped'] = False
if win[2] - win[0] > room:
    USED.add('crop_pad_m')
    if NEWB:
        win = unary_union([g for p, g in NEWB]).buffer(float(D['crop_pad_m'])).bounds
    if win[2] - win[0] > room:
        cx = (win[0] + win[2]) / 2
        win = (cx - room / 2, win[1], cx + room / 2, win[3])
    stats['cropped'] = 'the site is wider than %g mm at 1:%d: cropped to the new buildings' % (D['panel_w_mm'], scale)
wx0, wy0, wx1, wy1 = win
Wm, Hm = wx1 - wx0, wy1 - wy0
fr = box(*win)
fs = TXT * k
P = lambda x, y: (x - wx0, wy1 - y)
f2 = lambda v: '%.2f' % v
lw = lambda key, f=1.0: float(S[key]) * k * f


def d(g):
    if g.is_empty:
        return ''
    if g.geom_type == 'Polygon':
        return ''.join('M' + 'L'.join('%.2f,%.2f' % P(*c[:2]) for c in r.coords) + 'Z' for r in [g.exterior, *g.interiors])
    if g.geom_type in ('LineString', 'LinearRing'):
        return 'M' + 'L'.join('%.2f,%.2f' % P(*c[:2]) for c in g.coords)
    return ''.join(d(q) for q in getattr(g, 'geoms', []))


o = ['<g clip-path="url(#map)">', f'<rect width="{f2(Wm)}" height="{f2(Hm)}" fill="{S["paper"]}"/>']
legend = {}


def fill(g, colour, key=None, stroke=None, extra=''):
    if key:
        legend.setdefault(key, ('fill', colour, stroke))
    st = f' stroke="{stroke}" stroke-width="{f2(lw("thin"))}"' if stroke else ' stroke="none"'
    o.append(f'<path d="{d(g)}" fill="{colour}"{st} fill-rule="evenodd"{extra}/>')


heavy = []   # every line drawn at the mid weight or thicker, as drawn, in drawing units: labels keep off them


def stroke(g, colour, w, dash=None, key=None, extra=''):
    if key:
        legend.setdefault(key, ('line', colour, w, dash))
    if w >= lw('mid') - 1e-9:
        heavy.append(shapely.affinity.affine_transform(g.intersection(fr.buffer(10)), [1, 0, 0, -1, -wx0, wy1]).buffer(w / 2))
    da = f' stroke-dasharray="{f2(dash[0] * k)} {f2(dash[1] * k)}"' if dash else ''
    o.append(f'<path d="{d(g)}" fill="none" stroke="{colour}" stroke-width="{f2(w)}"{da} stroke-linecap="round" stroke-linejoin="round"{extra}/>')


# base: the street surface, the buildings
if STREETS is not None and any(p.get('kind') == 'street' for p, g in STREETS):
    surf = unary_union([g for p, g in STREETS if p.get('kind') in ('street', 'path') and g.geom_type.endswith('Polygon') and g.intersects(fr)])
    walk['base'] = 'streets/streets.geojson'
else:
    USED.update(['street_widths', 'street_w_other', 'street_w_new'])
    surf = []
    for p, g in SITE_STREETS:
        if g.intersects(fr):
            w = D['street_widths'].get(p.get('highway'), D['street_w_other'])
            surf.append(g.buffer(float(w) / 2, cap_style=2, join_style=1))
    for p, g in MASS:
        if p.get('kind') == 'street':
            surf.append(g if g.geom_type.endswith('Polygon') else g.buffer(float(p.get('width') or D['street_w_new']) / 2, cap_style=2, join_style=1))
    surf = unary_union(surf) if surf else shapely.Polygon()
fill(surf.intersection(fr.buffer(10)), S['street'], 'street', S['path'])
fill(unary_union([g for p, g in CTX if g.intersects(fr) and not site.contains(g.representative_point())]), S['context'], 'context')
kept = [g for p, g in MASS if p.get('kind') == 'building' and p.get('existing') and g.intersects(fr)]
if kept:
    fill(unary_union(kept), S['existing'], 'existing')
if NEWB:   # the standard's colour for new, light enough for the routes to read on it
    fill(unary_union([g for p, g in NEWB if g.intersects(fr)]), S['new'], 'new', extra=' fill-opacity="0.45"')
stroke(site.exterior, S['ink'], lw('mid'), (3, 1.5), 'site')

# the rings at the walking limits around the main stop
X, Y = P(stop_pt.x, stop_pt.y)
ring_boxes = []   # the boxes of the rings' labels, which the other labels keep clear of
for i, L in enumerate(limits):
    da = f' stroke-dasharray="{f2(2 * k)} {f2(1.5 * k)}"' if i else ''
    o.append(f'<circle cx="{f2(X)}" cy="{f2(Y)}" r="{f2(L)}" fill="none" stroke="{S["ink"]}" stroke-width="{f2(lw("thin"))}"{da}/>')
    legend.setdefault('ring', ('ring',))
    a = math.radians(45)
    rx, ry = X + L * math.cos(a) + 1.5 * k, Y - L * math.sin(a)
    o.append(f'<text x="{f2(rx)}" y="{f2(ry)}" font-size="{f2(fs)}" fill="{S["ink"]}" '
             f'paint-order="stroke" stroke="{S["paper"]}" stroke-width="{f2(0.6 * k)}">{L:g} m</text>')
    ring_boxes.append(box(rx, ry - 0.75 * fs, rx + tw('%g m' % L, fs), ry + 0.25 * fs))

# the routes, by mode and level: foot under bike under car under bus
LOOK = {'bus': (S['ink'], 'thick', None), 'car': (S['existing'], 'mid', None), 'bike': (S['accent'], 'mid', None),
        'foot': (S['ink'], 'thin', (1.2, 0.8))}
for m in reversed(ORDER):
    col, wkey, dash = LOOK[m]
    for lvl in ('local', 'main'):
        sel = [g for p, g in feats if p['kind'] == 'route' and p['mode'] == m and p['level'] == lvl and g.intersects(fr)]
        if m == 'car':
            sel_through = [g for p, g in feats if p['kind'] == 'route' and p['mode'] == 'car' and p['level'] == lvl
                           and not p.get('access_only') and g.intersects(fr)]
            sel_access = [g for p, g in feats if p['kind'] == 'route' and p['mode'] == 'car' and p['level'] == lvl
                          and p.get('access_only') and g.intersects(fr)]
            if sel_access:
                stroke(unary_union(sel_access), col, lw(wkey, 0.6), (0.6, 0.9), 'car-access')
            sel = sel_through
        if not sel:
            continue
        key = {'bike': 'bike' if lvl == 'main' else 'bike-local'}.get(m, m)
        stroke(unary_union(sel), col, lw(wkey, 1.0 if lvl == 'main' else 0.6), dash, key)
o.append('</g>')


def symbol(kind, x, y):
    ink, paper, sw = S['ink'], S['paper'], f2(lw('mid'))
    if kind == 'stop':
        return (f'<circle cx="{f2(x)}" cy="{f2(y)}" r="{f2(2.4 * k)}" fill="{paper}" stroke="{ink}" stroke-width="{sw}"/>'
                f'<circle cx="{f2(x)}" cy="{f2(y)}" r="{f2(1.2 * k)}" fill="{ink}"/>')
    if kind == 'bus-stop':
        return f'<circle cx="{f2(x)}" cy="{f2(y)}" r="{f2(1.4 * k)}" fill="{paper}" stroke="{ink}" stroke-width="{sw}"/>'
    if kind in ('hub', 'local-hub'):
        r = 3.2 if kind == 'hub' else 2.2
        return (f'<circle cx="{f2(x)}" cy="{f2(y)}" r="{f2(r * k)}" fill="{paper}" stroke="{ink}" stroke-width="{sw}"/>'
                f'<circle cx="{f2(x)}" cy="{f2(y)}" r="{f2(r * 0.55 * k)}" fill="none" stroke="{ink}" stroke-width="{sw}"/>')
    if kind == 'garage':
        r = 1.8 * k
        return f'<rect x="{f2(x - r)}" y="{f2(y - r)}" width="{f2(2 * r)}" height="{f2(2 * r)}" fill="{S["existing"]}" stroke="{ink}" stroke-width="{sw}"/>'
    r = 1.8 * k
    return f'<path d="M{f2(x)},{f2(y - r)}L{f2(x + r)},{f2(y)}L{f2(x)},{f2(y + r)}L{f2(x - r)},{f2(y)}Z" fill="{paper}" stroke="{ink}" stroke-width="{sw}"/>'


SYM_R = {'stop': 2.4, 'bus-stop': 1.4, 'hub': 3.2, 'local-hub': 2.2, 'garage': 1.8, 'access': 1.8}   # mm, as drawn above
labelled, marks = [], []   # hubs first, the stops on top; one label for a stop and hub at the same place
for p, g in sorted(feats, key=lambda f: ('hub', 'access', 'stop').index(f[0]['kind']) if f[0]['kind'] in ('hub', 'access', 'stop') else 9):
    if p['kind'] in ('stop', 'hub', 'access') and g.intersects(fr):
        kind = {'stop': 'stop' if p.get('main') else 'bus-stop', 'access': 'access'}.get(p['kind'])
        if p['kind'] == 'hub':
            kind = 'garage' if p.get('function') == 'garage' else ('hub' if p['level'] == 'main' else 'local-hub')
        x, y = P(g.x, g.y)
        o.append(symbol(kind, x, y))
        legend.setdefault(kind, ('symbol', kind))
        r_ = (SYM_R[kind] + float(S['mid']) / 2) * k
        marks.append(box(x - r_, y - r_, x + r_, y + r_))
        if kind in ('stop', 'hub', 'local-hub') and not any(t == p['name'] and q.distance(g) < 10 * k for t, q, *_ in labelled):
            labelled.append((p['name'], g, x, y, r_, kind))


def label_spots(s, x, y, r_):
    """The places a label may take around its symbol, in order: (text x, baseline y, anchor, box, leader or None).
    A label's box is its character count times 0.56 of the font size wide, and its font size high."""
    USED.update(['label_gap_mm', 'leader_mm'])
    w, gap, pad = tw(s, fs), float(D['label_gap_mm']) * k, 0.4 * k
    up, dn = 0.75 * fs, 0.25 * fs                              # ascent and descent from the baseline

    def at(bx, by, anchor):                                    # bx: the anchor's x; by: the box's vertical middle
        x0 = {'start': bx, 'end': bx - w, 'middle': bx - w / 2}[anchor]
        base = by + (up - dn) / 2
        return bx, base, anchor, box(x0 - pad, base - up - pad, x0 + w + pad, base + dn + pad)

    e, c, h = r_ + gap, r_ + pad + 0.3 * k, (up + dn) / 2    # c: a corner place clears the symbol's square
    spots = [at(x + e, y, 'start'), at(x - e, y, 'end'), at(x, y - e - h, 'middle'), at(x, y + e + h, 'middle'),
             at(x + c, y - c - h, 'start'), at(x + c, y + c + h, 'start'),
             at(x - c, y - c - h, 'end'), at(x - c, y + c + h, 'end')]
    spots = [(*sp, None) for sp in spots]
    for far in D['leader_mm']:                                 # further out, on a short line from the symbol
        for deg in (0, 180, 45, 135, 315, 225, 90, 270):
            a = math.radians(deg)
            ex, ey = x + far * k * math.cos(a), y - far * k * math.sin(a)
            anchor = 'start' if math.cos(a) > 0.1 else ('end' if math.cos(a) < -0.1 else 'middle')
            by = ey - h if math.sin(a) > 0.9 else (ey + h if math.sin(a) < -0.9 else ey)
            sx, sy_ = x + r_ * math.cos(a), y - r_ * math.sin(a)
            spots.append((*at(ex + (0.5 * k if anchor == 'start' else -0.5 * k if anchor == 'end' else 0), by, anchor),
                          shapely.LineString([(sx, sy_), (ex, ey)])))
    return spots


# every label keeps clear of the other labels, of every symbol (its own too) and of the map's edge, then of the heavy
# lines: a place free of all is taken first, else the one least over labels and symbols, then least crossed by lines
inner = box(0, 0, Wm, Hm)
taken = list(ring_boxes)
HEAVY = unary_union(heavy) if heavy else shapely.Polygon()
lab_stats = dict(placed=0, moved=0, on_leader=0, warned=[], on_lines=[])
for name, g, x, y, r_, kind in sorted(labelled, key=lambda t: t[5] == 'local-hub'):   # the main stop and hub first
    s = str(name)
    own = box(x - r_, y - r_, x + r_, y + r_)
    others = [m for m in marks if not m.equals(own)]
    best, best_hit = None, None
    for i, (tx, ty, anchor, bx_, lead) in enumerate(label_spots(s, x, y, r_)):
        hit = sum(bx_.intersection(t).area for t in taken + marks) + bx_.difference(inner).area
        if lead is not None:
            hit += sum(lead.intersection(t).length for t in taken + others) * fs
        hit = (round(hit, 6), round(bx_.intersection(HEAVY).area, 6))
        if hit == (0, 0):
            best, best_hit = (i, tx, ty, anchor, bx_, lead), hit
            break
        if best is None or hit < best_hit:
            best, best_hit = (i, tx, ty, anchor, bx_, lead), hit
    i, tx, ty, anchor, bx_, lead = best
    if best_hit[0]:
        lab_stats['warned'].append(s)
        print('label "%s": no free place around its symbol, drawn where it overlaps least' % s, file=sys.stderr)
    elif best_hit[1]:
        lab_stats['on_lines'].append(s)
        print('label "%s": every place clear of labels and symbols is crossed by a route line, drawn where least' % s, file=sys.stderr)
    elif i == 0:
        lab_stats['placed'] += 1
    else:
        lab_stats['moved'] += 1
    lab_stats['on_leader'] += lead is not None
    taken.append(bx_)
    if lead is not None:
        o.append(f'<path d="M{f2(lead.coords[0][0])},{f2(lead.coords[0][1])}L{f2(lead.coords[1][0])},{f2(lead.coords[1][1])}" fill="none" stroke="{S["ink"]}" stroke-width="{f2(lw("thin"))}"/>')
    am = '' if anchor == 'start' else f' text-anchor="{anchor}"'
    o.append(f'<text x="{f2(tx)}" y="{f2(ty)}" font-size="{f2(fs)}"{am} fill="{S["ink"]}" paint-order="stroke" '
             f'stroke="{S["paper"]}" stroke-width="{f2(0.6 * k)}">{escape(s)}</text>')
stats['labels'] = lab_stats

# the walking shares, as one line
shares = ', '.join(LAB['within'].format(p=round(100 * walk['within_%dm' % L]), m='%g' % L)
                   for L in limits if walk.get('within_%dm' % L) is not None)
walk_line = LAB['walk'].format(shares=shares, unreached=LAB['unreached'].format(p=round(100 * walk['unreached'])) if walk.get('unreached') else '') if shares else ''


# ---------------- the strip under the map ----------------
def north_angle():
    cx, cy = (wx0 + wx1) / 2, (wy0 + wy1) / 2
    lon, lat = TO_LL(cx, cy)
    x, y = TO_M(lon, lat + 0.01)
    return math.atan2(x - cx, y - cy)


W = Wm / k
st = []
m_ = lambda v: f2(v * k)
Yb = lambda y: Hm / k + y
ink, thin = S['ink'], float(S['thin'])


def text(x, y, s, size=TXT, extra=''):
    st.append(f'<text x="{m_(x)}" y="{m_(Yb(y))}" font-size="{f2(size * k)}" fill="{ink}"{extra}>{escape(s)}</text>')


head = f'{LAB["title"]}, 1:{scale:,}'
text(4, 3 + TITLE, head, TITLE, ' font-weight="bold"')
r = 4.0
nx_, ny_ = W - 4 - r, 3 + r
a = north_angle()
st.append(f'<circle cx="{m_(nx_)}" cy="{m_(Yb(ny_))}" r="{m_(r)}" fill="none" stroke="{ink}" stroke-width="{m_(thin)}"/>'
          f'<path d="M{m_(nx_)},{m_(Yb(ny_))}L{m_(nx_ + r * math.sin(a))},{m_(Yb(ny_ - r * math.cos(a)))}" stroke="{ink}" stroke-width="{m_(thin * 2)}"/>')
# scale bar: one thin line stepping up and down, a tick at every step, numbers under, the unit on the last
L = nice(W * k / 6)
n = 5 if L in (10, 50, 500, 5000) else 4
Lmm, seg, hstep = L / k, L / k / n, 1.5
nums = [('%g' % (i * L / n)) + (' m' if i == n else '') for i in range(n + 1)]
gap = tw(max(nums, key=len), TXT) + 1
show, last = {0, n}, 0
for i in range(1, n):
    if (i - last) * seg >= gap and (n - i) * seg >= gap:
        show.add(i); last = i
x_end = nx_ - r - 6 - tw(' m', TXT)
row_y = 3 + max(TITLE, 2 * r)
if x_end - Lmm < 4 + tw(head, TITLE) * 1.1 + 6:
    x0, sy, row_y = 4, row_y + 3 + hstep, row_y + 3 + hstep + 1.2 + TXT + 1
else:
    x0, sy = x_end - Lmm, 3 + TITLE - 1.2 - TXT
pts = []
for i in range(n):
    yy = sy - (hstep if i % 2 else 0)
    pts += [(x0 + i * seg, yy), (x0 + (i + 1) * seg, yy)]
st.append('<path d="M' + 'L'.join(f'{m_(x)},{m_(Yb(y))}' for x, y in pts) + f'" fill="none" stroke="{ink}" stroke-width="{m_(thin)}"/>')
for i in range(n + 1):
    x = x0 + i * seg
    st.append(f'<path d="M{m_(x)},{m_(Yb(sy - hstep))}L{m_(x)},{m_(Yb(sy + 1.2))}" stroke="{ink}" stroke-width="{m_(thin)}"/>')
    if i in show:
        text(x, sy + 1.2 + TXT, nums[i], extra=' text-anchor="middle"')
# legend: every line, fill and symbol drawn
y, x = row_y + 4, 4
for key, spec in legend.items():
    lab = LAB.get(key, key)
    wi = 8 + 1.5 + tw(lab, TXT) + 5
    if x + wi > W - 4 and x > 4:
        x, y = 4, y + TXT + 3
    mid = y - 3.2 + 1.75
    if spec[0] == 'fill':
        sk = f' stroke="{spec[2]}"' if spec[2] else f' stroke="{S["path"]}"'
        op = ' fill-opacity="0.45"' if key == 'new' else ''
        st.append(f'<rect x="{m_(x)}" y="{m_(Yb(mid - 1.75))}" width="{m_(8)}" height="{m_(3.5)}" fill="{spec[1]}"{op}{sk} stroke-width="{m_(thin)}"/>')
    elif spec[0] == 'line':
        da = f' stroke-dasharray="{m_(spec[3][0])} {m_(spec[3][1])}"' if spec[3] else ''
        st.append(f'<path d="M{m_(x)},{m_(Yb(mid))}L{m_(x + 8)},{m_(Yb(mid))}" stroke="{spec[1]}" stroke-width="{f2(spec[2])}"{da} stroke-linecap="round"/>')
    elif spec[0] == 'ring':
        st.append(f'<path d="M{m_(x)},{m_(Yb(mid + 1.5))}A{m_(8)},{m_(8)} 0 0 1 {m_(x + 8)},{m_(Yb(mid - 1.5))}" fill="none" stroke="{ink}" stroke-width="{m_(thin)}"/>')
    else:
        st.append(symbol(spec[1], (x + 4) * k, Yb(mid) * k))
    text(x + 9.5, y, lab)
    x += wi
y += TXT + 3
for line_ in ([walk_line] if walk_line else []) + ([CREDIT] if CREDIT else []):
    cur = ''
    for w_ in line_.split():
        if cur and tw(cur + ' ' + w_, TXT) > W - 8:
            text(4, y, cur)
            y, cur = y + TXT + 1.5, w_
        else:
            cur = (cur + ' ' + w_).strip()
    if cur:
        text(4, y, cur)
        y += TXT + 1.5
H_strip = max(float(D['legend_mm']), y + 2)
USED.update(['text_floor_mm', 'legend_mm', 'png_px_per_mm'])
Hs = H_strip * k
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" height="{(Hm + Hs) / k:.1f}mm" '
       f'viewBox="0 0 {f2(Wm)} {f2(Hm + Hs)}" font-family="{FONT}">',
       f'<defs><clipPath id="map"><rect width="{f2(Wm)}" height="{f2(Hm)}"/></clipPath></defs>',
       f'<rect width="{f2(Wm)}" height="{f2(Hm + Hs)}" fill="{S["paper"]}"/>'] + o + st + ['</svg>']
fname = f'mobility_1-{scale}'
svgp = os.path.join(OUT, fname + '.svg')
open(svgp, 'w', encoding='utf8').write('\n'.join(svg))
png = os.path.join(OUT, fname + '.png')
try:
    px = D['png_px_per_mm']
    shot(svgp, png, int(W * px), int((Hm + Hs) / k * px))
except Exception as e:
    print('no PNG:', e, file=sys.stderr)
stats['drawing'] = dict(file=fname + '.svg', png=os.path.exists(png), width_mm=round(W, 1), height_mm=round((Hm + Hs) / k, 1),
                        scale=scale, base=walk.get('base', 'site street lines buffered at assumed widths'))

# ---------------- write ----------------
fc = {'type': 'FeatureCollection', 'features': [
    {'type': 'Feature', 'properties': {k_: v for k_, v in p.items() if v is not None},
     'geometry': mapping(shapely.set_precision(transform(TO_LL, g), 1e-7))} for p, g in feats if g is not None and not g.is_empty]}
open(os.path.join(OUT, 'mobility.geojson'), 'w', encoding='utf8').write(json.dumps(fc, ensure_ascii=False))
json.dump(walk, open(os.path.join(OUT, 'walk.json'), 'w', encoding='utf8'), indent=1, ensure_ascii=False)
json.dump(stats, open(os.path.join(OUT, 'stats.json'), 'w', encoding='utf8'), indent=1, ensure_ascii=False)
md = ['# Assumptions', '', 'The skill\'s own values used in this run; config.json may override each.', '']
for key in sorted(USED):
    md.append(f'- `{key}` = {json.dumps(D[key], ensure_ascii=False)}: {DEFAULTS[key][1]}' + (' (from config.json)' if key in CFG else ' (default)'))
if missing:
    md += ['', 'Missing layers: ' + '; '.join(missing) + '.']
if not_found:
    md += ['', 'Names in config.json not found in the structure plan: ' + ', '.join(sorted(set(map(str, not_found)))) + '.']
open(os.path.join(OUT, 'assumptions.md'), 'w', encoding='utf8').write('\n'.join(md) + '\n')
print(json.dumps(stats, indent=1, ensure_ascii=False))
