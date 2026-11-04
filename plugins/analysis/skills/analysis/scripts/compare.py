"""Compares today and design for every measure of every analysis in a proposal folder.

    python compare.py --proposal <proposal folder> [--config <proposal>/analysis/config.json]

Reads every <skill>/metrics.csv in the proposal folder; writes analysis/comparison.csv
(skill, measure, unit, today, design, change, better) and analysis/comparison.md (a table, best and worst first).
'better' is yes, no or blank, from config.json 'better': the first word of a measure and which way is better.
"""
import argparse, csv, glob, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import read_config

A = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
A.add_argument('--proposal', required=True)
A.add_argument('--config')
ARGS = A.parse_args()
OUT = os.path.join(ARGS.proposal, 'analysis')
cfg_path = ARGS.config or os.path.join(OUT, 'config.json')
BETTER = read_config(cfg_path)[0].get('better', {}) if os.path.exists(cfg_path) else {}

rows = []
for path in sorted(glob.glob(os.path.join(ARGS.proposal, '*', 'metrics.csv'))):
    skill = os.path.basename(os.path.dirname(path))
    vals = {}
    for r in csv.DictReader(open(path, encoding='utf8')):
        try:
            vals.setdefault((r['measure'], r['unit']), {})[r['state']] = float(r['value'])
        except (KeyError, ValueError):
            continue
    for (m, u), v in vals.items():
        if 'today' not in v and 'design' not in v:
            continue
        t, d = v.get('today'), v.get('design')
        ch = None if t is None or d is None else d - t
        way = BETTER.get(m.split()[0])
        better = '' if ch is None or not way or abs(ch) < 1e-9 else ('yes' if (ch > 0) == (way == 'higher') else 'no')
        rows.append({'skill': skill, 'measure': m, 'unit': u, 'today': t, 'design': d,
                     'change': None if ch is None else round(ch, 2), 'better': better})
if not rows:
    sys.exit('no metrics.csv with today or design rows in ' + ARGS.proposal)

with open(os.path.join(OUT, 'comparison.csv'), 'w', newline='', encoding='utf8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

fmt = lambda x: '' if x is None else f'{x:,.1f}'
# shares and counts first: they compare across sites; areas and lengths follow
order = {'yes': 0, 'no': 1, '': 2}
md = ['# Today and design', '', '| skill | measure | unit | today | design | change | better |', '| --- | --- | --- | ---: | ---: | ---: | --- |']
for r in sorted(rows, key=lambda r: (order[r['better']], r['skill'], r['unit'] != '%', r['measure'])):
    if r['measure'].startswith('use ') and r['unit'] == 'ha':
        continue  # the shares say the same
    md.append(f"| {r['skill']} | {r['measure']} | {r['unit']} | {fmt(r['today'])} | {fmt(r['design'])} | {fmt(r['change'])} | {r['better']} |")
open(os.path.join(OUT, 'comparison.md'), 'w', encoding='utf8').write('\n'.join(md) + '\n')
n = {k: sum(1 for r in rows if r['better'] == k) for k in ('yes', 'no')}
print(f"{len(rows)} measures from {len({r['skill'] for r in rows})} skills: {n['yes']} better, {n['no']} worse")
