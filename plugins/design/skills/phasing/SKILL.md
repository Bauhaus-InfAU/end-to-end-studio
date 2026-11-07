---
name: phasing
description: Splits an urban design into construction phases and says what comes first in each, with the homes and residents per phase, reconciled between the structure plan and the massing; checks that each finished phase works on its own and meets the brief while the next is built, and draws the phasing plan with a table for the panels. Use when asked for the phases, the construction sections, the step-by-step development, the homes or residents per phase, what is built first, or a phasing plan.
---
# Phasing

Reads: brief-reader, programme, structure-plan, massing
Reads (end): streets, mobility, open-space, drawing-graphics

Every new building gets one phase, each phase counts the homes it really holds, and those are the homes and residents per phase that panels and texts show. The second run checks that this works while it is being built. Asked once with everything there, do both runs.

Every number comes from the brief, its checklist or another skill's file, with its source next to it; never write a place or a number of this project into the skill or its scripts. Work in the proposal folder you are told, else the newest in the project's `proposals/`, and write only into `phasing/`; if the design should change, say what in `summary.md`. Needs `pip install shapely pyproj networkx`, and Chrome or Edge for the PNGs.

**First run: the phases.** Read `brief-reader/checklist.md`, and the brief's Markdown only at the pages it names for phases. Write `phasing/requirements.md`, one line per item with its page: the number of phases, what the first phase must hold and where, what must come early, any timing, what the panels must show about phases, the emergency-access rules. Write "not stated" for what the brief leaves out, and mark any decision of yours, with its reason. Copy `${CLAUDE_SKILL_DIR}/scripts/config.example.json` to `phasing/config.json` and fill every value as its `source` says. Where neither the structure plan nor the massing phases a new neighbourhood, decide it in `phase_of` from the brief's order, with the reason. Run `python "${CLAUDE_SKILL_DIR}/scripts/phases.py" --proposal <proposal folder> --config <proposal>/phasing/config.json`; the `flags` in `phasing/stats.json` name every mismatch. Write `summary.md` in three lines: the phases and what comes first in each; the homes and residents per phase against the brief's; every flag and what you're unsure of.

**Second run: does each phase work.** Run `python "${CLAUDE_SKILL_DIR}/scripts/phasing.py" --proposal <proposal folder> --site <site folder> --config <proposal>/phasing/config.json`. It never takes the nearest phase: a building without one is flagged, with its evidence in `evidence.csv`. Weigh that evidence, then write `phasing/decisions.json` after `${CLAUDE_SKILL_DIR}/scripts/decisions.example.json`:
- a building's phase with `basis: proposed` only where the evidence points one way, with the reason, else `basis: review` with what is missing or in conflict;
- the phase of each stop (0 for one that exists today) and of each new open space with no phase;
- services outside the site or temporary ones, each with its source;
- any closure of an existing street during building.

Run it again. Stage j is the time phase j is built: only what exists and phases 1 to j−1 work then. If a building is cut off though a street runs past it, try a larger `snap_m`, about a street's width, before asking for a change to the design: a gap in the drawing isn't a missing street. Do what each warning in `stage-stats.json` asks and name the others in `summary.md`; if a phase counts other homes than `phases.csv`, which the panels show, name the difference there too.

Run `python "${CLAUDE_SKILL_DIR}/scripts/draw.py" --proposal <proposal folder> --site <site folder> --style <proposal>/drawing-graphics/style.json --size large`, and `--size small` if the panels need it. A frame in the panels' plan sets the plan's size and, if named, its scale. Without the drawing standard it draws nothing; say so in `summary.md`. Look at each PNG once.

Write `phasing.md`: the sequence, phase by phase, what each brings and why it comes then, with sources; the count of buildings by basis, adding up to every building in the massing; each proposed or flagged building with its reason; your judgment of each `checks.csv` row marked "for Claude to judge".

Replace `summary.md`, in three lines: the phases and what comes first in each, with the plan's file and scale; the homes and residents per phase against the brief's; every flag in `stats.json`, the buildings flagged for review, the neighbourhood furthest from its planned homes (first in its `neighbourhoods`), the requirement least met and what you're unsure of.
