# The spec for `draw_diagrams.py`

## Running it

Install once: `pip install "shapely>=2" pyproj numpy`, and Chrome, Edge or Chromium for the PNGs (set `CHROME_PATH` if it isn't found).

1. `python "${CLAUDE_SKILL_DIR}/scripts/draw_diagrams.py" info --site <site.geojson> --layer <name>=<layer.geojson>` prints the site and its lines in metres. Skip it with no site.
2. Write `spec.json` as below, in the proposal's `concept-diagrams/`.
3. `python "${CLAUDE_SKILL_DIR}/scripts/draw_diagrams.py" render spec.json .` writes one SVG (its print size in mm) and one PNG per frame, named after the frame's `file` (e.g. `02_<move>.svg`), and `00_sheet`.
4. Read its warnings: a caption longer than about 90 characters runs into the footer; a label that still overlaps needs its `label_at`. A move too small to read at the scale of the site needs a close-up (`focus`).

**Style.** Put every colour, line weight, font and text size the project's drawing standard gives into `style`, under the keys listed below, and none of your own. Keys it doesn't give, and the whole `style` without a standard, fall back to black lines on white with one accent colour.

**Spatial signs.** An arrow only for what moves or connects (air, water, people, a link). A barrier is an arrow stopped by a bar (`ends: stop`). An opening is a gap with its removed part dashed (`clears`). A crossing is a raised deck (a `volume` with `base`). Shelter or a landmark is height. Rays mark only the one place the story centres on. Neutral placeholder blocks (`field`) are allowed for moves that act on built mass; they aren't a design, and the footer says so. A number the narrative marks as assumed isn't a label: name the thing ("lower housing"); the footer already says sizes are assumed.

## The file

One JSON file, `spec.json`, describes the whole set. Paths in it are relative to the spec. Coordinates are metres, x east and y north of the site's centre, as `draw_diagrams.py info` prints them.

```json
{
  "mode": "sequence",
  "site": "../../../site/site.geojson",
  "simplify": 30,
  "view": {"type": "iso", "rotation": 30, "tilt": 0.55, "exaggerate": 3},
  "size": [600, 560],
  "base": [
    {"name": "rail", "geojson": "../../../site/rail.geojson", "where": {"railway": "rail"}, "weight": "heavy", "label": "railway"}
  ],
  "field": {"cell": 105, "size": 60, "height": 10, "keep_off": ["rail"], "keep_off_distance": 20},
  "frames": [
    {"file": "01_the-line", "title": "A site cut in two", "caption": "The railway divides the site.",
     "highlight": ["rail"],
     "elements": [{"kind": "arrow", "coords": [[-400, 100], [-30, 100]], "ends": "stop"}]}
  ]
}
```

- `mode`: `sequence` (each frame keeps the earlier moves, in ink, and its own in the accent) or `separate` (each frame shows only its own move on the shared base).
- `site`: the site polygon. Leave it out for a schematic set with no place.
- `view`: `plan`, `iso` (axonometric), `section` or `elevation`. A frame overrides it with its own `view` when its move reads better in another; in a sequence the earlier moves are carried into that view.
  - `plan` with `cut_height` (metres) is a floor plan: what the cut passes through is solid (ink, or the accent if new), what lies below is outlined, what lies above (a roof, a void's edge, a lintel) is dashed. Without `cut_height` it is seen from above, roofs and all.
  - `section` with `cut: [[x0, y0], [x1, y1]]` cuts along that line and looks to its left (from the first point toward the second): what lies in front is left out, what the cut passes through is solid, what lies behind is seen in elevation. Draw the cut where the relationship is: through the void, the insertion, the stair or lift.
  - `elevation` is seen level from the south, heights only, on a ground line; `rotation` turns it (90 looks from the east). Use it when there is no inside to cut. A `plan` on site data draws a graphic scale; without a site, and in `iso` and `elevation`, the footer says "not to scale" (and gives the height exaggeration) and no numbers are drawn. `focus: [x0, y0, x1, y1]` (metres) frames a close-up, with an inset that locates it on the site: for a move too small to read at the scale of the whole site.
- `size`: the width and the most height of the drawing, in px; the height shrinks to what the site needs.
- `style`: only from the drawing standard; leave out what it doesn't give, and the whole key without one. Colours: `ink`, `paper`, `accent`; `font`. Line weights in px at the drawing's size: `outline` (site), `line` (base lines), `heavy` (a base layer with `weight: heavy`), `box` (block edges), `thin`, `hatch`, `rule`, `sign` (a new arrow, rays), `sign_old` (an earlier one), `ghost` (removed outlines), `leader`, `tee` (the bar of a stopped arrow), `halo` (behind labels). Patterns: `dash`, `ghost_dash` (SVG dash arrays), `tint_opacity`, `solid_opacity`. Text in px: `label_size`, `small_size` (scale, north), `title_size`, `title_weight`, `caption_size`, `footer_size`, `footer_style`. The fallback values are at the top of the script.
- `base`: site data drawn in every frame, clipped to the site. `where` filters on properties: exact values, or a regular expression starting with `~`. Other keys: `weight` (`heavy`), `dashed`, `label`, `only_in` (a list of frame numbers), `margin` (metres shown beyond the site).
- `field`: optional neutral placeholder blocks for the moves to act on. They are not a design.
- `frames`: 3 to 6. `file` names the drawing after what it shows. `highlight` lists base layers that are this frame's subject.

## Elements

Every element can carry `label` (a word or two, shown only in its own frame; `label_at` and `label_z` set the point it names, and the script moves the text off the drawing, with a leader, when it would cover something), `accent: false` (drawn in ink even in its own frame: what already exists, and what the move serves rather than adds; cut in a plan or section, it is solid in ink), `z` (height in metres for signs), `clears: true` (it takes away placeholder blocks and earlier volumes it overlaps; they show once as dashed outlines, where they were: at their height in 3D and in a section; `clears: [z0, z1]` takes away only what lies in that height range, such as the ground floor of a wall under its lintel), and `geojson` + `where` instead of coordinates, for geometry from another skill's output.

| kind | geometry | what it is for |
|---|---|---|
| `area` | `coords` polygon, `holes` | a ground surface: green, a square, a phase. `fill`: `tint` (later hatched), `solid` (later outlined) or `none`. `marks: true` turns the placeholder blocks inside it to the accent in its frame. |
| `strip` | `coords` line, `width` | a corridor, a street, a link on the ground |
| `volume` | `coords` polygon, `holes`, `height` or `slope`, `base` | a building, a deck (`base` above 0), a landmark; a ring around courtyards (`holes`); a mass that rises (`slope`) |
| `row` | `along` (a base name or a line), `offset`, `depth`, `segment`, `gap`, `sides`, `height` | a continuous built edge along a line, cut into buildings |
| `point` | `at`, `radius` | a node: a stop, a meeting point |
| `arrow` | `coords`, `ends`: `end`, `both`, `stop` | a movement or a relation; `stop` ends in a bar, for a barrier. Points `[x, y, z]` give it a height at each point: a route that climbs. |
| `flow` | `coords`, `count`, `spread` | parallel arrows for a flow (air, water, people); shown only in its own frame |
| `rays` | `at`, `z` | short rays: the one place the story centres on |
| `label` | `at`, `z`, `text`, `color` | a free label |

**Holes, slopes, lifts.** `holes` is a list of polygons cut out of `coords`: courtyards in one ring, drawn as one form rather than many blocks. `slope: [[x0, y0, h0], [x1, y1, h1]]` replaces `height`: the top rises evenly from `h0` at the first point to `h1` at the second and stays level beyond them, so one volume shows one continuous slope. `lift` (metres, on a volume or an area) draws the element that much higher with dashed lines down to where it belongs: an exploded view of layers that sit on one another. A lift is a way of drawing, not a height.

**Sides of a row.** The script first turns the line to run south to north (west to east if it runs more east–west), whatever order its data has. Then `1` is its left and `-1` its right: `1` is west of a north–south line and north of an east–west one. Clearer still, name the side: `"west"`, `"east"`, `"north"` or `"south"`. `offset` is metres from the line to the buildings' near face. Without `sides`, both.

`footer` overrides the line under each caption. Without it the script writes which layers are site data, which elements come from another skill's GeoJSON, and that everything else is concept.
