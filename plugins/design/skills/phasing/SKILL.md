---
name: phasing
description: Splits an urban design into construction phases and says what comes first in each, with the homes and residents per phase, reconciled between the structure plan and the massing; checks that each finished phase works on its own and meets the brief while the next is built, and draws the phasing plan with a table for the panels. Use when asked for the phases, the construction sections, the step-by-step development, the homes or residents per phase, what is built first, or a phasing plan.
---
# Phasing

Reads: brief-reader, programme, structure-plan, massing, streets, mobility, open-space, drawing-graphics

The structure plan gives its neighbourhoods and centres a phase and the homes it plans; the massing builds them, and its buildings may carry a phase of their own. This skill makes them one answer: every new building gets one phase, each phase counts the homes it really holds, and its numbers are the homes and residents per phase that panels and texts show. Then it checks that the answer works while it is being built.

Never invent data, and never write a place or a number of this project into the skill or its scripts: every number comes from the brief, its checklist or the other skills' files, with its source next to it. Work in the proposal folder you are told, else the newest in the project's `proposals/`, and write only into `phasing/`. Never change another skill's file; if the design should change, say what in `summary.md`. Needs `pip install shapely pyproj networkx`, and Chrome or Edge for the PNGs; no Rhino.

**1. The brief.** Read `brief-reader/checklist.md`, and the brief's Markdown only at the pages it names for phases. Write `phasing/requirements.md`, one line per item with its page: the number of phases, what the first phase must hold and where, the facilities that must come early, any timing, what the panels must show about phases, and the emergency-access rules. Write "not stated" for each item the brief leaves out. Where you must decide something it leaves open, write the decision and its reason, marked as yours. Then copy `${CLAUDE_SKILL_DIR}/scripts/config.example.json` to `phasing/config.json` and fill every value with its source: the floor area per home the massing used, so both count homes alike, unless the brief gives one; the residents per home from the programme; the brief's minimum homes per phase and what must come first. Where neither the structure plan nor the massing phases a new neighbourhood, decide it in `phase_of` from the brief's order, with the reason. Only `first_phase`, `open_space_per_resident_m2`, `emergency` and `existing_residents` may be "not stated". Give `existing_residents` only from the brief or a cited source. Without it, open space per resident and service capacity are not measured wherever buildings stay. Emergency access takes only values from the brief or a regulation you cite by clause, never a standard of your own.

**2. The phases and their numbers.** Run `python "${CLAUDE_SKILL_DIR}/scripts/phases.py" --proposal <proposal folder> --config <proposal>/phasing/config.json`. A building takes its phase from `phase_of`, else from its structure-plan neighbourhood or centre, else from the massing; its homes are its housing floor area over the floor area per home, without a mixed building's ground floor or a daycare's floors. It writes `phases.csv` (per phase: homes, residents, the structure plan's planned homes and the difference, the minimum, its neighbourhoods, and what comes first: its centres and community buildings), `phases.geojson` (a `phase` area per phase, and every new building with its `phase` and `homes`) and `stats.json`, whose `flags` name every mismatch: a phase whose homes differ from the plan's, buildings the massing phases differently, buildings with no phase, a phase below its minimum, something due first that isn't there.

**3. Does each phase work.** Run `python "${CLAUDE_SKILL_DIR}/scripts/phasing.py" --proposal <proposal folder> --site <site folder> --config <proposal>/phasing/config.json`. Every building keeps the phase and the homes of step 2. The script never falls back on the nearest phase; a building without a phase is flagged for review and its evidence goes to `evidence.csv`. Weigh that evidence (location, access, the neighbourhood and centre it belongs to, the streets and services it depends on and when they are built). Then write `phasing/decisions.json` after `${CLAUDE_SKILL_DIR}/scripts/decisions.example.json`:
- a building's phase with `basis: proposed` only where the evidence points one way, with the reason, else `basis: review` with what is missing or in conflict;
- the phase of each stop (0 for one that exists today) and of each shared open space. A stop left undecided makes its checks "not measured", never a failure;
- services outside the site or temporary ones, each with its source;
- any closure of an existing street during building.

Run it again. Each street is built with the first phase that needs it, one no phase needs with the land it lies on, else with the last phase. A new street is for cars only where the mobility layer routes cars along it. An open space's paths are walking routes from its own phase, never before. Stage j is the time phase j is built: only what exists and phases 1 to j−1 work then, so a building under construction never counts. Each working building, and each building that stays, is checked at every stage: reached, connected to the streets beyond the site, by car, emergency access, and each service within walking distance. Open space per resident is checked at every stage too, and so is every car link the mobility config forbids between gateways. A building that stays and isn't reached today is counted in `stage-stats.json`, not failed, since no phase caused it. If `stage-stats.json` warns that the massing changed, check every building decision, then update `massing_fingerprint`; if it warns that a phase counts other homes than `phases.csv`, name the difference in `summary.md`, because the panels show `phases.csv`.

**4. The plan and the table.** Run `python "${CLAUDE_SKILL_DIR}/scripts/draw.py" --proposal <proposal folder> --site <site folder> --style <proposal>/drawing-graphics/style.json --size large`, and `--size small` if the panels need it. A frame in the panels' plan sets the plan's size and, if named, its scale. Without the drawing standard it draws nothing; say so in `summary.md`. Look at each PNG once.

**What steps 3 and 4 add to `phasing/`:**
- `phasing.geojson`, every feature with a `kind`:
  - `phase` (land, homes, residents as an estimate)
  - `building` (`id`, `phase`, `basis`, `reason`, `homes`, `geometry_valid`)
  - `street`, `stop` and `open-space`, each with its `phase`
- `stage-phases.csv`, the panel table's facilities, open space and access; its homes and residents come from `phases.csv`
- `stages.csv` and `access.csv`, what works at each stage
- `checks.csv`, `meets`, `partly`, `does not meet`, "not stated / not measured" or "for Claude to judge", each with the brief's figure, the design's and both sources. Judge the last kind yourself in `phasing.md`.
- `evidence.csv` and `stage-stats.json`
- `phasing_large.svg`/`.png` and `phases_table.svg`/`.png`

An invalid footprint keeps its ID and its phase from a name, but is left out of every measured figure, and each figure says so.

Then write `phasing.md`:
- the sequence, phase by phase, what each brings and why it comes then, with sources;
- the count of buildings by basis, adding up to every building in the massing;
- each proposed or flagged building with its reason.

And write `summary.md` in three lines: the phases and what comes first in each, with the plan's file and scale; the homes and residents per phase against the brief's; every flag, the buildings flagged for review, the neighbourhood furthest from its planned homes, the requirement least met and what you're unsure of.
