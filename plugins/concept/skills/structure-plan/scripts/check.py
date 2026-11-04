"""The checks of a structure plan, and a check plan to look at.

    python check.py --proposal <proposal folder> --site <site folder> [--climate <folder>] [--distance 150]
                    [--style style.json]

Reads <proposal>/structure-plan/structure-plan.geojson, the site and, where they exist, the climate's rules.geojson
(default <proposal>/climate), the site's terrain model (terrain*.tif or terrain.csv) and the brief's homes from
<proposal>/programme/programme.csv, else the brief's checklist. Writes into <proposal>/structure-plan/: checks.txt, check-plan.svg and check-plan.png.
build.py runs it after every build; it also runs alone.
"""
import argparse, csv, heapq, html, json, math, os, re, subprocess, sys
from pathlib import Path

import numpy as np
import pyproj
import shapely
from shapely import STRtree, segmentize
from shapely.geometry import shape, Point
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frame import Frame, parts

DEFAULTS = {
    'distance_m': 150,          # proximity: new land within this straight-line distance of a centre or public green
    'walk_m': 400,              # walk: homes within this distance of the stop, along routes and streets
    'spare': 0.15,              # each phase holds this much more than it is asked for
    'grid_m': 20,               # the walk is measured from points this far apart in the neighbourhoods
    'node_step_m': 25,          # routes and streets get a node at least this often
    'reach_m': 250,             # from a point in a neighbourhood to the network, at most this far ...
    'detour': 1.3,              # ... and this much longer than the straight line
    'route_buffer_m': 10,       # a route takes this much land on each side when looking for unassigned land
    'loose_end_m': 20,          # a route end farther than this from every other route, street, gateway and the boundary is loose
    'street_half_m': 8,         # a main or local route becomes a street this wide on each side (a 16 m street)
    'follows_m': 6,             # a route this close to an existing street or path runs along it
    'cover_min_m2': 5,          # a building with less than this under a route's street is touched, not covered
    'foot_share': 0.5,          # a route with more than this share of its length along foot or cycle ways runs along a path
    'crossing_m': 25,           # an existing way crossing a rail or road this close to where a route crosses it is its crossing
    'foot_highways': ['footway', 'cycleway', 'path', 'steps', 'pedestrian', 'bridleway'],   # foot or cycle only
    'barrier_highways': ['motorway', 'motorway_link', 'trunk', 'trunk_link'],            # roads crossed only off grade
    'phase_reach_m': 50,        # a centre with half its area this close to the first phase's neighbourhoods counts in it
    'phase_ratio': 0.8,         # warn when the first phase's share of land is below this times its share of homes
    'water_roles': ['water', 'rain', 'blue', 'retention', 'sponge', 'storm'],   # a role with one of these is a water role
    'low_buffer_m': 100,        # a green's ground is compared with the ground this far around it
    'low_step_m': 5,            # the ground is sampled on a grid this fine
    'low_share': 0.4,           # warn when less than this share of a water green lies below the median ground around it
    'listed': 10,               # at most this many pieces are listed under a check
    'min_piece_m2': 25,         # pieces smaller than this are left out of the lists
    'check_scale': 10000,       # scale of the check plan
    'margin_m': 60,             # the check plan shows this much around the site
    'png_dpi': 150,             # resolution of the PNG
}
C = DEFAULTS

# fallback look: black on white, greys, one accent. A drawing standard overrides it through --style.
STYLE = {'paper': '#ffffff', 'ink': '#1a1a1a', 'accent': '#c8442b', 'context': '#e4e4e4', 'park': '#c9dcbc',
         'font': 'Arial, Helvetica, sans-serif', 'thin': 0.13, 'mid': 0.25, 'thick': 0.5, 'text': 3.2, 'title': 5.6}
GREY = {'keep': 0.10, 'change': 0.18, 'new': 0.28}          # neighbourhoods: share of ink in the paper, by action
ROUTE = {'main': ('thick', None), 'local': ('mid', None), 'landscape': ('mid', (1.2, 0.8))}


def mix(c1, c2, f):
    a = [int(c1.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    return '#%02x%02x%02x' % tuple(round(x + (y - x) * f) for x, y in zip(a, b))


def ha(g):
    return g.area / 1e4


def at(g):
    p = g.representative_point()
    return f'({p.x:.0f},{p.y:.0f})'


def pieces(g):
    return sorted([q for q in parts(g) if q.area >= C['min_piece_m2']], key=lambda q: -q.area)[:C['listed']]


def read_plan(path, F):
    """The plan's features as (properties, geometry in local metres, problems)."""
    out = []
    for f in json.loads(Path(path).read_text(encoding='utf-8')).get('features') or []:
        p, raw = f.get('properties') or {}, f.get('geometry')
        g0 = shape(raw) if raw else None
        bad = []
        if g0 is None or g0.is_empty:
            bad.append('empty geometry')
        elif not g0.is_valid:
            bad.append('invalid geometry')
        out.append((p, F.local(g0) if g0 is not None and not g0.is_empty else None, bad))
    return out


def floor_area(p, g, asked):
    """The floor area a neighbourhood can hold, and the floor area its homes and commerce need, in m2."""
    cap = g.area * float(p.get('coverage') or asked['coverage']) * float(p.get('storeys') or asked['storeys'])
    return cap, (p.get('homes') or 0) * asked['m2_per_home'] + (p.get('commerce_m2') or 0)


def programme(nb, asked):
    """Each phase against what it is asked for: homes, and floor area for homes and commerce under the storey cap."""
    if not asked:
        return ['PROGRAMME', '  no F.programme(...) in design.py: nothing to check against']
    L = ['PROGRAMME' + (f" ({asked['source']})" if asked.get('source') else '')]
    sp = 1 + C['spare']
    L.append(f"  {asked['m2_per_home']} m2 per home, {asked['storeys']} storeys, coverage {asked['coverage']:.2f}; "
             f"each phase needs {C['spare']:.0%} to spare")
    phases = sorted({str(p.get('phase')) for p, g in nb if p.get('phase') is not None} | set(asked['homes']))
    for ph in phases:
        part = [(p, g) for p, g in nb if str(p.get('phase')) == ph]
        homes = sum(p.get('homes') or 0 for p, g in part)
        want = asked['homes'].get(ph, 0)
        cap = sum(floor_area(p, g, asked)[0] for p, g in part)
        need = sum(floor_area(p, g, asked)[1] for p, g in part)
        bad = [w for w, ok in (('homes', homes >= want * sp), ('floor area', cap >= need * sp)) if not ok]
        L.append(f"  phase {ph}: {homes} homes of {want} asked; floor area needed {need:,.0f} of {cap:,.0f} m2 possible "
                 f"({100 * need / cap if cap else 0:.0f} %)  " + (f"SHORT: {', '.join(bad)}" if bad else 'ok'))
    com = sum(p.get('commerce_m2') or 0 for p, g in nb)
    L.append(f"  commerce placed {com:,.0f} of {asked['commerce_m2']:,.0f} m2 asked  "
             + ('ok' if com >= asked['commerce_m2'] else 'SHORT: give the neighbourhoods commerce_m2'))
    return L


def walk(nb, ce, ro, F):
    """The share of homes within walk_m of a centre that holds the stop, along routes and streets."""
    L = [f"WALK ({C['walk_m']} m along routes and streets to a centre that holds the stop)"]
    stops = [(p, g) for p, g in ce if re.search(r'stop|station|halt|bahnhof|tram|s-bahn', str(p.get('holds', '')), re.I)]
    if not stops:
        return L + ["  no centre holds the stop: say holds='the stop, ...' on the centre at the station"]
    main = [p for p, g in stops if p.get('level') == 'main']
    L.append(f"  stop in {', '.join(p.get('name', '') for p, g in stops)}"
             + ('' if main else '  NOTE: the main centre does not hold the stop'))
    net = unary_union([g for p, g in ro] + [g for p, g in F.streets]).intersection(
        F.site.buffer(C['walk_m'] + C['reach_m']))
    G = {}
    for ln in [q for x in parts(net) for q in parts(x) if 'LineString' in q.geom_type]:
        cs = [tuple(round(v, 1) for v in c[:2]) for c in segmentize(ln, C['node_step_m']).coords]
        for a, b in zip(cs, cs[1:]):
            d = math.dist(a, b)
            G.setdefault(a, []).append((b, d))
            G.setdefault(b, []).append((a, d))
    goal = unary_union([g for p, g in stops])
    D = {n: goal.distance(Point(n)) * C['detour'] for n in G if goal.distance(Point(n)) <= C['reach_m']}
    q = [(d, n) for n, d in D.items()]
    heapq.heapify(q)
    while q:
        d, n = heapq.heappop(q)
        if d > D.get(n, 1e18) or d > C['walk_m']:
            continue
        for m, e in G[n]:
            if d + e < D.get(m, 1e18):
                D[m] = d + e
                heapq.heappush(q, (d + e, m))
    nodes = [n for n, d in D.items() if d <= C['walk_m']]
    tree = STRtree([Point(n) for n in nodes])
    near = total = 0.0
    for p, g in nb:
        if not p.get('homes'):
            continue
        x0, y0, x1, y1 = g.bounds
        s = C['grid_m']
        pts = [Point(x0 + s * (i + 0.5), y0 + s * (j + 0.5)) for i in range(int((x1 - x0) / s) + 1)
               for j in range(int((y1 - y0) / s) + 1)]
        pts = [pt for pt in pts if g.contains(pt)] or [g.representative_point()]
        ok = 0
        for pt in pts:
            if goal.distance(pt) * C['detour'] <= C['walk_m'] or any(
                    D[nodes[i]] + pt.distance(Point(nodes[i])) * C['detour'] <= C['walk_m']
                    for i in tree.query(pt.buffer(C['reach_m']))):
                ok += 1
        near += p['homes'] * ok / len(pts)
        total += p['homes']
        L.append(f"  {p.get('name', '')}: {100 * ok / len(pts):.0f} % of its homes")
    if total:
        L.append(f"  all homes within {C['walk_m']} m walk of the stop: {100 * near / total:.0f} % "
                 f"({near:,.0f} of {total:,.0f})")
    return L


def checks(feats, F, distance, proposal=None, asked=None):
    L = []
    by = lambda k: [(p, g) for p, g, b in feats if p.get('kind') == k and g is not None]
    nb, gr, ce, ro, ga = (by(k) for k in ('neighbourhood', 'green', 'centre', 'route', 'gateway'))
    w = max([len(str(p.get('name', ''))) for p, g, b in feats] + [10])
    L.append(f'site {ha(F.site):.1f} ha')
    L.append('')
    L.append('NEIGHBOURHOODS')
    for p, g in nb:
        noise = ''.join(f'  noise {k}: {ha(g.intersection(z)):.2f} ha' for k, z in sorted(F.noise.items()))
        L.append(f"  {p.get('name', ''):<{w}}  {p.get('action', ''):<6} {ha(g):7.2f} ha{noise}")
    for a in ('new', 'change', 'keep'):
        L.append(f"  total {a}: {sum(ha(g) for p, g in nb if p.get('action') == a):.2f} ha")
    for ph in sorted({str(p['phase']) for p, g in nb if p.get('phase') is not None}):
        part = [(p, g) for p, g in nb if str(p.get('phase')) == ph]
        L.append(f"  phase {ph}: {sum(p.get('homes') or 0 for p, g in part)} homes on {sum(ha(g) for p, g in part):.2f} ha")
    if any(p.get('action') in ('new', 'change') and p.get('phase') is None for p, g in nb):
        L.append('  some new or changed neighbourhoods have no phase: the homes per phase cannot be checked')
    taken = unary_union([g for p, g in nb + gr + ce] + [g.buffer(C['route_buffer_m']) for p, g in ro])
    left = F.site.difference(taken)
    L.append(f'  site assigned to nothing (not a neighbourhood, green, centre or within {C["route_buffer_m"]} m of a route): '
             f'{ha(left):.2f} ha')
    for q in pieces(left):
        L.append(f'     {ha(q):.2f} ha at {at(q)}')
    L.append('')
    L += programme(nb, asked)
    L.append('')
    L += walk(nb, ce, ro, F)
    L.append('')
    L.append('GREEN')
    for p, g in gr:
        pub = '' if p.get('public', True) is not False else '  not public'
        L.append(f"  {p.get('name', ''):<{w}}  {p.get('action', ''):<6} {ha(g):7.2f} ha  roles {p.get('roles')}{pub}")
    public = unary_union([g for p, g in gr if p.get('public', True) is not False])
    L.append(f'  total public green: {ha(public):.2f} ha')
    L.append('')
    L += low_ground(gr, F) + ['']
    L.append('CENTRES')
    for p, g in ce:
        holds = p.get('holds') or 'nothing (the massing can build nothing there)'
        L.append(f"  {p.get('name', ''):<{w}}  {p.get('level', ''):<6} {ha(g):7.2f} ha at {at(g)}  holds: {holds}")
    L.append('')
    L.append('PROXIMITY (straight line, not walking access)')
    land = unary_union([g for p, g in nb if p.get('action') in ('new', 'change')])
    near_any = unary_union([public] + [g for p, g in ce]).buffer(distance)
    near_c = unary_union([g for p, g in ce]).buffer(distance)
    if land.is_empty:
        L.append('  no new or changed neighbourhood: no share')
    else:
        for what, near in (('a public green or a centre', near_any), ('a centre', near_c)):
            L.append(f'  share of new and changed neighbourhood area within {distance:g} m of {what}: '
                     f'{100 * land.intersection(near).area / land.area:.0f} %')
        beyond = land.difference(near_any)
        L.append(f'  beyond {distance:g} m of a public green or a centre: {ha(beyond):.2f} ha')
        for q in pieces(beyond):
            L.append(f'     {ha(q):.2f} ha at {at(q)}')
    L.append('')
    L += first_phase(nb, ce, proposal, F) + ['']
    L.append('ROUTES')
    for p, g in ro:
        L.append(f"  {p.get('name', ''):<{w}}  {p.get('level', ''):<9} {g.length:7.0f} m")
    gates = unary_union([g for p, g in ga])
    streets = unary_union([g for p, g in F.streets])
    edge, inside = F.site.boundary, F.site.buffer(1)
    loose = []
    for i, (p, g) in enumerate(ro):
        others = unary_union([h for j, (q, h) in enumerate(ro) if j != i])
        for line in parts(g):
            for xy in (line.coords[0], line.coords[-1]):
                e = Point(xy)
                if not inside.contains(e):
                    continue                     # it leaves the site: it joins the city
                d = min(x.distance(e) for x in (others, streets, gates, edge) if not x.is_empty)
                if d > C['loose_end_m']:
                    loose.append(f"     {p.get('name', '')} ends at ({e.x:.0f},{e.y:.0f}), {d:.0f} m from anything")
    L.append(f"  loose ends (more than {C['loose_end_m']} m from every other route, street, gateway and the site "
             f"boundary): {len(loose)}")
    L += loose
    L += over_buildings(ro, nb, ce, gr, F)
    L += path_levels(ro, F)
    L.append('')
    L.append('GEOMETRY')
    for what in ('invalid geometry', 'empty geometry'):
        hit = [f"{p.get('kind')} {p.get('name')}" for p, g, b in feats if what in b]
        L.append(f'  {what}: {len(hit)}' + (f" ({', '.join(hit)})" if hit else ''))
    counts = {}
    for p, g, b in feats:
        counts[p.get('kind')] = counts.get(p.get('kind'), 0) + 1
    L.append(f'  features: {len(feats)} {counts}')
    return L


# ---------------------------------------------------------------- checks that warn on what later skills trip over
PHASE1 = re.compile(r'\b(phase\s*(1|one|i)\b|first\s+(construction\s+)?phase|1st\s+phase)', re.I)
HOMES = re.compile(r'\b(homes?|units?|dwellings?|apartments?|flats?)\b', re.I)


def is_first(p):
    """True when a feature says it is the first phase: a `phase` of 1, else 'phase 1' in its name or source."""
    v = p.get('phase')
    if v is not None:
        return str(v).strip().lower() in ('1', 'i', 'one', 'first', '1st', 'phase 1')
    return bool(PHASE1.search(f"{p.get('name', '')} {p.get('source', '')}"))


def numbers(text):
    """The whole numbers in a text, thousands separators read, page references and file names left out."""
    t = re.sub(r'\S+\.(md|pdf|csv)\b', ' ', str(text or ''))
    t = re.sub(r'\b(pp?|pages?)\.?\s*\d+(\s*[-–]\s*\d+)?', ' ', t, flags=re.I)
    return [int(re.sub(r'[,.\s ]', '', n)) for n in re.findall(r'\d{1,3}(?:[,. ]\d{3})+|\d+', t)]


def brief_homes(proposal, F):
    """(homes in the first phase, total homes as a list, where from), from the programme table, else the checklist."""
    if proposal:
        table = Path(proposal) / 'programme' / 'programme.csv'
        if table.exists():
            with table.open(encoding='utf-8') as fh:
                rows = list(csv.DictReader(fh))
            cols = list(rows[0]) if rows else []
            col = next((c for c in cols if HOMES.search(c or '')), None)
            if col:
                first, total = [], []
                for r in rows:
                    n, label = numbers(r.get(col)), str(r.get(cols[0]) or '')
                    if n and PHASE1.search(label):
                        first.append((n[0], r.get('source') or ''))
                    elif n and 'phase' not in label.lower():
                        total.append(n[0])
                if first and total:
                    return first[0][0], total, f"programme/programme.csv: {first[0][1]}".rstrip(': ')
    for md in ([Path(proposal) / 'brief-reader' / 'checklist.md'] if proposal else []) + \
              [F.site_dir.parent / 'brief' / 'checklist.md']:
        if not md.exists():
            continue
        first, total = None, None
        for line in md.read_text(encoding='utf-8').splitlines():
            if not HOMES.search(line):
                continue
            n = [x for x in numbers(line) if x >= 10]
            if n and first is None and PHASE1.search(line):
                first = n[0]
            elif n and total is None and 'phase' not in line.lower():
                total = n
        if first and total:
            return first, [t for t in total if t >= first] or total, f'{md.parent.name}/{md.name}'
    return None


def first_phase(nb, ce, proposal, F):
    """The first phase's share of the land against its share of the brief's homes: no density assumed."""
    L = ['FIRST PHASE (its share of the land against its share of the homes, no density assumed)']
    land = [(p, g) for p, g in nb if p.get('action') in ('new', 'change')]
    first = [(p, g) for p, g in land if is_first(p)]
    if not first:
        L.append('  no new or changed neighbourhood says it is the first phase (phase=1, or "phase 1" in its source): '
                 'not checked')
        return L
    near = unary_union([g for p, g in first]).buffer(C['phase_reach_m'])
    cen = [(p, g) for p, g in ce if is_first(p) or g.intersection(near).area >= 0.5 * g.area]
    a1 = ha(unary_union([g for p, g in first + cen]))
    a = ha(unary_union([g for p, g in land + ce]))
    share = 100 * a1 / a
    L.append(f"  first phase: {', '.join(p.get('name', '') for p, g in first)}"
             + (f"; centres {', '.join(p.get('name', '') for p, g in cen)}" if cen else '')
             + f': {a1:.2f} of {a:.2f} ha of new and changed neighbourhoods and centres = {share:.0f} % of the land')
    homes = brief_homes(proposal, F)
    if not homes:
        L.append("  the brief's homes in the first phase and in all: not found in programme/programme.csv or the "
                 'checklist: not compared')
        return L
    h1, totals, src = homes
    lo, hi = min(totals), max(totals)
    s_lo, s_hi = 100 * h1 / hi, 100 * h1 / lo
    span = f'{lo:,}' if lo == hi else f'{lo:,} to {hi:,}'
    pct = f'{s_lo:.0f}' if lo == hi else f'{s_lo:.0f} to {s_hi:.0f}'
    L.append(f'  the brief puts at least {h1:,} of {span} homes in the first phase = {pct} % of the homes ({src})')
    if share < C['phase_ratio'] * s_lo:
        even = f'{round(share / 100 * lo):,}' + ('' if lo == hi else f' to {round(share / 100 * hi):,}')
        L.append(f'  warning: the first phase has {share:.0f} % of the land for at least {s_lo:.0f} % of the homes; '
                 f'with the homes spread evenly over the land it holds about {even}, not {h1:,}: give it more land')
    return L


def describe(bp, bg, polys):
    q = bg.representative_point()
    what = next((str(bp[k]) for k in ('name', 'building', 'use') if bp.get(k) not in (None, '', 'yes', 'undefined')), '')
    where = next((f"in {p.get('kind')} {p.get('name')} ({p.get('action')})" for p, g in polys if g.contains(q)),
                 'in no plan feature')
    return f"{bp.get('id', '?')}{' ' + what if what else ''} at ({q.x:.0f},{q.y:.0f}) {where}"


def over_buildings(ro, nb, ce, gr, F):
    """Main and local routes whose street would cover an existing building the plan keeps."""
    half, foot = C['street_half_m'], C['foot_highways']
    fresh = unary_union([g for p, g in nb + ce if p.get('action') == 'new'])
    kept = [(p, g) for p, g in F.buildings
            if F.site.contains(g.representative_point()) and not fresh.contains(g.representative_point())]
    roads = unary_union([g for p, g in F.streets if p.get('highway') not in foot]).buffer(C['follows_m'])
    polys = nb + ce + gr
    L, n = [], 0
    for p, g in ro:
        if p.get('level') not in ('main', 'local'):
            continue
        own = g if roads.is_empty else g.difference(roads)
        if own.is_empty:
            continue
        band = own.buffer(half)
        hit = [(bp, bg) for bp, bg in kept if bg.intersects(band) and bg.intersection(band).area >= C['cover_min_m2']]
        if hit:
            n += 1
            more = f'; and {len(hit) - C["listed"]} more' if len(hit) > C['listed'] else ''
            L.append(f"  warning: {p.get('name', '')} ({p.get('level')}) covers {len(hit)} kept building(s): "
                     + '; '.join(describe(bp, bg, polys) for bp, bg in hit[:C['listed']]) + more)
    return [f'  main and local routes over kept buildings (as streets {2 * half:g} m wide, the parts along existing '
            f'streets left out; kept = existing in the site and not on a new neighbourhood or centre): {n}'] + L


def path_levels(ro, F):
    """Main and local routes that run along a foot or cycle way, or through a crossing that is not a street."""
    foot_cls, near_m = C['foot_highways'], C['crossing_m']
    foot = unary_union([g for p, g in F.streets if p.get('highway') in foot_cls]).buffer(C['follows_m'])
    big = unary_union([g for p, g in F.streets if p.get('highway') in C['barrier_highways']])
    barriers = []
    for what, bar, ways in (('the rail', F.rail, F.streets),
                            ('the road', big, [(p, g) for p, g in F.streets
                                               if p.get('highway') not in C['barrier_highways']])):
        if not bar.is_empty:                     # where each existing way crosses it
            barriers.append((what, bar, [(p.get('highway'), x) for p, g in ways if g.intersects(bar)
                                         for x in [g.intersection(bar)]]))
    L = []
    for p, g in ro:
        if p.get('level') not in ('main', 'local'):
            continue
        why = []
        s = 0 if foot.is_empty else g.intersection(foot).length / g.length
        if s > C['foot_share']:
            why.append(f'{100 * s:.0f} % of it runs along existing foot or cycle ways')
        for what, bar, ways in barriers:
            done = []
            for pt in parts(g.intersection(bar)):
                pt = pt.representative_point()
                if any(pt.distance(d) <= near_m for d in done):
                    continue
                done.append(pt)
                cross = [hw for hw, x in ways if x.distance(pt) <= near_m]
                if cross and all(c in foot_cls for c in cross):
                    why.append(f"it crosses {what} at ({pt.x:.0f},{pt.y:.0f}), where the only crossing is a "
                               f"{'/'.join(sorted(set(cross)))}, not a street")
        if why:
            L.append(f"  warning: {p.get('name', '')} ({p.get('level')}): {'; '.join(why)}: "
                     f"probably a landscape route, unless the brief opens it to cars")
    return [f'  main and local routes on foot or cycle ways (along them, or through a crossing that is not a '
            f'street): {len(L)}'] + L


def low_ground(gr, F):
    """For each green with a water role: how much of it lies on low ground, from the site's terrain model."""
    L = ['GREEN ON LOW GROUND (greens with a water role)']
    wet = [(p, g) for p, g in gr
           if any(k in str(r).lower() for r in (p.get('roles') or []) for k in C['water_roles'])]
    if not wet:
        L.append('  no green has a water role: not checked')
        return L
    from terrain import find_terrain
    to_ll = pyproj.Transformer.from_crs(F.epsg, 4326, always_xy=True)
    x0, y0, x1, y1 = F.site.buffer(C['low_buffer_m']).bounds
    t, notes = find_terrain(F.site_dir, (x0 + F.x0, y0 + F.y0, x1 + F.x0, y1 + F.y0), to_ll)
    if not t:
        L.append('  no terrain model in the site folder (terrain*.tif or terrain.csv): not checked'
                 + (f" ({' '.join(notes)})" if notes else ''))
        return L
    buf, step = C['low_buffer_m'], C['low_step_m']
    w = max([len(str(p.get('name', ''))) for p, g in wet] + [10])
    L.append(f'  ground from {t.source}; low ground is below the median ground within {buf:g} m of the green, '
             f'the green included')
    for p, g in wet:
        ring = g.buffer(buf)
        bx0, by0, bx1, by1 = ring.bounds
        xs, ys = np.meshgrid(np.arange(bx0, bx1, step), np.arange(by0, by1, step))
        xs, ys = xs.ravel(), ys.ravel()
        inr = shapely.contains_xy(ring, xs, ys)
        xs, ys = xs[inr], ys[inr]
        z = t.sample(xs + F.x0, ys + F.y0)
        ing = shapely.contains_xy(g, xs, ys) & ~np.isnan(z)
        if not ing.any():
            L.append(f"  {p.get('name', ''):<{w}}  no ground under it")
            continue
        med = float(np.nanmedian(z))
        share = float((z[ing] < med).mean())
        warn = (f'  warning: it lies mostly above the ground around it, so little rain runs into it'
                if share < C['low_share'] else '')
        L.append(f"  {p.get('name', ''):<{w}}  {100 * share:3.0f} % on low ground  (its median {np.median(z[ing]):.1f} m, "
                 f'around it {med:.1f} m){warn}')
    return L


# ---------------------------------------------------------------- the check plan
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


def shot(svg, png, w_mm, h_mm):
    """A PNG of the SVG by a headless Chrome or Edge. Returns a note when it could not be made."""
    browser = find_browser()
    if not browser:
        return 'No Chrome or Edge found: no PNG made.'
    w, h = round(w_mm / 25.4 * C['png_dpi']), round(h_mm / 25.4 * C['png_dpi'])
    page = svg.with_name(svg.stem + '_wrap.html')
    page.write_text(f'<html><body style="margin:0"><img src="{svg.name}" style="width:{w}px;height:{h}px"></body></html>',
                    encoding='utf-8')
    if png.exists():
        png.unlink()
    subprocess.run([browser, '--headless', '--disable-gpu', '--hide-scrollbars', f'--screenshot={png.resolve()}',
                    f'--window-size={w},{h}', page.resolve().as_uri()], capture_output=True, timeout=180)
    page.unlink()
    return None if png.exists() else f'{png.name} was not made: the browser failed.'


def draw(feats, F, S, out_dir):
    k = 1000 / C['check_scale']                         # mm per metre
    fs = max(3.2, float(S.get('text', 3.2)))
    ft = max(fs, float(S.get('title', fs * 1.6)))
    thin, mid, thick = (float(S.get(n, d)) for n, d in (('thin', 0.13), ('mid', 0.25), ('thick', 0.5)))
    lw = {'thin': thin, 'mid': mid, 'thick': thick}
    ink, paper, accent = S['ink'], S['paper'], S['accent']
    x0, y0, x1, y1 = F.site.buffer(C['margin_m']).bounds
    pad = 8.0
    W = (x1 - x0) * k + 2 * pad
    Hm = (y1 - y0) * k + 2 * pad
    X = lambda x: pad + (x - x0) * k
    Y = lambda y: pad + (y1 - y) * k
    esc = lambda s: html.escape(str(s), quote=True)
    tw = lambda s, size=fs: len(str(s)) * size * 0.56

    def path(g):
        d = []
        for q in parts(g):
            if q.geom_type == 'Polygon':
                for ring in [q.exterior, *q.interiors]:
                    d.append('M' + 'L'.join(f'{X(x):.2f},{Y(y):.2f}' for x, y in ring.coords) + 'Z')
            elif 'LineString' in q.geom_type:
                for ln in parts(q):
                    d.append('M' + 'L'.join(f'{X(x):.2f},{Y(y):.2f}' for x, y in ln.coords))
        return ''.join(d)

    def text(x, y, s, size=fs, anchor='start', weight=None, halo=False):
        wt = f' font-weight="{weight}"' if weight else ''
        h = f' stroke="{paper}" stroke-width="{size * 0.25:.2f}" paint-order="stroke"' if halo else ''
        return (f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size:.2f}" text-anchor="{anchor}" fill="{ink}"{wt}{h}>'
                f'{esc(s)}</text>')

    by = lambda kd: [(p, g) for p, g, b in feats if p.get('kind') == kd and g is not None]
    o = [f'<g clip-path="url(#map)">']
    view = F.box(x0, y0, x1, y1)
    ctx = unary_union([g for p, g in F.buildings if g.intersects(view)])
    if not ctx.is_empty:
        o.append(f'<path d="{path(ctx)}" fill="{S.get("context", "#e4e4e4")}" fill-rule="evenodd"/>')
    for p, g in by('neighbourhood'):
        o.append(f'<path d="{path(g)}" fill="{mix(paper, ink, GREY.get(p.get("action"), 0.18))}" fill-opacity="0.85" '
                 f'fill-rule="evenodd" stroke="{ink}" stroke-width="{thin}"/>')
    for p, g in by('green'):
        o.append(f'<path d="{path(g)}" fill="{S.get("park", "#c9dcbc")}" fill-rule="evenodd" stroke="{ink}" '
                 f'stroke-width="{thin}"/>')
    for p, g in by('centre'):
        o.append(f'<path d="{path(g)}" fill="{accent}" fill-opacity="0.8" fill-rule="evenodd" stroke="{accent}" '
                 f'stroke-width="{mid}"/>')
    for p, g in by('route'):
        wd, dash = ROUTE.get(p.get('level'), ('mid', None))
        da = f' stroke-dasharray="{dash[0]} {dash[1]}"' if dash else ''
        o.append(f'<path d="{path(g)}" fill="none" stroke="{ink}" stroke-width="{lw[wd] * 2:.2f}"{da}/>')
    o.append(f'<path d="{path(F.site.boundary)}" fill="none" stroke="{ink}" stroke-width="{mid}" '
             f'stroke-dasharray="3 1.5"/>')
    for p, g in by('gateway'):
        o.append(f'<circle cx="{X(g.x):.2f}" cy="{Y(g.y):.2f}" r="1.6" fill="{paper}" stroke="{accent}" '
                 f'stroke-width="{thick}"/>')
    for kd in ('neighbourhood', 'green', 'centre'):
        for p, g in by(kd):
            q = g.representative_point()
            o.append(text(X(q.x), Y(q.y) + fs * 0.35, p.get('name', ''), anchor='middle', halo=True,
                          weight='bold' if kd == 'centre' else None))
    o.append('</g>')

    # the strip under the map: title, north, scale bar, legend
    s = []
    y = Hm + 2 + ft
    s.append(text(pad, y, f"Structure plan, check plan 1:{C['check_scale']:,}", ft, weight='bold'))
    r = 4.0
    nx, ny = W - pad - r, Hm + 2 + r
    c = F.site.centroid
    lon, lat = F.to_wgs(c).coords[0]
    ux, uy = F.to_local(lon, lat + 0.01)
    a = math.atan2(ux - c.x, uy - c.y)
    s.append(f'<circle cx="{nx:.2f}" cy="{ny:.2f}" r="{r}" fill="none" stroke="{ink}" stroke-width="{thin}"/>'
             f'<path d="M{nx:.2f},{ny:.2f}L{nx + r * math.sin(a):.2f},{ny - r * math.cos(a):.2f}" stroke="{ink}" '
             f'stroke-width="{thin * 2:.2f}"/>')
    # scale bar: one thin line stepping up and down, a tick at every step, numbers under, the unit on the last
    total, n = 500, 5
    seg, hstep = total / n * k, 1.5
    sy = y + 6 + hstep
    pts = []
    for i in range(n):
        yy = sy - (hstep if i % 2 else 0)
        pts += [(pad + i * seg, yy), (pad + (i + 1) * seg, yy)]
    s.append('<path d="M' + 'L'.join(f'{px:.2f},{py:.2f}' for px, py in pts) + f'" fill="none" stroke="{ink}" '
             f'stroke-width="{thin}"/>')
    for i in range(n + 1):
        px = pad + i * seg
        s.append(f'<path d="M{px:.2f},{sy - hstep:.2f}L{px:.2f},{sy + 1.2:.2f}" stroke="{ink}" stroke-width="{thin}"/>')
        if i % 2 == 0 or i == n:
            s.append(text(px, sy + 1.2 + fs, f'{i * total / n:g}' + (' m' if i == n else ''), anchor='middle'))
    # legend
    items = [('fill', mix(paper, ink, GREY[a_]), f'neighbourhood, {a_}') for a_ in ('keep', 'change', 'new')]
    items += [('fill', S.get('park', '#c9dcbc'), 'green'), ('fill', accent, 'centre'),
              ('line', 'thick', 'main route'), ('line', 'mid', 'local route'), ('dash', 'mid', 'landscape route'),
              ('dot', accent, 'gateway'), ('site', 'mid', 'site')]
    lx, ly = pad, sy + 1.2 + fs + 4 + fs
    for kind_, val, lab in items:
        wi = 7.5 + tw(lab) + 5
        if lx + wi > W - pad and lx > pad:
            lx, ly = pad, ly + fs + 3
        top = ly - fs * 0.85
        if kind_ == 'fill':
            s.append(f'<rect x="{lx:.2f}" y="{top:.2f}" width="6" height="3.5" fill="{val}" stroke="{ink}" '
                     f'stroke-width="{thin}"/>')
        elif kind_ == 'dot':
            s.append(f'<circle cx="{lx + 3:.2f}" cy="{top + 1.75:.2f}" r="1.6" fill="{paper}" stroke="{val}" '
                     f'stroke-width="{thick}"/>')
        else:
            da = {'dash': ' stroke-dasharray="1.2 0.8"', 'site': ' stroke-dasharray="3 1.5"'}.get(kind_, '')
            sw = lw[val] * (1 if kind_ == 'site' else 2)
            s.append(f'<path d="M{lx:.2f},{top + 1.75:.2f}h6" stroke="{ink}" stroke-width="{sw:.2f}"{da}/>')
        s.append(text(lx + 7.5, ly, lab))
        lx += wi
    H = ly + pad
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" height="{H:.1f}mm" viewBox="0 0 {W:.2f} {H:.2f}" '
           f'font-family="{esc(S.get("font", "Arial, Helvetica, sans-serif"))}">',
           f'<defs><clipPath id="map"><rect x="{pad}" y="{pad}" width="{W - 2 * pad:.2f}" height="{Hm - 2 * pad:.2f}"/>'
           f'</clipPath></defs>',
           f'<rect width="{W:.2f}" height="{H:.2f}" fill="{paper}"/>', *o, *s, '</svg>']
    out = out_dir / 'check-plan.svg'
    out.write_text('\n'.join(svg), encoding='utf-8')
    return shot(out, out_dir / 'check-plan.png', W, H)


def run(proposal, F, distance=None, style_path=None):
    """Writes checks.txt and the check plan for the proposal's structure plan; returns the checks as text."""
    out = Path(proposal) / 'structure-plan'
    plan = out / 'structure-plan.geojson'
    if not plan.exists():
        raise SystemExit(f'no structure-plan.geojson in {out}: run build.py first')
    distance = C['distance_m'] if distance is None else distance
    feats = read_plan(plan, F)
    asked = json.loads(plan.read_text(encoding='utf-8')).get('programme')
    L = checks(feats, F, distance, proposal, asked)
    style_path = Path(style_path) if style_path else Path(proposal) / 'drawing-graphics' / 'style.json'
    S = dict(STYLE)
    if style_path.exists():
        S.update(json.loads(style_path.read_text(encoding='utf-8')))
    note = draw(feats, F, S, out)
    L.append('')
    L.append('check plan: check-plan.svg' + (f' ({note})' if note else ' and check-plan.png')
             + (f', look from {style_path.name}' if style_path.exists() else ', fallback look'))
    L.append('coordinates: metres from the south-west corner of the site, in its UTM zone')
    if F.missing:
        L.append('missing: ' + ', '.join(F.missing))
    text = '\n'.join(L) + '\n'
    (out / 'checks.txt').write_text(text, encoding='utf-8')
    return text


def climate_of(proposal, climate):
    if climate:
        return climate
    c = Path(proposal) / 'climate'
    return c if (c / 'rules.geojson').exists() else None


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='The checks of a structure plan, and a check plan.')
    ap.add_argument('--proposal', required=True)
    ap.add_argument('--site', required=True, help='the folder with site.geojson and its layers')
    ap.add_argument('--climate', help="the climate folder with rules.geojson (default: the proposal's climate/)")
    ap.add_argument('--distance', type=float, default=C['distance_m'], help='proximity distance, m')
    ap.add_argument('--style', help="the drawing standard's style.json (default: the proposal's drawing-graphics/)")
    A = ap.parse_args()
    print(run(A.proposal, Frame(A.site, climate_of(A.proposal, A.climate)), A.distance, A.style))
