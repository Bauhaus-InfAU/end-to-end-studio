---
name: mobility
description: Plans public transport, bike roads, pedestrian roads and car access for an urban design, and draws them as a mobility plan. Use when asked for mobility, transport, bike or pedestrian routes, or how traffic is organised.
---
# Mobility

Reads: brief-reader, structure-plan, massing, drawing-graphics

Take the site and its streets from `site.geojson` and its layers, the station, bus lines, allowed accesses, forbidden links and scales from the brief, and the neighbourhoods and streets from the other skills; cite the brief's page for each rule. Work in Python with `shapely`, never writing a place or number into the skill.

Make the station the centre, with buses arriving from the sides the brief gives and meeting behind a bus gate. Cars stop at the edge on short access streets with no through-route. Draw three or four direct main bike routes, each with an arrow to a place beyond the site, plus local ones, and for pedestrians draw promenades to the station and footpaths along the edges and through the neighbourhoods. No hub blobs or mobility points.

Write `mobility/mobility.geojson`, a plan as SVG and PNG at the brief's scale in the `drawing-graphics` style with a 500 m circle around the station, `mobility.md` with each move and its source, and a three-line `summary.md`.
