---
name: drawing-graphics
description: Writes the drawing standard of a competition entry, the one every drawing and panel takes its look from. It starts from a best-practice base, fits it to the entry's narrative, then to the project's reference images if there are any. Use when asked for the look, the graphic standard, the style of the drawings, fonts, colours or line weights.
---

# Drawing graphics

Reads: brief-reader, narrative

Work in the proposal folder you are given and write only into `drawing-graphics/`. Three steps, each starting from the one before:

1. **The base.** Read `${CLAUDE_SKILL_DIR}/base.md` and copy `${CLAUDE_SKILL_DIR}/base.json` to `drawing-graphics/style.json`. This is the look when nothing else is decided.
2. **The narrative.** Read `narrative/summary.md` and the title and principles in `narrative/`. Let the idea choose what the base leaves open: the accent colour and the layer it marks (the public ground, a green corridor, the water, the air), whether the palette runs warm or cool, and which of the panel's drawings carries the most weight. Keep it to a few choices, and write each with the sentence of the narrative it comes from. If there is no narrative, keep the base and say so.
3. **The references.** If the project has reference images (where its `CLAUDE.md` says, else `references/`), look at each one once, whole boards first if there are any, then kind by kind: plans, sections, isometrics, perspectives, diagrams, maps, each kind from the files the project names for it, else from what each image shows. For each kind, write a recipe of a few lines into `standard.md`, naming its images: what they share in colours, line weights, fonts, fills and hatching, trees and people, labels, and how much they leave white. Where they disagree with step 2, the references win, unless that breaks a floor. Set the keys of `style.json` the recipes change, `render_style` from the perspectives, `storey_labels` from the plans, `diagram` from the diagrams and `modes` from the maps among them (each way of moving named by one of the standard's own colour keys, a different one for each, never a new colour, so the maps share the plans' palette). Take their look, never their texts or titles. Without references, skip this step.

Never go below a floor of `base.md` (12 px text, the contrasts, the line weights). Take the panel format from `brief-reader/checklist.md`. Run `python "${CLAUDE_SKILL_DIR}/scripts/check_style.py" drawing-graphics/style.json` and fix what it names.

Write `drawing-graphics/standard.md`: the whole base, every section under its own heading (the renders too), never summed up, with your changes in place, and each change marked with where it came from (narrative or a reference image by name). Also write `style.json`, which the drawing scripts read, keeping every key of `base.json`. `summary.md`: three lines. The look in one sentence, the accent and what it marks, and what you're unsure of.
