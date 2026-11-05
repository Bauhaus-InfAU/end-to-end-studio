# Judge C: studio tutor

Opus, independent. Read the changes from C10 to C18, then C1 to C9. Saved word for word from its reply.

## 1. Ratings

| id | gap | effort | risk | potential | rank | one-line reason |
|---|---|---|---|---|---|---|
| C1 | 2 | 2 | 3 | 4 | 17 | The loop runs inside each helper, so its fixes are lost with each run's script copy. It clashes with STUDIO.md:21 and :67, and it does the copying that the students should learn to do. |
| C2 | 0 | 1 | 1 | 7 | 1 | The cheapest enabler. Every run puts each drawing beside the winners' drawing of the same kind, so every student and every PR can see whether it got closer. |
| C3 | 2 | 2 | 2 | 5 | 9 | The board failures are real, but a second run alone would not fix them. Drawings should be drawn at their frame's scale and cropped by the frame. |
| C4 | 2 | 3 | 3 | 5 | 11 | An art director a student can own, with one bounded round. It only helps once the scripts can act on its fixes. The jury line is a separate quick fix. |
| C5 | 1 | 1 | 2 | 6 | 4 | Only text changes. It unlocks people, use labels and scenes for C13 to C16, and it teaches the difference between a fact and a proposal. |
| C6 | 2 | 4 | 3 | 6 | 7 | It multiplies every other change: today the standard can't even reach the isometric's walls. It is big and touches many skills, so build it key by key. |
| C7 | 3 | 2 | 2 | 8 | 2 | One rule and a shadow pass turn the main drawing from "141 red boxes" into a district with public ground. |
| C8 | 3 | 3 | 2 | 8 | 3 | Trees are the most visible difference in five kinds of drawing, and planting is a clean new design layer a student can own. |
| C9 | 4 | 5 | 4 | 7 | 6 | The biggest gap, because it is the design itself. It means weeks in an 823-line generator that every other skill reads. Start it now; it lands late. |
| C10 | 3 | 4 | 3 | 5 | 13 | It answers the jury's test of the interior and is a good new skill for a student. It is heavy and should not run on Opus. |
| C11 | 1 | 2 | 1 | 4 | 12 | A small open slot. It removes a contradiction printed on the panels and feeds C17 and C18, but adds little you can see. |
| C12 | 2 | 3 | 2 | 4 | 16 | It mostly waits for C9: with today's massing every ensemble is a group of bars. |
| C13 | 3 | 3 | 2 | 5 | 14 | The winners make the isometric a main drawing. It becomes cheap once C5, C7 and C8 exist. |
| C14 | 3 | 2 | 3 | 6 | 8 | One hard-coded prompt line makes our views look like another project. Cheap, but a winner's image sent as a style example may get copied. |
| C15 | 2 | 3 | 2 | 5 | 10 | Moving it after the structure plan fixes a wrong drawing (75.6 ha instead of 41.1 ha) with one line. The richer vocabulary is the slow half. |
| C16 | 2 | 3 | 2 | 4 | 15 | The section strip runs along the bottom of the winners' boards, and ours was left off. It waits for C8's trees and C6's style. |
| C17 | 2 | 4 | 3 | 3 | 18 | A new skill that copies the map code of three skills with three owners. Shared frames, one scale and one style get most of the effect. |
| C18 | 3 | 2 | 2 | 7 | 5 | The boards as a whole are what a jury reads first. It is mostly text in a skill that already runs on Opus. |

## 2. Dependencies

- C2 -> all: it is the measure every change is judged by. C1 and C4 reuse its `side_by_side.py`.
- C5 -> C13, C14, C15, C16: people, use labels, scenes and notes on the section line need the rule first.
- C7 -> C12, C13: white volumes and the accent on public ground are the new look for the isometric and the building types.
- C7, C8 -> C6: they are C6's first two keys (shadow, tree). Doing them first makes C6 smaller, and C6 then mostly wires up the rest.
- C8 -> C13, C14, C16: the same trees appear in the isometric, the base views and the section. C8 also makes C5's change to "only the trees the data has" unnecessary, because the trees become data.
- C9 -> C10, C12, C13, C14: building parts, roofs and ground-floor uses. C12 means little without C9.
- C6 -> C1, C4, C12 to C17: an art director's or a helper's fixes need style keys to land in.
- C3 -> C18: main-drawing frames only work if the drawings fill them.
- C11 -> C17, C18: the phase plan, and one count per figure on the panels.
- C10 -> C13, C18: centre uses to label, and a detail area that deserves a main frame.
- C18 -> C13, C16: it gives the close-up isometric and the section strip their frames.
- C1 and C4: the same loop twice. Do one, and I'd take C4, later.
- C3 and C4: both open the lead's "No other skill ever runs twice" (competition-proposal/SKILL.md:19). Make one revision round serve both.
- C17 and C6 + C18: C17 is largely unnecessary once the existing maps share one frame, one scale and one diagram style.
- C15 needs `structure-plan` in its `Reads:`. That makes no cycle, since structure-plan reads narrative, climate and programme.

## 3. Top five

**C2, measure the gap in every run (rank 1).** It works like a crit wall. For about 100 lines of Pillow code (changes.md:11) and a link in `preview.py` (103 lines, checked), each of the 20 students sees their own drawing beside the winners' drawing every run. Every PR can then show its effect as a picture instead of a claim. This review's own `evidence/02_site-plan_same-size.jpg` convinced me more than any text in it, and it was made exactly this way. Today nothing in a run compares anything: run-10 `version.md` says "Reference images: none", and the jury runs last with nothing reading its report (`log.md` 00:36, K17). The root `.gitignore` already lets only logs, costs, summaries, jury reports and panel PNGs out of the run folders, so sheets holding the winners' cuts stay private by default. Share them on the course board instead. What could go wrong: "the same print size" needs each drawing's size in mm, and perspectives have no scale. Students may also read a sheet as a target and copy the winners' content rather than their craft, so the tutor has to frame it as a crit.

**C7, buildings white with a shadow, the accent on public life (rank 2).** This is the largest visible change for the least work. In `02_site-plan_same-size.jpg` all three winners draw white volumes with a thin dark outline and a cast shadow, with pink or rose on squares and shared streets. Ours shows red slabs with white numbers. The causes are plain text I checked: `base.md:16` ("usually the new buildings"), `plans/SKILL.md:11` ("One thing dominates each plan: the new buildings") and `isometric/SKILL.md:14`. In code, `plans.py:371-376` fills every new building with `S['new']`. A grep finds "shadow" only in climate, and `climate/scripts/common.py:165 shadow_hulls` is a 9-line cast shadow that can be copied. Ownership works well as a studio exercise: the tutor changes the base, and three owners change one line each. What could go wrong: `check_style.py:33-35` also checks `new` against 3:1 contrast, so pale buildings fail until that check changes. Public ground is thin today (one 30 m square per centre, `massing.py` DEFAULTS `square: 30.0`), so the accent may nearly vanish until C9 or C10 add squares. And `plans`, which draws this, has no owner (STUDIO.md:90).

**C8, planting as a design layer (rank 3).** Trees are the single largest difference across the site plan, the detail areas, the isometric and the section. The winners' patches in `02` are mostly tree crowns. Ours has none at 1:3,000, `03_detail-areas.jpg` shows only street-tree dots, and `05_isometric.jpg` shows thousands of trees against none. I checked the causes. `massing.py:735-745` plants only street trees: run 10 had 1,363 of them, invisible at 1:3,000 because `plans.py:49` has `tree_scale_max: 2000`. `open_space.py` writes no `tree` kind (grep). `structure-plan/SKILL.md:10` leaves "planting" to "the skills that follow", and none does. A `trees.geojson` that every drawing reads is exactly the kind of layer `design/TOPIC.md:9` invites, so a new student or the open-space owner can own it and keep it working. What could go wrong: trees placed on kept-free strips (the 150 kV line, the canal) unless it reads `keep-free.geojson`. Crowns can hide buildings at 1:3,000. `isometric.py` draws trees only when the scale is 1:1,000 or larger (`LARGE`, line 103 and its loop), so the readers must change too.

**C5, design intent is not invented data (rank 4).** It costs an afternoon of text and unlocks C13 to C16. It also teaches something architects already know: a drawing shows a proposal, and a fact needs a source. The lines that read "never invent data" as "show nothing" are where changes.md says: `STUDIO.md:63`, `isometric/SKILL.md:14` ("No labels, arrows or people") and `concept-diagrams/SKILL.md:10`. The winners' drawings in `05` and `06` are full of use labels and people doing what the story says. What could go wrong: the same freedom that brings people also brings the inventions we already suffer. `06_perspectives.jpg` and run-10 `perspective/summary.md` show a tractor and a field robot, and run 8 had crenellations. Every intent must come from a design layer or a sentence of the narrative and be marked as illustrative. I would keep panel-layout's "never ... add content of your own" (see Corrections).

**C18, panel composition learnt from the boards (rank 5).** A jury judges the boards as a whole first. `01_boards.jpg` shows the gap at a glance: the winners put one main drawing across the full width with bands above and below, while ours is a grid with white gaps and sourced tables. The rules behind it are in `panel-layout/SKILL.md:15` ("show both"), `:17` and `base.md:47` ("Empty space is allowed"). `competition/references/README.md:21` says panel-layout should look at the boards, but the skill never mentions references. Run-10 `panel-layout/summary.md` confirms it printed two versions of sealing and of homes per phase, left the section off and cropped detail area 2 by 52 %. One student owns it, and it already runs on Opus. What could go wrong: the first run plans frames before any drawing exists (`log.md` 23:40), so main frames still misfit without C3. Showing "the owner's number" needs a rule on who owns each number before C11 exists. A one-line source must stay under each big number.

## 4. Bottom three

- **C17 (18).** It is a new skill that takes the map code out of `mobility.py` (924 lines), `open_space.py` and climate's `draw.py` (649 lines), owned by three students, and draws again what they already draw. The gap it closes (G8) is modest. Giving the existing maps one frame size and scale in `layout.json` (C18) and a diagram key (C6) gets most of winner 3's "row of four" effect without a fourth owner and duplicated code.
- **C1 (17).** It automates the very loop the students should own. The helper's fixes stay in a per-run copy (`studio-helper.md:14`), and `.gitignore` keeps run scripts out of git, so the fixes reach neither the repo nor the student. It contradicts `STUDIO.md:21` ("Code it needs in every run goes in its scripts/, so no run writes it again") as well as `:67` and `studio-helper.md:15`. Three rounds in each of eight drawing skills add cost. Sonnet editing scripts until they match a picture is how drawings start to misstate the design. Keep one line of it: "look at the references of your kind before drawing, and name the largest differences in summary.md".
- **C12 (16).** It waits for C9. With today's `TYPES`/`TYPOLOGY` and `block_buildings()` (`massing.py:59-75, 173-187`), every block is a set of bars on a grid, so an "ensemble" is three bars with trees. Building types are one small row on panel 3. It is a good task for its owner later in the semester, once C9 has landed.

## 5. Corrections

- **gaps.md:7 and K1 (line 81) are partly overstated.** The lead passes the project's rules to every helper (`competition-proposal/SKILL.md:23`), and `CLAUDE.md` now says a drawing skill looks at the winners' drawing of the same kind first. So run-11 helpers may look. What holds is that they can't use much of it (K2, `studio-helper.md:14-15`). Also, `references/README.md`'s table and the `CLAUDE.md` change are uncommitted on `runs-in-git`, and `winners/` isn't in git. "This repo already has one" (changes.md:11) is true only on this computer.
- **K2 (line 82) is understated.** `isometric.py:26-31` keeps its own keys (`new_wall`, `new_roof`, `new_line`, `floor_line`), which `base.json` doesn't have. So `STYLE.update(style.json)` leaves the new buildings in the script's red whatever the standard says. Run 10's straw fields came through only because drawing-graphics added a `field` key the script happens to share. The perspective also used "script tones ... not standard.md" (run-10 `perspective/summary.md`).
- **K5 (line 85) and C8 (changes.md:87).** `tree_scale_max` is a default that `config.json` overrides (`CFG = {**DEFAULTS, **CFG}` in `plans.py`), so trees at 1:3,000 are already a config value. What is missing is the tree layer itself, plus the isometric's `LARGE` gate on trees.
- **K6 (line 86) and G10.** The comb of bars is also the narrative's choice. Run-10 `massing/config.json` `figure.source` cites "principle 4: rows and streets run with the cold air ... the comb of the storyline". A library (C9) helps only if the config chooses a mix. `references/README.md` has no row for `massing`.
- **K7 (line 87) cites the wrong line.** The jury's "hardest on its interior" is `jury/SKILL.md:21`, not `:12`.
- **G1 (line 17) is overstated.** Not all 141 buildings are about 13 m by 30 to 50 m. The 27 commerce halls are 25 m deep (`TYPOLOGY['halls']` d=25; run-10 `massing/summary.md`), and the school, the pool and two 10-storey landmarks differ too.
- **G6 (line 47) could not be confirmed.** I couldn't confirm "phase 1 on the wrong side of the railway" from run-9 `concept-diagrams/summary.md`, which only calls the positions conceptual.
- **C3 (changes.md:33) would not have fixed run 10's isometric.** `isometric.py:99-102` steps to the next smaller usual scale whenever the drawing is wider than the width it is given. With the 222 mm frame it picks 1:10,000 again (`log.md` 00:08). The section's 564 x 36 mm frame (`log.md` 00:06) was impossible at true scale, a planning error of the first run (K18). Reframe C3: the drawing skills draw at their frame's scale and let `panels.py` crop (it already does), and the lead checks `scan()` against `layout.json` in code.
- **C7 (changes.md:75) misses one check.** `check_style.py:33-35` tests `new` at 3:1 against paper, as well as `accent`. C7 must drop `new` from that test or add a separate building-fill key.
- **C4 and C10 break a test and a rule.** `tests/test_order.py:4` fixes the set of Opus skills, and `test_model_lines` asserts it, so both new skills break the tests. C10 designs and doesn't judge, so under CLAUDE.md it runs on Sonnet with scripts. Cost matters here too: README.md:78 says $30 was about three Pro windows, so run 10's $21 is already above one window.
- **C14 (changes.md:149) misses two things.** `render.py`'s `CLOSING` ("No text, no labels") also blocks the use signs C14 wants, and `test_perspective_render.py:110` asserts exactly two images. Sending the winners' perspectives as a style image risks Gemini copying their content (the pink tower, "WUTZLHUB"), which goes against "Don't put the winners' texts, titles or names on our panels". Send the standard's description of the render style, or say "take the technique, none of the content".
- **C5 (changes.md:53) should drop less.** Keep panel-layout's "never ... add content of your own": the layout skill shouldn't design, and C18 solves the filling.
- **Merges and splits.**
  - Split C15 and do its `Reads:` line now.
  - Split C4: let the jury compare with the project's references now (one line, `jury/SKILL.md:10`), and write the art-direction skill later.
  - Merge C3's and C4's reruns into one revision round.
  - Fold C1 into C2.
  - Build C6 step by step: first make every script read `style.json`'s keys, then let C7, C8, C14 and C16 each add their own key.
- **Missing.**
  - An owner for `plans` (STUDIO.md:90 says "open"). It draws the site plan and the detail areas, the main drawings, and C7, C8 and C10 all land in `plans.py`. Without an owner, nobody keeps those fixes working.
  - A rule for who owns each number on the panels (massing for homes, open-space for sealing), until C11 exists.

## 6. JSON

```json
{"judge": "C", "ratings": {"C1": {"gap": 2, "effort": 2, "risk": 3, "potential": 4, "rank": 17}, "C2": {"gap": 0, "effort": 1, "risk": 1, "potential": 7, "rank": 1}, "C3": {"gap": 2, "effort": 2, "risk": 2, "potential": 5, "rank": 9}, "C4": {"gap": 2, "effort": 3, "risk": 3, "potential": 5, "rank": 11}, "C5": {"gap": 1, "effort": 1, "risk": 2, "potential": 6, "rank": 4}, "C6": {"gap": 2, "effort": 4, "risk": 3, "potential": 6, "rank": 7}, "C7": {"gap": 3, "effort": 2, "risk": 2, "potential": 8, "rank": 2}, "C8": {"gap": 3, "effort": 3, "risk": 2, "potential": 8, "rank": 3}, "C9": {"gap": 4, "effort": 5, "risk": 4, "potential": 7, "rank": 6}, "C10": {"gap": 3, "effort": 4, "risk": 3, "potential": 5, "rank": 13}, "C11": {"gap": 1, "effort": 2, "risk": 1, "potential": 4, "rank": 12}, "C12": {"gap": 2, "effort": 3, "risk": 2, "potential": 4, "rank": 16}, "C13": {"gap": 3, "effort": 3, "risk": 2, "potential": 5, "rank": 14}, "C14": {"gap": 3, "effort": 2, "risk": 3, "potential": 6, "rank": 8}, "C15": {"gap": 2, "effort": 3, "risk": 2, "potential": 5, "rank": 10}, "C16": {"gap": 2, "effort": 3, "risk": 2, "potential": 4, "rank": 15}, "C17": {"gap": 2, "effort": 4, "risk": 3, "potential": 3, "rank": 18}, "C18": {"gap": 3, "effort": 2, "risk": 2, "potential": 7, "rank": 5}}}
```
