---
name: structure-plan
description: Sets the urban figure before any building is placed: neighbourhoods, a hierarchy of centres, the green structure and its roles, main routes and the gateways to the surrounding city, as GeoJSON that massing, mobility and open-space build on. Use when asked for a structure plan, framework plan, urban framework or the urban figure.
---
# Structure plan

Reads: narrative, climate, programme, analysis
Model: opus

Set the urban figure in `structure-plan/` of the proposal folder: neighbourhoods, centres, green, routes and gateways, nothing finer. Take the idea and its numbers from `narrative/`, the corridors from `climate/`, homes per phase and commerce from `programme/` (else the brief), the site from the site folder; name what is missing in `summary.md`. Use `site.geojson` as it is and only report where it disagrees with the brief.

**Design.** Start from what is there: keep, then change, then new. Open gateways where streets, stops and landscape meet the site, and continue them in. Every main and local route joins another route, an existing street, a centre or the site edge at both ends; no street ends in nothing. Decide on every existing building on land you change: keep it and lead a route to it, or demolish it, each with a reason (a listed building, a use worth keeping, the brief's word, or what stands in the way); never demolish what `analysis/keep.geojson` keeps. Name neighbourhoods by their spatial qualities, never by assumed residents. Put the main centre on the stop and gather the homes around it; local centres take the rest. Give green real extent and roles, and keep climate corridors free. Keep homes out of the climate's loud zones and put commerce there to shield them. Follow the narrative's figure and numbers exactly (how many islands on which side, a width, a distance), or say why the site forbids it.

**Hold the programme.** Each phase holds its homes and its floor area (homes, commerce) under the storey cap with 15 % to spare; where it falls short, enlarge the neighbourhoods before raising density. At least half of the homes lie within a 400 m walk of the stop, or say why not.

**Build.** Copy `${CLAUDE_SKILL_DIR}/scripts/design.example.py` to `structure-plan/design.py`: one `F.programme(...)`, then one `F.add(...)` per feature, decisions only. Run `python "${CLAUDE_SKILL_DIR}/scripts/build.py" <proposal>/structure-plan/design.py --site <site> --proposal <proposal> --climate <climate>` and change `design.py` until `checks.txt` shows no SHORT, in at most four builds. A route end that meets nothing, an existing building on changed land with no decision, a kept one no street reaches, or a demolished one the analysis keeps is SHORT too. They also warn when the first phase has less of the land than of the homes, a main or local route runs over a kept building or along a foot way, or a water green lies above the ground around it. The scripts check every field, clip to the site, cut routes out of neighbourhoods and measure every area. `scripts/georef.py` places a picture from the brief on the site. Needs `pip install shapely pyproj`.

Features: `neighbourhood` (`phase`, `homes`, `density`, `commerce_m2`), `centre` (`level` main or local, `holds`: the stop, shops, a school), `green` (`roles`), `route` (`level` main, local or landscape), `gateway` and `existing` (the buildings inside it, with a `reason`; massing builds on demolished land), each with `action` (keep, change, new; keep or demolish for `existing`), `basis` (documented, brief, mapped, hypothesis) and `source`.

**`summary.md`, three lines:** the figure, with the homes and floor area each phase holds against those asked; the share of homes within a 400 m walk of the stop, from `checks.txt`; the hypothesis that matters most and the evidence that would settle it. Write nothing else.
