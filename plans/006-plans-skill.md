# Plan 006: A `plans` skill draws the site plan, the detail areas and the figure-ground for the panels from every design layer

> **Executor instructions**: Read `plans/000-shared-context.md` first. Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. Do not update `plans/README.md`: the reviewer maintains it.
>
> **Drift check (run first)**: plans 001 and 005 must be DONE. `ls plugins/drawings/skills/plans` must not exist yet. `git diff --stat 98cdb74..HEAD -- plugins/delivery/skills/panel-layout/SKILL.md` prints nothing. Otherwise STOP.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: plans/001-massing-figure-from-config.md (synthetic proposal for tests), plans/005-streets-as-the-shared-base.md (the street surface)
- **Category**: direction (the drawing the jury asks for first)
- **Planned at**: commit `98cdb74`, 2026-11-03

## Why this matters

The panels carry the massing's check drawing as the site plan, with "K8" and "M8" codes, translucent structure-plan strips painted over existing roads and kept houses, and tree dots every 12 m. Nobody draws the brief's site plan or its detail areas: the `plans` skill is "open" in `STUDIO.md`, so the massing helper improvises detail areas that come out too tall (811 mm) and are left off. The jury eliminated runs 3, 4 and 5 in round 2 each time for the same reason: no drawing of detail area 1 around the hub. After this plan one skill composites the design's layers (buildings from massing, the street surface from streets, the ground from open-space, hubs and stops from mobility) into the plans the brief lists, at their scales, cropped to fit the panel, in the drawing standard's look.

## Current state

- `plugins/drawings/TOPIC.md`: each drawing skill "decides what its drawing shows; how it looks comes from the studio's standard, and its scale comes from the brief. ... Give each SVG its print width and height in mm at the scale it is drawn at, so the panels can print it true to scale."
- `plugins/drawings/skills/isometric/` is the pattern for a drawing skill with one script: `SKILL.md` (18 lines) with `Reads:`/`Reads (end):`, a script taking `<site folder> <proposal folder> <scale> <panel width mm> [--style style.json]`, writing SVG + PNG + `summary.md`. Its `STYLE` dict and `--style` override are the look mechanism.
- `plugins/drawings/skills/drawing-graphics/base.md` "Every plan and section": title with scale, graphic scale bar (one thin stepping line, ticks, numbers under, unit on the last), north arrow (a circle in outline, one line from its centre, no letter), a legend for every colour, a source line; drawn at the brief's scale and printed true; "What a drawing shows depends on its scale: at 1:500 and larger the block, its entrances and trees; at 1:5,000 and smaller the district in its city, no single buildings labelled. One thing dominates each drawing."
- `drawing-graphics/style.json` keys: see `plans/000-shared-context.md` rule 5. `drawing-graphics/base.json` is the fallback copy of those keys (`plugins/drawings/skills/drawing-graphics/base.json`).
- The inputs this skill composites, all GeoJSON in WGS84 in the proposal folder:
  - `massing/massing.geojson`: `building` (`floors`, `height_m`, `use`, `type`, `existing`, `landmark`, `note`), `street` (lines, `width`, `level` main/local/secondary/path), `open-space` (`use` park/square/garden/water, `name`, `type`), `tree` points.
  - `streets/streets.geojson` (plan 005): `street` polygons (`existing`, `use` street/square), `path` polygons or lines, `centreline` lines. Optional.
  - `open-space/open-space.geojson`: `open-space` (`use` park/playground/water, `existing`, `role`), `ground-cover` (`cover`: lawn, meadow, wet meadow, grove), `retention` (`deep core`), `path`, `green-link`. Optional.
  - `mobility/mobility.geojson`: `route` (`mode`, `level`), `stop` (`mode`), `hub` (`level`), `access`. Optional.
  - `structure-plan/structure-plan.geojson`: `centre` polygons with `name`, `level`; used to place detail-area windows.
  - The site folder: `site.geojson`, `buildings.geojson` (context, `height`), `water.geojson`, `rail.geojson`, `plots.geojson` (`landuse`), `kit.json` (`bbox`).
- The brief's checklist (`brief-reader/checklist.md` in the proposal or next to the brief) lists the drawings and scales under `## Drawings and scales`, for this brief: figure-ground 1:15,000; site plan 1:3,000 with the number of storeys; detail area 1 around the mobility hub 1:1,000; detail area 2 1:1,000 or 1:500 (the district centre recommended); and under `## Panels and format`: 3 panels A1 portrait 594 × 841 mm. The skill reads these into its `config.json`; never into the script.
- The run-5 massing helper's `plan()` function in `competition/proposals/2026-11-02_run-5/massing/draw.py` (owner's computer; lines 93-247 there) is a working draft of the compositing and fitting: a window in metres, `k = scale / 1000` metres per mm, `assert Wm / k <= PANEL_W`, layers drawn in order (open space, streets as thick lines, trees, context, site outline, kept buildings pale, new buildings toned, storey labels at `TXT * k`), a legend strip of 34 mm, and `fit(bounds, scale, pad, max_h_mm)` that clamps a window to the panel. Reuse its structure; replace its street lines by the streets surface and its ground by the open-space layer.
- `panel-layout/scripts/panels.py scan` lists every SVG in the proposal with its print size and takes the scale from the line of the skill's `summary.md` that names the file (`scale_hint`, lines 99-110). So the summary must name each file with its scale on the same line, as `site-plan_1-3000.svg at 1:3,000`.
- `plugins/delivery/skills/panel-layout/SKILL.md` and `plugins/design/skills/massing/SKILL.md` need one sentence each (Step 5).

## Scope

**In scope** (create or modify):

- `plugins/drawings/skills/plans/SKILL.md` (create)
- `plugins/drawings/skills/plans/scripts/plans.py` (create)
- `plugins/drawings/skills/plans/scripts/config.example.json` (create)
- `plugins/delivery/skills/panel-layout/SKILL.md` (one sentence)
- `plugins/design/skills/massing/SKILL.md` (one sentence)
- `tests/test_plans.py` (create), `tests/test_scripts.py` (add the new script to `NEW_SCRIPTS`)

**Out of scope**: `STUDIO.md` (its "Who" column and the `plans` row are the owner's to update), `panels.py`, `draw.py` of massing, every other skill.

## Steps

### Step 1: The config

`scripts/config.example.json`, every entry `{"value": ..., "source": "..."}`:

- `site_plan_scale` (3000), `figure_ground_scale` (15000), `storeys_on_site_plan` (true/false), `panel_width_mm`, `panel_height_mm`, `margin_mm` (15 if the standard says nothing), each with the brief's page.
- `detail_areas`: a list of `{"name": "detail-area-1", "scale": 1000, "at": "<a centre name from structure-plan.geojson, or 'phase1', or [lon, lat]>", "shows": "<what the brief asks to show>", "page": "..."}`.
- `labels`: optional `{"new": "New buildings", ...}` for the legend in the brief's language; default English.

Required keys (the script stops with the name): `site_plan_scale`, `panel_width_mm`, `panel_height_mm`. Copy `read_config` from `plugins/design/skills/massing/scripts/massing.py:21-33`.

### Step 2: The script

`scripts/plans.py --proposal <folder> --site <site folder> --config <proposal>/plans/config.json [--style <style.json>]`. Structure:

1. Load site, UTM transformer (`utm_epsg` as in massing.py), style (`FALLBACK_STYLE` with the keys of rule 5, overridden by `--style`), the layers above (each optional except massing; missing ones recorded in a `missing` list).
2. A `Plan` function `draw_plan(name, title, scale, window, kind)` with `kind` in `site`, `detail`, `figure-ground`. `k = scale / 1000` m per mm. SVG viewBox in metres, `width`/`height` in mm; a legend strip of 30 mm under the map; text size `max(3.2, style['text']) * k`; line weights `style['thin'|'mid'|'thick'] * k`.
   Layer order for `site` and `detail`:
   1. paper; context plots with `landuse` in a green set (forest, wood, scrub, meadow, grass, park, farmland, allotments) in `style['context']` lightened; water in `style['water']`.
   2. ground from open-space: `ground-cover` by `cover` (`lawn`, `meadow`, `wet-meadow`, `grove` keys of the style), `open-space` parks in `style['park']`, kept green in `style['kept']`, playgrounds outlined, retention pools in `style['water']`; without open-space: massing `open-space` (park → park, garden → lawn, square → paper, water → water).
   3. streets: from `streets/streets.geojson` polygons (`street` existing in `style['street']`, new in `style['street']` with a `style['ink']` thin outline; `path` polygons in `style['street']`, path lines dashed in `style['path']`); without it, massing `street` lines buffered by `width / 2` (flat caps) and the site's streets by a small default table in `DEFAULTS` (the same numbers as `isometric.py`'s `WIDTH`), unioned; `missing` notes it.
   4. rail: four thin parallel lines as `isometric.py:139-143` does.
   5. context buildings outside the site in `style['context']`; kept buildings in the site in `style['existing']` with a thin ink outline.
   6. new buildings in `style['new']` with a `mid` ink outline; landmarks a `thick` outline.
   7. trees as small circles (`style['grove']`) only when `scale <= 2000`.
   8. mobility: `stop` points as a circle with a ring, `hub` points as a double ring, `access` as a small diamond; routes are not drawn (they belong to the mobility plan).
   9. storey numbers on new buildings when `kind == 'site'` and `storeys_on_site_plan`, or when `kind == 'detail'`: text size `3.2 mm * k`, white on buildings with 5 floors or more, ink otherwise, only on buildings whose footprint is at least 3 × the text box.
   10. the site boundary dashed in `style['ink']` thick; the detail-area windows drawn on the site plan as thin dashed rectangles with their names.
   11. legend (one swatch per colour used), title `"<title>, 1:<scale>"`, source line (the OSM credit from `SOURCES.md` if it names OpenStreetMap, as `massing/draw.py:40-42`), a scale bar (stepping line; length a nice number near one sixth of the width), north (circle and line).
   `figure-ground`: every building (context, kept, new) in `style['ink']`, nothing else but the site boundary dashed in `style['accent']`, water left white.
3. Windows. Panel room: `pw = panel_width_mm - 2 * margin_mm`, `ph = panel_height_mm - 2 * margin_mm - 60` (room for a caption and the legend). Site plan: the site's bounds plus 40 m, clamped to `pw * k` × `ph * k` centred on the new buildings' centroid; if the site doesn't fit at the scale, crop and set `cropped: true`. Figure-ground: `kit.json`'s bbox when it exists, else the site buffered by 600 m, clamped the same way at its scale. Detail areas: centre on the named centre's centroid (`at` a name), on the union of the `phase1` neighbourhoods of the massing config if `at == 'phase1'` (read `<proposal>/massing/config.json`), or on a `[lon, lat]`; window `min(pw, ph) * k` wide and high... no: width `pw * k`, height `ph * k`, so it uses the whole panel at that scale; then shrink to the bounds of the new buildings within 150 m of the centre plus 30 m if that is smaller.
4. Write `plans/<name>_1-<scale>.svg` and `.png` (PNG via headless Chrome/Edge, `shot` from massing `draw.py:82-90`), `plans/drawings.json` (name, scale, width_mm, height_mm, fits, cropped, layers used, layers missing), and print it. The helper writes `summary.md` itself (three lines) naming each file with its scale on one line.

Everything in `DEFAULTS` with a one-line meaning: the fallback width table, the tree-scale limit 2000, the label floor 3.2 mm, the window pads, the legend strip height.

### Step 3: The skill text

`SKILL.md` frontmatter: `name: plans`, `description: Draws the plans a brief asks for from the finished design layers, at their scales and cropped to the panel: the site plan with storeys, the detail areas and the figure-ground. Use when asked for the site plan, a detail plan, the figure-ground or the plans for the panels.` Then:

```
# Plans

Reads: brief-reader, massing, streets, open-space, mobility, structure-plan, drawing-graphics

Copy `${CLAUDE_SKILL_DIR}/scripts/config.example.json` to `plans/config.json` in the proposal folder and fill it from the brief's checklist: the scales of the site plan, the figure-ground and each detail area, whether the site plan shows the storeys, the panel size and margin, and for each detail area the structure plan's centre it is around (or `phase1`, or a point), with the page of each. Then run `python "${CLAUDE_SKILL_DIR}/scripts/plans.py" --proposal <proposal folder> --site <site folder> --config <proposal>/plans/config.json --style <proposal>/drawing-graphics/style.json` (`pip install shapely pyproj`; Chrome or Edge for the PNG). It composites what the design skills wrote: buildings from `massing/`, the street surface from `streets/`, the ground from `open-space/`, stops and hubs from `mobility/`; a layer that is missing is left out and named in `drawings.json`. Look at each PNG once. Never fix a colour or line weight here: the look is the standard's.

**What it shows.** Large (a detail area, 1:1,000 and larger): every building with its storeys, entrances where the data has them, the street surface, paths, trees, pools and playgrounds. The site plan (1:2,000 to 1:5,000): buildings, storeys if the brief asks, streets, green and water, the detail-area windows outlined. Small (the figure-ground, 1:10,000 and smaller): buildings black on white and the site boundary. One thing dominates each plan: the new buildings.

**What to write**, into `plans/`: `site-plan_1-<scale>.svg` and `.png`, `detail-area-<n>_1-<scale>.svg` and `.png`, `figure-ground_1-<scale>.svg` and `.png`, `drawings.json`, and `summary.md` in three lines: each file with its scale on one line (`site-plan_1-3000.svg at 1:3,000 …`); how many of the brief's plans are drawn and fit the panel; what you are unsure of, such as a layer that was missing or a plan that had to be cropped.
```

### Step 4: Tests

`tests/test_plans.py`, with `tests/synthetic.py` (run `massing.py` on it first; `streets/` and `open-space/` absent, so the fallback paths run):

- `test_plans_draws_the_three_kinds`: config with `site_plan_scale` 3000, `figure_ground_scale` 15000, panel 594 × 841, margin 15, `detail_areas = [{"name": "detail-area-1", "scale": 1000, "at": "Square"}]` → the six files exist; `drawings.json` has three entries with `fits: true`.
- `test_plans_fit_the_panel`: parse each SVG's `width`/`height` in mm → width ≤ 564 and height ≤ 811 + 30 (legend strip; adjust to what the script writes, and keep the panel room rule: map window ≤ 564 × 751).
- `test_plans_text_floor`: every `font-size` in each SVG, converted to mm (`value / scale * 1000`), is ≥ 3.2.
- `test_plans_reads_streets_when_present`: write a small `streets/streets.geojson` (one `street` polygon) → `drawings.json` `layers_used` contains `streets`.
- `test_plans_missing_required_stops`: config without `site_plan_scale` → non-zero exit and `site_plan_scale` in stderr.
- In `tests/test_scripts.py` add `REPO / "plugins/drawings/skills/plans/scripts/plans.py"` to `NEW_SCRIPTS`.

### Step 5: The two sentences

`panel-layout/SKILL.md`, second paragraph, after "One panel per step of the storyline;": add "A plan from `plans/` is the one that goes on a panel; a check plan of the same thing from `massing/` never does."

`massing/SKILL.md`, in **What to write.**, after the `massing.svg` item's "It is a check, not a panel drawing." (the `massing_3d` item) add to the `massing.svg` item: "The panel plans and the detail areas are the `plans` skill's, not this one's."

**Verify**: `python -m pytest tests/test_plans.py tests/test_order.py tests/test_scripts.py::test_no_site_in_new_scripts -q` → 0 failed; `python -m pytest tests -q` → 0 failed. Then, if run-5 exists, copy it to `C:\Users\egayd\AppData\Local\Temp\claude\plan006\run5`, write a `plans/config.json` for it (site plan 3000 with storeys, figure-ground 15000, detail area 1 at the main centre at 1000, detail area 2 at the main centre at 500, panel 594 × 841, margin 15), run the script with run-5's style, and look at `site-plan_1-3000.png` and `detail-area-1_1-1000.png` once each: new buildings dark, streets one clean surface, no storeys smaller than the floor, no ochre over roads. Report what you saw.

## Done criteria

- [ ] `python -m pytest tests -q` → 0 failed.
- [ ] `plugins/drawings/skills/plans/SKILL.md` has a `Reads:` line naming `massing, streets, open-space, mobility` and `tests/test_order.py` passes (no cycle).
- [ ] On the run-5 copy (if present): six files written, `drawings.json` says `fits: true` for the site plan and detail area 1.
- [ ] `grep -n "plans/" plugins/delivery/skills/panel-layout/SKILL.md plugins/design/skills/massing/SKILL.md` finds both sentences.
- [ ] `git status --short` shows only in-scope files changed or added (plus the owner's six pre-existing modified files).

## STOP conditions

- A required input format differs from "Current state" (for instance open-space has no `ground-cover` kind): report, don't guess.
- The detail area at 1:1,000 can't fit the panel height with the whole phase-1 area: that is expected; the window shrinks to the centre; don't enlarge the panel.
- `panels.py` would need a change for the scan to pick the drawings up: don't change it; make the summary line carry the scale instead.

## Maintenance notes

- `STUDIO.md`'s skills table lists `plans` as "open"; the owner updates that row and the "Who" column.
- When `building-types` or `phasing` skills exist, their layers can join `draw_plan` the same way (read if present, listed in `drawings.json`).
- Reviewer: check the layer order (ground, streets, buildings, labels), that nothing is drawn outside the window (use a clipPath), and that every colour comes from the style.
