"""Publish a built runs site to the gh-pages branch of a git remote.

    python publish_site.py <site folder> --remote <git remote url> [--references <folder>] [--no-references]

Keeps every run the published site has more of than this build (runs are made on different computers),
checks that nothing of the reference entries is in it, shows what will go up, asks, then replaces the
branch with one fresh commit. Nothing is pushed without a yes.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from runsite.safety import BANNED_PARTS, forbidden_names, scrub  # noqa: E402

TEXT = {".json", ".html", ".js", ".css", ".md", ".txt", ".csv"}


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def richness(site: Path, key: str) -> int:
    """How much of a run a site holds: images, + 50 for its geometry, + 10 per drawing on its panels."""
    img = site / "img" / key
    n = sum(1 for p in img.rglob("*") if p.is_file()) if img.is_dir() else 0
    if (site / "data/geo" / f"{key}.json").exists():
        n += 50
    run = _json(site / "data/runs" / f"{key}.json") or {}
    n += 10 * sum(len(p.get("items") or []) for p in run.get("panels") or [] if isinstance(p, dict))
    return n


def merge(local: Path, published: Path | None) -> list[str]:
    """Copy into the local build each published run it lacks or has less of; the keys taken from the published site."""
    if published is None or not (Path(published) / "data/index.json").exists():
        return []
    pub_idx = _json(published / "data/index.json") or {}
    loc_idx = _json(local / "data/index.json") or {"runs": []}
    have = {r["key"]: r for r in loc_idx.get("runs", [])}
    kept = []
    for card in pub_idx.get("runs", []):
        key = card.get("key")
        if not key or (key in have and richness(local, key) >= richness(published, key)):
            continue
        for rel in (f"data/runs/{key}.json", f"data/geo/{key}.json"):
            if (published / rel).exists():
                (local / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(published / rel, local / rel)
        if (local / "img" / key).exists():
            shutil.rmtree(local / "img" / key)
        if (published / "img" / key).is_dir():
            shutil.copytree(published / "img" / key, local / "img" / key)
        have[key] = card
        kept.append(key)
    if kept:
        loc_idx["runs"] = sorted(have.values(), key=lambda r: (str(r.get("date") or ""), _number(r), r["key"]))
        (local / "data/index.json").write_text(json.dumps(loc_idx, separators=(",", ":"), ensure_ascii=False),
                                               encoding="utf-8")
    return kept


def _number(card):
    m = re.search(r"(\d+)$", str(card.get("label") or ""))
    return int(m.group(1)) if m else 0


def check(site: Path, names: list[str], no_references: bool) -> list[str]:
    """Everything that makes this build unsafe to publish; empty when it is safe."""
    problems = []
    built = _json(site / "build.json")
    if not isinstance(built, dict) or not built.get("built"):
        problems.append("build.json is missing or the build did not finish: build the site again")
    elif not built.get("references") and not no_references:
        problems.append("the site was built without --references: build it with the references folder, "
                        "or pass --no-references if the project has none")
    for p in sorted(site.rglob("*")):
        rel = p.relative_to(site)
        parts = [x.lower() for x in rel.parts]
        if any(x in BANNED_PARTS or x.startswith(".env") for x in parts):
            problems.append(f"{rel.as_posix()}: a reference, comparison sheet or key folder")
            continue
        if names and scrub(rel.as_posix(), names) != rel.as_posix():
            problems.append(f"{rel.as_posix()}: its path names a reference entry")
        if p.is_file() and p.suffix.lower() in TEXT and names:
            text = p.read_text(encoding="utf-8", errors="replace")
            if scrub(text, names) != text:
                found = [n for n in names if scrub(text, [n]) != text][:3]
                problems.append(f"{rel.as_posix()}: names a reference entry ({', '.join(found)})")
    return problems


def _run(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def _pages_url(remote):
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote)
    return f"https://{m.group(1).lower()}.github.io/{m.group(2)}/" if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("site", type=Path, help="the built site (runs_site.py's --out)")
    ap.add_argument("--remote", required=True, help="the git remote to publish to, e.g. https://github.com/<owner>/<repo>.git")
    ap.add_argument("--references", type=Path, help="the reference images folder, to check no entry's name is in the site")
    ap.add_argument("--no-references", action="store_true", help="the project has no reference images")
    ap.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)  # for tests only
    a = ap.parse_args()
    if not (a.site / "data/index.json").exists():
        sys.exit(f"{a.site} is not a built runs site")
    if a.references is not None and not a.references.is_dir():
        sys.exit(f"--references {a.references} is not a folder")
    extra = a.references / "names.txt" if a.references and (a.references / "names.txt").exists() else None
    names = forbidden_names(a.references, extra)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        stage = tmp / "site"
        shutil.copytree(a.site, stage)
        pub = tmp / "published"
        got = _run(["git", "clone", "--quiet", "--depth", "1", "--branch", "gh-pages", "--single-branch", a.remote, str(pub)])
        kept = merge(stage, pub if got.returncode == 0 else None)
        problems = check(stage, names, a.no_references)
        if problems:
            print("Not published. Fix these first:")
            for p in problems[:40]:
                print("  - " + p)
            sys.exit(1)
        idx = _json(stage / "data/index.json") or {}
        files = [p for p in stage.rglob("*") if p.is_file()]
        size = sum(p.stat().st_size for p in files) / 1e6
        runs = [r.get("label") or r.get("key") for r in idx.get("runs", [])]
        print(f"Runs: {', '.join(runs)}")
        if kept:
            print(f"Kept from the published site, which has more of them: {', '.join(kept)}")
        question = f"Publish {len(runs)} runs ({len(files)} files, {size:.0f} MB) to gh-pages of {a.remote}? [y/N] "
        if not a.yes and input(question).strip().lower() not in ("y", "yes"):
            print("Not published.")
            return
        steps = [["git", "init", "--quiet"], ["git", "checkout", "--quiet", "-b", "gh-pages"], ["git", "add", "-A"],
                 ["git", "commit", "--quiet", "-m", f"Runs site, {datetime.now():%Y-%m-%d %H:%M}"],
                 ["git", "push", "--force", "--quiet", a.remote, "HEAD:gh-pages"]]
        for s in steps:
            done = _run(s, cwd=stage)
            if done.returncode != 0:
                sys.exit(f"{' '.join(s[:2])} failed: {done.stderr.strip()}")
    url = _pages_url(a.remote)
    print("Published." + (f" The site: {url} (once Pages serves the gh-pages branch)" if url else ""))


if __name__ == "__main__":
    main()
