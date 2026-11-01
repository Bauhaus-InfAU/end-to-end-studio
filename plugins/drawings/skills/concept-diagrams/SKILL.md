---
name: concept-diagrams
description: Draws three to six concept pictograms that tell a proposal's central idea, taken from its narrative, as SVG with a PNG next to each. Use when a proposal needs concept diagrams or pictograms, a step-by-step sequence of how the design develops, strategy diagrams for a panel, or when asked to "diagram the idea".
---

# Concept diagrams

Reads: narrative, drawing-graphics

Turn the narrative's central idea into three to six pictograms, each showing one architectural move so clearly that it reads without its caption. You translate; you don't design. Take the moves from `narrative/narrative.md`, in its words and order, and their places from what exists: the project's site data and any GeoJSON other skills left in the proposal folder. What nothing places or sizes is conceptual geometry, as simple as the idea allows, never shown as data; don't add a use, height, position or route the narrative doesn't give, and name what you had to assume in `summary.md`. With no narrative, draw nothing and say so; with no site, draw schematically and say so.

**Choose the drawing from the relationship.** For each move, say which spatial relationship it changes, then draw it the simplest way that shows it:
- a *plan*, cut at the level where it happens: a figure, a layout, an opening in an edge, inside meeting public space;
- a *section*, cut through every part the relationship links: a void, light from above, something inserted within a volume, levels joined by a stair, ramp or lift; an *elevation* when there's no inside to cut;
- an *axonometric* for mass, an *exploded axonometric* for layers that make one whole;
- an *abstract pictogram* (points and arrows) for a relationship without a place.

Frames share a viewpoint only when comparing them is the point; a set that uses one drawing for every move needs a reason. Moves that act in turn on one thing are a *sequence*: earlier moves in ink, the new one in the accent, what it removes dashed once where it was. A move may only use what earlier ones made: if the narrative's order breaks that, draw the enabling move first and say so. Separate strategies are *separate* pictograms on the same base. What exists before any move is never in the accent (`accent: false`).

**Make the geometry carry the move.** Show only what the move needs, give it its own spatial sign (a gap, a lifted layer, a link, a change in height; an arrow only for what moves or connects; the spec lists them), and prefer one clear form to many pieces: colour marks only what's new, it doesn't explain. Small, a pictogram shows only the idea, its primary geometry and key relationships; large, it keeps these and may add the secondary spatial information and labels the input supports. Label a word or two, only what the shape doesn't say, never with an assumed number. The caption is a title of up to five words and one sentence in the narrative's words, and says what the drawing says. Every footer says what is site data and what is concept; only a plan on site data gets a graphic scale. The look is never yours: put the colours, line weights and fonts of `drawing-graphics/standard.md` into the spec's `style`, or leave it out for the fallback. Write `spec.json` and render it as `${CLAUDE_SKILL_DIR}/spec.md` describes, look at every PNG, and change the spec until each frame reads without its caption and nothing overlaps.

Work in the proposal folder you're told, else the newest in the project's `proposals/`, else a new `<YYYY-MM-DD>_draft/`, and write only into its `concept-diagrams/`: an SVG and a PNG per pictogram, named after its move, `00_sheet` with all of them, `spec.json`, and `summary.md` in three lines:
1. The pictograms, sequence or separate, each one's drawing type and scale, and what must still read when it's small (a pictogram usually takes one column of a panel).
2. Their number.
3. What's conceptual rather than data, and the one thing you're unsure of.
