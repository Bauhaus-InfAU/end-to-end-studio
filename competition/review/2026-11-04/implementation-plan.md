# Implement the review's changes, in waves, one fresh agent per change

## Context

The review of 04.11.2026 (`competition/review/2026-11-04/report.md`) found that our runs fall short of the three Europan 18 winners for three reasons. The design layers hold too little to draw (only boxes, no trees, no ground floors). The look can't be learnt (the standard can only recolour, and the accent sits on the buildings). Nothing loops back. Three Opus judges ranked 18 changes and corrected some claims, and a planning agent then checked this plan against the code. You want all the changes, split so that no single context fills up, with one local branch and one commit per change, no push, starting from `runs-in-git` once your three edits are committed.

Every change is built in the form the judges recommended:

- **Reduced or split.** C1 becomes one line in the helper. C4 splits into the jury clause and the gate. C8 splits into planting and drawing. C15 splits into the `Reads:` line and the vocabulary. C6 is built key by key. C17 is done without a new skill. C3's redraw waits for wave 6, because the scripts can't take a frame before then.
- **Added from the reviews.** M1 sets the centre size by level. M4 is the rule on who owns a number. M5 moves panel-layout's first run after the structure plan. M6 is a cost ceiling. M7 builds the hub at a stated size. P1 gives plans a frame per detail area.

### Your question: do we need a full run to test the parts?

No. A full run is needed only once, at the end, to see the whole and its cost. Each part is tested on its own:

1. `python -m pytest tests`, in its worktree.
2. Re-run the changed scripts, and the drawings downstream of a design layer, on a copy of run 10 in `competition/proposals/test/<id>/`. Every input is on disk, and no script calls a model, so this costs nothing. Then make a before/after sheet next to the winners with C2's script.
3. Optionally, one helper run of a skill whose text changed: $0.1 to $0.6 on Sonnet, $1.5 to $4 for panel-layout and the jury. Only where you ask.

## How the work is split

- **One fresh implementer per change.** Each is an Agent with `isolation: "worktree"`. Its task is at most ten lines: its id, the absolute paths of this plan (saved as `competition/review/2026-11-04/implementation-plan.md` once approved) and of the judges' verdicts, and "reply in at most 15 lines". It reads only its own section and "Rules for every implementer".
- **The lead (me) keeps only the replies.** Per change I check `git diff --stat` and look once at the sheet. I don't read whole diffs.
- **Model.** Sonnet: C5, C1r, C4a, M4, C2, M1, M7, C15a, C14. Opus: everything else.
- **Branches.** `review/all` starts at `runs-in-git`. Each change gets `review/<id>-<slug>` from `review/all` at its wave's start, with one commit. Changes in a chain branch from the previous change in the chain. After each wave I merge the branches into `review/all` (`--no-ff`, local) and run pytest. A failing branch goes back to its agent through SendMessage. Parallel items in a wave touch disjoint files (checked by the planning agent). Nothing is pushed.
- **Expected cost.** About 30 implementer runs: roughly 5 to 8 million tokens. No studio run is included.

## Step 0, before wave 1

1. On `runs-in-git`, commit only `CLAUDE.md`, `competition/references/README.md` and `.gitignore`, with the message "references: the Europan 18 winners as references, and the rules for using them". `competition/feedback/` stays untracked.
2. `git branch review/all runs-in-git`.
3. Save this plan to `competition/review/2026-11-04/implementation-plan.md`. It stays untracked.

## Rules for every implementer

- Follow `CLAUDE.md` and `STUDIO.md`. A skill works alone, in any project. Never write a site, competition, layer name or repo path into a skill. Scripts go in the skill's `scripts/`, and the brief's numbers go in `config.json`. Change the fewest lines, say which, and suggest deleting lines that no longer change the result. New skills get a `STUDIO.md` row with "open" under "Who".
- `Model: opus` only for a skill that judges, and keep `tests/test_order.py:4` in step with it. Every new script goes into `NEW_SCRIPTS` (`tests/test_scripts.py:16-21`). Scripts that print JSON print nothing else (`test_open_space.py:63`).
- **Worktree setup.** Copy `competition/proposals/2026-11-02_run-3/` from the main checkout `C:\Work\GitHub\end-to-end-studio` into the worktree, or the run-3 tests fail. Read run 10, `competition/climate/` and `competition/references/winners/` from the main checkout by absolute path. Write test output only to the main checkout's `competition/proposals/test/<id>/`.
- **Testing.** Run pytest. Make the "before" yourself: run 10 was drawn with edited copies of the scripts, so its own drawings are not a fair before. Run the scripts of `review/all` on the same copy of run 10 into `test/<id>_base/`, then yours into `test/<id>/`, and compare those two. pytest rewrites run 3's tracked summaries (line endings only): restore them with `git checkout -- competition/proposals/2026-11-02_run-3` before you commit, and commit only your files. For a drawing or design change, re-run its scripts on a copy of run 10 in `test/<id>/` and run `side_by_side.py` (from wave 2 on), then look at the sheet once.
- **Delivery.** `git switch -c review/<id>-<slug> <base>`, one commit naming the review change it answers, no push. Reply with: branch, commit, files and lines, tests, sheet path, open problems, lines to delete.
- **Shared names, fixed now so parallel work fits together:**
  - Trees are features `kind: tree` with `crown_m`, `height_m` and `group` (street, park, grove, avenue, orchard, courtyard, wood). Massing writes street trees in `massing.geojson`. Open-space writes the rest in `open-space.geojson`.
  - Style keys: `public` (#rrggbb), `shadow` (#rrggbb plus `shadow_len` in metres per floor), `render_style` (text), `storey_labels` (roman or arabic), `diagram` (an object).
  - Massing buildings gain an optional `block` (an id, unique per block), plus `part`, `roof` and `ground_floor` (that floor's use, owned by massing). The detail skill (C10) refines uses in its own file only.
  - A revision run is named `<skill> <label> rerun`, which `cost.py:126` counts.

## Wave 1: rules, measuring, small massing fixes

All in parallel, except M1 → M7, which is a chain.

- **C5 design intent is not invented data.**
  - Files: `STUDIO.md:63`, `plugins/drawings/TOPIC.md`, `isometric/SKILL.md:14`, `concept-diagrams/SKILL.md:10`.
  - Facts and numbers keep their source. Planting, people, use labels and furniture may show where a design layer or a narrative line proposes them, marked as illustrative. Keep `panel-layout/SKILL.md:17`.
- **C1r look at your references.** File: `studio/agents/studio-helper.md` (Pictures bullet). Add: if the project has reference images of the kind your skill draws, look at them before drawing and name the largest differences in `summary.md`.
- **C4a the jury compares.** File: `jury/SKILL.md:10`. The project's reference images are inputs and may be compared with. Never look up results.
- **M4 who owns a number.** File: `panel-layout/SKILL.md:15`. Show the number from the skill that designs that thing, and note the other in `notes`, instead of "show both". Check `test_panel_layout` still passes.
- **C2 measure the gap.**
  - Files: new `competition-proposal/scripts/side_by_side.py`, `scripts/preview.py` and `preview.html`, `competition-proposal/SKILL.md` step 4, `requirements.txt` (Pillow), new `tests/test_side_by_side.py` with small fixture images, and `NEW_SCRIPTS`.
  - References: an optional `references.json` (skill → glob patterns) in the references folder; else the backticked stems of its README's table, searched one level down, with a trailing `-N` widened to `-*`.
  - Px per mm: for a reference, the board's px width divided by the brief's panel width (from `layout.json`'s format). For ours, the SVG's mm size. For a drawing without a scale, its frame's width.
  - Output: `<version>/.compare/`, a folder `panels.py:191` skips.
  - Check: run it on run 10 into `test/c2/`.
- **M1 centre size by level.**
  - Files: `massing.py` `square` (`:52`), with all three places changed together (`:396-397` community buildings around it, `:716` the square, `:741, 761` trees and green), `config.example.json`, `massing/SKILL.md`.
  - Two config sizes, `square_main_m` and `square_local_m`, capped by the centre polygon and by what its `holds` needs.
  - Keep `test_scripts.py:357-358, 363, 371-372` passing (the synthetic 60 m "Square").
- **M7 build the hub** (chained after M1). File: `massing.py` community buildings. A community building that the brief names but gives no area for (run 10: the bus station, `gfa: null`) is built at a stated, flagged assumption instead of being skipped.

## Wave 2: the look, step one; the frame check; perspectives

All in parallel.

- **C7 buildings white with a shadow, the accent on public ground.**
  - Standard: `drawing-graphics/base.md:16`; `base.json` (pale `new`; `public`, `shadow`, `shadow_len`); `check_style.py:7, 33-35` (keep 3:1 for `accent`, not for `new`); `tests/test_drawing_graphics.py`.
  - Plans: `plans.py:371-376`, plus a shadow pass (the union of each footprint swept along the sun vector, so courtyards stay open; the idea from climate's `shadow_hulls`, copied into the skill). `plans.py:292-336` draws the public tone on the centres, massing squares and shared streets (mobility's `access_only` lines at a default width), with open-space present too. `plans/SKILL.md:11`.
  - Isometric: `isometric.py:26-33, 117-122`. Map the standard's keys explicitly, because `STYLE.update` currently turns `text` 3.2 into a stroke. `isometric/SKILL.md:14`.
  - Building types: `building_types.py` and `building-types/SKILL.md:14` (white faces with shade).
  - Section and mobility: keep new buildings visible in `section.py:691, 717`, `site-section/SKILL.md:12` and `mobility.py:672`.
  - Check: re-render plans, isometric, building types and section on `test/c7/`, and make the sheet.
- **C15a pictograms after the structure plan.** File: `concept-diagrams/SKILL.md:8`, adding `structure-plan` to `Reads:`.
- **C3a + M5 the frame check, without a redraw yet.**
  - Files: `panel-layout/SKILL.md` (`Reads:` gains `structure-plan`; the first run also saves `layout-plan.json`); `panels.py` (the report lists every planned item not placed); new `competition-proposal/scripts/frames.py` (compares each drawing's mm size and scale with `layout-plan.json`); lead step 2 (run it before `panel-layout (end)` and log the result); tests.
  - Keep `test_panel_layout.py:123-125, 133` and `test_order.py:47, 52`.
  - Check: regenerate run 10's first plan from its `build_layout.py` in `test/c3/`, and `frames.py` must name the isometric, the section and both detail areas.
- **C14 illustrated perspectives.**
  - Files: `render.py:118-127` (drop the fixed "photorealistic" line; the style comes from `render_style` in `style.json`, else the standard's render section, else an illustrated default), `perspective/SKILL.md`, `tests/test_perspective_render.py` (keep `:110`, two images, and `:112, 129-130`).
  - Send no reference image. Keep `CLOSING`. Don't touch `base.json` or `base.md`.

## Wave 3: trees and panels

The chain C8b → C8a runs alongside C18.

- **C8b plant the open space.**
  - Files: `open_space.py` (tree features by the shared schema: groves and clusters in parks, avenues on park paths, canopy over kept woods, courtyard trees; never on kept-free strips, water, pools, playgrounds, fields, farmland or the solar park), `open-space/SKILL.md`, `design/TOPIC.md:5` (the only change to that line in this wave), `tests/test_open_space.py`.
  - Check: re-run open-space and plans on `test/c8b/`.
- **C8a draw the trees.**
  - Files: `plans.py:49-50, 377-383` (every plan scale, a crown symbol, both files), `isometric.py:53, 103, 176-178` (a loader for open-space trees, all scales), `perspective/scripts/scene.py:397-404`, `site-section/scripts/section.py:33, 730-731`.
  - `Reads` gains `open-space` in `isometric/SKILL.md:8` (end), `perspective/SKILL.md:7` and `site-section/SKILL.md:8` (end).
  - Keep `test_streets_base.py:69-74, 93-97`.
  - Check: on `test/c8a/`, run 10's 1,363 street trees show at 1:3,000.
- **C18 panel composition.**
  - Files: `panel-layout/SKILL.md:13-17` (look at the project's reference boards; one hero drawing across each panel; a band of thematic plans of one size and scale; a section band; a large frame for a close isometric; key numbers as big type with a one-line source), `drawing-graphics/base.md:45-48` (drop "Empty space is allowed"), `panels.py` (a big-number item that keeps `test_panel_layout.py:19-24`), tests.

## Wave 4: massing, plans, standard, phasing

The chain C9a → C9b → C9c runs alongside P1, C6 and C11.

- **C9a block types.**
  - Files: `massing.py:55-100, 156-188` (a library made of parts: perimeter block with corner, L, U, open courtyards of varying size, town-house rows, point buildings, a tower, a hub; each building with `block`, `part`, `roof` and `ground_floor`), `massing/SKILL.md`, `design/TOPIC.md:5`.
  - Update `test_scripts.py:184, 196, 199-201, 236, 381-382` with reasons (a tower now exists).
- **C9b mixing.** `figure` gains a `mix` per neighbourhood, and the SKILL asks for two or three types per neighbourhood.
- **C9c placement.**
  - Each piece takes its bearing from its nearest structure-plan route by default (the existing `route` option), and is split at local routes. Secondary streets and row/col then stay per piece.
  - Scope: `massing.py:196-354, 594, 694`.
  - Keep `test_scripts.py:239-258, 289-322` and `test_streets_massing_clash.py:60-85`.
- **P1 plans take frames.**
  - Files: `plans.py:142-144, 185-201` (each detail area's scale and frame from `layout.json`; `storey_labels` read with an arabic default), `plans/SKILL.md`, `tests/test_plans.py` (keep `:59, 68-80`).
- **C6 standard v2, key by key.**
  - Files: `drawing-graphics/SKILL.md:14` (step 3 reads each kind's references and writes a short recipe per kind), `base.json` (`render_style`, `storey_labels: roman`, `diagram`), `check_style.py`, and the style dicts of `section.py`, `draw_view.py`, `draw_diagrams.py`, `open_space.py` and `mobility.py`. Keys are mapped, not merged, so a `tree` key never overwrites a tree colour.
  - Not `plans.py` (P1's), not `isometric.py` (C7 did it). Keep `test_drawing_graphics.py:43-46`.
- **C11 phasing.**
  - New `plugins/design/skills/phasing/` (the `STUDIO.md:84` row already exists): `Reads: structure-plan, massing, programme`. Scripts reconcile the plan's phases with the massing's into `phases.csv` and `phases.geojson`, with homes, residents and what comes first, and flag any mismatch. It owns the homes-per-phase number for M4.
  - Also `concept-diagrams/SKILL.md:8` (add `phasing`). No `TOPIC.md` change.

## Wave 5: drawings that need the new massing

All in parallel. None of these edits `drawings/TOPIC.md`.

- **C12 ensembles.** Files: `building_types.py` and `SKILL.md:14`. One block per type, by `block`, with its courtyard, trees, roofs, a window rhythm and three to five notes.
- **C13 isometric large and inhabited.** Files: `isometric.py` and `SKILL.md`. The district plus the main centre at 1:1,000 to 1:1,500, with use labels, people and roofs. It draws at its frame's scale and lets panels crop, replacing the step-down at `:98-102`. Keep `test_streets_base.py:69-74`.
- **C16 section as a story strip.** Files: `section.py` (zone bands, the principles as notes on the line, tree crowns, people, a line through the idea, a frame length and height input) and `SKILL.md` (`Reads` gains `structure-plan` and `open-space`). Keep `test_site_section.py:78-80, 112-113`.
- **C15b pictogram vocabulary.** Files: `spec.md`, `draw_diagrams.py` and `SKILL.md`. New elements `person`, `tree`, `icon`, `vignette`, `layers` and `metaphor`.
- **C10 ground floors and detail areas.**
  - A new Sonnet skill (it designs; it doesn't judge), with a `STUDIO.md` row. Scripted rules: entrances on the street side, bike stands at entrances, play in courtyards, uses with areas at the centres, the hub's surfaces.
  - It writes `<name>/detail.geojson`, and `plans.py` draws it inside the detail areas. Keep `test_plans.py:59, 74-80`.
- **C17 thematic plans in one style.** Files: the drawing parts of `mobility.py:593-606`, `open_space.py:742-747` and climate's `draw.py:287`. Each takes a frame width, height and centre from `layout.json`, and the `diagram` key. Keep `test_mobility.py:52, 106-176`.
- **Check for each:** pytest, plus re-render on `test/<id>/` and make the sheet.

## Wave 6: the loop

- **C4b + C3b + M6.**
  - New `plugins/delivery/skills/art-direction/`: `Model: opus`, `Reads: every drawings`, and a `STUDIO.md` row. After the drawings, it puts each drawing beside its references and gives at most three fixes per skill.
  - Lead: one revision round, named `rerun`. It carries the art-direction fixes and every redraw that `frames.py` asks for, before `panel-layout (end)`. Skip the round if `cost.py` shows the run past its ceiling (default $30, `--ceiling`).
  - Also: the exception in `STUDIO.md:49` and `competition-proposal/SKILL.md:19`, the OPUS set in `test_order.py:4`, and `test_cost.py`.

## Not in this plan

- **An owner for `plans`.** The "Who" column is yours.
- **A deeper rework of the urban figure in `structure-plan`**, beyond M1 and C9c.
- **Public ground as its own layer.** It is covered by M1, M7 and C7.

## Verification

- After each wave: `python -m pytest tests` on `review/all`, in a worktree with run 3 copied in.
- After each drawing or design change: its sheet in `competition/proposals/test/<id>/.compare/`, which I look at once.
- At the end:
  1. pytest on `review/all`.
  2. Every drawing script re-run on one copy of run 10, and C2's sheets of every kind next to the winners. The site plan must show white buildings with shadows, trees at 1:3,000 and the accent on the squares. The isometric must take the standard's colours.
  3. `frames.py` on that copy.
  4. Optionally, one full run in `test/` (about $20 to $30). It is the only check of the whole and of the cost.
- Then I remind you to check out `review/all` and type `/reload-plugins`, so the new skills are the ones that run.
