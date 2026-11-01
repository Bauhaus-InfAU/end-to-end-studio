---
name: massing
description: Places the buildings, streets and open spaces of an urban design on its structure plan, and checks them against the brief's programme. Use when asked for the massing, the built volumes, a design of the buildings, or to redo the massing of an earlier version. Writes massing.geojson, the file every drawing and the second analysis read.
---
# Massing

Reads: brief-reader, structure-plan, programme, analysis, drawing-graphics

Never invent data, and never write a site, a city or a number of this project into the skill or a script it makes: the script reads every number from the inputs. Take the site from the project's `site.geojson` and its layers, the rules of the brief (heights, setbacks, what must stay, the scales) from `brief-reader/`, the urban figure from `structure-plan/`, the homes and areas from `programme/`, and what must stay from `analysis/`. If one is missing, read the brief for it yourself, cite the page, and say so in `summary.md`; take the programme only from the brief, never from a guess. Use `site.geojson` as it is, even where it differs from the brief's plans: what lies inside it is existing, and the mismatch goes in `summary.md`.

**How.** Work in Python with `shapely` and `pyproj` (`pip install shapely pyproj`) in a metric projection, and write WGS84, longitude first. No Rhino.

- **Where to build.** Inside the site, on the structure plan's neighbourhoods, minus its green corridors, the kept green and water, every no-build strip of the brief (setbacks from roads, lines and pipes), the main streets, and 4 m around each existing building you keep. The structure plan's streets become `street` (16 m unless it gives a width); its corridors and centres become `open-space`. Land the structure plan leaves unplanned stays open.
- **Blocks.** Fill each neighbourhood with a grid of blocks turned to its long side, 10 m greened secondary streets between them; drop blocks less than a third complete. Buildings are 30 to 50 m long with gaps of 5 to 8 m between them, so air and people pass. By density: low, two rows of houses, 10 m deep, 3 floors; medium, an open courtyard block, 13 m deep, 4 floors; high and urban, courtyard blocks 14 m deep, 5 and 6 floors, mixed; commercial, halls 25 m deep in rows, 3 floors. Courtyards become `open-space` garden.
- **Uses.** Mixed buildings have commerce on the ground floor and homes above. School and pool go on the structure plan's community land with their yards and sports; daycares take the housing building nearest the mobility hub and then those furthest from each other, with enough floors for their area.
- **Heights.** One floor more within 40 m of a main route and within 150 m of the centre, one less beside the green, unless the structure plan says otherwise. Then scale floors per use until the floor area meets the programme, within the brief's height limit; the two buildings nearest the centre rise above it only where the brief allows landmarks. Take 3 m a floor unless the brief says otherwise, and write each assumption into `summary.md`.
- **Trees and squares.** A street tree every 12 m along every street, 4 m off its middle; a square of about 30 m around the centre and the mobility hub.

**What to write.** Everything into `massing/` in the proposal folder:

- `massing.geojson`: every feature with a `kind`. `building` (footprint, `floors`, `height_m`, `use`, `type`, `phase` if known, `existing`), `street` (`width` in m), `open-space` (`use`: park, square, garden, water) and `tree`.
- `areas.csv`: `use, programme_m2, design_m2, difference_m2, source`, one row per use, one for homes (counted in homes, not m²) and one for public green (land area), so the gap to the programme can be seen at a glance.
- `massing.svg` and `.png`: a check plan at the brief's site plan scale, new buildings toned by height and labelled with their floors, kept buildings in outline. Colours, line weights and fonts come from `drawing-graphics/standard.md`; without it, black lines on white and greys by height.
- `massing_3d.svg` and `.png`: a bird's-eye view of the footprints raised to their heights, with the neighbours, to see where the heights rise before the drawing skills start.
- `summary.md`: three lines. What you placed, the gross floor area against the programme (and the floor area ratio), what you are unsure of.

Open both pictures before you finish. Other design skills add their own layers in their own files and never change this one. If one of them needs the massing to change, it says so in its `summary.md`, and you run this skill again.
