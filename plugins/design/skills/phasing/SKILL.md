---
name: phasing
description: Divides an urban design into construction phases, assigns every building to one, checks that each finished phase works on its own and meets the brief while the next is built, and draws the phasing plan with a table for the panels. Use when asked for phasing, construction phases or stages, the order of building, or what comes first.
---
# Phasing

Reads: brief-reader, programme, structure-plan, massing, streets, mobility, open-space, drawing-graphics

Never invent data, and never write a site, a city or a number of this project into the skill or its scripts: every number comes from the brief, its checklist or the other skills' files, with its source next to it. Work in the proposal folder you are told, else the newest in the project's `proposals/`, and write only into `phasing/`. Never edit another skill's file; if the design must change for the phases to work, say so in `summary.md`. Needs `pip install shapely pyproj networkx`, and Chrome or Edge for the PNGs.

**1. The brief.** Read `brief-reader/checklist.md`, and the brief's Markdown only at the pages it names for phases. Write `phasing/requirements.md`, one line per item with its page: the number of phases, what the first phase must hold and where, the facilities that must come early, any timing, what the panels must show about phases, and the emergency-access rules. Write "not stated" for each item the brief leaves out. Where you must decide something it leaves open, write the decision and its reason, marked as yours. Then copy `${CLAUDE_SKILL_DIR}/scripts/config.example.json` to `phasing/config.json` and fill every value with its source. Only `first_phase`, `open_space_per_resident_m2`, `emergency` and `existing_residents` may be "not stated". Give `existing_residents` only from the brief or a cited source. Without it, open space per resident and service capacity are not measured wherever buildings stay. Emergency access takes only values from the brief or a regulation you cite by clause, never a standard of your own.

**2. Run, decide, run again.** Run `python "${CLAUDE_SKILL_DIR}/scripts/phasing.py" --proposal <proposal folder> --site <site folder> --config <proposal>/phasing/config.json`. Every building takes its phase from the massing, else from the structure plan's neighbourhood. The script never falls back on the nearest phase; a building with neither is flagged for review and its evidence goes to `evidence.csv`. Weigh that evidence (location, access, the neighbourhood and centre it belongs to, the streets and services it depends on and when they are built). Then write `phasing/decisions.json` after `${CLAUDE_SKILL_DIR}/scripts/decisions.example.json`:
- a building's phase with `basis: proposed` only where the evidence points one way, with the reason, else `basis: review` with what is missing or in conflict;
- the phase of each stop (0 for one that exists today) and of each shared open space. A stop left undecided makes its checks "not measured", never a failure;
- services outside the site or temporary ones, each with its source;
- any closure of an existing street during building.

Run again. Each street is built with the first phase that needs it. An open space's paths are walking routes from its own phase, never before. Stage j is the time phase j is built: only what exists and phases 1 to j−1 work then, so a building under construction never counts. Each working building, and each building that stays, is checked at every stage: reached, connected to the streets beyond the site, by car, emergency access, and each service within walking distance. Open space per resident is checked at every stage too, and so is every car link the mobility config forbids between gateways. If `stats.json` warns that the massing changed, check every building decision, then update `massing_fingerprint`.

**3. The plan and the table.** Run `python "${CLAUDE_SKILL_DIR}/scripts/draw.py" --proposal <proposal folder> --site <site folder> --style <proposal>/drawing-graphics/style.json --size large`, and `--size small` if the panels need it. Without the drawing standard it draws nothing; say so in `summary.md`. Look at each PNG once.

**What it writes into `phasing/`:**
- `phasing.geojson`, every feature with a `kind`:
  - `phase` (land, homes, residents as an estimate)
  - `building` (`id`, `phase`, `basis`, `reason`, `homes`, `geometry_valid`)
  - `street`, `stop` and `open-space`, each with its `phase`
- `phases.csv`, the panel table
- `stages.csv` and `access.csv`, what works at each stage
- `checks.csv`, `meets`, `partly`, `does not meet`, "not stated / not measured" or "for Claude to judge", each with the brief's figure, the design's and both sources. Judge the last kind yourself in `phasing.md`.
- `evidence.csv` and `stats.json`
- `phasing_large.svg`/`.png` and `phases_table.svg`/`.png`

An invalid footprint keeps its ID and its phase from a name, but is left out of every measured figure, and each figure says so.

Then write `phasing.md`:
- the sequence, phase by phase, what each brings and why it comes then, with sources;
- the count of buildings by basis, adding up to every building in the massing;
- each proposed or flagged building with its reason.

And write `summary.md` in three lines: the phases and what comes first; the homes and residents of the first phase against the brief's; the number of buildings flagged for review, and the requirement least met or the decision you are least sure of.
