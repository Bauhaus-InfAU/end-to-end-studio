import csv, shutil, subprocess, sys
from pathlib import Path
import pytest
from conftest import REPO

FIX = Path(__file__).parent / "fixtures" / "cost"
SCRIPT = REPO / "plugins/studio/skills/competition-proposal/scripts/cost.py"
TRANSCRIPTS = Path.home() / ".claude/projects/C--Work-GitHub-end-to-end-studio"
RUN3 = REPO / "competition/proposals/2026-11-02_run-3"


def run_cli(args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=True)


def read_csv(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_counts_each_message_id_once():
    import cost
    t = cost.tally(FIX / "dup.jsonl")
    assert t["steps"] == 2 and t["cache_write_5m"] == 3000 and t["input"] == 20 and t["output"] == 10
    assert round(t["usd"], 6) == round((20 * 2 + 3000 * 2.5 + 10 * 10) / 1e6, 6)


def test_writes_cost_csv(tmp_path):
    version = tmp_path / "with space" / "2026-01-01_x"
    version.mkdir(parents=True)
    out = run_cli(["--version", str(version), "--projects", str(FIX / "projects")])
    rows = read_csv(version / "cost.csv")
    assert [r["skill"] for r in rows] == ["massing", "lead", "total"]
    assert rows[0]["model"] == "opus" and rows[0]["run"] == "1"
    assert float(rows[0]["usd"]) == pytest.approx(5.0, abs=0.01)   # 1M 5-minute cache write on Opus
    assert "total $" in out.stdout


def test_rerun_counts_as_a_second_run_and_the_ceiling(tmp_path):
    projects = tmp_path / "projects"
    shutil.copytree(FIX / "projects", projects)
    sub = projects / "s1" / "subagents"
    shutil.copy(sub / "agent-b.jsonl", sub / "agent-d.jsonl")
    (sub / "agent-d.meta.json").write_text('{"description":"plans x rerun"}', encoding="utf-8")
    version = tmp_path / "2026-01-01_x"
    out = run_cli(["--version", str(version), "--projects", str(projects)])
    rows = read_csv(version / "cost.csv")
    assert [(r["skill"], r["run"]) for r in rows[:-2]] == [("massing", "1"), ("plans", "2")]
    assert "under its ceiling of $30.00" in out.stdout    # about $5 against the default
    out = run_cli(["--version", str(version), "--projects", str(projects), "--ceiling", "4"])
    assert "past its ceiling of $4.00" in out.stdout


@pytest.mark.skipif(not (RUN3.exists() and TRANSCRIPTS.exists()), reason="run-3 not on this computer")
def test_run3_baseline(tmp_path):
    version = tmp_path / RUN3.name
    version.mkdir()
    run_cli(["--version", str(version), "--projects", str(TRANSCRIPTS)])
    rows = read_csv(version / "cost.csv")
    helpers = [r for r in rows if r["skill"] not in ("lead", "total")]
    assert len(helpers) == 17
    assert sum(r["run"] == "2" for r in helpers) == 4     # narrative, concept-diagrams, site-section, isometric
    assert 25 <= float(rows[-1]["usd"]) <= 36
