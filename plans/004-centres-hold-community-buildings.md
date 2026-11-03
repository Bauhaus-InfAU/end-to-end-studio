# Plan 004: A centre says what it holds, and the massing builds the hub, the school and the pool there

> **Executor instructions**: Read `plans/000-shared-context.md` first. Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. Do not update `plans/README.md`: the reviewer maintains it.
>
> **Drift check (run first)**: plan 001 must be DONE. `grep -n "school_court = \|pool_court = \|def ring_of" plugins/design/skills/massing/scripts/massing.py` finds all three; `git diff --stat 98cdb74..HEAD -- plugins/concept/skills/structure-plan` prints nothing. Otherwise STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/001-massing-figure-from-config.md
- **Category**: bug (a required building is never built) + contract between two skills
- **Planned at**: commit `98cdb74`, 2026-11-03

## Why this matters

The brief's centrepiece, a mobility hub with a bus station at the new stop, has had no building in any run: the jury of run-3 counted "0 of 6 mobility points have a building", run-5's massing says "the station square itself stays open". The massing script only knows how to place a school and a pool, and only on the nearest courtyard block. The run-5 helper invented a `holds` property on the structure plan's centres ("stop, bus station, food market") to pass the brief's wishes down, and patched the massing to read it; neither skill's text has it, so the next run starts without it. After this plan the structure plan writes `holds` on every centre, the massing reads it, and any community building the brief asks for (hub, bus station, market hall, school, pool) is listed once in `config.json` and built on the centre that holds it, with its grounds.

## Current state

`plugins/concept/skills/structure-plan/SKILL.md` (22 lines) lists the features it writes:

```
- `neighbourhood` (polygon), which massing fills with buildings
- `centre` (polygon), `level` main or local
- `green` (polygon), `roles` as a list
- `route` (line), `level` main, local or landscape
- `gateway` (point), where the site meets the city or the landscape
```

`plugins/design/skills/massing/scripts/massing.py` (after plan 001): `centres` is a list of `(props, geom)`; `main_centre` the main one's geometry. The community block (originally lines 209-267) picks `school_court = min(cand, key=lambda c: c.distance(main_centre))` among courtyards whose ring buildings can give way, removes those buildings, places a school bar 14 m deep along the plot side nearest the main centre, grows a yard and a sports ground; then `pool_court` the same way with a hall. `OPTIONAL` holds `school_gfa, school_yard, school_sports, pool_gfa, pool_plot, daycare_gfa, daycares, food_market`. Open spaces of the centres are written (originally lines 393-402):

```python
for p, g in centres:
    c = g.representative_point()
    sq = box(c.x - CONFIG['square'] / 2, c.y - CONFIG['square'] / 2, c.x + CONFIG['square'] / 2, c.y + CONFIG['square'] / 2)
    sq_all.append(sq)
    add('open-space', sq, use='square', name=p['name'])
    rest = g.difference(sq)
    if rest.area > 50: add('open-space', rest, use='park', name=p['name'] + ' (centre ground)')
```

`areas.csv` rows (originally lines 441-451) list homes, housing, commerce, daycare, school, schoolyard, school sports, pool, public green.

The run-5 helper's working patch (in `competition/proposals/2026-11-02_run-5/massing/massing.py` on the owner's computer, lines 99-103 and 227-294 there) is the shape to port. Its pieces: `centre_for(word)` returns the centre whose `holds` contains the word, else the main centre; `_centre_land(c)` is the centre polygon minus its square, the street buffers and the kept-building buffers; `_place(R, area, depth, anchor)` slides a rectangle of `area` m² and `depth` m, long side along the grid bearing, over `R` in 4 m steps and keeps the one nearest `anchor` that lies inside `R`; `_grow(R, core, target)` grows a ring around `core` inside `R` until it holds `target` m². It built the school and the pool on their centres and subtracted `COMMUNITY_LAND` from the centre ground.

## Scope

**In scope**: `plugins/concept/skills/structure-plan/SKILL.md`, `plugins/design/skills/massing/scripts/massing.py`, `plugins/design/skills/massing/scripts/config.example.json`, `plugins/design/skills/massing/SKILL.md`, `plugins/design/TOPIC.md`, `tests/test_scripts.py`.

**Out of scope**: the mobility skill, `draw.py`, `tests/synthetic.py` (it already writes `holds` on both centres).

## Steps

### Step 1: The contract in the structure plan

In `structure-plan/SKILL.md`, change the `centre` line to:

`- `centre` (polygon), `level` main or local, and `holds`: in words, what the brief or the narrative puts there (the stop, a bus station, shops, a market, a school, a daycare, a pool), so the massing builds it on that centre`

In `plugins/design/TOPIC.md` add after the first bullet: `- A community building the brief asks for goes on the structure plan's centre whose `holds` names it; `massing` lists them in its `config.json`.`

### Step 2: The massing reads `holds`

In `massing.py`:

1. Add to `OPTIONAL`: `'community_buildings': []`. Each entry is a dict `{"use": "bus station", "gfa": 2500, "floors": 2, "ground_m2": 6000, "at": "bus station", "depth": 20}` (`at` is a word to find in a centre's `holds` or a centre's name; `depth` optional, default 14; `ground_m2` optional, the plot including its open ground).
2. Port `centre_for(word)` (case-insensitive search in `holds` as text or list, then in `name`; returns the main centre when nothing matches and warns in a list `WARN`), `_centre_land`, `_place` (use the neighbourhood's grid bearing when the centre lies in a built neighbourhood, else 0), `_grow`.
3. Before the school block, place every `community_buildings` entry: `R, sq = _centre_land(centre_for(e['at']))`; `g = _place(R, e['gfa'] / e['floors'], e.get('depth', 14), sq)`; if `g` is None, try `depth` 10 and then the largest rectangle that fits by scaling; if still none, append to `WARN` "no room for <use> on <centre name>" and skip. Append `dict(geom=g, t='community', nb=<centre name>, fixed=True, use=e['use'], type=e.get('type', 'community'), floors=e['floors'], phase=None)` to `buildings`; grounds `_grow(R, g, max(0, e.get('ground_m2', 0) - g.area))` → `community.append(('square' if any(w in e['use'] for w in ('station', 'hub', 'market')) else 'park', e['use'] + ' grounds', grounds))`.
4. School and pool: when `centre_for('school')` is not the main centre (a centre holds it) → build the school on that centre's land with `_place`, yard by `_grow(…, school_yard)`, sports by `_place` with depths 40/50/60 then the largest free piece (the run-5 logic); else today's courtyard logic. Same for the pool with `'pool'`. Mark `SCHOOL_DONE`/`POOL_DONE` so the courtyard logic is skipped.
5. `COMMUNITY_LAND = unary_union(all community grounds + fixed buildings)`; in the centre open-space loop use `rest = g.difference(sq).difference(COMMUNITY_LAND)`; in `green_land` subtract it too.
6. `areas.csv`: one row per `community_buildings` entry: `(e['use'] + ' floor area', e['gfa'], gfa of that building or 0, source from `SOURCE.get('community_buildings', '')`)`.
7. `stats`: `'community': {use: placed True/False}`, `'warnings': WARN`. Write `WARN` lines into `assumptions.md` under `## Warnings`.
8. The old `food_market` note stays as it is.

### Step 3: Template and skill text

`config.example.json`: add

```json
 "community_buildings": {
  "value": [
   {"use": "bus station", "gfa": null, "floors": 2, "ground_m2": null, "at": "bus station"},
   {"use": "market hall", "gfa": null, "floors": 1, "at": "market"}
  ],
  "source": "optional: every community building the brief asks for, with its page; `at` is a word in a centre's `holds`"
 },
```

`massing/SKILL.md`, the **Uses.** bullet: replace "The community buildings the programme lists, such as a school, go on the structure plan's community land with their yards and sports;" by "The community buildings the brief asks for (a hub or bus station, a market, a school, a pool) are listed in `config.json` as `community_buildings` and built on the structure plan's centre whose `holds` names them, with their grounds; a school or pool without such a centre takes the nearest courtyard block;". Keep the daycare sentence.

### Step 4: Tests

In `tests/test_scripts.py` with `make_proposal` (centre "Square" holds "stop, bus station, shops"; centre "Corner" holds "school, daycare"):

- `test_massing_builds_what_the_centre_holds`: config adds `community_buildings = {"value": [{"use": "bus station", "gfa": 2000, "floors": 2, "ground_m2": 4000, "at": "bus station"}], "source": "test"}` → a new building with `use == 'bus station'` exists, its footprint lies within the "Square" centre polygon buffered 1 m, it overlaps no other building (pairwise intersection area < 1), and an `open-space` with `type == 'bus station grounds'` exists.
- `test_massing_school_on_the_centre_that_holds_it`: the fixture config already has `school_gfa` etc. → the `school` building lies within the "Corner" centre polygon buffered 1 m.
- `test_massing_without_holds_falls_back`: `make_proposal(tmp, holds=False)` → exit 0 and the school still exists (courtyard logic) and `stats['warnings']` is a list.

**Verify**: `python -m pytest tests/test_scripts.py -q` → 0 failed; `python -m pytest tests -q` → 0 failed.

## Done criteria

- [ ] `python -m pytest tests -q` → 0 failed.
- [ ] `grep -n "holds" plugins/concept/skills/structure-plan/SKILL.md plugins/design/skills/massing/SKILL.md plugins/design/skills/massing/scripts/massing.py plugins/design/TOPIC.md` finds all four.
- [ ] On run-3 inputs (if present; its structure plan has no `holds` and the config no `community_buildings`), `stats['n_new']` equals plan 001's number.
- [ ] `git status --short` shows only in-scope files changed (plus the owner's six pre-existing modified files).

## STOP conditions

- The community block doesn't match the excerpt.
- `_place` finds no room for the test bus station on the synthetic "Square" centre (60 × 60 m minus a 30 m square): then shrink the test's `gfa` to 1200 once; if it still fails, STOP and report the land left.
- A change seems needed in `tests/synthetic.py`: don't; report.

## Maintenance notes

- Plan 008 (mobility script) reads the massing's `use` values containing "station" or "hub" to place the hub symbol on the building; keep those words in `use`.
- A reviewer should check that community buildings are `fixed=True` (excluded from the height solver) and that `COMMUNITY_LAND` is subtracted from the centre ground and the public green.
