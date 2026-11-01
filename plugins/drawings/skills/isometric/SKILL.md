---
name: isometric
description: Draws an isometric overview of a district, its buildings extruded to their real heights on the ground with streets, rail, water and the project site, first of the site as it is and again on the design. Use when asked for an isometric, an isometry, an axonometric overview or a 3D view of a site or district.
---
# Isometric

Reads: drawing-graphics, brief-reader
Reads (end): massing, narrative

Inputs: the project's site folder (the site polygon and its buildings, plots, streets, water and rail), the brief's checklist for the scales, the drawing standard for the look, and at the end `massing/massing.geojson`. Never invent data; if one is missing, say so in `summary.md`. Work in Python with `shapely` and `pyproj` in a metric projection and write the SVG directly; make the PNG with a headless Chrome or Edge, giving it absolute paths. No Rhino.

**The view.** A true isometric (30°, no perspective), looking from the side that shows the site's main front and hides the least behind tall buildings; say in `summary.md` which way you look. Draw about 200 m past the site on every side, so the neighbours show. Buildings stand on their footprints at their height from the data; say how many heights are defaults. Draw far buildings first, so near ones cover them.

**What it shows.** The new is the subject, the city around it the quiet ground: existing buildings plain and pale, new buildings in the accent, told apart by use where the massing gives it. Streets are surfaces at their width, not lines; rail shows its tracks; water, parks, forest and meadows are surfaces, with trees on them and along streets where the data or the design puts them (state any assumed tree size). Let the frame cut the surroundings; never show the edge of the data.

**Large and small.** Small, the whole site at the brief's site plan scale: buildings as volumes, trees in clusters, no people; up to three arrows with a short label each for the main moves of the narrative, and symbols for mobility points, stops and centres where the design or `mobility/` names them. Large, an excerpt of about 300 m at the brief's largest scale, around its detail area if it names one: open ground floors where the design has them, single trees, people and vehicles for scale. Of the site as it is, draw only the small one, with the site boundary in the accent.

**The look.** Colours, line weights and fonts come from `drawing-graphics/standard.md`. Without it, black lines on white and one accent for the site boundary and what is new. Open every PNG before you finish: buildings that float, a site cut by the frame or overlapping labels are mistakes.

**What to write**, into `isometric/` in the proposal folder: `isometric_<scale>.svg` and `.png` for the whole site, `isometric_excerpt_<scale>.svg` and `.png` once there is a design, and `summary.md` in three lines: what you drew and at which scale, the number of buildings and how many heights are defaults, what you are unsure of. Write the scale in a file name as `1-2000`, and give each SVG its width and height in mm at its scale, so it prints true to scale.
