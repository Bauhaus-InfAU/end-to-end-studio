"""Construction phases of a design: every building's phase, the streets each phase needs, and whether each finished
phase works while the next is built.

    python phasing.py --proposal <proposal folder> --site <site folder> --config <proposal>/phasing/config.json
                      [--decisions <proposal>/phasing/decisions.json]

config.json holds the brief's values, each as {"value": ..., "source": "<brief file> p. N" or "assumption: ..."}
(see config.example.json); a value left empty or a source still in <angle brackets> stops the script with its name.
first_phase, open_space_per_resident_m2, emergency and existing_residents may be "not stated": their checks are then
"not stated / not measured" (for existing_residents: open space per resident and capacity are not measured).
decisions.json holds Claude's decisions (see decisions.example.json); the script only ever adds `epsg` and
`massing_fingerprint` to it, and only when they are missing.

Phase k is the set of things built together; stage j is the time phase j is under construction. At stage j what works
is what exists plus phases 1 to j-1; phase j and later count for nothing. The last stage, n+1, is completion.

Each building takes the phase phases.py gave it (phasing/phases.geojson), and its homes are counted by phases.py's rule,
so both scripts give one answer; before phases.py has run, a building takes the massing's phase, else its neighbourhood's.

Reads from the proposal: massing/massing.geojson, massing/config.json and massing/areas.csv (required);
structure-plan/structure-plan.geojson, streets/streets.geojson, mobility/mobility.geojson,
mobility/config.json (its no_car_link), open-space/open-space.geojson (its open spaces and paths) and
programme/programme.csv (each optional; a missing one is named in stats.json).
Writes into <proposal>/phasing/: phasing.geojson, stage-phases.csv (no homes: phases.csv holds those), stages.csv, access.csv, checks.csv, evidence.csv, stage-stats.json.
Needs shapely>=2, pyproj and networkx.
"""
import argparse, csv, hashlib, json, math, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fingerprint import fingerprint, relink, FingerprintError  # noqa: E402
from phases import homes_of  # noqa: E402

try:
    import networkx as nx
    import pyproj
    from shapely import STRtree, unary_union as noded_union
    from shapely.geometry import shape, mapping, Point, LineString, box
    from shapely.ops import transform, unary_union, nearest_points
    from shapely.validation import explain_validity
except ImportError as e:
    sys.exit(f'needs shapely, pyproj and networkx ({e.name} is missing): pip install shapely pyproj networkx')

NS = 'not stated'
NSM = 'not stated / not measured'
REQUIRED = ['phase_count', 'residents_per_home', 'requirements', 'facility_words', 'services', 'open_space_uses',
            'entrance_max_m', 'snap_m', 'near_site_m', 'scale_large', 'scale_small']
STATABLE = ['first_phase', 'open_space_per_resident_m2', 'emergency', 'existing_residents']
UNDECIDED = 'not measured: stop phase not decided'
EXIST_UNKNOWN = 'not measured: existing residents unknown'
OPS = {'>=': lambda a, b: a >= b, '<=': lambda a, b: a <= b, '==': lambda a, b: a == b,
       '>': lambda a, b: a > b, '<': lambda a, b: a < b}
NUMERIC = ('homes', 'residents')
SHARES = ('access', 'car', 'emergency')


def die(msg):
    sys.exit('phasing: ' + msg)


def placeholder(s):
    s = str(s or '').strip()
    return not s or s.startswith('<')


# ---------------- config ----------------
def read_config(path):
    try:
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        die(f'cannot read {path}: {e}')
    unfilled = lambda e: not isinstance(e, dict) or e.get('value') is None or placeholder(e.get('source'))
    missing = [k for k in REQUIRED + STATABLE if unfilled(raw.get(k))]
    if missing:
        die('missing in config.json: ' + ', '.join(missing) + ' (from the brief, with its page; "not stated" only for '
            + ', '.join(STATABLE) + ')')
    stated = [k for k in REQUIRED if raw[k]['value'] == NS]
    if stated:
        die(', '.join(stated) + ' may not be "not stated": decide it, and give the decision as an assumption with its reason')
    C = {k: v['value'] for k, v in raw.items() if isinstance(v, dict) and 'value' in v}
    SRC = {k: v.get('source', '') for k, v in raw.items() if isinstance(v, dict)}
    n = C['phase_count']
    if not isinstance(n, int) or n < 1:
        die('phase_count must be a whole number of 1 or more')
    for k in ('entrance_max_m', 'snap_m', 'near_site_m', 'scale_large', 'scale_small'):
        if not isinstance(C[k], (int, float)) or C[k] <= 0:
            die(f'{k} must be a number above 0')
    if not isinstance(C['facility_words'], dict) or any(placeholder(k) or not isinstance(w, list) or not w
                                                        or any(placeholder(x) for x in w) for k, w in C['facility_words'].items()):
        die('facility_words: {"<facility name>": ["<word in the massing use>", ...]}, every name and word filled in')
    if not isinstance(C['open_space_uses'], list) or not C['open_space_uses']:
        die('open_space_uses: a list of the open-space uses that count')
    for i, r in enumerate(C['requirements']):
        who = f'requirements[{i}]'
        if not isinstance(r, dict) or any(r.get(x) is None for x in ('phase', 'measure', 'op', 'value')) or placeholder(r.get('source')):
            die(f'{who}: needs phase, measure, op, value and source, all filled in')
        if r['op'] not in OPS:
            die(f'{who}: op is one of ' + ', '.join(OPS))
        if not (r['phase'] in ('each', 'all') or (isinstance(r['phase'], int) and 1 <= r['phase'] <= n)):
            die(f'{who}: phase is "each", "all" or a phase from 1 to {n}')
    names = set()
    for i, s in enumerate(C['services']):
        who = f'services[{i}]'
        if not isinstance(s, dict) or placeholder(s.get('name')) or placeholder(s.get('facility')) or placeholder(s.get('source')) \
                or s.get('walk_m') is None or s.get('by_phase') is None:
            die(f'{who}: needs name, facility, walk_m, by_phase and source, all filled in (walk_m or by_phase may be "not stated")')
        if s['facility'] != 'stop' and s['facility'] not in C['facility_words']:
            die(f'{who}: facility {s["facility"]!r} is not in facility_words (or "stop")')
        if s['by_phase'] != NS and not (isinstance(s['by_phase'], int) and 1 <= s['by_phase'] <= n):
            die(f'{who}: by_phase is a phase from 1 to {n}, or "not stated"')
        names.add(s['name'])
    for i, r in enumerate(C['requirements']):
        m = r['measure']
        if m.startswith('walk:') and m[5:] not in names:
            die(f'requirements[{i}]: {m}: no service of that name')
        if m.startswith('facility:') and m[9:] not in C['facility_words']:
            die(f'requirements[{i}]: {m}: no facility of that name in facility_words')
    er = C['existing_residents']
    if er != NS and (not isinstance(er, (int, float)) or er < 0):
        die('existing_residents: the residents of the buildings that stay, a number from the brief or a cited source, or "not stated"')
    em = C['emergency']
    if em != NS:
        if not isinstance(em, dict) or any(em.get(k) is None for k in ('max_distance_m', 'min_width_m', 'second_access')):
            die('emergency: {"max_distance_m", "min_width_m", "second_access"} from the brief or a cited regulation, or "not stated"')
    return C, SRC


# ---------------- reading GeoJSON in any system ----------------
def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        die(f'cannot read {path}: {e}')


def layer(path, site_m=None, to_m=None, near=None):
    """[(props, lon-lat GeoJSON geometry, lon-lat shapely geometry)], converted from the CRS the file names; checked
    to lie on the site when site_m is given."""
    fc = read_json(path)
    name = ((fc.get('crs') or {}).get('properties') or {}).get('name', '')
    feats = [(f.get('properties') or {}, f['geometry']) for f in fc.get('features', []) if f.get('geometry')]
    out = []
    if name and not re.search(r'CRS84$|EPSG:+4326$', name):
        try:
            tr = pyproj.Transformer.from_crs(pyproj.CRS.from_user_input(name), 4326, always_xy=True).transform
        except Exception as e:
            die(f'{path}: cannot read its CRS {name!r}: {e}')
        for p, g in feats:
            ll = transform(tr, shape(g))
            out.append((p, mapping(ll), ll))
    else:
        for p, g in feats:
            s = shape(g)
            x0, y0, x1, y1 = s.bounds
            if min(x0, y0) < -180 or max(x1, y1) > 180 or y0 < -90 or y1 > 90:
                die(f'{path}: coordinates beyond longitude and latitude, and no CRS named: never guessed')
            out.append((p, g, s))
    if site_m is not None and out:
        bb = unary_union([s.envelope for _, _, s in out]).bounds
        d = transform(to_m, box(*bb)).distance(site_m)
        if d > near:
            sw = (bb[1], bb[0], bb[3], bb[2])
            if -90 <= sw[1] <= 90 and -90 <= sw[3] <= 90 and transform(to_m, box(*sw)).distance(site_m) <= near:
                die(f'{path}: longitude and latitude look reversed')
            die(f'{path}: lies {d:.0f} m from the site (near_site_m = {near})')
    return out


def utm_epsg(lon, lat):
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


def has_word(use, words):
    u = str(use or '').lower()
    return any(w.lower() in u for w in words)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def as_phase(v, n, who):
    if v in (None, ''):
        return None
    try:
        k = int(v)
    except (TypeError, ValueError):
        die(f'{who}: phase {v!r} is not a number')
    if not 1 <= k <= n:
        die(f'{who}: phase {k} is outside 1 to {n} (phase_count in config.json)')
    return k


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proposal', required=True)
    ap.add_argument('--site', required=True)
    ap.add_argument('--config', required=True)
    ap.add_argument('--decisions')
    a = ap.parse_args()
    P, SITE = Path(a.proposal), Path(a.site)
    OUT = P / 'phasing'
    OUT.mkdir(parents=True, exist_ok=True)
    C, SRC = read_config(a.config)
    n = C['phase_count']
    STAGES = list(range(1, n + 2))           # n+1 is completion
    stats = {'missing_inputs': [], 'warnings': []}
    warn = stats['warnings'].append

    # ---- inputs and the one metric system ----
    for req in ('massing/massing.geojson', 'massing/config.json', 'massing/areas.csv'):
        if not (P / req).exists():
            die(f'missing {req} in {P}: run the massing first')
    if not (SITE / 'site.geojson').exists():
        die(f'no site.geojson in {SITE}')
    site_l = layer(SITE / 'site.geojson')
    site_ll = unary_union([s for _, _, s in site_l])
    mass_raw = (P / 'massing/massing.geojson').read_bytes()
    mass_fc = json.loads(mass_raw)
    mcfg = read_json(P / 'massing/config.json')
    mval = lambda k: (mcfg.get(k) or {}).get('value') if isinstance(mcfg.get(k), dict) else mcfg.get(k)
    m_note = re.search(r'EPSG:(\d+)', str(mass_fc.get('note', '')))
    if m_note:
        EPSG, why = int(m_note.group(1)), "the massing's note"
    elif mval('epsg'):
        EPSG, why = int(mval('epsg')), "the massing's config"
    else:
        c = site_ll.centroid
        EPSG, why = utm_epsg(c.x, c.y), 'UTM zone of the site'
    TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
    TO_LL = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform
    M = lambda g: transform(TO_M, g)
    site = M(site_ll)
    stats.update(epsg=EPSG, epsg_from=why, massing_fingerprint=hashlib.sha256(mass_raw).hexdigest()[:16])
    near = C['near_site_m']
    LL = lambda path: layer(path, site, TO_M, near)

    def opt(rel):
        p = P / rel
        if p.exists():
            return LL(p)
        stats['missing_inputs'].append(rel)
        return None

    mass = LL(P / 'massing/massing.geojson')
    sp = opt('structure-plan/structure-plan.geojson')
    st = opt('streets/streets.geojson')
    mob = opt('mobility/mobility.geojson')
    osp = opt('open-space/open-space.geojson')
    # the gateway pairs no car route may join, from the mobility config, with its source
    NO_CAR, no_car_src = [], ''
    if (P / 'mobility/config.json').exists():
        e = read_json(P / 'mobility/config.json').get('no_car_link')
        raw = e.get('value') if isinstance(e, dict) else e
        no_car_src = 'mobility/config.json: ' + str((e or {}).get('source', '') if isinstance(e, dict) else '')
        for pair in raw or []:
            if isinstance(pair, (list, tuple)) and len(pair) == 2 and not any(placeholder(x) for x in pair):
                NO_CAR.append((str(pair[0]), str(pair[1])))
    else:
        stats['missing_inputs'].append('mobility/config.json')
    m2_home = num(C.get('m2_per_home')) or num(mval('m2_per_home'))
    if not m2_home:
        die('no m2_per_home in phasing/config.json or massing/config.json: the homes cannot be counted')
    hs, hs_src = C['residents_per_home'], SRC['residents_per_home']
    if not isinstance(hs, (int, float)) or hs <= 0:
        die('residents_per_home must be a number above 0')

    # ---- decisions ----
    dpath = Path(a.decisions) if a.decisions else OUT / 'decisions.json'
    D = read_json(dpath) if dpath.exists() else {}
    for k in ('buildings', 'stops', 'open_spaces', 'services_outside', 'closures'):
        if not isinstance(D.get(k, []), list):
            die(f'decisions.json: {k} must be a list')
        D.setdefault(k, [])
    for k in ('buildings', 'stops', 'open_spaces', 'services_outside', 'closures'):   # drop untouched template rows
        D[k] = [r for r in D[k] if not any(placeholder(v) for v in r.values() if isinstance(v, str))]
    if D.get('massing_fingerprint') and D['massing_fingerprint'] != stats['massing_fingerprint'] and D['buildings']:
        warn('the massing has changed since the decisions were made: check every building decision, then set '
             'massing_fingerprint in decisions.json to ' + stats['massing_fingerprint'])
    if D.get('epsg') and int(D['epsg']) != EPSG:
        warn(f'decisions were made in EPSG:{D["epsg"]}, this run measures in EPSG:{EPSG}: the IDs do not depend on it, '
             'but check the re-linked decisions')
    changed = False
    for k, v in (('epsg', EPSG), ('massing_fingerprint', stats['massing_fingerprint'])):
        if not D.get(k):
            D[k] = v
            changed = True
    if changed or not dpath.exists():
        dpath.write_text(json.dumps(D, indent=1, ensure_ascii=False), encoding='utf-8')

    # ---- the phases phases.py gave the buildings, by footprint ----
    GIVEN = {}
    if (OUT / 'phases.geojson').exists():
        for f in read_json(OUT / 'phases.geojson')['features']:
            if f['properties'].get('kind') == 'building':
                GIVEN[fingerprint(f['geometry'])] = f['properties'].get('phase')

    # ---- buildings: IDs, validity, homes ----
    B = []
    seen = {}
    for i, (p, gll, sll) in enumerate(mass):
        if p.get('kind') != 'building':
            continue
        who = f'building {i + 1} of massing.geojson'
        existing = bool(p.get('existing'))
        if existing and p.get('osm_id') not in (None, ''):
            bid = f'osm-{p["osm_id"]}'
        else:
            try:
                bid = fingerprint(gll, who)
            except FingerprintError as e:
                die(str(e))
        if bid in seen:
            die(f'{who} and {seen[bid]} have the same footprint ({bid}): the massing holds it twice')
        seen[bid] = who
        g = M(sll)
        valid = g.is_valid and not g.is_empty
        b = dict(i=i, id=bid, p=p, g=g, existing=existing, valid=valid, invalid_reason=None if valid else explain_validity(g),
                 use=p.get('use'), floors=num(p.get('floors')) or 0, phase=None, basis=None, reason=None, homes=None)
        if not existing and valid:
            b['area'] = g.area
            b['gfa'] = g.area * b['floors']
            b['homes'] = homes_of(p, sll, m2_home)
        B.append(b)
    new = [b for b in B if not b['existing']]
    invalid = [b for b in B if not b['valid']]
    stats['invalid_footprints'] = [{'id': b['id'], 'reason': b['invalid_reason']} for b in invalid]

    # the massing's own totals
    areas = list(csv.DictReader((P / 'massing/areas.csv').open(encoding='utf-8')))
    hrow = next((r for r in areas if str(r.get('use', '')).startswith('homes')), None)
    total_homes = sum(b['homes'] for b in new if b['homes'] is not None)
    if any(not b['valid'] for b in new):
        stats['homes_check'] = f'not possible: {sum(1 for b in new if not b["valid"])} invalid footprints'
    elif hrow is None or num(hrow.get('design_m2')) is None:
        stats['homes_check'] = 'not possible: massing/areas.csv has no homes row'
    else:
        m_h = num(hrow['design_m2'])
        if abs(round(total_homes) - m_h) > 1:
            die(f'homes do not match the massing: {round(total_homes)} here, {m_h:.0f} in massing/areas.csv; '
                "the massing's housing rule may have changed")
        stats['homes_check'] = f'matches massing/areas.csv: {round(total_homes)} against {m_h:.0f}'
    gfa_off = [b['id'] for b in new if b['valid'] and num(b['p'].get('gfa_m2')) is not None and abs(b['gfa'] - num(b['p']['gfa_m2'])) > 1]
    if gfa_off:
        warn(f'{len(gfa_off)} buildings differ from the massing\'s gfa_m2 by more than 1 m2: its rule may have changed ({", ".join(gfa_off[:5])})')

    # ---- structure plan ----
    NB, CENTRES, GATES = [], [], {}
    for j, (p, _, s) in enumerate(sp or []):
        k = p.get('kind')
        if k == 'neighbourhood':
            NB.append(dict(name=p.get('name'), phase=as_phase(p.get('phase'), n, f'neighbourhood {p.get("name")}'), g=M(s)))
        elif k == 'centre':
            CENTRES.append(dict(name=p.get('name'), holds=p.get('holds'), g=M(s)))
        elif k == 'gateway':
            GATES[p.get('name') or f'gateway {j + 1}'] = M(s)
    for p, _, s in (mob or []):          # the mobility layer's own gateways, where the structure plan has none of that name
        if p.get('kind') == 'gateway' and p.get('name') and p['name'] not in GATES:
            GATES[p['name']] = M(s)
    nb_by_name = {x['name']: x for x in NB}

    # ---- phases for buildings ----
    by_id = {b['id']: b for b in new}
    dec_for, relinked, lost, ignored = {}, [], [], []
    unmatched = []
    for d in D['buildings']:
        if d.get('id') in by_id:
            dec_for[d['id']] = d
        else:
            unmatched.append(d)
    for d in unmatched:
        try:
            cx, cy = TO_M(*d['centre_lonlat'])
            area = float(d['footprint_m2'])
        except (KeyError, TypeError, ValueError):
            lost.append({'id': d.get('id'), 'why': 'lost: no centre_lonlat or footprint_m2 to find it by'})
            continue
        cands = [{'id': b['id'], 'centre': (b['g'].centroid.x, b['g'].centroid.y), 'area': b['area']}
                 for b in new if b['valid'] and b['id'] not in dec_for]
        found, why = relink({'id': d.get('id'), 'centre': (cx, cy), 'area': area}, cands, C['snap_m'])
        if found:
            dec_for[found] = d
            relinked.append({'from': d.get('id'), 'to': found})
        else:
            lost.append({'id': d.get('id'), 'why': why})
    for b in B:
        if b['existing']:
            b['basis'] = 'existing'
            continue
        p = b['p']
        given = GIVEN.get(b['id'])
        k = as_phase(p.get('phase') if b['id'] not in GIVEN else given, n, f'building {b["id"]}')
        nb = nb_by_name.get(p.get('neighbourhood'))
        d = dec_for.get(b['id'])
        if k:
            b.update(phase=k, basis='phases.py' if given is not None else 'massing')
        elif nb and nb['phase']:
            b.update(phase=nb['phase'], basis='structure-plan', reason=f'in neighbourhood {nb["name"]}')
        elif b['valid'] and any(x['phase'] and x['g'].contains(b['g'].representative_point()) for x in NB):
            x = next(x for x in NB if x['phase'] and x['g'].contains(b['g'].representative_point()))
            b.update(phase=x['phase'], basis='structure-plan', reason=f'lies in neighbourhood {x["name"]}')
        elif not b['valid']:
            b.update(basis='review', reason='invalid footprint: ' + b['invalid_reason'] + ('; its decision is not applied' if d else ''))
        elif d and d.get('basis') == 'proposed' and d.get('phase') is not None:
            b.update(phase=as_phase(d['phase'], n, f'decision for {b["id"]}'), basis='proposed', reason=d.get('reason') or '')
            if placeholder(b['reason']):
                die(f'decision for {b["id"]}: a proposed phase needs its reason')
        elif d:
            b.update(basis='review', reason=d.get('reason') or 'flagged for review in decisions.json')
        else:
            b.update(basis='review', reason='no phase from the massing or the structure plan: see evidence.csv')
        if d and b['basis'] in ('phases.py', 'massing', 'structure-plan'):
            ignored.append(b['id'])
    counts = {}
    for b in B:
        counts[b['basis']] = counts.get(b['basis'], 0) + 1
    if sum(counts.values()) != sum(1 for p, _, _ in mass if p.get('kind') == 'building'):
        die('buildings by basis do not add up to the massing\'s buildings')
    stats.update(buildings_by_basis=counts, buildings_total=len(B), relinked=relinked, lost_decisions=lost,
                 ignored_decisions=ignored)
    if ignored:
        warn(f'{len(ignored)} building decisions ignored: those buildings have a phase from the massing or the structure plan')

    # ---- the land of each phase ----
    LAND = {}
    for k in range(1, n + 1):
        parts = [x['g'] for x in NB if x['phase'] == k] + \
                [b['g'].buffer(C['entrance_max_m']) for b in new if b['valid'] and b['phase'] == k]
        LAND[k] = unary_union(parts) if parts else None
    for k in range(2, n + 1):
        before = unary_union([LAND[j] for j in range(1, k) if LAND[j] is not None] or [Point()])
        if LAND[k] is not None:
            LAND[k] = LAND[k].difference(before)

    def land_phase(geom):
        # a straight line's representative point is one of its ends, which may lie outside its land: take its middle
        pt = geom.interpolate(0.5, normalized=True) if 'LineString' in geom.geom_type else geom.representative_point()
        return next((k for k in range(1, n + 1) if LAND[k] is not None and LAND[k].contains(pt)), None)

    # ---- open spaces: existing, else as decided, else the phase whose land they lie in ----
    dec_os = {d.get('name'): d for d in D['open_spaces']}
    OS = []
    for p, _, s in (osp if osp is not None else [(p, g, s) for p, g, s in mass if p.get('kind') == 'open-space']):
        if p.get('kind') != 'open-space':
            continue
        g = M(s)
        nm = p.get('name') or p.get('id')
        d = dec_os.get(nm)
        if p.get('existing'):
            ph, src = 0, 'existing'
        elif d is not None and d.get('phase') is not None:
            ph, src = int(d['phase']), 'decisions.json: ' + str(d.get('reason') or '')
        else:
            ph = land_phase(g) if g.is_valid and not g.is_empty else None
            src = 'lies in the land of phase %s' % ph if ph else 'no phase: not counted'
        OS.append(dict(name=nm, use=p.get('use'), g=g, phase=ph, source=src, valid=g.is_valid))
    stats['open_spaces_without_phase'] = sum(1 for o in OS if o['phase'] is None)

    # ---- the street network ----
    LINES = []

    def lines_of(g):
        return [g] if g.geom_type == 'LineString' else [q for q in getattr(g, 'geoms', []) if q.geom_type == 'LineString']

    # where mobility routes cars, a new street without them (a bus link) is not for cars
    car_routes = [M(s) for p, _, s in (mob or []) if p.get('kind') == 'route' and p.get('mode') == 'car']
    CAR_AREA = unary_union(car_routes).buffer(C['snap_m']) if car_routes else None
    if st is not None:
        src_net = 'streets/streets.geojson'
        for p, _, s in st:
            if p.get('kind') not in ('centreline', 'path'):
                continue
            is_street = p.get('kind') == 'centreline'
            for q in lines_of(M(s)):
                car = is_street and (bool(p.get('existing')) or CAR_AREA is None or CAR_AREA.contains(q.interpolate(0.5, normalized=True)))
                LINES.append((q, dict(existing=bool(p.get('existing')), car=car, width=num(p.get('width') if is_street else p.get('width_m')),
                                      level=p.get('level') or ('path' if not is_street else None), name=p.get('name'), source=src_net)))
    else:
        src_net = 'massing streets and the site\'s streets'
        foot = ('footway', 'path', 'cycleway', 'pedestrian', 'steps', 'bridleway', 'track')
        if (SITE / 'streets.geojson').exists():
            for p, _, s in LL(SITE / 'streets.geojson'):
                for q in lines_of(M(s)):
                    LINES.append((q, dict(existing=True, car=p.get('highway') not in foot, width=num(p.get('width')),
                                          level=p.get('highway'), name=p.get('name'), source='site streets.geojson')))
        for p, _, s in mass:
            if p.get('kind') == 'street':
                for q in lines_of(M(s)):
                    LINES.append((q, dict(existing=False, car=p.get('level') != 'path', width=num(p.get('width')),
                                          level=p.get('level'), name=p.get('name'), source='massing')))
    # paths of the open spaces: for walking only, built with the open space they run through, never before
    os_paths = 0
    for p, _, s in (osp or []):
        if p.get('kind') != 'path':
            continue
        g = M(s)
        owner = max((o for o in OS if o['valid'] and o['g'].intersects(g)), key=lambda o: o['g'].intersection(g).length, default=None)
        ph = owner['phase'] if owner else land_phase(g)
        for q in lines_of(g):
            os_paths += 1
            LINES.append((q, dict(existing=False, car=False, width=num(p.get('width_m')), level='path', name=None,
                                  source='open-space path' + (f' in {owner["name"]}' if owner else ''), fixed=True, fixed_phase=ph)))
    stats['open_space_paths'] = os_paths
    stats['network_from'] = src_net if LINES else None
    snap = C['snap_m']
    E, NODES = [], {}
    OUTN, CAROUT = set(), set()
    if LINES:
        tree = STRtree([l for l, _ in LINES])
        conn = []
        for i, (l, at) in enumerate(LINES):
            for c in (l.coords[0], l.coords[-1]):
                pt = Point(c)
                near_ = [j for j in tree.query(pt.buffer(snap)) if j != i]
                if any(LINES[j][0].distance(pt) < 0.01 for j in near_):
                    continue
                best = min(((LINES[j][0].distance(pt), j) for j in near_ if LINES[j][0].distance(pt) <= snap), default=None)
                if best:
                    q = nearest_points(pt, LINES[best[1]][0])[1]
                    conn.append((LineString([pt, q]), dict(at, source='joined within snap_m')))
        stats['snapped_joins'] = len(conn)
        stats['snap_m'] = snap
        allL = LINES + conn
        tree2 = STRtree([l for l, _ in allL])
        noded = noded_union([l for l, _ in allL], grid_size=0.01)
        key = lambda c: (round(c[0], 2), round(c[1], 2))
        for piece in lines_of(noded):
            if piece.length < 0.005:
                continue
            mid = piece.interpolate(0.5, normalized=True)
            cands = [j for j in tree2.query(mid.buffer(0.05)) if allL[j][0].distance(mid) < 0.05]
            if not cands:
                continue
            j = min(cands, key=lambda j: (not allL[j][1]['existing'], not allL[j][1]['car'], bool(allL[j][1].get('fixed')), j))
            at = dict(allL[j][1])
            fixed, fixed_phase = at.pop('fixed', False), at.pop('fixed_phase', None)
            u, v = key(piece.coords[0]), key(piece.coords[-1])
            if u == v:
                continue
            NODES[u], NODES[v] = Point(piece.coords[0]), Point(piece.coords[-1])
            E.append(dict(u=u, v=v, g=piece, length=piece.length, mid=mid, fixed=fixed,
                          phase=0 if at['existing'] else (fixed_phase if fixed else None), **at))
        # where the network leaves the site: existing ends outside it, the gateways and the car accesses
        inner = site.buffer(0.5)
        for e in E:
            if e['existing']:
                for nd in (e['u'], e['v']):
                    if not inner.contains(NODES[nd]):
                        OUTN.add(nd)
                        if e['car']:
                            CAROUT.add(nd)
        ntree_keys = list(NODES)
        ntree = STRtree([NODES[k] for k in ntree_keys]) if ntree_keys else None
        accesses = [M(s) for p, _, s in (mob or []) if p.get('kind') == 'access']
        for pt in list(GATES.values()) + accesses:
            if ntree is None:
                break
            j = ntree.nearest(pt)
            if NODES[ntree_keys[j]].distance(pt) <= snap:
                OUTN.add(ntree_keys[j])
                if any(pt is x for x in accesses):
                    CAROUT.add(ntree_keys[j])
        if not OUTN:
            warn('no street of the network leaves the site: connection checks are not measured')
    etree = STRtree([e['g'] for e in E]) if E else None
    closed = {}
    for c in D['closures']:
        for s_ in c.get('stages') or []:
            closed.setdefault(int(s_), set()).add(c.get('street'))

    def usable_at(j):
        return {i for i, e in enumerate(E) if (e['existing'] and e.get('name') not in closed.get(j, set()))
                or (not e['existing'] and e['phase'] is not None and e['phase'] < j)}

    def attach(geom, usable, maxd):
        """[(node, distance)] from a footprint or point to the usable edges within maxd."""
        if etree is None:
            return []
        best = {}
        for i in etree.query(geom.buffer(maxd)):
            if i not in usable:
                continue
            e = E[i]
            d = geom.distance(e['g'])
            if d > maxd:
                continue
            t = e['g'].project(nearest_points(geom, e['g'])[1])
            for nd, off in ((e['u'], d + t), (e['v'], d + e['length'] - t)):
                if off < best.get(nd, math.inf):
                    best[nd] = off
        return list(best.items())

    def graph(edges):
        G = nx.Graph()
        for i in edges:
            e = E[i]
            if not G.has_edge(e['u'], e['v']) or G[e['u']][e['v']]['weight'] > e['length']:
                G.add_edge(e['u'], e['v'], weight=e['length'], e=i)
        return G

    def dist_from(G, sources):
        """Shortest distance along G from [(node, offset)] to every node."""
        H = G.copy()
        H.add_node('__S__')
        for nd, off in sources:
            if nd in H:
                if not H.has_edge('__S__', nd) or H['__S__'][nd]['weight'] > off:
                    H.add_edge('__S__', nd, weight=off)
        d = nx.single_source_dijkstra_path_length(H, '__S__', weight='weight')
        d.pop('__S__', None)
        return d

    def reach(dists, att):
        return min((off + dists[nd] for nd, off in att if nd in dists), default=None)

    # ---- phases for streets: each new segment is built with the first phase that needs it ----
    newE = [i for i, e in enumerate(E) if not e['existing'] and not e['fixed']]     # open-space paths keep their phase
    connected_at_assign = {}
    if E and OUTN:
        for k in range(1, n + 1):
            built = {i for i, e in enumerate(E) if e['existing'] or (e['phase'] is not None and e['phase'] <= k)}
            later = unary_union([LAND[j] for j in range(k + 1, n + 1) if LAND[j] is not None] or [Point()])
            cand = {i for i in newE if E[i]['phase'] is None and not later.contains(E[i]['mid'])}
            dout = None
            for b in [b for b in new if b['valid'] and b['phase'] == k]:
                if dout is None:              # remade only when a street was added
                    dout = dist_from(graph(built), [(o, 0.0) for o in OUTN])
                if reach(dout, attach(b['g'], built, C['entrance_max_m'])) is not None:
                    connected_at_assign[b['id']] = k
                    continue
                Gc = graph(built | cand)
                att = attach(b['g'], built | cand, C['entrance_max_m'])
                if not att:
                    continue
                H = Gc.copy()
                for nd, off in att:
                    H.add_edge('__S__', nd, weight=off)
                for o in OUTN:
                    if o in H:
                        H.add_edge(o, '__T__', weight=0.0)
                try:
                    path = nx.shortest_path(H, '__S__', '__T__', weight='weight')
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                # the street the building stands on, up to the path's first node, and then the path
                at_door = min((i for i in built | cand if path[1] in (E[i]['u'], E[i]['v'])), key=lambda i: E[i]['g'].distance(b['g']))
                for i in [at_door] + [H[x][y]['e'] for x, y in zip(path[1:-2], path[2:-1])]:
                    if E[i]['phase'] is None:
                        E[i]['phase'] = k
                        built.add(i)
                        cand.discard(i)
                        dout = None
                connected_at_assign[b['id']] = k
        for i in newE:                       # the rest: built with the phase whose land it lies in
            if E[i]['phase'] is None:
                E[i]['phase'] = land_phase(E[i]['g'])
        left = [i for i in newE if E[i]['phase'] is None]
        for i in left:                       # no phase needs it and it lies on no phase's land: it waits for the last, so all is built at completion
            E[i]['phase'] = n
        stats['streets_left_to_the_last_phase'] = len(left)
        if left:
            warn(f'{len(left)} pieces of new street or path are needed by no phase and lie on no phase\'s land: built with the last phase')
        for bid, k in connected_at_assign.items():     # guard: a phase never needs a later street
            built = {i for i, e in enumerate(E) if e['existing'] or (e['phase'] is not None and e['phase'] <= k)}
            dout = dist_from(graph(built), [(o, 0.0) for o in OUTN])
            if reach(dout, attach(by_id[bid]['g'], built, C['entrance_max_m'])) is None:
                die(f'bug: building {bid} of phase {k} needs a street of a later phase')
    stats['streets_without_phase'] = sum(1 for i in newE if E[i]['phase'] is None)
    stats['open_space_paths_without_phase'] = sum(1 for e in E if e['fixed'] and e['phase'] is None)

    # ---- stops, open spaces, services outside ----
    dec_stop = {d.get('name'): d for d in D['stops']}
    STOPS = []
    for p, _, s in (mob or []):
        if p.get('kind') == 'stop':
            d = dec_stop.get(p.get('name'))
            ph = None if d is None or d.get('phase') is None else int(d['phase'])
            STOPS.append(dict(name=p.get('name'), g=M(s), phase=ph, source=(d or {}).get('source') or 'no phase in decisions.json'))
    stats['stops_without_phase'] = [s['name'] for s in STOPS if s['phase'] is None]
    OUTSIDE = []
    for d in D['services_outside']:
        try:
            OUTSIDE.append(dict(name=d['name'], service=d['service'], g=Point(TO_M(*d['lonlat'])), stages=set(int(x) for x in d['stages']),
                                temporary=bool(d.get('temporary')), source=d.get('source', '')))
        except (KeyError, TypeError, ValueError):
            die(f'decisions.json services_outside: {d} needs name, service, lonlat, stages and source')

    # ---- the stage checks ----
    em = C['emergency']
    svc = C['services']
    FW = C['facility_words']
    ACC, STG = [], []
    worst = {}                 # building id -> list of failed checks at some stage
    def gate_node(pt):
        """The network node a gateway lies on (within snap_m), else None."""
        if pt is None or not NODES:
            return None
        nd = min(NODES, key=lambda k: NODES[k].distance(pt))
        return nd if NODES[nd].distance(pt) <= C['snap_m'] else None

    NCL = []                   # the forbidden car links, stage by stage
    has_existing = any(b['existing'] for b in B)
    ex_res = 0 if not has_existing else (None if C['existing_residents'] == NS else float(C['existing_residents']))
    existing_ok = [b for b in B if b['existing'] and b['valid']]
    TODAY = {'connected': set(), 'car': set()}   # the buildings that stay and are reached today: only these can lose it to a phase
    if OUTN:
        today = {i for i, e in enumerate(E) if e['existing']}
        today_car = {i for i in today if E[i]['car']}
        d_today = dist_from(graph(today), [(o, 0.0) for o in OUTN])
        d_car = dist_from(graph(today_car), [(o, 0.0) for o in (CAROUT or OUTN)])
        for b in existing_ok:
            if reach(d_today, attach(b['g'], today, C['entrance_max_m'])) is not None:
                TODAY['connected'].add(b['id'])
            if reach(d_car, attach(b['g'], today_car, C['entrance_max_m'])) is not None:
                TODAY['car'].add(b['id'])
        stats['existing_not_reached_today'] = len(existing_ok) - len(TODAY['connected'])
    CHECKED = ('connected', 'car') if any(r['measure'] == 'car' for r in C['requirements']) else ('connected',)   # car access only where the brief asks for it
    SV = {}                    # (stage, service) -> (within the limit, not measured, buildings)
    CAP = {}                   # (stage, service) -> (places, places needed), None where existing residents are unknown
    G_today = graph({i for i, e in enumerate(E) if e['existing'] and e['car']})
    for j in STAGES:
        U = usable_at(j)
        for i in U:   # guard: nothing new is usable before its phase is built
            if not E[i]['existing'] and (E[i]['phase'] is None or E[i]['phase'] >= j):
                die(f'bug: a {"path" if E[i]["fixed"] else "street"} of phase {E[i]["phase"]} usable at stage {j}')
        working = [b for b in new if b['valid'] and b['phase'] is not None and b['phase'] < j]
        G = graph(U)
        dout = dist_from(G, [(o, 0.0) for o in OUTN]) if OUTN else {}
        UC = {i for i in U if E[i]['car']}
        GC = graph(UC)
        dcar = dist_from(GC, [(o, 0.0) for o in (CAROUT or OUTN)]) if OUTN else {}
        for ga, gb in NO_CAR:     # a car route the mobility config forbids, on the car streets of this stage
            ends = [gate_node(GATES.get(x)) for x in (ga, gb)]
            lab = f'no car link {ga} - {gb}'
            stl = j if j <= n else 'completion'
            if None in ends:
                miss = [x for x, e_ in zip((ga, gb), ends) if e_ is None]
                NCL.append((stl, lab, 'no car route joins them', '', 'not measured: gateway ' + ', '.join(miss) + ' not found on the network'))
            elif ends[0] in G_today and ends[1] in G_today and nx.has_path(G_today, ends[0], ends[1]):
                NCL.append((stl, lab, 'no car route joins them', 'existing streets join them today', 'not measured: existing streets already join them'))
            else:
                joined = ends[0] in GC and ends[1] in GC and nx.has_path(GC, ends[0], ends[1])
                NCL.append((stl, lab, 'no car route joins them', 'a car route joins them' if joined else 'no car route joins them',
                            'does not meet' if joined else 'meets'))
        if em != NS:
            UE = {i for i in UC if E[i]['width'] is not None and E[i]['width'] >= em['min_width_m']}
            UEu = {i for i in UC if E[i]['width'] is None or E[i]['width'] >= em['min_width_m']}
            dem = dist_from(graph(UE), [(o, 0.0) for o in (CAROUT or OUTN)]) if OUTN else {}
            demu = dist_from(graph(UEu), [(o, 0.0) for o in (CAROUT or OUTN)]) if OUTN else {}
        # providers of each service that work at this stage
        sdist = {}
        for s in svc:
            items = []        # (who, phase it works from, geometry)
            if s['facility'] == 'stop':
                items += [(x['name'], x['phase'], x['g']) for x in STOPS if x['phase'] is not None and x['phase'] < j]
            else:
                w = FW[s['facility']]
                items += [(b['id'], 0 if b['existing'] else b['phase'], b['g']) for b in B if b['valid'] and has_word(b['use'], w)
                          and (b['existing'] or (b['phase'] is not None and b['phase'] < j))]
            tmp = [x for x in OUTSIDE if x['service'] == s['name'] and j in x['stages']]
            items += [(x['name'], 0, x['g']) for x in tmp]
            for who, ph, _ in items:   # guard: nothing of phase j or later serves
                if ph is None or ph >= j:
                    die(f'bug: {who} of phase {ph} counted as a service at stage {j}')
            prov = [g for _, _, g in items]
            src = [(nd, off) for g in prov for nd, off in attach(g, U, C['entrance_max_m'])]
            undecided = s['facility'] == 'stop' and any(x['phase'] is None for x in STOPS)
            sdist[s['name']] = (dist_from(G, src) if src and E else None, prov, bool(tmp), undecided)
        res_working = sum(b['homes'] for b in working if b['homes'] is not None) * hs
        for b in working + existing_ok:   # the buildings that stay are checked at every stage too
            row = dict(id=b['id'], phase=0 if b['existing'] else b['phase'], stage=j if j <= n else 'completion')
            att = attach(b['g'], U, C['entrance_max_m'])
            row['entry'] = 'yes' if att else 'no'
            if not OUTN:
                row['connected'] = row['car'] = 'not measured: no street leaves the site'
            else:
                row['connected'] = 'yes' if reach(dout, att) is not None else 'no'
                row['car'] = 'yes' if reach(dcar, attach(b['g'], UC, C['entrance_max_m'])) is not None else 'no'
            if em == NS:
                row['emergency'] = NSM
            elif not OUTN:
                row['emergency'] = 'not measured: no street leaves the site'
            else:
                ae = attach(b['g'], UE, em['max_distance_m'])
                if reach(dem, ae) is None:
                    row['emergency'] = 'not measured: street width unknown' if reach(demu, attach(b['g'], UEu, em['max_distance_m'])) is not None else 'does not meet'
                elif em['second_access']:
                    row['emergency'] = 'meets' if ways_in(graph(UE), ae, CAROUT or OUTN) >= 2 else 'partly: one way in'
                else:
                    row['emergency'] = 'meets'
            for s in svc:
                dmap, prov, tmp, und = sdist[s['name']]
                lim = s['walk_m']
                dd, how = None, ''
                if prov:
                    if dmap is None:
                        dd, how = min(b['g'].distance(g) for g in prov), ' (straight-line)'
                    else:
                        dd = reach(dmap, att)
                # a stop whose phase is not decided could be the nearer one: unless a decided stop already meets the
                # limit, the result is not measured, never a failure
                if und and (dd is None or (lim != NS and dd > lim)):
                    row[s['name'] + '_m'] = UNDECIDED
                elif not prov:
                    row[s['name'] + '_m'] = 'none working'
                else:
                    row[s['name'] + '_m'] = 'not reached' if dd is None else f'{dd:.0f}{how}{" (temporary)" if tmp else ""}'
            fails = [c for c in CHECKED if row[c] == 'no' and (not b['existing'] or b['id'] in TODAY[c])] + \
                (['emergency'] if row['emergency'] == 'does not meet' and not b['existing'] else [])
            if fails:
                worst.setdefault(b['id'], set()).update(f'{c} at stage {row["stage"]}' for c in fails)
            ACC.append(row)
        # what works at this stage
        os_now = [o for o in OS if o['valid'] and o['phase'] is not None and o['phase'] < j and o['use'] in C['open_space_uses']]
        os_area = unary_union([o['g'] for o in os_now]).area if os_now else 0.0
        stl = j if j <= n else 'completion'
        rows_all = [r for r in ACC if r['stage'] == stl]
        rows_j = [r for r in rows_all if r['phase'] != 0]          # the new buildings
        rows_x = [r for r in rows_all if r['phase'] == 0]          # the buildings that stay
        res_all = None if ex_res is None else res_working + ex_res
        srow = dict(stage=stl, under_construction=j if j <= n else '',
                    working_phases=', '.join(str(k) for k in range(1, min(j, n + 1))) or 'existing only',
                    homes=round(sum(b['homes'] for b in working if b['homes'] is not None)),
                    residents=round(res_working), existing_residents='not stated' if ex_res is None else round(ex_res),
                    buildings=len(working),
                    connected=f'{sum(1 for r in rows_j if r["connected"] == "yes")}/{len(rows_j)}',
                    existing_connected=f'{sum(1 for r in rows_x if r["id"] in TODAY["connected"] and r["connected"] == "yes")}/{len(TODAY["connected"])}',
                    car=f'{sum(1 for r in rows_j if r["car"] == "yes")}/{len(rows_j)}',
                    emergency=NSM if em == NS else f'{sum(1 for r in rows_j if r["emergency"] == "meets")}/{len(rows_j)}',
                    open_space_m2=round(os_area),
                    open_space_per_resident_m2=EXIST_UNKNOWN if res_all is None else (round(os_area / res_all, 1) if res_all else ''))
        for s in svc:
            lim = s['walk_m']
            vals = [r[s['name'] + '_m'] for r in rows_j]
            if lim == NS:
                srow[s['name']] = 'walk_m ' + NSM
                SV[(stl, s['name'])] = None
            else:
                ok = sum(1 for v in vals if re.match(r'^\d', str(v)) and float(str(v).split()[0]) <= lim)
                nm = sum(1 for v in vals if str(v).startswith('not measured'))
                srow[s['name']] = f'{ok}/{len(vals)} within {lim} m' + (f', {nm} {UNDECIDED}' if nm else '')
                SV[(stl, s['name'])] = (ok, nm, len(vals))
            if s.get('places_per_provider') is not None and s.get('places_per_resident') is not None:
                places = len(sdist[s['name']][1]) * s['places_per_provider']
                CAP[(stl, s['name'])] = None if res_all is None else (places, res_all * s['places_per_resident'])
                srow[s['name'] + '_capacity'] = EXIST_UNKNOWN if res_all is None else \
                    f'{places:.0f} places for {res_all * s["places_per_resident"]:.0f} needed'
        STG.append(srow)

    # ---- figures per phase ----
    PH = []
    for k in list(range(1, n + 1)) + ['total']:
        bs = [b for b in new if (b['phase'] == k if k != 'total' else b['phase'] is not None)]
        val = [b for b in bs if b['valid']]
        homes = sum(b['homes'] for b in val)
        uses = {}
        for b in val:
            uses[b['use']] = uses.get(b['use'], 0) + b['gfa']
        fac = {f: sum(1 for b in val if has_word(b['use'], w)) for f, w in FW.items()}
        osa = [o for o in OS if o['valid'] and (o['phase'] == k if k != 'total' else o['phase'] not in (None, 0)) and o['use'] in C['open_space_uses']]
        s_after = STG[k] if k != 'total' else STG[-1]   # stage k+1: phase k finished
        PH.append(dict(phase=k, homes=round(homes), residents=round(homes * hs), left_out=len(bs) - len(val),
                       uses='; '.join(f'{u} {a:.0f} m2' for u, a in sorted(uses.items(), key=lambda x: str(x[0]))),
                       uses_m2={u: a for u, a in uses.items()},
                       facilities='; '.join(f'{f} {c}' for f, c in fac.items() if c), fac=fac,
                       open_space_m2=round(unary_union([o['g'] for o in osa]).area) if osa else 0,
                       access=f'{s_after["connected"]} connected once finished',
                       source=f'homes: housing floor area / {m2_home:g} m2 per home (massing/config.json); '
                              f'residents: estimate, homes x {hs:.2f} ({hs_src})'))

    # ---- checks against the brief ----
    CH = []

    def add(stage, phase, req, brief, design, verdict, source):
        CH.append(dict(stage=stage, phase=phase, requirement=req, brief=brief, design=design, verdict=verdict, source=source))

    def share_verdict(ok, tot, need, nm=0):
        """nm: buildings not measured because a stop's phase is not decided; they never count as failures."""
        if tot == 0:
            return 'not measured: nothing working'
        if ok / tot >= need:
            return 'meets'
        if nm:
            return UNDECIDED
        return 'partly' if ok else 'does not meet'

    def os_verdict(v, test):
        if isinstance(v, str) and v.startswith('not measured'):
            return v
        if v == '':
            return 'not measured: no residents'
        return 'meets' if test(v) else 'does not meet'

    def phases_of(r):
        return list(range(1, n + 1)) if r['phase'] == 'each' else (['total'] if r['phase'] == 'all' else [r['phase']])

    for r in C['requirements']:
        m, op, want = r['measure'], r['op'], r['value']
        for k in phases_of(r):
            stage = (k + 1 if k != 'total' else n + 1)
            stage_l = stage if stage <= n else 'completion'
            ph = PH[k - 1] if k != 'total' else PH[-1]
            if want == NS:
                add(stage_l, k, m, NS, '', NSM, r['source'])
                continue
            if m in NUMERIC or m.startswith('floor_area:') or m.startswith('facility:'):
                if m in NUMERIC:
                    v = ph[m]
                elif m.startswith('floor_area:'):
                    v = sum(a for u, a in ph['uses_m2'].items() if has_word(u, [m[11:]]))
                else:
                    v = ph['fac'][m[9:]]
                ok = OPS[op](v, want)
                if ph['left_out']:
                    if op in ('>=', '>') and ok:
                        verdict = 'meets'                     # the invalid buildings can only add
                    elif op in ('<=', '<') and not ok:
                        verdict = 'does not meet'
                    else:
                        verdict = f'not measured: {ph["left_out"]} invalid buildings in this phase'
                else:
                    verdict = 'meets' if ok else 'does not meet'
                add('', k, m, f'{op} {want}', f'{v:.0f}', verdict, r['source'])
            elif m in SHARES or m.startswith('walk:'):
                for s_ in [s for s in STAGES if s > (k if k != 'total' else n)]:
                    rows = [x for x in ACC if x['stage'] == (s_ if s_ <= n else 'completion') and x['phase'] != 0
                            and (k == 'total' or x['phase'] <= k)]
                    nm = 0
                    if m == 'emergency' and em == NS:
                        add(s_ if s_ <= n else 'completion', k, m, NS, '', NSM, SRC['emergency'])
                        continue
                    if not OUTN and not m.startswith('walk:'):
                        add(s_ if s_ <= n else 'completion', k, m, f'{op} {want} of buildings', '',
                            'not measured: no street leaves the site', r['source'])
                        continue
                    if m.startswith('walk:'):
                        s = next(x for x in svc if x['name'] == m[5:])
                        if s['walk_m'] == NS:
                            add(s_ if s_ <= n else 'completion', k, m, NS, '', NSM, s['source'])
                            continue
                        col = s['name'] + '_m'
                        good = sum(1 for x in rows if re.match(r'^\d', str(x[col])) and float(str(x[col]).split()[0]) <= s['walk_m'])
                        nm = sum(1 for x in rows if str(x[col]).startswith('not measured'))
                    else:
                        col = 'connected' if m == 'access' else m
                        good = sum(1 for x in rows if x[col] in ('yes', 'meets'))
                    add(s_ if s_ <= n else 'completion', k, m, f'{op} {want} of buildings',
                        f'{good}/{len(rows)}' + (f', {nm} not measured' if nm else ''), share_verdict(good, len(rows), want, nm), r['source'])
            elif m == 'open_space_per_resident_m2':
                v = STG[stage - 1]['open_space_per_resident_m2']
                add(stage_l, k, m, f'{op} {want}', str(v), os_verdict(v, lambda x: OPS[op](x, want)), r['source'])
            else:
                add(stage_l, k, m, f'{op} {want}', '', 'for Claude to judge', r['source'])
    # services by the phase they must work by, and the first phase's place
    for s in svc:
        if s['by_phase'] == NS:
            add('', '', 'service ' + s['name'], 'by_phase ' + NS, '', NSM, s['source'])
            continue
        k = s['by_phase']
        srow = STG[k]
        sv = SV[(srow['stage'], s['name'])]
        add(srow['stage'], k, 'service ' + s['name'], f'working once phase {k} is finished' + ('' if s['walk_m'] == NS else f', within {s["walk_m"]} m'),
            srow[s['name']], NSM if sv is None else share_verdict(sv[0], sv[2], 1.0, sv[1]), s['source'])
        if (srow['stage'], s['name']) in CAP:
            cap = CAP[(srow['stage'], s['name'])]
            if cap is None:
                add(srow['stage'], k, 'capacity ' + s['name'], 'places for every resident', '', EXIST_UNKNOWN, s['source'])
            else:
                add(srow['stage'], k, 'capacity ' + s['name'], f'{cap[1]:.0f} places', f'{cap[0]:.0f}',
                    'meets' if cap[0] >= cap[1] else 'does not meet', s['source'])
        else:
            add(srow['stage'], k, 'capacity ' + s['name'], NS, '', NSM, s['source'])
    if C['first_phase'] == NS:
        add('', 1, 'first phase location', NS, '', NSM, SRC['first_phase'])
    elif not NB:
        add('', 1, 'first phase location', str(C['first_phase']), '', 'not measured: no structure plan', SRC['first_phase'])
    else:
        want = set(C['first_phase'] if isinstance(C['first_phase'], list) else [C['first_phase']])
        have = {x['name'] for x in NB if x['phase'] == 1}
        add('', 1, 'first phase location', ', '.join(sorted(want)), ', '.join(sorted(have)) or 'no neighbourhood has phase 1',
            'meets' if want <= have else ('partly' if want & have else 'does not meet'), SRC['first_phase'])
    if C['open_space_per_resident_m2'] == NS:
        add('', '', 'open space per resident', NS, '', NSM, SRC['open_space_per_resident_m2'])
    else:
        for srow in STG[1:]:
            v = srow['open_space_per_resident_m2']
            add(srow['stage'], '', 'open space per resident', f'>= {C["open_space_per_resident_m2"]} m2',
                str(v), os_verdict(v, lambda x: x >= C['open_space_per_resident_m2']), SRC['open_space_per_resident_m2'])
    # the buildings that stay: still reached at every stage, while the new ones are built around them
    if has_existing:
        for srow in STG:
            ok, tot = (int(x) for x in srow['existing_connected'].split('/'))
            add(srow['stage'], 0, 'existing buildings stay reached', 'every building reached today',
                srow['existing_connected'], 'not measured: no street leaves the site' if not OUTN else share_verdict(ok, tot, 1.0),
                'existing buildings in massing.geojson')
    for stl, lab, brief, design, verdict in NCL:
        add(stl, '', lab, brief, design, verdict, no_car_src)
    if not NO_CAR:
        add('', '', 'forbidden car links', 'none listed in mobility/config.json' if (P / 'mobility/config.json').exists()
            else 'no mobility/config.json', '', NSM, no_car_src or 'mobility/config.json')

    # ---- evidence for the buildings left for review ----
    EV = []
    for b in B:
        if b['basis'] != 'review':
            continue
        c_ll = transform(TO_LL, b['g'].representative_point()) if b['valid'] else None
        row = dict(id=b['id'], centre_lon=round(c_ll.x, 7) if c_ll else '', centre_lat=round(c_ll.y, 7) if c_ll else '',
                   footprint_m2=round(b['area']) if b['valid'] else '', use=b['use'], floors=b['floors'],
                   massing_neighbourhood=b['p'].get('neighbourhood'), valid=b['valid'], reason=b['reason'])
        if b['valid']:
            pt = b['g'].representative_point()
            row['lies_in'] = '; '.join(f'{x["name"]} (phase {x["phase"]})' for x in NB if x['g'].contains(pt)) or 'no neighbourhood'
            if CENTRES:
                cn = min(CENTRES, key=lambda x: x['g'].distance(b['g']))
                row['nearest_centre'] = f'{cn["name"]}, {cn["g"].distance(b["g"]):.0f} m, holds {cn["holds"]}'
            if E:
                ne = min(range(len(E)), key=lambda i: E[i]['g'].distance(b['g']))
                row['nearest_street'] = f'phase {E[ne]["phase"]}, {E[ne]["g"].distance(b["g"]):.0f} m, {"existing" if E[ne]["existing"] else "new"}'
            nbs = sorted({x['phase'] for x in new if x['phase'] and x['valid'] and x['g'].distance(b['g']) <= C['entrance_max_m']})
            row['phases_of_neighbours'] = ', '.join(map(str, nbs)) or 'none within entrance_max_m'
        EV.append(row)

    # ---- write ----
    feats = []

    def put(kind, g, **pr):
        feats.append({'type': 'Feature', 'properties': {'kind': kind, **pr}, 'geometry': mapping(transform(TO_LL, g))})

    for k, ph in zip(range(1, n + 1), PH):
        if LAND[k] is not None and not LAND[k].is_empty:
            put('phase', LAND[k], phase=k, homes=ph['homes'], residents=ph['residents'],
                residents_source='estimate: ' + ph['source'].split('; ')[1], floor_area_m2=round(sum(ph['uses_m2'].values())))
    for b in B:
        g_ll = mass[b['i']][1]
        feats.append({'type': 'Feature', 'geometry': g_ll, 'properties': {
            'kind': 'building', 'id': b['id'], 'phase': b['phase'], 'basis': b['basis'],
            'reason': b['reason'] if b['basis'] in ('proposed', 'review') else None,
            'homes': None if b['homes'] is None else round(b['homes'], 2), 'use': b['use'], 'existing': b['existing'],
            'geometry_valid': b['valid'], 'invalid_reason': b['invalid_reason'],
            'fails': sorted(worst.get(b['id'], []))}})
    for e in E:
        put('street', e['g'], phase=e['phase'], existing=e['existing'], level=e['level'], width_m=e['width'], car=e['car'],
            open_space_path=e['fixed'], source=e['source'])
    for s in STOPS:
        put('stop', s['g'], name=s['name'], phase=s['phase'], source=s['source'])
    for o in OS:
        put('open-space', o['g'], use=o['use'], phase=o['phase'], area_m2=round(o['g'].area) if o['valid'] else None, source=o['source'])
    (OUT / 'phasing.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'name': 'phasing',
                                                     'note': f'WGS84, longitude first; areas measured in EPSG:{EPSG}',
                                                     'features': feats}, ensure_ascii=False), encoding='utf-8')

    def write_csv(name, rows, cols=None):
        cols = cols or list(dict.fromkeys(k for r in rows for k in r))
        with (OUT / name).open('w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
            w.writeheader()
            w.writerows(rows)

    if (OUT / 'phases.csv').exists():   # the homes per phase the panels show are phases.py's: say where this count differs
        shown = {r['phase']: num(r['homes']) for r in csv.DictReader((OUT / 'phases.csv').open(encoding='utf-8'))}
        for ph in PH[:-1]:              # the numbered phases: phases.csv's total also holds homes with no phase
            if shown.get(str(ph['phase'])) not in (None, ph['homes']):
                warn(f'phase {ph["phase"]}: {ph["homes"]} homes here, {shown[str(ph["phase"])]:.0f} in phases.csv: a building decided in decisions.json?')
    kept = [o for o in OS if o['valid'] and o['phase'] == 0 and o['use'] in C['open_space_uses']]
    table = PH + ([dict(phase='existing', open_space_m2=round(unary_union([o['g'] for o in kept]).area))] if kept else [])
    write_csv('stage-phases.csv', [dict(r, source='facilities and floor areas: massing.geojson; open space: open-space.geojson; '
                                                  'access: stages.csv; homes and residents: phases.csv') for r in table],
              ['phase', 'uses', 'facilities', 'open_space_m2', 'access', 'left_out', 'source'])
    write_csv('stages.csv', STG)
    write_csv('access.csv', ACC)
    write_csv('checks.csv', CH, ['stage', 'phase', 'requirement', 'brief', 'design', 'verdict', 'source'])
    write_csv('evidence.csv', EV, ['id', 'centre_lon', 'centre_lat', 'footprint_m2', 'use', 'floors', 'massing_neighbourhood',
                                   'lies_in', 'nearest_centre', 'nearest_street', 'phases_of_neighbours', 'valid', 'reason'])
    stats['buildings_flagged_for_review'] = counts.get('review', 0)
    stats['buildings_failing_a_stage_check'] = len(worst)
    (OUT / 'stage-stats.json').write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{len(B)} buildings: ' + ', '.join(f'{v} {k}' for k, v in counts.items()) + f'; {len(invalid)} invalid; '
          f'{len(stats["warnings"])} warnings; wrote {OUT}')


def ways_in(G, att, outs):
    """How many separate routes (sharing no street) lead from a building to the outside: a maximum flow of capacity 1 per street."""
    Dg = nx.DiGraph()
    outs = set(outs)
    for x, y in G.edges():
        x2, y2 = ('__T__' if x in outs else x), ('__T__' if y in outs else y)
        if x2 == y2:
            continue
        for s, t in ((x2, y2), (y2, x2)):
            Dg.add_edge(s, t, capacity=Dg[s][t]['capacity'] + 1 if Dg.has_edge(s, t) else 1)
    if '__T__' not in Dg:
        return 0
    for nd, _ in att:
        if nd in outs:       # the building's own stretch of street leads straight out: one way, not more
            Dg.add_edge('__S__', '__T__', capacity=Dg['__S__']['__T__']['capacity'] + 1 if Dg.has_edge('__S__', '__T__') else 1)
        else:
            Dg.add_edge('__S__', nd, capacity=math.inf)
    if '__S__' not in Dg:
        return 0
    return int(nx.maximum_flow_value(Dg, '__S__', '__T__'))


if __name__ == '__main__':
    main()
