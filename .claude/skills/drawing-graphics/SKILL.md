---
name: drawing-graphics
description: The studio's drawing standard. Read it before making any drawing for the entry (figure-ground, masterplan, detail plans, sections, isometric, building types, diagrams), so all three panels look like one studio.
---

# Drawing graphics

Reads: nothing

Black lines on white, as SVG. Hierarchy comes from line weight and grey. Colour is one accent, red `#c8102e`, and it marks only what's new: the new buildings, the new routes, the site boundary. If a drawing needs a second colour to be read, the drawing is wrong, not the palette. What is new and what is cut is heaviest. What already exists is light.

| Weight | mm at print scale | Use |
| --- | --- | --- |
| heavy | 0.50 | cut walls, outlines of new buildings at 1:1000 and larger |
| medium | 0.25 | new streets and paths, outlines of new buildings at 1:5000 |
| thin | 0.13 | existing buildings, kerbs, trees, plot lines |
| hairline | 0.08 | hatches, contour lines, dimension lines |

- Fills: existing buildings `#d9d9d9` in plans, black only in the figure-ground. New buildings white with a heavy outline, or the accent at 1:5000. Green space `#eef0ea`, water `#e4ecf0`. No gradients, no shadows, no textures.
- Text: one sans-serif font (Helvetica or Arial), two sizes only, 2.5 mm for labels and 3.5 mm for titles, at print size on A1. Place names in capitals, letter-spaced.
- Every plan gets a north arrow (a plain N with a short line), a scale bar in metres and the scale written next to it. The title goes bottom left, in one line: drawing, scale.
- Label less than you think. If a line needs a legend to be understood, change the line.
- Attribution from `proposal/site-kit/SOURCES.md` in hairline text along the bottom edge.
