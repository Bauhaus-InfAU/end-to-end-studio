# run-10: Field Edge

A new version on the Regensburg brief, 2026-11-03, 23:29 to 00:37, skills at commit 612b8c4. The idea: a tight district built along one fixed edge, the field line, with the land that can't take homes and the farmland between kept as one field (41.1 ha). The jury gives **no award**: shortlisted in round 1, eliminated in round 2.

Panels: `panel-layout/panel-1.png`, `panel-2.png`, `panel-3.png` (and PDFs). Text: `narrative/text.md`. Jury: `jury/report.md`. Map of every run: `../preview/index.html`.

## Skills

| Skill | State | Time | Cost |
| --- | --- | --- | --- |
| pdf-to-md | done earlier (brief's Markdown already there) | – | – |
| brief-reader | copied (key matched) | – | – |
| site-kit | done earlier (site.geojson already there) | – | – |
| climate | copied (key matched); second run done | 1 min | $0.13 |
| analysis | done, 2 runs | 1 + 1 min | $0.27 |
| programme | done | 1 min | $0.13 |
| narrative | done, 2 runs | 3 + 5 min | $2.44 |
| structure-plan | done | 25 min | $5.44 |
| drawing-graphics | done | 1 min | $0.09 |
| panel-layout | done, 2 runs | 6 + 12 min | $4.08 |
| concept-diagrams | done | 4 min | $0.59 |
| isometric | done, 2 runs | 1 + 0.5 min | $0.22 |
| site-section | done, 2 runs | 0.5 + 0.5 min | $0.22 |
| massing | done | 6 min | $1.58 |
| streets | done | 1 min | $0.10 |
| building-types | done | 0.3 min | $0.09 |
| mobility | done | 1 min | $0.21 |
| open-space | done | 1 min | $0.21 |
| perspective | done | 4 min | $0.19 |
| plans | done | 1 min | $0.15 |
| jury | done | 6 min | $1.61 |
| phasing | not written yet (open in STUDIO.md) | – | – |
| figure-ground | not written yet (open in STUDIO.md; plans drew the figure-ground) | – | – |
| lead | | 68 min | $3.24 |

**Total: $21.01** (23 helper runs and the lead; `cost.csv`).

## What each skill found

**climate** (second run)
- Made (1:15,000, redrawn in the entry drawing standard, drawings only, no recalculation): cold-air corridor traced from the brief's Fig. 20 (p. 31), sun, shadows, wind, road noise (day and night), heat, rules map, `climate.json`, `climate.md` and `climate_sheet`.
- Key number: 16 % of the site is at 65 dB(A) or more by day (no homes; 11.9 % at the low traffic end, 17.6 % at the high end) and another 61 % at 55 to 65 (homes only behind a shielding edge); the cold-air corridor along Pilsen-Allee takes 4 % (3.5 to 5 %).
- Least sure: noise, as the brief (p. 24) gives only 10,000 to 20,000 vehicles, so speeds (70, 100 km/h) are ASSUMED, the railway is left out (no train data), DIN 18005 limits and RLS-90 are German defaults; the climate map has no legend and fits the streets to about 70 m.

**analysis** (second run)
- Measured the design (massing.geojson in place of what it covers, 112.8 ha site) the same way as today: 10 measures better, 9 worse. Within 400 m: shops 12 to 78 %, green 65 to 95 %, schools 1 to 27 %; crossings 34 to 45.
- Sealed share design: 28.2 % fully, 11.7 % partly, 60.1 % unsealed, against 14.2 / 8.3 / 77.5 % today.
- Unsure: wooded land falls from 4.1 to 0.03 ha because the design tags the old woods as park, so check that the 7.4 ha of keep woods really stay; no stops in the data; site 112.8 ha against about 107 ha.

**programme**
- Tabled homes and residents, commerce (with food market), 3 daycares, primary school, Nordbad pool, social/sport envelope, public green and play, each with its brief page; household mix left empty because the brief gives none.
- Total homes: 2,800 (framework plan) up to 3,400, for 5,000 to 6,100 residents, at least 1,100 homes in phase 1.
- Uncertainty: no household shares, no housing floor area, and only about 9,000 m² of the 36,500 m² social/sport total is itemised; residents per home (1.79) is my ratio from the brief's totals.

**narrative** (second run)
- The text: `text.md` with the brief's eight points (about 1,800 words), `communication.md` (763 signs); phase 1 1,315 homes and about 2,350 residents, phase 2 1,445 and 2,590, phase 3 680 and 1,220. No A4 PDF and no 3 JPGs.
- The field is 41.1 ha in one piece (own target at least 30 ha); the site stays 60.1 % unsealed.
- Gaps named in the text: open-space lays meadow over most of the farmed fields (only 3.9 ha of farmland counted) and 4.7 ha of park over the solar park (p. 30); 2 car streets cross the field; 40 homes over; commerce short.

**structure-plan**
- One 41 ha field with eight housing neighbourhoods on 24.6 ha along its edge, the main centre at the Wutzlhofen stop and six local centres; 3,470 homes in 3 phases (phase 1 1,350), above the 3,400 maximum, so the massing should stop at 3,400.
- Within 200 m walk of green or a centre: 98 % of the housing area; within 200 m of the field 93 %; within 400 m of a centre 74 %.
- Least sure: the 150 kV line, canal, stop and solar park read by eye from Fig. 26 (30 to 50 m); 2 car streets cross the field where the brief fixes the access.

**drawing-graphics**
- The base standard, made warm by a pale-straw fill for the kept farmland; no reference images.
- Accent #c8442b for new buildings and the field line (0.5 mm on every plan); farmland #e9e0b0.
- Unsure: the straw field against the pale greens in dense drawings; untested against references.

**panel-layout** (second run)
- 3 A1 portrait panels in the drawing standard; panel 1 the field, panel 2 the whole, panel 3 phase 1 at the station; every drawing at true scale, cropped, never shrunk.
- All 15 required panel items placed, the housing mix only in part; no A4 text PDF and no 3 JPGs.
- Unsure: the long section (632 mm) left off, as are the check plan and the today maps; sealing and homes per phase shown in two versions; detail area 2 cropped 52 %; pictograms still draw a 75.6 ha field.

**concept-diagrams**
- Six pictograms: field today, no-build strips, one field, field line, built behind, phases behind the line.
- Six pictograms, plus 00_sheet and spec.json.
- Conceptual: the structure plan didn't exist yet, so the field is drawn as 75.6 ha (the plan has 41.1 ha) and the band lies over existing housing in the west.

**isometric** (second run)
- The design, isometric at 1:10,000 (not the layout's 1:5,000, which would not fit the 222 mm frame), 144 × 144 mm.
- 141 new buildings; 412 existing, 8 at default heights.
- Unsure: streets from streets.geojson; PNG from headless Chrome or Edge.

**site-section** (second run)
- Section A-A' (1,822 m, looking north) on the design at 1:3,000 plus a 200 m excerpt at 1:500; the cut meets 2 new buildings, 7 more behind.
- Ground 336.3 to 399.8 m a.s.l.; the excerpt climbs about 33 m with the new buildings on that slope.
- Unsure: tree heights assumed; the layout frame (564 × 36 mm) is much flatter than the cut, which ended up off the panels.

**massing**
- 141 new buildings on the structure plan's 10 neighbourhoods: rows and open courtyard blocks on the cold-air axis, 5 to 6 storeys, 2 landmarks of 10 storeys at Station Rise; school, pool and 3 daycares meet the brief.
- 3,440 homes (40 over 3,400); commerce 180,552 of 230,000 m² (49,448 short), all commerce at the 6-floor cap.
- Unsure: 54 of 108 home buildings at the 6-floor cap; Line Corner 154 homes of 340 planned; no bus station (no floor area in the brief); 2 secondary streets end in nothing.

**streets**
- Existing streets from street-land.geojson, the massing's new streets added on top.
- Streets cover 22.3 % of the site (10.32 ha new); 0 buildings under new streets, 0 main routes ending nowhere.
- Unsure: 223 centrelines at default widths; the share counts street land outside the boundary too.

**building-types**
- 5 types (daycare, school, rows, open courtyard block, hall) in isometric at 1:500.
- Tallest: hall, 6 floors, 18 m; 640 × 198 mm printed.
- Unsure: the scale is the default 1:500; the daycare label reads "not in programme.csv" (programme has one daycare row, the massing three named daycares).

**mobility**
- Hub at Station Square, 5 bus routes, 6 main bike routes, cars only at the five brief gateways; 0 car links Chamer–Sandgasse.
- 2 % of new housing floor area within 400 m and 41 % within 800 m of the main stop.
- Open: plan 113.6 × 223.9 mm against a 163 × 100 mm frame; no hub building in the massing.

**open-space**
- 14 parks, 5 corridors, 8 rain basins (5,145 of 5,188 m³), 6 playgrounds within 300 m of every home, 5.1 km of paths.
- Public green 41.95 ha; play 7,704 m² against 7,500 m²; sealed 32.3 % fully, 2.8 % partly.
- Unsure: retention 43 m³ short; residents taken as 5,000 although the massing gives about 6,100; legend cut off.

**perspective**
- Two eye-level views rendered with Gemini: view-1 the edge, view-2 the square.
- 2 views from 915 candidates; 4 warnings; the script's tones, not standard.md.
- Unsure: the renders added a tractor, field robot, crop rows, glazed facades, lavender and a large tree; the masses kept their place.

**plans**
- Site plan 1:3,000 with storeys, detail area 1 Station Square 1:1,000, detail area 2 Canal School 1:1,000, figure-ground 1:15,000.
- 4 of the brief's 4 plans; none matches its panel-layout frame.
- Unsure: site plan cropped to panel width; detail area 2 at Canal School, as no district centre lies on the field line.

**jury**
- Verdict: no award. Admitted and shortlisted in round 1, eliminated in round 2: detail area 1 doesn't draw the mobility point, no plan shows the interior, commerce is 21 % short; not brought back as a Special Mention.
- Weighed most: 3.9 ha of farmland against the 23.1 ha the idea keeps farmed; the site plan shows the field as park and draws no field line.
- Unsure: the 2 % stop reach (straight line gives 42 %); the 150 kV and canal strips read by eye; 112.8 against about 107 ha.

## Open problems

- **The idea didn't reach the plan.** open-space laid meadow and park over the fields the narrative keeps farmed, and over the solar park, which the brief protects (p. 30). The site plan draws no field line.
- **Some drawings came before what they show.** The concept pictograms were drawn before the structure plan and show a 75.6 ha field, not 41.1 ha. No skill runs twice unless its own `Reads (end):` says so, so this stays in the panels.
- **Two counts of one figure.** Sealing (analysis 28.2 / 11.7 / 60.1 %, open-space 32.3 / 2.8 / 64.9 %) and homes per phase (massing against structure plan) disagree, and the panels print both.
- **Frames and drawings don't match.** The isometric, mobility, plans and section were each drawn at a size other than their panel frame; the long section is left off the panels.
- **Programme gaps.** 40 homes over the maximum, commerce 49,448 m² short, no bus station, no household mix, play short at full occupancy.
- **The stop.** 2 % of new housing within a 400 m walk of the stop, against 42 % in a straight line: the path network or the count needs checking.
- **Not made:** the A4 text PDF and the 3 communication JPGs. The skills `phasing` and `figure-ground` aren't written yet.
- **Helpers:** eight runs didn't save their own summary (narrative twice, panel-layout twice, structure-plan, massing, drawing-graphics, and jury with its report); the lead saved each from its reply, word for word. isometric's summary came in cp1252 and was converted to UTF-8.
