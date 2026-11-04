"""Reconcile the structure plan's construction phases with the massing's buildings.

    python phases.py --proposal <proposal folder> --config <proposal>/phasing/config.json

Each new building takes its phase from `phase_of` in the config, else from the structure plan's neighbourhood or
centre it belongs to (by its `neighbourhood` name, else by where it stands), else from its own `phase` in the
massing. Its homes are its own `homes`, else its housing floor area / `m2_per_home` (mixed buildings: the ground
floor is not homes; daycare floors are not homes). Writes phases.csv, phases.geojson and stats.json into
<proposal>/phasing/ and prints stats.json, nothing else.
"""
import argparse, csv, json, sys
from collections import defaultdict
from pathlib import Path
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from pyproj import Geod

REQUIRED = ['m2_per_home', 'residents_per_home']
DEFAULTS = {'min_homes': {}, 'first': [], 'phase_of': {}}
NOT_HOMES = ('housing', 'mixed', 'commerce', 'homes', 'residential')
GEOD = Geod(ellps='WGS84')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def config(path):
    raw = load(path)
    cfg, src = dict(DEFAULTS), {}
    for k, v in raw.items():
        val = v.get('value') if isinstance(v, dict) and 'value' in v else v
        if val is not None:
            cfg[k] = val
        src[k] = v.get('source', '') if isinstance(v, dict) else ''
    for k in REQUIRED:
        if cfg.get(k) in (None, '', 0):
            sys.exit('phasing config: %s is empty; fill it from the brief or the massing, with its source' % k)
    return cfg, src


def key(phase):
    """A phase as a string: 1, 1.0 and '1' are the same phase."""
    if phase is None or phase == '':
        return None
    if isinstance(phase, float) and phase.is_integer():
        phase = int(phase)
    return str(phase).strip()


def order(k):
    try:
        return (0, float(k), k)
    except ValueError:
        return (1, 0.0, k)


def homes_of(p, geom, m2_per_home):
    if p.get('homes') is not None:
        return float(p['homes'])
    use = (p.get('use') or '').lower()
    if not use.startswith(('housing', 'mixed', 'homes', 'residential')):
        return 0.0
    floors = p.get('floors') or 0
    non = p.get('daycare_floors') or 0
    gf = (p.get('ground_floor') or '').lower()
    if use.startswith('mixed') or (gf and not gf.startswith(('housing', 'homes', 'residential'))):
        non += 1
    area = p.get('footprint_m2') or abs(GEOD.geometry_area_perimeter(geom)[0])
    return max(0.0, area * (floors - non)) / m2_per_home


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proposal', required=True)
    ap.add_argument('--config', required=True)
    a = ap.parse_args()
    prop = Path(a.proposal)
    cfg, src = config(a.config)
    out = prop / 'phasing'
    out.mkdir(parents=True, exist_ok=True)
    m2, rpp = float(cfg['m2_per_home']), float(cfg['residents_per_home'])
    override = {n: key(v) for n, v in cfg['phase_of'].items()}

    # the structure plan's neighbourhoods and centres, with their phase, planned homes and what they hold
    sp_path = prop / 'structure-plan/structure-plan.geojson'
    places = []
    if sp_path.exists():
        for f in load(sp_path)['features']:
            p = f['properties']
            if p.get('kind') not in ('neighbourhood', 'centre') or not f.get('geometry'):
                continue
            ph = override.get(p.get('name'), key(p.get('phase')))
            places.append(dict(name=p.get('name'), kind=p['kind'], level=p.get('level'), phase=ph, geom=shape(f['geometry']),
                               homes=p.get('homes') if isinstance(p.get('homes'), (int, float)) else None,
                               holds=p.get('holds') or '', new=p.get('action') != 'keep'))
    by_name = {pl['name']: pl for pl in places}

    # every new building, its phase and its homes
    m_path = prop / 'massing/massing.geojson'
    if not m_path.exists():
        sys.exit('phasing: no massing/massing.geojson in %s' % prop)
    blds, moved = [], defaultdict(lambda: defaultdict(int))
    for f in load(m_path)['features']:
        p = f['properties']
        if p.get('kind') != 'building' or p.get('existing') or not f.get('geometry'):
            continue
        g = shape(f['geometry'])
        nb, own = p.get('neighbourhood'), key(p.get('phase'))
        place = by_name.get(nb)
        if place is None:
            inside = [pl for pl in places if pl['phase'] and pl['geom'].contains(g.representative_point())]
            place = min(inside, key=lambda pl: pl['geom'].area) if inside else None
        if nb in override:
            ph, how = override[nb], 'config'
        elif place and place['phase']:
            ph, how = place['phase'], 'structure plan'
        else:
            ph, how = own, 'massing' if own else 'none'
        if own and ph and own != ph:
            moved[nb or '?'][(own, ph)] += 1
        blds.append(dict(geom=g, phase=ph, how=how, own=own, use=p.get('use') or '', nb=nb or (place or {}).get('name'),
                         homes=homes_of(p, g, m2)))

    phases = sorted({b['phase'] for b in blds if b['phase']} | {pl['phase'] for pl in places if pl['phase']}, key=order)
    rank = {ph: i for i, ph in enumerate(phases)}
    homes, planned, nbs = defaultdict(float), defaultdict(float), defaultdict(list)
    for b in blds:
        homes[b['phase']] += b['homes']
    for pl in places:
        if pl['phase'] and pl['homes'] is not None:
            planned[pl['phase']] += pl['homes']
        if pl['phase'] and pl['kind'] == 'neighbourhood' and pl['new']:
            nbs[pl['phase']].append(pl['name'])

    def comes_first(ph):
        centres = ['%s (%s)' % (pl['name'], pl['level']) if pl['level'] else pl['name']
                   for pl in places if pl['kind'] == 'centre' and pl['phase'] == ph]
        uses = []
        for b in blds:
            for u in b['use'].split('+'):
                u = u.strip()
                if b['phase'] == ph and u and not u.lower().startswith(NOT_HOMES) and u not in uses:
                    uses.append(u)
        return '; '.join(x for x in (', '.join(centres), ', '.join(uses)) if x)

    flags, rows, table = [], [], {}
    for ph in phases:
        h, plan = round(homes[ph]), round(planned[ph]) if ph in planned else None
        diff = h - plan if plan is not None else None
        mn = cfg['min_homes'].get(ph)
        table[ph] = dict(homes=h, residents=round(homes[ph] * rpp), homes_planned=plan, difference=diff,
                         homes_minimum=mn, neighbourhoods=nbs[ph], first=comes_first(ph))
        if plan and diff:
            flags.append('phase %s: the massing builds %d homes, the structure plan planned %d (%+d)' % (ph, h, plan, diff))
        if mn is not None and h < mn:
            flags.append('phase %s: %d homes, below the minimum of %d (%s)' % (ph, h, mn, src.get('min_homes', '')))
    for nb, pairs in moved.items():
        for (own, ph), n in pairs.items():
            flags.append('%s: %d buildings are phase %s in the massing, phase %s here' % (nb, n, own, ph))
    loose = [b for b in blds if not b['phase'] and b['homes'] > 0]
    if loose:
        flags.append('%d new buildings with %d homes have no phase' % (len(loose), round(sum(b['homes'] for b in loose))))
    for item in cfg['first']:
        what, by = str(item.get('what', '')).lower(), key(item.get('phase'))
        if not what:
            continue
        early = {ph for ph in phases if by in rank and rank[ph] <= rank[by]}
        found = any(b['phase'] in early and what in b['use'].lower() for b in blds) or \
            any(pl['phase'] in early and (what in pl['holds'].lower() or what in (pl['name'] or '').lower()) for pl in places)
        if not found:
            flags.append('%s is not in phase %s or earlier (%s)' % (item.get('what'), by, src.get('first', '')))
    total = round(sum(b['homes'] for b in blds))
    stats_path = prop / 'massing/stats.json'
    m_total = load(stats_path).get('homes') if stats_path.exists() else None
    if m_total and abs(total - m_total) > 0.01 * m_total:
        flags.append('all phases hold %d homes, the massing counts %d: m2_per_home differs from the massing\'s?' % (total, m_total))

    source = 'massing.geojson, housing floor area / %g m2 per home; residents x %g per home; planned: structure-plan.geojson; '         'sources in phasing/config.json' % (m2, rpp)
    cols = ['phase', 'homes', 'residents', 'homes_planned', 'difference', 'homes_minimum', 'neighbourhoods', 'first', 'source']
    with open(out / 'phases.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for ph, t in table.items():
            w.writerow([ph, t['homes'], t['residents'], t['homes_planned'], t['difference'], t['homes_minimum'],
                        ', '.join(t['neighbourhoods']), t['first'], source])
        if loose:
            lh = sum(b['homes'] for b in loose)
            w.writerow(['none', round(lh), round(lh * rpp), '', '', '', '', '', source])
        tp = sum(planned.values())
        w.writerow(['total', total, round(total * rpp), round(tp) if planned else '', total - round(tp) if planned else '',
                    '', '', '', source])

    feats = []
    for ph, t in table.items():
        shapes = [pl['geom'] for pl in places if pl['phase'] == ph] or [b['geom'] for b in blds if b['phase'] == ph]
        feats.append({'type': 'Feature', 'geometry': mapping(unary_union(shapes)),
                      'properties': {'kind': 'phase', 'phase': ph, 'order': rank[ph] + 1, **t, 'source': source}})
    for b in blds:
        pr = {'kind': 'building', 'phase': b['phase'], 'homes': round(b['homes'], 1), 'use': b['use'],
              'neighbourhood': b['nb'], 'phase_source': b['how']}
        if b['own'] and b['own'] != b['phase']:
            pr['massing_phase'] = b['own']
        feats.append({'type': 'Feature', 'geometry': mapping(b['geom']), 'properties': pr})
    (out / 'phases.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': feats}), encoding='utf-8')

    per_nb = defaultdict(float)
    for b in blds:
        per_nb[b['nb']] += b['homes']
    gaps = [dict(name=pl['name'], phase=pl['phase'], homes=round(per_nb.get(pl['name'], 0)), homes_planned=pl['homes'],
                 difference=round(per_nb.get(pl['name'], 0)) - pl['homes'])
            for pl in places if pl['kind'] == 'neighbourhood' and pl['homes']]
    stats = dict(phases=table, homes=total, residents=round(total * rpp), homes_planned=round(sum(planned.values())),
                 homes_massing=m_total, flags=flags, neighbourhoods=sorted(gaps, key=lambda g: -abs(g['difference'])),
                 source=source)
    (out / 'stats.json').write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == '__main__':
    main()
