---
name: figure-ground
description: Draws the figure-ground plan (Schwarzplan) of the design in its city. Use when asked for a figure-ground plan, a Schwarzplan, or the figure-ground part of a competition entry.
---

# Figure-ground

Reads: site-kit, massing

Read `drawing-graphics` first. The figure-ground answers one question for the jury: how does the new district sit in the city? Every existing building is solid black, all open space is white, and the new buildings are the only colour on the sheet, the accent colour from `drawing-graphics`. Nothing grey, no green, no beige. Where this drawing departs from `drawing-graphics`, this file wins.

Inputs: the site, the new buildings in `proposal/massing/massing.geojson`, the existing buildings in `proposal/site-kit/`. Output: `proposal/figure-ground/figure-ground.svg` and a PNG, north up, at the scale that fits the site with a wide margin of city around it on a square of about 30 cm: 1:5000 for a district, 1:1000 for a block. Plus a `summary.md` of three lines.

- Existing buildings black, no outline. Leave out any that stand inside the site and aren't kept by the design.
- New buildings in the accent colour, no outline, no labels.
- No streets, no plot lines, no trees, no legend, no figures. Water as a thin outline only, if a river or lake is in the frame.
- The site boundary as a thin black dashed line.
- Bottom left, in one line: FIGURE-GROUND 1:5000 (or the scale used). Bottom right: a scale bar and a plain N with a short line. Attribution from `proposal/site-kit/SOURCES.md` in hairline text under the title.
