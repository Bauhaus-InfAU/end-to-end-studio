# Jury report: Regensburg, "Half Field"

Europan 18, Regensburg Nord. One entry, read from its three panels (`panel-layout/panel-1.png` to `panel-3.png`, cited P1 to P3), its explanatory text (`narrative/text.md`) and the brief (`Regensburg_EN_1.md`, PDF pages). The jury judged only what the entry shows and what the brief says. No results, jury reports or other entries were consulted. Where a caption promises something the drawing does not show, the drawing counts. The jury's own recounts from the entry's geometry are in `jury/check.py` and `jury/check.txt`.

## 1. Task and criteria

The task is a new district on about 107 ha of farmland 4 km north of the centre (p. 27): 2,800 to 3,400 homes for 5,000 to 6,100 residents, at least 1,100 of them in a first phase between Chamer Straße and the railway, with the intermodal mobility point at the new Wutzlhofen stop (pp. 27, 33). The programme includes 230,000 m² of commerce floor area, a primary school, three daycare centres, the Nordbad and a food market (p. 30). The city asks for less soil sealing, few to no cars, flexible ground floors and fresh-air corridors kept open, and it expressly welcomes bold ideas (p. 33). The framework plan's areas count as minimum and/or maximum values (p. 28).

The brief names the criteria without weighting them (p. 14). The local jury checks compliance first, then conceptual content and innovation against the Europan 18 topic. The national jury may then assess seven criteria. The jury weights them as follows:

| Weight | Criterion (p. 14, p. 33) | Why |
|---|---|---|
| Carrying | Relationship between concept and site | The brief makes the treatment of unsealed soil the central question (p. 33). |
| Carrying | Relevance of the programme to the brief | The homes, the first phase and the mobility point are stated as musts (p. 33); the framework areas are limits (p. 28). |
| Carrying | Architectural and technical qualities, including how the blocks and uses are organised | At this scale the interior of an entry is its blocks and the uses inside them. The brief asks for flexible ground floors and against use-based blocks (p. 33). |
| Contributing | Relevance to the topic: sustainable development and adaptability | This is already mostly covered by the first carrying criterion. |
| Contributing | Integration into an urban process adapted to the site | Phasing is required content (p. 34). |
| Contributing | Innovative nature of the public spaces | This carries weight here because the entry makes open space its idea. |
| Contributing | Connection between functions | This is tested through mobility and uses. |
| Supplementary | Unwritten criteria: self-evidence, fit with the place, whether a political majority could back it | These are the jury's own assessments, each one supported by the entry and the brief. |

## 2. Preliminary check

### Formal requirements (pp. 11–12)

| Requirement | Brief | Entry | Met |
|---|---|---|---|
| Panels | 3, A1 portrait, PDF, ≤ 20 MB (p. 11) | 3 PDFs, 594 × 841 mm; 0.80, 2.53, 7.25 MB | yes |
| Code box | 60 × 40 mm blank, upper left (p. 11) | Blank on all three panels (pixel test); city name beside it at 66 mm | yes |
| Panel numbers | 1 to 3, upper right (p. 11) | 1, 2, 3, upper right | yes |
| Site name and title | On every document (p. 11) | "Regensburg", "Half Field" on each panel | yes, on the panels |
| Language | English (p. 11) | English | yes |
| Graphic scale | On every graphic document (p. 11) | Present on all plans, pictograms, sections and the isometric. Missing on detail area 2 (P3), where the 81 % crop cuts off its title, scale bar and legend. | no, one drawing |
| Text | A4 portrait PDF, 3–4 pages, code box (p. 12) | Written as Markdown, about 2,200 words; no A4 PDF made | no |
| Communication | 800 signs and 3 JPG images ≤ 1 MB (p. 12) | 798 signs (`narrative/communication.md`); no JPG images | partly |

### Required contents (pp. 11, 33–34)

| Item | Where | Remark |
|---|---|---|
| Figure-ground 1:15,000 | P1 | present |
| Site plan 1:3,000 with storeys | P2 | present; every new building is labelled with its storey count |
| Detail area 1, mobility hub, 1:1,000 | P3 | present as a plan. The mobility point is a grey square with a symbol: no bus station with 6 platforms, no Kiss+Ride, no Park+Ride or district garage, no platform at the stop (p. 27). |
| Detail area 2, 1:1,000 or 1:500 | P3 | at 1:500 (Field school); the panel shows no title, scale or legend |
| At least 2 perspectives | P3 | 2 views, captioned "illustrative render". They contradict the plan (gabled houses, a terraced slope, faceted spheres on stilts, windowless concrete walls). |
| At least 1 isometry | P2 | present, 1:5,000, with the context |
| Sealing: full, partial, % of site | P1 | 29.4 % full, 2.6 % partial, 68.0 % unsealed |
| Residents per phase | P3 | 2,020 / 1,860 / 1,530 |
| Phasing | P3 | Pictogram and table disagree: the pictogram shows 4 phases with phase 1 east of the railway, the table 3 phases with phase 1 west of it. P3 also gives two totals, 3,022 and 3,278. |
| Housing mix (p. 33) | P3 | "open, the brief gives no shares". The brief asks for statements on the mix, not shares, so the item is missing. |
| Relation to the existing context, 3D (p. 11) | P2 | isometric, section P3 |
| Implementation method (p. 11) | P3 | "Field first" text, 5 lines |
| Text: eight points (p. 34) | `text.md` | all eight are answered; construction methods are left open (point 4) |

### Material requirements (pp. 27–34), recomputed by the jury

| Requirement | Brief | Entry | Met |
|---|---|---|---|
| Homes | 2,800–3,400 (p. 33) | 3,022 = 271,954 m² housing GFA / 90 m² (P3, `massing/stats.json`) | yes |
| Homes in phase 1 | ≥ 1,100 (p. 33) | 1,128; the margin is 28 homes (2.5 %) | yes, narrowly |
| Residents | 5,000–6,100 (p. 33) | 5,410 at 1.79 per home (5,000 / 2,800 from p. 30) | yes |
| Public green | 12 m² per resident = 6.5 ha (p. 34) | 51.3 ha, counting the field parks | yes |
| Play area | 1.5 m² per resident = 8,115 m² (p. 28) | 8,405 m², 6 playgrounds | yes |
| Commerce floor area | 230,000 m², as a limit (pp. 28, 30) | 151,893 m², 66 %, short by 78,107 m² | no |
| Daycares | 3 × 1,000 m², 10 m² play per child (p. 30) | 3,841 m² floor area. The outdoor play areas are not shown, and the daycares are not drawn on the centres named for them. | partly |
| Primary school | 3,000 m², yard 2,000 m² (≥ 5 × 370 = 1,850), sports 3,000 m² (p. 30) | 3,000 / 2,043 / 3,000 m² | yes |
| Nordbad | 3,000 m² hall, 4,000 m² with its plot (p. 30) | 3,000 m² hall; the plot is not shown | partly |
| Food market | about 1,200 m² sales area (p. 33) | Claimed in a Station square landmark; not drawn | not shown |
| Bus station, 6 platforms; K+R, P+R (p. 27) | required | Claimed in the text; not drawn (P3) | not shown |
| Height | no extensive building from 21 m; a few taller in the centre (pp. 28, 33) | 148 of 152 at 6 floors (18 m); 2 at 8 floors (24 m) at Station square | yes |
| B16 setback | ≥ 20 m to the street (p. 28) | One commerce hall stands 14 m from the B16 axis. Two more stand 21 m from the axis, which puts them inside 20 m of the carriageway (jury's measure). | no |
| Canal 10 m, 150 kV 20 m (p. 30) | kept free | Neither strip is drawn on any panel. Not shown to be met. | not shown |
| Solar park, retention basin (p. 30) | kept | No new building on either (jury's check) | yes |
| Fresh-air corridor (p. 33) | respected | 3 Wood edge court buildings stand in the corridor drawn on the entry's own climate rules map (P1) | no |
| ≥ 65 dB(A) by day (entry's own rule, P1) | no homes | 2 mixed buildings with homes above (Station rows, Rail yard blocks) stand in that zone | no |
| No link Chamer Straße – Sandgasse (p. 28) | no car link | 0 car links; a bus-only gate | yes |
| Existing trees, biotopes (p. 28) | kept, integrated | Not drawn | not shown |
| Project site | about 107 ha (p. 27) | 112.8 ha measured, 5.4 % more | to be clarified |

**Admission.** The entry is admitted. The formal gaps are the missing A4 text PDF, the missing JPG images and the missing scale on one drawing. These concern documents outside the panels or are minor, and they do not compromise anonymity. The material breaches are the commerce shortfall, the B16 setback and the buildings in the air corridor. They are taken into the judging, not treated as exclusion.

## 3. Rounds

One entry cannot be compared with others, so the brief's procedure (p. 14) is used as a sequence of hurdles.

**Round 1, local jury: conceptual content and innovation against the Europan 18 topic.** The entry passes. Its idea is stated in one sentence and drawn in one move (P1): the strips and areas where the site already forbids building are joined into one field of 58.0 ha, 51.4 % of the site, and the district is gathered onto islands. Soil as the resource kept is a plausible reading of the theme. The idea can be counted, and the entry counts it.

**Round 2, national jury, hurdle 1: concept and site, topic relevance.** The entry passes. The field continues the cold-air corridor and the landscape at the urban edge, and it gives the Konradsiedlung a common edge. Sealing of 32.0 % in all is a strong answer to p. 33.

**Round 2, hurdle 2: relevance of the programme and integration into an urban process.** The entry passes with reservations, by majority. Homes, residents, phase 1, green, play and the school meet the brief. Commerce reaches only two thirds of a framework value the brief treats as a limit (p. 28). The housing mix is missing. The phasing contradicts itself on the same panel (P3).

**Round 2, hurdle 3: public spaces, connection of functions, architectural and technical qualities.** The entry is eliminated here. The organisation of the blocks and their uses is not shown. Every new building is the same red slab with a storey number (P2, P3). Housing rows, mixed blocks and six-storey commerce "halls" cannot be told apart. No ground floor, entrance, address or open-space division is drawn, even at 1:500. Detail area 1, the one detail every entrant must work out, lacks the mobility point that the brief calls the centrepiece of the strategy (p. 27). The working field, the entry's own public space, appears only in a pictogram (P1) and in renders that the entry itself calls illustrative (P3).

**Control round.** The jury tested whether the entry could return to the prize ranks, and it cannot: the elimination concerns carrying criteria. It then tested a Special Mention, which the brief reserves for "a project considered innovative although not completely adapted to the site" (p. 13). The method of turning the site's prohibitions into one counted commons is found innovative, and its weaknesses are weaknesses of adaptation. The entry is brought back for a Special Mention.

## 4. Appraisal

The authors read the site through its prohibitions. The canal and power-line strips, the retention basin, the solar park, the cold-air corridor and the land too loud for homes are drawn first, and joined they become one field (P1, pictogram 2). The building land is whatever remains. This reading is self-evident and legible from a distance. It takes the brief's phrase about the "high value of unsealed soil" (p. 33) literally and makes it measurable. The figure-ground (P1) shows the islands as a clear figure on open ground, and the long section (P1) places the site in the shallow valley between the B16 and the eastern slope. The jury welcomes the decision to set the Konradsiedlung's garden-city tradition next to a common field. It is a fitting gesture to the place (assessment).

On the site plan (P2) the islands are less compact than the text claims. In the north-west they spread as parallel bars over a large area, and the field between them narrows to strips. The "one field" is cut in two by the railway and Pilsenallee, and only the underpass joins the halves. The bars run north–south along the night air flow. The jury finds this a reasoned choice, but it is not carried through: three buildings of Wood edge court stand in the corridor the entry draws itself (P1, climate rules). Along the B16 one commerce hall stands well inside the 20 m setback (p. 28). Two mixed buildings with homes above stand in the zone of 65 dB(A) or more where the entry's own rule allows no homes.

The key figures are well kept in most respects. At 3,022 homes and about 5,410 residents the entry lies inside the brief's range, and phase 1 clears the 1,100 minimum by 28 homes. Public green (51.3 ha against 6.5 ha), play (8,405 against 8,115 m²) and the school figures are met. Sealing is 29.4 % full and 2.6 % partial. The floor area ratio of 1.71 on 25.4 ha of building land is a sober density. Commerce, however, reaches 151,893 m² of the framework's 230,000 m² (p. 30), a shortfall of a third, and the entry concedes it (text, section 10). With 148 of 152 buildings already at six storeys, the jury doubts that the islands can absorb the missing area without giving up either the field share or the height limit. P3 gives two totals, 3,022 and 3,278, without saying which applies. The site is measured at 112.8 ha against the brief's 107 ha, so every percentage depends on that choice.

The entry is weakest where the jury tests hardest. Inside the islands, nothing is shown of how the buildings work. The pairs of 14 m bars 15 m apart only just clear 2 × 0.4 H. The resulting daylight in the lower floors is questioned, and no section through a row is offered. The brief asks for flexible ground floors and no use-based blocks (p. 33). The text promises flexible ground floors along Station rows and the rail yard (text, section 7), but no plan shows them. Commerce is put into separate works, which is precisely a use-based block. Six-storey "halls" for crafts are not a credible typology. The housing mix and the construction methods are left open, although the brief asks for both (pp. 33, 34).

Mobility fails to fully convince. The stop and the bus station at Station square are named in the text and drawn as a symbol. Only 2.5 % of new housing floor area lies within a 400 m walk of the stop, against about 40 % within 400 m in a straight line (jury's measure). The network therefore routes people around the field rather than towards the stop, contrary to the brief's call for short routes (p. 27). The phasing idea that each phase first lays out and hands over its part of the field is attractive and fits an urban process. But the phase pictogram places phase 1 east of the railway, where the plan shows field (P3), and the brief's first phase lies west of it (p. 33). The perspectives show vegetable beds, gabled houses and blank concrete walls. They do not represent the plan and cannot count as evidence of its spatial quality.

A political majority could plausibly form around half the land kept as farmland and commons, a low sealing figure and the full housing number (assessment). It is put at risk by the missing third of the commerce, by uniform six-storey bars next to a garden city of the 1920s, and by the open question of who runs and pays for the field. The entry offers a clear and innovative strategy, but it remains a structure plan without the district inside it.

## 5. Verdict

**Special Mention.** The entry is eliminated in round 2, hurdle 3, and brought back in the control round as a project considered innovative although not completely adapted to the site (p. 13). It receives no ranking.

## 6. Recommendations for further work

- Draw the mobility point in detail area 1 at 1:1,000: the stop with its platform, the 6-platform bus station with regional access from Chamer Straße and city access from Sandgasse, Kiss+Ride, Park+Ride or the district garage, and the food market (p. 27, p. 33).
- Re-route the paths so that a meaningful share of homes lies within a 400 m walk of the stop, or move homes and the stop closer together.
- Close the commerce gap of 78,107 m² (p. 30), or justify the reduction against p. 28. Test where it goes without giving up the 21 m limit or the field share.
- Show the interior of the islands: ground-floor uses and entrances, a typical row and a courtyard block in plan and section, the private and public open space between the bars, and daylight between rows 15 m apart.
- Give the housing mix and the construction methods (p. 33, p. 34), and differentiate the housing, mixed and commerce buildings in the site plan legend.
- Draw the 10 m canal strip and the 20 m 150 kV strip (p. 30), the existing trees and the biotopes (p. 28). Move the hall inside the B16 setback (p. 28), the three buildings in the air corridor and the homes in the zone of 65 dB(A) or more.
- Draw the working field: plots, operators, access, water and energy. Replace the illustrative renders with views that follow the plan.
- Make the phasing consistent: one pictogram and one table with the same phases, phase 1 between Chamer Straße and the railway, and one total of homes.
- Recrop detail area 2 so that its title, scale bar and legend show, and show the schoolyard, the sports area and the daycare play areas.
- Clarify the site area (112.8 ha against about 107 ha, p. 27) and restate the percentages on the brief's figure.
- Produce the A4 text PDF with the code box and the 3 JPG images (p. 12).
