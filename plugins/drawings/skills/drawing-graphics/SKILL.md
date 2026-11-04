---
name: drawing-graphics
description: Writes the drawing standard of a competition entry, the one every drawing and panel takes its look from. It starts from a best-practice base, fits it to the entry's narrative, then to the project's reference images if there are any. Use when asked for the look, the graphic standard, the style of the drawings, fonts, colours or line weights.
---

# Drawing graphics

Reads: brief-reader, narrative

Work in the proposal folder you are given and write only into `drawing-graphics/`. Three steps, each starting from the one before:

1. **The base.** Read `${CLAUDE_SKILL_DIR}/base.md` and copy `${CLAUDE_SKILL_DIR}/base.json` to `drawing-graphics/style.json`. This is the look when nothing else is decided.
2. **The narrative.** Read `narrative/summary.md` and the title and principles in `narrative/`. Let the idea choose what the base leaves open: the accent colour and the layer it marks (the public ground, a green corridor, the water, the air), whether the palette runs warm or cool, and which of the panel's drawings carries the most weight. Keep it to a few choices, and write each with the sentence of the narrative it comes from. If there is no narrative, keep the base and say so.
3. **The references.** If the project has reference images (where its `CLAUDE.md` says, else `references/`), look at each one once and take what they share: their colours, line weights, fonts, fills and hatching, and how much they leave white. Where they disagree with step 2, the references win, unless that breaks a floor. Without references, skip this step.

Never go below a floor of `base.md` (12 px text, the contrasts, the line weights). Take the panel format from `brief-reader/checklist.md`. Run `python "${CLAUDE_SKILL_DIR}/scripts/check_style.py" drawing-graphics/style.json` and fix what it names.

Write `drawing-graphics/standard.md`: the whole base, every section under its own heading (the renders too), never summed up, with your changes in place, and each change marked with where it came from (narrative or a reference image by name). Also write `style.json`, which the drawing scripts read, keeping every key of `base.json`. `summary.md`: three lines. The look in one sentence, the accent and what it marks, and what you're unsure of.
