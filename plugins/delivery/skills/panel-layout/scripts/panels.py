"""Panels for a competition entry, in two steps.

  python panels.py scan   <proposal folder>
      Lists every summary, drawing, table and text in the proposal folder, with each
      drawing's print size, and writes panel-layout/inventory.json.

  python panels.py render <proposal folder>/panel-layout/layout.json [--png-dpi 96] [--check] [--plan]
      Places the items of layout.json on the panels, each drawing with a scale in its frame
      at a true scale, cropped by the frame's edge; renders panel-N.html/.pdf/.png with a
      headless Chrome or Edge, checks the result and writes panel-layout/report.md.
      --check: only the check and report.md, no browser, no PDF or PNG.
      The first render saves the planned drawings to panel-layout/plan.json, and every later
      render names a planned drawing that is gone; --plan saves the plan again.

Needs Python 3.11+ and Chrome, Edge or Chromium. Set BROWSER to its path if it isn't found.
"""

import argparse
import csv
import html
import json
import os
import re
import secrets
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

OWN = "panel-layout"
DRAWING_EXT = {".svg", ".png", ".jpg", ".jpeg"}
MM_PER = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72, "pc": 25.4 / 6}
PX_MM = 25.4 / 96  # CSS pixel
MIN_PT = 9  # 12 px: no text on a panel is smaller, whatever the layout or the standard asks
MIN_TEXT_MM = MIN_PT * 25.4 / 72
COLUMN_EM = 32  # a text wider than this is set in columns, about 65 characters a line
DEFAULTS = {
    "usual_scales": [200, 500, 1000, 2000, 2500, 3000, 5000, 10000, 15000, 20000, 25000],  # what "scale": "auto" picks from
    "max_enlarge": 1.5,  # "auto" never prints a drawing larger than this times its own size: its lines grow with it
    "max_crop": 0.5,     # a drawing whose frame hides more than this share of its area is flagged
    "max_crop_required": 0.25,  # the same for a drawing the brief requires; over it, it doesn't count as on the panels
    "unscaled": ["perspective"],  # a drawing whose path holds one of these never gets a scale bar
    # a source that is a file of the proposal folder is printed as "<skill>, <its name> <what it is>";
    # a file name here is printed as its words alone, an extension not here as the skill's name alone
    "source_words": {"summary.md": "summary", ".csv": "table", ".json": "figures", ".geojson": "layer",
                     ".md": "text", ".txt": "text", ".svg": "drawing", ".png": "image", ".jpg": "image"},
}
FILE_SCALE_RE = re.compile(r"(?:^|[_\-.])1[-_](\d{2,6})(?=$|[_\-.])")  # "plan_1-2000"
FONT_RE = re.compile(r"font-size\s*[:=]\s*[\"']?\s*([\d.]+)\s*(px|pt|mm|cm|in|pc)?", re.I)
# a drawing's own scale bar: an element named scale-bar, or a text "0" with a text such as "200 m" or "1 km"
BAR_NAME_RE = re.compile(r"(?:id|class)\s*=\s*[\"'][^\"']*scale[-_ ]?bar", re.I)
BAR_ZERO_RE = re.compile(r">\s*0\s*<")
BAR_END_RE = re.compile(r">\s*\d[\d.,]*\s*k?m\s*<")
PATH_RE = re.compile(r"(?<![\w/.:-])((?:[\w-][\w.-]*/)*[\w-][\w.-]*\.[a-z][a-z0-9]{1,6})(?![\w/])")  # "open-space/sealing.csv"


def pt_(v):
    return max(float(v), MIN_PT)
SCALE_RE = re.compile(r"1\s*:\s*(\d{1,3}(?:[,.  ]\d{3})+(?!\d)(?!\s*(?:k?m|ha)\b)|\d+)")


# ---------- scan ----------

def svg_size(path):
    """Print size of an SVG in mm, if its width and height carry a physical unit; else its aspect."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        return {"error": f"not readable SVG: {e}"}
    out = {}
    w, h = root.get("width"), root.get("height")
    vb = root.get("viewBox")
    if vb:
        parts = [float(v) for v in re.split(r"[\s,]+", vb.strip())]
        if len(parts) == 4 and parts[2] > 0 and parts[3] > 0:
            out["aspect"] = parts[3] / parts[2]
    for name, val in (("w", w), ("h", h)):
        m = re.fullmatch(r"\s*([\d.]+)\s*([a-z%]*)\s*", val or "")
        if m and m.group(2) in MM_PER:
            out[f"{name}_mm"] = float(m.group(1)) * MM_PER[m.group(2)]
        elif m and m.group(2) in ("", "px"):
            out[f"{name}_px"] = float(m.group(1))
    if "w_mm" in out and "h_mm" in out:
        out["aspect"] = out["h_mm"] / out["w_mm"]
    elif "w_px" in out and "h_px" in out and "aspect" not in out:
        out["aspect"] = out["h_px"] / out["w_px"]
    if "w_mm" in out:
        out["text_mm"] = svg_text_mm(path, out["w_mm"], vb)
    src = Path(path).read_text(encoding="utf-8", errors="replace")
    out["scale_bar"] = bool(BAR_NAME_RE.search(src) or (BAR_ZERO_RE.search(src) and BAR_END_RE.search(src)))
    return out


def unscaled(file, defaults=DEFAULTS):
    return any(w in str(file).lower() for w in defaults["unscaled"])


def source_words(text, folder, defaults=DEFAULTS):
    """Every path of a file of the proposal folder in text, such as "open-space/sealing.csv" or a bare
    "sealing.csv" found once in it, turned into words: "open-space, sealing table". Other text stays."""
    folder = Path(folder)
    words = defaults["source_words"]

    def one(m):
        p = Path(m.group(1))
        if len(p.parts) > 1:
            if not (folder / p.parts[0]).is_dir() or p.parts[0] == OWN:
                return m.group(0)
            skill = p.parts[0]
        else:
            found = [f for f in folder.glob(f"*/**/{p.name}") if f.is_file() and f.relative_to(folder).parts[0] != OWN]
            if len(found) != 1:
                return m.group(0)
            skill = found[0].relative_to(folder).parts[0]
        what = words.get(p.name.lower())
        if what is None and p.suffix.lower() in words:
            stem, kind = re.sub(r"[_-]+", " ", p.stem).strip(), words[p.suffix.lower()]
            what = stem if stem.lower().endswith(kind) else f"{stem} {kind}"
        return f"{skill}, {what}" if what else skill
    return PATH_RE.sub(one, text) if "." in text else text


def printed_caption(caption, sc):
    """The caption with the printed scale: added when it holds none, put in place of any other it holds."""
    printed = f"1:{sc:,}"
    return SCALE_RE.sub(printed, caption) if SCALE_RE.search(caption) else f"{caption} · {printed}"


def svg_text_mm(path, w_mm, vb):
    """Printed height in mm of the smallest font size an SVG declares; None if it has no text.
    Sizes set by a scaling transform around the text are not seen."""
    src = Path(path).read_text(encoding="utf-8", errors="replace")
    if "<text" not in src:
        return None
    vb_w = float(re.split(r"[\s,]+", vb.strip())[2]) if vb else w_mm / PX_MM
    unit_mm = w_mm / vb_w  # one user unit, printed
    sizes = [float(v) * (1 if not u or u.lower() == "px" else MM_PER[u.lower()] / PX_MM)
             for v, u in FONT_RE.findall(src) if float(v) > 0] or [16]  # 16 px when none is set
    return round(min(sizes) * unit_mm, 3)


def raster_size(path):
    """Pixel size (and print size if the PNG says its resolution) of a PNG or JPEG."""
    data = Path(path).read_bytes()
    out = {}
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        out.update(w_px=w, h_px=h, aspect=h / w)
        i = data.find(b"pHYs")
        if i > 0:
            ppx, ppy, unit = struct.unpack(">IIB", data[i + 4:i + 13])
            if unit == 1 and ppx > 0:  # pixels per metre
                out["dpi"] = round(ppx * 0.0254)
    elif data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                out.update(w_px=w, h_px=h, aspect=h / w)
                break
            i += 2 + seg
    return out


def scale_hint(stem, summary):
    """The scale a skill gives for this drawing: in its file name, else on the summary.md line naming it,
    else the only one the summary gives."""
    in_name = FILE_SCALE_RE.findall(stem)
    if in_name:
        return f"1:{in_name[-1]}"
    lines = summary.splitlines()
    key = stem.lower().replace("_", "-")
    for line in lines:
        at = line.lower().replace("_", "-").find(key)
        if at >= 0:
            m = SCALE_RE.search(line, at) or SCALE_RE.search(line)
            if m:
                return "1:" + re.sub(r"[^\d]", "", m.group(1))
    found = {re.sub(r"[^\d]", "", m.group(1)) for m in SCALE_RE.finditer(summary)}
    return f"1:{found.pop()}" if len(found) == 1 else None


def scan(folder):
    folder = Path(folder).resolve()
    inv = {"proposal": str(folder), "skills": {}, "drawings": [], "tables": [], "texts": [],
           "checklist": None, "standard": None, "missing": [], "no_scale_bar": []}  # at a scale, no scale bar of its own
    for sub in sorted(p for p in folder.iterdir() if p.is_dir() and p.name != OWN and not p.name.startswith(".")):
        summary_path = sub / "summary.md"
        summary = summary_path.read_text(encoding="utf-8", errors="replace") if summary_path.exists() else ""
        inv["skills"][sub.name] = {"summary": summary.strip() or None}
        if not summary:
            inv["missing"].append(f"{sub.name}/summary.md")
        for f in sorted(sub.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(folder).as_posix()
            ext = f.suffix.lower()
            if ext in DRAWING_EXT:
                if ext == ".png" and f.with_suffix(".svg").exists():
                    continue  # the PNG next to an SVG is its preview; the SVG is placed
                d = {"file": rel, "skill": sub.name, "stem": f.stem}
                d.update(svg_size(f) if ext == ".svg" else raster_size(f))
                d["scale_hint"] = scale_hint(f.stem, summary)
                inv["drawings"].append(d)
                if d["scale_hint"] and d.get("scale_bar") is False and not unscaled(rel):
                    inv["no_scale_bar"].append(rel)
            elif ext == ".csv":
                with open(f, newline="", encoding="utf-8", errors="replace") as fh:
                    rows = list(csv.reader(fh))
                inv["tables"].append({"file": rel, "columns": rows[0] if rows else [], "rows": max(len(rows) - 1, 0)})
            elif ext == ".md" and f.name != "summary.md":
                inv["texts"].append(rel)
                if f.name == "checklist.md":
                    inv["checklist"] = rel
                if f.name == "standard.md":
                    inv["standard"] = rel
    if not inv["checklist"]:
        inv["missing"].append("checklist.md (brief-reader): read the format from the brief itself")
    if not inv["standard"]:
        inv["missing"].append("standard.md (drawing-graphics): black on white, one accent colour")
    if "narrative" not in inv["skills"]:
        inv["missing"].append("narrative: no storyline; order the panels by the brief's list")
    out = folder / OWN
    out.mkdir(exist_ok=True)
    (out / "inventory.json").write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")
    return inv


# ---------- layout ----------

def overlaps(a, b):
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def scale_number(scale):
    if not scale:
        return None
    m = SCALE_RE.search(str(scale))
    return int(re.sub(r"[^\d]", "", m.group(1))) if m else None


def nice_length(max_m):
    """A round length in metres not longer than max_m: 1, 2, 5, 10, 20, 50 ..."""
    step = 1
    while step * 10 <= max_m:
        step *= 10
    for f in (5, 2, 1):
        if f * step <= max_m:
            return f * step
    return step


def text_ok(text_mm, factor):
    """Rescaling by factor keeps the drawing's smallest text at 12 px or more, or doesn't shrink it."""
    return text_mm is None or factor >= 1 - 1e-6 or text_mm * factor >= MIN_TEXT_MM - 0.01


def choose_scale(own, size_mm, frame_mm, text_mm, defaults=DEFAULTS):
    """For "scale": "auto": the largest usual scale at which the whole drawing fits the frame,
    never one that brings its smallest text under 12 px; at that limit the limit scale, cropped.
    own: the scale it is drawn at (1:own); size_mm: its print size at own. Returns the scale or None."""
    (w, h), (fw, fh) = size_mm, frame_mm
    ok = [s for s in sorted(set(defaults["usual_scales"]) | {own})
          if own / s <= defaults["max_enlarge"] + 1e-6 and text_ok(text_mm, own / s)]
    fits = [s for s in ok if w * own / s <= fw + 0.01 and h * own / s <= fh + 0.01]
    return fits[0] if fits else (ok[-1] if ok else None)


def crop_window(size_mm, frame_mm, crop=None):
    """What a frame shows of a drawing printed at size_mm: the frame (shrunk to the drawing where the
    drawing is smaller), the drawing's offset in it, and the share of the drawing's area hidden.
    crop: {"focus": [fx, fy]}, the point of the drawing (fractions of its width and height) at the
    frame's centre, default the centre; or {"offset_mm": [dx, dy]}, how far the drawing's top-left
    corner sits left of and above the frame's."""
    (w, h), (fw, fh) = size_mm, frame_mm
    vw, vh = min(w, fw), min(h, fh)
    crop = crop or {}
    if "offset_mm" in crop:
        ox, oy = crop["offset_mm"]
    else:
        fx, fy = crop.get("focus", [0.5, 0.5])
        ox, oy = fx * w - vw / 2, fy * h - vh / 2
    ox, oy = min(max(ox, 0), w - vw), min(max(oy, 0), h - vh)  # the frame never shows past the drawing's edge
    return {"w": vw, "h": vh, "ox": ox, "oy": oy, "hidden": 1 - vw * vh / (w * h)}


def measure(item, folder, inv_by_file, style, notes, room=(None, None), defaults=DEFAULTS, scale_bars=None):
    """Fill item['w'], item['h'] (mm, the whole box with caption) and how the drawing is sized.
    room: the content area's width and height, the frame of an "auto" drawing that has none.
    scale_bars: "all" gives a scale bar to every drawing held at a scale that has none of its own."""
    cap_mm = style["body_pt"] * 25.4 / 72 * 1.6 if item.get("caption") else 0
    if item.get("type", "text") != "drawing":
        item.setdefault("w", None)
        item.setdefault("h", None)
        item["_cap"] = 0
        return
    f = item["file"]
    d = inv_by_file.get(f)
    if d is None:
        p = folder / f
        if not p.exists():
            fr = item.get("frame")
            if not fr:
                item["_error"] = f"file not found: {f}"
                return
            # a planned frame whose drawing isn't made yet: printed as a grey labelled frame, never dropped
            item.update(_empty=True, _cap=cap_mm, _img_w=fr["w"], _img_h=fr["h"], w=fr["w"], h=fr["h"] + cap_mm)
            return
        d = svg_size(p) if p.suffix.lower() == ".svg" else raster_size(p)
    auto = str(item.get("scale", "")).strip().lower() == "auto"
    sc = scale_number(item.get("scale"))
    item["_cap"] = cap_mm
    item["_own_bar"] = d.get("scale_bar")
    want_bar = bool(item.get("scale_bar", scale_bars == "all" and not d.get("scale_bar"))) and not unscaled(f, defaults)
    if sc or auto:
        if "w_mm" in d and "h_mm" in d:
            size, text_mm = (d["w_mm"], d["h_mm"]), d.get("text_mm")
        elif "dpi" in d:
            size, text_mm = (d["w_px"] / d["dpi"] * 25.4, d["h_px"] / d["dpi"] * 25.4), MIN_TEXT_MM  # a raster's text is unknown: never shrunk
        else:
            size = None
            item["_scale_held"] = False
            notes.append(f"`{item['id']}` ({f}) has no print size (width and height in mm), so {item['scale']} can't be held; placed at the width asked for")
        own = scale_number(item.get("drawn_at")) or scale_number(d.get("scale_hint")) or scale_number(scale_hint(Path(f).stem, ""))
        fr = item.get("frame") or ({"w": room[0], "h": room[1] - cap_mm - (8 if want_bar else 0)}
                                   if auto and room[0] else None)
        if size and auto and not (own and fr):
            item["_unfit"] = ("\"scale\": \"auto\" needs the scale it is drawn at (in its file name, such as _1-2000, its summary, "
                              "or `drawn_at`)" if not own else "\"scale\": \"auto\" needs a `frame`")
            return
        if size:
            sc = choose_scale(own, size, (fr["w"], fr["h"]), text_mm, defaults) if auto else sc
            if sc is None:
                item["_unfit"] = f"no usual scale keeps its smallest text at 12 px ({text_mm:.2f} mm at 1:{own:,})"
                return
            factor = own / sc if own else 1.0
            if not text_ok(text_mm, factor):
                item["_unfit"] = (f"at 1:{sc:,} its smallest text would be {text_mm * factor / PX_MM:.1f} px, under 12 px: "
                                  f"ask its skill to draw it at 1:{sc:,}, never shrink it")
                return
            if text_mm is not None and text_mm * factor < MIN_TEXT_MM - 0.01:
                item["_small_px"] = text_mm * factor / PX_MM
                notes.append(f"`{item['id']}`: its own smallest text is {text_mm * factor / PX_MM:.1f} px printed, under 12 px: ask its skill to enlarge it")
            dw, dh = size[0] * factor, size[1] * factor
            win = crop_window((dw, dh), (fr["w"], fr["h"]) if fr else (dw, dh), item.get("crop"))
            item.update(_img_w=win["w"], _img_h=win["h"], _draw_w=dw, _draw_h=dh, _ox=win["ox"], _oy=win["oy"],
                        _hidden=win["hidden"], _factor=factor, _own=own, _print_scale=sc, _auto=auto,
                        _framed=bool(fr), _scale_held=True,
                        _fills=win["w"] * win["h"] / (fr["w"] * fr["h"]) if fr else 1.0)
            if item.get("w") and not fr and abs(item["w"] - dw) > 0.5:
                notes.append(f"`{item['id']}`: width {item['w']} mm ignored; at 1:{sc:,} the drawing is {dw:.0f} mm wide: give it a `frame` to crop it")
    elif item.get("frame"):
        notes.append(f"`{item['id']}`: `frame` ignored, the drawing has no scale; size it by `w` or `h`")
    item["_bar"] = want_bar and bool(item.get("_scale_held"))  # drawn only when the scale is held
    if item["_bar"]:
        item["_cap"] += 8  # room for the scale bar
    if "_img_w" not in item:
        aspect = d.get("aspect") or 0.75
        if item.get("w"):
            item["_img_w"] = item["w"]
            item["_img_h"] = item["w"] * aspect
        elif item.get("h"):
            item["_img_h"] = item["h"] - item["_cap"]
            item["_img_w"] = item["_img_h"] / aspect
        else:
            item["_img_w"] = 100
            item["_img_h"] = 100 * aspect
            notes.append(f"`{item['id']}`: no size given, placed 100 mm wide")
    item["w"] = item["_img_w"]
    item["h"] = item["_img_h"] + item["_cap"]


def place(panel, fmt, reserved, style, folder, inv_by_file, notes):
    W, H = fmt["width_mm"], fmt["height_mm"]
    m, g = fmt.get("margin_mm", 15), fmt.get("gutter_mm", 8)
    content_w = W - 2 * m
    top = max([r["y"] + r["h"] for r in reserved] + [m]) + g
    top = fmt.get("content_top_mm", top)
    placed, unplaced = [], []
    x, y, row_h = m, top, 0
    for it in panel.get("items", []):
        measure(it, folder, inv_by_file, style, notes, (content_w, H - m - top), scale_bars=fmt.get("scale_bars"))
        if "_error" in it or "_unfit" in it:
            unplaced.append((it, it.get("_error") or it["_unfit"]))
            continue
        if it["w"] is None:
            it["w"] = content_w
        if it["h"] is None:
            it["h"] = 60
        if "x" in it and "y" in it:
            box = {"x": it["x"], "y": it["y"], "w": it["w"], "h": it["h"]}
        else:
            if it["w"] > content_w + 0.01:
                unplaced.append((it, f"{it['w']:.0f} mm wide, the panel has {content_w:.0f} mm between its margins"))
                continue
            if x > m and x + it["w"] > m + content_w + 0.01:
                x, y, row_h = m, y + row_h + g, 0
            box = {"x": x, "y": y, "w": it["w"], "h": it["h"]}
        if box["x"] < m - 0.01 or box["y"] < m - 0.01 or box["x"] + box["w"] > W - m + 0.01 or box["y"] + box["h"] > H - m + 0.01:
            unplaced.append((it, f"{box['w']:.0f} x {box['h']:.0f} mm at ({box['x']:.0f}, {box['y']:.0f}) runs into the {m:g} mm margin; "
                                 + (f"it must be at most {content_w:.0f} mm wide: give it a `frame` to crop it, never shrink it"
                                    if box["w"] > content_w + 0.01 else "move it inside the margins")))
            continue
        clash = [r.get("what", "reserved area") for r in reserved if overlaps(box, r)]
        clash += [p["id"] for p, b in placed if overlaps(box, b)]
        if clash:
            unplaced.append((it, f"would cover {', '.join(clash)}"))
            continue
        placed.append((it, box))
        if "x" not in it:
            x += box["w"] + g
            row_h = max(row_h, box["h"])
    return placed, unplaced


# ---------- html ----------

def fill(text, ctx):
    for k, v in ctx.items():
        text = text.replace("{" + k + "}", str(v))
    return text


def paragraphs(text):
    out = []
    for para in re.split(r"\n\s*\n", text.strip()):
        p = html.escape(para.strip())
        p = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", p)
        out.append(f"<p>{p}</p>")
    return "\n".join(out)


def item_html(it, box, style, folder):
    s = f"left:{box['x']:.2f}mm;top:{box['y']:.2f}mm;width:{box['w']:.2f}mm;height:{box['h']:.2f}mm"
    kind = it.get("type", "text")
    inner = ""
    if kind == "drawing" and it.get("_empty"):
        sc = scale_number(it.get("scale"))
        label = " · ".join(x for x in (it["id"], f"1:{sc:,}" if sc else "", it.get("shows", "")) if x)
        inner = (f'<div class="empty" style="width:{it["_img_w"]:.2f}mm;height:{it["_img_h"]:.2f}mm">'
                 f'{html.escape(label)}</div>')
        if it.get("caption"):
            inner += f'<div class="cap">{html.escape(source_words(it["caption"], folder))}</div>'
    elif kind == "drawing":
        src = (folder / it["file"]).resolve().as_uri()
        dw, dh = it.get("_draw_w", it["_img_w"]), it.get("_draw_h", it["_img_h"])
        inner = (f'<div class="frame" style="width:{it["_img_w"]:.2f}mm;height:{it["_img_h"]:.2f}mm">'
                 f'<img src="{src}" style="width:{dw:.2f}mm;height:{dh:.2f}mm;'
                 f'margin-left:{-it.get("_ox", 0):.2f}mm;margin-top:{-it.get("_oy", 0):.2f}mm"></div>')
        sc = it.get("_print_scale") or scale_number(it.get("scale"))
        if it.get("_bar") and sc:
            length = nice_length(it["_img_w"] * 0.25 * sc / 1000)
            bar_mm = length * 1000 / sc
            lw = style["line_mm"]
            fs = pt_(style["body_pt"] * 0.7) * 25.4 / 72  # label size follows the body text, never below 12 px
            # a line that steps up and down, a tick and a number at every step, fewer steps if the numbers would touch
            n = next(n for n in ((4, 2, 1) if f"{length:g}"[0] == "2" else (5, 2, 1))
                     if bar_mm / n >= (len(f"{length:g}") + 1) * 0.6 * fs + 1 or n == 1)
            step, x0 = bar_mm / n, 2   # not `s`: that holds the box's position
            inner += (f'<svg class="bar" width="{bar_mm + 12:.2f}mm" height="7mm" viewBox="0 0 {bar_mm + 12:.2f} 7">'
                      f'<path d="{"".join(f"M{x0 + i * step:.2f},{1 + 1.5 * (i % 2)}h{step:.2f}" for i in range(n))}{"".join(f"M{x0 + i * step:.2f},1v1.5" for i in range(n + 1))}" '
                      f'fill="none" stroke="{style["text"]}" stroke-width="{lw}"/>'
                      + "".join(f'<text x="{x0 + i * step:.2f}" y="6.4" font-size="{fs:.2f}" text-anchor="middle">{length * i / n:g}{" m" if i == n else ""}</text>' for i in range(n + 1))
                      + '</svg>')
        if it.get("caption"):
            cap = source_words(it["caption"], folder)
            cap = printed_caption(cap, sc) if sc and it.get("_scale_held") else cap
            inner += f'<div class="cap">{html.escape(cap)}</div>'
    elif kind == "figures":
        rows = "".join(
            f'<tr><td>{html.escape(str(r[0]))}</td><td class="v">{html.escape(str(r[1]))}</td>'
            f'<td class="src">{html.escape(source_words(str(r[2]), folder)) if len(r) > 2 else ""}</td></tr>'
            for r in it.get("rows", []))
        head = f"<h2>{html.escape(source_words(it['heading'], folder))}</h2>" if it.get("heading") else ""
        inner = f"{head}<table>{rows}</table>"
    else:
        head = f"<h2>{html.escape(source_words(it['heading'], folder))}</h2>" if it.get("heading") else ""
        pt = it.get("pt")
        st = f' style="font-size:{pt_(pt)}pt;line-height:1.1;font-weight:{it.get("weight", 400)}"' if pt else ""
        inner = f"{head}<div{st}>{paragraphs(source_words(it.get('text', ''), folder))}</div>"
    return f'<div class="box {kind}" id="{html.escape(it["id"])}" style="{s}">{inner}</div>'


CHECK_JS = """
<script nonce="{nonce}">
window.addEventListener('load', () => {
  const r = [];
  document.querySelectorAll('.box').forEach(b => {
    if (b.scrollHeight > b.clientHeight + 2 || b.scrollWidth > b.clientWidth + 2)
      r.push({id: b.id, problem: 'overflow', need_h_mm: +(b.scrollHeight * 25.4 / 96).toFixed(1),
              has_h_mm: +(b.clientHeight * 25.4 / 96).toFixed(1)});
    b.querySelectorAll('img').forEach(i => { if (!i.complete || !i.naturalWidth) r.push({id: b.id, problem: 'image did not load'}); });
  });
  const pre = document.createElement('pre'); pre.id = 'layout-check'; pre.style.display = 'none';
  pre.textContent = JSON.stringify(r); document.body.appendChild(pre);
});
</script>
"""


def panel_html(n, total, placed, fmt, reserved, marks, style, ctx, folder):
    W, H = fmt["width_mm"], fmt["height_mm"]
    style = {**style, "heading_pt": pt_(style["heading_pt"]), "body_pt": pt_(style["body_pt"])}
    c = {**ctx, "n": n, "total": total}
    parts = [item_html(it, b, style, folder) for it, b in placed]
    for r in reserved:
        border = f"border:{style['line_mm']}mm dashed rgba(0,0,0,.12);" if r.get("outline") else ""
        parts.append(f'<div class="reserved" style="left:{r["x"]}mm;top:{r["y"]}mm;width:{r["w"]}mm;height:{r["h"]}mm;{border}"></div>')
    for mk in marks:
        align = mk.get("align", "left")
        pos = f"top:{mk['y']}mm;" + (f"right:{mk['x']}mm;" if align == "right" else f"left:{mk['x']}mm;")
        parts.append(f'<div class="mark" style="{pos}font-size:{pt_(mk.get("pt", 14))}pt;font-weight:{mk.get("weight", 400)};'
                     f'text-align:{align}">{html.escape(fill(mk["text"], c))}</div>')
    nonce = secrets.token_hex(16)  # only the page's own check may run; nothing loads from the network
    csp = f"default-src 'none'; img-src file: data:; style-src 'unsafe-inline'; font-src file: data:; script-src 'nonce-{nonce}'"
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{csp}"><title>Panel {n}</title><style>
@page {{ size: {W}mm {H}mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: {W}mm; height: {H}mm; overflow: hidden; background: {style['background']}; color: {style['text']};
  font-family: {style['font']}; font-size: {style['body_pt']}pt; line-height: 1.35;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.box, .reserved, .mark {{ position: absolute; }}
@media print {{ .reserved {{ border: none !important; }} }}
.box {{ overflow: hidden; }}
.box .frame {{ overflow: hidden; }}
.box .empty {{ background: #e6e6e6; color: #555; padding: 3mm; overflow: hidden; }}
.box img {{ display: block; max-width: none; }}
.box h2 {{ font-size: {style['heading_pt']}pt; line-height: 1.15; margin-bottom: 0.4em; font-weight: 700; }}
.box p {{ margin-bottom: 0.6em; }}
.box .cap {{ font-size: {style['body_pt']}pt; margin-top: 1mm; }}
.box .bar {{ display: block; margin-top: 1mm; font-family: inherit; fill: {style['text']}; }}
.box table {{ border-collapse: collapse; width: 100%; }}
.box td {{ border-top: {style['line_mm']}mm solid {style['text']}; padding: 1.2mm 2mm 1.2mm 0; vertical-align: top; }}
.box td.v {{ font-weight: 700; color: {style['accent']}; white-space: nowrap; }}
.box td.src {{ opacity: .6; font-size: max(.8em, 12px); }}
.box.text > div {{ column-width: {COLUMN_EM}em; column-gap: 6mm; }}
.box.text > div p {{ break-inside: avoid-column; }}
</style></head><body>
{chr(10).join(parts)}
{CHECK_JS.replace("{nonce}", nonce)}</body></html>"""


# ---------- browser ----------

def find_browser():
    cands = [os.environ.get("BROWSER")]
    cands += [shutil.which(n) for n in ("chrome", "msedge", "google-chrome", "chromium", "chromium-browser")]
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
        if base:
            cands += [os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
                      os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")]
    cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def run_browser(browser, args, timeout=180):
    with tempfile.TemporaryDirectory() as prof:
        cmd = [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
               f"--user-data-dir={prof}", *args]
        try:
            return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:  # a hung browser: the report then says what wasn't written
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="timeout")


def pdf_pages(path):
    """Page count and page sizes in mm, read from the PDF without a library (None if it can't be read)."""
    data = Path(path).read_bytes()
    boxes = re.findall(rb"/MediaBox\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\]", data)
    pages = len(re.findall(rb"/Type\s*/Page(?![s\w])", data))
    sizes = [((float(b[2]) - float(b[0])) * 25.4 / 72, (float(b[3]) - float(b[1])) * 25.4 / 72) for b in boxes]
    return pages, sizes


# ---------- render ----------

def planned(L):
    """The drawings layout.json plans: what plan.json keeps, so a later render can name one that is gone."""
    return [{"id": it.get("id"), "file": it.get("file"), "scale": it.get("scale"), "frame": it.get("frame"), "panel": n}
            for n, p in enumerate(L.get("panels", []), 1) for it in p.get("items", []) if it.get("type") == "drawing"]


def render(layout_path, png_dpi, check=False, plan=False):
    layout_path = Path(layout_path).resolve()
    out = layout_path.parent
    folder = out.parent
    L = json.loads(layout_path.read_text(encoding="utf-8"))
    fmt = {"scale_bars": L.get("scale_bars"), **L["format"]}  # the switch works in `format` or at the top
    style = {"font": "Helvetica, Arial, sans-serif", "text": "#000", "background": "#fff", "accent": "#d0312d",
             "line_mm": 0.25, "heading_pt": 20, "body_pt": 11, **L.get("style", {})}
    reserved = L.get("reserved", [])
    marks = L.get("marks", [])
    ctx = L.get("labels", {})
    inv = scan(folder)
    inv_by_file = {d["file"]: d for d in inv["drawings"]}
    panels = L["panels"]
    total = len(panels)
    browser = None if check else find_browser()
    notes, results = [], []
    plan_path = out / "plan.json"
    if plan or not plan_path.exists():
        drawings = planned(L)
        plan_path.write_text(json.dumps({"drawings": drawings}, indent=1, ensure_ascii=False), encoding="utf-8")
        notes.append(f"plan.json saved: {len(drawings)} planned drawings, which every later render checks for")

    for i, panel in enumerate(panels, 1):
        placed, unplaced = place(panel, fmt, reserved, style, folder, inv_by_file, notes)
        page = panel_html(i, total, placed, fmt, reserved, marks, style, ctx, folder)
        hp = out / f"panel-{i}.html"
        hp.write_text(page, encoding="utf-8")
        res = {"n": i, "placed": placed, "unplaced": unplaced, "checks": [], "story": panel.get("story", ""),
               "paths": paths_left(placed, folder)}
        if browser:
            uri = hp.as_uri()
            dom = run_browser(browser, ["--virtual-time-budget=10000", "--dump-dom", uri]).stdout
            m = re.search(r'<pre id="layout-check"[^>]*>(.*?)</pre>', dom, re.S)
            res["checks"] = json.loads(html.unescape(m.group(1))) if m else [{"id": "-", "problem": "layout check did not run"}]
            pdf = out / f"panel-{i}.pdf"
            run_browser(browser, ["--no-pdf-header-footer", "--print-to-pdf-no-header", "--virtual-time-budget=10000",
                                  f"--print-to-pdf={pdf}", uri])
            scale = png_dpi / 96
            wpx, hpx = round(fmt["width_mm"] / PX_MM), round(fmt["height_mm"] / PX_MM)
            png = out / f"panel-{i}.png"
            run_browser(browser, [f"--window-size={wpx},{hpx}", f"--force-device-scale-factor={scale}",
                                  "--virtual-time-budget=10000", f"--screenshot={png}", uri])
            res["pdf"] = pdf if pdf.exists() else None
            res["png"] = png if png.exists() else None
            if res["pdf"]:
                res["pages"], res["sizes"] = pdf_pages(pdf)
                res["mb"] = pdf.stat().st_size / 1e6
        results.append(res)

    used = {it.get("file") for r in results for it, _ in r["placed"]}
    unused = [d for d in inv["drawings"] if d["file"] not in used]
    ids = {it["id"] for r in results for it, _ in r["placed"]}
    report = write_report(out, L, fmt, results, unused, ids, notes, inv, browser, png_dpi, check)
    print(report)


def paths_left(placed, folder):
    """Headings, captions and sources that still show a file path once paths of the proposal folder are words."""
    out = []
    for it, _ in placed:
        texts = [("heading", it.get("heading")), ("caption", it.get("caption"))]
        texts += [("source", r[2]) for r in it.get("rows", []) if len(r) > 2]
        for where, t in texts:
            m = PATH_RE.search(source_words(str(t), folder)) if t else None
            if m:
                out.append(f"`{it['id']}` {where}: {m.group(1)}")
    return out


def plan_check(out, L):
    """The drawings plan.json planned that layout.json lost, and lines on those it changed. Empty without a plan.json."""
    p = Path(out) / "plan.json"
    if not p.exists():
        return [], []
    now = {d["id"]: d for d in planned(L)}
    dropped, changed = [], []
    say = lambda v: "none" if v is None else f"{v.get('w'):g} x {v.get('h'):g} mm" if isinstance(v, dict) else v
    for d in json.loads(p.read_text(encoding="utf-8")).get("drawings", []):
        c = now.get(d["id"])
        if c is None:
            dropped.append(d)
        else:
            changed += [f"`{d['id']}`: {k} planned as {say(d.get(k))}, now {say(c.get(k))}"
                        for k in ("file", "scale", "frame") if d.get(k) != c.get(k)]
    return dropped, changed


def figure_conflicts(results, L):
    """Rows of `figures` boxes on the panels whose label is the same and whose value isn't. Only labelled
    figures are compared, never running text. Returns (label, named in notes, [(panel, value, source)])."""
    norm = lambda s: " ".join(str(s).lower().split()).rstrip(":")
    seen = {}
    for r in results:
        for it, _ in r["placed"]:
            for row in it.get("rows", []) if it.get("type") == "figures" else []:
                if len(row) > 1 and norm(row[0]):
                    value = re.sub(r"(?<=\d)[,   ](?=\d{3}(?!\d))", "", norm(row[1]))  # 1,200 = 1200
                    seen.setdefault(norm(row[0]), {}).setdefault(value, []).append((r["n"], row[1], row[2] if len(row) > 2 else ""))
    said = " ".join(L.get("notes", [])).lower()
    return [(label, label in said, [x for v in values.values() for x in v])
            for label, values in seen.items() if len(values) > 1]


SEVERITY = ("high", "medium", "low")


def skill_of(file, by=None):
    """The skill responsible for a file: `by` from layout.json's `required` (taken from the studio's list of skills),
    else the folder the file sits in, since every skill writes only into its own folder. Unknown when neither
    says, or when the two disagree: never a guess."""
    parts = Path(str(file)).parts if file else ()
    folder = parts[0] if len(parts) > 1 and parts[0] != OWN else None
    if by and folder and by != folder:
        return f"unknown (`by` names {by}, the file is in {folder}/)"
    return by or folder or "unknown"


def whereabouts(skill, file, folder, inv):
    """What the proposal folder shows about a drawing that isn't there."""
    if skill.startswith("unknown"):
        return "layout.json names no file and no skill for it"
    if not (Path(folder) / skill).is_dir():
        return f"no `{skill}/` folder in the proposal: the skill has not run"
    said = ((inv.get("skills", {}).get(skill) or {}).get("summary") or "").strip()
    return (f"`{skill}/` exists but has no {file}" if file else f"`{skill}/` exists; layout.json names no file") + \
           (f"; its summary begins: \"{said.splitlines()[0]}\"" if said else "; it has no summary.md")


def source_skills(sources, folder):
    """The skills behind the sources of a figure: the folder a source starts with, unknown if it names none."""
    out = set()
    for s in sources:
        head = re.split(r"[/,:\s]", str(s).strip(), maxsplit=1)[0]
        out.add(head if head and head != OWN and (Path(folder) / head).is_dir() else "unknown")
    return ", ".join(sorted(out))


def missing_skill(text):
    """The skill a line of the scan's missing inputs names: "x/summary.md", "checklist.md (brief-reader)", "narrative: ..."."""
    m = re.match(r"([\w-]+)/", text) or re.search(r"\(([\w-]+)\)", text) or re.match(r"([\w-]+):", text)
    return m.group(1) if m else "unknown"


def write_issues(out, issues):
    """issues.md: what other skills must fix, by skill, for the studio lead; then what panel-layout fixes itself."""
    cell = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    rank = lambda i: (SEVERITY.index(i["severity"]), i["issue"], i["affected"])
    up = [i for i in issues if i["where"] == "upstream"]
    here = [i for i in issues if i["where"] == "here"]
    count = lambda xs: ", ".join(f"{sum(i['severity'] == s for i in xs)} {s}" for s in SEVERITY)
    head = ["| Severity | Issue | Affected | Evidence | Recommended fix |", "|---|---|---|---|---|"]
    row = lambda i: f"| {i['severity']} | {cell(i['issue'])} | {cell(i['affected'])} | {cell(i['evidence'])} | {cell(i['fix'])} |"
    skills = sorted({i["skill"] for i in up}, key=lambda s: (s.startswith("unknown"), s))
    lines = ["# Panel layout: issues", "",
             "Written by every render, from the same checks as `report.md`. Nothing here was corrected, drawn or "
             "made up by panel-layout. High: a required item is not on the panels as the brief asks. Medium: an item "
             "is on the panels but wrong, or a non-required one is missing. Low: it reads less well.", "",
             f"For the studio lead: {len(up)} ({count(up)}) for {len(skills)} skill(s). "
             f"Fix in panel-layout: {len(here)} ({count(here)}).", "",
             "## For the studio lead, by responsible skill", "",
             "The skill is the one `required` names in `by`, else the folder its file is in (each skill writes only "
             "into its own); unknown where neither says or the two disagree.", ""]
    for skill in skills:
        lines += [f"### {skill}", ""] + head + [row(i) for i in sorted((i for i in up if i["skill"] == skill), key=rank)] + [""]
    if not up:
        lines += ["- none", ""]
    lines += ["## Fix in panel-layout", ""] + (head + [row(i) for i in sorted(here, key=rank)] if here else ["- none"])
    text = "\n".join(lines) + "\n"
    (Path(out) / "issues.md").write_text(text, encoding="utf-8")
    return text


def write_report(out, L, fmt, results, unused, ids, notes, inv, browser, png_dpi, check=False):
    out = Path(out)
    folder = out.parent
    W, H = fmt["width_mm"], fmt["height_mm"]
    max_mb = fmt.get("max_mb")
    lines = [f"# Panel layout: report", "",
             f"Format: {W:g} x {H:g} mm, {len(results)} of {fmt.get('panels', len(results))} panels asked for "
             f"({fmt.get('source', 'source not given')}). Style: {L.get('style', {}).get('source', 'no standard, black on white with one accent')}.", "",
             "Issues by responsible skill, for the studio lead: `issues.md`.", ""]
    if check:
        lines += ["**Check only (`--check`): no PDF or PNG written; text too long for its box shows only in a full render.**", ""]
    elif not browser:
        lines += ["**No Chrome, Edge or Chromium found: only the HTML was written, no PDF or PNG.** Set BROWSER to its path.", ""]
    problems, no_bar, issues = 0, [], []
    req = L.get("required", [])
    req_ids = {q.get("id") for q in req if q.get("id")}
    req_by = {q["id"]: q.get("by") for q in req if q.get("id")}
    item_file = {it.get("id"): it.get("file") for p in L.get("panels", []) for it in p.get("items", [])}
    crop_limit = fmt.get("max_crop_required", DEFAULTS["max_crop_required"])
    over_crop = {}  # required id: share hidden, over the limit

    def add(where, severity, issue, affected, evidence, fix, skill=OWN):
        issues.append({"where": where, "severity": severity, "issue": issue, "affected": affected,
                       "evidence": evidence, "fix": fix, "skill": skill})

    for r in results:
        n = r["n"]
        lines.append(f"## Panel {n}")
        if r["story"]:
            lines.append(f"Story: {r['story']}")
        lines.append("")
        if r.get("pdf"):
            sizes = ", ".join(f"{w:.1f} x {h:.1f} mm" for w, h in r["sizes"]) or "size not readable"
            ok = r["pages"] == 1 and all(abs(w - W) < 1 and abs(h - H) < 1 for w, h in r["sizes"]) and r["sizes"]
            mb_ok = max_mb is None or r["mb"] <= max_mb
            problems += (not ok) + (not mb_ok)
            lines.append(f"- PDF: {r['pages']} page(s), {sizes}, {r['mb']:.2f} MB"
                         f"{'' if ok else '  **WRONG SIZE OR PAGE COUNT**'}{'' if mb_ok else f'  **OVER {max_mb} MB**'}")
            lines.append(f"- PNG: {'written' if r.get('png') else '**missing**'} at {png_dpi} dpi")
            if not ok:
                add("here", "high", "PDF of the wrong size or page count", f"panel {n}", f"{r['pages']} page(s), {sizes}",
                    f"set `format` to {W:g} x {H:g} mm as the brief asks and render again")
            if not mb_ok:
                add("here", "high", f"PDF over the brief's {max_mb} MB", f"panel {n}", f"{r['mb']:.1f} MB",
                    "find the largest image on the panel; ask its skill for a lighter file")
        elif browser:
            problems += 1
            lines.append("- **PDF was not written**")
            add("here", "high", "PDF not written", f"panel {n}", "the browser wrote no PDF", "render again; set BROWSER if it fails twice")
        area = sum(b["w"] * b["h"] for _, b in r["placed"]) / (W * H)
        lines.append(f"- covered by items: {100 * area:.0f} % of the panel" + ("  **mostly empty**" if area < 0.35 else ""))
        if area < 0.35:
            add("here", "low", "panel mostly empty", f"panel {n}", f"{100 * area:.0f} % covered",
                "place the available drawings the storyline can use; where a drawing is missing upstream, leave its space")
        for it, b in r["placed"]:
            held, iid = "", it["id"]
            sev = "high" if iid in req_ids else "medium"
            what = f"`{iid}` on panel {n}" + (f" ({it['file']})" if it.get("file") else "")
            skill = skill_of(it.get("file"), req_by.get(iid))
            if it.get("_empty"):
                problems += 1
                held = "  **empty frame: its drawing is not made yet**"
                fr, sc_txt = it.get("frame") or {}, f" at {it['scale']}" if it.get("scale") else ""
                frame_txt = f"a frame of {fr.get('w', 0):g} x {fr.get('h', 0):g} mm"
                add("upstream", sev, "planned drawing not made", what,
                    f"planned{sc_txt} in {frame_txt}; " + whereabouts(skill, it["file"], folder, inv),
                    f"run `{skill}` to draw {it['file']}{sc_txt} to {frame_txt}"
                    + (f", showing: {it['shows']}" if it.get("shows") else ""), skill)
            elif it.get("type") == "drawing" and it.get("_print_scale"):
                sc, own, k = it["_print_scale"], it.get("_own"), it["_factor"]
                frame_txt = f"its frame of {it['_img_w']:.0f} x {it['_img_h']:.0f} mm"
                held = (f", 1:{sc:,} {'chosen' if it['_auto'] else 'held'}"
                        + (f", rescaled from 1:{own:,} (x{k:.2f})" if abs(k - 1) > 1e-6 else ", not rescaled")
                        + (f", frame {it['_img_w']:.0f} x {it['_img_h']:.0f} mm hides {100 * it['_hidden']:.0f} % of its area"
                           + (" (no smaller usual scale keeps its text at 12 px or more)" if it["_auto"] else "")
                           if it["_hidden"] > 0.005 else ", whole drawing shown"))
                if it.get("_fills", 1) < 0.8:
                    held += f", fills {100 * it['_fills']:.0f} % of its frame"
                if it.get("_bar"):
                    held += ", scale bar added"
                elif not it.get("_own_bar") and not unscaled(it["file"]):
                    no_bar.append(it)
                if not it["_auto"] and own and own != sc:
                    problems += 1
                    held += (f"  **drawn at 1:{own:,}, printed at 1:{sc:,}, the scale layout.json fixes: "
                             f"ask its skill to draw it at 1:{sc:,}**")
                    add("upstream", "medium", "drawn at another scale than its frame", what,
                        f"drawn at 1:{own:,} (its file name, summary or `drawn_at`), printed at 1:{sc:,}, the scale layout.json fixes",
                        f"draw it at 1:{sc:,} to {frame_txt}", skill)
                if it.get("_small_px"):
                    add("upstream", "medium", "text in the drawing under 12 px", what,
                        f"its smallest text is {it['_small_px']:.1f} px printed at 1:{sc:,}",
                        f"enlarge its labels to 12 px or more at 1:{sc:,}", skill)
                if iid in req_ids and it["_hidden"] > crop_limit:
                    problems += 1
                    over_crop[iid] = it["_hidden"]
                    held += (f"  **cropped {100 * it['_hidden']:.0f} %, over the {100 * crop_limit:.0f} % limit for a required "
                             "drawing: aim `crop` at what the brief asks to show, or give it a larger frame**")
                    add("here", "high", "required drawing cropped over the limit", what,
                        f"{frame_txt} hides {100 * it['_hidden']:.0f} % of it at 1:{sc:,} (limit {100 * crop_limit:.0f} %)",
                        f"aim `crop.focus` at what the brief asks to show and give it a larger frame; if the panels have no room "
                        f"at 1:{sc:,}, the lead asks `{skill}` for a tighter extent")
                elif it["_hidden"] > DEFAULTS["max_crop"]:
                    problems += 1
                    held += f"  **cropped by more than {100 * DEFAULTS['max_crop']:.0f} %: check that what the brief asks to show is in the frame**"
                    add("here", "low", f"drawing cropped over {100 * DEFAULTS['max_crop']:.0f} %", what,
                        f"{frame_txt} hides {100 * it['_hidden']:.0f} %", "aim `crop.focus` at what it must show, or give it a larger frame")
            elif it.get("type") == "drawing" and it.get("scale"):
                held = f", **{it['scale']} not held**"
                add("upstream", sev, "drawing without a print size in mm", what,
                    f"{it['scale']} can't be held: the file gives no width and height in mm",
                    "give the SVG its print width and height in mm at the scale it is drawn at", skill)
            lines.append(f"- placed `{iid}` at ({b['x']:.0f}, {b['y']:.0f}) mm, {b['w']:.0f} x {b['h']:.0f} mm{held}")
        for p in r["paths"]:
            problems += 1
            lines.append(f"- **file path on the panel: {p}**: write what it is instead")
            add("here", "low", "file path printed on the panel", f"panel {n}", p, "write what it is instead")
        for it, why in r["unplaced"]:
            problems += 1
            lines.append(f"- **did not fit: `{it['id']}`** ({it.get('file', it.get('type', 'text'))}): {why}")
            iid = it["id"]
            sev = "high" if iid in req_ids else "medium"
            what = f"`{iid}` for panel {n}" + (f" ({it['file']})" if it.get("file") else "")
            skill = skill_of(it.get("file"), req_by.get(iid))
            if "_error" in it:
                if iid not in req_ids:  # a required one is named under what the brief asks for
                    add("upstream", "medium", "drawing in layout.json not in the proposal", what,
                        whereabouts(skill, it.get("file"), folder, inv),
                        f"run `{skill}` to make it, or plan a frame for it", skill)
            elif "12 px" in why:
                add("upstream", sev, "text in the drawing too small at the scale asked", what, why,
                    "draw it at the printed scale with labels of 12 px or more", skill)
            else:
                add("here", sev, "item did not fit", what, why,
                    "move or resize its neighbours, or give it a frame and a panel of its own; never shrink it")
        for c in r["checks"]:
            problems += 1
            extra = f" (needs {c['need_h_mm']} mm, has {c['has_h_mm']} mm)" if c.get("need_h_mm") else ""
            lines.append(f"- **{c['problem']}: `{c['id']}`**{extra}")
            if c["problem"] == "overflow":
                add("here", "medium", "text longer than its box", f"`{c['id']}` on panel {n}", extra.strip(" ()"),
                    "give the box more height, or shorten narrative's words; never smaller text")
            else:
                f = item_file.get(c["id"])
                add("upstream", "medium", c["problem"], f"`{c['id']}` on panel {n}" + (f" ({f})" if f else ""),
                    "the browser could not show the file", "check that the file opens; ask its skill to write it again",
                    skill_of(f, req_by.get(c["id"])))
        lines.append("")
    empty = {it["id"] for r in results for it, _ in r["placed"] if it.get("_empty")}
    missing = [q for q in req if not q.get("id") or q["id"] not in ids or q["id"] in empty]
    refused = {it["id"] for r in results for it, _ in r["unplaced"] if "_error" not in it}  # a missing file is missing, not too big
    available = []
    lines.append("## What the brief asks for")
    for q in req:
        f = q.get("file") or item_file.get(q.get("id"))
        if q in missing and q.get("id") not in empty and q.get("id") not in refused and f and (folder / f).is_file():
            available.append(q)
        state = (f"**CROPPED {100 * over_crop[q['id']]:.0f} %: `{q['id']}` is placed, but its frame hides more than "
                 f"{100 * crop_limit:.0f} %**" if q not in missing and q["id"] in over_crop else
                 f"on the panels, `{q['id']}`" if q not in missing else
                 f"**EMPTY FRAME: `{q['id']}` is planned, its drawing is not made yet**" if q.get("id") in empty else
                 f"**NOT PLACED: `{q['id']}` exists but did not fit**" if q.get("id") in refused else
                 f"**AVAILABLE, NOT PLACED: {f} exists but is not on the panels**" if q in available else
                 "**MISSING: no input**")
        lines.append(f"- {q['what']} ({q.get('source', '')}): {state}"
                     + (f". {q['note']}" if q.get("note") else ""))
        what = q["what"] + (f" ({f})" if f else "")
        if q in available:
            add("here", "high", "required drawing available but not on the panels", what,
                f"{f} is in the proposal folder; asked for by {q.get('source') or 'the brief'}",
                "place it on the panel of its storyline step, at its scale, in a frame")
        elif q in missing and q.get("id") not in empty and q.get("id") not in refused:
            skill = skill_of(f, q.get("by"))
            add("upstream", "high", "required item missing", what,
                whereabouts(skill, f, folder, inv) + f"; asked for by {q.get('source') or 'the brief'}",
                f"run `{skill}` to make it" if not skill.startswith("unknown")
                else "name the skill that makes it (`by` in `required`), or the lead decides who does", skill)
    if not req:
        lines.append("- **No list of required items in layout.json: nothing was checked against the brief.**")
        add("here", "high", "no list of required items", "layout.json", "`required` is empty",
            "list every drawing and figure the brief and the storyline ask for in `required`")
    lines.append("")
    lines.append("## Drawings at a scale without a scale bar")
    lines.append("Tested on the SVG: no element named scale-bar, and no text \"0\" together with a text such as \"200 m\" "
                 "or \"1 km\"; a PNG or JPEG is not tested. `\"scale_bars\": \"all\"` in `format` adds one to each.")
    lines += [f"- **`{it['id']}`** ({it['file']}), 1:{it['_print_scale']:,}" for it in no_bar] or ["- none on the panels"]
    problems += len(no_bar)
    for it in no_bar:
        add("here", "low", "drawing at a scale without a scale bar", f"`{it['id']}` ({it['file']})",
            f"printed at 1:{it['_print_scale']:,}, no scale bar of its own", "`\"scale_bars\": \"all\"` in `format`, or `scale_bar: true`")
    lines.append("")
    dropped, changed = plan_check(out, L)
    if dropped or changed:
        lines.append("## Planned drawings (plan.json)")
        lines += [f"- **DROPPED: planned `{d['id']}` ({d.get('file')}) is no longer in layout.json**" for d in dropped]
        lines += [f"- {c}" for c in changed]
        lines.append("")
    problems += len(dropped)
    for d in dropped:
        add("here", "high" if d["id"] in req_ids else "medium", "planned drawing dropped from layout.json",
            f"`{d['id']}` ({d.get('file')}), planned on panel {d.get('panel')}", "in plan.json, not in layout.json",
            "put it back in its planned frame; if it goes on purpose, say why in `notes` and render with --plan")
    conflicts = figure_conflicts(results, L)
    lines.append("## Numbers to check")
    lines.append("Figures with the same label and different values; neither is corrected here.")
    for label, named, values in conflicts:
        problems += not named
        shown = "; ".join(f"{v} (panel {n}{', ' + source_words(str(s), folder) if s else ''})" for n, v, s in values)
        lines.append(f"- {'' if named else '**'}{label}: {shown}" + ("  (named in notes)" if named else "**"))
        add("upstream", "medium", "figures that should agree don't", f"figure \"{label}\"", shown,
            "the skills behind these sources agree on one value; the panels show both until then",
            source_skills([s for _, _, s in values], folder))
        if not named:
            add("here", "medium", "disagreeing figures not named", f"figure \"{label}\"", shown,
                "name the mismatch in `notes` and in summary.md; correct neither")
    if not conflicts:
        lines.append("- none")
    lines.append("")
    lines.append("## Drawings in the proposal folder not on the panels")
    lines += [f"- {d['file']}" for d in unused] or ["- none"]
    req_files = {q.get("file") for q in available}
    for d in unused:
        if d["file"] not in req_files:
            add("here", "low", "drawing available but not on the panels", d["file"], "in the proposal folder, not in layout.json",
                "place it if the storyline can use it; leave it off if it is a working drawing its skill doesn't mean for the panels")
    lines.append("")
    lines.append("## Inputs missing")
    lines += [f"- {m}" for m in inv["missing"] + L.get("missing", [])] or ["- none"]
    for m in inv["missing"]:
        skill = missing_skill(m)
        add("upstream", "medium", "input missing", m, "not in the proposal folder",
            f"`{skill}` writes it" if skill != "unknown" else "the lead decides who writes it", skill)
    for m in L.get("missing", []):
        cited = re.search(r"([\w-]+)/[\w.-]+\.\w+", m)  # a file of a skill's folder it cites, such as plans/summary.md
        skill = cited.group(1) if cited and cited.group(1) != OWN and (folder / cited.group(1)).is_dir() else "unknown"
        add("upstream", "medium", "input missing or wrong", m,
            "named in layout.json" + (f", citing {cited.group(0)}" if cited else ""),
            f"ask `{skill}`, whose file it cites" if skill != "unknown" else "the lead decides who makes it", skill)
    notes = notes + L.get("notes", [])
    if notes:
        lines += ["", "## Notes"] + [f"- {n}" for n in notes]
    not_fit = sum(q.get("id") in refused for q in missing)
    lines += ["", f"Problems: {problems}. Required items missing: {len(missing)} of {len(req)} "
                  f"({len(missing) - not_fit - len(available)} without input, {not_fit} did not fit, "
                  f"{len(available)} available but not placed). "
                  f"Required drawings cropped over {100 * crop_limit:.0f} %: {len(over_crop)}. Planned drawings dropped: {len(dropped)}."]
    text = "\n".join(lines) + "\n"
    (out / "report.md").write_text(text, encoding="utf-8")
    write_issues(out, issues)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("folder")
    r = sub.add_parser("render")
    r.add_argument("layout")
    r.add_argument("--png-dpi", type=int, default=96)
    r.add_argument("--check", action="store_true", help="check and report only: no browser, no PDF or PNG")
    r.add_argument("--plan", action="store_true", help="save the planned drawings to plan.json again")
    a = ap.parse_args()
    if a.cmd == "scan":
        inv = scan(a.folder)
        print(json.dumps({k: v for k, v in inv.items() if k != "skills"}, indent=1, ensure_ascii=False))
        print("summaries:", ", ".join(k for k, v in inv["skills"].items() if v["summary"]) or "none")
    else:
        render(a.layout, a.png_dpi, a.check, a.plan)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
