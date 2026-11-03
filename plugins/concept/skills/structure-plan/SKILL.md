---
name: structure-plan
description: Sets the urban figure before any building is placed: neighbourhoods, a hierarchy of centres, the green structure and its roles, main routes and the gateways to the surrounding city, as GeoJSON that massing, mobility and open-space build on. Use when asked for a structure plan, framework plan, urban framework or the urban figure.
---
# Structure plan

Reads: narrative, climate
Model: opus

Work in the proposal folder you are given and write only into `structure-plan/`. Take the idea from `narrative/`, the corridors to keep open from `climate/`, the site and its layers from the project's site folder, and the brief's checklist and the site analysis from `brief-reader/` and `analysis/` where they exist, else from the brief's Markdown; name each missing input in `summary.md`. If there is no site, ask for it. Work on `site.geojson` as it is; where it disagrees with the brief's plans, say so in `summary.md`. This is a framework, not a masterplan: stop at neighbourhoods, centres, green, routes and gateways, and leave buildings, street widths, hubs, planting and detail areas to the skills that follow.

Start from what is there: what to keep, then what to change, and only then what is new. Read the site's barriers, arrival points, existing destinations and the landscape beyond its boundary, and answer each: bridge or hold an edge, open a gateway where a route, a stop or a landscape meets the site, and continue the surrounding streets and paths into it. Divide the site into neighbourhoods by their existing spatial qualities (landscape, fabric, edges, relations) and name them by these, never by assumed residents or lifestyles. Place a main centre and local centres where the narrative and the site point, existing destinations among them, so that no single centre carries everything and a walk leads from one place to the next. Give green areas real extent and their roles (ecology, water, climate, recreation), combining roles in one area only where the site shows they are compatible, and keep climate corridors and green free of neighbourhoods.

Write `structure-plan.geojson` in WGS84, longitude first. Every feature has `kind`, `name`, `action` (keep, change or new), `basis` (documented, brief, mapped or hypothesis) and `source` where there is one:

- `neighbourhood` (polygon), which massing fills with buildings
- `centre` (polygon), `level` main or local, and `holds`: in words, what the brief or the narrative puts there (the stop, a bus station, shops, a market, a school, a daycare, a pool), so the massing builds it on that centre
- `green` (polygon), `roles` as a list
- `route` (line), `level` main, local or landscape
- `gateway` (point), where the site meets the city or the landscape

**Start from the scripts.** Write your decisions, and nothing else (no imports, no files opened), as `structure-plan/design.py` in the proposal folder, after `${CLAUDE_SKILL_DIR}/scripts/design.example.py`: each neighbourhood, centre, green, route and gateway as one `F.add(...)` with its action, basis, source and, for a centre, what it holds; `F.lu`, `F.street` and `F.strip` give you the site's land uses, streets and strips in metres. Run `python "${CLAUDE_SKILL_DIR}/scripts/build.py" <proposal>/structure-plan/design.py --site <site folder> --proposal <proposal> --climate <climate folder>`: it writes `structure-plan.geojson`, `checks.txt` and `check-plan.png`. Read the checks, change `design.py`, run again: they warn when the first phase (give its neighbourhoods `phase=1`) has a smaller share of the land than of the brief's homes, when a main or local route would run over a building you keep or along a foot or cycle way, and when a green for water lies above the ground around it. To take a plan from the brief's pictures, `scripts/georef.py` places a picture on the site from three or more points you name and pulls its colours out as polygons. Don't copy the site's layers; `pip install shapely pyproj`, no Rhino. Write `summary.md` in three lines: the figure in one sentence; the share of neighbourhood area within a distance you state of a centre or green, measured along routes where the site has a path network, else labelled as straight-line proximity, not walking access; the hypothesis that matters most and what evidence would settle it.
