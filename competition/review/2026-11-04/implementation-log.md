# Implementation log

What each change of `implementation-plan.md` did, branch by branch. Every branch has one commit, starts from `review/all` (or from the change before it in a chain), and is merged into `review/all` locally. Nothing is pushed. The integration worktree is `.claude/worktrees/review-all`.

Step 0: commit `26e28da` on `runs-in-git` holds your three edits (CLAUDE.md, references README, .gitignore). `review/all` starts there. Baseline: 95 tests pass.

## Wave 1: rules, measuring, small massing fixes

| Change | Branch | Commit | What changed | Tests |
|---|---|---|---|---|
| C5 intent is not data | `review/c5-intent-not-data` | 4237108 | `STUDIO.md:63` keeps "every number has its source" and adds that a drawing may show what a design layer or narrative line proposes, marked illustrative. `drawings/TOPIC.md` gets one bullet. `isometric/SKILL.md:14` allows labels, people and trees from the design. `concept-diagrams/SKILL.md:10` allows people and use signs for a narrative move. Panel-layout's line is kept. | pass (the 4 run-3 failures came only from missing data in the worktree) |
| C1r look at references | `review/c1r-look-at-references` | a938684 | `studio-helper.md:15`: look at the project's reference images of your kind before drawing, and name the largest differences in `summary.md`. | 95 pass |
| C4a jury compares | `review/c4a-jury-compares` | 7d8f0ca | `jury/SKILL.md:10`: the project's reference images are inputs; compare drawing by drawing. It still never looks up results. | pass |
| M4 number owner | `review/m4-number-owner` | 35967f3 | `panel-layout/SKILL.md:15`: the number of the skill that designs that thing goes on the panel, the other goes in notes. | 12 panel tests pass |
| C2 compare sheets | `review/c2-compare-sheets` | 8e1c6d3 | New `competition-proposal/scripts/side_by_side.py` writes `<version>/.compare/<kind>.jpg`, references beside ours at one print size. The lead runs it at the end, `preview.html` links it, Pillow goes into `requirements.txt`, and there's a new test. | new tests pass |
| M1 centre size | `review/m1-centre-size` | c739984 | `massing.py`: main squares 60 m and local ones 30 m (`square_main_m`, `square_local_m`), cut back to the centre's land and its needs. One test now checks housing only, because a school now fits on the synthetic centre. | pass |
| M7 hub building | `review/m7-hub-building` | a40357b | `massing.py`: a community building the brief names without an area is built at `community_gfa_m2` (default 300 m², an assumption named in `stats.json`, `assumptions.md` and `areas.csv`) instead of being skipped. On run 10 that puts a 300 m² bus station at Station Square, and every other total is unchanged. | 95 pass |

**After wave 1:** 97 tests pass on `review/all` (5 min 47 s).

Notes for you:
- Run 10 was drawn with edited copies of its scripts, so every "before" in the tests is the `review/all` script on the same copy, not run 10's own files.
- C2: the winners' cut files are 1.25 times the boards' scale (`CUT_ZOOM`, which `references.json` can override). Labels are cut off on narrow tiles. The analysis and climate sheets list many of our maps.
- C1r's agent suggests deleting the helper's line about copying a script into its own folder. I didn't, because that line lets a helper fit a script to a brief. It's your call.
- M1's sizes (60 and 30 m) and the cap at 0.4 of the centre's area are assumptions, named in the config.
- Sample sheet: `competition/proposals/test/c2/2026-11-03_run-10/.compare/plans.jpg`.

## Wave 2: the look, step one; the frame check; perspectives

| Change | Branch | Commit | What changed | Tests |
|---|---|---|---|---|
| C7 white buildings, shadow, accent on public ground | `review/c7-white-buildings` | 21b77fc | `base.json`: `new` is white, with new keys `public`, `shadow` and `shadow_len`. `check_style.py`: 3:1 contrast only for `accent`. `plans.py`: a shadow pass (footprints swept along the light, so courtyards stay open) and the public tone on the massing's squares, community grounds and shared streets. The isometric maps the standard's keys one by one, which fixes run 10's leak of red walls and yellow fields. Building types and section: white faces with shade. Mobility: new buildings outlined. One fix: the structure plan's centres no longer print as pink discs. | full run passes (98), plans and standard 12/12 after the fix |
| C15a pictograms after the plan | `review/c15a-pictograms-after-plan` | b7b4432 | `concept-diagrams/SKILL.md:8, 10`: `Reads:` gains `structure-plan`, and the moves take their places from its GeoJSON. | order tests pass |
| C3a + M5 frame check | `review/c3a-frame-check` | d2f9a01 | panel-layout reads `structure-plan` (its first run comes after the plan), sizes frames from what they show, and keeps `layout-plan.json`. `panels.py` reports planned items not on the panels. New `frames.py` names every drawing off its frame, and the lead logs it before panel-layout's end run. On run 10 it names 13 of 21, among them the isometric (1:10,000 against 1:5,000) and the section (77 % hidden). | 101 pass |
| C14 illustrated perspectives | `review/c14-illustrated-renders` | c4f33bc | `render.py`: no fixed "photorealistic" line. The style comes from `render_style` in `style.json`, else an illustrated default in words (line drawing with flat colour, collage, cut-out trees and people). No reference image is sent, and `CLOSING` is kept. | 8/8 perspective tests |

Notes for you:
- C7: with run 10's 30 m squares there is still little pink. M1's 60 m main square and wave 4's massing will give the accent more to mark.
- C7: the section's key plan still shows new buildings in the accent (`section.py:599`).
- C3a's agent suggests deleting "The drawing skills then draw to their frames." in panel-layout's SKILL.md. I left it for you.
- Sheets: `competition/proposals/test/c7/.compare/` (after) and `test/c7_base/.compare/` (before).

**After wave 2:** 103 tests pass on `review/all` (4 min 13 s).

## Wave 3: trees and panels

| Change | Branch | Commit | What changed | Tests |
|---|---|---|---|---|
| C8b plant the open space | `review/c8b-planting` | ca07f50 | `open_space.py` writes trees (`kind: tree`, `crown_m` as the diameter, `height_m`, `group`, `existing` only for kept woods): canopy over kept woods, courtyard trees, loose clusters in parks, avenues on park paths, groves. None on kept-free strips, fields, the solar park, sport, water, pools, playgrounds or streets. On run 10: 1,280 trees (650 kept-wood canopy, 630 planted). The shared schema is on `design/TOPIC.md:5`. | 102 pass, plus a new test |
| C8a draw the trees | `review/c8a-draw-trees` | 0d060cf | `plans.py` draws every tree from massing and open-space at every scale (the 1:2,000 limit is gone), as crowns with a soft shadow under the buildings. The isometric (all scales), the perspective scene and the section (trees on or near the line) read the same trees. `Reads` gains `open-space` in isometric, perspective and site-section. On run 10 the 1,363 street trees now show at 1:3,000. | 103 pass |
| C18 panel composition | `review/c18-panel-composition` | 4bf7f94 | `panel-layout/SKILL.md`: look once at the project's whole-panel references; one hero drawing across each panel; bands of thematic plans of one size and scale; a section band; a large frame for a close isometric. Key numbers go on as big type with a one-line source. `panels.py` gets a `number` item. `base.md` drops "Empty space is allowed". | 104 pass |

Notes for you:
- C8b: 603 planted trees stand on farmland that the structure plan turns into park, because run 10's open-space laid park over the farmed fields. They follow the design, so the design's own problem stays.
- C8a: the perspective's base view still draws each crown at a fixed 3.5 m (`draw_view.py`, `find_views.py`).
- Sheets: `competition/proposals/test/c8a/.compare/plans.jpg` (white buildings, shadows, tree-lined streets) and `test/c8b/.compare/open-space.jpg`.

**After wave 3:** 105 tests pass on `review/all` (4 min 18 s).

## Wave 4: massing, plans, standard, phasing

| Change | Branch | Commit | What changed | Tests |
|---|---|---|---|---|
| C11 phasing | `review/c11-phasing` | c243e2b | New skill `design:phasing` (Sonnet; `Reads: structure-plan, massing, programme`), with `scripts/phases.py` and `config.example.json`. It writes `phases.csv`, `phases.geojson` and `stats.json`: one homes-per-phase count from the massing, the plan's figure beside it, the gaps flagged, and what comes first. `concept-diagrams` now reads it. On run 10: 1,315 / 1,445 / 680 homes (3,440 in all, as massing), against the plan's 1,350 / 1,400 / 720. | 106 pass |
| P1 plans take frames | `review/p1-plans-frames` | c00acff | `plans.py` takes each detail area's and the site plan's scale and frame from `layout-plan.json` (else `layout.json`), legend included, and storeys follow `storey_labels` (roman or arabic). On run 10: detail 1 goes from 34 % hidden to fitting, detail 2 from 75 % hidden to fitting, and the site plan is exactly its frame. The figure-ground is still off its frame. | 105 pass |
| C9a block types | `review/c9a-block-types` | 6e5e393 | `massing.py`: seven new block types built from parts (perimeter with corners one floor higher, L, U, ensemble of an L, a bar and a point, town houses on 6.5 m plots, tower, hub of a garage plus a tower). Blocks in odd rows and columns are mirrored, and a part that doesn't fit breaks into its arms, then into bars. Each building gets `block`, `part`, `roof` and `ground_floor`. A daycare now goes only into a building that holds it under its floor cap. On run 10 with a mix: homes 3,440 → 3,349 (inside the brief), commerce 180,552 → 179,122 m², home buildings at the cap 54/108 → 110/157. | 112 pass |
| C6 standard v2, key by key | `review/c6-standard-keys` | 35a98d0 | `drawing-graphics` step 3 reads the whole reference boards, then each kind from the files the project names for it, and writes a short recipe per kind. It takes the look, never the texts. `base.json` gets `storey_labels: roman`, `render_style` and `diagram`, and `check_style.py` checks them. `section.py`, `open_space.py`, `mobility.py`, `draw_view.py` and `draw_diagrams.py` take only the keys they use, mapped one by one. The perspective base view and the pictograms now take the standard's colours and font. It also removes three lines that had become false (a perspective warning, and sentences in perspective's and concept-diagrams' SKILL.md). | 106 pass, 45 after the fix |
| C9c placement along routes | `review/c9c-route-placement` | 54ed7d5 | `massing.py`: "route" is the default orientation (each piece takes the bearing of the route it fronts longest, and keeps its long side where that holds more blocks). A route that ends inside the land goes on to its edge as a secondary street and splits the piece. Each row of blocks is one depth of the mix, and the ensemble variant no longer lines up with a 3-type list. New: when `homes_target_is_minimum` is false, floors come off the tallest non-landmark home buildings until homes are within the brief's maximum. On run 10: 3,398 homes with C9b's fixed bearing, 3,397 when the blocks follow the routes. | 128 pass, 45 after the fix |

Notes for you (wave 4):
- C9a: on run 10's narrow land many L, U and perimeter blocks break into bars. C9c (placement along routes) should help. Homes count as floor area ÷ 85 m², so a town house counts as 2.7 homes.
- C11: residents (6,158) are over the brief's 6,100 because the homes are; phasing doesn't flag totals against the brief.
- P1: the figure-ground is still off its frame. At 1:15,000 its frame reaches past the site data, so framing it would print empty paper.

**After C11, P1, C9a and C6:** 116 tests pass on `review/all` (4 min 26 s).

## Wave 5: drawings that need the new massing

| Change | Branch | Commit | What changed | Tests |
|---|---|---|---|---|
| C13 isometric large and inhabited | `review/c13-large-isometric` | c9c1119 | `isometric.py` no longer steps down to a smaller scale; it draws at its scale and the panels crop. A second drawing, `isometric_centre_1-1000`, shows the main centre with use labels on the façades (a ground-floor use the massing allots is marked `*` illustrative), square names, illustrative people on the squares and streets, roofs (gable, green, PV) and fading edges. It also fixes a precision bug at large scales. `Reads (end)` gains `structure-plan`. | 116 pass |
| C10 ground floors and detail areas | `review/c10-ground-floors` | e1942ba | New Sonnet skill `design:ground-floor`, with `scripts/ground_floor.py` and `config.example.json`, and a `STUDIO.md` row. Scripted rules: doors on the street side, bike stands at doors, play in courtyards, the centres' uses with their areas, bus bays and bike parking at the hubs. It writes `detail.geojson`, which `plans.py` draws in the detail areas only. On run 10: 213 doors, 844 stands, 50 courtyard play areas, 7 centre uses, 6 bus bays at Station Square. | 118 pass |
| C15b pictogram vocabulary | `review/c15b-pictogram-vocabulary` | c5d4e78 | `draw_diagrams.py`, `spec.md` and `SKILL.md`: new elements `person`, `tree`, `icon` (23 line signs), `vignette`, `layers` (an "A + B = together" sequence) and `metaphor` (a free frame off the site). The footer marks people and signs as illustrative. Run 10's spec renders byte-identically. | 117 pass |
| C16 section as a story strip | `review/c16-section-strip` | 1733f06 | `section.py`: the design pass draws zone bands under the ground from the structure plan and open space, each named. The narrative's principles become notes in the sky, at their place, from `notes.json`; a hollow dot marks a note placed by the script (illustrative). Lobed tree crowns, and people on the whole cut. A frame (`--frame W,H`, else `layout-plan.json`) sets the size, and the line runs past the site to fill it. `Reads (end)` gains `structure-plan` and `narrative`. On run 10 the 564 × 36 mm band is filled exactly; before, the section was 632 × 140 mm and left off. | 117 pass |
| C9b type mixing | `review/c9b-type-mixing` | 3ebafb2 | `massing.py`: `figure` gains `mix` per neighbourhood, as a list cycling by grid position or as shares. Neighbouring blocks differ, and a type that builds nothing passes to the next. `massing/SKILL.md`: each neighbourhood mixes two or three types unless the narrative gives a reason. On run 10, mixed: homes 3,349 → 3,244, commerce 179,122 → 152,113 m² (the test put three hubs in the commerce areas). | 118 pass |
| C17 thematic plans in one style | `review/c17-thematic-plans` | 6260890 | `mobility.py`, `open_space.py` and climate's `draw.py` take one frame (width, height, scale, optional centre) from `layout-plan.json`, else `layout.json`, else `--frame` and `--centre`, plus the standard's `diagram` weights. Each draws a short legend in a box at the corner that covers least of the site. On run 10 all three come out at 184 × 240 mm at 1:10,000, centred on the site, so they line up in a row (before: 170 × 229, 178 × 215 and 330 × 305 mm). | 120 pass |
| C12 building types as ensembles | `review/c12-type-ensembles` | 46f1c67 | `building_types.py` draws the block of each type with the most buildings: ground, courtyard, streets and trees from massing and open space, roofs by `roof` (green, PV rows, gable at an assumed 35°, flat), windows in an illustrative 3 m rhythm with shop fronts, and 3 to 5 notes with leader lines (from `notes.json`, which the skill writes from the narrative, else facts from the layers with their source). The most-built types come first, at most six, wrapped to the frame; those left out are named. It also fixes a bug: the script never found its frame. | 120 pass, plus 6 building-types tests |
Notes for you (wave 5):
- C13: run 10's main centre has only a one-floor bus station, so the close view is mostly park. That comes from the massing.
- C10: the food market is flagged, because the massing puts no shop within 30 m of the main centre. The bus bays sit about 15 m off the street. The bike spaces (200 and 40) are assumptions.
- Sheets: `test/c13/.compare/isometric.jpg` and `test/c13/isometric/isometric_centre_1-1000.png`; `test/c10/2026-11-03_run-10/.compare/plans.jpg`; `test/c15b/vocabulary/00_sheet.png`.
- C17: `layout.md` doesn't mention `frame.centre`, so panel-layout won't write it yet (the site's centre lines the maps up today). The bus line at the `diagram` weight is heavy. Open space draws new buildings dark grey, unlike the other two. Suggested deletion: in `open-space/SKILL.md`, the sentence telling the helper to put the standard's values into a JSON with the keys of `FALLBACK_STYLE`, because the script reads `style.json` by key since C6. Row: `test/c17/.compare/thematic-row.jpg`.
- C16: the line, chosen on the site as it is, mostly crosses existing houses, and a 36 mm band is low for notes. panel-layout should plan a taller band.
- C9b: mixing row types with courtyard types makes every block as deep as the largest type. C9c is asked to size the pitch per type.
- C12: run 10's frame (564 × 164 mm at 1:500) can't hold even one block with its notes, so the script draws the most-built type alone and says the set fits at about 1:2,000. panel-layout should plan this frame at about 1:1,000 and taller, as the winners do. Drawing: `test/c12/building-types/building-types_1-500.png`.

## Wave 6: the loop

| Change | Branch | Commit | What changed | Tests |
|---|---|---|---|---|
| C4b + C3b + M6 art direction, one revision round, cost ceiling | `review/c4b-art-direction-loop` | 219907d | New skill `delivery:art-direction` (`Model: opus`, `Reads: every drawings (end)`). It uses the `.compare/` sheets and writes `fixes.json` (at most three fixes per skill that its scripts can carry out), `notes.md` and `summary.md`, and it never copies a reference's text. The lead runs `side_by_side.py` before it, then one round per run before `panel-layout (end)`: each skill named in `fixes.json` or by `frames.py` runs again as `<skill> <label> rerun` with its fixes and frame, changing only its drawings. The round is skipped past `cost.py --ceiling` (default $30). `STUDIO.md` gets the exception and a row, and tests cover the OPUS set, the order and the ceiling. | 127 pass |

Notes for you (wave 6):
- `narrative (end)` also waits for art-direction, so it may run alongside the reruns.
- In `cost.csv` a rerun shows as run 2, like a skill's second run.
- Nobody acts on the standard's gaps in `notes.md` within the run.

**After waves 5 and 6 (all but C9c):** 137 tests pass on `review/all` (5 min 16 s).
- C9c: run 10's config gives every neighbourhood a fixed 8° bearing, so the route default only shows when the narrative gives none (`test/c9c_route/.compare/plans.jpg`). Without the bearing, commerce drops 7%, because the buildings in the loud strip that counted as commerce move out. A piece facing several routes follows only one. The blocks still stand as loose bars in green, far sparser than the winners' continuous blocks.

**Final:** with every change merged, 141 tests pass on `review/all` (5 min 34 s). `review/all` is 54 commits ahead of `runs-in-git`: 25 changes and their merges.

## End-to-end check on `review/all` (36da3be)

A copy of run 10 in `competition/proposals/test/final/2026-11-03_run-10/`, run with every new script and no model calls. Massing used a mix in each neighbourhood and no fixed bearing.

- **Ran:** massing, streets, open-space, mobility, ground-floor, phasing, plans, isometric (district and centre), building types, site section (design pass, to its 564 × 36 mm band), perspective (base views, no Gemini), climate maps, concept diagrams (run 10's spec; its relative site path had to be deepened in the copy), `frames.py`, `side_by_side.py`, panels.
- **Figures:** homes 3,397 (max 3,400); commerce 148,977 m², 35 % short of 230,000; phases 1,172 / 1,317 / 908 against the plan's 1,350 / 1,400 / 720; 2,562 trees (1,281 street, 654 kept-wood canopy, 627 planted); 217 doors, 864 bike stands, 56 courtyard play areas.
- **Frames:** 9 of 21 drawings are off their frame, against 13 on run 10. The site plan, the section, both detail areas and the thematic maps now fit. Still off: the two views (not rendered), the isometric (by plan: it is at 1:5,000 and the panel crops it), building types (68 % hidden at 1:500), figure-ground, the analysis maps and two pictograms.
- **Panels:** `panel-layout/panel-1.png` to `panel-3.png`, laid out with run 10's own end layout, only three file names changed. A real panel-layout run would re-plan them with C18's rules.
- **Sheets:** `.compare/plans.jpg`, `.compare/isometric.jpg` and `.compare/boards.jpg` in that folder.

**Still far from the winners:**
1. The urban fabric. Our blocks are loose bars and L's in pale green; the winners' blocks form continuous streets and squares. The main centre is still a one-floor bus station on a pink patch.
2. Board composition. Run 10's old layout puts five large pictograms on panel 1 and has no slot for the section or the close isometric. That needs a real panel-layout run.
3. Depth of the ground and the views. Our ground is pale with solid pink squares; the winners thread pink public ground through the streets and use darker canopy. The views need the illustrated render (Gemini).

## Lines the implementers suggested deleting (left for you)

- `studio-helper.md`: "copy a script into your own folder and change the copy" (C1r's agent). I'd keep it: it is how a helper fits a script to a brief.
- `panel-layout/SKILL.md`: "The drawing skills then draw to their frames." (C3a's agent).
- `open-space/SKILL.md`: the sentence on putting the standard into a JSON with the keys of `FALLBACK_STYLE` (C17's agent), since the script reads `style.json` by key.
- `concept-diagrams/SKILL.md:10`: the words "marked illustrative", since the footer now says so (C15b's agent).
