"""Side-by-side sheets: the project's reference drawings of one kind beside the version's own, at one print size.

    python side_by_side.py <version> [--references <folder>] [--out <folder>] [--panel-mm <mm>]

One sheet per skill that has both: references on the left, the version's drawings on the right, every tile at the
same pixels per millimetre of paper, so a 150 mm patch looks the same size on both sides. A last sheet puts the
reference boards beside the version's panels. Sheets go to <version>/.compare/ (a folder panel-layout skips and a
variant run need not copy). No model is called; needs only Pillow.

Which references: <references>/references.json if there is one, {"skill": ["glob", ...], "cut_zoom": 1.25}, with
globs relative to the references folder; else the backticked stems in the second column of the README's table
(| skill | `stem`, `stem-*` |), searched in the folder and in the folders below it; a trailing -N counts as -*.
Pixels per mm: a board's width over the panel width (from <version>/panel-layout/layout.json, or --panel-mm); a cut
drawing is cut at cut_zoom times the board's resolution; ours from the SVG's size in mm; a drawing without a scale is
fitted to the width of the references beside it.
"""
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

IMG = {".png", ".jpg", ".jpeg"}
SKIP_OURS = re.compile(r"_(base|depth|ids|mask|marked)$")  # helper images next to a drawing
BOARD_SKILLS = {"drawing-graphics", "panel-layout", "jury"}  # their references are the boards, compared on their own sheet
MM_PER = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72}
CUT_ZOOM = 1.25  # the winners' cut drawings are cut at 1.25 x the board's pixels per mm (measured by matching them to the boards)
SHEET_PX_MM = 3.0  # pixels per mm on a sheet
MAX_SIDE = 6000  # a sheet is scaled down, all tiles together, past this
MAX_TILES = 6  # per side
FRAME_MM = 150.0  # width for a drawing without a scale, when there is nothing beside it to take it from
BAR = 44  # height of a label bar


def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def svg_mm(path):
    """(width, height) in mm of an SVG whose size carries a physical unit, else None."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    out = []
    for key in ("width", "height"):
        m = re.fullmatch(r"\s*([\d.]+)\s*([a-z%]*)\s*", root.get(key) or "")
        if not m or m.group(2) not in MM_PER:
            return None
        out.append(float(m.group(1)) * MM_PER[m.group(2)])
    return tuple(out)


def entry_label(folder):
    m = re.match(r"(\d+)_([a-z]+)", folder.name)
    return f"Winner {m.group(1)} ({m.group(2)})" if m else folder.name


# ---------- references ----------

def readme_patterns(refs):
    """{skill: [glob, ...]} from the backticked stems of the README's table."""
    readme = refs / "README.md"
    out = {}
    if not readme.exists():
        return out
    for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.lstrip().startswith("|") or len(cells) < 2 or set(cells[0]) <= set("-: "):
            continue
        skill = cells[0].strip("` ")
        for stem in re.findall(r"`([^`]+)`", cells[1]):
            stem = re.sub(r"\.(jpe?g|png)$", "", stem)
            stem = re.sub(r"-\d+$", "-*", stem)
            pat = stem if stem.endswith("*") else stem + ".*"
            out.setdefault(skill, [])
            for p in (pat, "**/" + pat):
                if p not in out[skill]:
                    out[skill].append(p)
    return out


def reference_files(refs, patterns):
    seen, files = set(), []
    for pat in patterns:
        for f in sorted(refs.glob(pat)):
            if f.suffix.lower() in IMG and "_marked" not in f.stem and f not in seen:
                seen.add(f)
                files.append(f)
    return sorted(files, key=lambda f: (f.parent.name, f.name))


def board_px(entry_folder):
    """Pixel width of an entry's boards (board-N.jpg), 0 if it has none."""
    for f in sorted(entry_folder.glob("board-?.*")):
        if "_marked" not in f.stem and f.suffix.lower() in IMG:
            return Image.open(f).width
    return 0


def ref_px_mm(f, panel_mm, zoom, cache={}):
    """Pixels per mm of paper of a reference image, or None if unknown."""
    if not panel_mm:
        return None
    if f.parent not in cache:
        cache[f.parent] = board_px(f.parent)
    if not cache[f.parent]:
        return None
    k = 1.0 if f.stem.startswith("board-") else zoom
    return cache[f.parent] / panel_mm * k


# ---------- ours ----------

def our_drawings(version):
    """{skill: [(png path, mm width or None, mm height or None), ...]} for every drawing in the version."""
    out = {}
    for sub in sorted(p for p in version.iterdir() if p.is_dir() and not p.name.startswith(".")):
        if sub.name in BOARD_SKILLS:
            continue
        for f in sorted(sub.rglob("*")):
            if f.suffix.lower() not in IMG or SKIP_OURS.search(f.stem):
                continue
            if any(part.startswith(".") for part in f.relative_to(version).parts):
                continue
            size = svg_mm(f.with_suffix(".svg")) if f.with_suffix(".svg").exists() else None
            out.setdefault(sub.name, []).append((f, size))
    return out


# ---------- drawing the sheets ----------

def tile(img, label, width_px):
    img = img.convert("RGB")
    img = img.resize((max(1, width_px), max(1, round(img.height * width_px / img.width))), Image.LANCZOS)
    t = Image.new("RGB", (img.width, img.height + BAR), "white")
    t.paste(img, (0, BAR))
    d = ImageDraw.Draw(t)
    d.rectangle((0, 0, img.width, BAR - 4), fill=(30, 30, 30))
    d.text((10, 6), label, fill="white", font=font(28))
    return t


def stack(tiles, gap=16):
    w = max(t.width for t in tiles)
    out = Image.new("RGB", (w, sum(t.height for t in tiles) + gap * (len(tiles) - 1)), "white")
    y = 0
    for t in tiles:
        out.paste(t, (0, y))
        y += t.height + gap
    return out


def save(columns, path, gap=24):
    cols = [stack(c) for c in columns if c]
    sheet = Image.new("RGB", (sum(c.width for c in cols) + gap * (len(cols) - 1), max(c.height for c in cols)), "white")
    x = 0
    for c in cols:
        sheet.paste(c, (x, 0))
        x += c.width + gap
    k = min(1.0, MAX_SIDE / sheet.width, MAX_SIDE / sheet.height)
    if k < 1:
        sheet = sheet.resize((int(sheet.width * k), int(sheet.height * k)), Image.LANCZOS)
    sheet.save(path, quality=86)
    return sheet.size


def scale_name(f):
    m = re.search(r"(?:^|_)1-(\d+)", f.stem)
    return f", 1:{int(m.group(1)):,}" if m else ""


def skill_sheet(skill, refs, ours, panel_mm, zoom, out_dir):
    left, widths = [], []
    for f in refs[:MAX_TILES]:
        ppm = ref_px_mm(f, panel_mm, zoom)
        im = Image.open(f)
        mm = im.width / ppm if ppm else None
        if mm:
            widths.append(mm)
        left.append((f, im, mm))
    frame = sorted(widths)[len(widths) // 2] if widths else FRAME_MM
    left = [tile(im, f"{entry_label(f.parent)}: {f.stem}" + ("" if mm else " (no scale, fitted)"),
                 round((mm or frame) * SHEET_PX_MM)) for f, im, mm in left]
    right = []
    for f, size in ours[:MAX_TILES]:
        im = Image.open(f)
        mm = size[0] if size else None
        right.append(tile(im, f"Ours: {skill}/{f.stem}" + (f" ({mm:.0f} x {size[1]:.0f} mm)" if mm else " (no scale, fitted)"),
                          round((mm or frame) * SHEET_PX_MM)))
    path = out_dir / f"{skill}.jpg"
    return path, save([left, right], path)


def boards_sheet(refs_root, version, out_dir, width=700):
    rows = []
    for entry in sorted(p for p in refs_root.glob("*/") if p.is_dir()):
        row = [tile(Image.open(f), f"{entry_label(entry)}, {f.stem}", width)
               for f in sorted(entry.glob("board-?.*")) if "_marked" not in f.stem and f.suffix.lower() in IMG]
        if row:
            rows.append(row)
    panels = sorted((version / "panel-layout").glob("panel-?.png"))
    if not rows or not panels:
        return None
    rows.append([tile(Image.open(f), f"Ours: {f.stem}", width) for f in panels])
    path = out_dir / "boards.jpg"
    # one column per board number, one row per entry: columns of the rows' tiles
    cols = [[r[i] for r in rows if i < len(r)] for i in range(max(len(r) for r in rows))]
    return path, save(cols, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version", type=Path)
    ap.add_argument("--references", type=Path, help="default: references/ in the version's project (next to proposals/)")
    ap.add_argument("--out", type=Path, help="default: <version>/.compare")
    ap.add_argument("--panel-mm", type=float, help="panel width in mm, default from panel-layout/layout.json")
    a = ap.parse_args()
    version = a.version.resolve()
    refs = (a.references or version.parent.parent / "references").resolve()
    out_dir = (a.out or version / ".compare").resolve()
    if not refs.is_dir():
        sys.exit(f"no references folder at {refs}")
    out_dir.mkdir(parents=True, exist_ok=True)

    panel_mm = a.panel_mm
    layout = version / "panel-layout" / "layout.json"
    if not panel_mm and layout.exists():
        try:
            panel_mm = float(json.loads(layout.read_text(encoding="utf-8"))["format"]["width_mm"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if not panel_mm:
        print("no panel width (layout.json or --panel-mm): references are fitted to width, not at print size")

    conf = {}
    if (refs / "references.json").exists():
        conf = json.loads((refs / "references.json").read_text(encoding="utf-8"))
    zoom = float(conf.get("cut_zoom", CUT_ZOOM))
    patterns = {k: ([v] if isinstance(v, str) else v) for k, v in conf.items() if k != "cut_zoom"} or readme_patterns(refs)

    ours = our_drawings(version)
    made = []
    for skill, pats in patterns.items():
        if skill in BOARD_SKILLS:
            continue
        files = reference_files(refs, pats)
        if not files or skill not in ours:
            print(f"  {skill}: {'no reference' if not files else 'nothing of ours'}, no sheet")
            continue
        path, size = skill_sheet(skill, files, ours[skill], panel_mm, zoom, out_dir)
        made.append(path)
        print(f"  {path.name}: {len(files)} references, {len(ours[skill])} of ours, {size[0]} x {size[1]} px")
    r = boards_sheet(next((p for p in [refs / "winners", refs] if any(p.glob("*/board-?.*"))), refs), version, out_dir)
    if r:
        made.append(r[0])
        print(f"  {r[0].name}: boards beside our panels, {r[1][0]} x {r[1][1]} px")
    print(f"wrote {len(made)} sheets in {out_dir}")


if __name__ == "__main__":
    main()
