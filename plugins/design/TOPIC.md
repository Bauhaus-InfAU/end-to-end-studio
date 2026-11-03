# Design

Skills that make the design. `massing` owns the buildings; every other skill here adds a layer in the same format.

- Output: GeoJSON in WGS84 with a `kind` on every feature. `massing` writes `massing/massing.geojson` with `building` (footprint, `floors`, optional `use`, `type`, `phase`), `street`, `open-space` (`use`: park, square, garden, water) and `tree`. Other skills write their own file in their own folder with their own kinds, such as `mobility/mobility.geojson` with `route` and `hub`.
- A community building the brief asks for goes on the structure plan's centre whose `holds` names it; `massing` lists them in its `config.json`.
- A skill never edits another skill's file. If the design has to change, say so in `summary.md`.
- `streets` writes the one street surface (`streets/streets.geojson`); a skill that draws streets reads it when it exists and buffers lines only without it.
- A new skill here: another layer of the design, such as energy, water or a ground floor plan of uses.
