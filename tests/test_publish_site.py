"""publish_site: merge with what is already published, refuse an unsafe build. Made-up names only."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from publish_site import check, merge

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/studio/skills/competition-proposal/scripts/publish_site.py"


def make_site(root, runs, references=True):
    """A built site with one run per key, `runs[key]` images under img/<key>/."""
    (root / "data/runs").mkdir(parents=True)
    (root / "data/geo").mkdir(parents=True)
    cards = []
    for key, n_img in runs.items():
        (root / "img" / key).mkdir(parents=True)
        for i in range(n_img):
            (root / "img" / key / f"d{i}.jpg").write_bytes(b"x")
        (root / "data/runs" / f"{key}.json").write_text(json.dumps({"key": key, "panels": []}), encoding="utf-8")
        cards.append({"key": key, "date": key, "label": key})
    (root / "data/index.json").write_text(json.dumps({"project": {"name": "p"}, "runs": cards, "ledger": []}),
                                          encoding="utf-8")
    (root / "build.json").write_text(json.dumps({"built": "2026-01-01T00:00", "references": references}),
                                     encoding="utf-8")
    return root


def test_merge_keeps_richer_published_run(tmp_path):
    local, pub = make_site(tmp_path / "l", {"r1": 2}), make_site(tmp_path / "p", {"r1": 9, "r0": 3})
    kept = merge(local, pub)
    assert sorted(kept) == ["r0", "r1"]
    assert len(list((local / "img/r1").iterdir())) == 9
    idx = json.loads((local / "data/index.json").read_text(encoding="utf-8"))
    assert [r["key"] for r in idx["runs"]] == ["r0", "r1"]


def test_merge_replaces_poorer_published_run(tmp_path):
    local, pub = make_site(tmp_path / "l", {"r1": 9}), make_site(tmp_path / "p", {"r1": 2})
    assert merge(local, pub) == []
    assert len(list((local / "img/r1").iterdir())) == 9


def test_merge_keeps_published_run_with_geometry_when_local_has_more_images_but_none(tmp_path):
    local, pub = make_site(tmp_path / "l", {"r1": 9}), make_site(tmp_path / "p", {"r1": 2})
    (pub / "data/geo/r1.json").write_text('{"massing": {}}', encoding="utf-8")
    (local / "data/geo/r1.json").write_text("{}", encoding="utf-8")  # a real build writes {} for a run without geometry
    assert merge(local, pub) == ["r1"]
    assert json.loads((local / "data/geo/r1.json").read_text(encoding="utf-8")) == {"massing": {}}
    assert len(list((local / "img/r1").iterdir())) == 2


def test_merge_keeps_published_run_with_more_items(tmp_path):
    local, pub = make_site(tmp_path / "l", {"r1": 2}), make_site(tmp_path / "p", {"r1": 2})
    (pub / "data/runs/r1.json").write_text(json.dumps({"panels": [{"items": [1, 2]}]}), encoding="utf-8")
    assert merge(local, pub) == ["r1"]


def test_publish_stops_when_references_give_no_names(tmp_path):
    site, remote = make_site(tmp_path / "s", {"r1": 1}), _bare(tmp_path)
    (tmp_path / "refs").mkdir()
    done = subprocess.run([sys.executable, str(SCRIPT), str(site), "--remote", str(remote), "--references",
                           str(tmp_path / "refs"), "--yes"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert done.returncode != 0 and "no reference names" in done.stdout + done.stderr


def test_merge_with_nothing_published(tmp_path):
    local = make_site(tmp_path / "l", {"r1": 1})
    assert merge(local, None) == [] and merge(local, tmp_path / "missing") == []


def test_check_refuses(tmp_path):
    s = make_site(tmp_path / "s", {"r1": 1}, references=False)
    assert check(s, [], False) and not check(s, [], True)
    (s / "data/runs/r1.json").write_text('{"t": "the Northern Lantern plan"}', encoding="utf-8")
    assert any("Northern Lantern" in p for p in check(s, ["Northern Lantern"], True))
    (s / ".compare").mkdir()
    (s / ".compare/x.jpg").write_bytes(b"x")
    assert any(".compare" in p for p in check(s, [], True))


def test_check_finds_names_in_keys_and_paths(tmp_path):
    s = make_site(tmp_path / "s", {"r1": 1})
    (s / "data/geo/r1.json").write_text('{"northern-lantern": {"x": {}}}', encoding="utf-8")
    (s / "img/r1/lantern-plan.jpg").write_bytes(b"x")
    problems = check(s, ["Northern Lantern", "Lantern"], False)
    assert any("r1.json" in p for p in problems) and any("lantern-plan.jpg" in p for p in problems)


def test_check_needs_build_json(tmp_path):
    s = make_site(tmp_path / "s", {"r1": 1})
    (s / "build.json").unlink()
    assert check(s, [], True)


def test_merge_skips_keys_that_are_not_run_names(tmp_path):
    local, pub = make_site(tmp_path / "l", {"r1": 1}), make_site(tmp_path / "p", {"r1": 1})
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("x", encoding="utf-8")
    idx = json.loads((pub / "data/index.json").read_text(encoding="utf-8"))
    idx["runs"].append({"key": "../../victim", "date": "z"})
    (pub / "data/index.json").write_text(json.dumps(idx), encoding="utf-8")
    assert merge(local, pub) == []
    assert (victim / "keep.txt").exists()


def test_merge_skips_cards_without_a_run_file_and_dropped_runs(tmp_path):
    local, pub = make_site(tmp_path / "l", {"r1": 1}), make_site(tmp_path / "p", {"r0": 3, "r2": 3})
    (pub / "data/runs/r2.json").unlink()
    assert merge(local, pub) == ["r0"]
    local2 = make_site(tmp_path / "l2", {"r1": 1})
    assert merge(local2, pub, ("r0",)) == []


def test_merge_skips_runs_with_links(tmp_path):
    local, pub = make_site(tmp_path / "l", {"r1": 1}), make_site(tmp_path / "p", {"r0": 1})
    outside = tmp_path / "secret.txt"
    outside.write_text("x", encoding="utf-8")
    try:
        (pub / "img/r0/link.jpg").symlink_to(outside)
    except OSError:
        pytest.skip("this computer can't make symbolic links")
    assert merge(local, pub) == []


def _bare(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    return remote


def _publish(site, remote, *extra, answer=None):
    return subprocess.run([sys.executable, str(SCRIPT), str(site), "--remote", str(remote), "--no-references", *extra],
                          input=answer, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _branch_files(remote):
    got = subprocess.run(["git", "-C", str(remote), "ls-tree", "-r", "--name-only", "gh-pages"],
                         capture_output=True, text=True)
    return got.stdout.split() if got.returncode == 0 else None


def test_publish_needs_a_yes(tmp_path):
    site, remote = make_site(tmp_path / "s", {"r1": 1}, references=False), _bare(tmp_path)
    done = _publish(site, remote, answer="n\n")
    assert "Not published" in done.stdout and _branch_files(remote) is None
    done = _publish(site, remote, answer="")          # no terminal: input() ends
    assert "Not published" in done.stdout + done.stderr and _branch_files(remote) is None


def test_publish_then_republish_keeps_other_runs(tmp_path):
    remote = _bare(tmp_path)
    first = make_site(tmp_path / "a", {"r0": 2}, references=False)
    assert _publish(first, remote, "--yes").returncode == 0
    second = make_site(tmp_path / "b", {"r1": 1}, references=False)
    done = _publish(second, remote, "--yes")
    assert done.returncode == 0, done.stderr
    files = _branch_files(remote)
    assert "img/r0/d0.jpg" in files and "img/r1/d0.jpg" in files


def test_publish_stops_when_the_remote_cannot_be_read(tmp_path):
    site = make_site(tmp_path / "s", {"r1": 1}, references=False)
    done = _publish(site, tmp_path / "no-such-remote.git", "--yes")
    assert done.returncode != 0 and "Nothing was changed" in done.stdout + done.stderr


def test_publish_needs_references_or_no_references(tmp_path):
    site, remote = make_site(tmp_path / "s", {"r1": 1}), _bare(tmp_path)
    done = subprocess.run([sys.executable, str(SCRIPT), str(site), "--remote", str(remote), "--yes"],
                          capture_output=True, text=True)
    assert done.returncode != 0 and "--no-references" in done.stdout + done.stderr


def test_a_run_key_with_a_space_survives_another_publish(tmp_path):
    remote = _bare(tmp_path)
    assert _publish(make_site(tmp_path / "a", {"2026-11-08_run 12": 1}, references=False), remote, "--yes").returncode == 0
    done = _publish(make_site(tmp_path / "b", {"2026-11-09_run-13": 1}, references=False), remote, "--yes")
    assert done.returncode == 0, done.stdout + done.stderr
    files = _branch_files(remote)
    assert "img/2026-11-08_run 12/d0.jpg" in " ".join(files)


def test_a_published_run_that_cannot_be_kept_stops_the_publish(tmp_path):
    remote = _bare(tmp_path)
    assert _publish(make_site(tmp_path / "a", {"r0": 1}, references=False), remote, "--yes").returncode == 0
    clone = tmp_path / "c"
    subprocess.run(["git", "clone", "-q", "--branch", "gh-pages", str(remote), str(clone)], check=True)
    (clone / "data/runs/r0.json").unlink()
    for cmd in (["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "break"], ["push", "-q"]):
        subprocess.run(["git", "-C", str(clone), *cmd], check=True)
    site = make_site(tmp_path / "b", {"r1": 1}, references=False)
    done = _publish(site, remote, "--yes")
    assert done.returncode != 0 and "r0" in done.stdout + done.stderr
    assert _publish(site, remote, "--yes", "--drop", "r0").returncode == 0
    assert not any(f.startswith("img/r0/") for f in _branch_files(remote))


def test_drop_takes_a_run_off_even_when_the_build_has_it(tmp_path):
    remote = _bare(tmp_path)
    site = make_site(tmp_path / "a", {"r0": 1, "bad": 1}, references=False)
    assert _publish(site, remote, "--yes", "--drop", "bad").returncode == 0
    files = _branch_files(remote)
    assert not any("bad" in f for f in files) and "img/r0/d0.jpg" in files
