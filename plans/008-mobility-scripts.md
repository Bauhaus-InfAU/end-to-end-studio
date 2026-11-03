# Plan 008: The mobility plan comes from a script and a config, on the streets surface, instead of 240 lines written per run

> **Executor instructions**: Read `plans/000-shared-context.md` first. Follow this plan step by step. Run every verification command and confirm the expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report; do not improvise. Do not update `plans/README.md`: the reviewer maintains it.
>
> **Drift check (run first)**: plans 004 and 005 must be DONE. `git diff --stat 98cdb74..HEAD -- plugins/design/skills/mobility` shows only `SKILL.md` (plan 005 added `streets` to its Reads). `ls plugins/design/skills/mobility/scripts` must not exist. Otherwise STOP.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/004-centres-hold-community-buildings.md (hub buildings), plans/005-streets-as-the-shared-base.md (the surface and centrelines)
- **Category**: perf (cost per run) + repeatability
- **Planned at**: commit `98cdb74`, 2026-11-03

## Why this matters

The mobility skill has no scripts, so every run writes its own (238 lines in run-5, 32 steps and $1.28 in run-4) and draws its own version of the streets. After this plan the helper fills a `config.json` (the hub, the walking limits with their source, which gateways cars may use, where the stops are) and a script reads the structure plan's routes and their modes, the massing's streets and buildings, and the streets skill's surface and centrelines, computes the walking shares along the network, and draws the plan in the standard's look.

## Current state

`plugins/design/skills/mobility/SKILL.md` (14 lines after plan 005): `Reads: brief-reader, structure-plan, massing, drawing-graphics, streets`; asks for `mobility.geojson` with `route` (`mode` bus, bike, foot or car; `level` main or local), `stop`, `hub`, `access`; a plan SVG/PNG at the brief's scale with the walking distance to the main stop; `mobility.md` with each move and its source; a three-line `summary.md`. "Keep cars to the edge where the brief allows, on short access streets with no through-route. Draw a few direct main bike routes, each leading to a named place beyond the site."

Inputs available in a proposal folder:

- `structure-plan/structure-plan.geojson`: `route` lines with `name`, `level` (main, local, landscape) and a free-text `mode` (run-5 examples: "cars, regional buses from the north (p. 27)", "foot and cycle only", "cars from Glashuettenstrasse, buses, foot and cycle"); `gateway` points with `name`; `centre` polygons with `name`, `level`, `holds`.
- `massing/massing.geojson`: `street` lines (`level` main/local/secondary/path, `width`), `building` with `use`, `gfa_m2`, `existing`; after plan 004 a community building whose `use` contains "station" or "hub" may exist.
- `streets/streets.geojson` (plan 005): `street` polygons, `centreline` lines with `level` and `width`, `path` features.
- `drawing-graphics/style.json`: see rule 5 of the shared context.

The run-5 helper's `mobility.py` (owner's computer, `competition/proposals/2026-11-02_run-5/mobility/mobility.py`, 238 lines) is the draft: its network check builds a `networkx` graph from every street line's segments (nodes rounded to 2 m), joins ends within 15 m, runs Dijkstra from the hub, and sums the housing floor area within 400 and 800 m; its drawing has rings at the limits, lines by mode and level, symbols for stops, hubs, garages and accesses, a legend and the credit line. Its brief-specific parts (route names, gateway names, page numbers, labels) must move into the config.

`networkx` 3.4 is installed on the owner's computer but is not in `requirements.txt`.

## Scope

**In scope** (create or modify):

- `plugins/design/skills/mobility/scripts/mobility.py` (create)
- `plugins/design/skills/mobility/scripts/config.example.json` (create)
- `plugins/design/skills/mobility/SKILL.md`
- `requirements.txt` (add `networkx`)
- `tests/test_mobility.py` (create), `tests/test_scripts.py` (`NEW_SCRIPTS`)

**Out of scope**: every other skill, `tests/synthetic.py`.

## Steps

### Step 1: The config

`config.example.json`, entries as `{"value": ..., "source": ...}`:

- `hub`: the name of the structure plan's centre with the main stop (required).
- `main_stop`: the name of the gateway or centre that is the rail or main public-transport stop (required).
- `walk_limits_m`: e.g. `[400, 800]` with the brief's page or "assumption: 5 and 10 minutes at 80 m/min" (required).
- `car_access`: list of gateway names where cars may enter, with the page (required; may be empty).
- `no_car_link`: optional list of pairs of gateway names that must not be joined by a car route, with the page.
- `bike_destinations`: optional list of `{"route": "<route name>", "to": "<place beyond the site>"}`.
- `stops`: optional list of `{"at": "<gateway or centre name>", "mode": "bus"}`.
- `garages`: optional list of `{"at": "<centre or gateway name>", "what": "district garage"}`.
- `modes`: optional overrides `{"<route name>": ["car", "bus"]}` when the structure plan's words are unclear.
- `scale`: the site plan scale with its page (required).

### Step 2: The script

`mobility.py --proposal <folder> --site <site folder> --config <proposal>/mobility/config.json [--style style.json]`:

1. Read the structure plan, the massing, the streets file if present, the style. Stop with the key's name on a missing required config value (`read_config` from massing.py).
2. Modes from words: parse each route's `mode` text with a small table in `DEFAULTS['mode_words']`: car ← "car", "cars", "lorr"; bus ← "bus"; bike ← "cycle", "bike", "bicycle"; foot ← "foot", "walk", "pedestrian". A route with no recognised word takes `DEFAULTS['mode_by_level']` (`main` → car+bus+bike+foot, `local` → car+bike+foot, `landscape` → bike+foot). `config.modes` overrides by name. Massing `secondary` streets → bike+foot (and car as access only), massing `path` → foot+bike.
3. Features: one `route` per route per mode (`mode`, `level`, `name`, `source`, `basis` from the structure plan); `stop` for `main_stop` (mode rail unless the config says) and each `stops` entry (the point on the nearest bus route to the named place); `hub` at the hub centre (on the building whose `use` contains "station" or "hub" when the massing has one, else the centre's centroid) and at every centre whose `holds` contains "mobility" or "sharing" as local hubs; `access` at each `car_access` gateway; `garages` as `hub` with `function: garage`.
4. Checks: `car_link_violations`: for each `no_car_link` pair, whether a car-only path exists in the car network between the two gateways (networkx); `walk`: network of streets centrelines (from the streets file, else the site's streets lines) + massing streets + foot routes, Dijkstra from the main stop, housing floor area (`use` containing housing/residential/mixed/home) within each limit and unreached; `bike_routes_to_named_places`: count of main bike routes with a `to`.
5. Write `mobility.geojson`, `stats.json` (the checks), `walk.json`, `assumptions.md` (defaults used), and the plan `mobility_1-<scale>.svg` + `.png`: base in the standard's greys (streets surface from the streets file or buffered lines, buildings new in `style['new']`, context in `style['context']`), rings at the walk limits from the stop, routes by mode (bus `ink` thick, car `existing` mid, bike `accent` mid, foot `ink` thin dashed) and level, symbols, a legend with every symbol, the walking shares as one text line, the credit, a scale bar (stepping line) and north (circle and line). Text ≥ 3.2 mm. Fit: if the site at the scale is wider than `DEFAULTS['panel_w_mm']` (564) minus margins, crop to the new buildings' extent and say so in `stats.json`.
6. The helper writes `mobility.md` (each move and its source) and `summary.md` itself.

### Step 3: The skill text

Rewrite the third paragraph of `SKILL.md` to: copy `config.example.json` to `mobility/config.json`, fill it from the brief (the hub, the stop, the walking limits with their source, where cars may enter, forbidden links, the bike destinations), run `python "${CLAUDE_SKILL_DIR}/scripts/mobility.py" --proposal ... --site ... --config ... --style <proposal>/drawing-graphics/style.json` (`pip install shapely pyproj networkx`), read `stats.json`, and write `mobility.md` and the three-line `summary.md` (the walking shares as the number that matters). Keep the first two paragraphs. Keep the file under 20 lines.

### Step 4: Tests

`tests/test_mobility.py` with `tests/synthetic.py` (run `massing.py` first; the synthetic structure plan has a `route` "Main road" with no `mode` text, a `gateway` "Gate", a main centre "Square" holding "stop, bus station"):

- `test_mobility_runs_on_synthetic`: config `hub: "Square"`, `main_stop: "Square"`, `walk_limits_m: [400, 800]`, `car_access: ["Gate"]`, `scale: 3000` → exit 0; `mobility.geojson` has kinds `route`, `stop`, `hub`, `access`; `walk.json` shares are between 0 and 1 and `within_800m >= within_400m`; the SVG and PNG exist; every SVG `font-size` ≥ 3.2 mm at the scale.
- `test_mobility_missing_hub_stops`: config without `hub` → non-zero exit, `hub` in stderr.
- `test_mobility_mode_words`: a structure plan route with `mode: "foot and cycle only"` yields `route` features for foot and bike only.
- Add the script to `NEW_SCRIPTS`.

**Verify**: `python -m pytest tests/test_mobility.py tests/test_scripts.py::test_no_site_in_new_scripts -q` → 0 failed; `python -m pytest tests -q` → 0 failed. If run-5 exists, copy it to `C:\Users\egayd\AppData\Local\Temp\claude\plan008\run5`, write a config for it (hub "Wutzlhofen station square", stop "Wutzlhofen stop", limits [400, 800], car access the four gateways run-5's `mobility.md` lists under Cars, scale 3000) and run; look at the PNG once; report the walking shares against run-5's (20 % / 72 %).

## Done criteria

- [ ] `python -m pytest tests -q` → 0 failed.
- [ ] `grep -n "networkx" requirements.txt` finds it.
- [ ] `grep -n "mobility.py\|config.json" plugins/design/skills/mobility/SKILL.md` finds both.
- [ ] No place name or page number in `mobility.py` or `config.example.json` (the `FORBIDDEN` test covers it).
- [ ] `git status --short` shows only in-scope files changed or added (plus the owner's six pre-existing modified files).

## STOP conditions

- The synthetic structure plan lacks a `gateway` or the route has no `level`: report (don't edit `synthetic.py`).
- Dijkstra finds no path from the stop to any building (network disconnected): check the 15 m end-joining first; if still none, STOP and report the node counts.

## Maintenance notes

- When `building-types` or `phasing` exist, the walking check could read phases; not now.
- Reviewer: the mode-word table must be in `DEFAULTS`, and the config, not the script, must carry every name.
