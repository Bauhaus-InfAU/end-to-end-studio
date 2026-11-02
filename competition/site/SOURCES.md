# Sources

The site kit for Regensburg Nord, the project site of Europan 18 (Regensburg), remade on 2026-11-03 by the `site-kit` skill. About 2,800 x 2,900 m: the project site plus a 600 m margin on every side.

Bounding box, west, south, east, north: 12.109104, 49.03909, 12.148261, 49.063572. All coordinates are WGS84 longitude and latitude, longitude first, except `terrain-dgm1.tif` (ETRS89 / UTM 32N, EPSG:25832).

| File | Source | Licence |
| --- | --- | --- |
| `site.geojson` | re-traced from the brief's infrastructure plan (brief p. 36, Fig. 25-26; the settlement and green plans on pp. 36-37 carry the same outline). Placed on the map by four features that both the plan's aerial and OSM show (underpass under rail and Pilsenallee, sports pitches, Pilsenallee ramp, B16 underpass), fit residuals 12 to 24 m, 21 vertices read by eye. Checked against the run-5 check outline (`proposals/2026-11-02_run-5/structure-plan/brief-outline-check.geojson`, 113.8 ha): overlap 97 percent, largest gap 34 m, centroid 2 m apart | brief: Europan; map base OSM, ODbL |
| `buildings.geojson` | footprints OpenStreetMap via Overpass (2026-11-03); heights from the Bavarian LoD2 building models (`measuredHeight`, CityGML tiles 726_5436, 728_5436, 726_5438, 728_5438 from download1.bayernwolke.de/a/lod2/citygml/) | ODbL 1.0 (OSM); CC BY 4.0 (LoD2) |
| `buildings-3d.geojson` | Bavarian LoD2 CityGML (same four tiles as the heights), every WallSurface and RoofSurface of the 5,597 buildings whose footprint touches the bbox, as Polygon with [lon, lat, z], z in metres above the building's lowest ground point (0.1 m), coordinates 7 decimals; `id` is the `buildings.geojson` id where the footprints overlap (5,175 buildings), else the LoD2 id; `surface` wall or roof, `roof_type` the LoD2 roof code; ground surfaces left out. 48,479 surfaces (37,968 walls, 10,511 roofs), 13.4 MB. One structure (DEBY_LOD2_6337045, 12.113 E 49.057 N, 65.5 m) is above 60 m; kept as in the source | CC BY 4.0, Bayerische Vermessungsverwaltung |
| `terrain-dgm1.tif` | Bavarian DGM1, 1 m grid, tiles 727 to 729 / 5436 to 5439 from download1.bayernwolke.de/a/dgm/dgm1/, joined and cut to 727200-730000 E, 5436400-5439300 N. Float32 metres above sea level (DHHN2016), 2800 x 2900 cells, GeoTIFF, nodata -9999 (none inside) | CC BY 4.0 |
| `plots.geojson` | OpenStreetMap `landuse`, `natural` and `leisure` polygons, clipped to the bounding box. NOT cadastral parcels, see below | ODbL 1.0 |
| `streets.geojson` | OpenStreetMap `highway` ways, all types including paths | ODbL 1.0 |
| `rail.geojson` | OpenStreetMap `railway` ways | ODbL 1.0 |
| `water.geojson` | OpenStreetMap `waterway` lines and `natural=water` polygons | ODbL 1.0 |
| `street-land.geojson` | ALKIS actual land use (Tatsaechliche Nutzung) of Stadt and Landkreis Regensburg, geodaten.bayern.de: Strassenverkehr as `street`, Platz as `square`, Weg as `path`. Kept from the previous kit (2022-07-05 data), not downloaded again | CC BY 4.0 |
| `kit.json` | the skill | |

## Attribution

> Map data © OpenStreetMap contributors (ODbL, https://www.openstreetmap.org/copyright).

Where heights, terrain or street land are used:

> Building models, terrain model and land use © Bayerische Vermessungsverwaltung, www.geodaten.bayern.de (CC BY 4.0).

## Heights (`height_source`)

- `lod2` for 3,880 OSM footprints plus 1,296 footprints that exist only in LoD2 (marked `osm: false`, `building: yes`, `use: undefined`). Height is the LoD2 `measuredHeight` (ground to highest roof point), area-weighted if several LoD2 parts cover one footprint (match: overlap of at least 30 percent of the smaller shape). Because it is the roof top, pitched-roof houses read higher than an eaves height.
- `default` for 179 OSM footprints with no LoD2 model: floors from the `building` tag (house 2, residential 3, apartments 4, hall and garage 1, other 2), 3.2 m per floor plus 2 m of roof at 2 floors or fewer; industrial 9 m, warehouse 8 m, retail 6 m, church 14 m, garages and sheds 3 m. No `osm_levels` or `osm_height` source remains because LoD2 covered every footprint that had one.
- `floors` is the OSM `building:levels` when present, else height / 3.2 rounded (not surveyed).
- The LoD2 data is dated 2021 to 2022 for this area; OSM footprints are today's. Buildings built since are in OSM with a default height.
- The OSM footprint count (2,763) is lower than the old kit's (3,185), whose extent was smaller; the OSM layer was re-fetched, not edited. Not explained beyond OSM edits since October.

## Cadastral parcels: not available

Bavaria does not offer ALKIS parcels (Flurstuecke) openly as vectors. What is open is the ALKIS Parzellarkarte as a WMS picture (https://geoservices.bayern.de/od/wms/alkis/v1/parzellarkarte, CC BY 4.0) with buildings and parcel lines but no parcel numbers and no geometry to download; the vector parcels are a paid product. `plots.geojson` therefore stays OSM land use (it is not a full cover: fields without a landuse tag are missing; 3 features are genuine multi-part polygons). The ALKIS actual land use already in the kit (`street-land.geojson`) holds only streets, squares and paths.

## Site outline

- Area 112.8 ha (EPSG:25832), the brief says about 107 ha and the run-5 check outline measures 113.8 ha. The old outline (109.4 ha) was traced from Fig. 2 and lay about 225 m south of the brief's plans.
- Placement accuracy: 12 to 24 m at the four control points; the dashed line is drawn about 15 px (about 25 m) thick on the plan and was read by eye. Expect 30 to 50 m. Not snapped to roads or rail. The brief's outline cannot be matched exactly because the plan's aerial is a small grey image.

## Geometry check

Every layer was validated before writing (`make_valid`, no feature dropped for being invalid). Repaired: streets 9 (multi-part lines split into single lines; features 972 became 980), street-land 3 duplicates removed, all others 0. No OSM ring was unclosed, no empty or zero-area shape appeared, no repair changed an area by more than 1 percent. Final check: 0 invalid, 0 empty in all layers.

## Other gaps

- `street-land.geojson` covers the old extent: its margin north of the site is about 270 m, not 600 m. West, east and south it covers at least 500 m.
- `water.geojson` has two lakes and no waterway lines in this extent.
- `streets.geojson` has no pedestrian network, no directions and no connected graph.
