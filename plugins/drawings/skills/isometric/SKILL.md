---
name: isometric
description: Draws an isometric of an urban design, zoomed in on its new buildings with about 100 m of the city around them, the new in the accent and the existing pale; without a design yet, the site as it is. Use when asked for an isometric, an isometry, an axonometric or a 3D overview of a design or a site.
---
# Isometric

Reads: site-kit
Reads (end): massing

Draw only what the files hold: the project's site folder, `massing/massing.geojson` once it exists, the brief's scales and panel size, and `drawing-graphics/standard.md` if there. State every assumed size in `summary.md`. Python with `shapely` and `pyproj`, the SVG written directly, the PNG from a headless Chrome or Edge; if neither is installed, say so in `summary.md`. Without a site folder, draw nothing: say which site files you need (the site outline with its buildings, streets, water, green) and write it in `summary.md`.

**View.** A true isometric from the side where the fewest tall buildings stand in front of the new ones, framing them with about 100 m of city, cut by the frame. Without a massing: the site with 200 m around it, its boundary in the accent, and say the design is missing.

**What it shows.** New buildings in the accent with floor lines, roofs only where the massing names them; existing buildings pale (count the default heights); streets as surfaces at their width, rail, water, green, and only the trees the data has. No labels, arrows or people.

**Scale and look.** The brief's site plan scale, or the next smaller usual one if the drawing is wider than the panel; print size in mm. The look comes from the standard; without it, black on white and one accent. Check the PNG: new buildings cut or floating are mistakes.

**Write** into `isometric/` in the proposal folder: `isometric_<scale>.svg` and `.png` (scale as `1-3000`), and a three-line `summary.md`: what you drew and at which scale, the new buildings and default heights, what you are unsure of.
