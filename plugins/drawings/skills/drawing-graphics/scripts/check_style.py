"""Checks a style.json against the floors of the studio's standard. Exit 1 and one line per problem.

    python check_style.py <style.json>
"""
import json, re, sys

COLOURS = ["paper", "background", "ink", "accent", "new", "existing", "context", "building", "street", "path",
           "park", "kept", "lawn", "meadow", "wet-meadow", "grove", "water"]
NUMBERS = ["thin", "mid", "thick", "line", "line_mm", "outline", "text", "title", "body_pt", "heading_pt"]
MIN_TEXT_MM = 3.17   # 12 px = 9 pt printed


def luminance(hex_):
    rgb = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted([luminance(a), luminance(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def problems(s):
    out = [f"{k}: missing" for k in COLOURS + NUMBERS + ["font", "ramp"] if k not in s]
    for k in COLOURS:
        if k in s and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(s[k])):
            out.append(f"{k}: {s[k]!r} is not a colour as #rrggbb")
    if out:
        return out
    if contrast(s["ink"], s["paper"]) < 7:
        out.append(f"ink: contrast with paper {contrast(s['ink'], s['paper']):.1f}, needs 7")
    for k in ("accent", "new"):
        if contrast(s[k], s["paper"]) < 3:
            out.append(f"{k}: contrast with paper {contrast(s[k], s['paper']):.1f}, needs 3")
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
    return out


if __name__ == "__main__":
    found = problems(json.load(open(sys.argv[1], encoding="utf-8")))
    print("\n".join(found) or "ok")
    sys.exit(1 if found else 0)
