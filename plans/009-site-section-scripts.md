# Plan 009: The site section comes from one script that reads the site's own terrain model

> **Executor instructions**: Read `plans/000-shared-context.md` first. Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. Do not update `plans/README.md`: the reviewer maintains it.
>
> **Drift check (run first)**: plan 001 must be DONE (for `tests/synthetic.py`). `git diff --stat 98cdb74..HEAD -- plugins/drawings/skills/site-section` prints nothing; `ls plugins/drawings/skills/site-section/scripts` must not exist. Otherwise STOP.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/001-massing-figure-from-config.md
- **Category**: perf (cost per run) + repeatability
- **Planned at**: commit `98cdb74`, 2026-11-03

## Why this matters

The site section runs twice per run (the site as it is, then on the design) and has no scripts, so each run writes five of them (591 lines in run-5, $1.03 for both runs), hard-codes the site path and projection into them, and fetches a 25 m terrain from the web although the site folder now holds a 1 m terrain model. After this plan one script does the cut, the ground, the buildings, the plants, the labels and the excerpt, reads the site's own terrain first, and the helper only chooses the line if the automatic one is poor.

## Current state

`plugins/drawings/skills/site-section/SKILL.md` (22 lines): `Reads: drawing-graphics, brief-reader`, `Reads (end): massing`. It specifies: one straight line A–A′ through the site that also crosses buildings and the main lines (railway, main streets, a river, the detail area if the brief names one), 200 m past the site at each end; the ground from a terrain model every 10 m or less, written to `profile.csv` with its source, no vertical exaggeration; buildings cut (strongest tone) and up to 80 m behind in elevation, each on the ground at its own footprint; plants by land use; labels once per crossing; site boundary in the accent; scale bar, A and A′, a key plan; the whole cut at the site plan scale and an excerpt of about 200 m at the brief's largest scale with floor lines and people; at the end the same again on the design with new buildings in the accent. Files: `site-section_<scale>.svg/.png`, `site-section_excerpt_<scale>.svg/.png`, `profile.csv`, `summary.md` (three lines: what and at which scales, the height difference, what is unsure).

The site folder: `terrain-dgm1.tif` (GeoTIFF, mode F float32, 2800 × 2900 cells of 1 m, tags: `33550` ModelPixelScale `(1.0, 1.0, 0.0)`, `33922` ModelTiepoint `(0, 0, 0, E, N, 0)`, `34735` GeoKeyDirectory containing key `3072` = the projected EPSG, here 25832); `kit.json` has `"terrain": "terrain-dgm1.tif"`; `SOURCES.md` names its licence line. PIL reads it: `Image.open(path)`, `im.tag_v2[33550]`, `im.tag_v2[33922]`, `im.tag_v2[34735]` (a flat tuple of 4-value groups `(key, location, count, value)`; the group with key 3072 gives the EPSG), `numpy.array(im)`. rasterio is not installed and must not be required. The fallback for any site without a tif: `terrain.csv` (`lon, lat, ele, source`) in the site folder, then `https://api.opentopodata.org/v1/eudem25m,mapzen` (the pattern is `plugins/drawings/skills/perspective/scripts/terrain.py`), then flat ground with a warning.

The run-5 helper's scripts (owner's computer, `competition/proposals/2026-11-02_run-5/site-section/`): `geom.py` (the cut line: a direction and an offset from the centroid, ±2000 m, clipped to the site ±200 m; the profile every 10 m from opentopodata; buildings within 80 m; `cut.json`), `prep_design.py` (new buildings and trees near the line from the massing), `draw.py` and `draw_design.py` (the drawing: ground polygon, cut buildings, elevations behind sorted far to near, plants by land-use class at the ground, crossings labelled once within 80 m, a key plan at 1:30,000, the excerpt), `png.py` (Chrome screenshot at 150 dpi). `geom.py` hard-codes `SITE='C:/Work/GitHub/end-to-end-studio/competition/site/'` and EPSG 25832: exactly what a skill script must not do.

Pattern for a script: `plugins/drawings/skills/isometric/isometric.py` (arguments, `STYLE` with `--style`, summary). Pattern for `DEFAULTS` and `read_config`: `plugins/design/skills/massing/scripts/massing.py`.

## Scope

**In scope** (create or modify):

- `plugins/drawings/skills/site-section/scripts/section.py` (create)
- `plugins/drawings/skills/site-section/scripts/terrain.py` (create)
- `plugins/drawings/skills/site-section/SKILL.md`
- `tests/test_site_section.py` (create), `tests/test_scripts.py` (`NEW_SCRIPTS`)

**Out of scope**: the perspective skill's `terrain.py` (leave it), every other skill, `requirements.txt`.

## Steps

### Step 1: `terrain.py`

A module with `class Terrain` built by `Terrain.find(site_dir, out_dir, bounds_utm, to_lonlat)`:

1. A GeoTIFF: any `terrain*.tif` in the site folder, or the file `kit.json`'s `terrain` names. Read with PIL as described; build `pyproj.Transformer` from the UTM used by the script to the tif's EPSG; `sample(xs, ys)` → bilinear interpolation on the array (numpy; cells outside → NaN → filled with the nearest valid value, counted as `gaps`). `source = "<file name> (<EPSG>, <cell> m)"`.
2. Else `terrain.csv` in the site folder (lon, lat, ele): nearest-point lookup with a `scipy`-free approach (a regular grid if the CSV is one, else inverse-distance of the 4 nearest by a `shapely.STRtree`). `source = "terrain.csv"`.
3. Else download from opentopodata along the needed points only (not a grid), batches of 100, 1.1 s apart, `requests`; write `terrain.csv` into the output folder; `source = "EU-DEM 25 m / Mapzen via api.opentopodata.org"`. On any failure, `flat = True`, `source = "flat (no terrain found)"` and `sample` returns zeros.

### Step 2: `section.py`

`python section.py --site <site folder> --proposal <proposal folder> --scale <site plan scale> --detail-scale <largest scale> [--massing] [--line lon,lat lon,lat] [--look <north|south|east|west>] [--at <lon,lat>] [--style style.json]`:

1. Load the site and layers in its UTM. `DEFAULTS`: `step_m` 10, `beyond_m` 200, `behind_m` 80, `tree_h` `{forest: 16, wood: 16, park: 10, scrub: 4}`, `person_h` 1.75, `floor_h` 3.0 (used only for existing buildings without floors), `excerpt_m` 200, `key_scale` 30000, `label_min_gap_m` 80, `land_classes` (landuse → built, forest, scrub, park, grass, water, street), `angles` 15 (degrees step for the automatic line).
2. The line. With `--line`, those two points. Else the automatic choice: for angles 0, 15, … 165 degrees and offsets −300, −150, 0, 150, 300 m from the site centroid (perpendicular), score the line inside the site by: number of buildings it cuts (weight 2, capped at 20), + 5 for each of rail, a `highway` in {motorway, trunk, primary, secondary}, water that it crosses, + 10 if it passes within 100 m of `--at` (a centre or detail area the helper gives), − 1 per 100 m of length beyond the longest candidate; take the best; record the choice and the runner-up's score in `cut.json`. Extend `beyond_m` past the site at both ends. The direction of looking: `--look`, else the side that puts A on the left for a reader (looking north for an east–west line, east for a north–south line).
3. The profile: points every `step_m` along the line; `Terrain.sample`; `profile.csv` with `t_m_from_A, lon, lat, z_m_asl, source`.
4. Buildings: the site's buildings and, with `--massing`, the massing's new buildings (`existing: false`, `height_m`, `floors`); kept existing ones under new buildings are left out (overlap > 20 % of the smaller). Cut ones (the line crosses the footprint): a box from the ground at the footprint's mean sampled height to that plus the height; behind ones (footprint within `behind_m`, wholly on the far side): an elevation box at their own ground, drawn far to near, lighter. Heights: `height` of the site data (or `floors × floor_h`, flagged as default), `height_m` of the massing.
5. Plants by land use under the line (sample the `plots` `landuse` every 10 m): trees as simple circles-on-sticks of `tree_h` on forest/park/scrub, grass ticks on grass; nothing on built or street classes.
6. Labels: each street (`name` or `ref`), rail ("Railway"), water crossed, once per `label_min_gap_m`; A and A′; the site boundary crossings as vertical accent lines; the ground line thick; the earth below hatched or filled `style['existing']`; heights above sea level as a small vertical scale at the left.
7. The whole section at `--scale` and the excerpt (`excerpt_m` around `--at`, else around the first place where a new building meets open ground, else the site's centre) at `--detail-scale` with floor lines and people (simple figures of `person_h` at entrances and on open ground, every 25 m). Each SVG with `width`/`height` in mm; PNG via the Chrome screenshot (`shot` of massing `draw.py`); a key plan at `key_scale` with the line and the site in the whole section's corner.
8. Files: `site-section_1-<scale>.svg/.png`, `site-section_excerpt_1-<detail>.svg/.png`, and with `--massing` the same with `_design` before the scale as in run-5 (`site-section_design_1-3000.svg`), `profile.csv`, `cut.json` (the line, the look direction, the scores, counts of cut and behind buildings, the ground's fall and rise), `assumptions.md`. The helper writes `summary.md`.
9. The look: `STYLE` with the keys of rule 5 and `--style`; cut buildings `ink`, behind `existing`, new buildings `accent`, ground line `ink` thick, earth `context`, plants `grove`, people `ink` thin. Text ≥ 3.2 mm at the scale.

### Step 3: The skill text

Replace the paragraphs **The cut.**, **The ground.**, **What it shows.** and **Large and small.** with one paragraph that keeps their rules as what the script does, plus: "Run `python "${CLAUDE_SKILL_DIR}/scripts/section.py" --site <site folder> --proposal <proposal> --scale <site plan scale> --detail-scale <largest scale> --style <proposal>/drawing-graphics/style.json`, and at the end again with `--massing`. It chooses the line itself (buildings, rail, main streets, water, the place you give with `--at`), takes the ground from the site folder's terrain model, else a terrain CSV, else a free elevation service, and says which in `profile.csv`. If the line it chose crosses nothing of interest, give your own with `--line` and say why in `summary.md`." Keep **The look.** and **What to write.**; add `cut.json` and `assumptions.md` to the files. Keep the file under 25 lines.

### Step 4: Tests

`tests/test_site_section.py` (on `competition/site`, which has the tif; output in a tmp folder with a space):

- `test_section_site_as_is`: no `--massing` → exit 0; four files exist; `profile.csv` has > 100 rows and its `source` column names `terrain-dgm1.tif`; `cut.json` `fall_m + rise_m > 5` (the site is not flat); every SVG `font-size` ≥ 3.2 mm at its scale.
- `test_section_on_design`: with `tests/synthetic.py` and `massing.py` run first, `--massing --at <the synthetic centre's lon,lat>` → the `_design` files exist and `cut.json` `new_cut + new_behind >= 1`.
- `test_section_given_line`: `--line` with two points across the site → the profile's first and last points are 200 m beyond the site boundary (within 1 m).
- `test_terrain_fallback_flat`: a copy of the site folder without the tif, `kit.json` without `terrain`, and the environment variable `SECTION_NO_NETWORK=1` (the script honours it and skips the download) → exit 0, `profile.csv` source `flat (no terrain found)`, and `assumptions.md` says the ground is flat.
- Add both scripts to `NEW_SCRIPTS`.

**Verify**: `python -m pytest tests/test_site_section.py tests/test_scripts.py::test_no_site_in_new_scripts -q` → 0 failed; `python -m pytest tests -q` → 0 failed. If run-5 exists, copy it to `C:\Users\egayd\AppData\Local\Temp\claude\plan009\run5` and run both passes with run-5's style; look at the design PNG once; report whether the ground reads as terrain (the site falls about 30 m and rises 14 m along run-5's line) and whether the new buildings stand on it.

## Done criteria

- [ ] `python -m pytest tests -q` → 0 failed.
- [ ] `grep -rn "rasterio" plugins/drawings/skills/site-section/scripts` returns nothing; `grep -n "33550\|33922\|3072" plugins/drawings/skills/site-section/scripts/terrain.py` finds the tags.
- [ ] `grep -n "section.py" plugins/drawings/skills/site-section/SKILL.md` finds the run line.
- [ ] `git status --short` shows only in-scope files changed or added (plus the owner's six pre-existing modified files).

## STOP conditions

- PIL cannot open the tif (mode other than `F`, or the tags are missing): report the mode and tags.
- The automatic line crosses no building on the real site for every angle (score 0): report the scores; don't lower the scoring.
- Network access is needed in a test: it never is (the tif exists; the fallback test sets `SECTION_NO_NETWORK`).

## Maintenance notes

- The perspective skill has its own `terrain.py` reading a CSV grid or the web; a later plan can make it read the tif through this module.
- Reviewer: the vertical scale is 1:1 with the horizontal (no exaggeration), buildings behind stand on their own ground, and no path or EPSG is written into the script.
