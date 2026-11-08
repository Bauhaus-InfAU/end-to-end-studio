import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from runsite.loop import read_loop, skill_names

MASSING = "---\nname: massing\n---\nReads: narrative, brief-reader\nModel: opus\nbody\n"
NARRATIVE = "---\nname: narrative\n---\nReads: nothing, only the PDFs\nReads (end): everything\n"
JURY = "---\nname: jury\n---\nReads: brief-reader, panel-layout (end), narrative (end)\n"


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def tmp_repo(tmp_path):
    for rel, text in [("plugins/design/skills/massing", MASSING),
                      ("plugins/concept/skills/narrative", NARRATIVE),
                      ("plugins/studio/skills/competition-proposal", "Reads: massing\n")]:
        d = tmp_path / rel
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(text, encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "x")
    return SimpleNamespace(path=tmp_path, sha=git(tmp_path, "rev-parse", "--short", "HEAD"))


def test_reads_and_end(tmp_repo):
    loop = read_loop(tmp_repo.path, tmp_repo.sha)
    n = {x["id"]: x for x in loop["nodes"]}
    assert n["massing"]["reads"] == ["narrative", "brief-reader"] and n["massing"]["topic"] == "design"
    assert n["narrative"]["reads_end"] == ["everything"] and n["massing"]["model"] == "opus"
    assert n["narrative"]["reads"] == []
    assert "competition-proposal" not in n
    assert {"brief", "site"} <= {x["id"] for x in loop["nodes"] if x["kind"] == "input"}
    assert {"side_by_side", "frames", "cost", "redraw"} <= {x["id"] for x in loop["nodes"] if x["kind"] == "lead"}
    assert skill_names(loop) == {"massing", "narrative"}


def test_end_marker_moves_item_to_reads_end(tmp_path):
    d = tmp_path / "plugins/delivery/skills/jury"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(JURY, encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "x")
    n = {x["id"]: x for x in read_loop(tmp_path, "HEAD")["nodes"]}["jury"]
    assert n["reads"] == ["brief-reader"] and n["reads_end"] == ["panel-layout", "narrative"]


def test_unknown_commit():
    assert read_loop(Path("."), "0000000") is None and read_loop(Path("."), None) is None
