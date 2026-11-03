# Plan 003: Secondary streets reach the next street, cross the green as paths, or end on purpose; trees only in the new land

> **Executor instructions**: Read `plans/000-shared-context.md` first. Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. Do not update `plans/README.md`: the reviewer maintains it.
>
> **Drift check (run first)**: plan 001 must be DONE. `grep -n "sec_streets.append\|all_streets = " plugins/design/skills/massing/scripts/massing.py` finds both lines; if not, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/001-massing-figure-from-config.md
- **Category**: bug (the street network) + quality
- **Planned at**: commit `98cdb74`, 2026-11-03

## Why this matters

The massing draws its secondary streets as grid lines inside each land piece and clips them to that piece, so every street stops at the edge of a green strip, a main street's buffer or the site edge. Run-5 counted 17 such dead ends; the mobility skill found 17 % of the new housing unreachable on foot from the stop, and the streets skill reported 8 ends that meet nothing. The skill text already promises "every street meets another at both ends or stops at the site edge", but the script doesn't do it. Also, the tree loop puts a tree every 12 m along every structure-plan route, including the stretches that run through the existing settlement, which fills the check plan and the panel with dots where nothing is planned. After this plan a street end is led on up to 60 m to the next street, carried across a green strip as a path, or counted as a dead end in `stats.json`; trees stand only along streets inside the new neighbourhoods.

## Current state

`plugins/design/skills/massing/scripts/massing.py` (after plan 001). The secondary streets are made per piece inside the placement loop (originally lines 196-207):

```python
        # secondary streets: grid lines between kept blocks
        xs = sorted({x for x, _ in bl}); ys = sorted({y for _, y in bl})
        lines = []
        for x in xs[1:]:
            lines.append(LineString([(x - CONFIG['sec_street_w'] / 2 - sb, y0 - 50), (x - CONFIG['sec_street_w'] / 2 - sb, y1 + 50)]))
        for y in ys[1:]:
            lines.append(LineString([(x0 - 50, y - CONFIG['sec_street_w'] / 2 - sb), (x1 + 50, y - CONFIG['sec_street_w'] / 2 - sb)]))
        for ln in lines:
            cl = ln.intersection(loc)
            for q in ([cl] if cl.geom_type == 'LineString' else list(getattr(cl, 'geoms', []))):
                if q.geom_type == 'LineString' and q.length > 20:
                    sec_streets.append(affinity.rotate(q, ang, origin=o))
```

`loc` is the land piece (the neighbourhood minus `excl`, which is green, main street buffers, centres, water and kept-building buffers), so a line never leaves its piece. Later (originally lines 388-400) the streets are written:

```python
for p, g in street_routes:
    add('street', g.intersection(site.buffer(5)) if g.intersects(site) else g, width=CONFIG['street_w'], name=p['name'], level=p['level'])
for p, g in path_routes:
    add('street', g, width=CONFIG['path_w'], name=p['name'], level='path')
for g in sec_streets:
    add('street', g, width=CONFIG['sec_street_w'], level='secondary', note='greened secondary street')
```

And the trees (originally lines 408-422) walk `all_streets = [g for _, g in street_routes] + sec_streets`, clipped to `site`, a tree every `tree_step` at `tree_off` from the middle, both sides, skipping points inside buildings or squares. `street_routes` are the structure plan's `main` and `local` routes, which run through existing fabric too.

Names in scope: `site` (polygon, UTM), `green_u` (union of structure-plan greens), `kept` (list of (props, geom) existing buildings in the site), `buildings` (list of dicts with `geom`), `street_routes`, `main_routes`, `water` (list), `nbh` (list of (props, geom) neighbourhoods), `CONFIG`, `DEFAULTS`, `add(kind, geom, **props)`.

The run-5 helper's working version of the extension (in `competition/proposals/2026-11-02_run-5/massing/massing.py`, lines 444-469 there, present on the owner's computer only) is the shape to port: a function that, for each end of each secondary street not already within 3 m of another street, the site edge or the green, casts a ray straight on up to 60 m, cuts it at the first hit among the other streets, the main routes, the site edge and the green boundary, and extends the street there unless the new piece's buffer (half the street width minus 1 m) touches a building.

## Scope

**In scope**: `plugins/design/skills/massing/scripts/massing.py`, `plugins/design/skills/massing/SKILL.md`, `tests/test_scripts.py`.

**Out of scope**: `draw.py`, the streets skill (`plugins/design/skills/streets/`), `tests/synthetic.py`.

## Steps

### Step 1: Defaults

In `DEFAULTS` add `'street_reach_m': 60.0` (how far a secondary street that ends in nothing is led on to the next street, the green or the site edge) and `'path_reach_m': 150.0` (how far a path may carry a street end across the green to the next street).

### Step 2: Ends on purpose

After the placement loop (after all neighbourhoods, before `# ---------- community`), add a function `end_streets(sec)` and call it: `sec_streets, street_ends = end_streets(sec_streets)`.

Behaviour, for each end `p` of each secondary street (its other end's neighbour point is `q`):

1. Already met: if `p` is within 3 m of any other secondary street, any main/local route line, the site boundary, or within 6 m of `green_u`'s boundary → leave it; record its kind: `'street'`, `'site edge'` or `'green edge'`.
2. Else cast a ray from `p` in the direction `q → p`, `street_reach_m` long. Targets: the union of the other secondary streets, the main/local route lines, the site boundary and `green_u.boundary`. Take the nearest hit along the ray. If none → kind `'dead end'`.
3. If the extension segment, buffered by `sec_street_w / 2 - 1`, intersects any building (new or kept, `unary_union` of their geoms) or any water polygon → kind `'dead end'`, no extension.
4. Else extend the street's coordinates to the hit point and record the kind by what was hit (`'street'`, `'site edge'`, `'green edge'`).
5. Green crossings: for every end of kind `'green edge'`, cast a ray on from the hit point, `path_reach_m` long, through the green; if it meets another secondary street, a main/local route or a landscape route (`path_routes`) and the segment lies within `green_u.buffer(2)` except its last 3 m, and crosses no building or water, make a path `LineString([hit, meet])`; collect it in `green_paths`. (One path per green edge end; several ends may make parallel paths; that is fine.)

6. Two more kinds are ends on purpose (added by the reviewer during execution): `'centre'`, when the end lies within 3 m of a structure-plan centre polygon (the street arrives at the square); `'land edge'`, when the ray found nothing and the end lies within 3 m of the boundary of its own neighbourhood's buildable land (the street ends where the built land ends). Only the rest are `'dead end'`.

Return the extended streets and a list of `(kind, Point)`.

Then write: each secondary street as today, with `dead_end=True` added to the properties when either of its ends is `'dead end'`; each green path as `add('street', g, width=CONFIG['path_w'], level='path', note='path across the green')`. In `stats` add `'street_ends': {kind: count}` and `'secondary_dead_ends': count of 'dead end'` and `'green_crossings': len(green_paths)`.

### Step 3: Trees only in the new land

Compute `new_land = unary_union([g.intersection(site) for p, g in nbh if p['action'] != 'keep' and p['name'] in CONFIG['density']])`. In the tree loop replace `g = g.intersection(site)` by `g = g.intersection(new_land.buffer(CONFIG['street_w']))` so trees stand only along street stretches in or just beside the new neighbourhoods. Green paths get no trees.

### Step 4: Skill text

In `SKILL.md`, in the **Blocks.** bullet (rewritten by plan 001; it now ends with "Courtyards become `open-space` garden."), add before that last sentence: "Blocks less than a third complete are dropped. Every street is led on to the next street, across the green as a path, or ends at the site edge; the ends that still meet nothing are counted as `secondary_dead_ends` in `stats.json`, and the summary names them."  In the **Trees and squares.** bullet replace "along every street" by "along every street in the new neighbourhoods".

### Step 5: Tests

In `tests/test_scripts.py` with `make_proposal` (its neighbourhood is split in two by the 50 m green strip, so street ends meet the green on both sides):

- `test_massing_streets_end_on_purpose`: after a default run, read `massing.geojson` in UTM: for every `street` with `level == 'secondary'`, each end point is within 3 m of another street line (any level), the site boundary, or within 6 m of a structure-plan green boundary, unless the feature has `dead_end: true`. And `stats['secondary_dead_ends'] <= 3` (the synthetic site has kept buildings in the way of three ends), and `{'centre', 'land edge'} & set(stats['street_ends'])`.
- `test_massing_paths_cross_the_green`: `stats['green_crossings'] >= 1` and at least one `street` feature with `level == 'path'` and `note == 'path across the green'` intersects the green strip.
- `test_massing_trees_only_in_new_land`: every `tree` point lies within the neighbourhood polygon buffered by `street_w` (16 m) + 4 m.

**Verify**: `python -m pytest tests/test_scripts.py -q` → 0 failed; `python -m pytest tests -q` → 0 failed.

## Done criteria

- [ ] `python -m pytest tests -q` → 0 failed.
- [ ] On run-3 inputs (if present), `stats['n_new']` is unchanged from plan 001's number (streets don't move buildings), and `stats['secondary_dead_ends']` exists.
- [ ] `grep -n "def end_streets\|green_crossings\|path across the green" plugins/design/skills/massing/scripts/massing.py` finds all three.
- [ ] `git status --short` shows only in-scope files changed (plus the owner's six pre-existing modified files).

## STOP conditions

- The placement loop's secondary-street lines don't match the excerpt.
- After implementing, the synthetic run has more than 3 dead ends: inspect why (a building in the way is legitimate); if the cause is in the ray logic and one fix doesn't solve it, STOP and report the end points.
- A fix seems to need the streets skill: don't; report instead.

## Maintenance notes

- The streets skill (`plugins/design/skills/streets/scripts/streets.py`) still joins new streets into the existing surface and reports `main_routes_ending_nowhere`; after this plan it should see far fewer stubs. Plan 005 makes other drawings read its output.
- A reviewer should check that extensions never cross buildings (step 2.3) and that the ray uses the street's own direction, never a sideways jump.
