---
name: massing
description: Places the buildings, streets and open spaces of an urban design on its structure plan, and checks them against the brief's programme. Use when asked for the massing, the built volumes, a design of the buildings, or to redo the massing of an earlier version. Writes massing.geojson, the file every drawing and the second analysis read.
---
# Massing

Reads: brief-reader, structure-plan, programme, analysis

Never invent data, and never write a site, a city or a number of this project into the skill or a script it makes. Take the site from the project's `site.geojson` and its layers, the rules of the brief (heights, density, what must stay, the scales) from `brief-reader/`, the urban figure from `structure-plan/`, the homes and areas from `programme/`, and what must stay from `analysis/`. If one is missing, say so in `summary.md` and work with what there is; never guess a programme.

**How.** Inside the site boundary, follow the structure plan: its streets and routes become `street`, its green corridors and centres become `open-space`, and the neighbourhoods are filled with blocks and buildings. Keep the existing buildings and trees the analysis says to keep, as `building` or `tree` with `existing: true`. Size the buildings so that the gross floor area per use meets the programme; take a usable depth of about 12 to 14 m for housing and a floor height of 3 m unless the brief says otherwise, and write each assumption into `summary.md`. Make heights and building types vary with the structure plan, higher at centres and main routes, lower towards the edges and the green. Work in Python with `shapely` and `pyproj` (`pip install shapely pyproj`) in a metric projection, and write WGS84, longitude first. No Rhino.

**What to write.** Everything into `massing/` in the proposal folder:

- `massing.geojson`: every feature with a `kind`. `building` (footprint, `floors`, `use`, `type`, `phase` if known, `existing`), `street` (`width` in m), `open-space` (`use`: park, square, garden, water) and `tree`.
- `areas.csv`: `use, programme_m2, design_m2, difference_m2, source`, one row per use and one for homes, so the gap to the programme can be seen at a glance.
- `massing.svg` and `.png`: a check plan at the brief's site plan scale, buildings labelled with their floors, so the massing can be read before the drawing skills start. Colours, line weights and fonts come from `drawing-graphics/standard.md`; without it, black lines on white and greys by height.
- `summary.md`: three lines. What you placed, the gross floor area against the programme (and the floor area ratio), what you are unsure of.

Other design skills add their own layers in their own files and never change this one. If one of them needs the massing to change, it says so in its `summary.md`, and you run this skill again.
