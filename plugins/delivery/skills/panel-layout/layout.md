# layout.json

What `scripts/panels.py render` reads. All lengths in mm, measured from the panel's top-left corner. Every value that comes from the brief or the standard says where in `source`.

```json
{
  "format":   {"width_mm": 0, "height_mm": 0, "panels": 0, "margin_mm": 15, "gutter_mm": 8,
               "max_mb": 0, "source": "brief, page"},
  "style":    {"font": "...", "text": "#000", "background": "#fff", "accent": "#...", "line_mm": 0.25,
               "heading_pt": 20, "body_pt": 11, "source": "standard.md, or: no standard"},
  "labels":   {"title": "...", "site": "..."},
  "reserved": [{"x": 0, "y": 0, "w": 0, "h": 0, "what": "code box, left blank", "source": "brief, page"}],
  "marks":    [{"text": "{site}", "x": 0, "y": 0, "pt": 14},
               {"text": "{n}", "x": 15, "y": 10, "pt": 40, "align": "right"}],
  "required": [{"what": "site plan 1:2,000", "source": "brief, page", "id": "site-plan",
                "file": "plans/site-plan_1-2000.svg", "by": "plans"}],
  "missing":  ["anything else the report should name"],
  "panels": [
    {"story": "what this panel tells, from the storyline",
     "items": [
       {"id": "title", "type": "text", "text": "...", "pt": 48, "weight": 700, "h": 40},
       {"id": "site-plan", "type": "drawing", "file": "plans/site-plan_1-2000.svg", "scale": "1:2000",
        "frame": {"w": 0, "h": 0}, "shows": "what this drawing must show, from the storyline",
        "scale_bar": true, "caption": "Site plan"},
       {"id": "idea", "type": "text", "heading": "...", "text": "paragraph\n\nparagraph", "w": 180, "h": 90},
       {"id": "figures", "type": "figures", "heading": "Key figures", "w": 180, "h": 60,
        "rows": [["label", "value with unit", "source"]]},
       {"id": "homes", "type": "number", "value": "1,000", "text": "homes", "source": "massing, summary", "w": 90, "h": 30}
     ]}
  ]
}
```

- `reserved` and `marks` repeat on every panel. A box the brief puts in a corner sits at that corner, not inside the margin. In `marks`, `y` is the top of the text, `{n}` is the panel number, `{total}` the count, and every key of `labels` works too. `align: right` measures `x` from the right edge.
- Items without `x` and `y` flow left to right, top to bottom, in the order given, below the reserved areas, or from `format.content_top_mm` if you give it. Give `x` and `y` to fix one.
- A drawing with a `scale` (the brief's) is printed at it, rescaled from the scale it is drawn at (its file name such as `_1-2000`, else its summary, or `drawn_at`); `w` is then ignored. `"frame": {"w": 0, "h": 0}` clips it to that box; `"crop": {"focus": [0.5, 0.5]}` puts that point of the drawing (shares of its width and height) at the frame's centre, `{"offset_mm": [0, 0]}` shifts it left and up instead. `"scale": "auto"` picks the largest usual scale at which it fits its frame (default: the content area), never one that brings its text under 12 px, and crops the rest. A drawing without a scale is sized by `w` or `h`. A drawing with a `frame` whose `file` doesn't exist yet prints as a grey frame labelled with its id, scale and `shows`, and the report names it as an empty frame; without a `frame` it is missing. Drawing skills read `frame`, `scale`, `file` and `shows` to draw to it. `scale_bar: true` adds a graphic scale under a drawing; `"scale_bars": "all"` in `format` adds one under every drawing at a scale that has none of its own (never a perspective), and `scale_bar: false` keeps one off. The printed scale is added to the caption, or replaces the scale written there.
- A text or figures box has the `w` and `h` you give (default: full width, 60 mm). `pt` and `weight` set the size of a text item's text. If its text is longer, the report says how much height it needs.
- A `number` is one key figure as big type: `value` in the accent at `pt` (default twice the heading size), `text` under it, and its `source` in one line under that. The report names a number without a source, and a source too long for one line as an overflow. It names a `figures` table that no `required` item points to; each panel's largest blank block as the rendered panel shows it, empty parts of frames and text boxes included (with `--check`, which has no browser, only the space between the items), when a drawing of that panel would fit in it or it is at least `format.blank_min_side_mm` each way and `format.blank_min_cm2` large (defaults 60 mm and 150 cm²); and a caption that repeats the title its drawing prints. These go to `issues.md`, the blank to the skill whose planned drawing didn't fit where it lies, else to panel-layout, and not into the problem count.
- `required` lists what the brief asks to see, with the `id` of the item that shows it, or no `id` if nothing does; `file` is the drawing that shows it and `by` the skill that makes it. The report tells a required drawing whose `file` exists but isn't on the panels from one that is missing. `issues.md` names the responsible skill for each issue: `by`, else the folder the file is in, else unknown. A required drawing whose frame hides more than `format.max_crop_required` of it (default 0.25) is reported as cropped, not as on the panels. `missing` is only for what the scan didn't already find missing; `notes` is for anything else the report should say, such as two numbers that don't agree. `figures` rows with the same label and different values are reported until `notes` names the label.
- `layout-plan.json`, the first run's plan, is what every later `render` checks against: the report names a planned item that is gone and a planned drawing whose file, scale or frame changed. `--check` checks and reports without a browser.
