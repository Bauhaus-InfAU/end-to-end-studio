# Proposed changes

Step 3 of the review of 04.11.2026. Each change says what it does, which gaps (G) and causes (K) of `gaps.md` it addresses, where it starts in the code, what it depends on, and where to see the evidence. The order follows the studio's layers (harness, standard, design layers, drawings, delivery) and is **not** a ranking. File sizes are given so effort can be judged; no change is rated here.

None of these is a skill change made now. Every one keeps the rule that a skill works in any project: no site, brief or path of this repo goes into a skill.

## Harness

### C1. A reference check in every drawing helper

**What.** When the project has reference images of the kind of drawing a skill makes, the helper looks at them before it draws. After drawing, it puts its own PNG next to them at the same printed size, names the five largest differences, fixes in its copy of the script what it can, and renders again. It does this for up to three rounds and names what's left in `summary.md`. A shared script, `side_by_side.py` in the lead's `scripts/`, makes the comparison sheet (`evidence/` here was made the same way, about 100 lines with Pillow). The helper finds "its" references through a table that the project keeps next to its references (this repo already has one in `competition/references/README.md`). The lead passes on where that table is, with the other project inputs.

**Gaps.** G1 to G8, as a way to close them. **Causes.** K1, K15.

**Starts in.** `plugins/studio/agents/studio-helper.md:14-15` (the Scripts and Pictures bullets), `STUDIO.md:67` ("Look at a drawing once or twice"), `competition-proposal/SKILL.md` step 1 (what the task names), new `competition-proposal/scripts/side_by_side.py`.

**Depends on.** Nothing to start. The scripts can only move as far as their style keys and geometry allow (C6, C8, C9), so without those the helper's fixes stay in its per-run copy of the script and are lost after the run.

**Facts.** Today a helper changes only a copy of a script in its own folder (`studio-helper.md:14`), so a fix found in one run isn't kept. Each round costs about one image read of two pictures plus one re-render. Drawing skills cost $0.09 to $0.59 each in run 10.

### C2. Measure the gap in every run

**What.** At the end of a run the lead calls `side_by_side.py` (C1) to write `compare/` in the version: one sheet per kind of drawing, the references next to the run's drawing at the same print size, plus the three panels next to the reference boards. `preview.py` links them. Every run's gap can then be seen and compared with the run before.

**Gaps.** None directly; it makes every other change measurable. **Causes.** K15, K17.

**Starts in.** `competition-proposal/SKILL.md` step 4; `competition-proposal/scripts/preview.py` (103 lines).

**Depends on.** C1's script, or a stand-alone copy of it.

### C3. A gate before the final layout: every drawing fits its frame

**What.** After the drawings exist and before `panel-layout (end)`, the lead runs `panels.py scan`, which already lists each drawing's print size and scale, against `layout.json`'s frames. A drawing at another scale, or more than a set share larger than its frame, goes back to its own skill once, with the frame in the request. This adds one allowed exception to "No other skill ever runs twice".

**Gaps.** G9, G11 (run 10: section left off, isometric at 1:10,000 instead of 1:5,000, detail area 2 cropped 52 %, plans "none matches its panel-layout frame"). **Causes.** K14, K15.

**Starts in.** `competition-proposal/SKILL.md:19` (step 2); `panel-layout/scripts/panels.py` `scan()` (line 187).

**Depends on.** Nothing.

### C4. An art-direction gate with one revision round, and a jury that compares

**What.** A new judging skill (`Model: opus`), for example `delivery:art-direction`, runs after the drawings and before `panel-layout (end)`. It puts every drawing beside the reference of its kind and writes, per drawing skill, at most three concrete fixes ("trees at 1:3,000 in every park; buildings white with a shadow; Roman storey numbers"). The lead runs each named skill once more with its fixes, and only then panel-layout. The jury may compare the entry with the project's reference images, because they are project inputs and not a lookup. That removes the clash between `jury/SKILL.md:10` ("never look up results or other entries") and the project rule "The jury compares a run with them".

**Gaps.** G1 to G9, as a way to close them. **Causes.** K15, K16, K17.

**Starts in.** New `plugins/delivery/skills/art-direction/SKILL.md`; `competition-proposal/SKILL.md:19` (allow the one round it asks for); `jury/SKILL.md:10`.

**Depends on.** The drawing skills must be able to act on a fix (C6 to C18). Overlaps with C1: C1 loops inside one skill, C4 loops once across the whole run.

### C5. Design intent is not invented data

**What.** Split the first shared rule of `STUDIO.md`. Facts about the site and every number still need a source. A drawing shows the design's intent (planted trees, people using a place, the names of uses, furniture) where a design layer or the narrative proposes it, and marks what is only illustrative. Then drop or soften the lines that read the old rule as "show nothing": the isometric's "No labels, arrows or people" and "only the trees the data has", concept-diagrams' "add no use, height, position or route the narrative doesn't give", and panel-layout's "never ... add content of your own".

**Gaps.** G2, G4, G5, G6 (empty drawings). **Causes.** K8.

**Starts in.** `STUDIO.md:63`; `plugins/drawings/TOPIC.md`; `isometric/SKILL.md:14`; `concept-diagrams/SKILL.md:10`; `panel-layout/SKILL.md:17`.

**Depends on.** Nothing. It works with C6, C9, C11, C12 and C13.

## The drawing standard

### C6. Drawing standard v2: a recipe per kind of drawing, read from the references

**What.** `drawing-graphics` reads, for each kind of drawing, the references of that kind (not only the boards) and writes a recipe per kind in `standard.md`. It adds keys to `style.json` that the scripts can use: building fill and outline, cast shadow (direction, length per floor, tone), tree symbol (crown outline and fill, sizes by kind, shadow), ground textures (meadow stipple, field stripes), a public-ground tone, label style (storeys as Roman numerals, names of uses), section style (zone bands, notes on the line), diagram style, and render style (illustrated line, collage, photoreal). `check_style.py` checks the new keys, and every drawing script reads them instead of its own style dict.

**Gaps.** G1 to G8 (the look). **Causes.** K1, K2.

**Starts in.** `drawing-graphics/SKILL.md:14` (step 3), `base.md`, `base.json`, `scripts/check_style.py:7`; the style dicts in `plans/scripts/plans.py:70`, `isometric/isometric.py:26`, `building-types/scripts/building_types.py`, `site-section/scripts/section.py:63`, `perspective/scripts/draw_view.py` (STYLE), `concept-diagrams/scripts/draw_diagrams.py`, `open-space/scripts/open_space.py` (FALLBACK_STYLE), `mobility/scripts/mobility.py`.

**Depends on.** Each script must also learn to draw the new things (shadows in C7, trees in C8). `tests/test_drawing_graphics.py` checks `style.json`.

### C7. Buildings white with a shadow, the accent on public life

**What.** Change the base rule "One accent for what the entry is about, usually the new buildings" (`base.md:16`). New buildings become white or very pale with a thin dark outline and a cast shadow, and the accent marks public ground: squares, shared streets, centres, the hub and community buildings. Change plans' "One thing dominates each plan: the new buildings" to the new figure, meaning the buildings and the public space between them. `plans.py` gains a shadow pass (the footprint offset by height times a factor, drawn under the building), `isometric.py` gets pale walls, and building types loses the red face. `check_style.py` keeps the accent's 3:1 contrast for lines and text but allows a pale public-ground tone.

**Gaps.** G1, G2, G3, G4. **Causes.** K3, K4.

**Starts in.** `drawing-graphics/base.md:16`, `base.json`; `plans/SKILL.md:11`, `plans.py:371-376` (new buildings), plus a new shadow step; `isometric/SKILL.md:14`, `isometric.py:26`; `building-types/SKILL.md:14`; `check_style.py:33`.

**Depends on.** Public ground to colour: massing writes a 30 m `square` per centre and street `level`s today. C10 would add more. Smaller than C6, and can stand alone.

## Design layers

### C8. Planting as a design layer

**What.** A design layer writes `tree` features with crown size and kind: avenues on main streets, trees in courtyards, groves and loose clusters in parks, orchard grids, and canopy over kept woods. This could be a new `design:planting` skill or a step of `open-space`. `plans.py` drops the 1:2,000 limit and draws crowns at 1:3,000, as all three winners do. The isometric, section and perspective draw the same trees.

**Gaps.** G1, G2, G4, G5, G7. **Causes.** K5.

**Starts in.** `open-space/scripts/open_space.py` (855 lines, writes ground cover and no trees) or a new skill; `massing.py:745` (street trees only); `plans.py:49-50, 377-383`; `isometric.py` lines 165-188; `section.py:33` (tree heights by land use); `perspective/scripts/scene.py`.

**Depends on.** C6 for the tree symbol; works without it in the scripts' default look.

### C9. A typology library in the massing

**What.** Replace the box generator with a library of block types made of building parts: perimeter block with a corner and gaps, L and U, open-courtyard ensembles of varying length and depth, town-house rows on narrow plots, point buildings, a landmark tower, a hub (garage, tower, ground-floor uses) and a campus. Each part has floors, a roof (flat, green, PV, gable) and a ground-floor use. The config's `figure` gets a `mix` per neighbourhood (two or three types, varied length, depth and angle). `massing.geojson` gains `part`, `roof` and `ground_floor`.

**Gaps.** G1, G3, G4, G5, G10. **Causes.** K6.

**Starts in.** `design/skills/massing/scripts/massing.py:55-100` (types), `156-188` (`segs`, `squares`, `block_buildings`), `238` (rectangles on a grid); `massing/SKILL.md` ("Blocks", "What to write"); `design/TOPIC.md` (building properties).

**Depends on.** Nothing to start. Every reader of `massing.geojson` keeps working if the new properties are optional. It unlocks C10, C12 and C13. `massing.py` is 823 lines, and analysis, streets, open-space, mobility, plans, isometric, section, perspective and building types all read its output.

### C10. A new skill for ground floors and detail areas

**What.** A design skill (`Model: opus`) designs the detail areas the brief asks for. It gives every building there its ground-floor uses and entrances (with areas, as winner 3 does), zones the courtyards (private gardens, shared yard, play), and lays out the public surfaces: paving, squares with furniture, bike parking, bus bays, sports fields and playground equipment. It writes `<skill>/detail.geojson` (kinds `entrance`, `ground-floor`, `surface`, `furniture`, `play`, `label`), and `plans` draws it in the detail areas. `design/TOPIC.md:9` already names "a ground floor plan of uses" as a skill nobody wrote.

**Gaps.** G2, G10 (centres, hub), and the jury's "interior". **Causes.** K7.

**Starts in.** New `plugins/design/skills/<name>/`; `plans/scripts/plans.py`, the detail-area branch (around line 197) and its layers; `plans/SKILL.md:11` ("entrances where the data has them"); `Reads: massing, open-space, mobility, streets, programme, panel-layout`.

**Depends on.** C9 helps (building parts and ground-floor use), but it can work on today's boxes.

### C11. A phasing skill

**What.** Write the `phasing` skill that `STUDIO.md` lists as open. It owns which neighbourhood and which centre come in which phase, the homes and residents per phase, and what comes first (stop, hub, school). It writes a table and a GeoJSON that the phase diagram and the panels read, so the panels show one count instead of two.

**Gaps.** G8 (phase diagram), G11 (homes per phase from massing against structure plan, shown twice in run 10). **Causes.** K18.

**Starts in.** New `plugins/design/skills/phasing/`; massing's `phase` property; the `STUDIO.md` table.

**Depends on.** Nothing.

## Drawings

### C12. Building types as annotated ensembles

**What.** `building_types.py` draws a whole representative block of each type: all its buildings from the massing, its courtyard, trees and street edge on a ground plate, roofs by type and a façade rhythm (a window grid per floor). It adds three to five leader-line notes from the narrative and programme (shared rooms, entries, gardens).

**Gaps.** G3. **Causes.** K10.

**Starts in.** `drawings/skills/building-types/scripts/building_types.py` (383 lines, the median-building pick at line 151); `building-types/SKILL.md:14`.

**Depends on.** C9 for variety: with today's massing every type is a bar. C6 or C7 for the look.

### C13. The isometric large, on the centre, inhabited

**What.** Two isometrics, as the winners have. One is the district, pale, with trees and the public ground in the accent. The other is the main centre at 1:1,000 to 1:1,500, with use labels, people, trees and roofs. Panel-layout gives the close one a large frame (a third to half a board).

**Gaps.** G4. **Causes.** K3, K5, K8.

**Starts in.** `isometric/SKILL.md` ("View", "What it shows"); `isometric.py` (270 lines; `LARGE` at line 103, the view choice, the drawing loop at lines 165-208); `panel-layout` first-run frames.

**Depends on.** C5 (labels, people), C7, C8. C9 for roofs.

### C14. Illustrated perspectives with a style image and story scenes

**What.** `render.py` takes the render style from the standard instead of the fixed "photorealistic" line, and sends the reference perspectives as a style image next to the base and depth images. The model takes several images. The scene comes from the narrative (who does what where, signs of the uses from massing and programme), and the views go where the story happens (the centre, the hub, the green link), not only where `find_views.py` scores best.

**Gaps.** G5. **Causes.** K9.

**Starts in.** `perspective/scripts/render.py:22-26` (DEFAULTS look), `118-126` (`build_prompt`), `178-179` (`contents`); `perspective/SKILL.md`; `base.md:50-53`; `find_views.py` (226 lines).

**Depends on.** C6 for a render-style key, or an option file. `tests/test_perspective_render.py` covers `render.py`.

### C15. Concept diagrams with a richer vocabulary, after the structure plan

**What.** Change `Reads:` to `narrative, structure-plan, drawing-graphics, panel-layout`, so the pictograms show the plan's real figure. Add elements to the spec: `person`, `tree`, `icon`, `vignette` (a small axonometric scene), `layers` (an additive sequence like winner 1's "green connector + squares + streets + courtyards") and a free `metaphor` frame not on the site base.

**Gaps.** G6, G11. **Causes.** K11, K18, K8.

**Starts in.** `concept-diagrams/SKILL.md:8, 10`; `concept-diagrams/spec.md` (elements table); `scripts/draw_diagrams.py` (726 lines).

**Depends on.** C5 for metaphor and people.

### C16. The section as a story strip

**What.** `section.py` adds ground bands coloured by zone (from structure-plan and open-space: neighbourhood, park, street, field), notes on the line with the narrative's principles at their place (arc and dot, as both winners do), trees with crowns by kind, and people. It chooses a line through the idea (centre and green). A schematic "concept section" option fits a long thin frame.

**Gaps.** G7. **Causes.** K12.

**Starts in.** `site-section/scripts/section.py` (898 lines); `site-section/SKILL.md` ("The section").

**Depends on.** C8 for trees, C6 for the style.

### C17. A thematic plan set in one diagram style

**What.** A drawings skill (or a shared renderer in `drawings`) draws three to five small plans at the same frame, scale and pale base: mobility, blue-green, phases with homes, centres and uses, and climate. It uses icons and short labels, from the design skills' GeoJSON. The design skills keep their own maps as check plans.

**Gaps.** G8, G9. **Causes.** K13.

**Starts in.** New `plugins/drawings/skills/<name>/`; the drawing parts of `mobility.py` (924 lines), `open_space.py` and climate's `draw.py` (649 lines); panel-layout frames.

**Depends on.** C11 for the phase plan, C6 for the diagram style.

## Delivery

### C18. Panel composition learnt from the reference boards

**What.** Panel-layout looks at the reference boards and plans its grid from them: one hero drawing across the panel's width per board, a band of diagrams above, a band with the section below, the entry's title as a graphic element, and key numbers as big type with a one-line source in small print. Sourced tables go off the panels. Two numbers that disagree go into `notes`, and the panels show the owner's number (C11) instead of both. Drop "Empty space is allowed" from the base (`base.md:47`).

**Gaps.** G9. **Causes.** K14.

**Starts in.** `panel-layout/SKILL.md:13` (first run, frames), `:15` ("Every number on a panel shows its source", "show both"), `:17`; `base.md:45-48` (Panels); `panels.py` (766 lines; a big-number item next to `figures`).

**Depends on.** C3 so the drawings fill their frames; C11 for one count per figure.
