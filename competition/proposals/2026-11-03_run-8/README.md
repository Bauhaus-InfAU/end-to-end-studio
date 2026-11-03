# run-8: "The Kept Field"

New run, 2026-11-03, 18:05 to 18:49, skills at commit `7e7cccf`. Verdict of the studio's own jury: no award, eliminated in round 2. The idea holds, but the 34 ha city edge fits only 2,177 of the 2,800 to 3,400 homes, and the mobility point is not drawn.

## Skills

Time is the helper's own run time. Cost is from `cost.csv`.

| Skill | Status | Time | Cost |
| --- | --- | --- | --- |
| pdf-to-md | not run: the brief's Markdown was already there | | |
| site-kit | not run: `site.geojson` was already there | | |
| brief-reader | copied: key matched `made-from.txt` | | |
| climate | first run copied (key matched); second run done | 0:47 | $0.10 |
| analysis | not written yet (counted as done) | | |
| narrative | done, two runs | 3:56 + 3:27 | $1.99 |
| programme | done | 0:26 | $0.13 |
| structure-plan | done | 15:23 | $3.50 |
| drawing-graphics | done | 0:21 | $0.10 |
| concept-diagrams | done | 1:02 | $0.21 |
| isometric | done, two runs | 0:26 + 0:21 | $0.18 |
| site-section | done, two runs | 0:29 + 0:58 | $0.27 |
| massing | done | 7:37 | $1.77 |
| streets | done | 0:51 | $0.10 |
| mobility | done | 0:52 | $0.21 |
| open-space | done | 1:02 | $0.25 |
| perspective | done | 2:49 | $0.12 |
| plans | done | 0:31 | $0.11 |
| panel-layout | done | 1:55 | $0.34 |
| jury | done | 5:48 | $1.41 |
| phasing | not written yet | | |
| figure-ground | not written yet (`plans` draws the figure-ground) | | |
| building-types | not written yet | | |
| lead | | | $2.35 |
| **Total** | | | **$13.13** |

No skill failed. Five helpers were refused saving their files (`structure-plan`, `narrative` second run, `jury` summary and report) or did not save them (`concept-diagrams`); the lead saved each from the helper's reply, word for word. No skill reported seeing material from the closed competition.

## Outdated by later results (not rerun)

- `concept-diagrams` ran before `structure-plan`, so its city edge and phases are drawn by eye, not from the real figure. The narrative's second run and the jury both point this out.
- `massing` found that the programme doesn't fit (2,177 homes; school sports ground and most of the pool missing) and asks `structure-plan` for about 3 ha more housing land. The structure plan was not rerun.
- `open-space` counted its rain and play needs for 5,000 residents; the massing holds 3,887.
- `perspective`'s renders changed the geometry (view 2's building moved and shrank), so both views are illustrations, not the design.
- Public green appears as 10.1 ha (structure-plan, narrative, panels), 11.4 ha (massing) and 51.9 ha (open-space, counting the private field). The panels use 10.1 ha.

## Summaries

### climate

Made (redrawn only, no recalculation, 1:15,000, redrawn in the entry's drawing standard, drawing-graphics/style.json): fresh-air corridor traced from the brief's Fig. 20 (p. 31), sun, shadows, wind, road noise (day and night), heat, rules map, `climate.json`, `climate.md` and `climate_sheet`.
Key number: 16 % of the site is at 65 dB(A) or more by day (no homes; 11.9 % at the low traffic end, 17.6 % in the noise grid at the high end) and another 61 % at 55 to 65 (homes only behind a shielding edge); the cold-air corridor along Pilsen-Allee takes 4 % (3.5 to 5 %).
Least sure: noise, as the brief (p. 24) gives only 10,000 to 20,000 vehicles, so speeds (70, 100 km/h) are ASSUMED, the railway is left out (no train data), DIN 18005 limits are German defaults and the method is German too; the climate map has no legend and sits on the streets to about 70 m.

### narrative

"The Kept Field: build on a third, keep the field whole": the finished design gathers Regensburg Nord inside a 34 ha city edge and keeps 54.2 ha as one farmed field. The jury text is `narrative/text.md`, answering the brief's eight points (p. 34) with sources in footnotes, and the 768-sign communication text is `narrative/communication.md` (p. 12). `narrative.md` is unchanged.
Most important number: the 34.0 ha city edge (30 % of the 112.8 ha site; `structure-plan/city-edge.geojson`) holds only 2,177 homes against the brief's 2,800 to 3,400 (`massing/stats.json`; p. 30, p. 33), with 1,097 in phase 1 against at least 1,100 and 3,887 residents in all (`massing/phases.csv`).
Least sure, and the gaps from the framework: the full programme does not fit. The edge is four parts, not one line, and the densified Haslbach works (105,000 mÂ² of commerce) lie outside it. The rail stop is at the figure's southern tip (9 % of the housing within 800 m, `mobility/stats.json`). The school sports ground and most of the pool are missing, and the noise behind the open rows is not checked. The housing mix, construction methods, interim uses and pioneer projects are not designed. The concept diagrams show the planned edge, not the one that was built. No `analysis/` folder existed.


### programme

Tabled homes and residents, commerce, social and sport (daycares, school, pool), green and play, each with its brief page; household mix left open as the brief gives no shares.
Total homes: 2,800 (5,000 residents) up to 3,400 (6,100 residents), at least 1,100 in phase 1.
Uncertainty: the brief gives housing only as ground area (250,000 m2) and the 36,500 m2 social total is not defined as floor or plot area.


### structure-plan

The figure: the new city is one 34 ha figure west of the railway, on both sides of Chamer Strasse, running from the Wutzlhofen stop (the main centre, with the mobility point, the bus station and the market) to the 150 kV line. It has three local centres (school, Chamer crossing, Nordbad), puts crafts on the loud land at the transformer and the Pilsenallee junction, and densifies the existing Haslbach estate. The other 54 ha stay one field: east of the railway, along the B16 and under the power line. The field crosses the railway along the 150 kV line. Files: `structure-plan.geojson`, `city-edge.geojson`, `check-plan.png`. The four routes in the study site carry `perimeter: study site`, so the panels can draw them in red (p. 34).
Proximity: 90 % of the new and changed neighbourhood area is within a 300 m walk of a centre or public green, measured along the existing streets and paths plus the plan's routes (55 % within 150 m; 75 % within 150 m in a straight line, which is not walking access; `post-checks.txt`, `checks.txt`). Public green is 10.1 ha against the 6 to 7.3 ha the brief asks for (p. 30). Phase 1 has 33 % of the new land and about 1,400 to 1,700 homes if they are spread evenly (the brief asks for at least 1,100, p. 33).
Hypothesis that matters most: 2,800 to 3,400 homes fit on 15.1 ha of housing land. That is 185 to 225 homes per ha, a floor-area ratio of about 2 at up to 6 storeys under 21 m, with homes only behind closed edges on the 55 to 65 dB(A) land. `massing` settles it; about 4 ha left under the narrative's 38 ha cap is an unplaced reserve. Missing inputs: there is no `analysis/` folder. The canal, the 150 kV line, the stop, the underpasses, the basin, the solar park, the biotopes and the compensation areas are not in the site kit; they were traced from the brief's Figs. 26-27 to within about 20-40 m. Railway noise is not assessed. `site.geojson` gives 112.8 ha against the brief's 107 ha.


### drawing-graphics

The look is a white-paper, grey-context standard where one warm terracotta city figure sits in a large muted-green kept field.
Accent #c8442b marks the new city inside the drawn edge (plots, buildings, streets, squares, the edge line at 0.5 mm); the kept field is green, the site plan carries the most weight.
Unsure: no reference images existed, so the look is the base plus the narrative only; the green and the accent may need a tweak once references are added.


### concept-diagrams

1. Five separate pictograms on one plan base (site outline and railway, scale bar shown, about 1:15,000 on the sheet): 01_field-today, 02_programme-spread, 03_one-edge, 04_field-crosses-rail, 05_phases. All are plans. They must still read at one panel column: the single red mass against the empty field, and the arrow crossing the railway.
2. Five pictograms, with `00_sheet`, `spec.json`, and an SVG and PNG each, in `C:/Work/GitHub/end-to-end-studio/competition/proposals/2026-11-03_run-8/concept-diagrams/`.
3. Conceptual, not data: the city edge polygon along the railway, the 24 scattered plot squares, the field arrow's position, and the three phase pieces. The brief and narrative give no geometry for any of them, because `structure-plan` has left no GeoJSON yet. Only the site outline and railway are data. Not measured: the edge is not checked to be 38 ha, and the phase split is my own assumption (phase 1 west of the railway, as the narrative says). Unsure: frame 4's edge is drawn thin in ink, so the field crossing may read weakly. Redraw the frames from the real edge once `structure-plan` writes it. The phases frame has no resident or field-area numbers; `programme` and `structure-plan` must supply them.


### isometric

- The design, isometric at 1:3000, seen from the north-west, 423 × 297 mm in print.
- 134 new buildings; 294 existing buildings, 3 of them at default heights from the site data.
- Unsure: streets from streets/streets.geojson; colours from the drawing standard; PNG from headless Chrome or Edge.


### site-section

Drew the design section Aâ€“Aâ€² (1643 m, looking north, 1 m DGM1 terrain) at 1:3000 (573 x 135 mm) and a 218â€“418 m excerpt at 1:1000 (225 x 90 mm) as site-section_design_1-3000 and site-section_design_excerpt_1-1000 (SVG and PNG), with the existing-site section redrawn on the same line (site-section_1-3000, site-section_excerpt_1-1000), plus profile.csv, cut.json, assumptions.md; I gave my own --line (12.11164,49.05757 to 12.14808,49.04517) because the automatic line reused from the first run cut 0 new buildings (4 behind), while this one cuts 12 new and shows 18 behind; roofs: 3 cut from the 3D model (0 pitched), 2 behind (2 pitched), 0 flat without model, new buildings flat at massing height.
Ground runs 338.3â€“399.0 m a.s.l.: it falls up to 47.3 m and rises up to 60.7 m along the cut (about 61 m between low and high point).
Unsure: tree heights are assumed (forest/wood 16 m, park 10 m, scrub 4 m); the line crosses only the west part of the new fabric and none of the far north-east blocks; the excerpt shows one existing block and the western new blocks, no street trees; the full-cut sheet is wide and low, so panel-layout must crop or scale it, and the "Site boundary" label at left touches the B 16 label.


### massing

Placed 134 new buildings on the structure plan's eight new and changed neighbourhoods (29.6 ha): rows of 4 to 6 storeys running with the cold air at 188 deg on the four housing neighbourhoods, a closed courtyard edge with two 10-storey landmarks at the Wutzlhofen stop, crafts halls on the three works, a 4-storey school, the Nordbad hall and a food market, with 1,392 street trees, a 30 m square per centre and greened 10 m secondary streets; files `massing.geojson`, `areas.csv`, `phases.csv`, `stats.json`, `assumptions.md`, the check plan `massing.svg/.png` at 1:3,000 with storeys, and `massing_3d.svg/.png`.
Gross floor area 445,600 m2 (floor area ratio 0.40 on the 112.8 ha site, 1.51 on the new land): homes 206,900 m2 = 2,177 homes against the brief's 2,800 to 3,400 (p. 33), with 89 of 91 home buildings at the 6-storey cap, so the programme does not fit at 95 m2 per home under 21 m (phase 1 holds 1,097 homes against at least 1,100, phase 2 1,080; residents per phase in `phases.csv`); commerce 229,200 of 230,000 m2 (p. 30); daycares 3,537 of 3,000 m2; school 3,200 of 3,000 m2 with its 2,000 m2 yard; public green 11.4 ha against 6 ha.
Unsure: the structure plan needs about 3 ha more housing land (its 4 ha reserve under the 38 ha edge) or a seventh storey to reach 2,800 homes; there is no room for the school's 3,000 m2 sports ground on School green or for more than 1,200 of the pool's 3,000 m2 on Nordbad yard, so `structure-plan` must enlarge both centres; the 95 m2 per home and the 10-storey landmarks are my own assumptions; the rows are not the closed noise edges the structure plan asked for; 16 secondary dead ends remain, 12 of them between the kept yards of Haslbach works; my script copies (`massing/scripts/`) add mixed ground floors only along main routes, count only public greens, and take the look from `drawing-graphics/style.json`; no `analysis/`.


### streets

Existing streets came from the site folder's street-land.geojson (cadastre street, square and path areas), used as they are; the new streets from massing/massing.geojson were added at 1:3,000 (streets_1-3000.svg/.png).
Streets cover 19.6% of the site (existing 58.17 ha, new 8.22 ha, 1.21 ha of existing street land given way under new buildings); 0 kept buildings under new streets, 0 main routes ending nowhere.
Unsure: 219 widths came from defaults (no brief widths in config.json); 6 street ends are left as future links, 6 got turning heads, 23 end square at the site edge.


### mobility

Mobility plan at 1:3,000 (`mobility_1-3000.png/.svg`) with `mobility.geojson`, `walk.json`, `stats.json`, `mobility.md`: rail stop and bus station as the hub, cars only at the brief's gateways, no car link Chamer Strasse to Sandgasse (0 violations), 4 main bike routes to named places.
Share of new housing within walking distance of the main stop: 0 % within 400 m, 9 % within 800 m (by street network); the stop sits at the southern tip, far from most homes.
Assumptions: walk limits, bike destinations and the bus-only south stop street are assumed; no 1:1,000 detail plan of detail area 1 was made (the skill draws only 1:3,000); the crop to the new buildings omits the site's far edges.


### open-space

Laid out the blue-green network on the massing at 1:3,000 (`open-space_1-3000.svg/.png`, with `open-space.geojson`, `areas.csv`, `sealing.csv`, `assumptions.md`, `config.json`, `keep-free.geojson`): 10 corridor parks and 10 other parks, 14 rain pools (shallow edge 0.25 m, deep core 0.8 m, placed on the terrain's low ground, rain drains downhill), ground cover, 3 playgrounds (8,111 m2 against 7,500 m2, every home within 300 m), 4.3 km of loop paths, 26 green links (no park unlinked); canal (10 m each side), 150 kV line (20 m) and solar park kept free; sealing 28.9 % fully, 2.4 % partly, 68.7 % unsealed (brief p. 34).
Public green: the script counts 51.9 ha of parks against the brief's 6 ha minimum (12 m2 x 5,000 residents, p. 30); this is inflated because it counts the open land east of the railway (the B16 field and East field, which structure-plan marks as not public), so the honest figure is the structure plan's 10.1 ha of new public green, still above 6 ha (7.3 ha at 6,100 residents); retention 4,322 m3 against 4,394 m3 needed (-72 m3).
Unsure: the canal and 150 kV lines are traced from the brief's Fig. 26 (20-40 m off) and I took 5,000 residents although the massing holds only 2,177 homes, so the real need is lower; one park cannot hold its rain (areas.csv), and the pools in the big eastern field serve little, so the massing or structure plan should give the west parks more room; there is no `analysis/`, so kept biotopes and trees come only from the site layers and structure plan.


### perspective

Eye-level base views, no scale, at 1.65 m: view-1 (edge), view-2 (square).
2 views from 1396 scored candidates; 6 warnings.
Unsure: Land uses the skill has no rule for, drawn as bare ground: leisure:nature_reserve (2), leisure:swimming_pool (8), leisure:track (1), natural:bare_rock (1), natural:sand (1) All assumed numbers are in assumptions.md.


### plans

site-plan_1-3000.svg/.png at 1:3,000 (564 x 588 mm, storeys shown); detail-area-1_1-1000.svg/.png at 1:1,000 (Wutzlhofen stop square, mobility hub; 316 x 348 mm); detail-area-2_1-1000.svg/.png at 1:1,000 (Chamer crossing; 467 x 504 mm); figure-ground_1-15000.svg/.png at 1:15,000 (198 x 219 mm); drawings.json.
All 4 of the brief's plans (figure-ground, site plan, detail areas 1 and 2) are drawn and fit an A1 portrait panel (594 x 841 mm); the site plan was cropped to the panel's width, so the south-west edge of the surrounding city is cut.
Unsure: detail area 2 is Chamer crossing, chosen by me as the second centre (the brief allows another area); no layer was missing; on the site plan the "Detail area 2" label overlaps a text of the other window.


### panel-layout

3 A1 portrait panels (PDF and PNG in panel-layout/): 1 the idea (text, figure-ground 1:15,000, five concept pictograms, phases and residents); 2 site plan 1:3,000 with storeys and two perspectives; 3 detail areas 1 and 2 at 1:1,000 (area 2 cropped), isometric 1:3,000 and soil sealing; code box left blank, number top right, title and site on every panel.
12 of the brief's 15 required items are on the panels; missing with no input: housing mix, study-site measures in red, implementation method (pioneer projects, interim uses); the site sections are drawn but left off for room.
Unsure: homes (2,177 vs 2,800 to 3,400), residents (3,887 vs 5,000 to 6,100) and phase 1 (1,097 vs 1,100) fall short of the brief and are shown as they are; the three public-green figures disagree (10.1, 11.4, 51.9 ha), only 10.1 ha used; panels 1 and 3 have empty space at the foot.


### jury

Verdict: no award (no prize, no special mention); shortlisted in round 1, eliminated in round 2 (national jury) at the programme hurdle, not brought back in the control round (`jury/report.md`).
Number that weighed most: 2,177 homes against the brief's minimum of 2,800 (âˆ’623, 78 %; p. 33), from 15.1 ha of housing land against the framework's 25 ha (p. 30). The jury's recompute: about 19.4 ha (an edge of about 38 ha, still a third of the site) would fit 2,800 at six storeys. Also weighing: the mobility point (bus station, Kiss+Ride, Park+Ride) is not drawn in detail area 1, and no plan shows uses or interiors.
Unsure: whether a jury would value the strategic idea enough for a special mention; the B16 distance is measured from the road centreline (17.4 m, one Haslbach hall); the site counts as 112.8 ha against the brief's 107 ha; the text PDF and the communication JPGs do not exist. No closed-competition material was seen.

