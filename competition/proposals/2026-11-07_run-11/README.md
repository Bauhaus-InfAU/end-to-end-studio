# run-11: Two Banks

A new version on the Regensburg brief, 2026-11-07, 21:51 to 23:16, skills at commit cf97c2e, the first run with the three winners of this site as references. The idea: the railway and Pilsen-Allee, at the bottom of the valley, are treated as the district's river; work faces the line from both banks, homes sit on the slopes between seven green tributaries, and the centre is the Station Bridge over the stop. The jury gives a **Special Mention**: shortlisted in round 1, eliminated in round 2 at hurdle 3 (how blocks, homes and uses are organised), brought back in the control round for the idea.

Panels: `panel-layout/panel-1.png`, `panel-2.png`, `panel-3.png` (and PDFs). Text: `narrative/text.md`. Jury: `jury/report.md`. Our drawings beside the winners': `.compare/`. Map of every run: `../preview/index.html`.

## Skills

| Skill | State | Time | Cost |
| --- | --- | --- | --- |
| pdf-to-md | done earlier (brief's Markdown already there) | – | – |
| brief-reader | copied (key matched) | – | – |
| site-kit | done earlier (site.geojson already there) | – | – |
| climate | remade at project level (skill changed), second run, redraw | 3 + 1 + 5 min | $0.75 |
| programme | done | 1 min | $0.14 |
| analysis | done, 2 runs, redraw | 1 + 6 + 3 min | $0.61 |
| narrative | done, 2 runs | 9 + 6 min | $3.09 |
| drawing-graphics | done | 1 min | $0.30 |
| structure-plan | done, redraw | 20 + 7 min | $6.23 |
| panel-layout | done, 2 runs | 9 + 8 min | $4.23 |
| massing | done | 11 min | $2.37 |
| site-section | done, 2 runs, redraw | 1 + 2 + 5 min | $0.79 |
| isometric | done, 2 runs, redraw | 1 + 3 + 6 min | $0.79 |
| streets | done | 2 min | $0.09 |
| phasing | done, 2 runs, redraw | 1 + 4 + 4 min | $0.89 |
| concept-diagrams | done, redraw | 2 + 3 min | $0.56 |
| mobility | done, redraw | 2 + 10 min | $1.11 |
| open-space | done, redraw | 2 + 5 min | $0.55 |
| ground-floor | done | 1 min | $0.11 |
| building-types | done in part (1 of 13 types), redraw (6 of 13) | 1 + 5 min | $0.62 |
| perspective | done, redraw | 4 + 9 min | $0.79 |
| plans | done, redraw | 2 + 4 min | $0.46 |
| art-direction | done | 4 min | $1.06 |
| jury | done | 9 min | $2.11 |
| figure-ground | not written yet (open in STUDIO.md; plans drew the figure-ground) | – | – |
| lead | | 85 min | $5.92 |

**Total: $33.56** (40 helper runs and the lead; `cost.csv`). The run stood at $20.05 when the redraw round started, under the $30 ceiling, so the round ran; the round and the last three runs took it past.

## What each skill found

Each skill's `summary.md` as it stands at the end, word for word; for a skill that ran more than once, its last run.

**climate** (second run, redraw)

Made (1:15,000, in the entry's drawing standard): cold-air corridor traced from the brief's Fig. 20 (p. 31), sun, shadows, radiation, wind, road noise (day and night), heat, rules map, `climate.json`, `climate.md` and `climate_sheet`.
Key number: 16 % of the site is at 65 dB(A) or more by day (no homes; 11.9 % at the low traffic end, 17.6 % at the high end) and another 61 % at 55 to 65 (homes only behind a shielding edge); the cold-air corridor along Pilsen-Allee takes 4 % (3.5 to 5 %).
Least sure: noise, as the brief (p. 24) gives only 10,000 to 20,000 vehicles, so speeds (70, 100 km/h) are ASSUMED, the railway is left out (no train data), DIN 18005 limits and RLS-90 are German defaults; the climate map has no legend and fits the streets to about 70 m.
Redrawn only (no recalculation; copy of draw.py in climate/scripts/draw.py): rules.svg now shows the design (new buildings from massing, open space and corridors from open-space) over the rules, so the air corridor reads between the buildings; fresh-air.svg shows one broad soft band along the cold-air corridor with four arrows instead of 129 thin ones; all maps keep the 136.5 x 125 mm frame at 1:15,000 and the legend box now picks its width and corner to hide least of the site (still covers part of the west of the site on rules.svg, about a third of the map, because the site fills the frame).

**programme**

Tabled homes, residents, commerce, daycares, school, pool, green and play areas, each with brief page; the household mix is open.
Key number: 2,800 homes (up to 3,400) for 5,000 residents (up to 6,100); at least 1,100 in phase 1.
Uncertainty: the brief gives no household mix and no housing floor area; 36,500 m2 social total is not broken down.

**analysis** (second run, redraw)

1. Measured today and with the design: uses, edges with crossings (34 to 43), green, walking reach to green, shops and schools (400/800 m), sealed share and `keep.geojson`, each with a map at 1:3,000. `edges_today` is redrawn at 1:15,000 for its frame. Reach to stations and bus stops is not measured because the data has none. 12 measures are better, 8 worse.
2. Sealed share with the design: fully sealed 38.1 ha (33.8 %, today 14.2 %), partly sealed 17.2 ha (15.3 %, today 8.3 %), unsealed 57.4 ha (50.9 %, today 77.5 %).
3. Unsure:
   - The farmland and woods drops are a classing effect, not proof that the woods are felled.
   - "Design: plot" counts as partly sealed from an assumed buffer.
   - Sealing classes and walking radii are assumptions.
   - The maps use the default look and the winners' analysis drawings were not compared.
   - Fixes 1 and 3 are not done. The other maps still cannot go into a 136.5 x 125 mm frame at 1:15,000 until they are redrawn the same way.

**narrative** (second run)

Two Banks, *A district that faces its loudest line*: the railway and Pilsen-Allee are treated as the river of Regensburg North, with work facing the line from both banks, homes on the slopes between seven tributaries and the centre on the Station Bridge. Second run written: `text.md` (the brief's eight points, 3 to 4 sentences each, then how it was approached, where it moved from the idea, the sealing statement and homes and residents per phase; about 1,770 words for the 3 to 4 A4 pages, pp. 12, 34), `communication.md` (785 of 800 signs, p. 12), and `measure_design.py`/`.json`, which check the finished massing against the principles.
Key number: 6 crossings of the line, the longest gap 389 m against 724 m today (`narrative/measure_design.json`; the structure plan gives 395 m). Also measured: 0 homes, schools or daycares on land at 65 dB(A) or more, and 0 m² of building on the 4.49 ha air corridor.
Least sure, and where the design moved from the framework: the bank row is closed along 47 % (west) and 38 % (east) of the line against the 70 % target; 430 homes sit above the work on the banks; the market hall stands beside the deck, not on it, and the deck is drawn 16 m plus a 4 m path, not 30 m; both landmarks are on the west head; sealing is 49.1 % by `analysis` and 42.1 % by `open-space/sealing.csv`, both over the 40 % target (the text uses analysis); only 55 % of the home footprint keeps to the air axis; walking reach to the stop is 52 % (structure plan) or 5 % (mobility), so it is left out of the text. Missing, and not invented: the housing mix (the brief gives no shares), construction methods, study-site measures drawn in red, and interim uses beyond "land stays farmed until its phase" (from the framework only). Daycare 2 has 470 m² of grounds against the 950 m² the brief requires, so the text does not claim the outdoor play areas are met.

**drawing-graphics**

Look: a pale green-grey plan language with white buildings, fine ink lines, dotted tree crowns and roman storey numbers, as in all three winners' site plans, with almost no text on the drawings.
Accent: muted rose-red #c24a4f with pale pink #f0c4c4, marking only the public ground of the line (the six crossings, the Station Bridge deck, the first row's fronts onto the line).
Unsure: the rose accent matches all three winners, so it may not set us apart; I read the nine boards and four single drawings, so the mobility, climate and open-space recipes are thin; the accent is close to the pale greens in value, so it needs the hatch.

**structure-plan** (redraw)

Two Banks as a figure: one town on both banks of the rail and Pilsen-Allee. Work rows stand along the line (West, North, East and South Bank, with the B16, Lobe and Haslbach edges and North Works on the other loud edges). Homes fill 10 neighbourhoods on the slopes behind, between 7 tributaries (7.42 ha, 32 m wide; 87 % of the homes' land within 150 m of one). The main centre is the Station Bridge: west head with the bus station, a 30 m deck with the market over the stop, east head with the pool. There are 8 local centres and 6 crossings of the line, the longest gap 395 m (724 m today). Nothing is built on the 4.49 ha cold-air corridor and no homes stand at 65 dB(A) or more. Phase 1 (between Chamer Strasse and the rail) holds 1,270 homes against at least 1,100 asked (p. 33) and 13,000 m2 of commerce, at 86 % of its possible floor area. Phase 2 (east bank) holds 1,160 against our 1,000 and 48,000 m2, at 83 %. Phase 3 (west of Chamer Strasse, the lobe, the north) holds 810 against our 700 and 170,000 m2, at 79 %. In all: 3,240 homes against 2,800 asked (3,400 at most) and 231,000 of 230,000 m2 of commerce. Phase 1's slopes hold only 840 homes at 6 floors, so 430 homes sit on the upper floors of the quiet side of the West and North Bank, above the work; this departs from the narrative's "work along the line, homes behind". Redrawn for the panel (draw_plan.py, same geojson and numbers): zones by use (housing, homes above work, work and commerce, existing kept), 8 broad green arrows (7 tributaries across the line, the cold-air corridor towards 188 degrees), main and local streets as one accent network, and only the 9 centres and 10 housing neighbourhoods labelled, at 9.3 to 9.9 pt printed, 0 overlaps, 0 dropped; it prints 131.3 x 131.2 mm in its 131.2 mm high frame. Against the reference structure plan (Nordstern), ours still draws zones, not blocks, and has no landmarks or active ground floors.
52 % of the homes (1,699 of 3,240) are within a 400 m walk of the stop (checks.txt), measured to the Station Bridge centre with both heads. Phases 2 and 3 were split by us, because the brief fixes only phase 1. The 95 m2 per home is an assumption, because the brief gives no housing floor area. site.geojson is 112.8 ha against the brief's 107 ha. The plan took 7 builds, three over the skill's four, to keep every neighbourhood under its storey cap.
Least sure: the positions of the compensation land, the biotope, the canal, the 150 kV line, the solar park and the stop. They are traced from the brief's plans (pp. 36-37; fit 2 to 24 m, reading about 30 to 50 m), and they set the edges of the West Bank, the East Bank and the East Terrace, and the bus road past the biotope's tip. Also unsure: the Station Bridge deck, whose 210 m east ramp does not fit in the 145 m between the road and the corridor, so it folds inside the east row or uses lifts. The city's survey of those lines and the rail company's word on the deck would settle both.

**panel-layout** (second run)

Laid out the 3 final A1 portrait panels (`panel-1..3.pdf`/`.png`, 12.0, 8.5 and 9.7 MB, each under the brief's 20 MB, p. 11) from `layout.json`, built by `work/build_final.py` on the plan in `layout-plan.json`. Panel 1, why: the idea text, the six concept pictograms, the district isometric 1:5,000 (frame 564 x 380 mm, 4 % hidden), the valley section today and design 1:3,000, figure-ground, climate rules and edges today at 1:15,000, with 724 m / 395 m / 4.49 ha. Panel 2, what: structure plan, mobility and open space at 1:15,000, sealing 39.6 % fully and 2.5 % partly (today 14.2 % and 8.3 %), the site plan 1:3,000, the programme figures, 3,237 homes, 44 % of new home floor area within an 800 m walk of the stop. Panel 3, how: two perspectives (216 x 150 mm, not 279, because they have no scale and keep their proportions) with the views map beside them, detail area 1 and 2 at 1:1,000, the centre isometric 1:2,000, phases 1:15,000, the homes and residents per phase table, the method text, and building types at 1:4,000 (set by `drawn_at`, since the file name still says 1-1000). Panel captions are dropped where the drawing carries its own title. The largest differences from the winners: our panel 1 hero is the isometric, not the site plan; our section sits on panel 1, where theirs runs along the foot of panels 2 and 3; and our concept row and thematic maps are smaller and denser than theirs.
12 of the brief's 12 required items are on the panels (26 of 26 with the storyline drawings), none hidden more than 25 %, no planned item dropped; the report shows 0 problems.
Unsure: some numbers that should agree don't. Sealing is shown from open-space (analysis gives 33.8 % and 15.3 %, and the text uses analysis). Homes are 3,237 from massing (phasing 3,236, structure plan 3,240). The longest gap is 395 m from the structure plan (narrative measures 389 m). The stop reach shown is mobility's 44 % in 800 m and 5 % in 400 m (the structure plan gives 52 % in 400 m). All are in `notes`, none corrected. The concept pictograms' labels print at about 6 pt, under 9 pt, because their SVGs are 137.6 mm wide in 89 mm frames. About 50 working files and 1:3,000 analysis maps stay off the panels, as no room is left. `issues.md` hands 3 medium issues to 3 skills: concept-diagrams (label size), plans (study-site measures in red not drawn) and programme (no housing mix; the brief gives no shares, p. 33).

**massing**

Placed 253 new buildings on the structure plan's 18 new neighbourhoods and kept the 209 existing ones. On the slopes the homes are L blocks, ensembles, rows and town houses at 3 to 6 floors, mixed in each neighbourhood (a reply to issue 6 of run-10), on the 8/188 deg cold-air axis, or along Chamer Strasse and the B16 west of it. The West and North Bank are perimeter, U and hub blocks with work below and homes above, and the work rows are halls with U and L yards. The two 9-floor landmarks are on the west bridge head. The school, its yard and sports ground are on Canal School, the pool on the east head, the bus station, market hall and a 9,600 m2 garage on the west head, the 3 daycares and 5 local garages on their centres. Also 163 streets (no dead ends), 1,946 street trees, 12 squares and 124 courtyard gardens. Files: massing.geojson, areas.csv, stats.json, assumptions.md, massing.svg/.png (check plan 1:3,000 in the entry's standard, roman storeys, text 3.2 mm) and massing_3d.svg/.png.
Gross floor area 564,515 m2: floor area ratio 0.50 on the 112.8 ha site and 1.31 on the 43.1 ha of new land. Homes: 3,237 against the structure plan's 3,240, inside the brief's 2,800 to 3,400 (p. 30), at an assumed 95 m2 per home. 23 floors came off so the homes stay under that figure, and 42 of 165 home buildings are at the 6-floor cap. Phase 1 has 1,222 homes against at least 1,100 (p. 33), phase 2 has 1,087 and phase 3 has 928. Commerce: 229,475 m2 against 230,000 m2 (p. 30). The school, yard, sports and pool meet p. 30, and so do the 3 daycares of 1,000 m2. Public green: 33.0 ha against 7.3 ha, counting only the greens open to the public.
Unsure: the market hall has only 1,620 of 1,800 m2 and stands on the west head beside the deck, not on it, because the deck is a street in this file. The five local garages get only 720 to 1,680 of 2,400 m2 on their small centres. Both landmarks are on the west head, against the narrative's one per head. Only 55 % of the home footprint lies on the cold-air axis (principle 2), and I did not measure the first row's 70 % closure (principle 1). Several things are my own assumptions, not the brief's: 95 m2 per home, 9-floor landmarks, 72 x 56 m blocks, the 20 m row gap, and the sizes of the bus station, market and garages. Against the winners' site plan, ours has smaller blocks broken into many pieces, no continuous street edges, and strips of empty land along the tributaries. Changes in my copies in massing/scripts/: phases come from the structure plan, only open greens count as public green, and the plan takes the standard's colours and 9 pt text. check.py is my own check.

**site-section** (second run, redraw)

Site section A-A' redrawn on a new line through the Station Bridge (1,646 m, looking north, 1,290 m of it inside the site), today (1:3000, excerpt 1:1000) and on the design (site-section_design_1-3000 in its 564 x 64 mm frame, excerpt 1:1000); fixes: the line now runs through the Station Bridge and both banks, so 11 new buildings are cut and 15 stand behind (was 8 and 8), the bands now cover the valley and every wide band is named below the ground line (South Slope, Canal School, Station Bridge, Basin Land and others), and 10 crowns were added every 20 m where the cut runs through green on top of 71 trees of open-space/ and massing/; cut roofs 6 from the 3D model (2 pitched), 1 flat without model; behind 21 from model (13 pitched), 2 flat; line chosen by pick_line.py, a copy of section.py is in this folder.
Ground falls 48.0 m and rises 56.7 m along the cut (336.1-392.8 m a.s.l.), no vertical exaggeration.
Unsure: principles 1 (East Bank) and 3 (Chamer Gate) are not on the line and stay illustrative with hollow dots; bands narrower than a name, mostly on the east slope, stay unnamed (at 1:3,000 about 10 of 38); the green-area crowns are assumed 10 m high, 6 m crown; the farmland of Basin Land got no added trees; the design excerpt (392-592 m) shows South Slope homes but I did not recheck the whole excerpt after the final run.

**isometric** (second run, redraw)

- The design, isometric seen from the south-east (a true isometric, the rail running across the frame): the district at 1:5000, 564 x 394 mm in print, filling its frame (was 362 x 284 mm, 46 %), with existing buildings as pale volumes with shaded walls and their heights; its centre Station Bridge close up at 1:2000, 279 x 175 mm, now with every open-space playground, path, green link, pool and ground cover and the public fill under the deck and both heads.
- 253 new buildings (14 flat, 18 gable at an assumed 30 deg pitch, 146 green, 75 pv roofs); 3105 existing buildings, 163 of them at default heights; 3062 trees; close up 20 use labels from the massing (4 ground floors marked * as illustrative) and 238 people, illustrative; the stock script was fixed in my copy isometric/scripts/isometric.py (new --frame option, view axis from the rail, open-space layers).
- Unsure: the site data ends about 2 km from the district, so the top-left and bottom-right corners of the district frame fade to blank paper; the rail runs north-south, so it cannot run exactly across the frame from the south, south-east is the nearest; labels on the close-up still overlap in places; winners' isometrics not compared.

**streets**

Existing streets come from the site folder's street-land.geojson (cadastre street areas), used as they are; the new ones from massing.geojson (2,140 m of new street run on existing ones and are dropped, 0.3 ha of existing street land gives way).
Streets cover 26.2% of the plan area (existing 59.08 ha, new 14.64 ha); kept_buildings_under_new_streets is 0. Files: streets.geojson, stats.json, assumptions.md, streets_1-3000.svg/.png.
Unsure: 2 main routes still end nowhere (massing should lead them on or link them); 223 widths are defaults, no brief widths in config; 34 square ends, 22 turning heads, 7 future links; in the preview new streets read nearly as pale as existing ones, so check the accent in the PNG.

**phasing** (second run, redraw)

3 phases: 1 = South Slope, Middle Slope, West Bank, North Bank with Station Bridge, Wutzlhofen stop, bus station, market hall, school, pool, daycare 1; 2 = the east side with daycare 2 and Glashuetten Gate stop; 3 = west, lobe, north with daycare 3. Plans: phasing/phasing_large.png (1:3,000) and phasing/phasing_small.svg/.png (1:15,000, 136.5 x 125 mm frame, each phase labelled with number, homes, residents and what comes first, streets cropped to the site plus 100 m), table phasing/phases_table.svg (136.5 x 58 mm, fits its 136.5 x 60 mm frame, text 3.5 mm). Redrawn with phasing/draw_run11.py (a copy of the skill's draw.py with these two changes; the skill is unchanged).
Homes and residents: phase 1 1,222 and 2,187 (brief at least 1,100, met); phase 2 1,087 and 1,945; phase 3 928 and 1,661; total 3,236 and 5,792 (brief 2,800 to 3,400 homes, met). stage-phases counts 5,793 residents at completion from rounding; homes match massing/areas.csv within 1 (3,236 vs 3,237).
Flags: homes are 48 and 73 under the structure plan in phases 1 and 2 and 118 over in 3, South Slope furthest (348 of 460); 0 buildings for review; 2 tiny new buildings fail a stage check for lack of street (b-ef47b7ec5e55d96e, phase 2, and b-9f92d16d012eec3b, phase 3, 36 m from any street, so massing or streets should add a link), 95 street pieces left to the last phase, 28 existing buildings not reached today, two unnamed playgrounds unphased (open-space gives them no id); least met: the 12 m2 open space per resident and emergency access are not measurable (existing residents and the rule are not stated); unsure of Glashuetten Gate's phase and of the phase 2/3 split, which the brief does not fix.; redraw: the phase labels of 1 and 3 touch where the phases meet, and the table's facilities column shows what works at the stage (phases 2 and 3 read 'daycare 1'), not what each phase adds; numbers unchanged.

**concept-diagrams** (redraw)

1. Six pictograms in one sequence (earlier moves in ink, the new one in red), all axonometric at no scale, one per frame of the panel-1 row (89 x 66 mm): valley, two-halves, wall, wall-turned, six-crossings, tributaries; each must read at 89 mm wide, with labels at most "line", "cold air", "Station Bridge" and the two half sizes.
2. Six pictograms (SVG and PNG each, plus 00_sheet and spec.json); file names follow panel-layout/layout.json.
3. Conceptual, not data: arrow positions, the wall's rows (30-110 m band, 14 m high, drawn as 28 m deep blocks), the strips' lengths and widths (bridges drawn 28 m wide, 440 m long), the tributary and home positions, all illustrative; only the site, rail, Pilsen-Allee, the 57.5/43.7 ha split and the six crossing northings (narrative table) are data. Unsure: sequence mode keeps the wall of frame 3 as ghosts in frames 5 and 6, which crowds them, and the narrow site gives small figures at panel size; I looked at the sheet once and did not revise. The four-tributary count is my assumption (the narrative asks for at least four). No reference differences checked beyond one winners' concept board (lighter, simpler isometric blocks with pink site tint, which ours lacks).

**mobility** (redraw)

5 % of the new housing floor area lies within 400 m and 44 % within 800 m of the Wutzlhofen stop (walk network, stats.json); car-link check 0 violations; 5 of 10 main bike routes lead to named places.
Files in mobility/: config.json, mobility.geojson (unchanged), mobility_1-15000.svg/png (redrawn), walk.json, stats.json, mobility.md, scripts/mobility.py (copy, redraw changes marked 'run-11 fixes'). Art-direction fixes done: arrows on from the main bus, bike and car routes past the site edge, labelled with their named place or street (bike destinations from config.json); car access arrows from each gateway to the nearest district garage; bus stops snapped onto the bus line; legend cut to the 15 items drawn (50 mm wide, was 20 entries, longer than the map) and the distance circles dropped (the 5 % / 44 % numbers stay in the caption, panel-layout's job).
Plan now 136.5 x 125 mm at 1:15,000 in the frame of layout-plan.json (centre kept); the legend box (50 x about 95 mm, top-right) still covers about 20 % of the site's east edge and two labels (North Head, Pilsen-Allee), as the site is 108 mm wide in a 136 mm frame, so the frame should be 20 mm wider or the legend go beside the drawing; the car arrows are straight lines gateway to garage, not street-following; not checked against the winners' mobility drawings.

**open-space** (redraw)

Laid out the blue-green network on run-11's massing: 21 corridor parks (the structure plan's 7 tributaries and the cold-air corridor, with pools), 26 retention basins holding 7,574 m3 against 7,500 m3 needed (30 mm, the skill's default, not from the brief), 6 playgrounds, 31 green links, 1,621 m of paths and 170 m of boardwalk; 427 planted trees and 689 drawn over the kept woods; the 10 m canal strip (brief p. 30) is kept free; sealing is 39.6 % fully and 2.5 % partly sealed, 58.0 % unsealed. The plan (`open-space_1-15000.svg` and `.png`, 136.5 x 125 mm) is redrawn after the art-direction fixes. The frame is centred on the site with 100 m around it, flush right, and the legend sits in the empty west corner outside the site. Buildings are pale fills with no outlines, so the green network is the figure. Each playground has a round red symbol. Broad soft green arrows at the site edge show the 7 links running out to the landscape.
Public green is 26.3 ha of new parks against 7.3 ha at the maximum of 6,100 residents (12 m² per resident, brief p. 30 and p. 34), and a further 7.6 ha of kept green and water is counted apart. Play area is 9,266 m² against 9,150 m² (1.5 m² per resident, brief p. 28), and every home building is within 300 m of a playground.
Unsure of three things. (1) One park is still unlinked, which the massing could join to the network. (2) The canal's position is traced from the brief's plans (fit 2 to 24 m), and the 150 kV strip has no line of its own, so it is not in `keep-free.geojson`. The plan is at 1:15,000 for the panel, not the brief's 1:3,000. There are no sports fields in the data, so only playgrounds have the round symbol. The arrows mark where each landscape link leaves the site edge, not where it reaches the woods or fields. I did not compare the plan with the winners' open-space drawings in this redraw; the fixes come from art-direction. Pools sit on low ground because terrain was used.

**ground-floor**

Placed 281 doors on 253 buildings (all on a street facade), 1,088 bike stands, 79 play areas (7,174 m2; 45 of 124 courtyards under 600 m2 got none, none had a playground), 29 labelled centre uses (the 1,200 m2 food market put into building 172 at Station Bridge), 6 bus bays and 300 bike spaces at Station Bridge.
Ground-floor area of the non-housing uses at the centres: 66,984 m2.
Flags: none (every use and surface found room); stands (4 per door), play areas (100 m2) and the 300 bike spaces are illustrative proposals, not the brief's numbers (the brief gives only the 6 platforms, p. 27); massing change needed: none.

**building-types** (redraw)

Redrew 6 of 13 building types as isometric ensembles (market hall, town houses, courtyard ensemble, L blocks, rows, perimeter block), two rows of three, one block each with yard, street and trees, a two-line caption under each (name, what it offers) and two notes with leader lines; programme and sources moved to types.csv. The sheet is 258 x 140 mm, within the 279 x 140 mm frame, in building-types_1-1000.svg (the file name the layout plan uses).
The scale is 1:4,000, not the plan's 1:1,000 or the fix's about 1:2,500: at 1:2,500 only two types fit the frame (at 1:3,000 five, at 1:3,500 six but with the mobility hub, not the perimeter block); the layout plan still says 1:1,000 and the file name keeps 1-1000, so the lead should set its scale to 1:4,000 (title and scale bar on the drawing say 1:4,000). Left out, all in types.csv: mobility hub, hall, U block, garage, daycare, bus station, school.
Unsure: at 1:4,000 the facade windows (3 m bays) and the light PV grid are too small to read (PV roofs are in the code and lightened, but no PV roof shows in these blocks); notes come from the new notes.json (narrative principles and the massing, two per type, wording shortened by me); no config.json scale from the brief. Script copy: building-types/bt.py (scale set inside it). Look: drawing-graphics/style.json.

**perspective** (redraw)

Two eye-level views at 1.65 m, no scale, redrawn with art-direction's three fixes and rendered with Gemini (gemini-3.1-flash-image-preview): view-1 (paved square with lawn, trees and a block behind) and view-2 (lawn, tree row, water edge and bank row behind), in the layout's two frames as perspective-1 and perspective-2. Fixes: (1) the ground now comes from the layers, with sand paving and joints, lawn tone with mowing lines, beds, pools and paths from open-space and streets, instead of one pink plane; (2) every wall facing the camera has a window rhythm per floor, and shop fronts with the use written on the sign where the ground floor is commerce/market, but no shop front is in frame in either view, so none shows; (3) cameras moved along their axis (view-1 by 10 m, view-2 by 20 m, heading turned 8 degrees at most) so trees frame the edge; no wall takes over a quarter of the frame in view-1 (about 25 percent on the left, 14 percent right) and under 5 percent in view-2.
2 views from 1375 scored candidates, then 15 camera shifts each tried; 6 warnings, mostly land uses with no rule (nature_reserve, swimming_pool, track, bare_rock, sand) drawn as bare ground; redraw code is in perspective/scripts/ (copy of the skill's scripts, changed), shift.json holds the camera search.
Unsure: (1) the render changed things: view-1 recoloured part of the paving and a lawn patch to a bright pink-red and yellow-green, and added people; view-2 turned a ground strip pink and added people and a yellow wash on the lawn; both skies became grey-green and trees watercolour, geometry and windows kept, shop-front lettering is not in frame. (2) View-2's foreground is still a large plain lawn and its hedge-like green blocks in the middle are the open-space ground cover drawn as solid volumes, not a design choice; the winners' pictures show more people and planting near the camera. (3) Several near trees under 3 m are left out; terrain and assumptions are in assumptions.md.

**plans** (redraw)

- `plans/site-plan_1-3000.svg` and `.png` at 1:3,000 (564 x 540 mm), `detail-area-1_1-1000.svg` and `.png` at 1:1,000 (564 x 270 mm), `detail-area-2_1-1000.svg` and `.png` at 1:1,000 (279 x 175 mm), `figure-ground_1-15000.svg` and `.png` at 1:15,000 (136.5 x 125 mm, was 198 x 219 mm), plus `drawings.json`. The changed script is `plans/scripts/plans.py`. It is a copy; the skill's own files are untouched.
- 4 of the brief's 4 plans are drawn, and all four fit their panel frames. Fixes done:
  - Detail areas: the red rectangles are gone. The accent stays only as the pale public fill. Every new building now carries its use under its storeys. The ground-floor labels stay.
  - Detail areas: street trees every 11 m on both sides of every street centreline, added to the open-space and massing trees. Paths, pools and playgrounds were already drawn from open-space. I looked at detail-area-1 only; detail-area-2 I did not open.
  - Site plan: crowns on the existing woods (dense), scrub (medium) and gardens, parks and fields (sparse) outside the site boundary, out to the frame's edge.
  - Figure-ground: the script now takes the window from the layout frame and centres it on the site. It had ignored the frame.
- Unsure: the figure-ground is cropped. The site is taller than 125 mm at 1:15,000, so the north tip is cut and the frame shows about 95 mm of map. Both detail areas and the site plan are also flagged cropped in `drawings.json`; the overlaps check found no overlap. Site-plan crowns are generated at random points inside the context plots, not surveyed trees. The site plan still outlines the "Two Banks" idea in the accent, and still has a short stray accent line near North Head and near South Head. These come from idea features that are lines. If the skill's own script should carry these fixes, they still need porting.

**art-direction**

35 fixes for 12 skills (plans, isometric, building-types, concept-diagrams, site-section, perspective, structure-plan, open-space, mobility, climate, analysis, phasing); panel-layout gets none, since its panels are still grey frames waiting for the drawings, and figure-ground is already close to its references.
Largest gap: our drawings are emptier than the winners'. The perspectives are a blank wall on a flat red ground, the 1:1,000 detail areas are a few blocks in pale ground with trees only at the edges, the district isometric fills only a thin strip of its frame, and building types shows one type where the references show four to eight.
Unsure: the perspectives were rendered but still look like their base views, so the render step rather than the base may need the fix; phasing had no compare sheet, so I set it beside the one reference phase plan on the concept-diagrams sheet; the colour gaps (brown phasing and climate ramps, saturated red perspective ground, no colours per transport mode) are left to the standard in notes.md.

**jury**

Verdict: Special Mention. "Two Banks" is admitted and shortlisted in round 1. In round 2 it passes concept-and-site and the programme numbers, then is eliminated at hurdle 3 (how blocks, homes and uses are organised). The control round brings it back as a Special Mention for turning the noise wall into a working bank across a line that can be crossed (brief p. 14).
Weighed most: 16 of the 253 new buildings mix uses, and none of the 149 housing buildings on the slopes has a ground floor for anything but homes, against p. 33's "avoid use-related blocks, flexible ground floors". Also: no housing mix and no interiors on any panel; the Station Bridge is drawn as a flat street with no deck, ramps or platforms (P3); only 5 % of new home floor area is within 400 m of the stop (P2); three halls stand on the B16 and its ramps (0 m, p. 28).
Unsure: the B16 breach and the 1.9 ha cut off the 1:3,000 site plan come from my own overlay on the site data, not from the panels. Noise protection can't be confirmed, because the entry's noise model leaves out the railway. The 150 kV strip can't be checked. Sealing differs between panel 2 (39.6 % + 2.5 %) and the text (33.8 % + 15.3 %). Whether a Special Mention is too lenient is the jury's own call. No closed-competition material was seen.


## Handed on by panel-layout

From `panel-layout/issues.md`. No skill runs again in this version, so a variant starts from this list. (panel-layout also lists 50 low issues for itself: drawings in the folder that aren't on the panels, mostly analysis and climate maps.)

| Skill | Severity | Issue | Fix |
| --- | --- | --- | --- |
| concept-diagrams | medium | the pictogram labels print at about 2 mm (6 pt) in the 89 mm frames, under 9 pt, because each SVG is 137.6 mm wide | draw them at 89 x 66 mm with text of 3.2 mm or more |
| plans | medium | the study-site measures drawn in red (South Bridge, the landings in Konradsiedlung-Wutzlhofen and Brandlberg), asked of the site plan, are not on `plans/site-plan_1-3000.svg` | ask `plans`, whose file it cites |
| programme | medium | housing mix: the brief asks for it (p. 33) but gives no shares, programme leaves it open, and building-types shows six types, not a mix of home sizes | ask `programme`, whose file it cites |

## Open problems

- **The jury's main point: the uses sit in bands.** 16 of 253 new buildings mix uses; no housing building on the slopes has a ground floor for anything else, against p. 33. No panel shows a flat, a floor plan or a housing mix.
- **The Station Bridge isn't drawn as a bridge.** The idea's centre is a flat street band in detail area 1, with no deck, ramps or platforms; structure-plan says the 210 m east ramp doesn't fit, and massing put the market hall beside the deck.
- **One figure, several counts.** Sealing (analysis 33.8 + 15.3 %, open-space 39.6 + 2.5 %; the panel shows open-space, the text analysis), homes (3,237 / 3,236 / 3,240), the longest gap (395 / 389 m) and the stop reach (structure plan 52 % within 400 m of the bridge, mobility 5 % of floor area to the stop point). panel-layout printed them as they are.
- **Rules the jury found broken:** three halls of Haslbach Edge stand on the B16 and its ramps (20 m asked, p. 28); daycare 2 has 470 of 950 m² of grounds; the bank row is closed along 47 % and 38 % of the line against the idea's 70 %; noise leaves out the railway.
- **Redraws not finished:** building-types draws 6 of 13 types, at 1:4,000 instead of the planned 1:1,000 (file name still `_1-1000`); analysis did 1 of 3 fixes (no sealing pies, no walking-reach hatch); the perspective renders recoloured the ground and added people; the figure-ground and site plan are cropped.
- **Fixes kept in copies.** Several skills changed their own script in this run's folder (isometric's `make_valid` fix and frame option, plans, perspective, concept-diagrams, climate, phasing, analysis, massing, open-space, mobility, building-types). A plain run of the skill won't repeat them; the useful ones belong in the skills.
- **Not made:** the A4 text PDF and the 3 communication JPGs. `figure-ground` isn't written yet.
- **Helpers:** fourteen summaries were saved by the lead from the helpers' replies, word for word: narrative twice, drawing-graphics, structure-plan, panel-layout twice, massing, open-space twice, art-direction, plans (redraw), analysis (redraw), perspective, and jury with its report.
