---
name: streets
description: Turns the existing streets and a design's new ones into one clean street surface, at real widths, with rounded corners where streets meet and the paths apart, for every plan and 3D drawing to draw instead of thickened lines. Use when the streets in the drawings look wrong, when asked for the street space, street widths or the street network, or before drawing a plan of a design.
---
# Streets

Reads: site-kit, massing, drawing-graphics

Drawings that thicken each street line on its own get overlaps, notches at junctions, field tracks drawn as roads and roads through new buildings. This skill draws the street once, so every drawing can take it as it is. Take the site and its layers from the project's site folder and the design from `massing/massing.geojson`; never write a place or a number into the skill.

Run it, with `shapely`, `pyproj` and `numpy` installed (`pip install shapely pyproj numpy`) and no Rhino:

`python "${CLAUDE_SKILL_DIR}/scripts/streets.py" --layers <site folder> --out <proposal>/streets [--massing <massing.geojson>] [--config <config.json>] [--style <style.json>] [--scale <the brief's site plan scale>]`

- **Existing streets.** With the site folder's `street-land.geojson` (a cadastre's street, square and path areas), the streets are those areas as they are. Without it, the street lines are drawn at their `width` tag, else their lanes, else a default per type, joined into one surface with rounded corners; footways beside a street, short driveways and tracks are left out of the surface, and paths in open land stay lines. Say in `summary.md` which of the two it was.
- **The design.** With a massing, a new street that runs along an existing one, within 12 m and 25° of it, is that street, and only the existing one is drawn. A new street that ends short of another is led on, straight ahead or turning at most 45°, up to 60 m and never through a building, rail or water; corners are rounded, and existing street land under new buildings gives way. A street that still ends in nothing ends square at the site edge (a later link), with a turning head if it runs more than 50 m from its last crossing, else square, and a path leads from it to the nearest path or street. Without a massing it draws the site as it is.
- **Numbers.** Every number is a default in the script's `DEFAULTS`; put the brief's own widths or kerb radius into `config.json` with their page. For `--style`, put the colours, line weight and font of `drawing-graphics/standard.md` into a JSON with the keys of `FALLBACK_STYLE`.

**What it writes**, into `streets/` in the proposal folder you are told, else the newest in the project's `proposals/`: `streets.geojson` (`street` areas with `use` street or square and `existing`; `path` areas or lines; `centreline` with `level`, `width` and `width_source`), `stats.json`, `assumptions.md` with every default it used, and a check plan `streets_1-<scale>.svg` and `.png`, grey existing, accent new. Open the PNG. Then write `summary.md`, three lines: where the existing streets came from, the street share of the site, and what you're unsure of. If `kept_buildings_under_new_streets` or `main_routes_ending_nowhere` is above zero, say what the massing should change; never change its file.
