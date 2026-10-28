# The studio

Twenty skills, one per person, plus three examples, that together answer Europan 18 in Regensburg: three vertical A1 panels and up to four pages of text, as the brief asks. Each of you writes one. Nobody waits for anybody else: you can test your skill on the example in `examples/regensburg/` before the skills you depend on exist.

This file is the contract. If your skill reads and writes what it says here, the studio can run it.

## What every skill reads

- `brief/`: the competition brief. Read the parts that concern your skill.
- `proposal/site.geojson`: the project site, one polygon in longitude and latitude, WGS84, longitude first.
- `proposal/site-kit/`: the site data `site-kit` collected (buildings, land use, streets, water, rail). Read its `SOURCES.md` first.
- `proposal/<other-skill>/`: whatever an earlier skill wrote, if you need it. Say in your `SKILL.md` which ones.

## What every skill writes

- Everything into `proposal/<your-skill-name>/` and nowhere else.
- A `summary.md` there: three lines, plain words, for the people who write the text and lay out the panels. What you found or made, the one number that matters, and the one thing you're unsure of.
- Drawings as SVG with a PNG next to each, images as PNG, tables as CSV.

## The design itself

`massing` writes `proposal/massing/massing.geojson`. Every skill that needs the buildings reads it from there. Features carry a `kind`:

| `kind` | Geometry | Properties |
| --- | --- | --- |
| `building` | polygon, the footprint | `floors`; optional `use`, `type` (one of the `building-types`), `phase` |
| `street` | polygon | optional `phase` |
| `open-space` | polygon | `use` (park, square, garden, water) |
| `tree` | point | |

## Shared rules

- Never hard-code your site, your layer names or your paths. The same skill must work on another site and another brief.
- Never invent data. Every number has its source or its assumption next to it.
- Drawing skills read `drawing-graphics` and follow it, so the panels look like one studio. The room picks its direction from the moodboard.
- Keep a skill short. Two or three paragraphs, a list if it helps. Add a line when you don't like a result, delete lines the model no longer needs.
- If a skill needs a key, the key lives in `.env`, never in the skill.

## The order

Every skill says in one line near its top which other skills it reads: `Reads: concept, programme`. `competition-proposal` starts every skill whose inputs are ready, all at the same time, each as its own agent, waits for them, and repeats until nothing is left. So nobody has to keep an order up to date; a missing `Reads:` line only means your skill may run before its inputs exist. The groups below are by topic, roughly in the order things get ready.

| Group | Skill | What it does |
| --- | --- | --- |
| 1 Site and brief | `site-kit` | Collects the site data: buildings, land use, streets, water, rail. Example |
| | `brief-reader` | Turns the brief into a checklist: numbers, required drawings, scales, what the jury looks for |
| | `site-analysis` | The site from the region down to the neighbourhood: history, uses, edges, green and biotopes, what to keep |
| | `climate` | Fresh-air corridors, sun, wind, noise from the roads and the railway |
| 2 Concept | `concept` | The one idea, its title in three sentences, and three to six pictograms |
| | `structure-plan` | The urban figure: green corridors, neighbourhoods, centres, main routes |
| | `programme` | Homes and the household mix, residents, the food market, schools, social and sports uses, by area |
| 3 Design | `massing` | Buildings, streets and open spaces on the structure plan, written to `proposal/massing/` |
| | `phasing` | The construction phases, with phase 1 at the mobility point |
| 4 Systems | `mobility` | The mobility point, low-traffic streets, bike and foot routes, garages |
| | `open-space` | Parks, squares, gardens, and the blue-green network with rain retention |
| 5 Plans | `drawing-graphics` | The studio's drawing standard. The other drawing skills read it. Example |
| | `figure-ground` | The figure-ground plan of the district in its city. Example |
| | `masterplan` | The overall plan at 1:5000 |
| | `detail-plans` | Detail area 1 around the mobility point at 1:1000, and detail area 2, the district centre, at 1:500 |
| 6 Drawings | `site-section` | A long section through the site, from landscape to neighbourhood |
| | `isometric` | An isometric overview of the district |
| | `building-types` | A row of axonometric building types |
| 7 Visuals | `perspective` | Eye-level views with people, from a view in the massing |
| 8 Evidence | `evaluation` | Runs the same analyses on the site as it is and on the design (walking reach, green and sealed share, sun, fresh air, density, the brief's numbers) and shows where the design improves on today, where it doesn't, and what's still missing |
| 9 Delivery | `competition-text` | The text, up to four pages, with the key figures, from every `summary.md` |
| | `panel-layout` | The three vertical A1 panels, numbered, with the entry code |
| | `jury` | Reads the finished entry as the Europan jury would, against the brief and the theme, and writes a short jury report: what convinces, what's weak, a verdict |

`competition-proposal` itself is the lead: it runs the others and reports what's missing.
