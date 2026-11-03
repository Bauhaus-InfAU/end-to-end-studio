"""inputs_key.py: one fingerprint of a shared input's sources, so the lead remakes it only when they change."""
import subprocess, sys
from conftest import REPO

SCRIPT = REPO / "plugins/studio/skills/competition-proposal/scripts/inputs_key.py"


def key(cwd, *args):
    r = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], cwd=cwd, capture_output=True, text=True, check=True)
    return r.stdout.strip()


def project(tmp_path):
    (tmp_path / "site").mkdir()
    (tmp_path / "site/site.geojson").write_text("{}", encoding="utf-8")
    (tmp_path / "brief").mkdir()
    (tmp_path / "brief/b.md").write_text("brief", encoding="utf-8")
    sk = tmp_path / "plugins/site/skills/climate"
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text("v1", encoding="utf-8")
    return tmp_path


def test_same_sources_same_key(tmp_path):
    p = project(tmp_path)
    assert key(p, "site", "brief", "--skill", "climate") == key(p, "site", "brief", "--skill", "climate")


def test_a_changed_site_file_changes_the_key(tmp_path):
    p = project(tmp_path)
    a = key(p, "site", "brief")
    (p / "site/site.geojson").write_text('{"x": 1}', encoding="utf-8")
    assert key(p, "site", "brief") != a


def test_a_changed_skill_changes_the_key(tmp_path):
    p = project(tmp_path)
    a = key(p, "site", "--skill", "climate")
    (p / "plugins/site/skills/climate/SKILL.md").write_text("v2", encoding="utf-8")
    assert key(p, "site", "--skill", "climate") != a


def test_made_from_and_excluded_files_are_ignored(tmp_path):
    p = project(tmp_path)
    a = key(p, "brief", "--exclude", "checklist.md")
    (p / "brief/made-from.txt").write_text(a, encoding="utf-8")
    (p / "brief/checklist.md").write_text("made from the brief", encoding="utf-8")
    assert key(p, "brief", "--exclude", "checklist.md") == a


def test_unknown_skill_stops(tmp_path):
    p = project(tmp_path)
    r = subprocess.run([sys.executable, str(SCRIPT), "site", "--skill", "nope"], cwd=p, capture_output=True, text=True)
    assert r.returncode != 0 and "nope" in r.stderr
