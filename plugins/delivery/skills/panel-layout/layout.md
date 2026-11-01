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
  "required": [{"what": "site plan 1:2,000", "source": "brief, page", "id": "site-plan"}],
  "missing":  ["anything else the report should name"],
  "panels": [
    {"story": "what this panel tells, from the storyline",
     "items": [
       {"id": "title", "type": "text", "text": "...", "pt": 48, "weight": 700, "h": 40},
       {"id": "site-plan", "type": "drawing", "file": "plans/site-plan.svg", "scale": "1:2000",
        "scale_bar": true, "caption": "Site plan"},
       {"id": "idea", "type": "text", "heading": "...", "text": "paragraph\n\nparagraph", "w": 180, "h": 90},
       {"id": "figures", "type": "figures", "heading": "Key figures", "w": 180, "h": 60,
        "rows": [["label", "value with unit", "source"]]}
     ]}
  ]
}
```

- `reserved` and `marks` repeat on every panel. A box the brief puts in a corner sits at that corner, not inside the margin. In `marks`, `y` is the top of the text, `{n}` is the panel number, `{total}` the count, and every key of `labels` works too. `align: right` measures `x` from the right edge.
- Items without `x` and `y` flow left to right, top to bottom, in the order given, below the reserved areas, or from `format.content_top_mm` if you give it. Give `x` and `y` to fix one.
- A drawing with a `scale` keeps the print size its SVG gives (width and height in mm); `w` is then ignored. A drawing without a scale is sized by `w` or `h`. `scale_bar: true` adds a graphic scale under a drawing that has none. The scale is added to the caption: don't write it there yourself.
- A text or figures box has the `w` and `h` you give (default: full width, 60 mm). `pt` and `weight` set the size of a text item's text. If its text is longer, the report says how much height it needs.
- `required` lists what the brief asks to see, with the `id` of the item that shows it, or no `id` if nothing does. `missing` is only for what the scan didn't already find missing.
