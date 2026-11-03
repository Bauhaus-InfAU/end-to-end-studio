# Plan 001: The massing's figure (typology, orientation, row gap) comes from config, not from a rewritten script

> **Executor instructions**: Read `plans/000-shared-context.md` first. Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. Do not update `plans/README.md`: the reviewer maintains it.
>
> **Drift check (run first)**: `git diff --stat 98cdb74..HEAD -- plugins/design/skills/massing tests/test_scripts.py` must print nothing (no commits since the plan was written). Then `git status --short plugins/design/skills/massing` must show only `M plugins/design/skills/massing/scripts/draw.py` (the owner's uncommitted edit; leave it). If `massing.py` shows as modified, compare the "Current state" excerpts against the file before going on; on a mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: direction (quality of the design) + tech-debt
- **Planned at**: commit `98cdb74`, 2026-11-03

## Why this matters

The massing script places buildings in five fixed rectangle types, one per density word, and turns each block grid to the long side of the land piece it sits on. The idea of the entry (the "narrative") never reaches the script: the word "narrative" does not occur in it. So the helper that runs the skill rewrites the script every run to make the figure the narrative asks for (run-4 added block sizes and community sites; run-5 added a bearing, a rows-only mode and a row gap), at $1.3 to $2.8 per run on the expensive model, and the patches are lost at the next run. Run-3's own summary says: "blocks follow each field's long side as the skill says, not the narrative's Lamellen slats". After this plan the helper writes words into `config.json` (a typology, an orientation, a row gap, block sizes per neighbourhood, each with the narrative principle it comes from) and the script does the rest, the same way every run.

## Current state

Files:

- `plugins/design/skills/massing/scripts/massing.py` (475 lines): the placement script. Run as `python massing.py --proposal <folder> --site <site folder> --config <proposal>/massing/config.json`.
- `plugins/design/skills/massing/scripts/draw.py`: the check drawings; not changed by this plan (it has an uncommitted edit of the owner's; leave it).
- `plugins/design/skills/massing/scripts/config.example.json`: the template the helper copies and fills; every key as `{"value": ..., "source": ...}`.
- `plugins/design/skills/massing/SKILL.md` (30 lines): the skill text.
- `tests/test_scripts.py`: tests of the massing scripts; `tests/fixtures/massing_config_run3.json`: a filled config.

The types, `massing.py:61-67`:

```python
# skill defaults per density: block length, block depth, building depth, base floors, use, type
TYPES = {
    'low':        dict(L=90, D=40, d=10, fl=3, use='housing', type='row houses', gap=6, short=0),
    'medium':     dict(L=90, D=70, d=13, fl=4, use='housing', type='open courtyard block', gap=6, short=1),
    'high':       dict(L=100, D=80, d=14, fl=5, use='mixed', type='courtyard block', gap=6, short=2),
    'urban':      dict(L=100, D=80, d=14, fl=6, use='mixed', type='courtyard block', gap=6, short=2),
    'commercial': dict(L=100, D=60, d=25, fl=3, use='commerce', type='hall', gap=7, short=0),
}
```

`segs` and `block_buildings`, `massing.py:112-133`: `segs(S, gap, lo=30, hi=50)` splits a side into buildings of 30 to 50 m; `block_buildings(t)` takes a density key `t`, looks up `TYPES[t]`, builds the two long rows (`box(a, 0, b, d)` and `box(a, D - d, b, D)`), the short wings when `T['short']` is 1 or 2, and the court.

The placement loop, `massing.py:143-207` (abridged, the lines that matter):

```python
buildings, courts, sec_streets = [], [], []
for p, g in nbh:
    if p['action'] == 'keep' or p['name'] not in CONFIG['density']:
        continue
    t = CONFIG['density'][p['name']]; T = TYPES[t]
    land = g.intersection(site).difference(excl)
    pieces = [land] if land.geom_type == 'Polygon' else list(getattr(land, 'geoms', []))
    for piece in pieces:
        if piece.geom_type != 'Polygon' or piece.area < T['L'] * T['D'] / 3:
            continue
        r = piece.minimum_rotated_rectangle
        c = list(r.exterior.coords)
        e = max([(c[i], c[i + 1]) for i in range(4)], key=lambda s: math.dist(*s))
        ang = math.degrees(math.atan2(e[1][1] - e[0][1], e[1][0] - e[0][0]))
        o = piece.centroid
        loc = affinity.rotate(piece, -ang, origin=o)
        x0, y0, x1, y1 = loc.bounds
        sb = setback(t)
        pitchx, pitchy = T['L'] + CONFIG['sec_street_w'] + 2 * sb, T['D'] + CONFIG['sec_street_w'] + 2 * sb
        best = None
        for ox in range(0, int(pitchx), 10):
            for oy in range(0, int(pitchy), 10):
                ...  # the grid offset that fits most blocks
        bl, ox, oy = best
        for x, y in bl:
            blds, court = block_buildings(t)
            ...
            for cl in got:
                buildings.append(dict(geom=affinity.rotate(cl, ang, origin=o), t=t, nb=p['name'],
                                      phase=1 if p['name'] in CONFIG['phase1'] else None))
```

`setback(t)` at `massing.py:136-140` takes the density key too. The heights block at `massing.py:270-280` does `T = TYPES[b['t']]` per building and sets `b['use'] = T['use']; b['type'] = T['type']`.

The run-5 helper's working patch for rows, in `competition/proposals/2026-11-02_run-5/massing/massing.py` (present on the owner's computer, not in git), is the shape to generalise:

```python
'orientation_deg': None, 'rows_only': False, 'row_gap': 24.0}  # run-5 copy: rows along a bearing (fresh air)
...
if CONFIG['rows_only']:  # run-5 copy: parallel rows only, no cross wings across the air flow,
    for _t in TYPES.values():  # and the two rows of a block row_gap apart instead of a courtyard
        _t['short'] = 0; _t['D'] = 2 * _t['d'] + CONFIG['row_gap']
...
        if CONFIG['orientation_deg'] is not None:  # run-5 copy: long sides along the bearing
            ang = 90.0 - CONFIG['orientation_deg']
```

`read_config` (massing.py:21-33) drops any config entry whose `value` is `null` or whose `source` starts with `<`, so an unfilled template entry counts as absent. Optional keys have their defaults in `OPTIONAL`/`DEFAULTS` (massing.py:44-52) and `CONFIG = {**OPTIONAL, **DEFAULTS, **_values}`.

The skill text's **Blocks.** bullet (`SKILL.md:14`) describes the fixed figure: "Fill each neighbourhood with a grid of blocks turned to its long side, 10 m greened secondary streets between them; ... By density: low, two rows of houses, 10 m deep, 3 floors; medium, an open courtyard block, 13 m deep, 4 floors; high and urban, courtyard blocks 14 m deep, 5 and 6 floors, mixed; commercial, halls 25 m deep in rows, 3 floors. Courtyards become `open-space` garden."

## Commands you will need

See `plans/000-shared-context.md`. Also:

| Purpose | Command | Expected |
| --- | --- | --- |
| Run the massing on the synthetic proposal | `python plugins/design/skills/massing/scripts/massing.py --proposal <P> --site <S> --config <P>/massing/config.json` | exit 0, prints stats JSON |

## Scope

**In scope** (the only files you may modify or create):

- `plugins/design/skills/massing/scripts/massing.py`
- `plugins/design/skills/massing/scripts/config.example.json`
- `plugins/design/skills/massing/SKILL.md`
- `tests/synthetic.py` (create)
- `tests/test_scripts.py`

**Out of scope**: `draw.py` (owner's uncommitted edit), every other skill, `STUDIO.md`, `tests/test_order.py`, anything in `competition/`.

## Steps

### Step 1: Record the baseline

Run `python -m pytest tests/test_scripts.py -q`. Expected: `1 failed, 6 passed` (the failure is `test_massing_reproduces_run3`, pre-existing). If `competition/proposals/2026-11-02_run-3` is missing on this computer, every test there skips; note it and go on.

Then, if run-3 exists, keep a copy of today's output for a same-result check later:

```
python - <<EOF
import shutil, json, pathlib, subprocess, sys
root = pathlib.Path('.').resolve(); tmp = pathlib.Path(r'C:\Users\egayd\AppData\Local\Temp\claude\plan001'); tmp.mkdir(parents=True, exist_ok=True)
out = tmp / 'before'; shutil.rmtree(out, ignore_errors=True); out.mkdir()
for s in ['structure-plan', 'climate', 'programme', 'narrative']: shutil.copytree(root / 'competition/proposals/2026-11-02_run-3' / s, out / s)
(out / 'massing').mkdir(); shutil.copy(root / 'tests/fixtures/massing_config_run3.json', out / 'massing/config.json')
subprocess.run([sys.executable, 'plugins/design/skills/massing/scripts/massing.py', '--proposal', str(out), '--site', 'competition/site', '--config', str(out / 'massing/config.json')], check=True)
EOF
```

**Verify**: `type C:\Users\egayd\AppData\Local\Temp\claude\plan001\before\massing\stats.json` (PowerShell: `Get-Content`) shows `n_new` and `total_gfa`. Write both numbers down.

### Step 2: Write `tests/synthetic.py`

Create `tests/synthetic.py` exactly as `plans/000-shared-context.md` describes under "The synthetic proposal used by tests": `make_proposal(tmp_path, split_green=True, holds=True)` returning the proposal folder path. Build the geometry in the site's UTM zone (copy `utm_epsg` from massing.py), write WGS84 longitude first. Use `shapely` only. The largest rectangle: take the site polygon shrunk by 100 m (`site.buffer(-100)`), take its pole of inaccessibility `shapely.ops.polylabel(shrunk, 1.0)` (the point deepest inside it), and centre an axis-aligned box 400 × 300 m there; if it is not `within` the shrunk site, try 300 × 220 m; if that fails too, raise `RuntimeError("no room for the synthetic neighbourhood in this site")`.

**Verify**: `python -c "import sys; sys.path.insert(0,'tests'); import synthetic, pathlib, tempfile; p = synthetic.make_proposal(pathlib.Path(tempfile.mkdtemp())); print(p, sorted(x.name for x in p.iterdir()))"` prints the folder and `['drawing-graphics', 'massing', 'structure-plan']`.

### Step 3: Add the figure vocabulary to `massing.py`

1. In `DEFAULTS` add `'row_gap': 24.0` (metres between the two rows of a block in the rows and points typologies).
2. After `TYPES`, add:

```python
# a typology changes the block of a density; the figure comes from the narrative through config `figure`
TYPOLOGY = {
    'rows':           dict(short=0, rows=True, type='rows'),
    'open courtyard': dict(short=1, type='open courtyard block'),
    'courtyard':      dict(short=2, type='courtyard block'),
    'points':         dict(short=0, rows=True, points=True, type='point buildings'),
    'halls':          dict(short=0, d=25, gap=7, use='commerce', type='hall'),
}
FIGURE = CONFIG.get('figure') or {}


def figure_for(name):
    """config `figure`: {"*": {...}, "<neighbourhood>": {...}}; the named entry overrides "*"."""
    return {**FIGURE.get('*', {}), **FIGURE.get(name, {})}


def type_for(name):
    """the block of a neighbourhood: its density's TYPES entry, changed by its figure"""
    T = dict(TYPES[CONFIG['density'][name]]); F = figure_for(name)
    if F.get('typology'):
        if F['typology'] not in TYPOLOGY:
            sys.exit('figure.%s.typology "%s" is not one of %s' % (name, F['typology'], ', '.join(TYPOLOGY)))
        T.update(TYPOLOGY[F['typology']])
    T.update(F.get('block') or {})
    if T.get('rows'):
        T['D'] = 2 * T['d'] + float(F.get('row_gap', CONFIG['row_gap']))
    return T
```

Also add `'figure': {}` to `OPTIONAL` so `CONFIG.get('figure')` is never missing.

3. Change `block_buildings(t)` to `block_buildings(T)` taking the dict, and inside it: when `T.get('points')`, call `segs(L, g, lo=T['d'], hi=T['d'])` so the long sides carry square point buildings `d` × `d`; otherwise `segs(L, g)` as today. Change `setback(t)` to use `T` only through `CONFIG` (it does not use `t` except to be called; keep its signature, pass the density key).
4. In the placement loop: replace `t = CONFIG['density'][p['name']]; T = TYPES[t]` by `t = CONFIG['density'][p['name']]; T = type_for(p['name']); F = figure_for(p['name'])`. Keep `t` on each building (`b['t']`) for the heights block, and ALSO store `b['T'] = T` is not JSON-safe; instead store `b['type'] = T['type']` and `b['use0'] = T['use']` and `b['fl0'] = T['fl']` on the building dict at placement, and in the heights block use those instead of `TYPES[b['t']]` (`f = b['fl0']`, `b['use'] = b['use0']; b['type'] = b['type']`).
5. Orientation. After the line `ang = math.degrees(math.atan2(...))`, add:

```python
        ori = F.get('orientation', 'long side')
        if isinstance(ori, (int, float)):            # a bearing from north, clockwise; long sides run along it
            ang = 90.0 - float(ori)
        elif ori == 'route' and street_routes:       # along the nearest main or local route of the structure plan
            ln = min((g for _, g in street_routes), key=lambda g: g.distance(piece.centroid))
            ln = ln if ln.geom_type == 'LineString' else max(ln.geoms, key=lambda q: q.length)
            tt = ln.project(piece.centroid); a_, b_ = ln.interpolate(max(tt - 5, 0)), ln.interpolate(min(tt + 5, ln.length))
            ang = math.degrees(math.atan2(b_.y - a_.y, b_.x - a_.x))
        elif ori != 'long side':
            sys.exit('figure.%s.orientation must be "long side", "route" or a bearing in degrees' % p['name'])
```

6. Grid indices for later plans. After `bl, ox, oy = best`, compute `xs = sorted({x for x, _ in bl}); ys = sorted({y for _, y in bl})` once (the same two lines exist further down for the secondary streets; reuse them, don't compute twice) and store `col=xs.index(x), row=ys.index(y)` on every building dict appended in that block.
7. `assumptions.md`: after the "Skill defaults used" section, write a section `## Figure` with one line per built neighbourhood: `- <name>: <typology or "by density (<density>)">, orientation <long side | route | N deg>, row gap <m> (<source of config figure, or "skill default">)`.
8. Stats: add `'figure': {name: {'typology': ..., 'orientation': ...}}` to `stats`.

**Verify**: with run-3 present, repeat the Step 1 run into `.../plan001/after` and compare: `n_new` and `total_gfa` in `after/massing/stats.json` equal the numbers from Step 1 (no `figure` in that config, so nothing may change). Without run-3: run on the synthetic proposal (Step 2) → exit 0, `n_new > 0`.

### Step 4: The config template

In `config.example.json` add, after `phase1`:

```json
 "figure": {
  "value": {
   "*": {"typology": "rows | open courtyard | courtyard | points | halls", "orientation": "long side | route | <bearing in degrees from north>", "row_gap": 24},
   "<neighbourhood name>": {"typology": "...", "orientation": 0, "block": {"L": 90, "D": 70, "d": 13, "gap": 6}}
  },
  "source": "<narrative.md principle N, or brief p. N>; optional: without it the figure follows the density"
 },
```

**Verify**: `python -m pytest tests/test_scripts.py::test_massing_example_config_stops -q` still passes (the example still stops on the required keys; the `figure` entry's source starts with `<`, so it is dropped as unfilled).

### Step 5: The skill text

In `SKILL.md`, replace the **Blocks.** bullet by this (keep its first and last sentences' meaning, lose the fixed list):

> - **Blocks.** The figure comes from the narrative. In `config.json`, `figure` says per neighbourhood (or `*` for all) the typology (`rows`, `open courtyard`, `courtyard`, `points`, `halls`), the orientation (`long side` of the land, `route` for along the nearest route, or a bearing in degrees, such as the cold-air flow), the row gap and, if the brief sets them, the block sizes; name the principle each comes from. Without a `figure`, the density decides: low gives rows of houses, medium an open courtyard block, high and urban courtyard blocks with shops below, commercial halls. Blocks sit on a grid with 10 m greened secondary streets between them; buildings are 30 to 50 m long with gaps of 5 to 8 m, so air and people pass. Courtyards become `open-space` garden.

Keep the rest of the file as it is.

**Verify**: `python -m pytest tests/test_order.py -q` passes (the `Reads:` and `Model:` lines are untouched).

### Step 6: Tests

In `tests/test_scripts.py`:

1. Add `sys.path.insert(0, str(Path(__file__).parent))` and `from synthetic import make_proposal` near the top.
2. Replace `test_massing_reproduces_run3` by `test_massing_runs_on_run3_inputs` (same `@needs_run3`, same run of massing.py and draw.py), asserting: exit 0; the six output files exist; `stats["homes"]` is within 5 % of `cfg["homes_target"]["value"]` OR `stats["at_cap"] / stats["n_home"] > 0.5` (the programme does not fit at the cap, which the script reports).
3. Add, using the synthetic proposal (no skip):
   - `test_massing_synthetic_default`: exit 0; at least 4 new buildings; no two new buildings overlap (pairwise `intersection(...).area < 1` for buildings in UTM); every new building lies within the neighbourhood polygon buffered by 1 m.
   - `test_massing_figure_rows_bearing`: config `figure = {"value": {"*": {"typology": "rows", "orientation": 30}}, "source": "test"}` → every new building's `type` is `rows`, and for every building the long axis of its `minimum_rotated_rectangle` has a bearing within 3° of 30 or 210 (compute `atan2` of the longer side, convert to a bearing from north clockwise, fold to 0–180).
   - `test_massing_figure_points`: `{"*": {"typology": "points"}}` → every new building's `minimum_rotated_rectangle` has a long/short side ratio below 1.6.
   - `test_massing_figure_unknown_stops`: `{"*": {"typology": "towers"}}` → exit code non-zero and `towers` in stderr.
4. Add `tests/synthetic.py` to nothing (it names no site), but add every script you touched to `NEW_SCRIPTS` (massing.py and draw.py are already there).

**Verify**: `python -m pytest tests/test_scripts.py -q` → all pass or skip, 0 failed. Then `python -m pytest tests -q` → 0 failed.

## Test plan

Covered by Step 6: the no-figure path is unchanged (Step 3 verify, same `n_new` and `total_gfa` on run-3 inputs), rows with a bearing, points, an unknown word stops with its name, the synthetic default places non-overlapping buildings inside the neighbourhood. Pattern: `tests/test_scripts.py` (subprocess runs, `buildings()` reader).

## Done criteria

- [ ] `python -m pytest tests -q` → 0 failed (skips allowed).
- [ ] With run-3 present: `n_new` and `total_gfa` on run-3 inputs are the same before and after (Step 1 vs Step 3).
- [ ] `grep -n "TYPES\[b\['t'\]\]" plugins/design/skills/massing/scripts/massing.py` returns nothing (the heights block reads the per-building values).
- [ ] `grep -n "figure" plugins/design/skills/massing/scripts/config.example.json plugins/design/skills/massing/SKILL.md` finds both.
- [ ] `git status --short` shows changes only in the in-scope files (plus the owner's six pre-existing modified files).

## STOP conditions

- The excerpts in "Current state" don't match `massing.py` (lines may shift by a few; the code must match).
- Step 3's same-result check differs (`n_new` or `total_gfa` changed with no `figure` in the config): find the cause; if it isn't found within one attempt, STOP and report the two numbers.
- The synthetic neighbourhood can't be placed in the site (`RuntimeError` in Step 2).
- A fix seems to need `draw.py` or another skill.

## Maintenance notes

- Plans 002 (height profiles), 003 (secondary streets that end on purpose) and 004 (community buildings on the centre that holds them) build on `figure_for`, `type_for` and the `row`/`col` indices stored here.
- A reviewer should check that `block_buildings` with `points` makes square footprints and that `type_for` never mutates `TYPES` (it copies with `dict(...)`).
- Deferred: moving the skill from `Model: opus` to Sonnet. Do that only after one full run shows the helper no longer patches the script (its `summary.md` names no local script copy).
