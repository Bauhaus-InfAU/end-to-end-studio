---
name: open-space
description: Lays out the public open space of an urban design on its massing, as a blue-green network: parks, kept green and water, playgrounds, rain retention and the green links between them, checked against the brief's green and play areas, with the share of sealed ground. Use when asked for the open space, the parks, the green network, playgrounds, rainwater or sponge-city measures, or the sealed share of a design.
---
# Open space

Reads: brief-reader, programme, massing, structure-plan, analysis, climate

Never invent data, and never write a site, a city or a number of a project into the skill or its config by heart: every number comes from the inputs. Take the site and its layers (buildings, plots, streets, water) from the project's site folder, the design from `massing/massing.geojson`, the residents from `programme/programme.csv`, the green corridors from `structure-plan/` and the fresh-air corridors from `climate/` if they exist, and what must stay (biotopes, trees, water, basins) from `analysis/`. From the brief take the green area per resident, the play area per resident and its minimum, any rainfall or retention rule, which green and water must be kept, and the site plan scale; cite each page as the Markdown's page markers count it. Without a programme, take the residents from the brief, its planned figure where it gives a range, and say so; without an analysis, add the land-use tags of the green the brief keeps to `keep_landuse`. If the massing is missing, stop and say so in `summary.md`: this skill adds a layer to it and never changes it.

**How.** Write `config.json` into `open-space/`: `residents`, `green_m2_per_resident`, `play_m2_per_resident`, `play_min_m2`, `scale`, and `sources` with the page or file of each, plus any key of the script's `DEFAULTS` the brief or analysis gives (such as `design_rain_mm` or `keep_landuse`). Then run, with `shapely` and `pyproj` installed (`pip install shapely pyproj`) and no Rhino:

`python "${CLAUDE_SKILL_DIR}/scripts/open_space.py" --site <site.geojson> --layers <site folder> --massing <massing.geojson> --config <config.json> --out <proposal>/open-space [--structure <the GeoJSON in structure-plan/>] [--style <style.json>]`

It keeps the existing green and water, turns the free land wide and big enough into parks, places the fewest playgrounds that bring every home within reach and away from noisy roads, holds each park's share of the rain from the nearest new roofs and streets in a hollow beside them, and links the parks to each other and to the landscape. For `--style`, put the colours, line weights and font of `drawing-graphics/standard.md` into a JSON with the keys of `FALLBACK_STYLE`; without it the plan is greys with one accent. Open the PNG. If the green or the play area falls short, a park stays unlinked, or a basin sits on a corridor the brief wants open, say in the third line of `summary.md` what the massing should change, rather than forcing it.

**What to write**, into `open-space/` in the proposal folder you are told, else the newest in the project's `proposals/`:

- `open-space.geojson`: `open-space` (`use`: park, playground, water; `existing`), `retention` (`volume_m3`, `needed_m3`, `catchment_m2`) and `green-link` (`to`: park or landscape; `crosses_street`).
- `areas.csv` (required against design: public green, play, retention) and `sealing.csv` (fully and partly sealed shares, as the brief asks).
- `open-space_1-<scale>.svg` and `.png`, a check plan at the brief's site plan scale; `config.json`; `assumptions.md` with every default the script used.
- `summary.md`, three lines: what you laid out, public green against the brief's minimum, what you are unsure of (without terrain, retention sits where it is near, not where water flows).
