---
name: drawing-graphics
description: The office's drawing standard. Read it before making any architectural drawing (site plan, floor plan, section, elevation, detail, axonometric), so every sheet looks like it came from one office.
---

# Drawing graphics

Black lines on white, as SVG. Hierarchy comes from line weight and grey, never from colour. The one exception is the site boundary, in red. What is new and what is cut is heaviest. What already exists or is seen beyond is light. If two things look equally important, one of them is wrong.

| Weight | mm at print scale | Use |
| --- | --- | --- |
| heavy | 0.50 | cut walls, the outline of new buildings |
| medium | 0.25 | roof edges and steps of new buildings, kerbs, outlines of existing buildings in plan |
| thin | 0.13 | joints, paving, trees, plot lines, everything seen beyond the cut |
| hairline | 0.08 | hatches, dimension lines |

- Fills: new buildings solid `#1a1a1a` in a site plan and white with a heavy outline in plans, existing buildings `#d9d9d9`, open ground white. No gradients, shadows or textures.
- Site boundary: red `#c8102e`, 0.35 mm, dash-dot.
- Text: one sans-serif font (Helvetica or Arial), two sizes only, 2.5 mm for labels and 3.5 mm for titles. Street and place names in capitals, letter-spaced.
- Every drawing gets a north arrow (a plain open arrow with N), a scale bar in metres, and the scale written next to it (1:500). Titles go bottom left, in one line: drawing, scale, site.
- Label less than you think. If a line needs a legend to be understood, change the line.
- Attribution in hairline text along the bottom edge, when city kit data is drawn.
