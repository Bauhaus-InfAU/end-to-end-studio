---
name: structure-plan
description: Sets the urban figure before any building is placed: neighbourhoods, a hierarchy of centres, the green structure and its roles, main routes and the gateways to the surrounding city, as GeoJSON that massing, mobility and open-space build on. Use when asked for a structure plan, framework plan, urban framework or the urban figure.
---
# Structure plan

Reads: narrative, climate, programme

Work in the proposal folder you are given and write only `structure-plan.geojson` and `summary.md` into `structure-plan/`, nothing else. Take the idea from `narrative/`, the corridors to keep open from `climate/`, the homes per phase from `programme/`, the site from the project's site folder, and the checklist and analysis from `brief-reader/` and `analysis/` where they exist, else from the brief's Markdown; name each missing input in `summary.md`. If there is no site, ask for it. Check the site polygon and its area against the brief's plans and stated area; if they disagree, say why in `summary.md` and work on the brief's boundary. This is a framework, not a masterplan: stop at neighbourhoods, centres, green, routes and gateways.

Start from what is there: what to keep, then what to change, and only then what is new. Answer the site's barriers, arrival points, destinations and the landscape beyond it: bridge or hold an edge, open a gateway where a route, a stop or a landscape meets the site, and continue the surrounding streets and paths into it. Divide the site into neighbourhoods by their spatial qualities (landscape, fabric, edges, relations) and name them by these, never by assumed residents. Place a main centre and local centres where the narrative and the site point, so that no single centre carries everything and a walk leads from one place to the next. Give green areas real extent and their roles (ecology, water, climate, recreation), combine roles only where the site shows they fit, and keep climate corridors and green free of neighbourhoods. Follow every rule the narrative states in numbers (a rhythm, a width, a distance) exactly, or say in `summary.md` why the site forbids it.

The figure must hold the programme: give each neighbourhood a `phase` and the `homes` its area holds at a `density` from the brief, else one you state, and make each phase hold the homes the brief or `programme/` asks for with 15 % to spare, enlarging that phase's land before anything else. Clip every polygon to the site, cut the routes out of the neighbourhoods so massing never builds on one, and take every area you report from the file you wrote. Write `structure-plan.geojson` in WGS84, longitude first, with `shapely` and `pyproj` in a metric projection and one checking script; no Rhino, no drawings, no copies of the site's layers. Every feature has `kind`, `name`, `action` (keep, change or new), `basis` (documented, brief, mapped or hypothesis) and `source` where there is one:

- `neighbourhood` (polygon) with `phase`, `homes` and `density`, which massing fills with buildings
- `centre` (polygon), `level` main or local
- `green` (polygon), `roles` as a list
- `route` (line), `level` main, local or landscape
- `gateway` (point), where the site meets the city or the landscape

`summary.md` has four lines: the figure in one sentence; the homes each phase holds against those asked for; the share of neighbourhood area within a stated distance of a centre or green, along routes where there is a path network, else labelled straight-line; the hypothesis that matters most and what would settle it.
