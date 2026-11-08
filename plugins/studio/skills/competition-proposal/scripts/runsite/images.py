"""Pictures for the runs site: small JPGs made from a run's PNGs and panels."""
from pathlib import Path

from PIL import Image


def _save(im, dst, long_side):
    im = im.convert("RGB")
    scale = long_side / max(im.size)
    if scale < 1:
        im = im.resize((max(1, round(im.size[0] * scale)), max(1, round(im.size[1] * scale))), Image.LANCZOS)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=82, optimize=True)


def to_jpg(src, dst, long_side):
    """The picture as a JPG whose long side is at most long_side; False if it can't be read."""
    try:
        with Image.open(src) as im:
            _save(im, dst, long_side)
    except Exception:
        return False
    return True


def crop(panel_png, box, dst, long_side):
    """The part of a panel inside box = (x, y, w, h), each a share of the panel's width or height."""
    with Image.open(panel_png) as im:
        w, h = im.size
        x, y, bw, bh = box
        left, top = max(0, round(x * w)), max(0, round(y * h))
        right, bottom = min(w, max(left + 1, round((x + bw) * w))), min(h, max(top + 1, round((y + bh) * h)))
        _save(im.crop((left, top, right, bottom)), dst, long_side)


def item_source(run, file):
    """The picture of a layout item: the file if it is a PNG or JPG, else the PNG beside its SVG, else None."""
    path = Path(run) / file
    if path.suffix.lower() in (".png", ".jpg", ".jpeg"):
        return path if path.is_file() else None
    png = path.with_suffix(".png")
    return png if path.suffix.lower() == ".svg" and png.is_file() else None
