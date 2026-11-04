"""A local map preview of a project's geometry: the shared inputs (site, climate, analysis) and each run's results.

    python preview.py <project inputs folder> [--proposals <folder>] [--open]

Writes <proposals>/preview/index.html and one data file per source next to it. Open index.html in a browser.
"""
import argparse
import json
import re
import sys
import webbrowser
from pathlib import Path

SHARED = ["site", "climate", "analysis"]  # project folders every run shares, in this order
RUN = re.compile(r"^\d{4}-\d{2}-\d{2}_.+")


def rounded(x):
    """Coordinates to 6 decimals (about 10 cm), so the data files stay small."""
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, list):
        return [rounded(v) for v in x]
    return x


def load(path):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"  skipped {path}: {e}", file=sys.stderr)
        return None
    feats = d.get("features") if d.get("type") == "FeatureCollection" else [d] if d.get("type") == "Feature" else None
    if not feats:
        return None
    for f in feats:
        if f.get("geometry"):
            f["geometry"]["coordinates"] = rounded(f["geometry"].get("coordinates"))
    return {"type": "FeatureCollection", "features": feats}


def layers(folder, depth):
    """Every GeoJSON in a folder (depth 1) or in its skill folders (depth 2), as {group: {name: data}}."""
    out = {}
    files = sorted(folder.glob("*.geojson")) if depth == 1 else sorted(folder.glob("*/*.geojson"))
    for p in files:
        data = load(p)
        if data:
            group = folder.name if depth == 1 else p.parent.name
            out.setdefault(group, {})[p.stem] = data
    return out


def title(run):
    readme = run / "README.md"
    if readme.exists():
        first = readme.read_text(encoding="utf-8").splitlines()[:1]
        if first and first[0].startswith("#"):
            return first[0].lstrip("# ").strip()
    return run.name


def write(out, key, payload):
    js = "PREVIEW.add(" + json.dumps(key) + "," + json.dumps(payload, separators=(",", ":")) + ");\n"
    (out / "data" / f"{key}.js").write_text(js, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path, help="the folder with site/, climate/, proposals/")
    ap.add_argument("--proposals", type=Path)
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    proposals = a.proposals or a.project / "proposals"
    out = proposals / "preview"
    (out / "data").mkdir(parents=True, exist_ok=True)

    shared = {}
    for name in SHARED:
        if (a.project / name).is_dir():
            shared.update(layers(a.project / name, 1))
    write(out, "shared", shared)

    runs = []
    for run in sorted((p for p in proposals.iterdir() if p.is_dir() and RUN.match(p.name)), reverse=True):
        found = layers(run, 2)
        if not found:
            continue
        write(out, run.name, found)
        panels = sorted(run.glob("panel-layout/panel-*.pdf"))
        runs.append({"key": run.name, "title": title(run),
                     "panels": [Path("..", run.name, p.relative_to(run)).as_posix() for p in panels],
                     "sheets": [Path("..", run.name, p.relative_to(run)).as_posix() for p in sorted(run.glob(".compare/*.jpg"))]})
        print(f"  {run.name}: {sum(len(v) for v in found.values())} layers")

    html = (Path(__file__).with_name("preview.html")).read_text(encoding="utf-8")
    (out / "index.html").write_text(html.replace("/*RUNS*/[]", json.dumps(runs)), encoding="utf-8")
    print(f"wrote {out / 'index.html'}: {len(shared)} shared groups, {len(runs)} runs")
    if a.open:
        webbrowser.open((out / "index.html").resolve().as_uri())


if __name__ == "__main__":
    main()
