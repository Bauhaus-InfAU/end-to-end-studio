# The office

Thirty skills, written by thirty people, that together turn a site in Weimar into a competition proposal. Each of you writes one. Nobody waits for anybody else: you can test your skill on the example in `examples/weimar-block/` before the skills you depend on exist.

This file is the contract. If your skill reads and writes what it says here, the office can run it.

## What every skill reads

- `proposal/site.geojson`: the site, one polygon in longitude and latitude, WGS84, longitude first. It's the only thing every proposal starts from.
- `public/data/`: the city kit (buildings, plots, streets, census). Read its `SOURCES.md` first.
- `proposal/<other-skill>/`: whatever an earlier skill wrote, if you need it. Say in your `SKILL.md` which ones.

## What every skill writes

- Everything into `proposal/<your-skill-name>/` and nowhere else.
- A `summary.md` there: three lines, plain words, for the people who write the text and lay out the sheets. What you found or made, the one number that matters, and the one thing you're unsure of.
- Drawings as SVG and a PNG next to each, images as PNG, tables as CSV.

## The design itself

`massing` writes `proposal/massing/massing.geojson`. Every skill that needs the building reads it from there. Features carry a `kind`:

| `kind` | Geometry | Properties |
| --- | --- | --- |
| `building` | polygon, the footprint | `floors`; optional `use`, `ground_floor_height_m` (default 4.5), `floor_height_m` (default 3.2) |
| `street` | polygon | |
| `courtyard` | polygon | |
| `tree` | point | |

## Shared rules

- Never hard-code your own layer names, paths or site. Your skill has to work on a site somebody picks in the room.
- Drawing skills read `drawing-graphics` and follow it, so the sheets look like one office.
- Keep a skill short. Two or three paragraphs, a list if it helps. Add a line when you don't like a result, delete lines the model no longer needs.
- If a skill needs a key, the key lives in `.env`, never in the skill.

## The order

`competition-proposal` runs the skills in this order. Within a group the order doesn't matter.

| Group | Skill | What it does |
| --- | --- | --- |
| 1 Brief and site | `brief` | Writes a competition brief for the site: what to build, how much, for whom |
| | `site-context` | History, uses and neighbours of the site, from the city kit and public sources |
| | `heritage` | Listed buildings and protected areas around the site, and what that means for the design |
| | `mobility` | Access, transit stops, walking reach from the site |
| 2 Regulation | `zoning` | The planning law that applies: a development plan, or the rule that the building must fit its surroundings |
| | `setbacks` | Distance areas to the neighbours under the Thuringian building code |
| | `fire-escape` | Escape routes and their lengths, fire brigade access |
| | `accessibility` | Step-free access and what the accessibility standard asks of the building |
| 3 Concept | `program` | The room schedule: spaces, areas, how they relate |
| | `massing` | The building in three variants and the chosen one, in Grasshopper, written to `proposal/massing/` |
| | `concept-diagram` | Three to five diagrams that explain the idea |
| 4 Drawings | `drawing-graphics` | The office's drawing standard. The other drawing skills read it |
| | `general-plan` | The site plan at 1:1000 |
| | `floor-plan` | The ground floor and a typical floor at 1:200 |
| | `section` | One long and one cross section at 1:200 |
| | `elevation` | The street elevation at 1:200 |
| | `detail` | One facade detail at 1:20 |
| | `axonometric` | An axonometric of the building in its block |
| 5 Analysis | `daylight` | Sun hours on the facades and the courtyard |
| | `isovist` | What you see from the important points around the site |
| | `density` | Site coverage, floor area ratio, against the neighbourhood |
| | `embodied-carbon` | Embodied carbon of the structure, by material |
| 6 Numbers | `area-schedule` | Gross and net floor areas by use |
| | `cost-estimate` | Building cost by cost group |
| 7 Visualisation | `render-style` | The office's render: from a Rhino view, through an image model |
| | `interior-mood` | One interior image |
| | `collage` | One collage of the building in use |
| 8 Delivery | `competition-text` | The explanatory text the jury reads, from every `summary.md` |
| | `layout` | The sheets: everything above on A0 or A1 boards |
| | `jury-check` | Reads the whole proposal against the brief, as a jury would, and lists what's weak |

`competition-proposal` itself is the lead: it runs the others and reports what's missing.
