# The spec for `draw_diagrams.py`

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
- `view`: `iso` or `plan`. A frame can override it with its own `view`, but only when its move needs a different view. `plan` draws a graphic scale; `iso` says "not to scale" and gives the height exaggeration. `focus: [x0, y0, x1, y1]` (metres) frames a close-up, with an inset that locates it on the site: for a move too small to read at the scale of the whole site.
- `size`: the width and the most height of the drawing, in px; the height shrinks to what the site needs.
- `style`: only from the drawing standard; leave out what it doesn't give, and the whole key without one. Colours: `ink`, `paper`, `accent`; `font`. Line weights in px at the drawing's size: `outline` (site), `line` (base lines), `heavy` (a base layer with `weight: heavy`), `box` (block edges), `thin`, `hatch`, `rule`, `sign` (a new arrow, rays), `sign_old` (an earlier one), `ghost` (removed outlines), `leader`, `tee` (the bar of a stopped arrow), `halo` (behind labels). Patterns: `dash`, `ghost_dash` (SVG dash arrays), `tint_opacity`, `solid_opacity`. Text in px: `label_size`, `small_size` (scale, north), `title_size`, `title_weight`, `caption_size`, `footer_size`, `footer_style`. The fallback values are at the top of the script.
- `base`: site data drawn in every frame, clipped to the site. `where` filters on properties: exact values, or a regular expression starting with `~`. Other keys: `weight` (`heavy`), `dashed`, `label`, `only_in` (a list of frame numbers), `margin` (metres shown beyond the site).
- `field`: optional neutral placeholder blocks for the moves to act on. They are not a design.
- `frames`: 3 to 6. `file` names the drawing after what it shows. `highlight` lists base layers that are this frame's subject.

## Elements

Every element can carry `label` (a word or two, shown only in its own frame; `label_at` and `label_z` set the point it names, and the script moves the text off the drawing, with a leader, when it would cover something), `accent: false` (drawn in ink even in its own frame: what the move serves rather than adds), `z` (height in metres for signs), `clears: true` (it takes away placeholder blocks and earlier volumes it overlaps; they show once as dashed outlines), and `geojson` + `where` instead of coordinates, for geometry from another skill's output.

| kind | geometry | what it is for |
|---|---|---|
| `area` | `coords` polygon | a ground surface: green, a square, a phase. `fill`: `tint` (later hatched), `solid` (later outlined) or `none`. `marks: true` turns the placeholder blocks inside it to the accent in its frame. |
| `strip` | `coords` line, `width` | a corridor, a street, a link on the ground |
| `volume` | `coords` polygon, `height`, `base` | a building, a deck (`base` above 0), a landmark |
| `row` | `along` (a base name or a line), `offset`, `depth`, `segment`, `gap`, `sides`, `height` | a continuous built edge along a line, cut into buildings |
| `point` | `at`, `radius` | a node: a stop, a meeting point |
| `arrow` | `coords`, `ends`: `end`, `both`, `stop` | a movement or a relation; `stop` ends in a bar, for a barrier |
| `flow` | `coords`, `count`, `spread` | parallel arrows for a flow (air, water, people); shown only in its own frame |
| `rays` | `at`, `z` | short rays: the one place the story centres on |
| `label` | `at`, `z`, `text`, `color` | a free label |

**Sides of a row.** The script first turns the line to run south to north (west to east if it runs more east–west), whatever order its data has. Then `1` is its left and `-1` its right: `1` is west of a north–south line and north of an east–west one. Clearer still, name the side: `"west"`, `"east"`, `"north"` or `"south"`. `offset` is metres from the line to the buildings' near face. Without `sides`, both.

`footer` overrides the line under each caption. Without it the script writes which layers are site data, which elements come from another skill's GeoJSON, and that everything else is concept.
