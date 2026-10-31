# Drawings

Skills that draw. Each decides what its drawing shows; how it looks comes from the studio's standard, and its scale comes from the brief.

- The standard: `drawing-graphics` reads the project's reference images (where its `CLAUDE.md` says, else `references/`) and writes `drawing-graphics/standard.md`. Every other drawing skill reads that file. Without it, draw black lines on white with one accent colour for what's new.
- Never fix a colour, line weight, font or scale in a drawing skill. Say what the drawing shows when it is large (a block, 1:500) and when it is small (the district in its city, 1:5000 and smaller), and take the scales from the brief's checklist.
- How: SVG written in code from the GeoJSON, not Rhino (see "The tools" in `STUDIO.md`). 3D drawings extrude the footprints by their heights; sections cut through them.
- Output: SVG with a PNG next to each, named after what it shows, and the drawings listed in `summary.md` with their scales.
- A new skill here: another kind of drawing, such as a street elevation, an exploded axonometric or a diagram of a process.
