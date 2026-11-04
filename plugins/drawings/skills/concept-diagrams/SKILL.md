---
name: concept-diagrams
description: Draws three to six concept pictograms that tell a proposal's central idea, taken from its narrative, as SVG with a PNG next to each. Use when a proposal needs concept diagrams or pictograms, a step-by-step sequence of how the design develops, strategy diagrams for a panel, or when asked to "diagram the idea".
---

# Concept diagrams

Reads: narrative, structure-plan, phasing, drawing-graphics, panel-layout

Turn the narrative's central idea into three to six pictograms, each showing one architectural move that reads without its caption. You translate; you don't design: take the moves from `narrative/narrative.md`, in its words and order, and their places from the site data, the structure plan's GeoJSON and any other GeoJSON other skills left in the proposal folder. The rest is conceptual geometry, as simple as the idea allows: add no use, height, position or route the narrative doesn't give; people and use signs may show a narrative move, marked illustrative. Name what you assumed in `summary.md`. With no narrative, draw nothing; with no site, draw schematically; say so.

**Choose the drawing from the relationship** the move changes, the simplest that shows it:
- a *plan*, cut where it happens: a figure, a layout, an opening in an edge, inside meeting public space;
- a *section* through everything the relationship links: a void, light from above, an insertion, levels joined by a stair, ramp or lift; an *elevation* when there's no inside;
- an *axonometric* for mass, an *exploded* one for layers of one whole;
- an *abstract pictogram* (points and arrows) for a relationship without a place.

Share a viewpoint only when comparing frames is the point. Moves acting in turn on one thing are a *sequence*: earlier moves in ink, the new one in the accent, what it removes dashed where it was; draw first any move a later one depends on, and say so. Separate strategies are *separate* pictograms on one base. What exists before any move is never in the accent.

**Make the geometry carry the move**: only what it needs, one clear form, its own spatial sign (see the spec); colour marks what's new, it doesn't explain. Small, a pictogram keeps the idea, its primary geometry and key relationships; large, it may add secondary information the input supports. If `panel-layout/layout.json` has frames for the pictograms, make one per frame, each showing what its `shows` asks and reading at its frame's size. Label a word or two, only what the shape doesn't say, never an assumed number. Caption: a title of up to five words and one sentence in the narrative's words. The look is never yours: put the colours, line weights and fonts of `drawing-graphics/standard.md` into the spec's `style`, or leave it out. Write `spec.json`, render it as `${CLAUDE_SKILL_DIR}/spec.md` describes, look at every PNG, and revise until each frame reads without its caption and nothing overlaps.

Work in the proposal folder you're told, else the newest in the project's `proposals/`, else a new `<YYYY-MM-DD>_draft/`, and write only into its `concept-diagrams/`. Everything outside it, in the proposal or the project, is read-only: never delete, move, rename, overwrite or tidy any of it, whatever its name (other skills' files, logs, `usage.csv`); on a rerun, replace only your own files. Write there: an SVG and a PNG per pictogram, named after its move, `00_sheet` with all of them, `spec.json`, and `summary.md` in three lines:
1. The pictograms, sequence or separate, each one's drawing type and scale, and what must still read small (usually one panel column).
2. Their number.
3. What's conceptual rather than data, and the one thing you're unsure of.
