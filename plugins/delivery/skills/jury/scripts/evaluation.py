"""One 16:9 slide of the jury's closeness scores: each drawing beside its reference (or what a 5 shows), score and why.

    python evaluation.py <proposal folder>

Reads <proposal>/jury/closeness.csv with the columns drawing, kind, score, why, image, reference:
- image: the drawing's PNG, relative to the proposal folder, or a panel and the box the drawing sits in as
  fractions of its width and height, `panel-layout/panel-2.png@0.05 0.10 0.95 0.60` (spaces, not commas).
- kind: a bold name from ../closeness.md (Site plan, Perspective, ...); its "a 5 shows" stands in for a missing reference.
  A whole panel is a row of kind `The boards` with the panel PNG as its image; boards get their own row on the slide.
- reference: a reference image's path (absolute, or relative to the proposal folder), or empty.
Takes the verdict from the first sentence of jury/summary.md. Writes jury/evaluation.png, 1920 x 1080. Needs Pillow.
"""
import csv
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1920, 1080
INK, GREY, LINE, PALE = (34, 34, 34), (130, 130, 130), (215, 215, 215), (243, 241, 236)
COL = {1: (200, 50, 43), 2: (200, 140, 40), 3: (63, 125, 85), 4: (63, 125, 85), 5: (40, 90, 60)}
RUBRIC = Path(__file__).resolve().parent.parent / "closeness.md"


def font(size, bold=False):
    for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def wrap(d, text, f, width):
    lines, line = [], ""
    for w in text.split():
        if line and d.textlength(line + " " + w, font=f) > width:
            lines.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    return lines + ([line] if line else [])


def a5(kind):
    """The 'a 5 shows' line for a kind, from closeness.md."""
    if not RUBRIC.exists():
        return ""
    for line in RUBRIC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"- \*\*(.+?)\.?\*\*\s*(.*)", line)
        if m and kind.strip() and m.group(1).lower().startswith(kind.lower().strip()):
            return m.group(2)
    return ""


def load(spec, root):
    """An image from a path, or a box of a panel: path@x0 y0 x1 y1 in fractions."""
    path, _, box = spec.partition("@")
    p = Path(path) if Path(path).is_absolute() else root / path
    if not path or not p.exists():
        return None
    im = Image.open(p).convert("RGB")
    if box:
        x0, y0, x1, y1 = (float(v) for v in re.split(r"[\s,]+", box.strip()))
        im = im.crop((int(x0 * im.width), int(y0 * im.height), int(x1 * im.width), int(y1 * im.height)))
    return im


def main():
    root = Path(sys.argv[1]).resolve()
    rows = list(csv.DictReader(open(root / "jury" / "closeness.csv", encoding="utf-8")))
    for r in rows:
        r["score"] = max(1, min(5, int(float(r["score"]))))
    boards = [r for r in rows if r.get("kind", "").lower().lstrip("the ").startswith("board")]
    drawings = [r for r in rows if r not in boards]
    total, most = sum(r["score"] for r in rows), 5 * len(rows)
    part = lambda rs: f"{sum(r['score'] for r in rs)} of {5 * len(rs)}"
    summary = root / "jury" / "summary.md"
    verdict = re.split(r"(?<=\.)\s", summary.read_text(encoding="utf-8").strip(), 1)[0] if summary.exists() else ""

    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.text((60, 36), f"Closeness to the awarded level: {total} of {most} (mean {total / len(rows):.1f} of 5)",
           font=font(34, True), fill=INK)
    sub = f"{root.name}  ·  boards {part(boards)}  ·  drawings {part(drawings)}  ·  {verdict}" if boards else f"{root.name}  ·  {verdict}"
    f21 = font(21)
    while d.textlength(sub, font=f21) > W - 120:
        sub = sub[:-2].rstrip() + "…"
    d.text((60, 86), sub, font=f21, fill=GREY)

    # left: every board and drawing as a bar
    x0, y = 60, 150
    step = min(36, (H - 110 - y - 80) // max(1, len(rows)))
    for title, group in (("Each board as a whole", boards), ("Every drawing the brief requires", drawings)):
        if not group:
            continue
        d.text((x0, y), title, font=font(19, True), fill=INK)
        y += 34
        for r in group:
            name, f17 = r["drawing"], font(17)
            while d.textlength(name, font=f17) > 205:
                name = name.rsplit(",", 1)[0] if "," in name else name[:-2].rstrip() + "…"
            d.text((x0, y), name, font=f17, fill=INK)
            for k in range(5):
                bx = x0 + 215 + k * 40
                d.rectangle([bx, y + 2, bx + 32, y + 20], fill=COL[r["score"]] if k < r["score"] else LINE)
            d.text((x0 + 420, y), str(r["score"]), font=font(17, True), fill=INK)
            y += step
        y += 24
    d.text((x0, H - 60), "Scale: 1 nothing alike or missing · 3 right content, less detail · 5 could stand on an awarded board",
           font=font(15), fill=GREY)

    def card(r, cx, cy, cw, ch, board):
        d.rounded_rectangle([cx, cy, cx + cw, cy + ch], 10, outline=LINE, width=2)
        d.text((cx + 12, cy + 8), r["drawing"], font=font(18, True), fill=INK)
        th = ch - 52
        if board:
            slots, tw = [(load(r["image"], root), "Ours")], int(th * 0.71)
        else:
            ref = load(r.get("reference", ""), root)
            slots, tw = [(ref, "Reference") if ref else (None, "A 5 shows"), (load(r["image"], root), "Ours")], th
        tx = cx + 12
        for pic, label in slots:
            ty = cy + 36
            if pic is not None:
                im.paste(ImageOps.pad(pic, (tw, th), Image.LANCZOS, color="white"), (tx, ty))
            else:
                d.rectangle([tx, ty, tx + tw, ty + th], fill=PALE)
                text = a5(r.get("kind", "")) if label == "A 5 shows" else "not found"
                f = font(13)
                for k, ln in enumerate(wrap(d, text, f, tw - 12)[: (th - 10) // 16]):
                    d.text((tx + 6, ty + 6 + k * 16), ln, font=f, fill=INK)
            d.rectangle([tx, ty, tx + tw, ty + th], outline=LINE)
            d.text((tx, ty + th + 1), label, font=font(13), fill=GREY)
            tx += tw + 8
        sx = tx + 4
        d.text((sx, cy + 30), str(r["score"]), font=font(52, True), fill=COL[r["score"]])
        d.text((sx + 4, cy + 90), "of 5", font=font(16), fill=GREY)
        f, lh, wx = font(14 if board else 15), 17 if board else 19, sx + 64
        for k, ln in enumerate(wrap(d, r["why"], f, cx + cw - wx - 10)[: max(1, (ch - 46) // lh)]):
            d.text((wx, cy + 38 + k * lh), ln, font=f, fill=INK)

    # right: the boards in one row, then the lowest-scored drawings
    cx0, right, top, bottom, gap = 540, 1860, 140, H - 70, 10
    if boards:
        bs = boards[:3]
        bw, bh = (right - cx0 - gap * (len(bs) - 1)) // len(bs), 300
        for i, r in enumerate(bs):
            card(r, cx0 + i * (bw + gap), top, bw, bh, True)
        top += bh + gap
    cards = sorted(drawings, key=lambda r: r["score"])[: 6 if boards else 10]
    if cards:
        cols = 2 if len(cards) > 3 else 1
        nrows = math.ceil(len(cards) / cols)
        cw = (right - cx0 - gap * (cols - 1)) // cols
        ch = (bottom - top - gap * (nrows - 1)) // nrows
        for i, r in enumerate(cards):
            card(r, cx0 + (i % cols) * (cw + gap), top + (i // cols) * (ch + gap), cw, ch, False)

    out = root / "jury" / "evaluation.png"
    im.save(out)
    print(f"wrote {out}: {len(boards)} boards, {len(drawings)} drawings, {total} of {most}")


if __name__ == "__main__":
    main()
