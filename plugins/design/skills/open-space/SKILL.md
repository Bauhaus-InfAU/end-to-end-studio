---
name: open-space
description: Lays out the public open space of an urban design on its massing as a blue-green network, with green corridors that gather the rain in chains of pools, parks with ground cover and paths, playgrounds and green links, and checks it against the brief's green and play areas, with the sealed share. Use when asked for the open space, the parks, the green network, playgrounds, rainwater or sponge-city measures, or the sealed share of a design.
---
# Open space

Reads: brief-reader, programme, massing, structure-plan, climate, analysis, streets, drawing-graphics

Never invent data, and never write a site, a city or a number of one project into the skill or its config by heart: every number comes from the inputs. Take the site and its layers (buildings, plots, streets, water) and its terrain (a GeoTIFF, else `terrain.csv` with `lon, lat, ele`) from the project's site folder, the design from `massing/massing.geojson`, the residents from `programme/programme.csv`, the green corridors from `structure-plan/`, the fresh-air corridors from `climate/`, and what must stay (biotopes, trees, water, basins) from `analysis/`. From the brief take the green area per resident, the play area per resident and its minimum, any rain or retention rule, the green, water and strips that must be kept free (pipes, power lines, protected land), and the site plan scale. Cite each page as the brief's Markdown counts it. Without a programme, take the residents from the brief, its planned figure where it gives a range, never from the floor area. Without an analysis, draw the green the brief keeps (biotopes, compensation land) into `keep-free.geojson` too. Without the massing, stop and say so in `summary.md`: this skill adds a layer to it and never changes it.

**How.** Write `config.json` into `open-space/`: `residents`, `green_m2_per_resident`, `play_m2_per_resident`, `play_min_m2`, `scale`, and `sources` with the page or file of each, plus any key of the script's `DEFAULTS` the brief or an input gives. Draw the brief's strips and protected land into `keep-free.geojson` (lines with their `width_m`, or polygons), citing the plan's page; fit a plan picture to the site by the corners of `site.geojson`, and say how far it may be off. Then run, with `shapely` and `pyproj` installed (`pip install shapely pyproj numpy pillow`) and no Rhino:

`python "${CLAUDE_SKILL_DIR}/scripts/open_space.py" --site <site.geojson> --layers <site folder> --massing <massing.geojson> --config <config.json> --out <proposal>/open-space [--structure <the corridor GeoJSONs of structure-plan/ and climate/>] [--keep-free <keep-free.geojson>] [--streets <proposal>/streets/streets.geojson] [--style <style.json>]`

Pass the streets skill's file when it exists, so the plan shows the same street surface as every other drawing.

The script makes these choices; each number is a default in its `DEFAULTS`, which `config.json` overrides and `assumptions.md` lists:

- **What stays.** Existing woods, meadows, water and basins stay, and count apart from the new public green. Existing house, work and farm plots stay as they are and never become parks. The kept-free strips take no pool, playground or path.
- **Parks.** The free land the massing leaves, at least 12 m wide and 2,000 m², is park; narrower pieces are street green.
- **Corridors.** A park at least 300 m long and 40 m wide on average, or one on a given corridor, is the spine of the network, like a river valley. The new roofs, streets and squares within 300 m drain to it; the rest drains to the nearest park. With terrain, rain runs downhill instead: to the first corridor its way enters within 300 m, else the first park, and a full park spills to the next one below. Existing roofs and streets drain already.
- **Rain.** 30 mm unless the brief says otherwise. In a corridor, a chain of rounded pools in its middle (with terrain, on each stretch's low ground), following its shape, with a shallow edge 0.25 m deep and a deep core 0.8 m deep, cut every 120 m by a dry crossing; in another park, one hollow 0.3 m deep on the side its rain comes from (with terrain, at its lowest ground).
- **Ground cover.** Wet meadow round the pools, lawn within 25 m of buildings and streets, groves beside kept woods, meadow in between.
- **Playgrounds.** The brief's play area in the fewest places that bring every home within 300 m, 50 m from busy roads.
- **Paths and links.** A loop path with rounded bends in every park over 8,000 m², a boardwalk over water. Green links join the parks and the landscape within 300 m; they may cross streets, never buildings.

For `--style`, put the colours, line weights and font of `drawing-graphics/standard.md` into a JSON with the keys of `FALLBACK_STYLE`; without it the plan is black lines on white, greys for the ground cover and one accent colour for water. The plan is at the brief's site plan scale and shows the pools, ground cover, paths and playgrounds; for a small overview, keep only the corridors, parks, water and links. Open the PNG. If the green or the play area falls short, a park stays unlinked or can't hold its rain, or no park is a corridor, say in the third line of `summary.md` what the massing should change, rather than forcing it.

**What to write**, into `open-space/` in the proposal folder you are told, else the newest in the project's `proposals/`:

- `open-space.geojson`: `open-space` (`use`: park, playground, water; `existing`; `role`: corridor or park), `ground-cover` (`cover`), `retention` (`volume_m3`, `needed_m3`, `catchment_m2`; a pool's `deep core`), `path` (`boardwalk` over water) and `green-link` (`to`: park or landscape; `crosses_street`).
- `areas.csv` (required against design: public green, play, retention, ground cover) and `sealing.csv` (fully and partly sealed shares, as the brief asks).
- `open-space_1-<scale>.svg` and `.png`, with the SVG's width and height in mm at its scale; `config.json`, `keep-free.geojson`; `assumptions.md` with every default the script used.
- `summary.md`, which you write, not the script, three lines: what you laid out, public green against the brief's minimum, what you are unsure of or what the massing should change. Without terrain, the pools sit where the corridors are, not where water runs: say so.
