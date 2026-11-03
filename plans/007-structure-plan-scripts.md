# Plan 007: The structure plan gets a frame, a checker and a tracer in `scripts/`, so the helper writes the design, not the plumbing

> **Executor instructions**: Read `plans/000-shared-context.md` first. Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. Do not update `plans/README.md`: the reviewer maintains it.
>
> **Drift check (run first)**: plan 004 must be DONE (it adds `holds` to the structure-plan contract). `git diff --stat 98cdb74..HEAD -- plugins/concept/skills/structure-plan` shows only `SKILL.md` changed (by plan 004). `ls plugins/concept/skills/structure-plan/scripts` must not exist. Otherwise STOP.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/004-centres-hold-community-buildings.md
- **Category**: perf (cost per run) + repeatability
- **Planned at**: commit `98cdb74`, 2026-11-03

## Why this matters

The structure plan is the most expensive skill of every run ($4.66 in run-5, $2.21 in run-4, $3.11 in run-3) because it has no scripts: each time, the helper writes 400+ lines of Python from scratch (loading the site in local metres, land-use helpers, a feature writer that validates geometry and adds areas, the checks, a check plan) before it designs anything, and it does it differently each run. The design itself (which land becomes which neighbourhood, where the centres and green lines go) is the helper's job and stays so. After this plan the plumbing is three scripts in the skill folder; the helper writes only a short `design.py` of geometry decisions, runs it through the frame, and the checks and the check plan come for free.

## Current state

`plugins/concept/skills/structure-plan/SKILL.md` (22 lines after plan 004): `Reads: narrative, climate`, `Model: opus`; writes `structure-plan.geojson` with features `neighbourhood` (polygon), `centre` (polygon, `level`, `holds`), `green` (polygon, `roles`), `route` (line, `level` main/local/landscape), `gateway` (point); every feature has `kind`, `name`, `action` (keep, change, new), `basis` (documented, brief, mapped, hypothesis), `source`. "Check the geometry with shapely and pyproj in a metric projection; no Rhino, no drawings." The summary's second line is "the share of neighbourhood area within a distance you state of a centre or green, ... labelled as straight-line proximity".

The run-5 helper's scripts (owner's computer, `competition/proposals/2026-11-02_run-5/structure-plan/`): `build.py` (243 lines) does all of the below in one file; its reusable parts are:

```python
site_w = transform(fw, shape(json.load(open(S + '/site.geojson'))['features'][0]['geometry']))
X0, Y0 = site_w.bounds[:2]
L = lambda g: transform(lambda x, y, z=None: (x - X0, y - Y0), g)      # UTM -> local metres from the site's SW corner
W = lambda g: transform(bw, transform(lambda x, y, z=None: (x + X0, y + Y0), g))
plots = [(f['properties'], L(transform(fw, shape(f['geometry']))).buffer(0)) for f in ...plots.geojson]
streets = [(f['properties'], L(transform(fw, shape(f['geometry'])))) for f in ...streets.geojson]
rail = unary_union([...rail.geojson])
def lu(*kinds): return unary_union([g for p, g in plots if p.get('landuse') in kinds]).intersection(site)
def street(prefix, hw=None): return unary_union([g for p, g in streets if (p.get('name') or '').startswith(prefix) and (hw is None or p.get('highway') in hw)])
def strip(coords, w): return LineString(coords).buffer(w / 2, cap_style=2, join_style=2).intersection(site)
noise = {f['properties']['kind']: ... for f in climate/rules.geojson if topic == 'noise' and kind in ('dont', 'careful')}
def add(props, g):   # drops empties, keeps polygons of polygon kinds and lines of route kinds, make_valid, area_ha / length_m, simplify 0.5 m, to WGS84
```

and the checks it printed: neighbourhood areas by action with their noise overlap, green areas and roles, the share of new neighbourhood area within 150/300/400 m of public green or a centre, slivers left unassigned, feature counts. It also made `check_plan.png` with matplotlib (not allowed by STUDIO.md: "No plotting library"). `georef.py` (64 lines) placed the brief's plan images on the site with a similarity fit from four control points and pulled coloured overlays out as polygons with OpenCV; its control points and colour rules are brief-specific and belong in a config.

The site folder's layers (`plans/000-shared-context.md`): `site.geojson`, `buildings.geojson`, `plots.geojson` (`landuse`), `streets.geojson` (`highway`, `name`), `water.geojson`, `rail.geojson`, `kit.json`. The climate folder (optional): `rules.geojson` with `topic` and `kind`.

Pattern for a script with a config: `plugins/design/skills/massing/scripts/massing.py` (`DEFAULTS`, `read_config`, `utm_epsg`). Pattern for a drawing with a PNG: `massing/scripts/draw.py` (`shot`).

## Scope

**In scope** (create or modify):

- `plugins/concept/skills/structure-plan/scripts/frame.py` (create)
- `plugins/concept/skills/structure-plan/scripts/build.py` (create)
- `plugins/concept/skills/structure-plan/scripts/check.py` (create)
- `plugins/concept/skills/structure-plan/scripts/georef.py` (create)
- `plugins/concept/skills/structure-plan/scripts/design.example.py` (create)
- `plugins/concept/skills/structure-plan/SKILL.md`
- `tests/test_structure_plan.py` (create), `tests/test_scripts.py` (`NEW_SCRIPTS`)

**Out of scope**: `plugins/concept/TOPIC.md`, the massing, `tests/synthetic.py`.

## Steps

### Step 1: `frame.py`

A module with class `Frame(site_dir, climate_dir=None)`:

- Loads the site in the UTM zone of its centroid, keeps `self.site` (polygon in local metres from the site's SW corner, so a designer's coordinates are small numbers), `self.to_local(lon, lat)`, `self.to_wgs(geom)`, `self.plots`, `self.streets`, `self.buildings`, `self.rail` (union), `self.water` (union), `self.noise` (dict `kind -> geometry` from the climate's `rules.geojson` where `topic == 'noise'`, else `{}`).
- Helpers: `lu(*landuse)`, `street(name_prefix, highway=None)`, `strip(coords, width)`, `box(x0, y0, x1, y1)`, `point(x, y)`, `line(coords)`.
- `add(kind, name, geom, action, basis, source, **props)`: validates `kind in {neighbourhood, centre, green, route, gateway}`, `action in {keep, change, new}`, `basis in {documented, brief, mapped, hypothesis}`, a non-empty `name`; a `centre` needs `level` in {main, local} and `holds` (a warning, not a stop, when `holds` is missing: "centre <name> says nothing it holds; the massing can build nothing there"); a `green` needs `roles` (list); a `route` needs `level` in {main, local, landscape}. Cleans geometry like run-5's `add` (make_valid, keep the right geometry type, `area_ha` / `length_m`, simplify 0.5 m), stops with `SystemExit('<kind> <name>: <what is wrong>')` on a bad value or an empty geometry.
- `write(path)`: the FeatureCollection in WGS84 (`"crs_note": "WGS84, longitude first"`), and returns the warnings list. Stops with "no main centre" if none has `level == 'main'`, and "no neighbourhood with action new or change" if none.

### Step 2: `build.py`

`python build.py <design.py> --site <site folder> --proposal <proposal folder> [--climate <folder>]`: makes a `Frame`, runs the design file with `exec(compile(...))` in a namespace holding `F` (the frame) and the shapely names (`Point, LineString, Polygon, box, unary_union`), then calls `F.write(<proposal>/structure-plan/structure-plan.geojson)`, prints the warnings, then runs the checks of `check.py` and writes `checks.txt` and the check plan. The design file is the only thing the helper writes; it must not import or open files itself (document that in the skill).

### Step 3: `check.py`

`python check.py --proposal <folder> --site <site folder> [--climate <folder>] [--distance 150] [--style style.json]`, also importable by `build.py`. Writes `structure-plan/checks.txt` and `check-plan.svg` + `.png`:

- Neighbourhoods: name, action, area in ha, and if noise exists its overlap with each noise kind; the total new area; slivers of the site assigned to nothing (site minus neighbourhoods, greens, route buffers of 10 m) in ha.
- Greens: name, action, area, roles; total public green (features without `public: false`).
- Centres: name, level, area, `holds`.
- Proximity: share of new neighbourhood area within `--distance` m (straight line) of a public green or a centre, and of a centre alone; the pieces beyond, with their area and local coordinates.
- Routes: name, level, length; routes whose ends lie more than 20 m from every other route, the site boundary or a gateway (loose ends).
- Geometry: invalid features (0 expected), features with empty geometry.
- The check plan: SVG at 1:10,000 (`DEFAULTS['check_scale']`), neighbourhoods in pale greys by action, greens in a green, centres in the accent, routes as lines by level, gateways as circles, names as labels ≥ 3.2 mm, the site dashed; a legend; PNG with `shot`. Fallback look black on white; the style keys of rule 5 override.

### Step 4: `georef.py`

`python georef.py --site <site folder> --image <png> --points <points.json> --out <proposal>/structure-plan/traced.geojson [--colours colours.json]`: a generic tracer for a plan picture from a brief. `points.json`: a list of at least three `{"px": [x, y], "lonlat": [lon, lat], "what": "..."}`; the script fits a similarity transform (scale, rotation, shift) by least squares (the maths of run-5's `georef.py`: `A += [[x, -y, 1, 0], [y, x, 0, 1]]`), prints the residual of each point in metres, and stops when the largest residual exceeds `DEFAULTS['max_residual_m']` (40). `colours.json`: `{"name": {"min": [r, g, b], "max": [r, g, b]}}`; for each named colour the pixels in the range are closed morphologically (`DEFAULTS['close_px']` 15), contoured with OpenCV and written as polygons in WGS84 with `colour` and `area_m2`; without `--colours` only the fitted outline of the image is written. Needs `opencv-python-headless`; without `cv2` it stops with `pip install opencv-python-headless`. Writes `georef.md` next to the output: the fit, the residuals, the colours and their areas.

### Step 5: `design.example.py`

A commented example that works on any site: one neighbourhood from the farmland in the site's largest piece, one main centre where the main street meets it, one green strip, one route, one gateway, each `F.add(...)` with `action`, `basis`, `source` and `holds`. It must not contain a place name.

### Step 6: The skill text

In `SKILL.md`, replace "Don't copy the site's layers. Check the geometry with `shapely` and `pyproj` (`pip install shapely pyproj`) in a metric projection; no Rhino, no drawings." by:

> **Start from the scripts.** Write your decisions as `structure-plan/design.py` in the proposal folder, after `${CLAUDE_SKILL_DIR}/scripts/design.example.py`: each neighbourhood, centre, green, route and gateway as one `F.add(...)` with its action, basis, source and, for a centre, what it holds; `F.lu`, `F.street` and `F.strip` give you the site's land uses, streets and strips in metres. Run `python "${CLAUDE_SKILL_DIR}/scripts/build.py" <proposal>/structure-plan/design.py --site <site folder> --proposal <proposal> --climate <climate folder>`: it writes `structure-plan.geojson`, `checks.txt` and `check-plan.png`. Read the checks, change `design.py`, run again. To take a plan from the brief's pictures, `scripts/georef.py` places a picture on the site from three or more points you name and pulls its colours out as polygons. Don't copy the site's layers; `pip install shapely pyproj`, no Rhino.

Keep the summary's three lines; the proximity share now comes from `checks.txt`.

### Step 7: Tests

`tests/test_structure_plan.py`:

- `test_example_design_builds`: run `build.py` with `design.example.py` on `competition/site` into a tmp proposal (folder with a space) → exit 0, `structure-plan.geojson` has the five kinds, `checks.txt` has the lines `NEIGHBOURHOODS`, `GREEN`, `CENTRES`, `share`, `check-plan.png` exists.
- `test_bad_action_stops`: a design file with `action='maybe'` → non-zero exit, `maybe` in stderr.
- `test_centre_without_holds_warns`: a design with a centre lacking `holds` → exit 0 and `says nothing it holds` in stdout.
- `test_no_main_centre_stops`: → non-zero exit, `main centre` in stderr.
- `test_georef_fit`: a 200 × 200 synthetic PNG made with PIL (a red square), three points mapping its corners to three site corners → exit 0, residuals < 1 m in `georef.md`, with a colours file the red square comes out as one polygon.
- Add the four scripts to `NEW_SCRIPTS` in `tests/test_scripts.py`.

**Verify**: `python -m pytest tests/test_structure_plan.py tests/test_scripts.py::test_no_site_in_new_scripts tests/test_order.py -q` → 0 failed; `python -m pytest tests -q` → 0 failed.

## Done criteria

- [ ] `python -m pytest tests -q` → 0 failed.
- [ ] `python plugins/concept/skills/structure-plan/scripts/build.py plugins/concept/skills/structure-plan/scripts/design.example.py --site competition/site --proposal <tmp>` → exit 0 and the three outputs exist.
- [ ] No plotting library imported: `grep -rn "matplotlib\|plotly" plugins/concept/skills/structure-plan/scripts` returns nothing.
- [ ] `grep -n "build.py\|design.py\|georef.py" plugins/concept/skills/structure-plan/SKILL.md` finds all three.
- [ ] `git status --short` shows only in-scope files changed or added (plus the owner's six pre-existing modified files).

## STOP conditions

- `competition/site/plots.geojson` has no `landuse` field (the example design can't find farmland): report.
- `cv2` import fails here (it is installed at planning time): STOP and report.
- A change seems needed in the massing to read anything new: don't; the contract (plan 004) already covers `holds`.

## Maintenance notes

- The helper still runs on Opus (`Model: opus` stays: dividing a site is judgment). Its cost should fall to what `design.py` costs to write.
- Reviewer: `frame.py` must hold no site, street or brief number; `design.example.py` must not name a place.
