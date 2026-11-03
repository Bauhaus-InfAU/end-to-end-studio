---
name: analysis
description: Measures a project site as it is (land uses, edges, green, walking reach, sealed share) and maps what must stay; run again on a design, it measures the design the same way and compares every analysis of the proposal, today against design. Use when asked for a site analysis, the sealed share, what to keep, walking distances, or how a design changes the site.
---
# Analysis

Reads: site-kit, brief-reader
Reads (end): massing, every analysis, drawing-graphics

Measure, never guess. Use only the project's site folder (`site.geojson` and its layers) and the brief's `checklist.md`, opened at the brief's pages it names; for the second run add `massing/massing.geojson`. Never write a site, a place or a number of this project into the skill or a script. Every value carries its source (layer, brief page) or is named as an assumption, and a layer or destination the data lacks is left out and named in `summary.md`. Work in Python, in a metric projection, inside the site polygon only (`pip install -r requirements.txt`: shapely, pyproj, networkx).

**What it measures.** Each measure is one row per value in `metrics.csv` and one map.
- **Uses:** the area and share of the site per land use, from the plots and buildings.
- **Edges:** what the site boundary meets (street, rail, water, built, open land), its length in metres, and how many street or path crossings each stretch has.
- **Green:** the green land and its share, split into wooded, open green and farmland, and the brief's green per resident, if the brief gives residents.
- **Walking reach:** the share of the site within 400 m and 800 m along the street and path network of each destination the data has: stations, green, shops and schools. A destination the data lacks is named in the summary as missing and is not measured.
- **Sealed share:** fully sealed (buildings, streets), partly sealed (paths, squares, pitches) and unsealed, in hectares and as a percentage of the site. The class of each land use goes in `config.json`, marked as an assumption.
- **What to keep:** `keep.geojson`, with the existing buildings inside the site, water, woods, scrub, nature reserves and everything the checklist says must stay that the layers show. Each feature has a `reason` and a `source` (the brief's page). Whatever the checklist names but the layers lack goes in the summary.

**Start from the scripts.** Copy `${CLAUDE_SKILL_DIR}/scripts/config.example.json` to `analysis/config.json` and fill it from the checklist, each value with its page. Then run `python "${CLAUDE_SKILL_DIR}/scripts/measure.py" --proposal <proposal folder> --site <site folder> --config <proposal folder>/analysis/config.json --state today` and `draw.py` with the same arguments. On the second run, `--state design` measures the massing in place of what it covers inside the site, with the same method. Then `compare.py --proposal <proposal folder>` reads every `metrics.csv` in the proposal folder and writes `comparison.csv` (`measure, unit, today, design, change, better`) and `comparison.md`, which says in a few lines where the design improves on today and where it doesn't. Whether higher or lower is better comes from `config.json`.

**What to write.** Everything into `analysis/`: `config.json`, `metrics.csv` (`measure, value, unit, state, source`, with `state` either `today` or `design`), `keep.geojson`, a map per measure as SVG with a PNG next to it, the comparison on the second run, and `summary.md` in three lines: what you measured, the sealed share, and what you are unsure of. The maps take their look from `drawing-graphics/standard.md` if it exists, else black lines on white with greys. Open the maps once before you finish.
