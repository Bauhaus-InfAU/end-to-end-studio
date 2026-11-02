---
name: mobility
description: Plans public transport, bike roads, pedestrian roads and car access for an urban design, and draws them as a mobility plan. Use when asked for mobility, transport, bike or pedestrian routes, or how traffic is organised.
---
# Mobility

Reads: brief-reader, structure-plan, massing, drawing-graphics

Take the site and its streets from `site.geojson` and its layers, the public transport, allowed accesses, forbidden links and scales from the brief, and the neighbourhoods and streets from the other skills; cite the brief's page for each rule. Work in Python with `shapely`, never writing a place or number into the skill.

Start from the public transport the site and the brief give (a station, stops, lines) and make the main stop the point the routes meet; place hubs only where the brief or the programme asks for them. Keep cars to the edge where the brief allows, on short access streets with no through-route. Draw a few direct main bike routes, each leading to a named place beyond the site, plus local ones, and for pedestrians the main links to the stops and centres and the paths along the edges and through the neighbourhoods.

Work in the proposal folder you are told, else the newest in the project's `proposals/`, and write only into `mobility/`: `mobility.geojson` in WGS84 with a `kind` on every feature (`route` with `mode` bus, bike, foot or car and `level` main or local; `stop`; `hub`; `access`), a plan as SVG and PNG at the brief's scale in the `drawing-graphics` style with the walking distance to the main stop the brief or a cited norm gives, `mobility.md` with each move and its source, and a three-line `summary.md`. Needs `pip install shapely pyproj`, and Chrome or Edge for the PNG.
