# Closing the gap to the winners

Review of 04.11.2026: what the three Europan 18 winners of our site do that our runs can't, why, and what to change first. Three independent Opus judges ranked the changes.

I didn't open `competition/feedback/`, the runs' `jury/` folders, `docs/`, `plans/` or the environment folder, and I changed no skill.

## What I found

Our panels don't lose on one drawing. They lose on the same three things in every drawing.

1. **The design layers hold too little to draw.** The massing makes only boxes 13 to 25 m deep on a grid. Nothing plants trees except one street tree every 12 m. No skill designs a ground floor, a square or a detail area. The winners' site plans are half tree crowns, full of L, U and courtyard blocks, and their detail areas show ground-floor uses with their areas. No drawing skill can draw what the data doesn't hold.
2. **The look can't be learnt.** Only `drawing-graphics` looks at references, and only for colours. The `style.json` it writes can do little more than recolour, and some scripts ignore even that: run 10's isometric kept the script's own red, not the standard's. The base rule puts the accent on the new buildings. That is why our boards read as "141 red boxes" while all three winners keep their buildings white with a shadow and put the colour on public ground.
3. **Nothing loops back.** No run has ever been compared with anything. Runs 1 to 10 had no reference images at all, and no step puts a drawing next to the reference and sends it back.

On run 11 the winners will be in the project for the first time, but from the code I expect little to change beyond the palette. The changes below have to reach the scripts and the geometry, not only the standard.

The gap kind by kind, with the file and line behind each cause, is in `gaps.md`. The sheets in `evidence/` show it: winners above, ours below, the same kind of drawing at comparable size. Open `evidence/02_site-plan_same-size.jpg` first. It shows the gap in one picture.

## The ranked changes

Combined from the three judges by mean rank (ties by mean potential). Potential runs from 0 to 10, and gap, effort and risk from 1 to 5. The full numbers are in `ranking.csv`, and each judge's verdict is in `judges/`.

| # | Change | A | B | C | Mean rank | Mean potential | Gap | Effort | Risk |
|---|---|---|---|---|---|---|---|---|---|
| 1 | C7 Buildings white with a shadow, the accent on public life | 1 | 2 | 2 | 1.7 | 8.0 | 3.0 | 2.0 | 2.0 |
| 2 | C8 Planting as a design layer | 2 | 4 | 3 | 3.0 | 7.7 | 3.3 | 3.0 | 2.0 |
| 3 | C5 Design intent is not invented data | 3 | 3 | 4 | 3.3 | 6.0 | 1.0 | 1.0 | 2.0 |
| 4 | C2 Measure the gap in every run | 12 | 1 | 1 | 4.7 | 5.7 | 0.0 | 1.0 | 1.0 |
| 5 | C14 Illustrated perspectives | 4 | 5 | 8 | 5.7 | 6.7 | 3.0 | 2.0 | 3.0 |
| 6 | C9 A typology library in the massing | 5 | 7 | 6 | 6.0 | 7.3 | 4.0 | 4.3 | 4.0 |
| 7 | C3 Frame gate before the final layout | 6 | 6 | 9 | 7.0 | 5.3 | 1.7 | 1.7 | 2.0 |
| 8 | C18 Panel composition from the reference boards | 8 | 9 | 5 | 7.3 | 6.0 | 2.7 | 2.3 | 2.3 |
| 9 | C6 Drawing standard v2, a recipe per kind | 7 | 10 | 7 | 8.0 | 5.7 | 2.0 | 4.0 | 3.3 |
| 10 | C15 Concept diagrams after the structure plan, richer vocabulary | 14 | 8 | 10 | 10.7 | 5.3 | 2.0 | 3.0 | 2.0 |
| 11 | C13 The isometric large, on the centre, inhabited | 9 | 13 | 14 | 12.0 | 5.3 | 3.0 | 3.0 | 2.7 |
| 12 | C10 A skill for ground floors and detail areas | 10 | 16 | 13 | 13.0 | 5.0 | 3.0 | 4.0 | 3.7 |
| 13 | C12 Building types as annotated ensembles | 11 | 14 | 16 | 13.7 | 4.3 | 2.0 | 3.0 | 2.0 |
| 14 | C11 A phasing skill | 18 | 11 | 12 | 13.7 | 3.7 | 1.0 | 2.3 | 1.7 |
| 15 | C16 The section as a story strip | 15 | 12 | 15 | 14.0 | 4.3 | 2.0 | 3.0 | 2.0 |
| 16 | C4 Art-direction gate with one revision round | 16 | 17 | 11 | 14.7 | 4.0 | 2.0 | 3.0 | 3.3 |
| 17 | C1 Reference check inside every drawing helper | 13 | 18 | 17 | 16.0 | 4.0 | 2.0 | 2.0 | 3.3 |
| 18 | C17 A thematic plan set in one style | 17 | 15 | 18 | 16.7 | 3.7 | 2.0 | 3.7 | 2.7 |

The judges saw the same 18 changes and the same evidence, but none of my ranking or each other's verdicts. Each had a point of view: A an architect who judges competitions, B an engineer of agent pipelines working to a fixed cost, C the tutor of a studio of 20 students who don't write code. Each read the list in a different order (forward, backward, from the middle), so no change gained from coming first. They agree closely. Rank correlation is 0.66 between A and B, 0.68 between A and C, and 0.88 between B and C.

## The case for each change

Each case uses the judges' words where they agree, plus what they corrected. I checked every correction I pass on here in the code.

**1. C7, buildings white with a shadow, the accent on public life.** All three judges put it in their top two, and they agree on it more than on any other change. It is the largest visible change for the least work: the site plan, detail areas, isometric and building types all change at once. It turns out cheaper than I wrote. `plans.py` already has a separate `new` colour, and the real lock is `check_style.py:33-35`, which demands 3:1 contrast for `new` as well as for the accent, so a pale building fails the check. `tests/test_drawing_graphics.py` has to change with it. A cast shadow already exists in climate (`climate/scripts/common.py`, `shadow_hulls`) and can be copied. The isometric needs its own fix. Its building keys (`new_wall`, `new_roof`, ...) aren't in any `style.json`, so the standard never reaches it: run 10's walls were the script's `#e2554d`, not the standard's `#c8442b` (I counted 330 fills). The risk all three name is that the accent has little public ground to land on, only one 30 m square per centre (`massing.py:52`). See "Missing" below.

**2. C8, planting as a design layer.** Trees are the largest difference by area on every winner's plan, and they show in five kinds of drawing. The judges split it in two. (a) Draw what already exists: run 10's massing holds 1,363 street trees, and the 1:3,000 site plan shows none only because of a default the config can override (`tree_scale_max` in `plans.py:49`, merged at line 88). That is an afternoon. (b) A planting layer that writes trees into parks, courtyards and the kept woods, and keeps them off the kept-free strips, the farmland and the solar park. The plans, isometric and perspective scripts already read `kind: tree`, though the isometric only at 1:1,000 and larger. The risk: trees placed over land the design keeps open would misstate the design.

**3. C5, design intent is not invented data.** On its own it draws nothing (gap 1), but it is an afternoon of text, and the isometric, perspectives, concept diagrams and section can't change without it. Keep "every number has its source" word for word. Allow people, use labels and planting only where a design layer or a sentence of the narrative proposes them, marked as illustrative. All three judges say to keep panel-layout's "never ... add content of your own" (`panel-layout/SKILL.md:17`), because it is about filling space, not about drawings. My C5 was wrong to include it.

**4. C2, measure the gap in every run.** Judges B and C put it first: a script with no model call that puts every drawing beside the reference of its kind at each run's end. Then every pull request can show its before and after as a picture, and a regression shows up one run later instead of three. Judge A put it 12th, because a jury sees no difference (more under "Where the judges disagree"). Two fixes from B: write it to a dot-folder (`.compare/`), because `panels.py scan()` lists every `.jpg` in the version as a drawing and skips only dot-folders (line 191), so the winners' cuts could land on our panels. And give the references their scale, or measure from the A1 boards.

**5. C14, illustrated perspectives.** These are the most visible break in the look, and the fix lives in one script that has a test. The style is already an option (`look` in `--options`). What has to go is the fixed "photorealistic" line in `render.py:125`. All three warn against sending the winners' perspectives to Gemini as a style image, because it would copy their lettering ("SKY BAR", "WUTZLHUB"), and the project forbids the winners' texts on our panels. Describe the style in words instead. The closing line "No text, no labels" (`render.py:39`) clashes with showing the uses on façades, so one of the two has to give way.

**6. C9, a typology library in the massing.** This is the only change to the design itself. It has the highest gap of all (4), but also the highest effort and risk, because nine skills read the massing. The judges start it early, in parallel, behind optional properties, knowing it lands late. Two corrections change its shape. First, the comb of bars was partly the run's choice: run 10's `massing/config.json` set rows at bearing 8° for every neighbourhood, citing narrative principle 4, though the script already offers courtyards and points. So the library needs a rule that each neighbourhood mixes two or three types. Second, the grid placement (`massing.py:224-246`, one angle per piece, a regular pitch) makes the grid as much as the box shapes do. Blocks should follow the structure plan's streets.

**7. C3, a frame gate before the final layout.** Cheap, and it brings back the section, the larger isometric and the uncropped detail area. But B and C showed that a rerun alone wouldn't have helped. The isometric script steps down to 1:10,000 whenever the drawing is wider than its frame (`isometric.py:100-102`), and no true 1:3,000 section fills a 564 by 36 mm frame. The frames were wrong because panel-layout planned them at 23:40, before the structure plan existed. Reframe it in three parts: check the frames in code, send an impossible frame back to panel-layout, and move panel-layout's first run after the structure plan. Also add a check that every planned item was placed, because panel-layout dropped the section despite its own rule "Never drop a planned drawing".

**8. C18, panel composition from the reference boards.** A jury reads the boards as a whole first: one hero drawing across the width, bands above and below, big numbers. Mostly text in a skill that already runs on Opus. It pays off once the drawings are worth enlarging (C7, C8, C3). Showing one number instead of two needs a rule on who owns each number (see "Missing").

**9. C6, drawing standard v2.** The judges call it the right contract (one skill reads the references, the scripts read keys) and say not to build it all at once. First make every script read the keys `style.json` already has, which the isometric doesn't today. Then let C7, C8, C14 and C16 each add their own key. Done that way, C6 shrinks to wiring.

**10. C15, concept diagrams after the structure plan.** Split it. Adding `structure-plan` to its `Reads:` line takes an afternoon and fixes a wrong number that sat on run 10's panels: a 75.6 ha field drawn against the plan's 41.1 ha. The richer vocabulary (people, icons, vignettes, layers) is the slow half and needs C5.

**11. C13, the isometric large, on the centre, inhabited.** A required drawing that the winners make a hero. It becomes cheap once C5, C7 and C8 exist. Without C9 it would zoom in on a centre that has no hub building.

**12. C10, a skill for ground floors and detail areas.** It closes the gap the jury tests hardest ("interior", `jury/SKILL.md:21`), but the judges rate it low for now. An Opus skill placing furniture freely would be the least repeatable output in the studio, cost $1.5 to $3 a run, and need `tests/test_order.py:4` changed. Judge C adds that it designs rather than judges, so by `CLAUDE.md` it belongs on Sonnet. Do it after C9, as rules a script carries out (entrances on the street side, bike stands at entrances, play in courtyards). A cheaper first step exists: run 10 built no hub because the bus station's floor area was left empty in the config (`gfa: null`), so the massing could build the brief's hub at a stated, flagged size now.

**13. C12, building types as annotated ensembles.** A good task for its owner, but with today's massing every ensemble is a group of bars. It waits for C9.

**14. C11, a phasing skill.** It removes the two counts of homes per phase on the panels, but little of it is visible. One line in panel-layout ("the layer that owns a number wins, the other goes to notes") fixes the visible part now.

**15. C16, the section as a story strip.** The winners all have one, and ours was left off. But the brief doesn't require a section (run-10 `panel-layout/report.md`), and the strip needs C8's trees and C6's style first.

**16. C4, an art-direction gate.** About $3 more a run, a new round in the contract (`STUDIO.md`, the lead, `tests/test_order.py`), and fixes the scripts can't act on until C6 to C9 land. All three say to split off its cheap part and do it now: let the jury compare the entry with the project's reference images. That ends the clash between `jury/SKILL.md:10` ("never look up results or other entries") and the project rule that the jury compares a run with the winners.

**17. C1, a reference check inside every drawing helper.** Last but one, and the judges convinced me. Each helper would edit a throwaway copy of a script, so nothing is kept, every run varies more, and nobody reviews the fixes. The biggest differences it would find are geometry, which a drawing helper can't fix honestly. Keep one line of it ("look at the references of your kind before you draw, and name the largest differences in `summary.md`") and let C2 carry the loop: sheet, issue, pull request to the script, between runs instead of inside one.

**18. C17, a thematic plan set.** A new skill that redraws the maps of three other skills. One frame size and scale for those maps (C18) plus a diagram key (C6) give most of winner 3's row of four.

## Where the judges disagree

- **C2, measuring the gap.** A ranks it 12th, B and C 1st, the widest split of all. It comes from the point of view, not the facts. A asks what a jury sees, and a sheet the jury never sees closes nothing. B asks what makes runs reliable, and C asks what teaches 20 students. For both of them, a sheet that every pull request can show is the base everything else is checked against. I side with B and C on the order: it costs an afternoon and no model call, and it makes every later change checkable.
- **C10, ground floors.** A puts it 10th: rounds 2 and 3 of a jury are decided on the interior. B puts it 16th, as the least repeatable output per dollar. C puts it 13th, a good student skill but heavy. All agree it comes after C9.
- **C15, concept diagrams.** A puts it 14th, B 8th, C 10th. B and C weigh the one-line `Reads:` fix of a wrong number, while A weighs the pictograms' small share of a board.
- **C11, phasing.** A puts it last, because a jury reads the double count as sloppy, not fatal. B and C put it 11th and 12th, because it feeds the panels and the phase plan.
- **C4, art direction.** C puts it highest, 11th, as a part a student can own with one bounded round. A and B put it 16th and 17th, for cost and overlap.

## Corrections the judges made

I checked each in the code. I left `gaps.md` and `changes.md` as the judges saw them, so their line references stay valid, and I list the corrections here instead.

- **K1 is partly overstated.** The lead passes the project's rules to every helper, and `CLAUDE.md` now says a drawing skill looks at the winners' drawing of its kind first. So on run 11 helpers may look. What holds is that they can't use much of what they see. Also, the reference table and the `CLAUDE.md` change are uncommitted on `runs-in-git`, and `winners/` isn't in git.
- **K2 is understated.** The isometric's own style keys mean the standard never reaches its buildings (run 10's walls: the script's red). The standard also promised things no script draws, such as the field line "on every plan", and the jury then weighed "no field line on the site plan".
- **K3: I quoted the base only in part.** `base.md:16` reads "usually the new buildings or the idea's layer", and the narrative may move the accent. The hard lock is `check_style.py:33-35`.
- **K5: the tree limit is a config default,** not a fixed limit. The real cause is that there is no tree data beyond the street trees.
- **K6 and G10 blamed only the script.** The run's config chose the comb, and the grid placement makes it as much as the box shapes do.
- **K7's line is 21, not 12.**
- **G1 is overstated.** Not all 141 buildings are 13 by 30 to 50 m. The 27 halls are 25 m deep, and the school, the pool and the two 10-storey landmarks differ.
- **G6: Judge C couldn't confirm the run-9 claim.** It wasn't in that run's `concept-diagrams/summary.md`. My source was run 9's `README.md`, "Open problems": "the phase pictogram (drawn before the structure plan) puts phase 1 on the wrong side of the railway".
- **G7 matters less for admission.** The brief's required items don't include a section.
- **C3, C5, C14 and C2 are reframed** as in their cases above.

## What the judges found missing

- **The urban figure.** No change touches `structure-plan`, the costliest skill ($5.44, 26 % of run 10) and the one that decides the figure, the centres and the squares at the stops. The references README even gives it winner 3's structure plan. A first step of one line: give each centre a size by its level, instead of massing's fixed 30 m square.
- **Public ground as a design layer.** Squares at the stops, shared streets, the centre's plaza, the hub's forecourt. Without them C7's accent has almost nothing to mark.
- **An owner for `plans`.** It draws the site plan and the detail areas, the main drawings of the boards, and C7, C8 and C10 all land in `plans.py`. `STUDIO.md` lists it as "open".
- **Who owns each number.** Massing for homes, open-space for sealing, until C11 exists. The panels then show one number, not two.
- **Panel-layout's first run after the structure plan,** so its frames fit the design (see C3).
- **A cost ceiling the lead checks.** C4, C10 and image reads could pass $30 without anyone noticing.

## An order of work

The combined ranking with the judges' dependencies and splits. It is a suggestion, not a plan anyone has agreed to.

**Now: an afternoon each, mostly one or two files.**

- C2 into `.compare/`.
- C5, keeping panel-layout's line.
- C7, with `check_style.py`, its test and the isometric's keys.
- C8a: draw the street trees at 1:3,000, with a better crown.
- C15's `Reads:` line.
- The jury may compare with the references (split from C4).
- The centre size by level (missing 1).
- The rule on who owns a number (missing 4).

**Next: days.**

- C8b: the planting layer.
- C14: the style in words, and a decision on the text line.
- C3 reframed, with panel-layout's first run moved.
- C18.
- C6 key by key.

**Start now, lands late: weeks.**

- C9 with a mixing rule and blocks along the structure plan's streets.
- Public ground (missing 2), in structure-plan or open-space.

**After C9.** C13, C12, then C10 as scripted rules on Sonnet, and C16.

**Hold.** C11 until the number rule falls short, C4's gate until the scripts can act on fixes, C17 until C18 and C6 are done. Drop C1 into C2.

## My own ranking against the judges

I wrote my ranking before any judge replied (`my-reading.md`). I agreed on the top three (C7, C8, C5, in another order). I was wrong in two places:

- **C1.** I ranked it 7th. The judges showed that its fixes are lost with each run's copy of the script, a fact I had written into C1 myself without weighing it.
- **C2.** I ranked it 9th. B and C convinced me it belongs first in the order, because it costs nothing per run.

I also had C10 at 5th, higher than any judge. I still think the interior is where our runs lose round 2, but I accept that a free-placing Opus skill on today's slabs is the wrong first step.

## What the judges cost

The judges used 680,671 tokens in all: A 214,080, B 220,949, C 245,642. They made 125 tool calls and took 7 to 10 minutes each. That is inside the 0.5 to 0.75 million tokens I expected at the start. In dollars that's my rough estimate of $10 to $25 at API prices, not a measured figure. This session's own reading, sheets and writing come on top.

## Files

- `report.md`: this file.
- `gaps.md`: steps 1 and 2. The gaps G1 to G11 by kind of drawing, and the causes K1 to K18 with file and line, as the judges saw them.
- `changes.md`: step 3. The 18 changes with their evidence and starting points, as the judges saw them.
- `ranking.csv`: every judge's rank and potential, and the combined order.
- `judges/brief.md`: what each judge was asked.
- `judges/judge-A.md`, `judge-B.md`, `judge-C.md`: the three verdicts, word for word.
- `my-reading.md`: my weighting of the gaps and my own ranking, written before the judges replied and kept from them.
- `evidence/`: nine comparison sheets. They hold cuts of the winners' boards, so `.gitignore` keeps them out of git, like `references/winners/`.
