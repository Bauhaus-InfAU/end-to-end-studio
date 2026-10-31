---
name: site-kit
description: Collects the site data for a competition proposal. Use at the start of a proposal, when asked to "collect the site data", or whenever a brief names a site (any city) and no site.geojson exists yet. Writes the site polygon and a local data kit (buildings, plots, streets, water, rail) that the other skills read.
---
# Site kit

Reads: nothing

Never hard-code a site, a city or a bounding box in this skill or in a script it makes; take the name, the stated area and the maps from the brief you are given. Never invent data. If a layer can't be found, leave it out and say so in `summary.md`.

**Where to look.** Collect the project site plus a margin wide enough for the smallest-scale drawing the brief asks for: a figure-ground at 1:15,000 on a 30 cm square needs about 2 km on every side; otherwise about 600 m. Go further if the brief names neighbours that lie further out, such as a station or a commercial area. Use OpenStreetMap through the Overpass API (`https://overpass-api.de/api/interpreter`, try a mirror if it is busy) for buildings, streets, landuse, water and rail. For heights, try the state's open 3D building data (in Bavaria LoD2, in Thuringia LoD2 from GDI-Th) first, then `height` and `building:levels` tags in OSM. Where neither exists, use a stated default per building type (for example 2 floors for houses, 1 for halls) and flag it in the data with `height_source`.

**Finding the boundary.** If the brief gives a polygon or coordinates, use them. If it only shows the site on a map, render that page, locate the area on OpenStreetMap (match rail lines, main roads, forest edges and settlement edges), fit the map to coordinates, trace the marked outline and snap it to roads, rail or field edges where it follows them. Then check the area against any figure in the brief. State how close it is and how sure you are; a traced boundary is rarely better than 30 to 50 m.

**What to write.** Everything into the project's site folder: the one you're told, else where the project's `CLAUDE.md` says, else `site/` at the top. The site belongs to the project, not to one version, so every version reads the same data. If the folder already has a `site.geojson`, ask before you replace it.

- `site.geojson`: one polygon, WGS84, longitude first, `kind: "site"`.
- `buildings.geojson`: `height`, `floors`, `use`, `height_source`.
- `plots.geojson`: `landuse` (OSM landuse, natural and leisure polygons).
- `streets.geojson`, `water.geojson`, `rail.geojson`: lines, with names and types where known.
- `kit.json`: `label`, `center`, `bbox` (west, south, east, north), `size_m`, `generated`.
- `SOURCES.md`: each file, its source and licence (OSM is ODbL), the attribution line, and every default you applied.
- `summary.md`: three lines. What you collected, the site area in ha, what you are unsure of.
