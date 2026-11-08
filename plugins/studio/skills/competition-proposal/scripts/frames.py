"""Do the drawings fit the frames the panels' first plan gave them?

    python frames.py <version> [--plan <layout json>]

Reads the plan of the panels, <version>/panel-layout/layout-plan.json, else layout.json (still the plan until
panel-layout's second run). For every drawing in it with a frame it finds what the drawing's skill wrote (the
planned file, else one in the same folder whose name differs only in its scale, such as _1-10000 for _1-5000),
the scale it is drawn at (its file name, else the plan's `drawn_at`, else its skill's summary.md) and its print
size in mm, and compares them with the frame at the frame's scale. A drawing without a scale, or at "auto", is
fitted to its frame, so only its proportions count. Prints one line per drawing that misses its frame, then the
ones that fit. Writes nothing; needs only Python.
"""
import argparse
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

EXT = (".svg", ".png", ".jpg", ".jpeg")  # in this order: an SVG is preferred to its PNG preview
MM_PER = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72, "pc": 25.4 / 6}
FILE_SCALE_RE = re.compile(r"(?:^|[_\-.])1[-_](\d{2,6})(?=$|[_\-.])")  # "plan_1-2000"
SCALE_RE = re.compile(r"1\s*:\s*(\d{1,3}(?:[,.  ]\d{3})+(?!\d)|\d+)")  # "1:2,000", "1:500"
TOLERANCE = 0.2  # a frame that hides more than this share of its drawing, or leaves this share of itself empty, is missed


def scale_of(text):
    m = SCALE_RE.search(str(text or ""))
    return int(re.sub(r"\D", "", m.group(1))) if m else None


def unscaled_stem(path):
    p = Path(path)
    return (p.parent / FILE_SCALE_RE.sub("", p.stem)).as_posix()


def print_mm(path):
    """(width, height) in mm: an SVG's size in a physical unit, a PNG's from its resolution; else None."""
    if path.suffix.lower() == ".svg":
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
    data = path.read_bytes()
    i = data.find(b"pHYs")
    if data[:8] == b"\x89PNG\r\n\x1a\n" and i > 0:
        w, h = struct.unpack(">II", data[16:24])
        ppx, ppy, unit = struct.unpack(">IIB", data[i + 4:i + 13])
        if unit == 1 and ppx > 0 and ppy > 0:  # pixels per metre
            return w / ppx * 1000, h / ppy * 1000
    return None


def aspect(path):
    """Height over width of a drawing, from its print size, its viewBox or its pixels; else None."""
    size = print_mm(path)
    if size:
        return size[1] / size[0]
    if path.suffix.lower() == ".svg":
        try:
            vb = [float(v) for v in re.split(r"[\s,]+", (ET.parse(path).getroot().get("viewBox") or "").strip()) if v]
        except (OSError, ET.ParseError, ValueError):
            return None
        return vb[3] / vb[2] if len(vb) == 4 and vb[2] > 0 else None
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return h / w
    i = 2
    while data[:2] == b"\xff\xd8" and i < len(data) - 9:  # a JPEG: its first frame header holds the size
        if data[i] != 0xFF:
            i += 1
            continue
        if data[i + 1] in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return h / w
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def find_drawn(version, planned):
    """The planned file, else a drawing in its folder whose name differs only in its scale."""
    p = version / planned
    if p.is_file():
        return p
    if not p.parent.is_dir():
        return None
    key = unscaled_stem(planned)
    found = [f for f in p.parent.iterdir() if f.suffix.lower() in EXT and unscaled_stem(f.relative_to(version)) == key]
    return min(found, key=lambda f: (EXT.index(f.suffix.lower()), f.name)) if found else None


def summary_scale(version, file):
    """The scale its skill's summary.md gives on the line naming the drawing, else the only one it gives."""
    s = version / Path(file).parts[0] / "summary.md"
    if not s.exists():
        return None
    text = s.read_text(encoding="utf-8", errors="replace")
    key = Path(file).stem.lower().replace("_", "-")
    for line in text.splitlines():
        at = line.lower().replace("_", "-").find(key)
        if at >= 0 and scale_of(line):
            return scale_of(line[at:]) or scale_of(line)
    found = {int(re.sub(r"\D", "", m)) for m in SCALE_RE.findall(text)}
    return found.pop() if len(found) == 1 else None


def asked_frame(drawing):
    """The drawing's own request for a frame, <drawing>.frame.json next to it, else None."""
    try:
        r = json.loads(drawing.with_suffix(".frame.json").read_text(encoding="utf-8"))
        return r if r["needs_mm"]["w"] and r["needs_mm"]["h"] else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def check_item(version, it):
    """What one framed drawing of the plan got: a dict with `problems`, empty when it fits its frame."""
    fw, fh = float(it["frame"]["w"]), float(it["frame"]["h"])
    want = scale_of(it.get("scale"))  # None: "auto" or no scale, the panels size it to the frame
    r = {"id": it.get("id") or it["file"], "skill": Path(it["file"]).parts[0], "planned": it["file"],
         "frame_mm": [round(fw), round(fh)], "scale": want, "problems": []}
    f = find_drawn(version, it["file"])
    if f is None:
        r["problems"].append("not drawn")
        return r
    r["drawn"] = f.relative_to(version).as_posix()
    asks = asked_frame(f)
    if asks and want and scale_of(asks.get("scale")) == want:   # it says what it needs, and panel-layout's second run gives it: no redraw
        r["asks"] = asks["needs_mm"]
        return r
    if not want:
        a = aspect(f)
        if a:  # fitted to the frame at whatever scale: the share of the frame it fills
            k = min(fw, fh / a)
            r["fills"] = k * k * a / (fw * fh)
        else:
            r["problems"].append("its proportions can't be read")
    else:
        in_name = FILE_SCALE_RE.findall(f.stem)
        own = int(in_name[-1]) if in_name else scale_of(it.get("drawn_at")) or summary_scale(version, r["drawn"])
        size = print_mm(f)
        r["drawn_at"], r["size_mm"] = own, [round(v) for v in size] if size else None
        if not own or not size:
            r["problems"].append("no " + ("scale in its file name or summary" if not own else "print size in mm")
                                 + f", so 1:{want:,} can't be checked")
            return r
        if own != want:
            r["problems"].append("not at its frame's scale")
        w, h = size[0] * own / want, size[1] * own / want  # as the panels print it, at the frame's scale
        shown = min(w, fw) * min(h, fh)
        r["at_frame_scale_mm"], r["hidden"], r["fills"] = [round(w), round(h)], 1 - shown / (w * h), shown / (fw * fh)
        if r["hidden"] > TOLERANCE:
            r["problems"].append((f"at 1:{want:,} it is {w:.0f} x {h:.0f} mm: " if own != want else "")
                                 + f"the frame hides {100 * r['hidden']:.0f} % of it")
    if r.get("fills", 1) < 1 - TOLERANCE:
        r["problems"].append(f"it fills {100 * r['fills']:.0f} % of its frame")
    return r


def check(version, plan=None):
    """Every framed drawing of the plan, checked. Returns (plan path, [result of check_item, ...])."""
    version = Path(version).resolve()
    if plan is None:
        plan = next((p for p in (version / "panel-layout" / n for n in ("layout-plan.json", "layout.json")) if p.exists()), None)
    if plan is None:
        return None, []
    L = json.loads(Path(plan).read_text(encoding="utf-8"))
    items = [it for p in L.get("panels", []) for it in p.get("items", [])
             if it.get("type") == "drawing" and it.get("file") and (it.get("frame") or {}).get("w") and it["frame"].get("h")]
    return Path(plan), [check_item(version, it) for it in items]


def line(r):
    planned = r["planned"] + (f" at 1:{r['scale']:,} in" if r["scale"] else ", fitted to") + f" {r['frame_mm'][0]} x {r['frame_mm'][1]} mm"
    drawn = (f"; drawn {r['drawn']}" + (f" at 1:{r['drawn_at']:,}" if r.get("drawn_at") else "")
             + (f", {r['size_mm'][0]} x {r['size_mm'][1]} mm" if r.get("size_mm") else "")) if r.get("drawn") else ""
    return f"- `{r['id']}` ({r['skill']}): planned {planned}{drawn}: " + "; ".join(r["problems"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version")
    ap.add_argument("--plan", help="the plan to check against (default: panel-layout/layout-plan.json, else layout.json)")
    a = ap.parse_args()
    plan, results = check(a.version, a.plan)
    if plan is None:
        print("No plan of the panels (panel-layout/layout-plan.json or layout.json): nothing to check.")
        return
    missed = [r for r in results if r["problems"]]
    print(f"Frames of {plan.parent.name}/{plan.name}: {len(missed)} of {len(results)} drawings miss their frame "
          f"(more than {100 * TOLERANCE:.0f} % hidden or empty, or another scale).")
    for r in missed:
        print(line(r))
    for r in results:
        if r.get("asks"):
            print(f"Asks for its frame, so panel-layout's second run gives it, no rerun: `{r['id']}` ({r['skill']}), "
                  f"{r['asks']['w']} x {r['asks']['h']} mm at 1:{r['scale']:,}, planned {r['frame_mm'][0]} x {r['frame_mm'][1]} mm.")
    fit = [r["id"] for r in results if not r["problems"] and not r.get("asks")]
    print("Fit their frames: " + (", ".join(f"`{i}`" for i in fit) or "none") + ".")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
