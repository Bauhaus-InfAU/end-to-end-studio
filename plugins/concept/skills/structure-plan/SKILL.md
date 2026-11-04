---
name: structure-plan
description: Sets the urban figure before any building is placed: neighbourhoods, a hierarchy of centres, the green structure and its roles, main routes and the gateways to the surrounding city, as GeoJSON that massing, mobility and open-space build on. Use when asked for a structure plan, framework plan, urban framework or the urban figure.
---
# Structure plan

Reads: narrative, climate, programme
Model: opus

Set the urban figure in `structure-plan/` of the proposal folder: neighbourhoods, centres, green, routes and gateways, nothing finer. Take the idea and its numbers from `narrative/`, the corridors from `climate/`, homes per phase and commerce from `programme/` (else the brief), the site from the site folder; name what is missing in `summary.md`. Use `site.geojson` as it is and only report where it disagrees with the brief.

**Design.** Start from what is there: keep, then change, then new. Open gateways where streets, stops and landscape meet the site, and continue them in. Name neighbourhoods by their spatial qualities, never by assumed residents. Put the main centre on the stop and gather the homes around it; local centres take the rest. Give green real extent and roles, and keep climate corridors free. Keep homes out of the climate's loud zones and put commerce there to shield them. Follow the narrative's figure and numbers exactly (how many islands on which side, a width, a distance), or say why the site forbids it.

**Hold the programme.** Each phase holds its homes and its floor area (homes, commerce) under the storey cap with 15 % to spare; where it falls short, enlarge the neighbourhoods before raising density. At least half of the homes lie within a 400 m walk of the stop, or say why not.

**Build.** Copy `${CLAUDE_SKILL_DIR}/scripts/design.example.py` to `structure-plan/design.py`: one `F.programme(...)`, then one `F.add(...)` per feature, decisions only. Run `python "${CLAUDE_SKILL_DIR}/scripts/build.py" <proposal>/structure-plan/design.py --site <site> --proposal <proposal> --climate <climate>` and change `design.py` until `checks.txt` shows no SHORT, in at most four builds. The scripts check every field, clip to the site, cut routes out of neighbourhoods and measure every area. `scripts/georef.py` places a picture from the brief on the site. Needs `pip install shapely pyproj`.

Features: `neighbourhood` (`phase`, `homes`, `density`, `commerce_m2`), `centre` (`level` main or local, `holds`: the stop, shops, a school), `green` (`roles`), `route` (`level` main, local or landscape) and `gateway`, each with `action` (keep, change, new), `basis` (documented, brief, mapped, hypothesis) and `source`.

**`summary.md`, four lines:** the figure; homes and floor area per phase against those asked; the share of homes within a 400 m walk of the stop, from `checks.txt`; the hypothesis that matters most and the evidence that would settle it. Write nothing else.
