"""Panels for a competition entry, in two steps.

  python panels.py scan   <proposal folder>
      Lists every summary, drawing, table and text in the proposal folder, with each
      drawing's print size, and writes panel-layout/inventory.json.

  python panels.py render <proposal folder>/panel-layout/layout.json [--png-dpi 96] [--check]
      Places the items of layout.json on the panels, each drawing with a scale in its frame
      at a true scale, cropped by the frame's edge; renders panel-N.html/.pdf/.png with a
      headless Chrome or Edge, checks the result and writes panel-layout/report.md.
      --check: only the check, report.md and issues.md, no browser, no PDF or PNG.

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
    "blank_min_side_mm": 60,  # a blank block at least this wide and high and this large is named even when no drawing fits in it:
    "blank_min_cm2": 150,     # about a quarter of an A4 page; thinner strips are gutters and margins
    "hero_share": 0.55,       # the dominant drawing should take at least this share of the content area, where it can
    "paper_share_max": 0.40,  # more of the rendered content area than this left as paper reads as unfinished
    "section_ratio_min": 0.15,  # a full-width section band at least this high for its width
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


def area_of(a, b):
    """The area two boxes share, in mm²."""
    return max(0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])) * \
        max(0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))


def largest_blank(boxes, fmt, reserved=()):
    """The largest empty rectangle (x, y, w, h) between the margins and below the reserved boxes, where no box is."""
    W, H = fmt["width_mm"], fmt["height_mm"]
    m, g = fmt.get("margin_mm", 15), fmt.get("gutter_mm", 8)
    top = fmt.get("content_top_mm", max([r["y"] + r["h"] for r in reserved] + [m]) + g)
    taken = list(boxes) + list(reserved)
    xs = sorted({m, W - m} | {min(max(v, m), W - m) for b in taken for v in (b["x"], b["x"] + b["w"])})
    ys = sorted({top, H - m} | {min(max(v, top), H - m) for b in taken for v in (b["y"], b["y"] + b["h"])})
    free = [[not any(b["x"] < (xs[i] + xs[i + 1]) / 2 < b["x"] + b["w"] and b["y"] < (ys[j] + ys[j + 1]) / 2 < b["y"] + b["h"]
                     for b in taken) for j in range(len(ys) - 1)] for i in range(len(xs) - 1)]
    best = (0, 0, 0, 0)
    for i in range(len(xs) - 1):          # every run of columns, and in it every run of free rows
        rows = [True] * (len(ys) - 1)
        for k in range(i, len(xs) - 1):
            rows = [a and b for a, b in zip(rows, free[k])]
            j = 0
            while j < len(rows):
                if not rows[j]:
                    j += 1
                    continue
                j0 = j
                while j < len(rows) and rows[j]:
                    j += 1
                w, h = xs[k + 1] - xs[i], ys[j] - ys[j0]
                if w * h > best[2] * best[3]:
                    best = (xs[i], ys[j0], w, h)
    return best


def png_rows(path):
    """Width, height and the rows (RGB bytes) of an 8-bit RGB or RGBA PNG, without a library."""
    import zlib
    data = Path(path).read_bytes()
    w, h, depth, ctype = struct.unpack(">IIBB", data[16:26])
    if depth != 8 or ctype not in (2, 6):
        raise ValueError(f"{path}: only 8-bit RGB or RGBA PNGs are read")
    bpp, pos, raw = (3 if ctype == 2 else 4), 8, b""
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind == b"IDAT":
            raw += data[pos + 8:pos + 8 + n]
        pos += 12 + n
    raw, stride, prev, rows = zlib.decompress(raw), w * bpp, bytearray(w * bpp), []
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a, b = line[i - bpp] if i >= bpp else 0, prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line[i] for i in range(stride) if i % bpp < 3))
        prev = line
    return w, h, rows


def paper_seen(png, fmt, reserved=(), background="#fff"):
    """The rendered panel between the margins as rows of True (paper) and False (ink), the reserved boxes left out,
    with the mm a pixel takes each way and where the content starts: what the blank and paper checks read."""
    w, h, rows = png_rows(png)
    W, H = fmt["width_mm"], fmt["height_mm"]
    m, g = fmt.get("margin_mm", 15), fmt.get("gutter_mm", 8)
    top = fmt.get("content_top_mm", max([r["y"] + r["h"] for r in reserved] + [m]) + g)
    sx, sy = W / w, H / h
    bg = bytes(int(background.lstrip("#")[i:i + 2] if len(background) == 7 else background.lstrip("#")[i // 2] * 2, 16)
               for i in (0, 2, 4))
    x0, x1, y0, y1 = int(m / sx + 0.999), int((W - m) / sx), int(top / sy + 0.999), int((H - m) / sy)
    held = lambda x, y: any(r["x"] <= (x + 0.5) * sx <= r["x"] + r["w"] and r["y"] <= (y + 0.5) * sy <= r["y"] + r["h"]
                            for r in reserved)
    grid = [[None if held(x, y) else all(abs(rows[y][3 * x + k] - bg[k]) <= 10 for k in range(3))
             for x in range(x0, x1)] for y in range(y0, y1)]
    return grid, sx, sy, x0, y0


def section_band(it, b, fmt):
    """A full-width section: a drawing named section (its id or file) whose box spans most of the content width."""
    name = f"{it.get('id', '')} {it.get('file', '')}".lower()
    return it.get("type") == "drawing" and "section" in name and b["w"] >= 0.9 * (fmt["width_mm"] - 2 * fmt.get("margin_mm", 15))


def ink_height_seen(png, fmt, reserved, background, box):
    """How high the drawing inside box (x, y, w, h in mm) is on the rendered panel: from its top-most to its
    bottom-most row holding ink (two cells or more), so white sky above or below doesn't count. None if no ink."""
    grid, sx, sy, x0, y0 = paper_seen(png, fmt, reserved, background)
    c0, c1 = max(int(box[0] / sx) - x0, 0), int((box[0] + box[2]) / sx) - x0
    r0, r1 = max(int(box[1] / sy) - y0, 0), min(int((box[1] + box[3]) / sy) - y0, len(grid))
    inked = [j for j in range(r0, r1) if sum(1 for c in grid[j][c0:c1] if c is False) >= 2]
    return (inked[-1] - inked[0] + 1) * sy if inked else None


def paper_share_seen(png, fmt, reserved=(), background="#fff"):
    """The share of the content area (between the margins, below the reserved boxes, without them) left as paper."""
    cells = [c for line in paper_seen(png, fmt, reserved, background)[0] for c in line if c is not None]
    return cells.count(True) / len(cells) if cells else 0.0


def largest_blank_seen(png, fmt, reserved=(), background="#fff"):
    """The largest rectangle (x, y, w, h in mm) of the rendered panel between the margins that is all paper:
    the empty part of a frame or a text box counts, as on the print. Reserved boxes don't."""
    grid, sx, sy, x0, y0 = paper_seen(png, fmt, reserved, background)
    x1, heights, best = x0 + (len(grid[0]) if grid else 0), {}, (0, 0, 0, 0)
    for j, line in enumerate(grid):
        y = y0 + j
        for x in range(x0, x1):
            heights[x] = heights.get(x, 0) + 1 if line[x - x0] is True else 0
        stack = []                       # the largest rectangle under this row's histogram
        for x in range(x0, x1 + 1):
            hx, start = (heights.get(x, 0) if x < x1 else 0), x
            while stack and stack[-1][1] >= hx:
                start, hs = stack.pop()
                if (x - start) * hs * sx * sy > best[2] * best[3]:
                    best = (start * sx, (y + 1 - hs) * sy, (x - start) * sx, hs * sy)
            stack.append((start, hx))
    return best


def caption_repeats_title(it, folder):
    """The drawing's own text that the caption repeats, where the frame shows it; else None."""
    cap, f = (it.get("caption") or "").split("·")[0].split(",")[0].strip().lower(), it.get("file", "")
    if len(cap) < 4 or not f.lower().endswith(".svg") or not (folder / f).exists():
        return None
    try:
        root = ET.parse(folder / f).getroot()
    except ET.ParseError:
        return None
    vb = (root.get("viewBox") or "").replace(",", " ").split()
    k = it.get("_draw_h", 0) / float(vb[3]) if len(vb) == 4 and float(vb[3]) else 0
    for t in root.iter():
        if t.tag.rsplit("}", 1)[-1] != "text":
            continue
        words = " ".join("".join(t.itertext()).split())
        try:
            y = float(re.match(r"[\d.\-]+", t.get("y", "") or "x").group()) * k
        except (AttributeError, ValueError):
            y = None
        shown = y is None or not k or it.get("_oy", 0) <= y <= it.get("_oy", 0) + it.get("_img_h", 1e9)
        if shown and words.lower().startswith(cap):
            return words
    return None


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
    elif kind == "number":  # one key figure as big type, what it counts under it, its source in one line
        inner = (f'<div class="big" style="font-size:{pt_(it.get("pt", 2 * style["heading_pt"]))}pt">{html.escape(str(it.get("value", "")))}</div>'
                 f'<div class="what">{html.escape(it.get("text", ""))}</div>'
                 f'<div class="src">{html.escape(source_words(it.get("source", ""), folder))}</div>')
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
.box .big {{ font-weight: 700; line-height: 1; color: {style['accent']}; }}
.box.number .src {{ opacity: .6; font-size: {pt_(style['body_pt'] * 0.8)}pt; white-space: nowrap; }}
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

def render(layout_path, png_dpi, check=False):
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
            with tempfile.TemporaryDirectory() as tmp:  # a small copy, about 2 mm a pixel, to find the paper left blank
                small = Path(tmp) / "check.png"
                run_browser(browser, [f"--window-size={wpx},{hpx}", f"--force-device-scale-factor={PX_MM / 2:.4f}",
                                      "--virtual-time-budget=10000", f"--screenshot={small}", uri])
                if small.exists():
                    try:
                        res["blank_seen"] = largest_blank_seen(small, fmt, reserved, style["background"])
                        res["paper_seen"] = paper_share_seen(small, fmt, reserved, style["background"])
                        res["section_ink"] = {it["id"]: ink_height_seen(small, fmt, reserved, style["background"],
                                                                        (b["x"], b["y"], it["_img_w"], it["_img_h"]))
                                              for it, b in placed if section_band(it, b, fmt) and "_img_w" in it}
                    except (ValueError, OSError):
                        pass
            if res["pdf"]:
                res["pages"], res["sizes"] = pdf_pages(pdf)
                res["mb"] = pdf.stat().st_size / 1e6
        results.append(res)

    used = {it.get("file") for r in results for it, _ in r["placed"]}
    unused = [d for d in inv["drawings"] if d["file"] not in used]
    ids = {it["id"] for r in results for it, _ in r["placed"]}
    plan = out / "layout-plan.json"  # the first run's plan, which the second run keeps
    plan = json.loads(plan.read_text(encoding="utf-8")) if plan.exists() and plan != layout_path else None
    report = write_report(out, L, fmt, results, unused, ids, notes, inv, browser, png_dpi, plan, check)
    print(report)


def paths_left(placed, folder):
    """Headings, captions and sources that still show a file path once paths of the proposal folder are words."""
    out = []
    for it, _ in placed:
        texts = [("heading", it.get("heading")), ("caption", it.get("caption")), ("source", it.get("source"))]
        texts += [("source", r[2]) for r in it.get("rows", []) if len(r) > 2]
        for where, t in texts:
            m = PATH_RE.search(source_words(str(t), folder)) if t else None
            if m:
                out.append(f"`{it['id']}` {where}: {m.group(1)}")
    return out


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


def composition(r, n, fmt, reserved, add):
    """Report lines on one panel's hierarchy: the dominant drawing's share of the content area, the paper left on the
    rendered panel, and how high a full-width section band is for its width. Each miss is an issue for panel-layout,
    never a problem in the count."""
    W, H = fmt["width_mm"], fmt["height_mm"]
    m, g = fmt.get("margin_mm", 15), fmt.get("gutter_mm", 8)
    top = fmt.get("content_top_mm", max([q["y"] + q["h"] for q in reserved] + [m]) + g)
    content = (W - 2 * m) * (H - m - top)
    get = lambda k: fmt.get(k, DEFAULTS[k])
    size = lambda it, b: (it.get("_img_w", b["w"]), it.get("_img_h", b["h"]))  # the drawing's own box, else the placed one
    drawings = [(it, size(it, b)) for it, b in r["placed"] if it.get("type") == "drawing" and not it.get("_empty")]
    out = []
    if drawings and content > 0:
        hero, (hw, hh) = max(drawings, key=lambda d: d[1][0] * d[1][1])
        share = hw * hh / content
        whole = lambda it, wh: it.get("_draw_w", wh[0]) * it.get("_draw_h", wh[1])
        can_grow = (hero.get("_hidden", 0) > 0.01 or hero.get("_auto") or not hero.get("_print_scale")
                    or any(whole(it, wh) >= get("hero_share") * content for it, wh in drawings))
        short = share < get("hero_share")
        out.append(f"- dominant drawing: `{hero['id']}`, {100 * share:.0f} % of the content area"
                   + (f"  **under {100 * get('hero_share'):.0f} %: give one drawing the full width and put the others in bands**"
                      if short and can_grow else f" (under {100 * get('hero_share'):.0f} %, but its scale fixes its size)" if short else ""))
        if short and can_grow:
            add("here", "low", "no dominant drawing", f"panel {n}",
                f"the largest drawing, `{hero['id']}`, takes {100 * share:.0f} % of the content area (aim: {100 * get('hero_share'):.0f} % or more)",
                "give the drawing that leads this panel the full width and about 55 to 65 % of the panel; the others go in bands of one size")
    if r.get("paper_seen") is not None:
        p = r["paper_seen"]
        out.append(f"- paper seen: {100 * p:.0f} % of the content area" +
                   (f"  **over {100 * get('paper_share_max'):.0f} %**" if p > get("paper_share_max") else ""))
        if p > get("paper_share_max"):
            add("here", "low", "much of the panel left as paper", f"panel {n}",
                f"{100 * p:.0f} % of the rendered content area is paper (aim: {100 * get('paper_share_max'):.0f} % or less)",
                "enlarge the dominant drawing, close the gaps between bands, or shrink text boxes to their text")
    for it, b in r["placed"]:
        if section_band(it, b, fmt):
            iw, ih = size(it, b)
            seen = (r.get("section_ink") or {}).get(it["id"])  # measured on the render; else only the frame is known
            shown = seen if seen is not None else ih
            ratio = shown / iw
            low = ratio < get("section_ratio_min")
            out.append(f"- section band `{it['id']}`: frame {iw:.0f} x {ih:.0f} mm, "
                       + (f"drawing seen {seen:.0f} mm high" if seen is not None else "drawing not measured (no render)")
                       + f", {ratio:.2f} high for its width" + (f"  **under {get('section_ratio_min'):.2f}**" if low else ""))
            if low:
                add("here", "low", "section drawing too low", f"`{it['id']}` on panel {n}",
                    f"frame {iw:.0f} x {ih:.0f} mm, the drawing in it {shown:.0f} mm high, {ratio:.2f} of its width "
                    f"(aim: {get('section_ratio_min'):.2f} or more)",
                    "plan the section at a larger scale, where the brief fixes none, so its ground, buildings and notes fill the band; "
                    "a taller frame alone adds only sky")
    return out


def write_report(out, L, fmt, results, unused, ids, notes, inv, browser, png_dpi, plan=None, check=False):
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
        seen = r.get("blank_seen")  # on the rendered panel, frames and text boxes included; else between the boxes
        bx, by, bw, bh = seen or largest_blank([b for _, b in r["placed"]], fmt, L.get("reserved", []))
        blank = {"x": bx, "y": by, "w": bw, "h": bh}
        inside = max(r["placed"], key=lambda p: area_of(p[1], blank), default=None)
        where = (f"inside `{inside[0]['id']}`" if inside and area_of(inside[1], blank) > 0.5 * bw * bh else "between the items")
        fits = sorted(((it, b) for it, b in r["placed"] if it.get("type") == "drawing" and b["w"] <= bw and b["h"] <= bh),
                      key=lambda p: p[1]["w"] * p[1]["h"])
        side = fmt.get("blank_min_side_mm", DEFAULTS["blank_min_side_mm"])
        large = min(bw, bh) >= side and bw * bh >= 100 * fmt.get("blank_min_cm2", DEFAULTS["blank_min_cm2"])
        lines.append(f"- largest blank block{' seen' if seen else ''}: {bw:.0f} x {bh:.0f} mm at ({bx:.0f}, {by:.0f}) mm, "
                     f"{bw * bh / 100:.0f} cm², {where}"
                     + (f"  **a drawing of this panel would fit in it (`{fits[0][0]['id']}`, {fits[0][1]['w']:.0f} x "
                        f"{fits[0][1]['h']:.0f} mm): fill it, shrink the frame or the text box, or move the items together**"
                        if fits else "  **a large blank: fill it, shrink the frame or the text box, or move the items together**"
                        if large else ""))
        if fits or large:  # a planned drawing that didn't fit, whose frame the blank mostly covers, is its skill's to fix
            slots = [(it, {"x": it["x"], "y": it["y"], **(it.get("frame") or {"w": 0, "h": 0})}) for it, _ in r["unplaced"]
                     if it.get("type") == "drawing" and "x" in it and "y" in it]
            held_by = [it for it, box in slots if area_of(box, blank) > 0.3 * min(bw * bh, box["w"] * box["h"] or 1)]
            evidence = (f"{bw:.0f} x {bh:.0f} mm of paper at ({bx:.0f}, {by:.0f}) mm, {where}; "
                        + (f"`{fits[0][0]['id']}` would fit in it" if fits else
                           f"at least {side:g} mm each way and {fmt.get('blank_min_cm2', DEFAULTS['blank_min_cm2']):g} cm²"))
            sev = "medium" if fits else "low"
            if held_by:
                for it in held_by:
                    sk = skill_of(it.get("file"), req_by.get(it["id"]))
                    add("upstream", sev, "blank space left where a planned drawing didn't fit", f"`{it['id']}` on panel {n} ({it.get('file')})",
                        evidence, f"draw {it.get('file')} at {it.get('scale', 'its planned scale')} to its frame", sk)
            else:
                add("here", sev, "blank space where a drawing would fit" if fits else "large blank space", f"panel {n}", evidence,
                    "fill it with a drawing from the folder the storyline can use, shrink the frame or text box, or move the items together")
        lines += composition(r, n, fmt, L.get("reserved", []), add)
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
            elif it.get("type") == "number" and not it.get("source"):
                problems += 1
                held = "  **a number without its source**"
                add("here", "medium", "a number without its source", what, "a `number` item with no `source`",
                    "give the table or summary it comes from")
            elif it.get("type") == "figures" and iid not in req_ids:  # like "panel mostly empty": for issues.md, not the count
                held = "  **a table the brief doesn't ask for: show its key numbers as `number` items**"
                add("here", "low", "a table the brief doesn't ask for", what, "a `figures` box that no `required` item points to",
                    "show its key numbers as `number` items, each with its source, or leave it out")
            twice = it.get("type") == "drawing" and not it.get("_empty") and caption_repeats_title(it, out.parent)
            if twice:
                held += f"  **its caption repeats the drawing's own title (\"{twice[:40]}\"): leave the caption out, or crop the title out of the frame**"
                add("here", "low", "caption repeats the drawing's own title", what, f"the drawing prints \"{twice[:60]}\"",
                    "leave the caption out, or crop the title out of the frame")
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
    gone = []  # planned items left out of layout.json
    if plan is not None:  # every item of the first run's plan is on the panels, by its id or its file
        files = {it.get("file") for r in results for it, _ in r["placed"]}
        why = {it.get("id"): w for r in results for it, w in r["unplaced"]}
        dropped = [it for p in plan.get("panels", []) for it in p.get("items", [])
                   if it.get("id") not in ids and not (it.get("file") and it["file"] in files)]
        gone = [it for it in dropped if it.get("id") not in why]  # one that did not fit is counted on its panel
        problems += len(gone)
        lines.append("## Planned items not on the panels")
        lines.append("In `layout-plan.json`, the first run's plan, and not placed now. Never drop a planned drawing.")
        lines += [f"- **`{it.get('id', '?')}`** ({it.get('file', it.get('type', 'text'))}): "
                  + (f"not placed, {why[it.get('id')]}" if it.get("id") in why else "left out of layout.json")
                  for it in dropped] or ["- none"]
        now = {it.get("id"): it for q in L.get("panels", []) for it in q.get("items", [])}
        say = lambda v: "none" if v is None else f"{v.get('w'):g} x {v.get('h'):g} mm" if isinstance(v, dict) else v
        planned = [(n, it) for n, q in enumerate(plan.get("panels", []), 1) for it in q.get("items", [])]
        lines += [f"- `{it['id']}`: {k} planned as {say(it.get(k))}, now {say(now[it['id']].get(k))}"
                  for _, it in planned if it.get("type") == "drawing" and it.get("id") in now
                  for k in ("file", "scale", "frame") if it.get(k) != now[it["id"]].get(k)]
        for n, it in planned:
            if it in gone:
                add("here", "high" if it.get("id") in req_ids else "medium", "planned item dropped from layout.json",
                    f"`{it.get('id', '?')}` ({it.get('file', it.get('type', 'text'))}), planned on panel {n}",
                    "in layout-plan.json, not in layout.json", "put it back in its planned frame")
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
    conflicts = figure_conflicts(results, L)
    lines.append("## Numbers to check")
    lines.append("Figures with the same label and different values; neither is corrected here.")
    for label, named, values in conflicts:
        problems += not named
        shown = "; ".join(f"{v} (panel {n}{', ' + source_words(str(s), folder) if s else ''})" for n, v, s in values)
        lines.append(f"- {'' if named else '**'}{label}: {shown}" + ("  (named in notes)" if named else "**"))
        add("upstream", "medium", "figures that should agree don't", f"figure \"{label}\"", shown,
            "the skills behind these sources agree on one value; until then the panel shows the number of the skill that designs it, the other goes in `notes`",
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
                  f"Required drawings cropped over {100 * crop_limit:.0f} %: {len(over_crop)}. Planned items dropped: {len(gone)}."]
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
    a = ap.parse_args()
    if a.cmd == "scan":
        inv = scan(a.folder)
        print(json.dumps({k: v for k, v in inv.items() if k != "skills"}, indent=1, ensure_ascii=False))
        print("summaries:", ", ".join(k for k, v in inv["skills"].items() if v["summary"]) or "none")
    else:
        render(a.layout, a.png_dpi, a.check)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
