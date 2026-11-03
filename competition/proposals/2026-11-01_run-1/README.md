# 2026-11-01_run-1

Run on what exists: the four skills on main ran, the sixteen others aren't written yet. Panels: `panel-layout/panel-1.pdf` to `panel-3.pdf`.

| Skill | State | Time | Tokens |
|---|---|---|---|
| `narrative` | done (2 runs) | 5 min 11 s | 181,160 |
| `site-section` | done (2 runs) | 11 min 50 s | 220,167 |
| `massing` | done | 12 min 48 s | 193,422 |
| `panel-layout` | done | 3 min 4 s | 113,592 |
| `brief-reader` | not written yet | | |
| `climate` | not written yet | | |
| `analysis` | not written yet | | |
| `structure-plan` | not written yet | | |
| `programme` | not written yet | | |
| `phasing` | not written yet | | |
| `mobility` | not written yet | | |
| `open-space` | not written yet | | |
| `drawing-graphics` | not written yet | | |
| `figure-ground` | not written yet | | |
| `plans` | not written yet | | |
| `isometric` | not written yet | | |
| `building-types` | not written yet | | |
| `concept-diagrams` | not written yet | | |
| `perspective` | not written yet | | |
| `jury` | not written yet | | |

Total: 32 min of agent time, 708,341 tokens (`usage.csv`). Cost: see "Cost" at the end.

## narrative

- Field Lines, *The lines that cut the site, made green*: the strips the sewer and the 150 kV line keep free are widened into green corridors (30 m and 40 m, plus a diagonal to the forest) and the district is built in blocks between them; second run, the story was rewritten because the massing built blocks on the brief's framework plan, not the first run's north-south field strips (`narrative.md`, "What changed"). No brief-reader, analysis or climate existed; the brief's Markdown, `competition/site/`, `massing/` and `site-section/` were read instead. Wrote `text.md` (brief headings, p. 34) and `publication.md` (750 of 800 signs, p. 12).
- Public green 188,419 m² against the 60,000 m² asked (`massing/areas.csv`; brief pp. 30, 34), for 3,204 homes (`massing/stats.json`).
- Least sure of the site boundary (`massing/summary.md`: about 200 m south of the brief's planning area, which also explains most of the 132,781 m² commerce shortfall) and of sealing, which no file measures yet; the text leaves the sealing shares open, and most panel drawings are listed as missing.

## massing

- Made: 228 new buildings (3 to 6 storeys, two 10-storey landmarks at the district centre by the new Wutzlhofen stop, school, 3 daycare centres, indoor pool, food market, 2 district garages), 10 km of new streets, green corridors over the sewer and the 150 kV line, and 323 existing buildings kept (`existing: true`). The urban figure was derived here from the brief's Fig. 26 and Fig. 28 (pp. 36–37), georeferenced on OSM, because structure-plan, programme, brief-reader, analysis and drawing-graphics were missing. The rules and programme come from brief pp. 28–34, and the assumptions (90 m² per home, 3 m storeys, 13/15/22 m depths, corridor widths) are in `design.json`.
- Floor area 394,585 m² gross: housing 288,364 m² = 3,204 homes (brief 2,800–3,400; 1,378 in phase 1, at least 1,100 asked) and commerce 97,219 m² (brief asks 230,000, so 132,781 m² short). FAR is 0.36 on the 109.4 ha site and 0.63 on the 62 ha of open land. Public green is 18.8 ha against the 6 ha asked; the full table is in `areas.csv`.
- Unsure: `site.geojson` sits about 200 m south of the brief's planning area (checked against the Fig. 26 aerial and the Fig. 28 boundary), so it takes in part of the existing Konradsiedlung and leaves out the brief's commercial land in the north, which is the main reason commerce falls short. Fix site-kit, then run massing again. The landmarks need checking against the 0.4 H street distance, and the school ended up on a leftover block in phase 3.

## site-section

- Drew the same line A–A′ (1,666 m, A 12.117737/49.048271 to A′ 12.138768/49.054035, looking NNW, A on the left) again on the design, from this run's `massing/massing.geojson`, at 1:3000 (`site-section_design_1-3000`) with the same excerpt a–a′ at 1:1000 (`site-section_excerpt_design_1-1000`, stations 460–660 m), plus a second excerpt b–b′ at 1:1000 (`site-section_excerpt-b_design_1-1000`, stations 640–840 m), because a–a′ ends just where the first new block begins (station 654), so on its own it shows almost nothing new; the as-is drawings (`site-section_1-3000`, `site-section_excerpt_1-1000`) stay next to them for comparison. The cut passes through 9 new buildings (open and perimeter blocks of 15–18 m, a mixed noise-shield block of 18 m by the railway, two 12 m commercial courts east of Pilsen-Allee) and shows 24 more in elevation, all in the red accent, with 98 new street trees and 10 new streets; fallback look (black on white, greys, one red accent), since `drawing-graphics` and `brief-reader` did not run; scales from the brief (site plan 1:3,000, detail areas 1:1,000).
- Height difference along the cut is 28.3 m (339.7 m a.s.l. just east of Pilsen-Allee at station 1,114 m, 368.0 m in the Konradsiedlung at station 42 m), and 21.9 m inside the site (339.7–361.6 m), from the Bavarian open DGM1 (1 m, DHHN2016), sampled every 2 m in `profile.csv` (unchanged from the first run); no vertical exaggeration. The massing gives no new ground levels, so the new buildings stand on today's terrain.
- Unsure of: the massing's heights (storeys × 3 m, flat roofs) and existing heights (OSM levels × 3.2 m; 4 of 10 existing cut and 30 of 75 existing elevation buildings have default heights), the assumed tree heights (new street trees 12 m, forest 22 m, park 14 m, scrub 4 m), the land between new blocks (field land within 6 m of a new building or under a new street or open space is drawn bare; new parks, corridors and courtyards as grass), people at assumed entrances, the site boundary (the massing notes it sits about 200 m south of the brief's planning area), and street names whose umlauts were restored by hand.

## panel-layout

- Made 3 vertical A1 panels (594 × 841 mm, brief p. 11) along the narrative storyline. Panel 1, "The lines of the field": title, idea, Concept and Green texts, the as-is section 1:3000 and excerpt a–a′ 1:1000. Panel 2, "Blocks between the lines": the massing check plan 1:3000 with storeys, the design section 1:3000, key figures. Panel 3, "Where the lines meet": the design excerpts a–a′ and b–b′ 1:1000, Project site, Mobility, Step-by-step texts, residents per phase. PDFs are 0.17, 0.80 and 0.13 MB (limit set to 5 MB). Every drawing is printed at its true scale. Each panel has a blank 60 × 40 mm code box, Regensburg / Field Lines and its number. No style standard existed, so the default look is used.
- 3 of the 9 drawings and figures the brief asks for (p. 34) are on the panels: the site plan with storeys, the residents per phase and the phasing. Still missing: the figure-ground 1:15,000, detail areas 1 and 2, two perspectives, an isometry and the soil sealing in %. Panel 3 (19 % covered) and the lower half of panel 1 are left empty where these belong.
- Unsure: the site plan is the massing's check plan, not a finished plan. The 1:3000 sections are 587 mm wide, so they sit 3.3 mm from the paper edge, inside the 15 mm margin. The per-phase homes (1,378 + 1,488 + 340 = 3,206, from massing.geojson) are 2 more than the total of 3,204 in stats.json, probably from rounding. The site boundary doubt from massing still applies.

## Open problems

- The site boundary may sit about 200 m south of the brief's planning area (massing); this is the likely cause of the commerce shortfall (97,219 of 230,000 m²). Check `competition/site/site.geojson` against brief Fig. 26 and 28, re-run site-kit if needed.
- The massing didn't follow narrative's first idea, because massing doesn't read narrative; narrative rewrote its story to the design.
- Agents were blocked from writing `summary.md` ("report file"); the lead wrote four of them from the agents' hand-backs, two agents wrote theirs through the shell.
- Street names in the site kit have lost their umlauts.
## Cost

- Whole Claude Code session, from `/cost` at the end: **$16.23** (Opus 5.5; 92.9k input, 233.5k output, 30.8M cache read, 884.6k cache write tokens). This includes the pull-request review, the fixes and the Miro upload, not only the run; no `/cost` was taken before the run, so the run's own share can't be separated exactly.
- The run's six agent jobs used 708,341 tokens (`usage.csv`): massing 193k, site-section 220k (2 runs), narrative 181k (2 runs), panel-layout 114k.
- `/cost`, usage over the last 24 h on this computer (all sessions, not only this one): the general-purpose agents, which ran the skills, are 10 % of usage; the Rhino connection is 28 %, although the run never used Rhino.
- Next run: type `/cost` before and after, and the difference is the run.

## Problems in the drawings

Marked by Egor on the Miro board after the run.

**massing**
- Buildings with hooks, slivers and fragments, also where blocks meet the site edge: of 228 new buildings, 29 have a part under 6 m wide, 20 are under 150 m², 118 are clearly not rectangular. The script cuts each block from what is left after streets, corridors and set-backs, and shrinks that leftover into buildings.
- Streets that end in the open, where they were cut off at the site edge.
- A block where a few small existing buildings stay and new pieces are squeezed in between them.
- Nothing caught this: the skill doesn't ask the agent to look at its own plan.
- Lines to add: build every building from straight wings at least the usable depth wide, and leave a leftover piece open rather than cut a building to fit it; every new street connects at both ends; where existing buildings stay, build the block around them or leave it; open `massing.png` before you finish, slivers, hooks, fragments and dead ends are mistakes.

**site-section**
- Buildings behind the cut float above the ground where their own ground is higher than the cut line (since the "stand on its own footprint" fix), because the ground behind isn't filled in.
- Line to add: fill the ground behind, between the cut line and the highest ground behind, in a light tone, so buildings standing higher behind don't float.
