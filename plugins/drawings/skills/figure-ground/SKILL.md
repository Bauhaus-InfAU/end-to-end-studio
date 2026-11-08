---
name: figure-ground
description: Draws the figure-ground plan of a district in its city at the brief's scale, the buildings as flat tones on white and nothing else, the new buildings darkest against an existing city that fades away from the site. Use when asked for the figure-ground, a figure-ground diagram, a Schwarzplan or the district in its urban context.
---
# Figure-ground

Reads: site-kit, massing
Reads (end): drawing-graphics, panel-layout

Write only into `figure-ground/` in the proposal folder. Run `python "${CLAUDE_SKILL_DIR}/scripts/figure_ground.py" --proposal <proposal folder> --site <site folder>` (`pip install shapely pyproj`; Chrome or Edge for the PNG); its options and their defaults are at the top of the script. Look at the PNG once, and fix the script, never the drawing.

**What it shows.** Only buildings, as flat fills without outlines on white paper: the design's new buildings darkest, the existing city in a mid grey, and outlying quarters away from the site lighter, so the city fades out around the project; a quarter keeps one tone, never a seam through it. The massing owns the site: the existing buildings there give way to its kept and new ones. Touching footprints become one mass, courtyards and gaps stay open, and walls the data models as buildings (noise barriers) are left out and counted. No streets, rail, water, trees, site boundary or legend: the site reads from where the dark buildings are. Without a massing, draw the city as it is and say the design is missing.

**Size, look and summary.** Take the scale, frame and centre from the panels' plan when it frames the figure-ground, else the brief's scale from its checklist. The plan fills its frame, centred on the new buildings, and runs off its edges; where the site data is smaller than the frame, cut the plan to the data and say so rather than print blank paper. Under it go the title and the written scale, a graphic scale, north and the site data's credits. Colours, font and line weights come from the drawing standard, else its base, else plain greys. Write `figure-ground_1-<scale>.svg` and `.png`, and `summary.md` in three lines: what was drawn, at which scale and size; the new footprint against the existing in the frame; what you are least sure of.
