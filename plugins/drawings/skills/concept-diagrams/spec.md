# The spec for `draw_diagrams.py`

## Running it

Install once: `pip install "shapely>=2" pyproj numpy`, and Chrome, Edge or Chromium for the PNGs (set `CHROME_PATH` if it isn't found).

1. `python "${CLAUDE_SKILL_DIR}/scripts/draw_diagrams.py" info --site <site.geojson> --layer <name>=<layer.geojson>` prints the site and its lines in metres. Skip it with no site.
2. Write `spec.json` as below, in the proposal's `concept-diagrams/`.
3. `python "${CLAUDE_SKILL_DIR}/scripts/draw_diagrams.py" render spec.json .` writes an SVG (print size in mm) and a PNG per frame, named after its `file`, and `00_sheet`.
4. Read its warnings: a caption over about 90 characters runs into the footer; a label that still overlaps needs `label_at`; a move too small at the site's scale needs `focus`.

**Spatial signs.** An arrow only for what moves or connects; a barrier is an arrow stopped by a bar (`ends: stop`). An opening is a gap with its removed part dashed (`clears`). Alternating solid and void (slats, a porous edge, strips between fields) reads small only with fewer, wider members: draw the solids, let the voids be strips or `clears` gaps; the script draws a strip no thinner than `min_width` and warns. A crossing is a raised deck (a `volume` with `base`). Shelter or a landmark is height. Rays mark only the one place the story centres on. Placeholder blocks (`field`) serve moves that act on built mass; they aren't a design, and the footer says so.

## The file

Paths in `spec.json` are relative to it; coordinates are metres, x east and y north of the site's centre, as `info` prints them.

```json
{
  "mode": "sequence",
  "site": "<site.geojson>",
  "view": {"type": "iso", "rotation": 30, "tilt": 0.55, "exaggerate": 3},
  "size": [600, 560],
  "base": [{"name": "street", "geojson": "<streets.geojson>", "weight": "heavy", "label": "street"}],
  "field": {"cell": 105, "size": 60, "height": 10, "keep_off": ["street"], "keep_off_distance": 20},
  "frames": [
    {"file": "01_open-the-block", "title": "A block opened", "caption": "A passage opens the block to the street.",
     "elements": [{"kind": "strip", "coords": [[0, -150], [0, 150]], "width": 12, "clears": true}]}
  ]
}
```

- `mode`: `sequence` (each frame keeps the earlier moves in ink, its own in the accent) or `separate` (only its own move on the shared base).
- `site`: the site, one polygon or several, with holes; leave it out for a schematic set. `simplify` (metres, default 30) smooths its outline. `site_line`: `solid` (default), `dotted`, `pale` or `none`.
- `view`: `plan`, `iso` (axonometric), `section` or `elevation`; a frame's own `view` overrides it, carrying a sequence's earlier moves along.
  - `plan` with `cut_height` (metres) is a floor plan: what is cut is solid, what lies below outlined, what lies above (a roof, a void's edge, a lintel) dashed. Without it, seen from above.
  - `section` with `cut: [[x0, y0], [x1, y1]]` looks to the left of that line (from the first point toward the second): what is in front is left out, what is cut solid, what is behind in elevation.
  - `elevation` looks level from the south; `rotation` turns it (90 looks from the east).
  - Pictograms carry no graphic scale: the footer says "not to scale". Only the first frame on the site gets a north sign, so frames on the site keep one turn. `focus: [x0, y0, x1, y1]` frames a close-up, with an inset locating it.
- `size`: width and most height in px; the height shrinks to fit the site. The script draws to the print width of the narrowest frame panel-layout's first plan gives these pictograms, or to `width_mm` if set; the text keeps its size.
- `style`: only what the drawing standard gives; without it, black on white with one accent (values at the top of the script). Colours: `ink`, `paper`, `accent`; `font`. Line weights in px: `outline` (site), `line` (base), `heavy`, `box` (block edges), `thin`, `hatch`, `rule`, `sign` (new arrow, rays), `sign_old`, `ghost` (removed outlines), `leader`, `tee` (bar of a stopped arrow), `halo` (behind labels). Patterns: `dash`, `ghost_dash` (SVG dash arrays), `tint_opacity`, `solid_opacity`; `min_width` (px, the narrowest a strip is drawn). Signs in px: `glyph` (their line), `figure` (a person's height), `icon` (its diameter), `vignette` (its radius). Text in px: `label_size`, `small_size` (scale, north), `title_size`, `title_weight`, `caption_size`, `footer_size`, `footer_style`.
- `base`: site data in every frame, clipped to the site. `where` filters on properties: exact values, or a regular expression starting with `~`. Also `weight` (`heavy`), `dashed`, `label`, `only_in` (frame numbers), `margin` (metres beyond the site). With `color` (and `opacity`) a layer is a soft mass without lines, such as woods or water around the site (`outline: true` keeps its line); `smooth` rounds it.
- `field`: optional placeholder blocks for the moves to act on.
- `frames`: 3 to 6. `file` names the drawing after what it shows; `highlight` lists base layers that are its subject; `step` and `source` record which step of the argument it answers and where that comes from (the script ignores them). `hidden: true` makes a frame only a part for a row of `layers`: it gets no drawing of its own and no number. `family` puts a frame in a family. `group` names the topic a frame belongs to; frames of one topic share it. The script writes `groups.json` for panel-layout: each topic's frames, else each family, else a sequence as one; a hidden frame or one with `number: false` is left out unless it has a `group`.
- `families`: `{"<name>": {"title": "...", "mode": "sequence" | "separate"}}`. A sequence carries earlier moves forward only within its family, pale; `00_sheet` puts each family on its own row under its title. The script warns when one family mixes views or turns.
- `footer` overrides the line under each caption, which otherwise names the site data and another skill's GeoJSON, and calls the rest concept.

## Elements

Any element can carry `label` (only in its own frame; `label_at` and `label_z` set the point it names; the script moves it aside with a leader if it covers something), `accent: false` (in ink even in its own frame: what exists, or what the move serves), `z` (metres, for signs), `clears: true` (removes placeholder blocks and earlier volumes it overlaps, dashed once where they were, and cuts its gap through the areas under it; a pale strip cuts solid areas too; `clears: [z0, z1]` only that height range, such as a ground floor under a lintel), and `geojson` + `where` instead of coordinates.

| kind | geometry | for |
|---|---|---|
| `area` | `coords` polygon, `holes` | a ground surface: green, a square, a phase. `fill`: `tint` (later hatched), `solid` (later outlined), `none`. `marks: true` turns the blocks inside it to the accent. |
| `strip` | `coords` line, `width` | a corridor, a street, a link on the ground |
| `volume` | `coords` polygon, `holes`, `height` or `slope`, `base` | a building, a deck (`base` above 0), a landmark |
| `row` | `along` (a base name or a line), `offset`, `depth`, `segment`, `gap`, `sides`, `height` | a built edge along a line, cut into buildings |
| `point` | `at`, `radius` | a node: a stop, a meeting point |
| `arrow` | `coords`, `ends`: `end`, `both`, `stop` | a movement or relation; `[x, y, z]` points climb |
| `flow` | `coords`, `count`, `spread` | parallel arrows for a flow; only in its own frame |
| `rays` | `at`, `z` | the place the story centres on |
| `label` | `at`, `z`, `text`, `color` | a free label |
| `note` | `at`, `z`, `text` | why, in up to eight words, italic and muted |
| `tree` | `at`, `coords` (several), `along` (a base name or a line) with `spacing`, or `geojson` of points or lines; `crown`, `height` | trees: a crown with a trunk dot in plan, a trunk and a round crown in 3D, never smaller than a person reads |
| `person` | `at`, or `coords` for several; `pose` | people, upright in any view and `figure` px tall: `person`, `walker`, `child`, `cheer` (arms up), `sitter`, `cyclist`, `people` (a group) |
| `icon` | `at`, `sign` | a use or activity in a circle: a sign's name, or one or two letters |
| `vignette` | `at`, `scene` (sign names), `label`, `offset` | what people do at a place: a small round scene set beside it where it covers least, with a leader; `offset` ([dx, dy] px) places it |
| `layers` | `of` (frame numbers), `labels`, `sum`, `result`, `result_label` | the frame is a row: each of those frames' own move alone on the site, joined by +; `sum: true` or a label adds = and all of them together; `result` (a frame number) adds = and that frame's move instead, when what they add up to is a shape of its own, not their union. Default: every earlier frame |
| `metaphor` | `parts`: [{`draw`: sign names, `label`}], `join`: `arrow` or `plus` | the frame is the idea as an image, without the site: two or three scenes at one size, the last in the accent |
| `pie` | `charts`: [{`title`, `parts`: [{`value`, `label`, `accent`}], `source`}] | the frame is up to three pie charts at one size, for ratios from the proposal's tables; `source` names each table, and the footer lists them |

**Drawn like a diagram.** These change only what is drawn; every source file, area and number stays as it is.
- `color` on any element (and on a `base` layer): a colour by meaning, by its name in the drawing standard's `style.json` (such as `park`, `kept`, `meadow`, `water`, `existing`, `context`, `public`), or `accent` / `ink`; without a standard, the script's own set of those names. An area or strip with it is a soft fill without an edge (`opacity` sets how soft); a `point` with it is a soft zone; a volume takes it on its roof; an arrow, its line and head. A name the standard doesn't have is left out, with a warning.
- `simplify` (metres) drops detail, `smooth` (metres) rounds a shape and closes its small gaps, `curve: true` rounds a line's corners (arrows, flows, strips). The footer then says the outlines are simplified.
- `width` on an arrow (px): one broad arrow for the main move, its head drawn to match.
- `halo` (metres) on any element: a soft round zone behind its place, in `halo_color` (default `public`).
- Volumes: walls on paper, the side turned from the light a step darker, the roof in `color`, the accent if new, else a pale roof. `roof: "pitched"` puts a gable along the long side of a near-rectangle. `height_from` with `geojson` takes each building's height from that property of its feature (`height` where it has none).
- Trees: a crown in the standard's `park` green (or `color`) with a fine edge, each a little different in size; `cluster: 3` puts three trees as a group at each place.
- `note`: `at`, `text`: one short line in italic and a muted tone that says why, kept apart from the labels.
- In a `section`, `depth` (metres) limits what is drawn behind the cut; an area or strip the cut crosses is a band under the ground line (`band`: its height in px), labelled at its middle.
- `sign`: `sign` (a sign's name), `at` or `coords`, `size`: any sign upright on the ground, scaled like a person (crops on a field, a bench).
- A metaphor with `band` (a share of the height) and `text` takes the top of its frame, one sentence below it ties the idea to the place, and the frame's other elements are drawn beneath: the idea and what it becomes in one frame.
- `carries` on a frame: the facts it explains; two frames with the same fact get a warning, never a deletion.
- `number` on a frame: its number, or `false` for a frame titled only (one that sits on another panel). The others are numbered in order.
- `compositions`: `[{"file": "...", "size": [w, h], "parts": [{"frame": n, "share": 1}, {"text": {"title": "...", "body": "...", "points": ["..."]}, "share": 0.8}]}]` draws one wide drawing from parts side by side: hidden frames (a metaphor, an axonometric, a section) and a text part. It is not a pictogram; make it only for a panel frame that asks for it, under that frame's `file`. `00_sheet` shows it under the families.
- No drawing has a scale bar. Text is at least 12 px.

**Signs** for `pose`, `sign`, `scene` and `draw`: `person`, `walker`, `child`, `cheer`, `sitter`, `cyclist`, `people`, `tree`, `conifer`, `bench`, `table`, `ball`, `house`, `block`, `tower`, `stall`, `bed`, `crop`, `water`, `sun`, `wind`, `heart`, `bus`; also `home`, `market`, `shop`, `garden`, `farm`, `walk`, `bike`, `sit`, `play`, `community`. People, icons and vignettes are only in their own frame (`only_here: false` keeps them); a frame with them, or a metaphor, says in its footer that they are illustrative. A `layers` or `metaphor` frame shows only itself.

`holes` cut polygons out of `coords`, so courtyards read as one ring. `slope: [[x0, y0, h0], [x1, y1, h1]]` replaces `height`: the top rises evenly between the points, level beyond. `lift` (metres, on a volume or area) draws it higher with dashed lines down to its place: an exploded view, not a height.

**Sides of a row.** The line is turned to run south to north (west to east if more east–west); `1` is then its left, `-1` its right. Clearer: `"west"`, `"east"`, `"north"` or `"south"`. `offset` is metres from the line to the near face. Without `sides`, both.
