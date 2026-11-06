---
name: art-direction
description: Puts each drawing of a competition entry beside the project's reference drawings of the same kind and writes, for each drawing skill, at most three concrete fixes it can carry out when it draws again. Use after the drawings and before the final panels, when asked for an art direction, a critique of the drawings against the references, or what to redraw.
---
# Art direction

Reads: every drawings (end)
Model: opus

Work in the proposal folder you are given, else the newest in the project's `proposals/`; write only to its `art-direction/`. You judge; you never draw or change another skill's files. Read the summary of each drawing skill, the standard in `drawing-graphics/`, and the project's reference images (where its `CLAUDE.md` says, else `references/`) with the file there that says which images are of which kind. If the proposal folder has side-by-side sheets in `.compare/` (references left, ours right, at one print size), look at each once; else open each drawing's PNG beside the references of its kind. Without references, compare with the standard alone and say so in `summary.md`.

For each drawing, find the largest differences from its references, the ones you see first from across the room: what is drawn and what is left out, the amount of detail, the weight of the figure against the ground, the hierarchy, the labels, how the drawing fills its frame. Turn the largest into at most three fixes per skill, each one its scripts can carry out and you could check, saying what to change and by how much ("draw the street trees as crowns at every scale", "label each centre with its uses, as the references do", "crop to the new district and 100 m around it"), never "make it richer". A fix asks only for what a design layer, the narrative or the standard gives, never for invented data. A gap in colour, line weight or font belongs to the standard: name it in `notes.md`, not as a fix. Never copy a reference's text, title or name. A skill whose drawings already come close gets no fixes.

Write `art-direction/fixes.json` as `{"<skill>": ["fix", ...]}`, only for skills that drew something, `{}` when none needs a fix. Write `notes.md`: per drawing, the references you compared it with and the differences, largest first. End with `summary.md` in three lines: how many fixes for how many skills; the largest gap; what you're unsure of.
