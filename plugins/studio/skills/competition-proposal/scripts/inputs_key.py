"""A fingerprint of what a shared input is made from, so it is remade only when that changes.

    python inputs_key.py <folder or file> [...] [--skill NAME] [--exclude NAME ...]

Hashes every file under the paths given (by relative path and content) and, with --skill, the
skill's own folder: the project's plugins/*/skills/NAME, else the newest installed copy in
~/.claude/plugins. Files named made-from.txt, and any name given with --exclude, don't count.
Prints a 16-character key. Write it to made-from.txt next to what you made; next time, the same
key means the output is still current.
"""
import argparse, hashlib, os, sys
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".git"}


def find_skill(name):
    here = sorted(Path.cwd().glob(f"plugins/*/skills/{name}"))
    if here:
        return here[0]
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "plugins"
    found = [p for p in base.glob(f"**/skills/{name}") if (p / "SKILL.md").exists()]
    return max(found, key=lambda p: (p / "SKILL.md").stat().st_mtime) if found else None


def files(path, exclude):
    path = Path(path)
    if path.is_file():
        yield path.name, path
        return
    for root, dirs, names in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for n in sorted(names):
            if n not in exclude:
                p = Path(root) / n
                yield p.relative_to(path).as_posix(), p


def key(paths, exclude):
    h = hashlib.sha256()
    for i, path in enumerate(paths):
        h.update(f"#{i}\n".encode())
        for rel, p in files(path, exclude):
            h.update(rel.encode() + b"\0" + hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()[:16]


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("paths", nargs="+")
    a.add_argument("--skill", action="append", default=[])
    a.add_argument("--exclude", action="append", default=[])
    args = a.parse_args()
    paths = list(args.paths)
    for name in args.skill:
        folder = find_skill(name)
        if folder is None:
            sys.exit(f"skill not found: {name}")
        paths.append(folder)
    print(key(paths, {"made-from.txt", *args.exclude}))


if __name__ == "__main__":
    main()
