"""The ground floors of an urban design, by rules: entrances on the street side, bike stands at the entrances, play in
the courtyards, the uses with their areas at the centres, and a hub's bus bays and bike parking.

    python ground_floor.py --proposal <proposal folder> --config <proposal>/ground-floor/config.json

Reads massing/massing.geojson, and where they exist streets/streets.geojson, structure-plan/structure-plan.geojson,
mobility/mobility.geojson and open-space/open-space.geojson. config.json holds, each as {"value", "source"}:
bike_stands_per_entrance, play_m2, centre_uses (a list of {"use", "area_m2", "at", "source"}: a use with an area that
goes into a ground floor at the centre `at`) and hubs (a list of {"at", "bus_bays", "bike_spaces", "source"}, `at` a hub
of the mobility layer or a centre of the structure plan); any key of DEFAULTS may be set there too. The massing's
ground_floor stays the massing's: a use refined here is written into this skill's file only. Writes detail.geojson,
uses.csv and stats.json into <proposal>/ground-floor/ and prints stats.json, nothing else.
"""
import argparse, csv, json, math, os, re, sys
from shapely.geometry import shape, mapping, Point, LineString, MultiLineString, MultiPolygon, Polygon, box
from shapely.ops import transform, unary_union, polylabel, nearest_points
from shapely.prepared import prep
from shapely import affinity
import pyproj

REQUIRED = ['bike_stands_per_entrance', 'play_m2', 'centre_uses', 'hubs']
DEFAULTS = {
    'entrance_spacing_m': 30,     # one door (a stair, a shop) per this much front, assumption
    'entrance_min_edge_m': 4,     # a facade shorter than this takes no door
    'street_reach_m': 40,         # a facade further than this from every street takes its door from the nearest path
    'door_gap_m': 2.0,            # the bike stands start this far beside the door
    'stand_gap_m': 1.0,           # between two stands, each for two bikes
    'stand_len_m': 1.8,           # a stand's length, out from the facade
    'stand_off_m': 0.6,           # and its start, off the facade
    'play_min_court_m2': 600,     # a courtyard smaller than this takes no play area
    'play_edge_m': 2.0,           # the play area keeps this far from the courtyard's edge
    'centre_reach_m': 30,         # a building this close to a centre fronts it
    'hub_reach_m': 150,           # a hub's surfaces lie this close to it
    'bus_bay_m': [3.5, 18.0],     # a bus bay's width and length, assumption: an articulated bus
    'platform_m': 3.0,            # the waiting platform beside the bays
    'bike_row_m': 4.0,            # a double row of bike stands, deep (four bikes per stand gap)
    'bike_aisle_m': 2.0,          # between two double rows
    'street_w_new_m': 10.0,       # a massing street without a width
    'label_bays': '{n} bus bays',
    'label_bikes': '{n} bike spaces',
}
HOUSING = ('housing', 'homes', 'residential')
SHOPS = ('commerce', 'shop', 'retail', 'mixed')
ENTRY_KEYS = {'centre_uses': ('use', 'area_m2', 'at'), 'hubs': ('at',)}


def read_config(path):
    """config.json as {key: {"value", "source"}} or {key: value}; an empty value or a <placeholder> stops on its name."""
    raw = json.load(open(path, encoding='utf8'))
    cfg, src = dict(DEFAULTS), {}
    for k, v in raw.items():
        val = v.get('value') if isinstance(v, dict) and 'value' in v else v
        s = str(v.get('source', '')) if isinstance(v, dict) else ''
        if val is None or s.startswith('<'):
            continue
        cfg[k], src[k] = val, s
    missing = [k for k in REQUIRED if k not in src]
    for k, need in ENTRY_KEYS.items():
        for i, e in enumerate(cfg.get(k) or []):
            missing += ['%s[%d].%s' % (k, i, f) for f in need if e.get(f) is None or str(e.get(f)).startswith('<')]
    if missing:
        sys.exit('ground-floor config: empty ' + ', '.join(missing) + ' (fill from the brief or the programme, with its source)')
    return cfg, src


A = argparse.ArgumentParser(description='The ground floors of an urban design, by rules.')
A.add_argument('--proposal', required=True)
A.add_argument('--config', required=True)
ARGS = A.parse_args()
RUN = ARGS.proposal
OUT = os.path.join(RUN, 'ground-floor')
os.makedirs(OUT, exist_ok=True)
CFG, SRC = read_config(ARGS.config)

mpath = os.path.join(RUN, 'massing', 'massing.geojson')
if not os.path.exists(mpath):
    sys.exit('missing massing/massing.geojson in the proposal: run the massing first')
RAW = json.load(open(mpath, encoding='utf8'))['features']
c0 = unary_union([shape(f['geometry']) for f in RAW if f.get('geometry') and f['properties'].get('kind') == 'building']).centroid
EPSG = (32600 if c0.y >= 0 else 32700) + int((c0.x + 180) // 6) + 1
TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
TO_LL = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform


def load(name):
    """[(properties, geometry in metres)] of a proposal's GeoJSON, [] when it is missing."""
    p = os.path.join(RUN, name)
    if not os.path.exists(p):
        return []
    out = []
    for f in json.load(open(p, encoding='utf8'))['features']:
        if f.get('geometry'):
            g = transform(TO_M, shape(f['geometry']))
            out.append((f.get('properties') or {}, g if g.is_valid else g.buffer(0)))
    return out


MASS = [(f.get('properties') or {}, transform(TO_M, shape(f['geometry'])) if f.get('geometry') else None) for f in RAW]
STREETS, SP = load('streets/streets.geojson'), load('structure-plan/structure-plan.geojson')
MOB, OPEN = load('mobility/mobility.geojson'), load('open-space/open-space.geojson')
used = ['massing'] + [n for n, L in (('streets', STREETS), ('structure-plan', SP), ('mobility', MOB), ('open-space', OPEN)) if L]
NEW = [(i, p, g.buffer(0) if not g.is_valid else g) for i, (p, g) in enumerate(MASS)
       if g is not None and p.get('kind') == 'building' and not p.get('existing') and g.geom_type.endswith('Polygon')]
ALL_B = unary_union([g for p, g in MASS if g is not None and p.get('kind') == 'building' and g.geom_type.endswith('Polygon')])
B_PREP = prep(ALL_B)
# the street surface: the streets skill's polygons (not its squares) and the massing's streets at their widths
STREET = unary_union([g for p, g in STREETS if p.get('kind') == 'street' and p.get('use') != 'square' and g.geom_type.endswith('Polygon')]
                     + [g if g.geom_type.endswith('Polygon') else g.buffer(float(p.get('width') or CFG['street_w_new_m']) / 2, cap_style=2)
                        for p, g in MASS if g is not None and p.get('kind') == 'street' and p.get('level') != 'path'])
PATH = unary_union([g for p, g in MASS + STREETS + OPEN if g is not None and (p.get('kind') == 'path' or p.get('level') == 'path')])
FEATS, FLAGS, ROWS = [], [], []


def add(kind, geom, **props):
    FEATS.append({'type': 'Feature', 'properties': {'kind': kind, **props}, 'geometry': mapping(transform(TO_LL, geom))})


def bearing(vx, vy):
    """The direction of a vector in degrees clockwise from the grid's north."""
    return round(math.degrees(math.atan2(vx, vy)), 1) % 360


def facades(g):
    """The outer edges of a footprint, counter-clockwise: [(start, unit along, unit out, length)]."""
    q = max(getattr(g, 'geoms', [g]), key=lambda x: x.area).simplify(0.5)
    c = [xy[:2] for xy in q.exterior.coords]
    if not q.exterior.is_ccw:
        c = c[::-1]
    out = []
    for a, b in zip(c, c[1:]):
        L = math.dist(a, b)
        if L > 0:
            u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
            out.append((a, u, (u[1], -u[0]), L))
    return out


def far(geom, target):
    return geom.distance(target) if not target.is_empty else math.inf


# ---------- 1. entrances on the street side, 2. bike stands beside each ----------
doors = {}      # massing index -> [(point, outward unit)]
faces = {'street': 0, 'path': 0, 'none': 0}
n_stands = 0
for idx, p, g in NEW:
    cand = []
    for a, u, n, L in facades(g):
        if L < CFG['entrance_min_edge_m']:
            continue
        probe = Point(a[0] + u[0] * L / 2 + n[0] * 2, a[1] + u[1] * L / 2 + n[1] * 2)
        if B_PREP.contains(probe):
            continue                                  # a party wall
        cand.append((a, u, n, L, far(probe, STREET), far(probe, PATH)))
    if not cand:
        FLAGS.append('building %d (%s): no free facade for a door' % (idx, p.get('use')))
        continue
    on_street = [c for c in cand if c[4] <= CFG['street_reach_m']]
    on_path = [c for c in cand if c[5] <= CFG['street_reach_m']]
    if on_street:
        side, pick = 'street', min(on_street, key=lambda c: (round(c[4] / 3), -c[3]))
    elif on_path:
        side, pick = 'path', min(on_path, key=lambda c: (round(c[5] / 3), -c[3]))
    else:
        side, pick = 'none', min(cand, key=lambda c: (c[4], -c[3]))
    a, u, n, L = pick[:4]
    gf = p.get('ground_floor') or p.get('use') or ''
    k = max(1, int(L / CFG['entrance_spacing_m'] + 0.5))
    for j in range(k):
        t = (j + 0.5) * L / k
        pt = Point(a[0] + u[0] * t, a[1] + u[1] * t)
        doors.setdefault(idx, []).append((pt, n))
        faces[side] += 1
        add('entrance', pt, building=idx, block=p.get('block'), use=gf, faces=side, bearing_deg=bearing(*n),
            source='rule: the facade nearest a street, one door per %g m of front' % CFG['entrance_spacing_m'])

        def row(sgn, count):
            segs = []
            for m in range(count):
                s = t + sgn * (CFG['door_gap_m'] + m * CFG['stand_gap_m'])
                if not 0.3 <= s <= L - 0.3:
                    break
                x, y = a[0] + u[0] * s, a[1] + u[1] * s
                seg = LineString([(x + n[0] * CFG['stand_off_m'], y + n[1] * CFG['stand_off_m']),
                                  (x + n[0] * (CFG['stand_off_m'] + CFG['stand_len_m']), y + n[1] * (CFG['stand_off_m'] + CFG['stand_len_m']))])
                if B_PREP.intersects(seg):
                    break
                segs.append(seg)
            return segs
        want = int(CFG['bike_stands_per_entrance'])
        segs = row(1, want)
        segs += row(-1, want - len(segs))
        if segs:
            n_stands += len(segs)
            add('bike-stands', MultiLineString(segs), building=idx, at='entrance', stands=len(segs),
                source=SRC.get('bike_stands_per_entrance', ''))

if faces['none']:
    FLAGS.append('%d doors face no street or path within %g m' % (faces['none'], CFG['street_reach_m']))

# ---------- 3. play in the courtyards ----------
PLAYGROUNDS = unary_union([g for p, g in OPEN if p.get('kind') == 'open-space' and p.get('use') == 'playground'])
play = {'courtyards': 0, 'placed': 0, 'm2': 0, 'has_playground': 0, 'too_small': 0}
for p, g in MASS:
    if g is None or p.get('kind') != 'open-space' or p.get('use') != 'garden' or not g.geom_type.endswith('Polygon'):
        continue
    play['courtyards'] += 1
    if g.area < CFG['play_min_court_m2']:
        play['too_small'] += 1
        continue
    if not PLAYGROUNDS.is_empty and g.intersection(PLAYGROUNDS).area > 0.1 * CFG['play_m2']:
        play['has_playground'] += 1
        continue
    inner = g.buffer(-CFG['play_edge_m'])
    q = max(getattr(inner, 'geoms', [inner]), key=lambda x: x.area) if not inner.is_empty else None
    if q is None or q.geom_type != 'Polygon':
        play['too_small'] += 1
        continue
    c = polylabel(q, 0.5)
    r = min(math.sqrt(CFG['play_m2'] / math.pi), q.boundary.distance(c))
    if math.pi * r * r < 0.5 * CFG['play_m2']:
        play['too_small'] += 1
        continue
    circle = c.buffer(r, 24)
    play['placed'] += 1
    play['m2'] += round(circle.area)
    add('play', circle, area_m2=round(circle.area), source=SRC.get('play_m2', ''))

# ---------- 4. the uses with their areas at the centres ----------
CENTRES = [(p, g) for p, g in SP if p.get('kind') == 'centre' and p.get('name')]
at_centre = {}
for idx, p, g in NEW:
    if CENTRES:
        d, name = min((g.distance(cg), cp['name']) for cp, cg in CENTRES)
        if d <= CFG['centre_reach_m']:
            at_centre[idx] = name
BY_IDX = {idx: (p, g) for idx, p, g in NEW}


def low(s): return str(s or '').lower()


def use_area(p, g):
    """The floor area of a building's ground-floor use: the whole building where it holds one use, a daycare's floors,
    else the ground floor."""
    fp = float(p.get('footprint_m2') or g.area)
    if low(p.get('ground_floor')) == 'daycare' and p.get('daycare_floors'):
        return fp * float(p['daycare_floors'])
    if not low(p.get('use')).startswith(HOUSING + ('mixed',)):
        return float(p.get('gfa_m2') or fp * float(p.get('floors') or 1))
    return fp


refined = {}    # massing index -> the config entry it takes
for e in CFG['centre_uses']:
    here = [idx for idx, c in at_centre.items() if low(c) == low(e['at']) and idx not in refined]
    if not here:
        FLAGS.append('%s: no new building at the centre "%s"' % (e['use'], e['at']))
        continue
    word = low(e['use']).split()[0]
    same = [i for i in here if word in low(BY_IDX[i][0].get('use')) + ' ' + low(BY_IDX[i][0].get('ground_floor'))]
    shops = [i for i in here if low(BY_IDX[i][0].get('ground_floor')).startswith(SHOPS)]
    fp = lambda i: float(BY_IDX[i][0].get('footprint_m2') or BY_IDX[i][1].area)
    if same:
        refined[max(same, key=fp)] = dict(e, kept=True)
    elif shops:
        fits = [i for i in shops if fp(i) >= float(e['area_m2'])]
        i = min(fits, key=fp) if fits else max(shops, key=fp)
        if not fits:
            FLAGS.append('%s needs %d m2; the largest shop floor at %s has %d m2' % (e['use'], e['area_m2'], e['at'], fp(i)))
        refined[i] = dict(e, kept=False)
    else:
        FLAGS.append('%s: no shop floor at the centre "%s" to take it' % (e['use'], e['at']))

centre_m2 = 0
for idx, name in sorted(at_centre.items()):
    p, g = BY_IDX[idx]
    gf = p.get('ground_floor') or p.get('use') or ''
    e = refined.get(idx)
    if e is None and low(gf).startswith(HOUSING):
        continue
    if e is not None and not e['kept']:
        use, area, src = e['use'], float(e['area_m2']), e.get('source', '')
    else:
        use, area, src = (gf if e is None else p.get('use') or gf), use_area(p, g), 'massing: the ground floor use and its floor area'
    prog = float(e['area_m2']) if e is not None else None
    if e is not None and e['kept'] and abs(area - prog) > 0.1 * prog:
        FLAGS.append('%s at %s: %d m2 built, %d m2 in the programme' % (use, name, area, prog))
    ds = doors.get(idx) or [(g.representative_point(), None)]
    cg = next(cg for cp, cg in CENTRES if cp['name'] == name)
    pt, n = min(ds, key=lambda d: d[0].distance(cg))
    centre_m2 += area
    label = '%s %s m²' % (re.sub(r'\s+\d+$', '', use), '{:,}'.format(int(round(area))))   # "daycare 1" reads "daycare"
    add('use', pt, building=idx, centre=name, use=use, area_m2=round(area), label=label, massing_ground_floor=gf,
        source=src, **({'bearing_deg': bearing(*n)} if n else {}))
    ROWS.append(dict(centre=name, use=use, area_m2=round(area), programme_m2=prog if prog is not None else '',
                     massing_ground_floor=gf, building=idx, block=p.get('block', ''), part=p.get('part', ''), source=src))

# ---------- 5. a hub's bus bays and bike parking ----------


def place(land, w, h, ang, near):
    """(x, y, angle) of a w x h rectangle at the angle, or at it plus 90 degrees, that fits in the land nearest `near`."""
    if land.is_empty:
        return None
    lp = prep(land.buffer(0.05))
    inner = land.buffer(-min(w, h) / 2 + 0.01)
    if inner.is_empty:
        return None
    ip = prep(inner)
    x0, y0, x1, y1 = inner.bounds
    pts = [(x0 + i * 2.0, y0 + j * 2.0) for i in range(int((x1 - x0) / 2) + 1) for j in range(int((y1 - y0) / 2) + 1)]
    pts = sorted((q for q in pts if ip.contains(Point(q))), key=lambda q: math.dist(q, (near.x, near.y)))
    for a in (ang, ang + 90):
        base = affinity.rotate(box(-w / 2, -h / 2, w / 2, h / 2), a, origin=(0, 0))
        for x, y in pts[:6000]:
            if lp.contains(affinity.translate(base, x, y)):
                return x, y, a
    return None


def local(shape_, at):
    x, y, a = at
    return affinity.translate(affinity.rotate(shape_, a, origin=(0, 0)), x, y)


hubs = []
BLOCKED = unary_union([ALL_B.buffer(2)] + ([STREET.buffer(0.5)] if not STREET.is_empty else [])
                      + [g for p, g in OPEN if p.get('kind') == 'retention' or p.get('use') in ('water', 'playground')]
                      + [g for p, g in MASS if g is not None and p.get('kind') == 'open-space' and p.get('use') == 'water'])
for h in CFG['hubs']:
    name = h['at']
    H = next((g for p, g in MOB if p.get('kind') == 'hub' and low(p.get('name')) == low(name) and g.geom_type == 'Point'), None)
    cen = next((g for p, g in CENTRES if low(p['name']) == low(name)), None)
    if H is None and cen is not None:
        H = cen.representative_point()
    if H is None:
        FLAGS.append('hub "%s": not a hub of the mobility layer nor a centre of the structure plan' % name)
        continue
    if cen is None and CENTRES:
        g = min((g for p, g in CENTRES), key=lambda g: g.distance(H))
        cen = g if g.distance(H) <= 50 else None
    R = CFG['hub_reach_m']
    land = unary_union([g for p, g in MASS if g is not None and p.get('kind') == 'open-space' and p.get('use') == 'square'
                        and g.distance(H) <= R] + ([cen] if cen is not None else []))
    land = land.intersection(H.buffer(R)).difference(BLOCKED) if not land.is_empty else land
    near_st = nearest_points(STREET, H)[0] if not STREET.is_empty else H
    piece = STREET.intersection(near_st.buffer(25)) if not STREET.is_empty else Polygon()
    ang = 0.0
    if not piece.is_empty:
        c = list(piece.minimum_rotated_rectangle.exterior.coords)
        (ax, ay), (bx, by) = max(((c[i], c[i + 1]) for i in range(2)), key=lambda e: math.dist(*e))
        ang = math.degrees(math.atan2(by - ay, bx - ax))
    rec = dict(at=name, bus_bays=0, bike_spaces=0)
    bw, bl = CFG['bus_bay_m']
    nb = int(h.get('bus_bays') or 0)
    if nb:
        for rows in (1, 2):
            per = math.ceil(nb / rows)
            w, hh = per * bl, rows * bw + CFG['platform_m']
            spot = place(land, w, hh, ang, near_st)
            if spot:
                bays = []
                for r_ in range(rows):
                    y0 = -hh / 2 if r_ == 0 else hh / 2 - bw
                    for i in range(min(per, nb - r_ * per)):
                        bays.append(local(box(-w / 2 + i * bl, y0, -w / 2 + (i + 1) * bl, y0 + bw), spot))
                for i, b in enumerate(bays):
                    add('bus-bay', b, hub=name, n=i + 1, source=h.get('source', ''))
                area = local(box(-w / 2, -hh / 2, w / 2, hh / 2), spot)
                add('use', area.centroid, hub=name, use='bus bays', label=CFG['label_bays'].format(n=len(bays)), source=h.get('source', ''))
                land = land.difference(area.buffer(2))
                rec['bus_bays'] = len(bays)
                break
        else:
            FLAGS.append('hub "%s": no room for %d bus bays on its squares and centre' % (name, nb))
    ns = int(h.get('bike_spaces') or 0)
    if ns:
        stop = min([g for p, g in MOB if p.get('kind') == 'stop' and g.geom_type == 'Point' and g.distance(H) <= R],
                   key=lambda g: g.distance(H), default=H)
        stands = math.ceil(ns / 4)                    # a stand gap of a double row holds four bikes
        k0 = max(1, math.ceil(stands * CFG['stand_gap_m'] / 30))
        for k in range(k0, k0 + 4):
            w = math.ceil(stands / k) * CFG['stand_gap_m']
            hh = k * CFG['bike_row_m'] + (k - 1) * CFG['bike_aisle_m']
            spot = place(land, w, hh, ang, stop)
            if spot:
                strips, lines = [], []
                for r_ in range(k):
                    y0 = -hh / 2 + r_ * (CFG['bike_row_m'] + CFG['bike_aisle_m'])
                    strips.append(local(box(-w / 2, y0, w / 2, y0 + CFG['bike_row_m']), spot))
                    lines += [local(LineString([(-w / 2 + (i + 0.5) * CFG['stand_gap_m'], y0), (-w / 2 + (i + 0.5) * CFG['stand_gap_m'], y0 + CFG['bike_row_m'])]), spot)
                              for i in range(int(round(w / CFG['stand_gap_m'])))]
                add('bike-parking', MultiPolygon(strips), hub=name, spaces=ns, source=h.get('source', ''))
                add('bike-stands', MultiLineString(lines), hub=name, at=name, stands=len(lines) * 2, source=h.get('source', ''))
                add('use', unary_union(strips).centroid, hub=name, use='bike parking', label=CFG['label_bikes'].format(n=ns), source=h.get('source', ''))
                rec['bike_spaces'] = ns
                break
        else:
            FLAGS.append('hub "%s": no room for %d bike spaces on its squares and centre' % (name, ns))
    hubs.append(rec)

# ---------- write ----------
json.dump({'type': 'FeatureCollection', 'name': 'ground-floor', 'note': 'WGS84, longitude first; built in EPSG:%d' % EPSG,
           'features': FEATS}, open(os.path.join(OUT, 'detail.geojson'), 'w', encoding='utf8'), ensure_ascii=False)
with open(os.path.join(OUT, 'uses.csv'), 'w', newline='', encoding='utf8') as f:
    w = csv.DictWriter(f, ['centre', 'use', 'area_m2', 'programme_m2', 'massing_ground_floor', 'building', 'block', 'part', 'source'])
    w.writeheader()
    w.writerows(ROWS)
stats = dict(buildings=len(NEW), entrances=sum(faces.values()), faces=faces, bike_stands=n_stands, play=play,
             centre_uses=len(ROWS), centre_ground_m2=round(centre_m2), refined=[dict(at=e['at'], use=e['use'], building=i)
             for i, e in refined.items() if not e['kept']], hubs=hubs, layers_used=used, flags=FLAGS,
             assumptions={k: CFG[k] for k in DEFAULTS if k not in SRC and not k.startswith('label')})
json.dump(stats, open(os.path.join(OUT, 'stats.json'), 'w', encoding='utf8'), indent=1, ensure_ascii=False)
print(json.dumps(stats, indent=1, ensure_ascii=False))
