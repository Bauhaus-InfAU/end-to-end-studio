---
name: isometric
description: Draws an isometric of an urban design, zoomed in on its new buildings with about 100 m of the city around them, the new in the accent and the existing pale; without a design yet, the site as it is. Use when asked for an isometric, an isometry, an axonometric or a 3D overview of a design or a site.
---
# Isometric

Reads: site-kit
Reads (end): massing

Inputs: the project's site folder (site polygon, buildings, plots, streets, water, rail), `massing/massing.geojson` once it exists, the brief for its scales and panel size (or `brief-reader/` if there), and `drawing-graphics/standard.md` if there. Never invent data: draw only what these files hold, and state every assumed size in `summary.md`. Python with `shapely` and `pyproj` in a metric projection, the SVG written directly, the PNG from a headless Chrome or Edge. No Rhino.

**The view.** A true isometric, from the side where the fewest tall existing buildings stand in front of the new ones. Frame the new buildings with about 100 m around them and let the frame cut the city. Without a massing, frame the site with about 200 m around it, mark its boundary in the accent, and say in `summary.md` that the design is missing.

**What it shows.** New buildings in the accent at their height, with floor lines, and their roofs only where the massing says what is on them. Existing buildings pale, at their data height; count the default heights. Streets as surfaces at their width (state the widths you assume), rail as tracks, water and green as surfaces, trees where the data or the massing has them. No labels, arrows or people.

**Scale and look.** The brief's site plan scale; if the drawing is then wider than the brief's panel, the next smaller usual scale, and say why. Give the SVG its print size in mm. Colours, line weights and fonts come from the standard; without it, black lines on white and one accent. Open the PNG: new buildings cut by the frame or floating are mistakes.

**What to write**, into `isometric/` in the proposal folder: `isometric_<scale>.svg` and `.png` (scale as `1-3000`), and `summary.md` in three lines: what you drew and at which scale, the number of new buildings and of default heights, what you are unsure of.
