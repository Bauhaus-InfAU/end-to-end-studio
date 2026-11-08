"""Build the runs site: every run folder of a project as one static website.

    python runs_site.py <project inputs folder> [--proposals <folder>] [--out <folder>]
                        [--references <folder>] [--repo <git root>]

Writes <proposals>/site/ (index.html, data/, img/). The site is for the team; publishing it is the user's step.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import preview  # noqa: E402
from runsite import images  # noqa: E402
from runsite.loop import read_loop, skill_names  # noqa: E402
from runsite.run import _scrub_all, card, discover_runs, read_run  # noqa: E402
from runsite.safety import BANNED_PARTS, forbidden_names, is_allowed  # noqa: E402

WEB = HERE / "runsite" / "web"
PANEL_PX, ITEM_PX = 2400, 1600
ITEM_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def _git(repo, *args):
    try:
        done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8")
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def _prepare(out):
    """Empty out, if it is empty or an earlier site of ours; stop for any other folder."""
    if out.exists():
        entries = list(out.iterdir())
        if entries and not (out / "build.json").exists():
            sys.exit("%s is not empty and is not a runs site; choose another --out" % out)
        for e in entries:
            shutil.rmtree(e) if e.is_dir() else e.unlink()
    out.mkdir(parents=True, exist_ok=True)
    _write(out / "build.json", {"built": None, "references": None, "commit": ""})  # marks a half-built site as ours
    for src in WEB.iterdir():
        if src.is_dir():
            shutil.copytree(src, out / src.name)
        else:
            shutil.copy2(src, out / src.name)
    (out / ".nojekyll").write_text("", encoding="utf-8")


def _head_skills(repo):
    listing = _git(repo, "ls-tree", "-r", "--name-only", "HEAD", "plugins") if repo else None
    names = set()
    for line in (listing or "").splitlines():
        parts = line.split("/")
        if len(parts) >= 4 and parts[-3] == "skills" and parts[-1] == "SKILL.md":
            names.add(parts[-2])
    return names


def _is_3d(fc):
    """True for a layer whose coordinates carry a z value (a 3D mesh, not footprints)."""
    def first(c):
        while c and isinstance(c[0], list):
            c = c[0]
        return c
    for f in fc["features"]:
        c = (f.get("geometry") or {}).get("coordinates")
        if c and len(first(c)) >= 3:
            return True
    return False


def _flat(groups):
    out = {}
    for group, layers in groups.items():
        kept = {n: fc for n, fc in layers.items() if not _is_3d(fc)}
        if kept:
            out[group] = kept
    return out


def _run_geo(folder):
    found = {}
    for p in sorted(folder.glob("*/*.geojson")):
        if not is_allowed(p.relative_to(folder)):
            continue
        data = preview.load(p)
        if data and not _is_3d(data):
            found.setdefault(p.parent.name, {})[p.stem] = data
    return found


def _check_layout_paths(folder, run):
    """A layout item that points out of the run or into references stops the build."""
    for panel in run["panels"]:
        for it in panel["items"]:
            if not ITEM_ID.match(it["id"]) or ".." in it["id"]:
                sys.exit("%s: layout item id %r is not a plain name" % (folder.name, it["id"]))
            parts = [p.lower() for p in Path(it["file"]).parts]
            if Path(it["file"]).is_absolute() or ".." in parts or any(p in BANNED_PARTS for p in parts):
                sys.exit("%s: layout item %s points to %s, outside the run; the site never copies it"
                         % (folder.name, it["id"], it["file"]))


def _inside(out, path):
    if not Path(path).resolve().is_relative_to(Path(out).resolve()):
        sys.exit("refusing to write %s outside %s" % (path, out))
    return path


def _images(folder, run, out):
    for panel in run["panels"]:
        png = folder / "panel-layout" / ("panel-%d.png" % panel["n"])
        if not images.to_jpg(png, _inside(out, out / panel["img"]), PANEL_PX):
            print("  warning: %s panel %d can't be read; its item pictures are skipped" % (folder.name, panel["n"]))
            continue
        for it in panel["items"]:
            dst = _inside(out, out / it["img"])
            src = images.item_source(folder, it["file"])
            ok = bool(src) and is_allowed(src.relative_to(folder)) and images.to_jpg(src, dst, ITEM_PX)
            if not ok:
                images.crop(png, (it["x"], it["y"], it["w"], it["h"]), dst, ITEM_PX)


def _order(path):
    m = re.search(r"(\d+)\s*$", path.name)
    return (path.name[:10], int(m.group(1)) if m else 0, path.name)


def build(project, proposals, out, references, repo):
    project, proposals, out = Path(project), Path(proposals), Path(out)
    if references is not None and not Path(references).is_dir():
        sys.exit("--references %s is not a folder" % references)
    _prepare(out)
    overrides = _json(proposals / "runs.json") or {}
    names_file = Path(references) / "names.txt" if references is not None else None
    names = forbidden_names(references, names_file if names_file and names_file.is_file() else None)
    ledger = _scrub_all(_json(proposals / "ledger.json") or [], names)
    head = _head_skills(repo)

    shared = {}
    for name in preview.SHARED:
        if (project / name).is_dir():
            shared.update(preview.layers(project / name, 1))
    _write(out / "data/geo/shared.json", _scrub_all(_flat(shared), names))

    cards, skills_all = [], set()
    for folder in sorted(discover_runs(proposals, overrides), key=_order):
        commit = overrides.get(folder.name, {}).get("commit") or _commit_of(folder)
        loop = read_loop(repo, commit) if repo and commit else None
        run = read_run(folder, (skill_names(loop) if loop else set()) | head, overrides, names)
        _check_layout_paths(folder, run)
        run["loop"] = _scrub_all(loop, names)
        run["has"]["loop"] = loop is not None
        geo = _run_geo(folder)
        run["has"]["geo"] = bool(geo)
        _write(out / "data/geo" / (folder.name + ".json"), _scrub_all(geo, names))
        _images(folder, run, out)
        _write(out / "data/runs" / (folder.name + ".json"), run)
        cards.append(card(run))
        skills_all |= set(run["skills"]) | (skill_names(loop) if loop else set())
        print("%s: %d panels, %d items, %d geo groups" % (
            run["label"], len(run["panels"]), sum(len(p["items"]) for p in run["panels"]), len(geo)))

    _write(out / "data/index.json", {"project": {"name": project.resolve().name}, "runs": cards,
                                      "ledger": ledger, "skills_all": sorted(skills_all)})
    built = {"built": datetime.now().strftime("%Y-%m-%dT%H:%M"), "references": references is not None,
             "commit": (_git(repo, "rev-parse", "--short", "HEAD") if repo else None) or ""}
    _write(out / "build.json", built)
    return built


def _commit_of(folder):
    """The commit a run's version.md names, read before the full run is."""
    try:
        text = (folder / "version.md").read_text(encoding="utf-8", errors="replace")
        text += (folder / "README.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"Skills at commit:\s*`?(\w+)", text) or re.search(r"skills at commit `?(\w+)", text)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path, help="the folder with site/, climate/, proposals/")
    ap.add_argument("--proposals", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--references", type=Path)
    ap.add_argument("--repo", type=Path)
    a = ap.parse_args()
    proposals = a.proposals or a.project / "proposals"
    out = a.out or proposals / "site"
    repo = a.repo or _git(HERE, "rev-parse", "--show-toplevel")
    build(a.project, proposals, out, a.references, Path(repo) if repo else None)
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
