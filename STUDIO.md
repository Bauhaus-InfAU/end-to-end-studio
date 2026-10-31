# The studio

A set of skills that makes a competition entry, from the brief to the panels. They are grouped into nine topics, and each topic is a plugin you can install into any project. This semester twenty of you write one skill each, and together they answer Europan 18 in Regensburg: three vertical A1 panels and up to four pages of text. Next year the same skills should answer another brief, and you should be able to take yours into your own practice.

This file is the contract. If your skill keeps to it, the studio can run it, and it works on its own too.

## Topics and modules

A topic is a plugin in `plugins/<topic>/`. Each skill in it is a module: one folder in `plugins/<topic>/skills/<skill>/` with a `SKILL.md`, and any scripts or files it needs next to it. Its `TOPIC.md` says what the skills of that topic read and what shape they write. Read it before you write yours.

You can add a module to a topic at any time. An `isovist` or `space-syntax` skill goes into `analysis`. If it writes what `analysis/TOPIC.md` asks for, the comparison and the panels pick it up without anyone else changing a line. In Claude Code the skill is then called `/analysis:isovist`.

## Every skill works alone

Copy one skill folder into another project's `.claude/skills/`, or install its topic, and it must still work:

- It names its inputs in plain words and looks for them in the project's inputs and the proposal folder. If one is missing, it asks or says so in `summary.md`; it never invents data.
- Nothing about Europan, Regensburg, A1 or this repo is written into a skill. All of that comes from the brief.
- If it needs a rule from its `TOPIC.md`, it says that rule in its own words, in one line.
- Its scripts and files sit in its folder, and it calls them through `${CLAUDE_SKILL_DIR}`, so the path works wherever it's installed.
- It says what it needs installed (`pip install docling`) and where a key goes (`.env`, never the skill).

## The inputs

Three things belong to the project, not to one version, and every version reads them:

- The brief: the PDFs in the project's `brief/`, each with its Markdown next to it, made by `pdf-to-md`.
- The site: the project's `site/`, made by `site-kit`. `site.geojson` is the project site, one polygon in WGS84, longitude first. Next to it are the layers (buildings, plots, streets, water, rail) and their `SOURCES.md`.
- The references: the images in the project's `references/`, for `drawing-graphics`.

In this repo they're in `competition/`. In another project they're wherever its `CLAUDE.md` says, else at the top. `pdf-to-md` and `site-kit` write there, and the lead runs them only when their output is missing. Every other skill only reads them.

## The proposal folder

Every version of a proposal is a folder `<YYYY-MM-DD>_<label>/` in the project's `proposals/`, such as `2026-11-02_run-1`. In this repo that's `competition/proposals/`. In another project it's wherever its `CLAUDE.md` says, else `proposals/` at the top. A skill works in the proposal folder it is told, else the newest one there, else a new `<YYYY-MM-DD>_draft/`. In it:

- `<skill>/`: everything a skill writes, and nothing outside it. Every skill leaves a `summary.md` of three lines: what it found or made, the one number that matters, the one thing it's unsure of.
- `version.md`, `README.md` and `log.md`, written by the lead.

Drawings are SVG with a PNG next to each, images PNG, tables CSV, geometry GeoJSON in WGS84.

`competition-proposal` makes a new version, a variant of an earlier one ("redo the massing of run-1"), or compares two. `proposals/` is never committed. To test your skill, tell it to work in `competition/proposals/test/`; the brief and the site are in `competition/` already. If it reads a skill that doesn't exist yet, ask your agent for a rough stand-in in that skill's folder, in the shape its `TOPIC.md` gives.

## The order

Near its top every skill has a line `Reads:` with the skills whose output it needs, such as `Reads: narrative, programme`. A skill that works twice adds `Reads (end): ...` and runs again once those exist. `everything` means every skill that doesn't wait for this one; `every analysis` means every skill of that topic that doesn't wait for this one. The lead starts each skill as soon as its inputs exist, side by side, so nobody keeps an order up to date. The flow, round by round, is on [the studio's page](https://bauhaus-infau.github.io/end-to-end-studio/).

## The tools

Skills work in code and plain files, not in a modelling program. Leave Rhino and Grasshopper out wherever you can: the lead runs twenty skills side by side with nobody at the screen, and every skill has to work in any project, on any computer.

- Python 3.11 or newer. What the studio needs is in `requirements.txt` at the top of the repo: `pip install -r requirements.txt`, once.
- Geometry with `shapely` and `pyproj`. 3D is the footprints extruded by their heights (`trimesh` if you need a mesh), and a section is a cut through them.
- Drawings as SVG, written directly, with a PNG next to each made by a headless browser (Chrome or Edge, `--headless --screenshot`). No plotting library: plots look like charts.
- Perspectives and atmosphere from an image API, on a view of the massing the skill draws first. The key goes in `.env`.
- If a skill really can't do without Rhino, it says why in one line, and without Rhino it says so in `summary.md` instead of failing silently.

## Shared rules

- Never invent data. Every number has its source or its assumption next to it.
- The look comes from `drawing-graphics`, which turns the project's reference images (here `competition/references/`) into a standard. Drawing skills decide what a drawing shows, never its colours, line weights or fonts.
- Scale comes from the brief. A drawing skill says what to show when the drawing is large and when it is small.
- Keep a skill short: two or three paragraphs, a list if it helps. Add a line when you don't like a result, delete lines the model no longer needs.

## The skills

| Topic | Skill | What it does | Who |
| --- | --- | --- | --- |
| utilities | `pdf-to-md` | PDFs to Markdown with page markers, tables, and the pictures and vector plans in them. Example | `YegorGaidukov` |
| brief | `brief-reader` | A checklist from the brief: numbers, required drawings and scales, panel format, what the jury looks for | open |
| site | `site-kit` | The site's boundary and data: buildings, plots, streets, water, rail. Example | `YegorGaidukov` |
| | `climate` | Fresh-air corridors, sun, wind, noise | `HawarHeidari` |
| analysis | `analysis` | The site as it is: uses, edges, green and biotopes, walking reach, sealed share, what to keep. At the end the same on the design, and the comparison of every analysis | `roy-mdr` |
| concept | `narrative` | The idea, its title and the storyline across the panels. At the end, the text with the key figures | `Emdot-code` |
| | `structure-plan` | The urban figure: green corridors, neighbourhoods, centres, main routes | `dishadesign1503-lab` |
| | `programme` | The brief's programme as a table: homes and household mix, residents, uses and their areas | `Mehrn00shK` |
| design | `massing` | Buildings, streets and open spaces on the structure plan | `TukaElGhazaly` |
| | `phasing` | The construction phases and what comes first | open |
| | `mobility` | How people arrive and move: hubs, low-traffic streets, bike and foot routes, parking | `simaycansubulat` |
| | `open-space` | Parks, squares, gardens, and the blue-green network with rain retention | open |
| drawings | `drawing-graphics` | The studio's drawing standard, made from the reference images | open |
| | `figure-ground` | The figure-ground plan of the district in its city | open |
| | `plans` | Every plan the brief asks for, at its scales: the overall plan and the detail areas | open |
| | `site-section` | A long section through the site, and elevations if the brief asks for them | `yhemayll` |
| | `isometric` | An isometric overview of the district | `MujdaMursal` |
| | `building-types` | A row of axonometric building types | `simonmazob9` |
| | `concept-diagrams` | Three to six pictograms that tell the idea | `nouranmoustafa` |
| | `perspective` | Eye-level views with people, from a view in the massing | `Isabelacano` |
| delivery | `panel-layout` | The panels the brief asks for, along the storyline | `bengunur` |
| | `jury` | Reads the entry as the competition's jury would, against the brief and its own storyline: what convinces, what's weak, a verdict | open |
| studio | `competition-proposal` | The lead: runs the others, keeps the versions | `YegorGaidukov` |

"Who" is the GitHub username of the person responsible. "open" means nobody has the skill yet. Egor (`YegorGaidukov`) keeps this column, so don't change it in your pull request.
