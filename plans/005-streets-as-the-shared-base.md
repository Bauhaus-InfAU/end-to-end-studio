# Plan 005: Every drawing takes the street surface from the streets skill instead of thickening lines itself

> **Executor instructions**: Read `plans/000-shared-context.md` first. Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. Do not update `plans/README.md`: the reviewer maintains it.
>
> **Drift check (run first)**: `git diff --stat 98cdb74..HEAD -- plugins/drawings/skills/isometric plugins/design/skills/open-space plugins/drawings/skills/perspective plugins/design/skills/mobility plugins/design/skills/streets` prints nothing. `git status --short plugins/drawings/skills/isometric` shows `M .../isometric.py` (the owner's uncommitted north-arrow edit; keep it, build on the file as it is). Otherwise STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (plan 001's `tests/synthetic.py` is used by the tests; if it doesn't exist yet, write the tests against `competition/proposals/2026-11-02_run-5` with a skip)
- **Category**: tech-debt (duplicated logic) + quality of the drawings
- **Planned at**: commit `98cdb74`, 2026-11-03

## Why this matters

The streets skill turns the existing streets and the design's new ones into one clean surface with rounded corners, and nobody reads it: no skill or script in `plugins/` opens `streets/streets.geojson`. Instead four scripts carry their own table of street widths by road class and buffer the lines themselves (`streets.py:27`, `open_space.py:26`, `isometric.py:126`, `perspective/scripts/scene.py:29`), and each plan shows a different street layer, with notches at junctions and roads through buildings. After this plan the isometric, the open-space plan, the perspectives and the mobility plan read the streets surface when it exists, and fall back to their own buffers only when it doesn't (a skill must still work alone).

## Current state

`plugins/design/skills/streets/SKILL.md` (`Reads: site-kit, massing, drawing-graphics`) writes `streets/streets.geojson` with features: `street` polygons (`use` street or square, `existing` true/false, `source`), `path` polygons or lines (`existing`, `type`), `centreline` lines (`level`, `width`, `width_source`, `name`, `existing`), `street-end` points. It runs in 8 steps for about $0.13.

`plugins/drawings/skills/isometric/isometric.py:122-137`:

```python
# streets as surfaces: the massing's widths, else assumed by class
WIDTH = {"motorway": 28, "trunk": 22, ...}
surf, assumed = [], set()
for p, g in layer("streets"):
    ...
    surf.append(rot(g).buffer(w / 2, cap_style=2, join_style=2))
for f in mass:
    p = f["properties"]
    if p.get("kind") == "street":
        g = rot(transform(tr, shape(f["geometry"])))
        surf.append(g if g.geom_type.endswith("Polygon") else g.buffer(float(p.get("width") or 16) / 2, cap_style=2))
if surf:
    svg.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.5" fill-rule="evenodd"/>' % (poly_d(unary_union(surf)), S["street"], S["street_line"]))
```

Its summary's third line names the assumed widths. Its `SKILL.md` has `Reads: site-kit, drawing-graphics` and `Reads (end): massing`.

`plugins/design/skills/open-space/scripts/open_space.py:127-148, 159-161`: `mass_streets` buffers massing `street` lines by their width; `old_streets` buffers the site's streets by `cfg["street_widths_m"]`; `streets = unary_union(mass_streets + old_streets).intersection(site)`. Retention later uses `mass_streets` pieces as new sealed surfaces (line 213). Its argparse is at lines 90-100 (`--site --layers --massing --config --out --structure --keep-free --style`). Its `SKILL.md` `Reads: brief-reader, programme, massing, structure-plan, climate, analysis, drawing-graphics`.

`plugins/drawings/skills/perspective/scripts/scene.py:411-424` buffers the site's streets by `self.assumed["street_width"]` into `self.flats` with tag `"old_street"` and warns how many widths were assumed; `"new_street_width": 12` at line 34 is used where the massing's streets are drawn (find it with `grep -n "new_street" plugins/drawings/skills/perspective/scripts/*.py`). The scene knows `self.proposal` (a Path) and `self.read(name)` for site layers. Its `SKILL.md` `Reads: massing, drawing-graphics, narrative`.

`plugins/design/skills/mobility/SKILL.md` (13 lines, no script yet) `Reads: brief-reader, structure-plan, massing, drawing-graphics`.

`tests/test_order.py::test_no_cycles` checks the `Reads:` graph has no cycle (streets reads massing; isometric's `Reads (end)` is not parsed by that test, only `Reads:`).

## Scope

**In scope**: `plugins/drawings/skills/isometric/isometric.py`, `plugins/drawings/skills/isometric/SKILL.md`, `plugins/design/skills/open-space/scripts/open_space.py`, `plugins/design/skills/open-space/SKILL.md`, `plugins/drawings/skills/perspective/scripts/scene.py`, `plugins/drawings/skills/perspective/SKILL.md`, `plugins/design/skills/mobility/SKILL.md`, `plugins/design/TOPIC.md`, `plugins/drawings/TOPIC.md`, `tests/test_streets_base.py` (create).

**Out of scope**: `streets.py` itself, `massing/scripts/draw.py` (the massing runs before streets, so its check plan can't read it; plan 006 puts a proper plan on the panels), `panel-layout`, `tests/test_order.py`.

## Steps

### Step 1: Isometric

In `isometric.py`, before the `WIDTH` block, add:

```python
streets_path = os.path.join(a.proposal, "streets", "streets.geojson")
street_feats = load(streets_path)   # the streets skill's surface, when it exists
```

Then: if `street_feats` is non-empty, build `surf` from its `street` polygons (rotate with `rot`, in metres via `transform(tr, shape(...))`) and draw `path` features (polygons filled `S["street"]`, lines stroked `S["street_line"]` width 0.4) and skip the `WIDTH` loop entirely (`assumed` stays empty); else the current code. In the summary's third line, write `streets from streets/streets.geojson` instead of the assumed-width list when it was used.

`SKILL.md`: change `Reads (end): massing` to `Reads (end): massing, streets`, and in **What it shows.** change "streets as surfaces at their width" to "the streets skill's surface when it exists, else streets at their width".

**Verify**: `python plugins/drawings/skills/isometric/isometric.py competition/site competition/proposals/2026-11-02_run-5 3000 564 --style competition/proposals/2026-11-02_run-5/isometric/style.json` (if run-5 exists) prints a summary whose third line contains `streets from streets/streets.geojson`. The output goes into run-5's `isometric/`: that is the owner's run folder; restore it afterwards by re-running nothing (the files are regenerated drawings; say in your report that run-5's isometric was redrawn).

Better: copy run-5 to a scratch folder first (`C:\Users\egayd\AppData\Local\Temp\claude\plan005\run5`) and run there. Do that.

### Step 2: Open space

In `open_space.py` add `ap.add_argument("--streets", help="the streets skill's streets.geojson; its surface replaces the buffered lines")`. After `mass_streets`/`old_streets` are computed: if `a.streets` is given and the file exists, load it, and set `old_streets = [polygons with existing True]`, `mass_streets = [polygons with existing False]`, both in metres and `.intersection(site)`; record `("streets", "from streets.geojson")` in `used_defaults`' neighbour list so `assumptions.md` says `streets: from the streets skill`. Keep `noisy` from the site layer (it needs `highway` tags).

`SKILL.md`: `Reads:` add `streets`; in the run line add `[--streets <proposal>/streets/streets.geojson]` and one sentence: "Pass the streets skill's file when it exists, so the plan shows the same street surface as every other drawing."

**Verify**: on the scratch copy of run-5, `python plugins/design/skills/open-space/scripts/open_space.py --site competition/site/site.geojson --layers competition/site --massing <copy>/massing/massing.geojson --config <copy>/open-space/config.json --out <copy>/open-space --streets <copy>/streets/streets.geojson --style <copy>/drawing-graphics/style.json` → exit 0, `<copy>/open-space/assumptions.md` contains `streets`.

### Step 3: Perspective

In `scene.py`, where the site's streets are buffered (lines 411-424), first look for `self.proposal / "streets" / "streets.geojson"`; when it exists, add its `street` polygons with `existing` True as `"old_street"` flats (order 65) and `existing` False as `"new_street"` flats (same order as the massing's new streets are drawn today; find that code with grep and give the streets-file polygons precedence over buffering the massing's lines), and its `path` polygons as `"old_street"`; set `assumed_w = 0`, append `"streets/streets.geojson"` to `self.used`, and skip the buffering. Otherwise the current code.

`SKILL.md`: `Reads:` add `streets`; in **Inputs** add "`streets/streets.geojson` for the street surface when it exists".

**Verify**: `python plugins/drawings/skills/perspective/scripts/perspective.py <copy> --site competition/site --count 1 --no-terrain` → exit 0 and `<copy>/perspective/assumptions.md` (or the summary) names `streets/streets.geojson`.

### Step 4: Mobility and the topic pages

`mobility/SKILL.md`: `Reads:` add `streets`; add one sentence to the second paragraph: "Take the street surface and the centrelines from `streets/streets.geojson` when it exists, for the plan's base and the walking network."

`plugins/design/TOPIC.md`: add a bullet `- `streets` writes the one street surface (`streets/streets.geojson`); a skill that draws streets reads it when it exists and buffers lines only without it.` `plugins/drawings/TOPIC.md`: same sentence after the "How:" bullet.

**Verify**: `python -m pytest tests/test_order.py -q` → passes (no cycle: streets reads massing; isometric, open-space, perspective, mobility read streets).

### Step 5: Tests

Create `tests/test_streets_base.py`:

- A fixture that makes a small `streets.geojson` in WGS84 inside the site: one `street` polygon (`existing: true`), one `street` polygon (`existing: false`), one `path` line; write it to `<tmp proposal>/streets/streets.geojson`. Use `tests/synthetic.py`'s proposal when it exists (plan 001), else a bare folder with the site copied and a minimal `massing/massing.geojson` holding one `building` polygon (then skip the open-space test).
- `test_isometric_uses_streets_file`: run `isometric.py` on it → `isometric/summary.md` contains `streets from streets/streets.geojson`.
- `test_open_space_accepts_streets`: run `open_space.py --streets ...` with the massing from the synthetic run (run `massing.py` first) and a config with `residents, green_m2_per_resident, play_m2_per_resident, play_min_m2, scale` → exit 0 and `assumptions.md` contains `streets`.
- `test_reads_lines_name_streets`: the `Reads` or `Reads (end)` line of isometric, open-space, perspective and mobility contains `streets`.

**Verify**: `python -m pytest tests/test_streets_base.py tests/test_order.py -q` → 0 failed; `python -m pytest tests -q` → 0 failed.

## Done criteria

- [ ] `python -m pytest tests -q` → 0 failed.
- [ ] `grep -rn "streets/streets.geojson\|streets.geojson" plugins/drawings/skills/isometric/isometric.py plugins/design/skills/open-space/scripts/open_space.py plugins/drawings/skills/perspective/scripts/scene.py` finds a reader in each.
- [ ] Each of the four `SKILL.md` files names `streets` in its `Reads` or `Reads (end)` line.
- [ ] The owner's north-arrow edit in `isometric.py` (circle and line, no letter) is still there: `grep -n "a circle in outline" plugins/drawings/skills/isometric/isometric.py` finds it.
- [ ] `git status --short` shows only in-scope files changed (plus the owner's six pre-existing modified files).

## STOP conditions

- `isometric.py` or `scene.py` don't match the excerpts.
- `scene.py`'s drawing of the massing's new streets can't be found with grep: STOP and report what the massing streets are called there.
- A change seems needed in `streets.py`: don't; report.

## Maintenance notes

- Plan 006 (the plans skill) and plan 008 (mobility script) read `streets/streets.geojson` the same way; keep the reading idiom (polygons by `kind` and `existing`).
- Reviewer: make sure every fallback path (no streets file) still runs, since a skill must work alone.
