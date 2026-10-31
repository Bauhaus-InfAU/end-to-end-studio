---
name: site-section
description: Draws a long section through a project site on its real ground, with the buildings it cuts, the buildings behind in elevation, plants by land use and people for scale. Use when asked for a site section, a long section, a terrain section or elevations of a site, first of the site as it is and again on the design.
---
# Site section

Reads: drawing-graphics, brief-reader
Reads (end): massing

Inputs: the project's site folder (the site polygon and its buildings, plots, streets, water and rail), the brief's checklist for the scales, the drawing standard for the look, and at the end `massing/massing.geojson`. Never invent data; if one is missing, say so in `summary.md`. Work in Python with `shapely`, `pyproj` and `requests`, in a metric projection, and write the SVG directly; make the PNG with a headless Chrome or Edge, giving it absolute paths. No Rhino.

**The cut.** One straight line A–A′, long through the site, that also crosses buildings and the main lines: the railway, the main streets, a river, and the detail area if the brief names one. The longest line through the centre often crosses only fields; then move it sideways or turn it, and say why in `summary.md`. Run it about 200 m past the site at each end, so the neighbours show. State the direction you look in, and draw so that the end on your left is the end on your left when you stand looking that way.

**The ground.** Never draw it flat. Take a terrain model along the line every 10 m or less: the state's open 1 m terrain model where there is one, else a European or global model (EU-DEM 25 m or SRTM via `api.opentopodata.org`). Write the samples to `profile.csv` with their source. No vertical exaggeration; heights above sea level on a small scale at the side.

**What it shows.** Buildings the line passes through are cut, the strongest tone; buildings up to about 80 m behind the line stand in elevation, lighter, the far ones drawn first. Heights and floors come from the data; say which are defaults. Under the ground line, the earth is cut. Along it, the land use decides the plants: trees on forest, park and scrub at an assumed height you state, grass on meadow, fields and lawns; nothing on built ground where the data shows no garden. Label each street, railway and river once where it is crossed (a double track is one label), mark the site boundary in the accent colour, and add a scale bar, A and A′, and a key plan with the line on it.

**Large and small.** Draw the whole cut at the brief's site plan scale: buildings as cut and elevation, trees, no people, no floor lines. Draw an excerpt of about 200 m at the brief's largest scale (its detail areas), where buildings meet open ground or in the detail area: floor lines, people for scale (about 1.75 m, at entrances, on streets and on open ground), grasses. If the brief asks for elevations, draw them the same way from the street. At the end, draw the same cut and excerpt again on the design, with new buildings in the accent colour.

**The look.** Colours, line weights and fonts come from `drawing-graphics/standard.md`. Without it, black lines on white, greys for cut and elevation, and one accent for the site boundary and what is new. Open every PNG before you finish: labels that overlap, a ground line that is missing, or buildings that float are mistakes.

**What to write**, into `site-section/` in the proposal folder: `site-section_<scale>.svg` and `.png` for the whole cut, `site-section_excerpt_<scale>.svg` and `.png`, `profile.csv`, and `summary.md` in three lines: what you drew and at which scales, the height difference along the cut, what you are unsure of.
