import re
from conftest import REPO

OPUS = {"narrative", "structure-plan", "massing", "jury", "panel-layout"}
SKILLS = {p.parent.name: p for p in REPO.glob("plugins/*/skills/*/SKILL.md")}


def line(skill, key):
    m = re.search(rf"^{re.escape(key)}:\s*(.+)$", SKILLS[skill].read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else None


def reads_of(skill):
    v = line(skill, "Reads") or ""
    return [w.strip(" .") for w in v.split(",") if w.strip()]


def test_model_lines():
    for s in SKILLS:
        assert line(s, "Model") == ("opus" if s in OPUS else None), s


def test_massing_reads_narrative():
    assert "narrative" in reads_of("massing")


def test_panels_planned_after_the_structure_plan_and_checked():
    assert "structure-plan" in reads_of("panel-layout")
    lead = (REPO / "plugins/studio/skills/competition-proposal/SKILL.md").read_text(encoding="utf-8")
    assert "frames.py" in lead and "layout-plan.json" in SKILLS["panel-layout"].read_text(encoding="utf-8")


def test_no_cycles():
    graph = {s: [r for r in reads_of(s) if r in SKILLS] for s in SKILLS}
    state = {}

    def visit(s, path):
        if state.get(s) == 1:
            raise AssertionError(" -> ".join(path + [s]))
        if state.get(s) == 2:
            return
        state[s] = 1
        for r in graph[s]:
            visit(r, path + [s])
        state[s] = 2

    for s in graph:
        visit(s, [])


def test_lead_starts_project_inputs_as_helpers():
    lead = (REPO / "plugins/studio/skills/competition-proposal/SKILL.md").read_text(encoding="utf-8")
    assert "each as a `studio:studio-helper` too" in lead


def test_lead_reuses_shared_inputs_by_key():
    lead = (REPO / "plugins/studio/skills/competition-proposal/SKILL.md").read_text(encoding="utf-8")
    assert "inputs_key.py" in lead and "climate" in lead and "made-from.txt" in lead
