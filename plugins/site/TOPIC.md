# Site

Skills that collect the data of a place. They describe what is there, never what should be.

- Input: the brief, for the site's name, area and maps.
- Output: GeoJSON in WGS84, longitude first. `site-kit` writes the boundary to `site.geojson` and its layers next to it, in the project's site folder, which every version shares. Every file has its source and licence in a `SOURCES.md`, and every default or guess is flagged in the data.
- A new skill here: one more layer of the place, such as heritage, noise, soil or flood zones.
