"""A small made-up project to check phasing.py and draw.py on: a square site, two neighbourhoods, a few buildings
(one mixed with a daycare, one with no phase, one that stays, optionally one invalid), streets with a dead end, a
garden whose path is the only way to one house, one stop, and a car link the mobility config forbids.

    python make_example.py <out folder> [--invalid] [--no-daycare-in-phase-1] [--crs EPSG:25832]
                           [--late-garden] [--undecided-stop] [--existing-residents N]

Writes <out>/site/site.geojson and <out>/proposal/ with massing, structure plan, streets, mobility, programme,
a drawing style and a filled phasing/config.json and decisions.json. The place is made up. Needs shapely and pyproj.
"""
import argparse, csv, json
from pathlib import Path

import pyproj
from shapely.geometry import box, Polygon, LineString, Point, mapping
from shapely.ops import transform

LON, LAT, EPSG = 9.5, 50.5, 32632          # a made-up spot in UTM zone 32N
TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
TO_LL = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform
X0, Y0 = TO_M(LON, LAT)
STYLE = {"source": "example", "paper": "#ffffff", "background": "#ffffff", "ink": "#1a1a1a", "accent": "#c8442b", "new": "#c8442b",
         "existing": "#cfcfcf", "context": "#e4e4e4", "building": "#9a9a9a", "street": "#f2f2f2", "path": "#bcbcbc",
         "park": "#c9dcbc", "water": "#9ec5d8", "ramp": ["#f3f1ec", "#e3d6bf", "#cfae85", "#b07d52", "#7a4a2c"],
         "font": "Arial, sans-serif", "thin": 0.13, "mid": 0.25, "thick": 0.5, "text": 3.2, "title": 5.6}


def m(x, y):
    return (X0 + x, Y0 + y)


def rect(x, y, w, h):
    return box(*m(x, y), *m(x + w, y + h))


def fc(feats, crs=None):
    out = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': p, 'geometry': mapping(g)} for p, g in feats]}
    if crs:
        out['crs'] = {'type': 'name', 'properties': {'name': crs}}
    return out


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--invalid', action='store_true')
    ap.add_argument('--no-daycare-in-phase-1', action='store_true')
    ap.add_argument('--crs', help='write massing.geojson in this CRS instead of WGS84, to check the IDs')
    ap.add_argument('--late-garden', action='store_true', help='the garden (and its path) is decided for phase 2')
    ap.add_argument('--undecided-stop', action='store_true', help='no phase decided for the stop')
    ap.add_argument('--existing-residents', type=float, help='the residents of the building that stays; else "not stated"')
    a = ap.parse_args()
    out = Path(a.out)
    P = out / 'proposal'
    ll = lambda g: transform(TO_LL, g)

    site = rect(0, 0, 400, 200)
    write(out / 'site/site.geojson', fc([({'kind': 'site'}, ll(site))]))

    n1, n2 = rect(10, 10, 180, 180), rect(210, 10, 120, 180)       # 330..400 belongs to no neighbourhood
    sp = [({'kind': 'neighbourhood', 'name': 'West', 'phase': 1, 'action': 'new', 'basis': 'hypothesis'}, n1),
          ({'kind': 'neighbourhood', 'name': 'East', 'phase': 2, 'action': 'new', 'basis': 'hypothesis'}, n2),
          ({'kind': 'centre', 'name': 'Square', 'level': 'main', 'holds': 'daycare, shops'}, rect(80, 80, 30, 30)),
          ({'kind': 'gateway', 'name': 'West gate'}, Point(m(-5, 100))),
          ({'kind': 'gateway', 'name': 'East gate'}, Point(m(400, 100)))]
    write(P / 'structure-plan/structure-plan.geojson', fc([(p, ll(g)) for p, g in sp]))

    day1 = 'housing' if a.no_daycare_in_phase_1 else 'mixed + daycare'
    B = [  # (props, footprint in metres)
        ({'use': 'housing', 'floors': 4, 'neighbourhood': 'West', 'phase': 1}, rect(30, 110, 40, 12)),
        ({'use': day1, 'floors': 4, 'neighbourhood': 'West', 'daycare_floors': 1 if day1.endswith('daycare') else None}, rect(120, 110, 40, 12)),
        ({'use': 'housing + daycare', 'floors': 3, 'neighbourhood': 'East', 'daycare_floors': 1}, rect(250, 110, 40, 12)),
        ({'use': 'housing', 'floors': 3, 'neighbourhood': 'unplanned'}, rect(345, 110, 30, 12)),
        ({'use': 'housing', 'floors': 2, 'existing': True, 'osm_id': 'w1'}, rect(2, 30, 15, 10)),     # stays, by the edge road
        # reached only by the garden's path
        ({'use': 'housing', 'floors': 2, 'neighbourhood': 'West', 'phase': 1}, rect(75, 162, 20, 10)),
    ]
    if a.invalid:
        # a bowtie with uneven halves: it crosses itself
        B.append(({'use': 'housing', 'floors': 3, 'neighbourhood': 'East'},
                  Polygon([m(250, 40), m(290, 70), m(290, 40), m(250, 80)])))
    feats, homes_m2 = [], 0.0
    for p, g in B:
        p = {k: v for k, v in p.items() if v is not None}
        p.setdefault('existing', False)
        if not p['existing']:
            fl = p['floors']
            hf = fl if p['use'] == 'housing' else fl - 1 if p['use'] == 'mixed' else \
                max(0, fl - p.get('daycare_floors', 0) - (1 if p['use'].startswith('mixed') else 0)) if p['use'].endswith('daycare') else 0
            if g.is_valid:
                homes_m2 += g.area * hf
            p.update(footprint_m2=round(g.area), gfa_m2=round(g.area * fl), height_m=fl * 3.0, type='row')
        feats.append(({'kind': 'building', **p}, g))
    feats.append(({'kind': 'street', 'width': 5, 'level': 'local', 'name': 'Main'}, LineString([m(0, 100), m(300, 100)])))
    feats.append(({'kind': 'open-space', 'use': 'park', 'name': 'Green'}, rect(20, 140, 60, 40)))
    if a.crs:
        tr = pyproj.Transformer.from_crs(EPSG, pyproj.CRS.from_user_input(a.crs), always_xy=True).transform
        mass = fc([(p, transform(tr, g)) for p, g in feats], a.crs)
        mass['note'] = 'example; areas measured in EPSG:%d' % EPSG
    else:
        mass = fc([(p, ll(g)) for p, g in feats])
        mass['note'] = 'WGS84, longitude first; areas measured in EPSG:%d' % EPSG
    write(P / 'massing/massing.geojson', mass)
    write(P / 'massing/config.json', {'m2_per_home': {'value': 80, 'source': 'example'}})
    with (P / 'massing/areas.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['use', 'programme_m2', 'design_m2', 'difference_m2', 'source'])
        w.writerow(['homes (count)', 20, round(homes_m2 / 80), round(homes_m2 / 80) - 20, 'example'])

    streets = [({'kind': 'centreline', 'level': 'main', 'width': 7.0, 'width_source': 'example', 'name': 'Edge Road',
                 'existing': True, 'source': 'osm'}, LineString([m(-5, -50), m(-5, 250)])),
               ({'kind': 'centreline', 'level': 'local', 'width': 5.0, 'width_source': 'massing', 'name': 'Main',
                 'existing': False, 'source': 'massing'}, LineString([m(-5, 100), m(200, 100)])),
               # the dead end into the east: needed only by phase 2
               ({'kind': 'centreline', 'level': 'local', 'width': 5.0, 'width_source': 'massing', 'name': 'Main east',
                 'existing': False, 'source': 'massing'}, LineString([m(200, 100), m(400, 100)]))]
    write(P / 'streets/streets.geojson', fc([(p, ll(g)) for p, g in streets]))
    write(P / 'mobility/mobility.geojson', fc([({'kind': 'stop', 'name': 'Stop A', 'mode': 'bus', 'main': True}, ll(Point(m(-10, 95))))]))
    write(P / 'mobility/config.json', {'no_car_link': {'value': [['West gate', 'East gate']], 'source': 'example: no through traffic'}})
    write(P / 'open-space/open-space.geojson', fc([
        ({'kind': 'open-space', 'use': 'park', 'name': 'Garden', 'existing': False}, ll(rect(20, 125, 70, 30))),
        ({'kind': 'path', 'width_m': 3.0}, ll(LineString([m(85, 100), m(85, 160)])))]))
    (P / 'programme').mkdir(parents=True, exist_ok=True)
    (P / 'programme/programme.csv').write_text('use,area_m2,plot_m2,homes,residents,source\nhousing,,,100,210,example\n', encoding='utf-8')
    write(P / 'drawing-graphics/style.json', STYLE)
    cfg = {
        'phase_count': {'value': 2, 'source': 'example'},
        'first_phase': {'value': ['West'], 'source': 'example'},
        'm2_per_home': {'value': 80, 'source': 'example'},
        'residents_per_home': {'value': 2.1, 'source': 'example'},
        'requirements': {'value': [
            {'phase': 1, 'measure': 'homes', 'op': '>=', 'value': 1, 'source': 'example'},
            {'phase': 'each', 'measure': 'access', 'op': '>=', 'value': 1.0, 'source': 'example'},
            {'phase': 1, 'measure': 'walk:daycare', 'op': '>=', 'value': 1.0, 'source': 'example'},
            {'phase': 1, 'measure': 'facility:daycare', 'op': '>=', 'value': 1, 'source': 'example'},
            {'phase': 'all', 'measure': 'emergency', 'op': '>=', 'value': 1.0, 'source': 'example'},
            {'phase': 1, 'measure': 'a lively first phase', 'op': '>=', 'value': 1, 'source': 'example'}],
            'source': 'example'},
        'facility_words': {'value': {'daycare': ['daycare']}, 'source': 'example'},
        'services': {'value': [
            {'name': 'daycare', 'facility': 'daycare', 'walk_m': 500, 'by_phase': 1, 'places_per_provider': None,
             'places_per_resident': None, 'source': 'example'},
            {'name': 'stop', 'facility': 'stop', 'walk_m': 400, 'by_phase': 1, 'source': 'example'}], 'source': 'example'},
        'open_space_uses': {'value': ['park'], 'source': 'example'},
        'open_space_per_resident_m2': {'value': 10, 'source': 'example'},
        'existing_residents': {'value': 'not stated' if a.existing_residents is None else a.existing_residents,
                               'source': 'example' if a.existing_residents is not None else 'example: the brief says nothing'},
        'emergency': {'value': 'not stated', 'source': 'example: neither the brief nor a cited regulation'},
        'entrance_max_m': {'value': 20, 'source': 'example'},
        'snap_m': {'value': 2, 'source': 'example'},
        'near_site_m': {'value': 500, 'source': 'example'},
        'scale_large': {'value': 1000, 'source': 'example'},
        'scale_small': {'value': 2500, 'source': 'example'},
    }
    write(P / 'phasing/config.json', cfg)
    write(P / 'phasing/decisions.json', {
        'buildings': [],
        'stops': [] if a.undecided_stop else [{'name': 'Stop A', 'phase': 0, 'source': 'example: exists today'}],
        'open_spaces': [{'name': 'Garden', 'phase': 2, 'reason': 'example: built with the east'}] if a.late_garden else [],
        'services_outside': [], 'closures': []})
    print(P)


if __name__ == '__main__':
    main()
