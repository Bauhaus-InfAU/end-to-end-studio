---
name: isometric
description: Draws an isometric overview of a district, its buildings extruded to their real heights on the ground with streets, rail, water and the project site, first of the site as it is and again on the design. Use when asked for an isometric, an isometry, an axonometric overview or a 3D view of a site or district.
---
# Isometric

Reads: drawing-graphics, brief-reader
Reads (end): massing

Inputs: the project's site folder (the site polygon and its buildings, plots, streets, water and rail), the brief's checklist for the scales, the drawing standard for the look, and at the end `massing/massing.geojson`. Never invent data; if one is missing, say so in `summary.md`. Work in Python with `shapely` and `pyproj` in a metric projection and write the SVG directly; make the PNG with a headless Chrome or Edge, giving it absolute paths. No Rhino.

**The view.** A true isometric (30°, no perspective), looking from the side that shows the site's main front and hides the least behind tall buildings; say in `summary.md` which way you look. Draw about 200 m past the site on every side, so the neighbours show. Buildings stand on their footprints at their height from the data; say how many heights are defaults. Draw far buildings first, so near ones cover them.

**What it shows.** _To fill in after the reference: large and small, what is labelled, trees, how the site boundary and what is new stand out._

**The look.** Colours, line weights and fonts come from `drawing-graphics/standard.md`. Without it, black lines on white and one accent for the site boundary and what is new. Open every PNG before you finish: buildings that float, a cropped drawing or overlapping labels are mistakes.

**What to write**, into `isometric/` in the proposal folder: `isometric_<scale>.svg` and `.png`, and `summary.md` in three lines: what you drew and at which scale, the number of buildings and how many heights are defaults, what you are unsure of. Write the scale in a file name as `1-2000`, and give each SVG its width and height in mm at its scale, so it prints true to scale.
