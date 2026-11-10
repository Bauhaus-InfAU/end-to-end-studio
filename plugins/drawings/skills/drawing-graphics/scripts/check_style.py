"""Checks a style.json against the floors of the studio's standard. Exit 1 and one line per problem.

    python check_style.py <style.json>
"""
import json, re, sys

COLOURS = ["paper", "background", "ink", "accent", "new", "public", "shadow", "existing", "context", "building", "street",
           "path", "park", "kept", "lawn", "meadow", "wet-meadow", "grove", "water"]
NUMBERS = ["thin", "mid", "thick", "line", "line_mm", "outline", "text", "title", "body_pt", "heading_pt", "shadow_len"]
MIN_TEXT_MM = 3.17   # 12 px = 9 pt printed


def luminance(hex_):
    rgb = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted([luminance(a), luminance(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def problems(s):
    out = [f"{k}: missing" for k in COLOURS + NUMBERS + ["font", "ramp", "render_style", "storey_labels", "diagram", "marks"] if k not in s]
    for k in COLOURS:
        if k in s and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(s[k])):
            out.append(f"{k}: {s[k]!r} is not a colour as #rrggbb")
    if out:
        return out
    if contrast(s["ink"], s["paper"]) < 7:
        out.append(f"ink: contrast with paper {contrast(s['ink'], s['paper']):.1f}, needs 7")
    if contrast(s["accent"], s["paper"]) < 3:   # not `new`: white buildings read by their outline and shadow
        out.append(f"accent: contrast with paper {contrast(s['accent'], s['paper']):.1f}, needs 3")
    if s["text"] < MIN_TEXT_MM:
        out.append(f"text: {s['text']} mm, needs at least {MIN_TEXT_MM} mm (12 px printed)")
    if s["title"] < s["text"]:
        out.append("title: smaller than text")
    if s["body_pt"] < 9 or s["heading_pt"] < s["body_pt"]:
        out.append("body_pt/heading_pt: body at least 9 pt, heading at least body")
    if not 0.1 <= s["thin"] <= s["mid"] <= s["thick"] <= 1.0:
        out.append("thin, mid, thick: from 0.1 to 1.0 mm, in that order")
    if not (isinstance(s["ramp"], list) and len(s["ramp"]) >= 3):
        out.append("ramp: at least three colours, light to dark")
    if not (isinstance(s["render_style"], str) and s["render_style"].strip()):
        out.append("render_style: a sentence on how the perspectives are rendered")
    if s["marks"] not in ("panel", "drawing"):   # panel: the panel carries caption, north arrow and scale bar once
        out.append(f"marks: {s['marks']!r}, needs panel or drawing")
    if s["storey_labels"] not in ("roman", "arabic"):
        out.append(f"storey_labels: {s['storey_labels']!r}, needs roman or arabic")
    if not isinstance(s["diagram"], dict):
        out.append("diagram: an object, the pictograms' line weights and text sizes in px")
    else:   # px at the pictogram's own size, where text has the 12 px floor
        out += [f"diagram.{k}: {v!r} px, needs at least 12" for k, v in s["diagram"].items()
                if k.endswith("_size") and not (isinstance(v, (int, float)) and v >= 12)]
    out += [f"modes.{m}: {k!r} is not one of the standard's colours" for m, k in (s.get("modes") or {}).items() if k not in COLOURS]
    return out


if __name__ == "__main__":
    found = problems(json.load(open(sys.argv[1], encoding="utf-8")))
    print("\n".join(found) or "ok")
    sys.exit(1 if found else 0)
