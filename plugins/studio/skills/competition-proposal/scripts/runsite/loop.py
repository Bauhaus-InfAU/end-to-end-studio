"""The skills' loop graph as it stood at one commit: who reads whom, who runs on which model."""
import re
import subprocess
from pathlib import Path

INPUTS = ["brief", "site"]
LEAD_STEPS = ["side_by_side", "frames", "cost", "redraw"]


def _git(repo, *args):
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


def _items(value):
    """Split a Reads value into (reads, reads_end); `nothing...` means none."""
    if value.strip().lower().startswith("nothing"):
        return [], []
    now, end = [], []
    for part in value.split(","):
        name = part.strip()
        if name.endswith("(end)"):
            name = name[:-5].strip()
            target = end
        else:
            target = now
        if name:
            target.append(name)
    return now, end


def _parse(text):
    reads, reads_end, model = [], [], None
    for line in text.splitlines():
        if m := re.match(r"^Reads \(end\):\s*(.*)", line):
            a, b = _items(m.group(1))
            reads_end += a + b
        elif m := re.match(r"^Reads:\s*(.*)", line):
            a, b = _items(m.group(1))
            reads += a
            reads_end += b
        elif m := re.match(r"^Model:\s*(\w+)", line):
            model = m.group(1)
    return reads, reads_end, model


def read_loop(repo, commit, plugins_rel="plugins"):
    if not commit:
        return None
    listing = _git(repo, "ls-tree", "-r", "--name-only", commit, plugins_rel)
    if listing is None:
        return None
    nodes = [{"id": i, "kind": "input"} for i in INPUTS]
    nodes += [{"id": s, "kind": "lead"} for s in LEAD_STEPS]
    for path in sorted(listing.splitlines()):
        parts = path.split("/")
        if len(parts) < 4 or parts[-3] != "skills" or parts[-1] != "SKILL.md":
            continue
        topic, name = parts[-4], parts[-2]
        if name == "competition-proposal":
            continue
        text = _git(repo, "show", f"{commit}:{path}") or ""
        reads, reads_end, model = _parse(text)
        nodes.append({"id": name, "kind": "skill", "topic": topic,
                      "reads": reads, "reads_end": reads_end, "model": model})
    return {"commit": commit, "nodes": nodes}


def skill_names(loop):
    return {n["id"] for n in loop["nodes"] if n["kind"] == "skill"}
