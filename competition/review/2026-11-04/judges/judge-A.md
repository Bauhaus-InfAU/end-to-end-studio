# Judge A: competition architect

Opus, independent. Read the changes C1 to C18 in order. Saved word for word from its reply.

1. Ratings

| id | gap | effort | risk | potential | rank | one-line reason |
|---|---|---|---|---|---|---|
| C1 | 2 | 2 | 3 | 5 | 13 | Gets each helper looking at the winners, but its fixes stay in per-run script copies, and the scripts can only recolour. |
| C2 | 0 | 1 | 1 | 4 | 12 | A jury sees no difference. It is a cheap ruler for every other change. |
| C3 | 2 | 1 | 2 | 6 | 6 | Cheap. It brings back the missing section, the 1:5,000 isometric and the uncropped detail area. |
| C4 | 2 | 3 | 4 | 4 | 16 | An Opus redline round on scripts that can't act on it yet. It duplicates C1 and breaks "the lead never adds a round". |
| C5 | 1 | 1 | 2 | 6 | 3 | Draws nothing itself, but it lifts the bans that keep the isometric, pictograms and views empty. |
| C6 | 2 | 4 | 3 | 6 | 7 | The pipe from the references to the scripts. It means migrating eight scripts, and it pays off only once they draw shadows and trees. |
| C7 | 3 | 2 | 2 | 8 | 1 | Removes the loudest wrong thing on our boards, 141 red boxes, and plans.py nearly supports it already. |
| C8 | 4 | 3 | 2 | 8 | 2 | Trees are most of what a jury sees on the winners' plans. Run 10's massing already holds 1,363 street trees that the site plan doesn't draw. |
| C9 | 4 | 4 | 4 | 8 | 5 | The only change that touches the urban design itself. It is costly, and nine skills read its output. |
| C10 | 3 | 4 | 4 | 6 | 10 | The interior is where rounds 2 and 3 are decided, but it is hard to design well in code and easy to make cluttered. |
| C11 | 1 | 3 | 2 | 3 | 18 | Removes one doubled number and gives the phase map an owner. A jury barely sees it. |
| C12 | 2 | 3 | 2 | 5 | 11 | One strip of one board, and with today's massing an ensemble is still bars. |
| C13 | 3 | 3 | 3 | 6 | 9 | A required drawing that the winners make a hero. It needs C5, C7 and C8 first. |
| C14 | 3 | 2 | 3 | 7 | 4 | Views are what a jury looks at first, and ours look like another project. The fix is mostly one prompt line and one image. |
| C15 | 2 | 3 | 2 | 5 | 14 | Moving it after the structure plan corrects a wrong 75.6 ha field in an afternoon. The new vocabulary is more work for less gain. |
| C16 | 2 | 3 | 2 | 4 | 15 | This brief doesn't require a section. A story strip is a good Europan habit but a low priority. |
| C17 | 2 | 4 | 2 | 4 | 17 | A new skill plus pulling the drawing parts out of three long scripts, for small plans a jury reads last. |
| C18 | 2 | 2 | 2 | 5 | 8 | Board hierarchy and big numbers count at first glance, but only once the drawings are worth enlarging. |

2. Dependencies

- C5 -> C13, C14, C15, C10: lifts "No labels, arrows or people", "only the trees the data has" and "add no use … the narrative doesn't give". Without it these four contradict STUDIO.md.
- C7 -> C13, C12: pale volumes with the accent on public ground are the look of both. C7 needs public ground to colour. Massing writes only 8 squares of about 30 m, so the missing public-ground layer (section 5) multiplies C7.
- C8 -> C13, C16, C14: the isometric, the section and the perspective base view all need the same tree data.
- C9 -> C12, C13, C10, C14: building parts, roofs, ground-floor use and a hub building. Without C9, C12 is a block of bars.
- C9 <-> C10: both want to own ground-floor uses. Decide the owner first, since a skill never edits another skill's file.
- C6 -> C7, C8, C14, C16, C17: keys for shadow, tree symbol, render style, section and diagram style. Do C7's and C8's keys as the first part of C6's schema, not after a big-bang migration.
- C3 -> C18, C16, C13: drawings must hold their frames before a hero layout or a large isometric frame makes sense. Without C3 the section is left off again.
- C11 -> C18, C17: one owner per count lets C18 drop "show both". C17's phase plan needs it.
- C2 -> C1, C4: the shared side_by_side.py script.
- C1 <-> C4: overlap. Do one loop, not both. Either is weak before C6 to C9, because the scripts can't take a fix.
- C15 delays concept-diagrams until after the structure plan (23:59 in run 10). That is fine for the order, but it lengthens the critical path.

3. Top five

C7 (rank 1). On the wall, the first thing a juror reads on our panel 2 is "141 red boxes", not a district. In `evidence/02_site-plan_same-size.jpg` all three winners keep their buildings white with a thin dark outline and a cast shadow, and spend the accent on public ground (winner 3's pink streets and centre, winner 1's rose hub square). The causes are exactly where gaps.md says: `drawing-graphics/base.md:16` ("usually the new buildings"), `plans/SKILL.md:11` ("One thing dominates each plan: the new buildings") and `building-types/SKILL.md:14`. It is cheaper than changes.md suggests. `plans.py:394` already switches the storey numbers to ink when `new` is pale. The real blocker is `check_style.py:33-35`, which demands 3:1 contrast for `new` as well as `accent`. A shadow pass in shapely, a translated footprint drawn under the building, is a few dozen lines. What could go wrong: with only 8 small squares as public ground (run-10 `massing/summary.md`), the accent has almost nothing to land on, and the plan can lose its figure entirely. White buildings on pale green need the outline and shadow to read at 1:3,000. The isometric needs its own fix, because its keys don't match style.json (section 5).

C8 (rank 2). Trees are the single largest difference in area on every winner's plan. In `02_site-plan_same-size.jpg` the winners' 150 mm patches are mostly crowns: avenues, courtyard trees, groves and canopy over the kept woods. Ours has none. `evidence/03_detail-areas.jpg` shows ours carrying only street-tree dots at 1:1,000. I checked: `plans.py:49` sets `tree_scale_max` to 2000 and `plans.py:378` applies it, so trees are skipped at 1:3,000. Line 381 draws each one as a 2.5 m circle. `open_space.py` writes no trees, and `massing.py:735-745` places only street trees. But run 10's massing already holds 1,363 street trees (`massing/summary.md`), and `tree_scale_max` can be overridden from `plans/config.json` (`plans.py:88`, `CFG = {**DEFAULTS, **CFG}`). So half of this is a config value today, and the other half is a planting layer from open-space's parks and the kept woods. What could go wrong: crowns hiding buildings and storey numbers at 1:3,000. Filler trees over pools, playgrounds, the solar park or farmland, which would misstate the design. Planted trees being counted as kept wood (analysis already confused park with wood, run-10 `log.md` 00:07).

C5 (rank 3). On its own it draws nothing, hence gap 1. But it is an afternoon's work, and four changes depend on it. `isometric/SKILL.md:14` ("No labels, arrows or people", "only the trees the data has") and `concept-diagrams/SKILL.md:10` ("add no use, height, position or route the narrative doesn't give") are why our isometric in `evidence/05_isometric.jpg` is mute. Winner 2's isometric at 1:1,000 names its mobility hub, supermarket and library, and winner 1's pictograms are people. A juror reads use labels and people as design intent, not as invented data. What could go wrong: a loose wording lets Sonnet helpers invent uses or numbers. Keep "every number has its source" (`STUDIO.md:63`), require that intent come from a named design layer or the narrative, and mark illustrative content as such. Leave panel-layout's line alone (section 5).

C14 (rank 4). In Europan the perspectives carry the atmosphere, and winner 1 opens board 1 with one. `evidence/06_perspectives.jpg` shows ours as photoreal grey concrete with invented objects: crenellations in run 8, domes in run 9, a tractor and a field robot in run 10 (`log.md` 00:11). They look like a different project from the panels around them. The cause is one line: `render.py:125` hard-codes "Render it as a photorealistic architectural perspective". `base.md:50-53` gives renders only don'ts. The fix is mostly a style key plus one extra image in `contents` (`render.py:178`), and `tests/test_perspective_render.py:109` only needs the prompt to stay last. What could go wrong: sending the winners' own perspectives as the style image invites the model to copy their content (the pink tower, "MOBILITY HUB" lettering), which breaks the CLAUDE.md rule on the winners' texts. A style sheet that drawing-graphics derives from them is safer. An illustrated style gives the model more licence to move geometry, so keep KEEP_GEOMETRY. "Signs of the uses" contradicts `render.py:39` ("No text, no labels"), so decide which wins.

C9 (rank 5). The drawings can't beat the geometry under them, and in round 2 a jury judges the figure and the blocks, not the graphics. `evidence/01_boards.jpg` and `02_site-plan_same-size.jpg` show winners mixing L and U blocks, open courtyards, town-house rows and towers. Ours are combs of 13 m by 30 to 50 m bars. `massing.py:156-185` (`segs`, `block_buildings`) can only make boxes on the long and short sides of a grid block. I start it fifth, in parallel, because it is the longest job. What could go wrong: it has the widest blast radius (nine readers of `massing.geojson`). The programme is already tight (54 of 108 home buildings at the 6-floor cap, run-10 `massing/summary.md`), and parts and roofs raise the Opus massing cost. Most of all, the comb was partly the agent's choice. Run-10 `massing/config.json` sets `orientation: 8` and rows on every housing neighbourhood, from narrative principle 4, although `massing.py:69-75` already offers courtyards, points and `route`. A library without a rule that each neighbourhood mixes two or three types can return the same comb.

4. Bottom three

C11 (rank 18). A juror would notice the doubled homes per phase (1,315 / 1,445 / 680 against 1,350 / 1,400 / 720, run-10 `panel-layout/summary.md`). It would read as sloppy, not as the reason an entry falls. A phase pictogram already exists. A new skill is a heavy cure. One line in panel-layout ("the layer that owns a number wins, and the other goes to notes") fixes the visible part.

C17 (rank 17). Winner 3's row of four small plans is elegant, but a jury reads small thematic plans last. The cost is high: a new skill, plus pulling the drawing parts out of `mobility.py` (924 lines), `open_space.py` (855) and climate's `draw.py` (649). C3 (maps held to one frame and scale) and C6's diagram style get most of the way for a fraction of the work.

C4 (rank 16). It adds an Opus judge plus re-runs, roughly $3 more on a $21 run. It needs exceptions in `STUDIO.md:49` ("the lead never adds a round") and `competition-proposal/SKILL.md:19`, and a change to `tests/test_order.py:4`, whose OPUS set is fixed. Before C6 to C9, a named skill can only patch its per-run script copy, so the redlines become improvised, unreviewed fixes that are lost after the run, and it overlaps C1. Its one cheap part, letting the jury compare with the project's references (`jury/SKILL.md:10`), should be split off and done now.

5. Corrections

- K2 is wrong for the plans. `base.json:4` already has a `new` key separate from `accent`, and `plans.py:394` reads it. What stops pale buildings is `check_style.py:33-35`, which applies the 3:1 floor to `new` too. So C7 in the plans is a few lines.
- K2 is understated for the isometric. `isometric.py:26-29` uses keys (`new_wall`, `new_wall_shade`, `new_roof`, `new_line`, `floor_line`) that no style.json has. The standard therefore never reaches its buildings: run 10's walls are the script's fallback `#e2554d`, not the standard's `#c8442b` (run-10 `drawing-graphics/style.json`). Only `accent`, `field` and `field_line` got through. The isometric's `summary.md` ("colours from the drawing standard") is only partly true.
- K5, G1 and C8 are overstated as a code cause. `tree_scale_max` is a default that can be overridden from config (`plans.py:49`, `:88`), and the 1,363 street trees exist (run-10 `massing/summary.md`). Split C8 into (a) draw what exists now, with a better crown than a 2.5 m disc, and (b) a planting layer.
- K7's line number is wrong. "Test … hardest on its interior" is at `jury/SKILL.md:21`, not `:12`.
- K8 is overstated for panel-layout. `panel-layout/SKILL.md:17` ("never blow up a diagram or add content of your own to fill it") is about filling leftover space. Dropping it in C5 closes no gap and invites the layout skill to draw. Keep it.
- K6 and G10 blame only the script. The 8° comb is in the run's `massing/config.json` `figure` (orientation 8 on all housing neighbourhoods, from narrative principle 4). The script already allows courtyards, points and per-neighbourhood bearings (`massing.py:69-75`, `:211-221`).
- G10's "no hub building" has a cheaper cause than C9. Run-10 `massing/config.json` lists the bus station with `gfa: null`, "so not built". Massing could build the brief's hub at an assumed, flagged size today.
- G7 matters less for admission than it reads. The brief's required items (run-10 `panel-layout/report.md`, "What the brief asks for") include no section. The winners have one, but it isn't a required item.
- C10 also needs `tests/test_order.py:4` changed (new Opus skill). C4 needs that and `STUDIO.md:49` changed, not only the lead's skill file.
- Merge C1 and C4 into one loop. Fold C7's keys into C6 as its first recipe. Split C15: the `Reads:` fix is an afternoon, the vocabulary is weeks. Split off C4's jury clause.
- Missing change 1: the urban figure. No change touches `structure-plan`, the most expensive skill ($5.44, run-10 `cost.csv`). It decides G10's figure, centres and squares at stops, and the references README even assigns it Nordstern's `structure-plan.jpg`. A jury judges this before any rendering.
- Missing change 2: public ground as a design layer (squares at stops, shared streets, centre plazas, the hub forecourt) from structure-plan or open-space. Without it, C7's accent has little to mark.

6. JSON

```json
{"judge": "A", "ratings": {"C1": {"gap": 2, "effort": 2, "risk": 3, "potential": 5, "rank": 13}, "C2": {"gap": 0, "effort": 1, "risk": 1, "potential": 4, "rank": 12}, "C3": {"gap": 2, "effort": 1, "risk": 2, "potential": 6, "rank": 6}, "C4": {"gap": 2, "effort": 3, "risk": 4, "potential": 4, "rank": 16}, "C5": {"gap": 1, "effort": 1, "risk": 2, "potential": 6, "rank": 3}, "C6": {"gap": 2, "effort": 4, "risk": 3, "potential": 6, "rank": 7}, "C7": {"gap": 3, "effort": 2, "risk": 2, "potential": 8, "rank": 1}, "C8": {"gap": 4, "effort": 3, "risk": 2, "potential": 8, "rank": 2}, "C9": {"gap": 4, "effort": 4, "risk": 4, "potential": 8, "rank": 5}, "C10": {"gap": 3, "effort": 4, "risk": 4, "potential": 6, "rank": 10}, "C11": {"gap": 1, "effort": 3, "risk": 2, "potential": 3, "rank": 18}, "C12": {"gap": 2, "effort": 3, "risk": 2, "potential": 5, "rank": 11}, "C13": {"gap": 3, "effort": 3, "risk": 3, "potential": 6, "rank": 9}, "C14": {"gap": 3, "effort": 2, "risk": 3, "potential": 7, "rank": 4}, "C15": {"gap": 2, "effort": 3, "risk": 2, "potential": 5, "rank": 14}, "C16": {"gap": 2, "effort": 3, "risk": 2, "potential": 4, "rank": 15}, "C17": {"gap": 2, "effort": 4, "risk": 2, "potential": 4, "rank": 17}, "C18": {"gap": 2, "effort": 2, "risk": 2, "potential": 5, "rank": 8}}}
```
