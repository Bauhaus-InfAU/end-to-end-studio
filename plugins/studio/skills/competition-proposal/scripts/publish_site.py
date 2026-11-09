"""Publish a built runs site to the gh-pages branch of a git remote.

    python publish_site.py <site folder> --remote <git remote url> (--references <folder> | --no-references)
                           [--drop <run key> ...]

Keeps every run the published site has more of than this build (runs are made on different computers),
checks that nothing of the reference entries is in it, shows what will go up, asks, then replaces the
branch with one fresh commit. Nothing is pushed without a yes, and nothing is pushed if the published
site could not be read or changed in the meantime. Run it in your own terminal: it asks a question.
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

def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _key_ok(key) -> bool:
    """A run key is one folder name: any characters a run folder can have, but no path in it."""
    return (isinstance(key, str) and key.strip() == key and bool(key) and not key.startswith(".")
            and ".." not in key and not any(c in key for c in "/\\:\0"))


def _inside(base: Path, path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(base.resolve())
    except OSError:
        return False


def _has_link(path: Path) -> bool:
    """True if the path or anything under it is a symbolic link."""
    if path.is_symlink():
        return True
    return path.is_dir() and any(p.is_symlink() for p in path.rglob("*"))


def _parts(site: Path, key: str) -> tuple[bool, int, int]:
    """What a site holds of a run: has geometry, panel items, images."""
    img = site / "img" / key
    n_img = sum(1 for p in img.rglob("*") if p.is_file()) if img.is_dir() else 0
    run = _json(site / "data/runs" / f"{key}.json") or {}
    items = sum(len(p.get("items") or []) for p in run.get("panels") or [] if isinstance(p, dict))
    return bool(_json(site / "data/geo" / f"{key}.json")), items, n_img  # a run without geometry has an empty {} file


def local_has_enough(local: Path, published: Path, key: str) -> bool:
    """The local run replaces the published one only if it lacks nothing: geometry where the site has it, and no fewer items or images."""
    lg, li, ln = _parts(local, key)
    pg, pi, pn = _parts(published, key)
    return (lg or not pg) and li >= pi and ln >= pn


def _sources(published: Path, key: str) -> list[Path]:
    return [published / "data/runs" / f"{key}.json", published / "data/geo" / f"{key}.json", published / "img" / key]


def unkeepable(published: Path | None, drop: tuple = ()) -> list[str]:
    """Published runs that merge can't safely carry over and nobody asked to drop: publishing would lose them."""
    if published is None:
        return []
    out = []
    for card in (_json(published / "data/index.json") or {}).get("runs", []):
        key = card.get("key") if isinstance(card, dict) else card
        if key in drop:
            continue
        if (not _key_ok(key) or not (published / "data/runs" / f"{key}.json").is_file()
                or any(_has_link(s) for s in _sources(published, key) if s.exists() or s.is_symlink())
                or not all(_inside(published, s) for s in _sources(published, key))):
            out.append(str(key))
    return out


def drop_runs(site: Path, drop: tuple) -> None:
    """Take runs off a built site: their card, run file, geometry and images."""
    idx = _json(site / "data/index.json") or {"runs": []}
    idx["runs"] = [r for r in idx.get("runs", []) if not (isinstance(r, dict) and r.get("key") in drop)]
    (site / "data/index.json").write_text(json.dumps(idx, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    for key in drop:
        if not _key_ok(key):
            continue
        for p in (site / "data/runs" / f"{key}.json", site / "data/geo" / f"{key}.json"):
            if p.exists() and _inside(site, p):
                p.unlink()
        if (site / "img" / key).is_dir() and _inside(site, site / "img" / key):
            shutil.rmtree(site / "img" / key)


def merge(local: Path, published: Path | None, drop: tuple = ()) -> list[str]:
    """Copy into the local build each published run it lacks or has less of; the keys taken from the published site.

    A published run named in `drop` is left out. Keys that aren't plain run names, cards without a run
    file and runs holding symbolic links are skipped.
    """
    if published is None or not (Path(published) / "data/index.json").exists():
        return []
    pub_idx = _json(published / "data/index.json") or {}
    loc_idx = _json(local / "data/index.json") or {"runs": []}
    have = {r["key"]: r for r in loc_idx.get("runs", []) if isinstance(r, dict) and r.get("key")}
    kept = []
    for card in pub_idx.get("runs", []):
        key = card.get("key") if isinstance(card, dict) else None
        if not _key_ok(key) or key in drop or not (published / "data/runs" / f"{key}.json").is_file():
            continue
        if key in have and local_has_enough(local, published, key):
            continue
        sources = _sources(published, key)
        if any(_has_link(s) for s in sources if s.exists() or s.is_symlink()):
            continue
        if not all(_inside(published, s) for s in sources) or not _inside(local, local / "img" / key):
            continue
        for rel in (f"data/runs/{key}.json", f"data/geo/{key}.json"):
            if (local / rel).exists():
                (local / rel).unlink()
            if (published / rel).is_file():
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


def _is_text(p: Path) -> bool:
    try:
        with p.open("rb") as f:
            return b"\0" not in f.read(8192)
    except OSError:
        return False


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
        if p.is_symlink():
            problems.append(f"{rel.as_posix()}: a link to somewhere else")
            continue
        if any(x in BANNED_PARTS or x.startswith(".env") for x in parts):
            problems.append(f"{rel.as_posix()}: a reference, comparison sheet or key folder")
            continue
        if names and scrub(rel.as_posix(), names) != rel.as_posix():
            problems.append(f"{rel.as_posix()}: its path names a reference entry")
        if p.is_file() and names and _is_text(p):
            text = p.read_text(encoding="utf-8", errors="replace")
            if scrub(text, names) != text:
                found = [n for n in names if scrub(text, [n]) != text][:3]
                problems.append(f"{rel.as_posix()}: names a reference entry ({', '.join(found)})")
    return problems


def _run(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _shown(remote: str) -> str:
    """The remote without any user or token in it, for printing."""
    return re.sub(r"//[^/@]+@", "//", remote)


def _pages_url(remote):
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote)
    return f"https://{m.group(1).lower()}.github.io/{m.group(2)}/" if m else None


def _published_head(remote):
    """(ok, sha): the gh-pages commit on the remote, None if it has no such branch; ok False if it can't be read."""
    got = _run(["git", "ls-remote", "--heads", remote, "gh-pages"])
    if got.returncode != 0:
        return False, None
    line = got.stdout.strip().split("\n")[0]
    return True, (line.split()[0] if line else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("site", type=Path, help="the built site (runs_site.py's --out)")
    ap.add_argument("--remote", required=True, help="the git remote, e.g. https://github.com/<owner>/<repo>.git")
    ap.add_argument("--references", type=Path, help="the reference images folder, to check no entry's name is in the site")
    ap.add_argument("--no-references", action="store_true", help="the project has no reference images")
    ap.add_argument("--drop", nargs="*", default=[], help="run keys to take off the published site")
    ap.add_argument("--yes", action="store_true", help="don't ask: the user has already said yes")
    a = ap.parse_args()
    if not (a.site / "data/index.json").exists():
        sys.exit(f"{a.site} is not a built runs site")
    if a.references is None and not a.no_references:
        sys.exit("Say where the reference images are (--references <folder>), or --no-references if there are none")
    if a.references is not None and not a.references.is_dir():
        sys.exit(f"--references {a.references} is not a folder")
    extra = a.references / "names.txt" if a.references and (a.references / "names.txt").exists() else None
    names = forbidden_names(a.references, extra)
    if a.references is not None:
        if not names:
            sys.exit(f"--references {a.references} gives no reference names: point it at the folder of the reference entries")
        print(f"Checking for {len(names)} reference names.")

    ok, head = _published_head(a.remote)
    if not ok:
        sys.exit(f"Not published: can't read {_shown(a.remote)} (network or sign-in?). Nothing was changed.")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        stage = tmp / "site"
        shutil.copytree(a.site, stage, symlinks=True)
        pub = None
        if head:
            pub = tmp / "published"
            got = _run(["git", "clone", "--quiet", "--depth", "1", "--branch", "gh-pages", "--single-branch",
                        a.remote, str(pub)])
            if got.returncode != 0:
                sys.exit("Not published: the published site exists but couldn't be downloaded, so its runs "
                         "would be lost. Nothing was changed.")
        pub_idx = _json(pub / "data/index.json") if pub else {}
        if not isinstance(pub_idx, dict):
            sys.exit("Not published: the published site's data/index.json can't be read, so its runs would be "
                     "lost. Nothing was changed.")
        published_runs = len(pub_idx.get("runs", []))
        lost = unkeepable(pub, tuple(a.drop))
        if lost:
            sys.exit("Not published: these published runs can't be carried over safely and would be lost: "
                     f"{', '.join(lost)}. Publish with --drop {' '.join(lost)} to take them off. Nothing was changed.")
        drop_runs(stage, tuple(a.drop))
        kept = merge(stage, pub, tuple(a.drop))
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
        print(f"The published site has {published_runs} runs now; after this it has {len(runs)}: {', '.join(runs)}")
        if kept:
            print(f"Taken from the published site (this build has less of them, or none): {', '.join(kept)}")
        if a.drop:
            print(f"Left out: {', '.join(a.drop)}")
        question = f"Publish {len(runs)} runs ({len(files)} files, {size:.1f} MB) to gh-pages of {_shown(a.remote)}? [y/N] "
        if not a.yes:
            try:
                answer = input(question)
            except EOFError:
                sys.exit("Not published: run this in your own terminal and answer y.")
            if answer.strip().lower() not in ("y", "yes"):
                print("Not published.")
                return
        steps0 = _run(["git", "init", "--quiet"], cwd=stage)
        if steps0.returncode != 0:
            sys.exit(f"Not published: git init failed.\n{steps0.stderr.strip()}")
        known = all(_run(["git", "config", k], cwd=stage).stdout.strip() for k in ("user.name", "user.email"))
        who = [] if known else ["-c", "user.name=runs site", "-c", "user.email=runs-site@localhost"]
        lease = f"--force-with-lease=refs/heads/gh-pages:{head or ''}"
        steps = [["git", "checkout", "--quiet", "-b", "gh-pages"], ["git", "add", "-A"],
                 ["git", *who, "commit", "--quiet", "-m", f"Runs site, {datetime.now():%Y-%m-%d %H:%M}"],
                 ["git", "push", "--quiet", lease, a.remote, "HEAD:gh-pages"]]
        for s in steps:
            done = _run(s, cwd=stage)
            if done.returncode != 0:
                stale = s[1] == "push" and re.search(r"stale info|fetch first|rejected", done.stderr)
                hint = " Someone published in the meantime: run this again." if stale else ""
                sys.exit(f"Not published: {' '.join(x for x in s[:2] if not x.startswith('-c'))} failed.{hint}\n"
                         f"{_shown(done.stderr.strip())}")
    url = _pages_url(a.remote)
    print("Published." + (f" The site: {url} (once Pages serves the gh-pages branch)" if url else ""))


if __name__ == "__main__":
    main()
