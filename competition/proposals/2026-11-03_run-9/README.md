# Run 9: Half Field

A new run of the whole studio on Europan 18 Regensburg, 2026-11-03, 20:01 to 21:00, at skills commit 9b2d939. Idea: the homes and work go on six compact islands so that half of the site (58.0 ha, 51.4 %) stays one working field. Jury verdict: **Special Mention**. Panels: `panel-layout/panel-1.pdf` to `panel-3.pdf`.

## Skills

| Skill | State | Time | Cost |
| --- | --- | --- | --- |
| pdf-to-md | input there, not run | – | – |
| brief-reader | input there, copied (key matched) | – | – |
| site-kit | input there, not run | – | – |
| climate | done, first run remade for the project (skill changed), second run redrew the maps | 2 min + 1 min | $0.26 + $0.09 |
| programme | done | 0.5 min | $0.15 |
| narrative | done, first run and second run (the text) | 5 min + 3 min | $1.05 + $0.85 |
| drawing-graphics | done | 0.5 min | $0.09 |
| structure-plan | done | 21 min | $4.43 |
| panel-layout | done, first run (plan) and second run (panels) | 4 min + 7 min | $0.91 + $1.64 |
| concept-diagrams | done | 2 min | $0.30 |
| isometric | done, first run (site as is) and second run (design) | 0.5 min + 0.5 min | $0.10 + $0.13 |
| site-section | done, first run (site as is) and second run (design) | 0.5 min + 0.5 min | $0.09 + $0.13 |
| massing | done | 8 min | $1.79 |
| streets | done | 2 min | $0.13 |
| mobility | done | 1 min | $0.22 |
| open-space | done | 1 min | $0.21 |
| perspective | done | 3 min | $0.17 |
| plans | done | 0.5 min | $0.13 |
| jury | done | 7 min | $1.84 |
| analysis | not written yet (counted as done) | – | – |
| phasing | not written yet | – | – |
| figure-ground | not written yet | – | – |
| building-types | not written yet | – | – |
| lead (competition-proposal) | | 59 min | $2.81 |

**Total: $17.52** (21 helper runs and the lead; run-8 was $13.13). Structure-plan alone took a quarter of it. The lead ran on Opus, not on Sonnet as the README's "On a Pro plan" says.

Ten helpers were refused saving `summary.md` (and jury its `report.md`), or left it unsaved. The lead saved each from the helper's reply, word for word: narrative (both runs), panel-layout (both runs), site-section (both runs), structure-plan, massing, open-space, plans, jury. Run-8's `README.md` and this run's `isometric/summary.md` were in Windows encoding, not UTF-8, and stopped `preview.py`; the lead converted both to UTF-8 without changing their text.

## Summaries

**programme**
- Tabled homes, residents and phase 1, commerce, social and sport (daycares, school, pool, market), public green and play, each with its brief page, in programme/ (programme.csv, households.csv, programme.md).
- Key number: 2,800 to 3,400 homes (5,000 to 6,100 residents), at least 1,100 in phase 1.
- Uncertainty: the brief gives no household mix (left open) and no housing floor area; residents per phase assume 1.79 per home, and the 36,500 m2 social total is not split in the brief.

**climate**
- Redrawn on the second run (drawing standard and panel frames now exist, no recalculation): all maps and `climate_sheet` in the entry's colours at 1:10,000, with `climate.json`, `climate.md` and the rules unchanged.
- Key number: 16 % of the site is at 65 dB(A) or more by day (no homes; 11.9 % to 17.6 % across the traffic range) and another 61 % at 55 to 65 (homes only behind a shielding edge); the cold-air corridor along Pilsen-Allee takes 4 %.
- Least sure: noise, as the brief (p. 24) gives only 10,000 to 20,000 vehicles, so speeds are ASSUMED, the railway is left out (no train data), limits and RLS-90 are German defaults; the climate map has no legend and fits the streets to about 70 m.

**narrative**
- Half Field (second run, the text): Regensburg Nord puts 3,022 homes and its work on six compact islands so that half of the site stays one working field. The jury text is in `text.md`, written to the brief's eight points (p. 34), with how we approached the site and where the design departs from its framework. The 798-sign communication text is in `communication.md` (p. 12). `narrative.md` is unchanged.
- Key number: the field is 58.0 ha, 51.4 % of the 112.8 ha site (`structure-plan/summary.md`). Sealing is 29.4 % full and 2.6 % partial, 68.0 % unsealed (`open-space/sealing.csv`), inside the framework's own targets of at most 30 % and 40 %.
- Least sure: the gaps from the framework. Commerce is 151,893 m² against 230,000 m² (`massing/areas.csv`; brief p. 28 treats framework values as limits). 98 % of buildings stand at 6 storeys, so the height profile doesn't show. Only 2.5 % of housing is within a 400 m walk of the stop (`mobility/stats.json`). The canal and 150 kV strips have no geometry. The daycares are off their named centres. The household mix and construction methods are open. The text is about 2,000 words, near the brief's 4-page maximum. The A4 PDF with the code box and the 3 JPG images are not made. No closed-competition material was seen.

**drawing-graphics**
- Look: white paper, near-black ink, pale grey city, calm farmland greens for one continuous field, with the new islands as the only warm mass, on A1 portrait at ISO 128 line weights and a 12 px text floor.
- Accent: terracotta #c8442b marks the new islands (buildings) only; the field stays in muted greens (from the narrative's "half of the site stays one working field").
- Unsure: no reference images exist, so the look is the base plus the narrative only; the green tints were chosen by me and not tested on print.

**structure-plan**
- Half Field as a structure plan: six new islands, each under 400 m across (largest 397 m), take 31.9 ha with the kept Konradsiedlung edge, the Wutzlhofen hamlet and the Chamer and Haslbach works, on one field of 58.0 ha (51.4 %). Main centre Station square, four local centres. Homes per phase 1,463 / 994 / 821 = 3,278 (brief 2,800 to 3,400, phase 1 at least 1,100). *(Shortened by the lead; full text in `structure-plan/summary.md`.)*
- Walking along the site's streets and paths and the plan's routes: 71 % of new neighbourhood land is within 400 m of a centre, and 100 % is within 150 m of a centre or public green. Rules not fully met: the Brandlberg lane crosses about 230 m of field edge, and the Chamer and Haslbach works (kept, 494 m across) are not held to the 400 m rule.
- Most important hypothesis: 165 to 180 homes per hectare of net neighbourhood land (about 1.5 to 1.6 floor-area ratio for housing alone at 90 m² per home, 4 to 6 storeys under 21 m), with most of the 230,000 m² of commerce floor area in the kept works and on the loud edges.

**panel-layout**
- Made 3 A1 portrait panels (second run, panel-N.pdf/png, look from drawing-graphics/standard.md): 1 the idea (title, idea, 4 pictograms, figure-ground 1:15,000, climate rules 1:10,000, section today 1:5,000, conflict, half-field figures with sealing 29.4 % full / 2.6 % partial / 68.0 % unsealed); 2 the site plan 1:3,000 with storeys, isometric 1:5,000, open space and mobility 1:10,000; 3 detail area 1 at 1:1,000, detail area 2 at 1:500, two perspectives, phases pictogram and "Field first" text, homes and residents per phase, design section 1:3,000.
- Key number: all 13 of the brief's required items are on the panels (report: 0 missing), with the code box, site name, title, panel numbers and a graphic scale on every drawing at a scale.
- Unsure: homes per phase disagree, massing 1,128 / 1,039 / 854 = 3,022 against structure plan 1,463 / 994 / 821 = 3,278, so both are shown and neither is corrected; detail area 2 is cropped by 81 % to 162 x 129 m around Field school; the design section moved from panel 2 to panel 3 and loses its east end and key plan; the perspectives are renders with things added that aren't in the design; the household mix stays open; the A4 text PDF and the 3 JPG images aren't made.

**concept-diagrams**
- Five separate pictograms on one site plan base (about 1:7,500, each with a graphic scale): spread or gathered, the no's joined, four crops, loud side and field side, one island per phase; the loud-side island (4) and the phase numbers (5) must still read at the 135 x 150 mm panel frame, and 5 should be 278 mm wide in the layout but is drawn in the same portrait frame.
- 5 pictograms (00_sheet, spec.json and an SVG and PNG each).
- Data: site outline, streets, rail, the retention basin, and noise and air-corridor areas from climate/rules.geojson; conceptual: the four island positions and sizes, the spread blocks, the crop areas and the air arrow, and the canal, the power line and the solar park are not drawn (no geometry); unsure whether frame 4 reads at panel size.

**isometric**
- The design, isometric at 1:5000, seen from the north-west, 209 × 264 mm in print.
- 152 new buildings; 231 existing buildings, 4 of them at default heights from the site data.
- Unsure: streets from streets/streets.geojson; colours from the drawing standard; PNG from headless Chrome or Edge.

**site-section**
- Drew the section on the design on the same line A–A′ as the first run (1,822 m, looking north, no vertical exaggeration): whole cut at 1:3,000 (632.4 x 139.8 mm) and a 200 m excerpt at 1:1,000. The cut crosses 21 buildings (1 new) and 77 stand behind (10 new). *(Shortened by the lead; full text in `site-section/summary.md`.)*
- The ground runs from 336.3 to 399.8 m a.s.l., a spread of 63.5 m. Only one new building is cut, on the rising ground to the east, so the cut shows the new islands mostly in elevation behind it.
- Unsure: the whole cut at 1:3,000 is 632 mm wide, but the `section-design` frame in panel-layout is 564 mm wide; panel-layout calls for the file `site-section_1-3000.svg`, while this one is named `site-section_design_1-3000.svg`. Tree heights are assumed. The checklist did not name elevations, so none were drawn.

**massing**
- Placed 152 new buildings on the structure plan's six islands and the Chamer and Haslbach works, plus 209 kept buildings, 103 streets, 98 open spaces and 1,163 street trees. Most buildings are rows of two 32 m bars, 14 m deep and 15 m apart, running along the cold-air flow. *(Shortened by the lead; full text in `massing/summary.md`.)*
- Gross floor area is 433,689 m² against about 525,000 m² asked. That gives 3,022 homes against the brief's range of 2,800 to 3,400, with 1,128 / 1,039 / 854 homes in phases 1 / 2 / 3. Commerce reaches 151,893 m² against 230,000 m², a shortfall of 78,107 m².
- Unsure: the programme doesn't fit under 21 m. 115 of 117 home buildings and all 33 commerce buildings stand at the 6-floor cap. The 15 m gap between rows only just clears 2 × 0.4 H = 14.4 m (p. 28); daylight is tight. Not built, because the brief gives no area: the bus station, the district garages, the youth centre and the library.

**streets**
- Existing streets: the cadastre's street, square and path areas, used as they are; the new ones come from `massing/massing.geojson`, 8.56 ha new and 58.78 ha existing, 0.61 ha of existing street land removed under new buildings.
- Street share of the site: 20.5 %; no kept building lies under a new street, but 2 main routes end nowhere, so the massing should link or end them; 223 widths are script defaults, not the brief's.
- Unsure: check plan is drawn at 1:1000 not the site plan's 1:3000; a topology crash patched in this run's copy `streets/scripts/streets.py` (skill file untouched); no brief widths in a config.json; Chamer Straße-Sandgasse rule (brief p. 28) not tested.

**mobility**
- Mobility plan for Half Field: rail and a 6-platform bus station meet at Station square; cars enter only at Sandgasse, Chamer Straße (2) and Haidhofweg with 0 car links Sandgasse to Chamer Straße; 3 main bike routes lead to named places (assumed), both underpasses stay for foot and bike.
- Share of new housing floor area within walking distance of the main stop along the network: 2 % within 400 m and 65 % within 800 m, because the stop sits at the edge of the station island.
- Missing: the 1:1,000 detail plan of the hub (the skill cannot crop it); bike destinations and bus-stop places are assumptions; no hub building in the massing.

**open-space**
- Laid out the blue-green network on run-9's massing, with terrain-dgm1 so rain runs downhill: 3 corridors, 14 retention basins, ground cover, 6 playgrounds with every home within 300 m, 4,782 m of loop paths and 26 green links (none unlinked), at 1:10,000.
- Public green is 51.3 ha against at least 6.5 ha asked, play is 8,405 m² against 8,115 m², and sealing is 29.4 % fully and 2.6 % partly sealed. Retention is 4,372 m³ against 4,387 m³ needed, 15 m³ short (0.3 %).
- Unsure: the brief's canal (10 m) and 150 kV (20 m) strips have no geometry, so nothing keeps those two strips free yet. There is no `analysis/`, so the biotopes and trees are not drawn. The 30 mm design rain is the script's default. Legend in the PNG is clipped on the right.

**perspective**
- Two eye-level views at 1.65 m: view-1 (edge, eye moved about 30 m west because the first camera stared at a blank wall) and view-2 (green); both rendered with Gemini.
- Render changes: view-1 turned the open field into a steep terraced vegetable slope, added gabled terraced houses, a retaining wall and two faceted spheres on stilts; view-2 turned the street into a paved plaza with vegetable beds, canals, solar panels and wind turbines; no building was clearly moved or removed.
- Unsure: 6 warnings stay (land uses without a rule drawn as bare ground, no bridge/tunnel data, no single existing trees, no standard.md style passed, near trees left out).

**plans**
- site-plan_1-3000, detail-area-1_1-1000 (Station square), detail-area-2_1-500 (Field school) and figure-ground_1-15000, each .svg and .png.
- All 4 of the brief's plans are drawn, and each fits the A1 panel, but none matches its frame in panel-layout/layout.json; the detail areas are far taller than their frames.
- The "Detail area 1" and "Detail area 2" labels overlap on the site plan.

**jury**
- Verdict: Special Mention. The entry passes round 1 and round 2 hurdles 1 and 2, the second only with reservations. It is eliminated in hurdle 3 (blocks, uses, public space and the mobility point are not shown) and brought back in the control round as "innovative although not completely adapted" (brief p. 13); `jury/report.md`.
- Weighed most: commerce is 151,893 m² of the framework's 230,000 m² (66 %, short 78,107 m²), and the brief treats that value as a limit (pp. 28, 30). 148 of 152 buildings already stand at 6 floors, so the islands can hardly take the missing area. Next most important: only 2.5 % of new housing is within a 400 m walk of the stop.
- Unsure: some breaches come from the jury's own geometry checks (`jury/check.txt`): one hall 14 m from the B16 axis (20 m asked), 3 buildings in the entry's own air corridor, 2 mixed buildings with homes in the 65 dB(A) zone. The canal and 150 kV strips have no geometry. The site is 112.8 ha against about 107 ha.

## Open problems

- Commerce: 151,893 of 230,000 m², with almost every building at the six-storey cap.
- Mobility: the stop sits at the edge of its island, so only 2 to 2.5 % of housing is within a 400 m walk; the hub isn't drawn at 1:1,000.
- Homes per phase: massing (3,022) and structure plan (3,278) disagree, and the phase pictogram (drawn before the structure plan) puts phase 1 on the wrong side of the railway.
- The canal and 150 kV strips have no geometry in the site data, so no skill can keep them free.
- The perspectives' renders invent things not in the design.
- Detail area 2 loses its title, scale and legend in the panel crop.
- Not made: the A4 text PDF and the three JPG images (p. 12), the housing mix.
- Nobody wrote `analysis`, `phasing`, `figure-ground` or `building-types` yet.
