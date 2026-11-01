"""Panels for a competition entry, in two steps.

  python panels.py scan   <proposal folder>
      Lists every summary, drawing, table and text in the proposal folder, with each
      drawing's print size, and writes panel-layout/inventory.json.

  python panels.py render <proposal folder>/panel-layout/layout.json [--png-dpi 96]
      Places the items of layout.json on the panels, keeps scaled drawings at their print
      size, renders panel-N.html/.pdf/.png with a headless Chrome or Edge, checks the
      result and writes panel-layout/report.md.

Needs Python 3.11+ and Chrome, Edge or Chromium. Set BROWSER to its path if it isn't found.
"""

import argparse
import csv
import html
import json
import os
import re
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
    return out


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
    """The scale a skill's summary.md gives for this drawing: on the line naming it, else the only one given."""
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
           "checklist": None, "standard": None, "missing": []}
    for sub in sorted(p for p in folder.iterdir() if p.is_dir() and p.name != OWN):
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


def measure(item, folder, inv_by_file, style, notes):
    """Fill item['w'], item['h'] (mm, the whole box with caption) and how the drawing is sized."""
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
            item["_error"] = f"file not found: {f}"
            return
        d = svg_size(p) if p.suffix.lower() == ".svg" else raster_size(p)
    sc = scale_number(item.get("scale"))
    item["_cap"] = cap_mm
    if sc:
        if "w_mm" in d and "h_mm" in d:
            item["_img_w"], item["_img_h"] = d["w_mm"], d["h_mm"]
            item["_scale_held"] = True
            if item.get("w") and abs(item["w"] - d["w_mm"]) > 0.5:
                notes.append(f"`{item['id']}`: width {item['w']} mm ignored; at {item['scale']} the drawing is {d['w_mm']:.0f} mm wide")
        elif "dpi" in d:
            item["_img_w"], item["_img_h"] = d["w_px"] / d["dpi"] * 25.4, d["h_px"] / d["dpi"] * 25.4
            item["_scale_held"] = True
        else:
            item["_scale_held"] = False
            notes.append(f"`{item['id']}` ({f}) has no print size (width and height in mm), so {item['scale']} can't be held; placed at the width asked for")
    if item.get("scale_bar") and item.get("_scale_held"):
        item["_cap"] += 8  # room for the scale bar, which is drawn only when the scale is held
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
        measure(it, folder, inv_by_file, style, notes)
        if "_error" in it:
            unplaced.append((it, it["_error"]))
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
        if box["x"] < 0 or box["y"] < 0 or box["x"] + box["w"] > W + 0.01 or box["y"] + box["h"] > H - m + 0.01:
            unplaced.append((it, f"needs {box['w']:.0f} x {box['h']:.0f} mm at ({box['x']:.0f}, {box['y']:.0f}); "
                                 f"runs past the panel's edge or bottom margin"))
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
    if kind == "drawing":
        src = (folder / it["file"]).resolve().as_uri()
        inner = f'<img src="{src}" style="width:{it["_img_w"]:.2f}mm;height:{it["_img_h"]:.2f}mm">'
        sc = scale_number(it.get("scale"))
        if it.get("scale_bar") and sc and it.get("_scale_held"):
            length = nice_length(it["_img_w"] * 0.25 * sc / 1000)
            bar_mm = length * 1000 / sc
            lw = style["line_mm"]
            fs = style["body_pt"] * 25.4 / 72 * 0.7  # label size follows the body text
            inner += (f'<svg class="bar" width="{bar_mm + 30:.2f}mm" height="7mm" viewBox="0 0 {bar_mm + 30:.2f} 7">'
                      f'<rect x="0.2" y="1" width="{bar_mm / 2:.2f}" height="1.5" fill="{style["text"]}"/>'
                      f'<rect x="{bar_mm / 2 + 0.2:.2f}" y="1" width="{bar_mm / 2:.2f}" height="1.5" fill="none" stroke="{style["text"]}" stroke-width="{lw}"/>'
                      f'<text x="0.2" y="6" font-size="{fs:.2f}">0</text><text x="{bar_mm + 1.5:.2f}" y="2.6" font-size="{fs:.2f}">{length:g} m</text></svg>')
        if it.get("caption"):
            sc = scale_number(it.get("scale"))
            cap = it["caption"] + (f" · 1:{sc:,}" if sc and it.get("_scale_held") else "")
            inner += f'<div class="cap">{html.escape(cap)}</div>'
    elif kind == "figures":
        rows = "".join(
            f'<tr><td>{html.escape(str(r[0]))}</td><td class="v">{html.escape(str(r[1]))}</td>'
            f'<td class="src">{html.escape(str(r[2])) if len(r) > 2 else ""}</td></tr>' for r in it.get("rows", []))
        head = f"<h2>{html.escape(it['heading'])}</h2>" if it.get("heading") else ""
        inner = f"{head}<table>{rows}</table>"
    else:
        head = f"<h2>{html.escape(it['heading'])}</h2>" if it.get("heading") else ""
        pt = it.get("pt")
        st = f' style="font-size:{pt}pt;line-height:1.1;font-weight:{it.get("weight", 400)}"' if pt else ""
        inner = f"{head}<div{st}>{paragraphs(it.get('text', ''))}</div>"
    return f'<div class="box {kind}" id="{html.escape(it["id"])}" style="{s}">{inner}</div>'


CHECK_JS = """
<script>
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
    c = {**ctx, "n": n, "total": total}
    parts = [item_html(it, b, style, folder) for it, b in placed]
    for r in reserved:
        border = f"border:{style['line_mm']}mm dashed rgba(0,0,0,.12);" if r.get("outline") else ""
        parts.append(f'<div class="reserved" style="left:{r["x"]}mm;top:{r["y"]}mm;width:{r["w"]}mm;height:{r["h"]}mm;{border}"></div>')
    for mk in marks:
        align = mk.get("align", "left")
        pos = f"top:{mk['y']}mm;" + (f"right:{mk['x']}mm;" if align == "right" else f"left:{mk['x']}mm;")
        parts.append(f'<div class="mark" style="{pos}font-size:{mk.get("pt", 14)}pt;font-weight:{mk.get("weight", 400)};'
                     f'text-align:{align}">{html.escape(fill(mk["text"], c))}</div>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Panel {n}</title><style>
@page {{ size: {W}mm {H}mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: {W}mm; height: {H}mm; overflow: hidden; background: {style['background']}; color: {style['text']};
  font-family: {style['font']}; font-size: {style['body_pt']}pt; line-height: 1.35;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.box, .reserved, .mark {{ position: absolute; }}
@media print {{ .reserved {{ border: none !important; }} }}
.box {{ overflow: hidden; }}
.box img {{ display: block; }}
.box h2 {{ font-size: {style['heading_pt']}pt; line-height: 1.15; margin-bottom: 0.4em; font-weight: 700; }}
.box p {{ margin-bottom: 0.6em; }}
.box .cap {{ font-size: {style['body_pt']}pt; margin-top: 1mm; }}
.box .bar {{ display: block; margin-top: 1mm; font-family: inherit; fill: {style['text']}; }}
.box table {{ border-collapse: collapse; width: 100%; }}
.box td {{ border-top: {style['line_mm']}mm solid {style['text']}; padding: 1.2mm 2mm 1.2mm 0; vertical-align: top; }}
.box td.v {{ font-weight: 700; color: {style['accent']}; white-space: nowrap; }}
.box td.src {{ opacity: .6; font-size: .8em; }}
</style></head><body>
{chr(10).join(parts)}
{CHECK_JS}</body></html>"""


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
               "--allow-file-access-from-files", f"--user-data-dir={prof}", *args]
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

def render(layout_path, png_dpi):
    layout_path = Path(layout_path).resolve()
    out = layout_path.parent
    folder = out.parent
    L = json.loads(layout_path.read_text(encoding="utf-8"))
    fmt = L["format"]
    style = {"font": "Helvetica, Arial, sans-serif", "text": "#000", "background": "#fff", "accent": "#d0312d",
             "line_mm": 0.25, "heading_pt": 20, "body_pt": 11, **L.get("style", {})}
    reserved = L.get("reserved", [])
    marks = L.get("marks", [])
    ctx = L.get("labels", {})
    inv = scan(folder)
    inv_by_file = {d["file"]: d for d in inv["drawings"]}
    panels = L["panels"]
    total = len(panels)
    browser = find_browser()
    notes, results = [], []

    for i, panel in enumerate(panels, 1):
        placed, unplaced = place(panel, fmt, reserved, style, folder, inv_by_file, notes)
        page = panel_html(i, total, placed, fmt, reserved, marks, style, ctx, folder)
        hp = out / f"panel-{i}.html"
        hp.write_text(page, encoding="utf-8")
        res = {"n": i, "placed": placed, "unplaced": unplaced, "checks": [], "story": panel.get("story", "")}
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
    report = write_report(out, L, fmt, results, unused, ids, notes, inv, browser, png_dpi)
    print(report)


def write_report(out, L, fmt, results, unused, ids, notes, inv, browser, png_dpi):
    W, H = fmt["width_mm"], fmt["height_mm"]
    max_mb = fmt.get("max_mb")
    lines = [f"# Panel layout: report", "",
             f"Format: {W:g} x {H:g} mm, {len(results)} of {fmt.get('panels', len(results))} panels asked for "
             f"({fmt.get('source', 'source not given')}). Style: {L.get('style', {}).get('source', 'no standard, black on white with one accent')}.", ""]
    if not browser:
        lines += ["**No Chrome, Edge or Chromium found: only the HTML was written, no PDF or PNG.** Set BROWSER to its path.", ""]
    problems = 0
    for r in results:
        lines.append(f"## Panel {r['n']}")
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
        elif browser:
            problems += 1
            lines.append("- **PDF was not written**")
        area = sum(b["w"] * b["h"] for _, b in r["placed"]) / (W * H)
        lines.append(f"- covered by items: {100 * area:.0f} % of the panel" + ("  **mostly empty**" if area < 0.35 else ""))
        for it, b in r["placed"]:
            held = ""
            if it.get("type") == "drawing" and it.get("scale"):
                sc = f"1:{scale_number(it['scale']):,}"
                held = f", {sc} held" if it.get("_scale_held") else f", **{sc} not held**"
            lines.append(f"- placed `{it['id']}` at ({b['x']:.0f}, {b['y']:.0f}) mm, {b['w']:.0f} x {b['h']:.0f} mm{held}")
        for it, why in r["unplaced"]:
            problems += 1
            lines.append(f"- **did not fit: `{it['id']}`** ({it.get('file', it.get('type', 'text'))}): {why}")
        for c in r["checks"]:
            problems += 1
            extra = f" (needs {c['need_h_mm']} mm, has {c['has_h_mm']} mm)" if c.get("need_h_mm") else ""
            lines.append(f"- **{c['problem']}: `{c['id']}`**{extra}")
        lines.append("")
    req = L.get("required", [])
    missing = [q for q in req if not q.get("id") or q["id"] not in ids]
    lines.append("## What the brief asks for")
    for q in req:
        state = "**MISSING**" if q in missing else f"on the panels, `{q['id']}`"
        lines.append(f"- {q['what']} ({q.get('source', '')}): {state}"
                     + (f". {q['note']}" if q.get("note") else ""))
    if not req:
        lines.append("- **No list of required items in layout.json: nothing was checked against the brief.**")
    lines.append("")
    lines.append("## Drawings in the proposal folder not on the panels")
    lines += [f"- {d['file']}" for d in unused] or ["- none"]
    lines.append("")
    lines.append("## Inputs missing")
    lines += [f"- {m}" for m in inv["missing"] + L.get("missing", [])] or ["- none"]
    if notes:
        lines += ["", "## Notes"] + [f"- {n}" for n in notes]
    lines += ["", f"Problems: {problems}. Required items missing: {len(missing)} of {len(req)}."]
    text = "\n".join(lines) + "\n"
    (out / "report.md").write_text(text, encoding="utf-8")
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("folder")
    r = sub.add_parser("render")
    r.add_argument("layout")
    r.add_argument("--png-dpi", type=int, default=96)
    a = ap.parse_args()
    if a.cmd == "scan":
        inv = scan(a.folder)
        print(json.dumps({k: v for k, v in inv.items() if k != "skills"}, indent=1, ensure_ascii=False))
        print("summaries:", ", ".join(k for k, v in inv["skills"].items() if v["summary"]) or "none")
    else:
        render(a.layout, a.png_dpi)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
