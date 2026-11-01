---
name: perspective
description: Chooses pedestrian-level viewpoints in a design and draws each as an accurate eye-level base view from the massing, with the existing buildings, vegetation, streets, rail, water and terrain around it, ready for an image model. Use when asked for perspectives, eye-level views, street views, or spatial representations of a design.
---
# Perspective

Reads: massing, drawing-graphics, narrative

Inputs: `massing/massing.geojson` in the proposal folder, the project's site folder, `narrative/narrative.md` for what the views should tell, the brief for how many views it asks for, and `drawing-graphics/standard.md` for the look. Never invent data: with no massing, stop and say so; everything else that's missing goes in `assumptions.md`. Work in the proposal folder you're told, else the newest in the project's `proposals/`, else a new `<YYYY-MM-DD>_draft/`, and write only into its `perspective/`.

Run `python "${CLAUDE_SKILL_DIR}/scripts/perspective.py" <proposal folder>`. Needs `pip install shapely pyproj numpy requests`, and Chrome or Edge. The site folder is found next to `proposals/` or through the project's `CLAUDE.md`; else pass `--site`. Terrain comes from `terrain.csv` (columns `lon, lat, ele`) in the site folder, else from a free open elevation service, sending only coordinates; if neither works the ground is flat and the summary says so. To follow `standard.md`, put its tones in a JSON file under `style`, and pass any corrected assumption in the same file, with `--options`.

Then check the result; the script can't. Open `views_map.png` and every `_base.png`: does each view show what the narrative needs? A view should read as buildings, public space, landscape and human scale together, with nothing blocking the eye. If not, change the view count or redraw edited cameras with `--views views.json`, and say why in `summary.md`. A view shows whatever the data shows, so read every warning: a warning you can't resolve stays in the summary. An image model works from `_base.png` and `_depth.png` and must not change the geometry; its result is `<view>.png`, and nothing here calls one.

Large, a view is judged on its floors and its edges; small, on its one spatial idea, so keep each view's subject simple. A perspective has no scale: never give one in `summary.md`.

**What it writes:** `view-N_base.svg` and `.png`, `view-N_depth.png`, `view-N_ids.png` (what each pixel is), `views_map.svg` and `.png`, `views.json` (each camera, why it was chosen, its scores), `candidates.csv`, `building_status.csv`, `terrain.csv` if fetched, `assumptions.md`, and `summary.md` in three lines: the views, how many from how many candidates, what you're unsure of. Files from a stand-in massing start with `TEST_` and say so in the summary.
