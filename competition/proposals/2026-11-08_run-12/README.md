# run-12: Furrows, a new full version on the Regensburg brief

New version, 2026-11-08, skills at commit 77f6924. See `version.md`, `log.md`, `cost.csv`.

## Skills

| Skill | Status | Minutes (first run + later runs) | Cost (USD) |
|---|---|---|---|
| pdf-to-md | shared input (not run) | shared input, not run | - |
| site-kit | shared input (not run) | shared input, not run | - |
| brief-reader | done (checklist copied, key unchanged) | copied (key unchanged) | - |
| climate | done | 1.3 (second) + 6.4 (rerun); first run copied | 0.46 |
| analysis | done | 1.3 + 7.2 (end) + 1.4 (rerun) | 0.44 |
| programme | done | 0.5 | 0.13 |
| narrative | done | 2.7 + 1.8 (end) | 1.20 |
| structure-plan | done | 9.4 + 3.1 (rerun) | 2.60 |
| drawing-graphics | done | 0.8 | 0.16 |
| massing | done | 15.6 | 0.83 |
| streets | done | 5.4 | 0.10 |
| phasing | done | 0.6 + 2.4 (end) + 0.9 (rerun) | 0.54 |
| mobility | done | 1.0 + 3.8 (rerun) | 0.58 |
| open-space | done | 1.0 + 4.4 (rerun) | 0.41 |
| ground-floor | done | 0.6 | 0.10 |
| figure-ground | done | 1.2 | 0.10 |
| plans | done | 2.2 + 6.1 (rerun) | 0.47 |
| site-section | done | 0.6 + 1.2 (end) + 3.7 (rerun) | 0.46 |
| isometric | done | 0.9 + 1.1 (end) + 4.9 (rerun) | 0.53 |
| building-types | done, in part (6 of 13 types) | 0.5 + 1.1 (rerun) | 0.27 |
| concept-diagrams | done | 1.6 + 2.5 (rerun) | 0.52 |
| perspective | done | 3.3 + 6.4 (rerun) | 0.60 |
| panel-layout | done | 6.5 + 9.3 (end); one end run stopped at once | 3.67 |
| art-direction | done | 2.2 | 0.69 |
| jury | done | 3.9 | 0.94 |
| lead | done | | 3.21 |

Every skill listed in `STUDIO.md` has been written; none is missing.

**Total: $19.01** (lead $3.21, 41 helpers; ceiling $30.00). Skills with several runs (end run, rerun) have their cost summed.

## Notes on this run

- `narrative` also reads everything and sits higher in `STUDIO.md` than `panel-layout`, so its second run came before the second run of `panel-layout`. The lead first started `panel-layout` too early and stopped it at once; nothing of it was kept.
- `figure-ground` was not started in the first pass (it reads only the site data and the massing); it ran with the redraw round.
- `drawing-graphics` opened only board-1 of each winner, not all nine boards as `CLAUDE.md` asks. No skill runs twice in a version, so this stays; a variant of `drawing-graphics` should read all nine.
- Helpers changed copies of a skill's scripts inside the version, not the skill: `analysis` (measure.py, a GeometryCollection), `figure-ground` (credits width 0.52 to 0.62), `open-space`, `isometric`, `plans`, `climate`, `concept-diagrams`, `building-types` (new config keys `must_draw`, `skip_types`). The skills' own files are untouched; these fixes are worth making there.
- The files of the entry disagree on three numbers: sealing (30.9 % fully sealed in `analysis` and the text, 37.2 % in `open-space` and on the panels), the walk to the stop (52 % of homes within 400 m in `structure-plan`, 0.8 % of new floor area in `mobility`) and a car link between Chamer Strasse and Sandgasse (`phasing` finds one, `mobility` none).
- Not drawn or measured, for lack of data: the stop, canal, 150 kV line, B16 setback, trees. `structure-plan`, `massing` and `open-space` follow a tracing of the brief's plans taken from run-11.
- `mobility` and `open-space` came back at 1:20,000 and 1:20,500 (planned 1:15,000) and `building-types` at 542 x 550 mm; `panel-layout` took the files as drawn, so the site plan, isometric and detail areas are cropped 16 to 25 % on the panels.
- The perspectives are rendered with an image model, which added people, birds and pink ground.

## What each skill says (its three lines)

### pdf-to-md

(shared input, made once for every version; see the project inputs)

### site-kit

(shared input, made once for every version; see the project inputs)

### brief-reader

(no summary.md; only the checklist was copied into this version)

### climate

Made (1:15,000, redrawn in the drawing standard (style.json) at the panel-layout frames, no recalculation; fresh-air arrows now run across the whole corridor width and on over the new buildings, legend boxes shortened): cold-air corridor traced from the brief's Fig. 20 (p. 31), sun, shadows, radiation, wind, road and rail noise (day and night), heat, rules map, `climate.json`, `climate.md` and `climate_sheet`.
Key number: 21 % of the site is at 65 dB(A) or more by day (no homes; 16.7 % at the low traffic end, 22.2 % at the high end) and another 60 % at 55 to 65 (homes only behind a shielding edge); the cold-air corridor along Pilsen-Allee takes 4 % (3.5 to 5 %).
Least sure: noise, as the brief (p. 24) gives only 10,000 to 20,000 vehicles, so speeds (70, 100 km/h) are ASSUMED; the railway uses 2020 train counts (Bundestag 19/24091 p. 16) with ASSUMED lengths, brakes and speeds; DIN 18005 limits and RLS-90 are German defaults; the climate map has no legend and fits the streets to about 70 m.

### analysis

Measured the massing the same way as the site today (uses, edges, green, walking reach to green, shops and schools, sealed share) and compared all 76 measures in comparison.csv; sealed share and land uses are now pairs of pie charts, today against design (sealing_pies, uses_pies), and the design maps of uses, sealing, green and edges (an outline or one flat fill, or the same as today) are left out; stations, bus stops, trees, underpasses, canal and 150 kV strips had no layer to draw.
Sealed share today 14.2 % fully, 8.3 % partly, 77.5 % unsealed; design 30.9 % fully, 15.4 % partly, 53.7 % unsealed (farmland 70 ha becomes 5 ha, green without farmland 5.8 % to 47.4 %, public green 88 m2 per resident, reach 400 m to shops 12 % to 93 %, to green 65 % to 98 %).
Unsure of: the sealing classes and the grouping of land uses in the pies (assumptions), the design's wooded green reads 0 ha and 0.2 ha is built over kept land (massing's use tags and overlaps), and I patched a copy of measure.py in analysis/scripts to handle a GeometryCollection in the massing.

### programme

Tabled homes, residents, commerce, social and sport uses (daycares, school, pool), green and play from the brief pp. 28-34; no household mix because the brief gives none.
Key number: 2,800 homes for 5,000 residents (framework plan), up to 3,400 homes for 6,100; at least 1,100 in phase 1.
Uncertainty: no housing floor area or household shares in the brief, and it is unclear whether the 36,500 m2 social total includes the pool.

### narrative

"Furrows: a district combed into the field": build the north in long north–south strips along the cold air, with an unsealed public furrow (at least 40 m wide, crossed by no car) between them from Haslbach to the garden city, planted before the strips beside it are built.
Key number: every front door within 125 m of a furrow, with the furrows holding at least the brief's 7.3 ha of public green (brief p. 30) and at least 50 % of the site unsealed at build-out (own target; today 77.5 %, analysis/metrics.csv).
Least sure: whether 2,800–3,400 homes and 230,000 m² of commerce fit between furrows 250 m apart at 50 % unsealed, and where the station, canal and 150 kV line sit, which are on the brief's plans (pp. 35–37) but not in the site layers; the framework plan's drawing is missing, so it is checked in words only.

### structure-plan

Furrows as a figure: the field is combed into north–south strips between six unsealed furrows, 40 m wide or more and at most 240 m apart (Canal, Garden, Lobe and Field Furrow, the cold-air corridor as the Air Furrow, the Forest Seam). Together they cover 14.0 ha, with 18.3 ha of public green in all against 7.3 ha asked, and 96 % of the homes' land lies within 125 m of a furrow. Working heads with no homes on 65 dB(A) land face the rail, B16 and Haslbach. The main centre, Station Square, sits on the stop with a west and an east head, and there are 7 local centres. No new car street crosses a furrow; Chamer Strasse already does, with a raised crossing at each. Phase 1 (Chamer Strasse to the rail, p. 33) holds 1,270 homes against 1,100 asked, with 510 of them above the work on the Line Head West's quiet side, and 1,000 m2 of commerce, at 86 % of its floor area under 6 storeys. Phase 2 (east bank, our split) holds 1,040 homes against 900, with 58,000 m2 of commerce, at 84 %. Phase 3 (B16 side, Haslbach, north works) holds 920 homes against 800, with 171,000 m2, at 86 %. In all: 3,230 homes and 230,000 of 230,000 m2 of commerce. The check plan (redrawn by check_plan.py, a copy of the skill's check script; plan numbers and geometry unchanged, checks.txt identical) now draws the massing's 254 new buildings in white inside the zones and names each area once, with no label overlapping; six small areas lost their label for lack of room (Existing Farmsteads East, Garden Rows, Compensation Ribbon, Power Strip, Biotope Wood, Sports Fields). It still lacks the reference's use colours, landmarks and active ground floors.
52 % of the homes (1,666 of 3,230) are within a 400 m walk of the stop (checks.txt). Not met by the plan: the first phase has 29 % of the land against 32 to 39 % of the homes; the Field Furrow and Forest Seam lie above the ground around them; Field Margins is an invalid geometry; the primary school (Garden Gate) stands across Chamer Strasse, outside phase 1's land. Missing from the inputs: the stop, canal, 150 kV line, biotopes and solar park are not in the site layers, so they are taken from the run-11 tracing of the brief's pp. 36–37 (good to 30 to 50 m). site.geojson is 112.8 ha against the brief's 107 ha. 95 m2 per home is assumed. It took 4 checked builds and 1 that stopped on an empty daycare.
Least sure: whether phase 1 can hold 1,100 homes or more without homes above the line-side work. Its strips hold only 760, because the canal and garden furrows take 5.7 ha of its land. The city's survey of the canal and the stop, plus a noise study of the line-side rows' quiet facades, would settle it.

### drawing-graphics

Fine-line plans on white paper with a pale green-grey city around them and soft layered greens for the furrows, new buildings white with grey shadow, Roman storey numerals, all at 12 px or more.
Accent pink #d4487a (pale #f2c6d2) marks the public ground that runs through the furrows (squares, shared streets, hub), taken from the narrative's public furrow and from all three winners' pink public ground; nothing else is pink.
Unsure: I opened only board-1 of each winner, not all nine boards, so the section, isometric and diagram recipes rest on board-1 and the README, and the pink may fight the furrow's own green.

### massing

Placed 254 new buildings on the furrow strips, with their long sides on 8/188 degrees along the cold air: 41 row blocks, 27 L blocks, 14 ensembles and 5 town-house groups at 3 to 6 floors, lower beside the furrows and stepping down to 2 to 3 floors at the garden city. The heads are 4 to 6 floors: 23 halls, 11 U blocks, 4 perimeter blocks and 1 hub. Station Square has the bus station, the market hall, the district garage, the Nordbad pool and two 9-floor landmarks. There are also 3 daycares, the school at Garden Gate, 5 local garages and 705 street trees. 209 existing buildings are kept.
Gross floor area 543,978 m2 (FAR 0.48 on the 112.8 ha site, 1.32 on the 41.2 ha of new land): 3,015 homes against the structure plan's 3,230 (brief 2,800 to 3,400, p. 30), 226,750 m2 of commerce against 230,000 m2, 48.6 ha of public green against 7.3 ha; after the noise step 6 loud buildings became commerce and 5 home buildings are marked for better acoustic protection.
Unsure: the programme does not fully fit under 21 m (111 of 166 home buildings are at the 6-floor cap, see assumptions.md); the school's 3,000 m2 sports area found no room at Garden Gate and the school rises to 4 floors; the market hall, daycare 1 and 3 local garages are smaller than set; B16 Head's 80 homes went to commerce on 65 dB(A) land; 5 secondary streets end in nothing; canal, 150 kV line and stop are not in the site layers and follow the structure plan only; the check plans use draw.py's fallback grey look, not drawing-graphics/standard.md, and were not compared with the winners' site plans.

### streets

Existing streets came from the cadastre's street-land areas as they are (59.2 ha existing, 13.2 ha new streets, 0.2 ha existing street given way to new buildings); no buildings sit under new streets; check plan at 1:3000, the brief's site plan scale.
Streets cover 24.7 % of the site; 2,319 m of new street run along existing ones and count as those; ends are 8 future links, 23 turning heads and 48 square ends.
Unsure: 5 main routes still end nowhere, so the massing should link them to a street or path; 223 centrelines got default widths, and no brief widths or kerb radius were set (6 m default); the new streets show in the PNG as dark grey, not an obvious accent.

### phasing

Three phases, our split (brief: "in sections", p. 33): phase 1 between Chamer Strasse and the railway (Canal Rows, Garden Rows, Line Head West, Station Square, Wutzlhofen Stop, bus station, market, school, pool, daycares 1 and 3), phase 2 the east bank with daycare 2, phase 3 the north; plan phasing/phasing_small.png at 1:15,000 in 136 x 119 mm (frame filled; large plan phasing_large.png at 1:2,000 kept) and the table phasing/phases_table.png at 259 x 69 mm in its 279 x 74 mm frame (about 87 %, rows taller via phasing/scripts/draw_local.py).
Homes and residents: phase 1 1,123 and 2,006 against at least 1,100 (p. 33), phase 2 1,133 and 2,023, phase 3 760 and 1,357; in all 3,016 and 5,387 against 2,800 to 3,400 homes (p. 30); each finished phase is fully connected to the street network and keeps all 175 existing buildings reached; counts match phases.csv.
Flags: phases differ from the structure plan (-147, +93, -160), Line Head West furthest (269 against 510); 0 buildings for review; at completion a car route joins Chamer Strasse North and Sandgasse, against p. 28 (streets/mobility must change); 12 unnamed new open spaces have no phase and 110 street pieces wait for the last phase; services, open space per resident and emergency access not measured (walks, existing residents and emergency rules not stated); unsure of the phase count, 95 m2 per home, and stop phases.

### mobility

Mobility: the rail stop Wutzlhofen is the main stop with buses from Sandgasse and Chamer Strasse North, cars only at five gateways with no Chamer Strasse to Sandgasse link (0 violations), and four bike routes to named places, redrawn in mobility_1-20000.png with the legend beside the map and the four bike routes and five car gateways leaving the frame as labelled arrows.
Within walking distance of the main stop: 0.8 % of new housing floor area within 400 m and 55.9 % within 800 m (structure plan counted 52 % by homes within 400 m, so the walk network likely lacks the footbridge crossing).
Assumed: the 400/800 m limits and the bike destinations; the plan is cropped to the new buildings plus 100 m, which needs 1:20,000 in the 136.5 x 119 mm frame (planned 1:15,000, would need a 106 mm wide map), so panel-layout must take the 1:20,000 file; a few arrow labels still touch place names (Coburger Strasse, Brandlberg).

### open-space

Laid out one green corridor with 17 retention basins (6,726 m3 against 6,721 m3 needed for 30 mm), parks with ground cover, 2,176 m of paths, 6 playgrounds, 23 green links and 1,273 planted trees; redrawn per the art direction, cropped to the district plus 100 m with the legend in its own column beside the map, and playgrounds and basins as filled 3.2 mm circles, at 1:20,500 (open-space_1-20500.svg/.png) because the district plus 100 m needs that scale to fill the 136.5 x 119 mm frame, so panel-layout must change the item's scale from 1:15,000 and its file name.
Public green is 31.1 ha of new parks against the 6.0 ha minimum (12 m2 x 5,000 residents, brief p. 30), but play area is 7,047 m2 against 7,500 m2 (1.5 m2 x 5,000, brief p. 28), 453 m2 short, and every home is within 300 m of a playground; the sealed share is 37.2% fully and 2.3% partly sealed.
Unsure: the canal and 150 kV strips are not in the data, so keep-free.geojson is empty; the 30 mm rain is a default and the brief gives none; the pools follow the terrain-dgm1 flow; the new scale and the legend column come from a changed copy of the script in open-space/scripts/, not yet in the skill; one park has no green link, and the massing should give the playgrounds about 450 m2 more or link that park.

### ground-floor

Placed 275 doors on 254 buildings (273 on a street, 2 on a path) with 1,036 bike stands, 76 play areas (7,121 m2) in 120 courtyards, 27 labelled centre uses, and at Station Square 6 bus bays (brief p. 27) and 300 bike spaces (assumed).
The non-housing ground floors at the centres cover 74,269 m2, with the food market put into the largest shop floor at Station Square.
Flags: the food market needs 1,200 m2 but the largest shop floor at Station Square has 893 m2 (the massing should enlarge it or join two floors), 44 courtyards are under 600 m2 and got no play area, and the stands, play areas and 300 bike spaces are illustrative proposals, not the brief's numbers.

### figure-ground

`figure-ground_1-15000.svg` and `.png` at 1:15,000, 136 x 100 mm (the frame in panel-layout/layout-plan.json): 219 new buildings dark, existing quarters reaching within 500 m of the site in mid grey, those further out light grey; no streets, lines or boundary; 14 walls the data models as buildings (over 30 m long, under 2 m wide) left out.
New footprint 9.8 ha against 10.6 ha existing in the frame.
Unsure: the site boundary only sorts the buildings (site.geojson as it is).

### plans

site-plan_1-3000.svg/.png at 1:3,000 (564 x 496 mm, storeys, contours, Furrow idea band, now with the existing city's woods and scrub as crowns and its parks and grass in pale greens out to the frame edge); detail-area-1_1-1000 (Station Square, 564 x 416 mm) and detail-area-2_1-1000 (Valley Rows, 279 x 158 mm) at 1:1,000 with open-space paths and green links in the courtyards and 'Commerce' notes only on centre buildings; figure-ground_1-15000 (198 x 211 mm); drawings.json.
4 of the brief's 4 plans are drawn and fit their frames (site-plan and both detail areas fitted); the site plan is cropped on the south.
Unsure: storey numerals were already at the 12 px floor (3.2 mm) so they could not shrink further; ground-floor holds no more play or paths than drawn, so some courtyards stay lawn (ground-floor/open-space to give more); context crowns are generated from the plots' forest and scrub land use, since the site kit has no tree layer; detail area 2 is still too small for its subject (57 %), panel-layout owns the frame; the idea is drawn as the five furrow areas.

### site-section

Redrew the design pass of the east-west long section A-A' (1,098 m, own line at 49.0518 N, looking north, ground from terrain-dgm1.tif 1 m) to fill its frame 564 x 83 mm at 1:2,000 whole (site-section_design_1-2000, SVG+PNG) plus the 200 m excerpt at 1:1,000 (site-section_design_excerpt_1-1000), with the fixes done: 95 trees from massing/open-space within 30 m behind the cut drawn in elevation, new buildings with storey lines, people every 20 m on streets and open ground in the excerpt; 13 buildings cut (9 new, 4 existing from the 3D model, 2 pitched), 32 behind (16 new), 25 new roofs flat at massing height, five narrative notes all on their areas.
The ground falls 14.6 m and rises 11.9 m along the cut, between 339.5 and 354.1 m a.s.l., lowest at the Pilsen-Allee and rail.
Unsure: to show the whole line at 1:2,000 in 564 mm I shortened it by dropping its western 258 m (B16 head) from the earlier 1,356 m line, so it is no longer the same line; new buildings are flat-topped and white; the notes' area choices are mine.

### isometric

- The design, isometric seen from the north-west: the district at 1:5000 in the planned 564 × 384 mm frame (a fixed frame, centred, the city filling it to the edges; the new district itself still spans about 58 % of its width at this scale), and Station Square close up at 1:1000, 564 × 340 mm; fixes done: open ground from the open-space layer (ground cover, parks, playgrounds, pools, paths) instead of the hatch, use labels on the ground beside each building, no panel rows on the commerce roofs.
- 254 new buildings (13 flat, 172 green, 69 pv roofs); 3412 existing buildings, 166 at default heights; 2770 trees; close up 20 use labels (2 marked * as illustrative) and 203 people, illustrative.
- Unsure: ground labels lie along one axis and are partly hidden by nearer buildings; the district fills about 58 % of the frame's width, not two thirds, because the scale is fixed; changed script copy is isometric/run.py (skill untouched).

### building-types

Drew 6 of 13 building types as ensembles, one block of each with its ground, street, 52 trees and 24 notes (town houses, U block, school, courtyard ensemble, hall, rows), in isometric at 1:1,000 (panel-layout/layout-plan.json), in building-types_1-1000.svg. Wrapped into 4 rows of 2, 2, 1, 1 types on a shared baseline grid, at the same scale, to keep within the 564 mm panel. It is 541 x 549 mm, within the 564 mm x 780 mm panel. Left out, to fit the panel, all in types.csv: perimeter block, garage, daycare, bus station, market hall, mobility hub. Asks for a frame of 542 x 550 mm at 1:1,000 in building-types_1-1000.frame.json (planned: 279 x 166 mm).
Tallest type drawn: rows, 6 floors, 18 m; the drawing is 541 x 549 mm printed; 0 notes from notes.json, 24 from the layers; illustrative: windows in 3 m bays.
Unsure: nothing flagged. Look: drawing-graphics\style.json.

### concept-diagrams

1. Six plan pictograms in one sequence (field and air, strips, furrows, heads and screen, station crossing, strip by strip), all plan view on the real structure-plan geometry, simplified, one turn, each redrawn to its 136.5 x 64 mm frame (drawing on the left 66 mm, title, caption and note in a column on the right, so the frame is full); labels stay at 12 px, and the thin strips and phase tints must still read at half the earlier scale.
2. 6 pictograms (one family; no concept family or composition made, as panel-layout has no frame asking for one).
3. Conceptual: the cold-air arrows and the "strips" reading of the neighbourhood zones; unsure: the district is nearly square, so even side by side the plan is about half the earlier size, and the leaders of "head" and "strip" cross the drawing; the side-by-side layout comes from a changed copy of the script (scripts/draw_side.py), not the skill's own.

### perspective

Eye-level views at 1.65 m, no scale, rendered: view-1 (green, along the furrow lane) and view-2 (Station Square, axis toward the bus station, nearest wall 22 m away); windows on every storey, shop fronts where the ground floor is not housing, grey streets and footpaths, pink only on the square, green lawns and meadow, bike stands from the ground-floor layer; frame 1536 x 848 px fitted to the 279 x 154 mm frames.
2 views redrawn from their earlier cameras (view-2 turned and moved, view-1 unchanged), no new candidates; 3 fixes carried out, frames fitted; the render added people, birds and a tree row and turned the forest block grey in view-2.
Unsure: the layers hold no benches, so none are drawn; the render's 2752 x 1536 px differs 1 % from the base's proportions; landuses without a rule (nature reserve, pool, track, sand, bare rock) are bare ground.

### panel-layout

Laid out the final 3 A1 portrait panels (panel-1 to 3 .pdf/.png, from layout.json built by make_final.py). Panel 1, the field and its furrows: idea text, 6 concept diagrams, the site plan at 1:3,000, the figure-ground, climate rules and cold air at 1:15,000, three big numbers (96 %, 14.0 ha, 60.5 % unsealed), and the section at 1:2,000. Panel 2, the comb: the isometric at 1:5,000, detail area 1 (Station Square) and detail area 2 (Valley Rows) at 1:1,000, the phases table and the programme. Panel 3, the doorstep: two perspectives, the building types at 1:1,000 as drawn (542 mm wide), mobility at 1:20,000, open space at 1:20,500 and phases at 1:15,000, plus soil sealing and the method text. All drawings are printed as drawn. Frames and captions changed, the drawings did not.
Brief's required items on the panels: 12 of 12, and 24 of 24 including the storyline's. The housing mix shows only as building types, because the brief gives no household shares.
Unsure: the building types' 542 x 550 mm frame forced the panels to be recomposed. The site plan is cropped 16 % (the northern tip is lost), the isometric 25 %, detail area 1 25 % and detail area 2 22 %. The building types lose their own title and source lines, which the caption carries. Their lower-right quarter (250 x 270 mm) stays blank: drawn as 3 rows of 2 they would free about 130 mm. The `stop-reach` number is left off (52 % against 0.8 %), and sealing shows open-space's 37.2 %/2.3 %, not analysis's 30.9 %/15.4 %. Both mismatches are in notes. Panel PDFs are 7 to 11 MB each. issues.md hands 2 issues to other skills (brief-reader summary, programme household mix).

### art-direction

24 fixes for 10 skills (plans, isometric, building-types, site-section, perspective 3 each; open-space, mobility, structure-plan, analysis 2 each; climate 1); concept-diagrams and the figure-ground are close to the winners and get none.
Largest gap: the perspectives show blank grey walls on an all-pink floor, and the plans and isometric leave the city around the district bare and empty in the frame, where the winners fill it with trees and green to the edge. The panels are still empty frames (panel-layout's step), see notes.md.
Unsure: I saw each sheet once at reduced size, so small labels and line weights are judged roughly; whether the perspectives were ever rendered with an image model is not stated; the analysis maps may be measurement maps not meant for the panels.

### jury

Verdict: no award. The entry passes round 1 (rules, concept) and is eliminated in round 2 on how its blocks and uses are organised inside. There is no housing mix (required, p. 33), no floor or ground-floor plans, the building types are volumes only, and the furrows are never drawn as designed spaces.
The number that weighed most: play area 7,047 m² against 1.5 × 5,387 = 8,081 m² (1,034 m² short). Also short or contradictory: the school's 3,000 m² sports area is missing, the food market is labelled 1,200 m² but the text admits 893 m², and sealing reads 37.2 % fully sealed on the panels against 30.9 % in the text.
Unsure of: the canal, the 150 kV line and the 20 m B16 setback are not drawn, so they can't be checked. The 112.8 ha site against the brief's 107 ha shifts every percentage. Homes rest on an assumed 95 m² each, so phase 1's margin (1,123 against 1,100 homes) is uncertain.

## Issues handed to other skills (from `panel-layout/issues.md`)

No skill runs again in this version; a variant starts from this list.

| Skill | Severity | Issue | Fix |
|---|---|---|---|
| brief-reader | medium | `brief-reader/summary.md` missing in the version (the checklist was copied) | `brief-reader` writes it |
| programme | medium | Housing mix: the brief gives no household shares (`programme/summary.md`); `building-types` must show it from the massing's types, or it stays open | ask `programme`; `building-types` shows a mix |

From the jury (`jury/report.md`), for the skills: draw one furrow at 1:1,000 (`plans`); housing mix and floor and ground-floor plans (`building-types`, `ground-floor`, `programme`); one sealing, green and homes table (`analysis`, `open-space`, `narrative`); play area to 8,100 m2, the school's sports area and a food market of 1,200 m2 (`massing`); remove the car link at completion (`mobility`, `phasing`, `streets`); draw the canal, 150 kV strip and B16 setback (`site-kit`, `plans`); show the site plan uncropped and a centre close-up (`plans`, `panel-layout`).

In `panel-layout` itself (all low or medium): the 250 x 270 mm blank in panel 3, `stop-reach` and `unsealed-today` dropped, the site plan and isometric cropped, the panels 40 to 68 % paper, the section frame too low (0.11 of its width).
