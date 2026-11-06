# Judge B: pipeline engineer

Opus, independent. Read the changes in reverse order, C18 to C1. Saved word for word from its reply.

## 1. Ratings

| id | gap | effort | risk | potential | rank | one-line reason |
|---|---|---|---|---|---|---|
| C1 | 2 | 2 | 4 | 3 | 18 | A loop inside the run where Sonnet edits throwaway copies of scripts. Each run varies more, nothing is kept, and its comparison sheets can end up on our panels. |
| C2 | 0 | 1 | 1 | 6 | 1 | A free, scripted before/after sheet for every run. Every later change needs it as its regression check. |
| C3 | 1 | 2 | 2 | 5 | 6 | A cheap scripted check. But a rerun can't fix frames that were planned before the design existed, so the gate must also be able to send a frame back. |
| C4 | 2 | 3 | 3 | 3 | 17 | About $3 more per run and a new round in the contract, for fixes the scripts can't yet carry out. Its jury part should be split off and done early. |
| C5 | 1 | 1 | 2 | 6 | 3 | Five rule lines that four later changes need. On its own it changes nothing that gets drawn. |
| C6 | 2 | 4 | 4 | 5 | 10 | The right contract: one skill reads the references and the scripts read keys. But it touches eight scripts with eight owners, so do it after C7, C8 and C14 show which keys matter. |
| C7 | 3 | 2 | 2 | 8 | 2 | The most visible change per hour of work: pale buildings with shadows and the accent on public ground, all in scripted code. |
| C8 | 3 | 3 | 2 | 7 | 4 | One scripted tree layer that three drawing scripts can already read. Trees are in every winner drawing. |
| C9 | 4 | 4 | 4 | 7 | 7 | The only change that alters the design itself. It is long and risky, so start it early and in parallel, behind optional properties. |
| C10 | 3 | 4 | 4 | 4 | 16 | It closes the jury's "interior" gap. But an Opus model placing furniture freely gives the least repeatable output in the studio, and costs $2 to $3 per run. |
| C11 | 1 | 2 | 2 | 4 | 11 | Ends the double counts on the panels and feeds C17 and C18. Little of it is visible. |
| C12 | 2 | 3 | 2 | 4 | 14 | A clear gain on one drawing. But with today's massing every ensemble is made of bars. |
| C13 | 3 | 3 | 3 | 5 | 13 | The winners use it as a hero drawing. Ours would zoom in on a centre that has no hub yet, so C5, C7, C8 and C9 come first. |
| C14 | 3 | 2 | 3 | 7 | 5 | One script with a test, and the look is already an option. The risk is Gemini copying the winners' lettering. |
| C15 | 2 | 3 | 2 | 6 | 8 | Changing its `Reads:` line takes an afternoon and fixes a wrong number on the panels. The new vocabulary is the slow part. |
| C16 | 2 | 3 | 2 | 5 | 12 | Brings back the missing section as the strip every winner has. Its trees need C8. |
| C17 | 2 | 3 | 3 | 4 | 15 | A new skill with no owner that redraws three design skills' maps. Worth it only after C11 and C6. |
| C18 | 3 | 3 | 3 | 6 | 9 | Shapes the boards' first impression. It needs C3, C11 and a hero drawing worth enlarging. |

## 2. Dependencies

- C2 -> all: gives every PR a before/after sheet. Land it before C7, C8 and C9. It also makes C1 largely unnecessary: the loop belongs in development (sheet, then issue, then a PR to the script), not inside a run.
- C5 -> C13, C14, C15, C16, C10: these draw people, use labels, notes on the line and planting intent. Without C5, each one fights `STUDIO.md:63` and its own "no labels or people" line.
- C7 -> C12, C13: pale volumes and public ground in the accent are what both drawings build on.
- C7 before C6: C7 adds the few keys first (building fill, outline, shadow, public-ground tone) and C6 then generalises them. Done in parallel, they collide in `base.json`, `check_style.py` and the scripts' style dicts.
- C8 -> C13, C16, C14, C12: one tree layer feeds the isometric, the section strip, the perspective's base view (so Gemini keeps the trees in place) and the ensembles.
- C9 -> C12, C13, C10, C14: those drawings show parts, roofs, a hub and ground-floor uses. Without C9, C12 draws bars, C13 zooms in on a 30 m square, C10 designs ground floors for slabs and C14 has no hub to stage.
- C11 -> C17, C18: one owner of homes per phase gives the phase plan, and the panels can show one count.
- C3 -> C18: drawings must fit their frames before a hero layout is worth planning. C3 itself only works if panel-layout's first run moves after structure-plan, or if the gate can send a frame back (see Corrections).
- C6 -> C14, C16, C17: render, section and diagram styles. C14 can start without C6 through its existing `look` option.
- C15: the `Reads:` change needs nothing; the new vocabulary needs C5.
- C4 overlaps C1 and would make it unnecessary. Neither is worth much before C6 to C9 give the scripts something to act on. C4 and C10 compete for the roughly $9 left under $30 (run 10 cost $21.01).
- C10 comes after C9. C10 -> the detail areas in plans (G2).
- C17 comes after C11 and C6. It overlaps the maps of mobility, open-space and climate, which stay as check plans.
- C18 gains from C16 (the bottom band) and C17 (the diagram band).
- Prerequisites in short: C12 needs C9 and C7. C13 needs C5, C7, C8 and C9. C16 needs C8 and C5.

## 3. Top five

**C2 (rank 1).** No run has ever been compared with anything. The evidence sheets were made by hand, once. A Pillow script with no model call costs nothing per run, and it turns that one-off into a check that runs every time. Each PR for C7 to C18 can then show its before and after, and a regression shows up the next run instead of three runs later. What convinced me is `evidence/02_site-plan_same-size.jpg`: a 150 mm patch of each board at the same print size makes the gap readable in seconds, and that is the format to automate. The lead already runs scripts at the end (`competition-proposal/SKILL.md:21`), and `preview.py` is 103 lines. What could go wrong:
- It closes no gap by itself, and a sheet nobody opens changes nothing.
- "Same print size" needs each reference's scale. The cut files carry none, so the script must work from the boards (A1, so the pixels per mm are known) or the references table needs a scale column.
- If `compare/` sits as a normal folder in the version, a variant run copies it (`SKILL.md:13`) and `panels.py scan()` lists its JPGs as drawings (lines 191 to 206, `DRAWING_EXT` includes .jpg). Call it `.compare/`, since scan skips folders whose names start with a dot (line 191).

**C7 (rank 2).** This is the cheapest change that turns four drawings from "141 red boxes" into a district. It is scripted, repeatable code:
- a shadow pass in `plans.py`: each footprint moved by height times a factor, minus the footprint, drawn under the buildings, about 30 lines of shapely;
- pale walls in the isometric;
- no red face in building types.

The evidence is `02_site-plan_same-size.jpg` and `05_isometric.jpg`. All three winners draw white buildings with a dark outline and a shadow, and put pink on public ground. In the code, `plans.py:371-376` fills every new building with `S['new']`, and `check_style.py:33` requires `new` to have 3:1 contrast on paper. That forbids pale buildings, so even with references, drawing-graphics on run 11 cannot make them white. `isometric.py:26-30` hard-codes red walls under keys (`new_wall`, `new_wall_shade`, `new_roof`) that `style.json` doesn't have, so the standard never colours the isometric's buildings at all. There is public ground to colour: the squares in the massing (`massing.py:716-718`), community grounds typed `square` (`massing.py:457, 488`) and mobility's shared streets. What could go wrong:
- Once the buildings are pale, the comb of parallel bars (G10) reads more clearly. The drawing gets better looking, the design doesn't.
- With only 30 m squares to mark, the accent has little to hold until C9 or C10.
- `base.md:16` sets every entry's default, so step 2 of drawing-graphics must still let a narrative choose another layer.
- `check_style.py` and `test_drawing_graphics.py:37-40` have to change together.

**C5 (rank 3).** It is an afternoon of text in five files, and C13, C14, C15, C16 and C10 can't be written without it. Doing it once, first, stops four PRs from each loosening the rule in its own way. The lines are real: `isometric/SKILL.md:14` ("No labels, arrows or people", "only the trees the data has"), `concept-diagrams/SKILL.md:10`, `panel-layout/SKILL.md:17` and `STUDIO.md:63`. The images show what they block: in `05_isometric.jpg` winner 2 labels "mobility hub", "supermarket" and "library", and in `06_perspectives.jpg` people act out the story. What could go wrong:
- On its own the scripts draw the same.
- Looser wording is read by an Opus panel-layout and a Sonnet concept-diagrams as licence to invent uses or numbers. Keep "every number has a source" word for word, and allow illustrative content only when it comes from a named design layer or narrative line, marked as illustrative.
- The jury must then not count it as invented.

**C8 (rank 4).** Trees are in every winner drawing at every scale, and in none of ours at 1:3,000. A planting step written as a script writes tree points once, and three drawing scripts already read `kind: tree`: `plans.py:380`, `isometric.py:176-178` and `perspective/scripts/scene.py:397`. So one data layer appears the same way in plan, isometric and perspective, which is the kind of reliability I want. It runs on Sonnet for about $0.2. The evidence is in `02`, `03_detail-areas.jpg` and `05`: avenues, courtyard trees and woods drawn as canopy against our dots along streets only. In the code, `massing.py:735-747` makes street trees only and `open_space.py` writes no trees. What could go wrong:
- Where it lives is an open choice. A new skill adds a step to the order and needs an owner. A step inside open-space writes open-space's own file (a skill never edits another's), so the readers that take trees from `massing.geojson` must learn a second file.
- `section.py:33` assumes tree heights by land use and reads no tree points.
- Trees over the farmed field or the solar park would misstate the design. Run 10's narrative already flagged open-space laying meadow over farmland (`log.md:32`).

**C14 (rank 5).** The perspectives catch the eye at the top of most winner boards, and ours look like a different project. The fix is mostly in one 265-line script that already has a test. In `06_perspectives.jpg` our renders add a tractor, a field robot, crenellations and domes on grey concrete. `render.py:125` writes "photorealistic" into every prompt. The look itself is already an option (the `look` key in `--options`, `perspective/SKILL.md:13`; `DEFAULTS` at `render.py:21-28`), so the style part is small. What could go wrong:
- Sending the winners' perspectives as a style image invites Gemini to copy their lettering ("SKY BAR", "MOBILITY HUB", "WUTZLHUB"), and `CLAUDE.md` forbids that on our panels. Describe the style in words, or crop the text out of the images first.
- `render.py:39` ends every prompt with "No text, no labels", which contradicts C14's signs of the uses.
- Illustrated styles drift from the geometry more than photoreal ones, so the "look once beside its base" check must stay.
- A story scene at the centre will show that there is no hub building (`log.md:27`) until C9.

## 4. Bottom three

**C1 (rank 18).** The loop sits in the wrong place:
- Each drawing helper, on Sonnet, edits its own copy of a script up to three times to look more like the winners (`studio-helper.md:14`). The edits are untested, differ every run and are thrown away; changes.md says so itself in C1's Facts. It adds variance, not reliability.
- The five largest differences it finds will be geometry: combs of bars, no trees, no hub. A drawing helper can't fix those honestly, and the temptation is to draw trees or courtyards the data doesn't hold.
- Its sheets go into the skill's folder. `panels.py scan()` lists them as drawings (lines 197 to 206), and panel-layout fills spare space "with drawings from the folder" (`SKILL.md:17`), so cuts of the winners' boards can land on our panels.
- It contradicts `STUDIO.md:67` ("Look at a drawing once or twice").

C2 plus PRs to the scripts does the same job once, for everyone.

**C4 (rank 17).**
- One Opus pass plus one rerun of each drawing skill it names costs about $3 a run. For scale, run 10's jury cost $1.61 on Opus and all six drawing skills $1.46 (`cost.csv`).
- It breaks "the lead never adds a round" (`STUDIO.md:49`, `competition-proposal/SKILL.md:19`) and `tests/test_order.py:4`.
- Until C6 to C9 land, a fix like "trees at 1:3,000 in every park" has nothing to work with, and the rerun again edits only a copy of a script that is thrown away after the run.
- It overlaps C1.

Its one cheap and valuable part should be split off and done with C2: letting the jury compare the entry with the project's reference images, which resolves the clash between `jury/SKILL.md:10` and `CLAUDE.md`.

**C10 (rank 16).** Its gap is real, but it has the worst reliability per dollar:
- An Opus skill that places entrances, furniture, bus bays and play equipment as free GeoJSON gives the least repeatable output in the studio.
- It adds about $1.5 to $3 per run (massing on Opus cost $1.58, structure-plan $5.44).
- It brings a new data model that plans must learn, and one more Opus line in `test_order.py:4`.
- On today's boxes, which have no parts and no ground floor, it would design ground floors for 13 m slabs.

Do it after C9, and as a rule-based script the model configures rather than draws: entrances on the street side, bike stands at entrances, play in courtyards.

## 5. Corrections

**Claims in gaps.md:**
- **K3 (`gaps.md:83`) and K2 (`gaps.md:82`).** `base.md:16` actually reads "usually the new buildings or the idea's layer", and `drawing-graphics/SKILL.md:13` already lets the narrative move the accent. The real locks are `check_style.py:33`, which demands 3:1 contrast for `new`, and `isometric.py:26-30`, whose own keys mean the standard never reaches the isometric's buildings. K2 is understated. Run 10's standard said the accent marks the field line "on every plan" (run-10 `drawing-graphics/summary.md`, line 2), no script draws a field line, and the jury weighed "no field line on the site plan" (`log.md:36`). The standard writes intentions that no script carries out.
- **K5 (`gaps.md:85`) and C8.** The 1:2,000 tree limit is a default that `config.json` overrides (`plans.py:49` and 88). "Drop the limit" is a config value; the real cause is that there is no tree data.
- **K7 (`gaps.md:87`).** "Test hardest on its interior" is `jury/SKILL.md:21`, not line 12.

**Claims in changes.md:**
- **C3 (`changes.md:33-35`).** A rerun with the frame in the request won't fix the two worst cases:
  - `isometric.py:100-102` steps to the next usual scale whenever the drawing is wider than its width, so a 222 mm frame gives 1:10,000 again.
  - No true 1:3,000 cut fills a 564 by 36 mm frame.
  - The frames were planned at 23:40, before the structure plan existed (`log.md:9`).

  Reframe C3 so the gate can send an infeasible frame back to panel-layout, and move panel-layout's first run after structure-plan. In run 10 that first run took 6 minutes, about as long as massing, which ran right after the structure plan anyway, so the delay would be small. Also, panel-layout dropped the section even though its own rule says "Never drop a planned drawing" (`panel-layout/SKILL.md:15`). A check in `panels.py` that every planned item was placed belongs in C3.
- **C14 (`changes.md:149`).** Only `render.py:125` is fixed; the look is already an option. C14 also has to change `render.py:39`. The style-image risk is above.
- **C1 and C2 (`changes.md:11`, `:23`).** Comparison sheets inside the version get scanned by panel-layout (`panels.py:191-206`), and variant runs copy the version. Use a dot-folder.
- **C9 (`changes.md:97-103`).** The comb comes from the grid placement (`massing.py:224-246`: one angle per piece, blocks at a regular pitch), not only from `block_buildings()` (174 to 188). A library of block types on the same grid will still read as a grid. C9 should say whether blocks follow the structure plan's streets; that is most of its effort.
- **Tests.** `tests/test_order.py:4` hard-codes which skills run on Opus, so C4 and C10 must change it. `test_drawing_graphics.py:37-40` tests the accent's contrast, so C7 must change it.

**Split:**
- C4: the jury comparison (cheap, do it early with C2) and the art-direction gate.
- C15: the `Reads:` line (an afternoon; it fixes the 75.6 ha field drawn against 41.1 ha, `log.md:14`, still on run 10's panels) and the vocabulary.
- C6: now, make every script map the base keys (the isometric ignores them today) and add C7's few keys; later, the recipe per kind of drawing.

**Merge:** C1 into C2. The loop runs in development, between runs, not inside one.

**Missing:**
- Move panel-layout's first run after structure-plan (see C3).
- A cost ceiling the lead checks. C4, C10 and image reads can pass $30 without anyone noticing.
- Nothing addresses structure-plan, the costliest skill ($5.44, 26 % of run 10) and the place where centres get their size. Centres are a 30 m square because massing's `square` default is 30 (`massing.py:52`). A size per centre level, taken from the structure plan, is a one-line start on G10's "designed centres".

## 6. JSON

```json
{"judge": "B", "ratings": {"C1": {"gap": 2, "effort": 2, "risk": 4, "potential": 3, "rank": 18}, "C2": {"gap": 0, "effort": 1, "risk": 1, "potential": 6, "rank": 1}, "C3": {"gap": 1, "effort": 2, "risk": 2, "potential": 5, "rank": 6}, "C4": {"gap": 2, "effort": 3, "risk": 3, "potential": 3, "rank": 17}, "C5": {"gap": 1, "effort": 1, "risk": 2, "potential": 6, "rank": 3}, "C6": {"gap": 2, "effort": 4, "risk": 4, "potential": 5, "rank": 10}, "C7": {"gap": 3, "effort": 2, "risk": 2, "potential": 8, "rank": 2}, "C8": {"gap": 3, "effort": 3, "risk": 2, "potential": 7, "rank": 4}, "C9": {"gap": 4, "effort": 4, "risk": 4, "potential": 7, "rank": 7}, "C10": {"gap": 3, "effort": 4, "risk": 4, "potential": 4, "rank": 16}, "C11": {"gap": 1, "effort": 2, "risk": 2, "potential": 4, "rank": 11}, "C12": {"gap": 2, "effort": 3, "risk": 2, "potential": 4, "rank": 14}, "C13": {"gap": 3, "effort": 3, "risk": 3, "potential": 5, "rank": 13}, "C14": {"gap": 3, "effort": 2, "risk": 3, "potential": 7, "rank": 5}, "C15": {"gap": 2, "effort": 3, "risk": 2, "potential": 6, "rank": 8}, "C16": {"gap": 2, "effort": 3, "risk": 2, "potential": 5, "rank": 12}, "C17": {"gap": 2, "effort": 3, "risk": 3, "potential": 4, "rank": 15}, "C18": {"gap": 3, "effort": 3, "risk": 3, "potential": 6, "rank": 9}}}
```
