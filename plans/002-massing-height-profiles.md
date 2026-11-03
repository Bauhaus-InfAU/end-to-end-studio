# Plan 002: Heights vary by a profile per neighbourhood instead of one factor that lands everything on the cap

> **Executor instructions**: Read `plans/000-shared-context.md` first. Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. Do not update `plans/README.md`: the reviewer maintains it.
>
> **Drift check (run first)**: plan 001 must be DONE in `plans/README.md`. Then confirm `grep -n "def figure_for\|def type_for\|row=ys.index" plugins/design/skills/massing/scripts/massing.py` finds all three; if not, STOP (plan 001 did not land as written).

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-massing-figure-from-config.md
- **Category**: direction (quality of the design)
- **Planned at**: commit `98cdb74`, 2026-11-03

## Why this matters

Every home building gets the same base floors for its density, then one factor scales them all until the home count is met, then the cap cuts them: 124 of 137 buildings in run-4 and 84 of 152 in run-5 stood at the 6-floor limit. The only variation is plus one floor near a main route or the centre and minus one beside the green. The result reads as one height everywhere. After this plan the narrative can ask for a profile per neighbourhood (rising to the centre, rising away from the green, alternating rows) and a floor range, the solver works within it, and the script says plainly when the programme doesn't fit under the cap instead of silently maxing out.

## Current state

`plugins/design/skills/massing/scripts/massing.py` after plan 001. The heights block (originally lines 270-280, now a little lower):

```python
# ---------- heights ----------
for b in buildings:
    if b.get('fixed'):
        continue
    f = b['fl0']
    if b['geom'].distance(main_routes) <= CONFIG['route_bonus_m']: f += 1
    if b['geom'].distance(main_centre) <= CONFIG['centre_bonus_m']: f += 1
    if b['geom'].distance(green_u) <= CONFIG['green_minus_m']: f -= 1
    b['base'] = max(1, f)
    b['use'] = b['use0']
    if b['geom'].representative_point().within(loud):
        b['use'] = 'commerce'   # climate/rules.json: no homes at 65 dB(A) or more by day
```

`apply` and `solve` (originally lines 288-308):

```python
def apply(group, f):
    for b in group:
        cap = CONFIG['landmark_floors'] if b.get('landmark') else CAP
        b['floors'] = int(min(cap, max(1, round(b['base'] * f))))
        if b.get('landmark'): b['floors'] = cap
```

Then two bisections on `f` for the home group and the commerce group (originally lines 336-350), each ending with `f_res = min([lo, hi], key=...)`, which picks whichever side of the bisection is closer to the target. The run-5 helper changed that line to `f_res = hi` because the brief's home count was a minimum. `stats` (originally lines 462-470) already has `at_cap` and `n_home`. `assumptions.md` is written at the end of the file.

Each building dict carries, from plan 001: `t` (density key), `fl0`, `use0`, `type`, `nb` (neighbourhood name), `row`, `col`, `phase`.

## Scope

**In scope**: `plugins/design/skills/massing/scripts/massing.py`, `plugins/design/skills/massing/scripts/config.example.json`, `plugins/design/skills/massing/SKILL.md`, `tests/test_scripts.py`.

**Out of scope**: `draw.py`, every other skill, `tests/synthetic.py` (read it, don't change it).

## Steps

### Step 1: The profile words

In `massing.py`, after the base-floors loop above, add:

```python
# a height profile per neighbourhood (config figure.<name>.heights), applied to the base floors before the solver
PROFILES = ('flat', 'to centre', 'from green', 'alternate')
for name in {b['nb'] for b in buildings if not b.get('fixed')}:
    F = figure_for(name); prof = F.get('heights', 'flat')
    if prof not in PROFILES:
        sys.exit('figure.%s.heights "%s" is not one of %s' % (name, prof, ', '.join(PROFILES)))
    grp = [b for b in buildings if b['nb'] == name and not b.get('fixed')]
    if prof == 'to centre' and grp:           # the nearest third of the buildings one floor up, the farthest third one down
        order = sorted(grp, key=lambda b: b['geom'].distance(main_centre)); n = len(order)
        for b in order[:n // 3]: b['base'] += 1
        for b in order[n - n // 3:]: b['base'] -= 1
    elif prof == 'from green':                 # beside the green one down (done above), well away from it one up
        for b in grp:
            if b['geom'].distance(green_u) > 3 * CONFIG['green_minus_m']: b['base'] += 1
    elif prof == 'alternate':                  # every second row one floor lower
        for b in grp:
            if b.get('row', 0) % 2: b['base'] -= 1
    for b in grp:
        b['base'] = max(1, b['base'])
        b['fmin'] = int(F.get('floors_min', 1)); b['fmax'] = int(F.get('floors_max', CAP))
```

In `apply`, use the range: `cap = CONFIG['landmark_floors'] if b.get('landmark') else min(CAP, b.get('fmax', CAP))` and `b['floors'] = int(min(cap, max(b.get('fmin', 1), round(b['base'] * f))))`. Landmarks keep their override line.

### Step 2: A target that is a minimum

Add `'homes_target_is_minimum': False` to `OPTIONAL`. In the home bisection, replace the final `f_res = min([lo, hi], key=...)` line by:

```python
f_res = hi if CONFIG['homes_target_is_minimum'] else min([lo, hi], key=lambda f: (apply(home_grp, f), abs(sum(homes_m2(b) for b in buildings) - res_target))[1])
apply(home_grp, f_res)
```

(Keep the first `solve(home_grp, res_gfa, res_target)` call as it is; only the re-solve after the daycares decides.)

### Step 3: Say when it doesn't fit

After `stats` is built, add `stats['at_cap_share'] = round(stats['at_cap'] / max(1, stats['n_home']), 2)` and `stats['profiles'] = {name: figure_for(name).get('heights', 'flat') for name in CONFIG['density']}`. In `assumptions.md`, add a section `## Heights` with one line per neighbourhood (`- <name>: profile <word>, floors <fmin> to <fmax>`), and when `at_cap_share > 0.5` one more line: `- <at_cap> of <n_home> home buildings stand at the cap of <CAP> floors: the programme barely fits or does not fit under the height limit. More land in the structure plan, a lower m2 per home, or a higher limit would be needed.`

### Step 4: Template and skill text

`config.example.json`: inside the `figure` value's `"*"` entry add `"heights": "flat | to centre | from green | alternate", "floors_min": 2, "floors_max": 6`; after `phase1` add `"homes_target_is_minimum": {"value": null, "source": "optional: true when the brief's homes figure is a minimum, with its page"}`.

`SKILL.md`, the **Heights.** bullet: after "One floor more within 40 m of a main route and within 150 m of the centre, one less beside the green, unless the structure plan says otherwise." add: "A profile per neighbourhood in `figure` shapes it further: `to centre`, `from green` or `alternate` rows, within `floors_min` and `floors_max`; name the principle it comes from." And after "Then scale floors per use until the floor area meets the programme, within the brief's height limit;" add "if more than half the home buildings end at the cap, `assumptions.md` says the programme doesn't fit, so the structure plan can give more land;".

### Step 5: Tests

In `tests/test_scripts.py`, using `make_proposal`:

- `test_massing_heights_to_centre`: `figure = {"*": {"heights": "to centre", "floors_max": 5}}` → mean `floors` of the third of new buildings nearest the main centre (distance in UTM to the centre polygon from the synthetic structure plan) is at least 1 higher than the mean of the farthest third, and no building has more than 5 floors.
- `test_massing_heights_alternate`: `{"*": {"heights": "alternate"}}` → among new buildings with the same `col` and different `row`, at least one pair differs by exactly 1 floor.
- `test_massing_heights_unknown_stops`: `{"*": {"heights": "wavy"}}` → non-zero exit, `wavy` in stderr.
- `test_massing_assumptions_name_the_cap`: config with `homes_target` doubled → `assumptions.md` contains "stand at the cap".

**Verify**: `python -m pytest tests/test_scripts.py -q` → 0 failed; then `python -m pytest tests -q` → 0 failed.

## Done criteria

- [ ] `python -m pytest tests -q` → 0 failed.
- [ ] Running massing on run-3 inputs (if present) with the run-3 config gives the same `n_new` as plan 001 recorded (no profile → unchanged).
- [ ] `grep -n "at_cap_share\|homes_target_is_minimum\|PROFILES" plugins/design/skills/massing/scripts/massing.py` finds all three.
- [ ] `git status --short` shows only in-scope files changed (plus the owner's six pre-existing modified files).

## STOP conditions

- Plan 001's functions are missing (drift check).
- The run-3 same-result check changes `n_new` (heights must not move buildings).
- `to centre` cannot be tested because the synthetic proposal yields fewer than 6 buildings: report it rather than loosen the test.

## Maintenance notes

- The profile acts on `base` before the solver, so the solver's factor still meets the programme; a reviewer should check `apply` clamps with `fmin`/`fmax` and that landmarks are untouched.
- If plan 003 or 004 changes which buildings exist, these profiles follow automatically (they run after placement).
