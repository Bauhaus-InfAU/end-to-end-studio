# Sources

The site kit for Regensburg Nord, the project site of Europan 18 (Regensburg). About 2771 x 2728 m: the project site plus a 600 m margin on every side. Generated on 2026-10-28 by the `site-kit` skill.

Bounding box, west, south, east, north: 12.110526, 49.037025, 12.148499, 49.06156. All coordinates are WGS84 longitude and latitude, longitude first.

| File                  | Source                                                                                                                          | Licence                         |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| `../site.geojson`   | traced from Fig. 2 of the competition brief (yellow outline), fitted to OpenStreetMap and snapped to roads and rail within 20 m | brief: Europan; OSM parts: ODbL |
| `buildings.geojson` | OpenStreetMap via Overpass                                                                                                      | ODbL 1.0                        |
| `plots.geojson`     | OpenStreetMap `landuse`, `natural` and `leisure` polygons, clipped to the bounding box                                    | ODbL 1.0                        |
| `streets.geojson`   | OpenStreetMap `highway` ways, all types including paths                                                                       | ODbL 1.0                        |
| `rail.geojson`      | OpenStreetMap `railway` ways                                                                                                  | ODbL 1.0                        |
| `water.geojson`     | OpenStreetMap `waterway` lines and `natural=water` polygons                                                                 | ODbL 1.0                        |
| `kit.json`          | the skill                                                                                                                       |                                 |

## Attribution

Put this line on every map or page that uses the kit:

> Map data © OpenStreetMap contributors (ODbL, https://www.openstreetmap.org/copyright).

## Defaults and gaps

- The Bavarian LoD2 building models were not used, so no building has a surveyed height.
- `height_source` is `osm_levels` for 1213 buildings (from `building:levels`: height is levels x 3.2 m, plus 2 m for roof on houses) and `default` for 1972 buildings. No building has an OSM `height` tag.
- The default floors per `building` tag: house, detached, semidetached_house and terrace 2; residential 3; apartments and dormitory 4; office and school 3; commercial and `yes` 2; hall, garage, shed and other small types 1. Default heights are 3.2 m per floor (plus 2 m for roof at 2 floors or fewer), except industrial 9 m, warehouse 8 m, retail 6 m, church 14 m, garages and sheds 3 m.
- `use` comes from the `building` tag only: residential, light_industrial, office, retail, education, civic, health, accommodation. Everything else is `undefined` (1604 buildings).
- `plots.geojson` uses OSM values as `landuse`, with `natural:` and `leisure:` prefixes for those tags. It is not a full cover: fields without a landuse tag in OSM are missing, and large farmland areas appear as clipped polygons.
- `streets.geojson` has no pedestrian network, no directions and no connected graph.
- The site boundary is traced by eye and by script from a small image. Expect 30 to 50 m of error. Area 109.1 ha against 107 ha in the brief.
