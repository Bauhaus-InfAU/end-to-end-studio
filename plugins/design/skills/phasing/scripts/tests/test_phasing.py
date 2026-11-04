"""phasing.py and draw.py on the made-up example. Run with pytest; skipped without shapely, pyproj and networkx.
The drawing check is skipped without Chrome, Edge or Chromium."""
import csv, json, subprocess, sys
from pathlib import Path

import pytest

for mod in ('shapely', 'pyproj', 'networkx'):
    pytest.importorskip(mod)

HERE = Path(__file__).resolve().parents[1]


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
    st = json.loads((P / 'phasing/stats.json').read_text(encoding='utf-8'))
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
    st = json.loads((P / 'phasing/stats.json').read_text(encoding='utf-8'))
    assert st['homes_check'].startswith('not possible')
    bad = [b for b in buildings(P) if not b['geometry_valid']]
    assert len(bad) == 1 and bad[0]['homes'] is None and bad[0]['id'].startswith('b-')
    assert bad[0]['phase'] == 2 and bad[0]['basis'] == 'structure-plan', 'a phase from a name still applies'
    assert bad[0]['id'] in [x['id'] for x in st['invalid_footprints']]
    assert not [r for r in rows(P, 'access.csv') if r['id'] == bad[0]['id']]
    ph2 = next(r for r in rows(P, 'phases.csv') if r['phase'] == '2')
    assert ph2['left_out'] == '1'


def test_ids_do_not_depend_on_the_crs(tmp_path):
    a = {b['id'] for b in buildings(project(tmp_path / 'a'))}
    b = {b['id'] for b in buildings(project(tmp_path / 'b', '--crs', 'EPSG:25832'))}
    assert a == b


def test_drawing(tmp_path):
    P = project(tmp_path, '--invalid')
    r = subprocess.run([sys.executable, HERE / 'draw.py', '--proposal', P, '--site', Path(tmp_path) / 'site',
                        '--style', P / 'drawing-graphics/style.json'], capture_output=True, text=True)
    if 'no Chrome' in r.stderr + r.stdout:
        pytest.skip('no browser for the PNG')
    assert r.returncode == 0, r.stdout + r.stderr
    for f in ('phasing_large.svg', 'phasing_large.png', 'phases_table.svg', 'phases_table.png'):
        assert (P / 'phasing' / f).stat().st_size > 0
