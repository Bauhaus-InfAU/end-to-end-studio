#!/usr/bin/env python3
"""Makes a proposal's pedestrian-level base views, ready for an image model.

    python perspective.py <proposal folder> [--site DIR] [--count N] [--eye-height 1.65] [--hfov 70]
                          [--floor-height M] [--no-terrain] [--options FILE] [--views FILE]

Reads <proposal>/massing/massing.geojson, the project's site folder and, if there,
<proposal>/narrative/narrative.md and drawing-graphics/standard.md. Writes into <proposal>/perspective/.
Needs shapely, pyproj, numpy and requests, and Chrome or Edge for the PNGs. Calls no image model.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

import draw_view
import find_views
import scene as scene_module
import terrain

NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def required_count(scene):
    """How many perspectives the brief asks for, read from its checklist or Markdown."""
    root = scene.proposal.parent.parent
    places = [scene.proposal / "brief-reader" / "checklist.md", *sorted((root / "brief").glob("*.md"))]
    for p in places:
        if p.exists() and not p.name.endswith("summary.md"):
            m = re.search(r"\b(one|two|three|four|five|six|\d)\s+(?:eye-level\s+)?(?:perspectives|spatial representations)", p.read_text(encoding="utf-8", errors="replace"), re.I)
            if m:
                word = m.group(1).lower()
                return NUMBERS.get(word) or int(word), p.name
    return None, None


def number_of_views(scene, given):
    if given:
        return given, "asked for with --count"
    n, source = required_count(scene)
    if n:
        return n, f"the number {source} asks for"
    scene.warn("The brief's number of perspectives wasn't found: two views were made.")
    return 2, "default"


def write_assumptions(scene, path, views, count_source):
    a = scene.assumed
    lines = ["# Assumptions and warnings", ""]
    if scene.is_test:
        lines += ["**TEST OUTPUT: made from a stand-in massing, not a design. Not for the panels.**", ""]
    lines += ["## Data used", *[f"- {u}" for u in scene.used]]
    if scene.absent:
        lines += ["", "## Data not there", *[f"- {u}" for u in scene.absent]]
    lines += ["", "## Assumed numbers",
              f"- Number of views: {len(views)}, {count_source}.",
              f"- Floor height: {scene.floor_height or 'none'} m ({scene.floor_height_source or 'not documented'}).",
              f"- Standing land cover, height in m: {a['tall_cover']}.",
              f"- New trees: {a['tree_height']} m tall, crown radius {a['tree_crown_radius']} m, unless the massing gives a height.",
              f"- Existing street widths by road class: {a['street_width']}; {a['lane_width']} m a lane where lanes are given.",
              f"- Railway strip: {a['rail_width']} m wide.",
              f"- Ground: {'from terrain data' if scene.terrain else 'flat, no terrain data'}.",
              "- A wood's uneven top edge is a drawing convention, not data.",
              "", "## Buildings", *[f"- {k}: {v}" for k, v in scene.building_counts.items()],
              f"- from the massing: {sum(b['group'] != 'context' for b in scene.buildings)}, listed in building_status.csv",
              "", "## Warnings", *[f"- {w}" for w in scene.warnings]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proposal")
    ap.add_argument("--site")
    ap.add_argument("--count", type=int)
    ap.add_argument("--eye-height", type=float, default=1.65)
    ap.add_argument("--hfov", type=float, default=70)
    ap.add_argument("--floor-height", type=float)
    ap.add_argument("--no-terrain", action="store_true")
    ap.add_argument("--options", help="JSON overriding assumed numbers, with an optional 'style'")
    ap.add_argument("--views", help="a views.json from an earlier run, to redraw the same cameras")
    args = ap.parse_args()
    if not 1.6 <= args.eye_height <= 1.7:
        print(f"Note: eye height {args.eye_height} m is outside the pedestrian 1.60 to 1.70 m.")
    options = json.loads(Path(args.options).read_text(encoding="utf-8")) if args.options else {}
    style = options.pop("style", {})
    scene = scene_module.Scene(args.proposal, args.site, options, args.floor_height)
    out = scene.proposal / "perspective"
    out.mkdir(parents=True, exist_ok=True)
    prefix = "TEST_" if scene.is_test else ""
    if args.no_terrain:
        scene.warn("Terrain was switched off: the ground is drawn flat.")
    else:
        found = terrain.find(scene, out) or terrain.fetch(scene, out)
        if found:
            scene.use_terrain(found)
        else:
            scene.warn("No terrain data: the ground is drawn flat.")

    count, count_source = number_of_views(scene, args.count)
    if args.views:
        spec = json.loads(Path(args.views).read_text(encoding="utf-8"))
        picks = [dict(v, heading=v["heading_deg"], hfov=v["hfov_deg"]) for v in spec["views"]]
        for p in picks:
            p["x"], p["y"] = scene.to_local.transform(*p["eye"])
        scored = []
        count_source = f"redrawn from {Path(args.views).name}"
    else:
        picks, scored = find_views.choose(scene, count, args.hfov)
    if not picks:
        (out / "summary.md").write_text(f"{'TEST OUTPUT. ' if scene.is_test else ''}No views made.\n0 views.\n" + "; ".join(scene.warnings) + "\n", encoding="utf-8")
        sys.exit("No viewpoint could be chosen. See perspective/summary.md.")

    views = []
    for i, p in enumerate(picks, 1):
        v = dict(p, name=f"view-{i}", eye_height=args.eye_height, hfov=p.get("hfov", args.hfov))
        stem = f"{prefix}view-{i}"
        made = draw_view.draw_view(scene, v, out, stem, style)
        if not made["png"]:
            scene.warn(f"{stem}_base.png wasn't made: no Chrome or Edge, or it hung. The SVG is there.")
        if made["trees_too_near"]:
            scene.warn(f"{stem}: {made['trees_too_near']} trees under 3 m from the camera were left out of the view.")
        lon, lat = scene.to_lonlat.transform(v["x"], v["y"])
        ground = draw_view.Camera(scene, v).ground
        views.append({"name": v["name"], "stem": stem, "situation": v.get("situation"),
                      "why": v.get("why"), "narrative": v.get("narrative"),
                      "eye": [round(lon, 7), round(lat, 7)], "eye_height_m": args.eye_height, "ground_m": round(ground, 2),
                      "heading_deg": round(v["heading"] % 360, 1), "hfov_deg": v["hfov"], "score": v.get("score"),
                      "metrics": v.get("metrics") or {k: round(v[k], 3) for k in ("new", "presence", "kept_context", "vegetation", "trees", "open", "public", "green", "depth", "blocked", "tree_near") if k in v},
                      "frame_shares": made["frame_shares"],
                      "files": {"base_svg": f"{stem}_base.svg", "base_png": f"{stem}_base.png", "depth_png": f"{stem}_depth.png",
                                "ids_png": f"{stem}_ids.png", "final_png": f"{stem}.png"}, "x": v["x"], "y": v["y"], "heading": v["heading"]})
    draw_view.draw_map(scene, views, out, f"{prefix}views_map")
    for v in views:
        low = [k for k in ("new",) if v["frame_shares"].get(k, 0) < 0.03]
        if low:
            scene.warn(f"{v['stem']}: new buildings fill under 3% of the frame.")
    clean = [{k: x for k, x in v.items() if k not in ("x", "y", "heading")} for v in views]
    (out / "views.json").write_text(json.dumps({
        "test_output": scene.is_test, "site": str(scene.site_dir) if scene.site_dir else None,
        "ground": "terrain" if scene.terrain else "flat", "ids_classes": {k: c * 20 for k, c in draw_view.CLASSES.items()},
        "views": clean}, indent=1), encoding="utf-8")
    with open(out / "building_status.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "id", "status", "reason", "height_m", "height_source", "drawn"])
        w.writerows(scene.status_rows)
    if scored:
        with open(out / "candidates.csv", "w", newline="", encoding="utf-8") as fh:
            keys = ["situation", "score", "heading", "x", "y", "new", "presence", "kept_context", "vegetation", "trees", "open", "public", "green", "depth", "blocked", "tree_near"]
            w = csv.DictWriter(fh, keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(scored)
    write_assumptions(scene, out / "assumptions.md", views, count_source)
    head = "TEST OUTPUT from a stand-in massing, not for the panels. " if scene.is_test else ""
    made = ", ".join(f"{v['stem']} ({v['situation']})" for v in views)
    (out / "summary.md").write_text(
        f"{head}Eye-level base views, no scale, at {args.eye_height} m: {made}.\n"
        f"{len(views)} views {f'from {len(scored)} scored candidates' if scored else 'redrawn from earlier cameras'}; {len(scene.warnings)} warnings.\n"
        f"Unsure: {scene.warnings[0] if scene.warnings else 'nothing flagged'} All assumed numbers are in assumptions.md.\n", encoding="utf-8")
    print(f"{len(views)} views in {out}; {len(scene.warnings)} warnings:")
    for w_ in scene.warnings:
        print(" -", w_)


if __name__ == "__main__":
    main()
