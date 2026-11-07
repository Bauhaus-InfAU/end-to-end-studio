"""phasing.py and draw.py on the made-up example. Run with pytest; skipped without shapely, pyproj and networkx.
The drawing check is skipped without Chrome, Edge or Chromium."""
import csv, json, subprocess, sys
from pathlib import Path

import pytest
from conftest import REPO

for mod in ('shapely', 'pyproj', 'networkx'):
    pytest.importorskip(mod)

HERE = REPO / 'plugins/design/skills/phasing/scripts'


def run(*args):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r


def project(tmp, *flags):
    run(HERE / 'example/make_example.py', tmp, *flags)
    P = Path(tmp) / 'proposal'
    run(HERE / 'phasing.py', '--proposal', P, '--site', Path(tmp) / 'site', '--config', P / 'phasing/config.json')
    return P


def rows(P, name):
    return list(csv.DictReader((P / 'phasing' / name).open(encoding='utf-8')))


def buildings(P):
    fc = json.loads((P / 'phasing/phasing.geojson').read_text(encoding='utf-8'))
    return [f['properties'] for f in fc['features'] if f['properties']['kind'] == 'building']


def test_valid_example(tmp_path):
    P = project(tmp_path)
    st = json.loads((P / 'phasing/stage-stats.json').read_text(encoding='utf-8'))
    assert st['homes_check'].startswith('matches')
    assert st['buildings_total'] == sum(st['buildings_by_basis'].values()) == 6
    bs = buildings(P)
    review = [b for b in bs if b['basis'] == 'review']
    assert len(review) == 1 and review[0]['phase'] is None and st['buildings_flagged_for_review'] == 1
    assert [r['id'] for r in rows(P, 'evidence.csv')] == [review[0]['id']]
    fc = json.loads((P / 'phasing/phasing.geojson').read_text(encoding='utf-8'))
    streets = [f['properties'] for f in fc['features'] if f['properties']['kind'] == 'street' and not f['properties']['existing']]
    assert sorted({s['phase'] for s in streets}) == [1, 2], 'the dead end into the east comes with phase 2'
    acc = rows(P, 'access.csv')
    assert not [r for r in acc if r['stage'] == '1' and r['phase'] != '0'], 'nothing new works while phase 1 is built'
    assert all(r['connected'] == 'yes' for r in acc if r['stage'] == '2')
    assert all(r['emergency'] == 'not stated / not measured' for r in acc)
    ch = rows(P, 'checks.csv')
    assert any(r['requirement'] == 'emergency' and r['verdict'] == 'not stated / not measured' for r in ch)
    assert any(r['requirement'] == 'a lively first phase' and r['verdict'] == 'for Claude to judge' for r in ch)
    d = json.loads((P / 'phasing/decisions.json').read_text(encoding='utf-8'))
    assert d['epsg'] == st['epsg'] and d['massing_fingerprint'] == st['massing_fingerprint']


UNDECIDED = 'not measured: stop phase not decided'
EXIST_UNKNOWN = 'not measured: existing residents unknown'


def test_forbidden_car_link(tmp_path):
    # the west and east gates are joined by cars only once the east street is built, with phase 2
    P = project(tmp_path)
    ch = {r['stage']: r for r in rows(P, 'checks.csv') if r['requirement'] == 'no car link West gate - East gate'}
    assert ch['1']['verdict'] == 'meets' and ch['2']['verdict'] == 'meets'
    assert ch['completion']['verdict'] == 'does not meet' and ch['completion']['source'].startswith('mobility/config.json')


def test_existing_buildings_checked_at_every_stage(tmp_path):
    P = project(tmp_path)
    ex = [r for r in rows(P, 'access.csv') if r['id'] == 'osm-w1']
    assert sorted(r['stage'] for r in ex) == ['1', '2', 'completion'] and all(r['connected'] == 'yes' for r in ex)
    stay = [r for r in rows(P, 'checks.csv') if r['requirement'] == 'existing buildings stay reached']
    assert stay and all(r['verdict'] == 'meets' for r in stay)


def test_existing_residents(tmp_path):
    P = project(tmp_path / 'a')          # the brief says nothing about who lives in the building that stays
    os_ = [r for r in rows(P, 'checks.csv') if r['requirement'] == 'open space per resident']
    assert os_ and all(r['verdict'] == EXIST_UNKNOWN for r in os_)
    P = project(tmp_path / 'b', '--existing-residents', '6')
    os_ = [r for r in rows(P, 'checks.csv') if r['requirement'] == 'open space per resident']
    assert os_ and all(r['verdict'] in ('meets', 'does not meet', 'not measured: no residents') for r in os_)
    st = {r['stage']: r for r in rows(P, 'stages.csv')}
    assert st['1']['existing_residents'] == '6'


def test_open_space_path_only_once_built(tmp_path):
    # the garden house is reached only by the garden's path
    P = project(tmp_path / 'a')
    assert all(r['connected'] == 'yes' for r in rows(P, 'access.csv') if r['stage'] == '2'), 'garden with phase 1: its path works'
    P = project(tmp_path / 'b', '--late-garden')
    acc = rows(P, 'access.csv')
    cut = [r['id'] for r in acc if r['stage'] == '2' and r['connected'] == 'no']
    assert len(cut) == 1, 'garden with phase 2: its path does not work at stage 2'
    assert next(r for r in acc if r['stage'] == 'completion' and r['id'] == cut[0])['connected'] == 'yes'
    fc = json.loads((P / 'phasing/phasing.geojson').read_text(encoding='utf-8'))
    paths = [f['properties'] for f in fc['features'] if f['properties']['kind'] == 'street' and f['properties']['open_space_path']]
    assert paths and all(p['phase'] == 2 for p in paths)


def test_undecided_stop_is_not_measured(tmp_path):
    P = project(tmp_path, '--undecided-stop')
    acc = [r for r in rows(P, 'access.csv') if r['phase'] != '0']
    assert acc and all(r['stop_m'] == UNDECIDED for r in acc)
    svc = [r for r in rows(P, 'checks.csv') if r['requirement'] == 'service stop']
    assert svc and all(r['verdict'] == UNDECIDED for r in svc)
    assert not [r for r in rows(P, 'checks.csv') if r['requirement'] == 'service stop' and r['verdict'] == 'does not meet']


def test_later_daycare_does_not_count_earlier(tmp_path):
    P = project(tmp_path, '--no-daycare-in-phase-1')
    acc = [r for r in rows(P, 'access.csv') if r['stage'] == '2']
    assert acc and all(r['daycare_m'] == 'none working' for r in acc), 'the phase-2 daycare must not serve at stage 2'
    done = [r for r in rows(P, 'access.csv') if r['stage'] == 'completion' and r['phase'] == '1']
    assert done and all(r['daycare_m'][0].isdigit() for r in done)


def test_invalid_footprint(tmp_path):
    P = project(tmp_path, '--invalid')
    st = json.loads((P / 'phasing/stage-stats.json').read_text(encoding='utf-8'))
    assert st['homes_check'].startswith('not possible')
    bad = [b for b in buildings(P) if not b['geometry_valid']]
    assert len(bad) == 1 and bad[0]['homes'] is None and bad[0]['id'].startswith('b-')
    assert bad[0]['phase'] == 2 and bad[0]['basis'] == 'structure-plan', 'a phase from a name still applies'
    assert bad[0]['id'] in [x['id'] for x in st['invalid_footprints']]
    assert not [r for r in rows(P, 'access.csv') if r['id'] == bad[0]['id']]
    ph2 = next(r for r in rows(P, 'stage-phases.csv') if r['phase'] == '2')
    assert ph2['left_out'] == '1'


def test_ids_do_not_depend_on_the_crs(tmp_path):
    a = {b['id'] for b in buildings(project(tmp_path / 'a'))}
    b = {b['id'] for b in buildings(project(tmp_path / 'b', '--crs', 'EPSG:25832'))}
    assert a == b


def test_drawing(tmp_path):
    P = project(tmp_path, '--invalid')
    run(HERE / 'phases.py', '--proposal', P, '--config', P / 'phasing/config.json')
    r = subprocess.run([sys.executable, HERE / 'draw.py', '--proposal', P, '--site', Path(tmp_path) / 'site',
                        '--style', P / 'drawing-graphics/style.json'], capture_output=True, text=True)
    if 'no Chrome' in r.stderr + r.stdout:
        pytest.skip('no browser for the PNG')
    assert r.returncode == 0, r.stdout + r.stderr
    for f in ('phasing_large.svg', 'phasing_large.png', 'phases_table.svg', 'phases_table.png'):
        assert (P / 'phasing' / f).stat().st_size > 0


def test_stage_checks_take_the_phases_and_homes_of_phases_py(tmp_path):
    """Both scripts give one answer: phases.py's phase wins over the massing's, and the homes per phase agree."""
    run(HERE / 'example/make_example.py', tmp_path)
    P = Path(tmp_path) / 'proposal'
    mass = json.loads((P / 'massing/massing.geojson').read_text(encoding='utf-8'))
    f = next(f for f in mass['features'] if f['properties'].get('neighbourhood') == 'West' and f['properties'].get('phase') == 1)
    f['properties']['phase'] = 2                              # the massing moves it; its neighbourhood is phase 1
    (P / 'massing/massing.geojson').write_text(json.dumps(mass), encoding='utf-8')
    cfg = P / 'phasing/config.json'
    run(HERE / 'phases.py', '--proposal', P, '--config', cfg)
    run(HERE / 'phasing.py', '--proposal', P, '--site', Path(tmp_path) / 'site', '--config', cfg)
    bs = buildings(P)
    assert {b['basis'] for b in bs if not b['existing'] and b['phase']} == {'phases.py'}
    assert not [b for b in bs if b['phase'] == 2 and b['use'] == 'housing' and b['homes'] and b['id'] == fingerprint_of(f)]
    st = json.loads((P / 'phasing/stage-stats.json').read_text(encoding='utf-8'))
    assert not [w for w in st['warnings'] if 'phases.csv' in w]
    assert 'homes' not in rows(P, 'stage-phases.csv')[0], 'the homes per phase have one source: phases.csv'
    assert json.loads((P / 'phasing/stats.json').read_text(encoding='utf-8'))['flags']    # phases.py keeps its own stats


def fingerprint_of(feature):
    sys.path.insert(0, str(HERE))
    from fingerprint import fingerprint
    return fingerprint(feature['geometry'])


def test_the_street_a_building_stands_on_comes_with_it(tmp_path):
    """A long new street whose middle lies on no phase's land: the building on it still gets it, and the run doesn't stop."""
    run(HERE / 'example/make_example.py', tmp_path)
    P = Path(tmp_path) / 'proposal'
    st = json.loads((P / 'streets/streets.geojson').read_text(encoding='utf-8'))
    east = next(f for f in st['features'] if f['properties'].get('name') == 'Main east')
    (x0, y0), (x1, y1) = east['geometry']['coordinates']
    east['geometry']['coordinates'] = [[x0, y0], [x0 + 3 * (x1 - x0), y0 + 3 * (y1 - y0)]]
    (P / 'streets/streets.geojson').write_text(json.dumps(st), encoding='utf-8')
    run(HERE / 'phasing.py', '--proposal', P, '--site', Path(tmp_path) / 'site', '--config', P / 'phasing/config.json')
    assert all(r['connected'] == 'yes' for r in rows(P, 'access.csv') if r['stage'] == 'completion' and r['phase'] == '2')
    fc = json.loads((P / 'phasing/phasing.geojson').read_text(encoding='utf-8'))
    assert 2 in {x['properties']['phase'] for x in fc['features'] if x['properties']['kind'] == 'street' and not x['properties']['existing']}


def edit(P, name, change):
    path = P / name
    fc = json.loads(path.read_text(encoding='utf-8'))
    change(fc)
    path.write_text(json.dumps(fc), encoding='utf-8')


def stages(tmp, P):
    run(HERE / 'phasing.py', '--proposal', P, '--site', Path(tmp) / 'site', '--config', P / 'phasing/config.json')
    return json.loads((P / 'phasing/stage-stats.json').read_text(encoding='utf-8'))


def example(tmp):
    run(HERE / 'example/make_example.py', tmp)
    return Path(tmp) / 'proposal'


def test_open_space_total_adds_up_and_existing_stays_apart(tmp_path):
    P = example(tmp_path)

    def add_park(fc):
        park = next(f for f in fc['features'] if f['properties'].get('name') == 'Garden')
        (x0, y0), (x1, y1) = park['geometry']['coordinates'][0][:2]
        shift = [[x + 0.002, y] for x, y in park['geometry']['coordinates'][0]]
        fc['features'].append({'type': 'Feature', 'properties': {'kind': 'open-space', 'use': 'park', 'name': 'Old park', 'existing': True},
                               'geometry': {'type': 'Polygon', 'coordinates': [shift]}})

    edit(P, 'open-space/open-space.geojson', add_park)
    stages(tmp_path, P)
    t = {r['phase']: r for r in rows(P, 'stage-phases.csv')}
    assert int(t['existing']['open_space_m2']) > 0
    assert int(t['total']['open_space_m2']) == int(t['1']['open_space_m2']) + int(t['2']['open_space_m2'])


def test_a_street_no_phase_needs_is_still_built_by_completion(tmp_path):
    P = example(tmp_path)

    def add_street(fc):
        edge = next(f for f in fc['features'] if f['properties'].get('existing') and f['properties'].get('kind') == 'centreline')
        x, y = edge['geometry']['coordinates'][-1]
        fc['features'].append({'type': 'Feature', 'properties': {'kind': 'centreline', 'level': 'local', 'width': 5.0, 'name': 'Spare', 'existing': False},
                               'geometry': {'type': 'LineString', 'coordinates': [[x, y], [x + 0.0005, y]]}})

    edit(P, 'streets/streets.geojson', add_street)
    st = stages(tmp_path, P)
    assert st['streets_left_to_the_last_phase'] >= 1 and st['streets_without_phase'] == 0
    assert any('last phase' in w for w in st['warnings'])


def test_a_street_mobility_keeps_from_cars_does_not_join_gates(tmp_path):
    P = example(tmp_path)
    streets = json.loads((P / 'streets/streets.geojson').read_text(encoding='utf-8'))['features']
    west = next(f for f in streets if f['properties'].get('kind') == 'centreline' and not f['properties'].get('existing') and f['properties'].get('name') != 'Main east')
    edit(P, 'mobility/mobility.geojson', lambda fc: fc['features'].append(
        {'type': 'Feature', 'properties': {'kind': 'route', 'mode': 'car', 'name': 'West only'}, 'geometry': west['geometry']}))
    stages(tmp_path, P)
    ch = {r['stage']: r for r in rows(P, 'checks.csv') if r['requirement'] == 'no car link West gate - East gate'}
    assert ch['completion']['verdict'] == 'meets', 'the east street is not on a car route, so no car joins the gates'


def test_a_building_cut_off_today_is_not_a_failure_of_the_phases(tmp_path):
    P = example(tmp_path)

    def add_shed(fc):
        old = next(f for f in fc['features'] if f['properties'].get('osm_id') == 'w1')
        ring = [[x + 0.0015, y] for x, y in old['geometry']['coordinates'][0]]
        fc['features'].append({'type': 'Feature', 'properties': dict(old['properties'], osm_id='shed'), 'geometry': {'type': 'Polygon', 'coordinates': [ring]}})

    edit(P, 'massing/massing.geojson', add_shed)
    st = stages(tmp_path, P)
    assert st['existing_not_reached_today'] == 1
    shed = next(b for b in buildings(P) if b['id'] == 'osm-shed')
    assert shed['fails'] == []
    assert all(r['verdict'] == 'meets' for r in rows(P, 'checks.csv') if r['requirement'] == 'existing buildings stay reached')


def test_no_car_access_fails_only_where_the_brief_asks_for_it(tmp_path):
    P = project(tmp_path)
    cfg = json.loads((P / 'phasing/config.json').read_text(encoding='utf-8'))
    assert not [r for r in cfg['requirements']['value'] if r['measure'] == 'car']
    no_car = {r['id'] for r in rows(P, 'access.csv') if r['phase'] != '0' and r['car'] == 'no' and r['connected'] == 'yes'}
    assert no_car, 'the garden house is reached on foot only'
    assert not [b for b in buildings(P) if b['id'] in no_car and b['fails']]


def test_plan_takes_its_frame_and_table_its_homes_from_phases_csv(tmp_path):
    P = project(tmp_path)
    run(HERE / 'phases.py', '--proposal', P, '--config', P / 'phasing/config.json')
    (P / 'panel-layout').mkdir()
    (P / 'panel-layout/layout-plan.json').write_text(json.dumps({'panels': [{'items': [
        {'file': 'phasing/phasing_large.svg', 'scale': '1:2,500', 'frame': {'w': 150, 'h': 120}}]}]}), encoding='utf-8')
    r = subprocess.run([sys.executable, HERE / 'draw.py', '--proposal', P, '--site', Path(tmp_path) / 'site',
                        '--style', P / 'drawing-graphics/style.json'], capture_output=True, text=True)
    if 'no Chrome' in r.stderr + r.stdout:
        pytest.skip('no browser for the PNG')
    assert r.returncode == 0, r.stdout + r.stderr
    svg = (P / 'phasing/phasing_large.svg').read_text(encoding='utf-8')
    assert 'width="150.0mm"' in svg and 'height="120.0mm"' in svg and '1:2,500' in svg
    table = (P / 'phasing/phases_table.svg').read_text(encoding='utf-8')
    total = next(x for x in rows(P, 'phases.csv') if x['phase'] == 'total')
    assert f">{total['homes']}<" in table and f">{total['residents']}<" in table
