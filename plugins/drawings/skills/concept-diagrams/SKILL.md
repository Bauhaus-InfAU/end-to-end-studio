---
name: concept-diagrams
description: Draws three to six concept pictograms that tell a proposal's central idea, taken from its narrative, as SVG with a PNG next to each. Use when a proposal needs concept diagrams or pictograms, a step-by-step sequence of how the design develops, strategy diagrams for a panel, or when asked to "diagram the idea".
---

# Concept diagrams

Reads: narrative

Turn the narrative's central idea into three to six pictograms. Each shows one architectural move, so clearly that the drawing would still make sense without its caption. You translate; you don't design. Take the moves from `narrative/narrative.md` (its idea, its own move and its principles, and what its storyline asks of these pictograms), in its words and order, and their places from what exists: the site data in the project's site folder, and any GeoJSON in the proposal folder from other skills (a structure plan, massing, open space). Where the narrative names a move but nothing gives its place or size, draw it as conceptual geometry, as simple as the idea allows, and never as if it were data. If there's no narrative, draw nothing and say so in `summary.md`. Without a site, draw schematically and say so. Don't add a use, height, position or route the narrative doesn't give; where a move can't be drawn without one, keep that part abstract and name it in `summary.md`.

**Find the relationship, then the drawing.** For each move, say in a few words which spatial relationship it changes and where that is seen: on one level, in height, in mass, in layers, or with no place yet. Then choose the simplest drawing that shows it:
- a *plan*, cut at the level where it happens, for what lies on one level: a figure, a layout, an opening in an edge, how inside meets public space;
- a *section*, cut through every part the relationship links, for what happens in height: a void through floors, light from above, something inserted within a volume, levels linked by a stair, ramp or lift; an *elevation* when there's no inside to cut;
- an *axonometric* for mass and how parts sit together;
- an *exploded axonometric* for layers or systems that make one whole;
- an *abstract pictogram* (points and arrows, no outline) for a relationship without a place.

Keep one viewpoint across frames only where comparing them is the point, as in a form changed step by step. Otherwise give each frame the drawing its own relationship needs; two moves share a drawing type only if they show the same kind of relationship. A set that uses one drawing for every move needs a reason.

Moves that act in turn on one thing are a *sequence*: earlier moves stay in ink, the new one is in the accent, and what it removes is dashed once, where it was. What exists before any move (a building, a structure, the site) is never in the accent, even in the frame that shows it (`accent: false`); the accent marks only what a move adds. A move may only use what the moves before it made: if the narrative's order has one rely on a later one (a path through an opening not yet made), draw the move that makes it first and say so in `summary.md`. Separate strategies (systems, scales, places) are *separate* pictograms on the same base, each with only its own. Either way the set stays one through the same base, orientation and labels.

**Make the drawing carry the move.**
- Show only what the move needs: the site outline and the lines the story is about. Leave out other streets, plots and existing buildings.
- Give each move its own spatial sign. Use arrows only for something that moves or connects: air, water, people, a link. A barrier is an arrow stopped by a bar. An opening is a gap with its removed blocks dashed. A crossing is a raised deck. Shelter or a landmark is height. Rays mark only the one place the story centres on.
- Let geometry carry the meaning: a layer lifted off, a gap, a link, a change in height. The accent only marks what's new; colouring part of a mass doesn't explain it. Prefer one clear form to many blocks: one continuous slope, not a staircase of boxes; one ring with its courtyards, not a grid of pieces.
- Neutral placeholder blocks are allowed for moves that act on built mass. They're not a design, and the footer says so.
- A word or two of label in the drawing, only for what the shape doesn't say. The caption is a title of at most five words and one sentence, in the narrative's own words, on one line of about 90 characters at most, so it never runs into the footer. A number the narrative marks as assumed (a height, a distance) isn't a label: name the thing ("lower housing"), and the footer says the sizes are assumed. The caption and the drawing say the same thing: nothing in one that's missing from the other.
- Each frame has a footer line saying which layers are site data and that everything else is concept. Only a plan on site data gets a graphic scale; a schematic, an elevation or a 3D view says "not to scale" and shows no number for size.

**How.** You decide what each pictogram shows, never how it looks. The look comes from `drawing-graphics/standard.md` in the proposal folder: put every colour, line weight, font and text size it gives into the spec's `style` (its keys are in the spec), and pick none of your own. Without it, leave `style` out: the script falls back to black lines on white with one accent colour for what's new. Run `python "${CLAUDE_SKILL_DIR}/scripts/draw_diagrams.py" info --site <site.geojson> --layer <name>=<layer.geojson>` to get the site and its lines in metres. Then write `spec.json` as `${CLAUDE_SKILL_DIR}/spec.md` describes, and run `python "${CLAUDE_SKILL_DIR}/scripts/draw_diagrams.py" render spec.json .`. It needs `pip install "shapely>=2" pyproj numpy`, and Chrome, Edge or Chromium for the PNGs (`CHROME_PATH` if it isn't found). Look at every PNG, and read the script's warnings. If a frame needs its caption to be understood, two signs or labels overlap, or a move is too small to read at the scale of the site (use a close-up, see the spec), change the spec and render again.

Work in the proposal folder you're told, else the newest one in the project's `proposals/`, else a new `<YYYY-MM-DD>_draft/`. Write only into its `concept-diagrams/`: one SVG (its size in mm) and PNG per pictogram, named after its move (`02_cold-air.svg`), `00_sheet` with all of them, and `spec.json`. Then write `summary.md` in three lines:
1. The pictograms, the form (sequence or separate), the drawing type of each, and their scale ("not to scale", or the plan's scale). A pictogram usually takes one column of a panel: large, it shows its blocks and labels; small, the outline, the main line and the accent move must still read.
2. Their number.
3. What's conceptual rather than data, and the one thing you're unsure of.
