# Runs site: a public page to study the studio's runs

Date: 2026-11-08. Status: for approval.

## Why

The studio runs end to end and hands in three panels. When something on a panel is wrong, the panels alone don't say where it went wrong: which skill drew it, what that skill read, what it was unsure of, what art direction asked it to fix and whether the redraw did. Today that story is spread over a dozen files in a run folder, and most of those files sit on the one computer that ran it. The site puts each run's model, drawings, timeline, costs and loop on one public page, so everyone in the studio (students and teachers) can study a run after it's finished and find where a problem started.

Success: someone looks at a weak drawing on a panel, clicks it, and within a minute can name the skill and the step where it went wrong, without opening the repo.

## Goals

1. **Model**: a 3D viewer of a run's geometry, with every layer that has geometry switchable on and off, and the run's timeline along the bottom.
2. **Panels**: the run's three panels, where every drawing can be clicked to show its provenance as a graph, with the same timeline below in more detail.
3. **Loop**: the system loop the run used, drawn as a diagram: which skills ran in what order and why (their `Reads:` lines at the run's commit), plus the lead's own steps.
4. **Dashboard**: every run side by side (cost, time, jury, required items, cost per skill, recurring problems), from which you can open any single run.
5. Built from the files each run already writes. No skill has to write anything new for the site.

## Non-goals

- Live progress while a run is going. The site shows finished runs only.
- Editing anything from the site (no comments, no stickies). Feedback stays on Miro and in `competition/feedback/`.
- Replacing the Session 4 slides. The slides tell the story of the runs for a session; the site is for looking things up. They may share code and data.
- A login or private area.

## Anti-goals (a failure even if it works)

- **Anything of the Europan 18 winners on the public site**: their boards, their cut drawings, the `.compare/` sheets with their drawings beside ours, their texts, titles or names. The repo is public and the winners stay off it (see `.gitignore`).
- Keys or anything from `.env`.
- A cluttered, dashboard-template look. It must read as minimal, clear, modern and elegant: one typeface family, ink and greys, one accent for selection, red only for problems. The approved direction is the mockup at `.superpowers/brainstorm/18470-1794091911/content/three-pages.html` (local, with its data in `d.js` beside it). The first mockup, with coloured boxes and a busy grid, was rejected.
- Publishing a run that loses what an earlier publish showed (see "Several people publish" below).

## Constraints

- The repo (`Bauhaus-InfAU/end-to-end-studio`) is public. GitHub Pages is on and today serves `main:/docs` at `https://bauhaus-infau.github.io/end-to-end-studio/`, the existing "Studio skill flow" page (`docs/index.html`, with panels of runs 1 to 5 in `docs/runs/`).
- Only a run's log, cost, notes, summaries, jury report and panel PNGs are in git (`.gitignore`). The drawings, the GeoJSON, `layout.json` and `fixes.json` exist only on the computer that ran it.
- Studio rules (`CLAUDE.md`): code that a skill needs in every run goes in its `scripts/` folder; a skill's text never names this repo's site, competition, layers or paths; a script takes its paths as arguments. Keys only in `.env`.
- The user doesn't write code. Every step they run must be one command, explained in plain words.
- Pushing to a public site is outward facing: the publish step asks before it pushes.

## The data each page uses

Per run folder (`competition/proposals/<date>_<label>/`):

| File | In git | Used for |
| --- | --- | --- |
| `README.md` | yes | title, skill table (state, time, cost), each skill's summary, open problems, issues handed on |
| `version.md` | yes | date, commit of the skills, kind of run, what was new in it |
| `log.md` | yes | the timeline: `HH:MM start a, b, c` and `HH:MM <skill> [first run / second run / rerun] done: …` lines; also lead steps (`side_by_side.py`, `frames.py`, `cost.py`) |
| `cost.csv` | yes | cost per skill and run, model (opus or sonnet), steps; a `total` row |
| `*/summary.md` | yes | what each skill made, its key number, what it was least sure of |
| `jury/report.md` | yes | verdict, rounds, appraisal |
| `panel-layout/panel-*.png` | yes | the panels |
| `panel-layout/layout.json` | no | every item on every panel: its file, position and size in mm (`panels[].items[]` with `file`, `x`, `y`, `w`, `h` or `frame`) |
| `panel-layout/issues.md` | no | issues handed to other skills |
| `art-direction/fixes.json` | no | the fixes per drawing skill |
| drawings named in `layout.json`, other PNG/SVG in skill folders | no | the drawing in the provenance card |
| `*/*.geojson` | no | the Model layers of the run |

Per project: `competition/site/`, `competition/climate/`, the analysis of the site as it is. `preview.py` (`plugins/studio/skills/competition-proposal/scripts/`) already gathers all of these and every run's GeoJSON into `proposals/preview/data/<source>.js`; the new builder reuses its loading code.

Per commit: each skill's `Reads:` and `Reads (end):` lines in `plugins/*/skills/*/SKILL.md`, read at the run's commit with `git show <commit>:<path>`, and the lead's steps in `competition-proposal/SKILL.md` at that commit.

Older runs (run-1 to run-5) have fewer files and log lines in an older form. Each page shows what a run has and leaves out the rest without error.

## The pages

One site, a bar along the top with the tabs **Model**, **Panels**, **Loop** and **All runs**, and a run picker on the right. Every run page has its own address (`#run-11/model`, `#run-11/panels`), so a link can be shared.

### Model

- Full-window 3D view of the run (deck.gl, as `preview.py`'s page uses): the existing city pale, the new buildings white with soft shading; hover a building for its use, floors, height and type.
- A layer panel listing every GeoJSON the run and the project have, grouped by the skill that wrote it (site, climate, analysis today, analysis design, structure-plan, massing, streets, open-space, mobility, phasing, ground-floor, …). Each group and each layer has an on/off switch; the panel can collapse. Each layer gets a quiet default style by its geometry and `kind`; climate and analysis layers that carry classes (noise bands, sun hours, sealing) are coloured by class with a small legend.
- A box with the run's headline numbers (title, homes, floor area, sealed share, cost, jury).
- The timeline along the bottom: one row per skill, Opus dark, Sonnet grey, reruns as outlines, lead checks as dashed marks. Play, or drag the cursor: each skill's layers appear when it finished, so you watch the model build up; a caption names the last skill done and its log line. Switching a layer off by hand wins over the timeline.

### Panels

- The three panels side by side, zoomable. Every item in `layout.json` is a clickable area on its panel (mm converted to the panel's pixel size).
- Clicking one opens a side panel with its **provenance graph**: the drawing, the skill that drew it, the skills that skill read (its `Reads:` at the run's commit), and so on back to the brief and the site. Each node shows the skill's runs (first, second, rerun), time and cost, model, and the "least sure" part of its summary. Nodes that went wrong are red: a skill with fixes in `fixes.json`, an issue in `issues.md`, a rerun that left fixes undone, or a jury point that names its work. The graph shows two steps back at first; the rest opens on click.
- Below it, the drawing itself and its story in order: first run → art direction's fix → redraw → least sure → what the jury said about it.
- Below the panels, the same timeline as on Model in more detail: each row has the skill's name, its total cost and a one-line state (red when something is open), the lead's checks labelled (frame check, cost check). Clicking a drawing highlights its skill's row, and clicking a row highlights that skill's drawings on the panels.

### Loop

- The loop the run used, as a diagram from left to right: the inputs (brief, site, climate), then the skills in waves by their `Reads:` lines, the lead's steps as small separate marks (side-by-side sheets, frame check, cost check with its ceiling), and the redraw round drawn as a loop going back into the drawing skills, then panel-layout's second run and the jury.
- On each node, what really happened in this run: time, cost, number of runs. Skills that the system has but the run didn't use are faint.
- A "compare with" picker draws the differences from another run: skills added or removed, reads that changed, a new round.

### All runs (dashboard)

- Headline numbers: runs, total spend, median run, best verdict, required items on the latest run.
- Cost and time per run (cost split Opus and Sonnet where `cost.csv` has it), with the jury's verdict under each run.
- Required items on the panels per run.
- Cost per skill and run, as a grid.
- Problems that come back, as a grid of runs with the run each fix landed after.
- Clicking a run anywhere opens its **run summary**: title, headline numbers, cost per skill by model, the timeline, the open problems and the issues handed on (from its README), the jury's verdict, and links to its Model, Panels and Loop.

## How it's built and published

- **Build**: one script, `site.py`, in `plugins/studio/skills/competition-proposal/scripts/`, next to `preview.py`: `python site.py <project inputs folder> --proposals <folder> --out <folder>`. It reads every run folder and the project inputs and writes a static site (one `index.html`, its scripts and styles, one data file per run, images) into `--out`. It runs at the end of every run, where `preview.py` runs now (one line added to step 4 of `competition-proposal/SKILL.md`), and can be run by hand at any time.
- **Images**: panels as JPG about 2,400 px tall; every other drawing as JPG at most 1,600 px on its long side; SVGs rasterised. Geometry rounded to 6 decimals, as `preview.py` does.
- **What may be copied**: an allow list, nothing else: the files in the data table above, `narrative/text.md`, and the project's site, climate and analysis GeoJSON. Never anything under a `references` or `winners` folder or `.compare/`, never `.env`. The build stops with an error if a drawing named in `layout.json` points into one of those.
- **Publish**: a second script, `publish.py`, run by hand: it shows what will go up (runs, number of files, size), asks, then replaces the `gh-pages` branch with the built site in one commit and pushes it (see "Decided by the user").
- **Several people publish**: runs are made on different computers, and each has only its own drawings. Publishing merges with what is already on the site: a run is replaced only if the local build has at least what the site has for it; otherwise the published version of that run is kept.
- **Tests**: `tests/test_site.py`, with a small fixture run (a few log lines, a `cost.csv`, a `layout.json`, one GeoJSON), checking the log parser, the allow list (a winners' path is refused), the mm-to-pixel mapping and the merge rule. Run with `python -m pytest tests`.

## My calls (the user can change any)

- The graph shows two steps back first, the rest on click.
- The problems grid starts from the error ledger in the Session 4 slides (`content.js`), copied into a hand-kept `competition/proposals/ledger.json`; new rows are added by hand.
- A run's headline numbers that the files only give in prose (jury verdict, required items) are read from `jury/report.md` and `panel-layout/summary.md` where a simple pattern finds them, and can be set in a small `runs.json` next to the ledger when it doesn't.
- The existing buildings use their footprints and heights (`site/buildings`), not the 17 MB LoD2 meshes, to keep the page light.
- **Red marks come only from structured files**, never from guessing in prose, because a wrong red mark sends people to the wrong skill: a skill is red when `art-direction/fixes.json` has fixes for it, `panel-layout/issues.md` hands it an issue, or `frames.py`'s log line names its drawing. A fix is tied to a drawing when the fix names that drawing's file; otherwise it shows on the skill. Whether a rerun left fixes undone is shown as its log line, not as a mark. The jury's points are listed on the run as the report has them, and are tied to a skill or drawing only where `runs.json` says so by hand (no language model at build time: no key, no cost per build).
- **Cost**: per skill exact from `cost.csv`; per single run of a skill (first, second, rerun) not shown, since `cost.csv` numbers a second run and a rerun alike.
- **What counts as a run**: a folder in `proposals/` whose name starts with a date and that has panels (`panel-layout/panel-*.png`). Drafts and tests without panels stay out; `runs.json` can hide a run or mark it a variant (as `mobility-lean`), and the dashboard counts variants apart from the runs.

## Left to the builder

The code structure, libraries beyond deck.gl, the graph layout method, colours within the approved direction, the exact typeface, how the timeline parser handles older log forms, file names inside the built site.

## Decided by the user (2026-11-08)

- **Who publishes**: only people with write access to `Bauhaus-InfAU/end-to-end-studio`. Students working from forks don't publish; their runs reach the site when a collaborator builds and publishes. `publish.py` pushes directly.
- **Where the site lives**: on its own `gh-pages` branch, which each publish replaces with one fresh commit, so `main` stays light. Pages must be switched from `main:/docs` to `gh-pages` in the repo's settings; that's done by hand by someone with admin rights, once, after the first publish, not by a script. Until then the old page stays live.
- **The old page**: "Studio skill flow" is folded into the new site, which takes the main address. Its content (how the skills feed each other, round by round) becomes the Loop tab. It fetches the SKILL.md files live from `main` today; in the new site the Loop data is built into the site instead. Its runs 1 to 5 move into the run picker. `docs/index.html` and `docs/runs/` can be removed from `main` once the new site is live.
- **Winners' names in our own files**: removed. At build time `site.py` takes the forbidden names from the local references folder (passed as an argument, e.g. `--references <folder>`): each winner folder's name and its parts (`3_special-mention_copper-moth` gives `copper-moth`, `Copper Moth`, `Moth`), plus any extra words in an optional names file next to it. Every text copied to the site (summaries, README, version.md, log, jury report) has these replaced by "a reference"; sentences that describe the winners without naming them stay. A build without `--references` still runs (a project may have no references), but it records that, and `publish.py` refuses to push such a build unless it's told the project has no references (`--no-references`). So a build on a computer without the winners' folder can't publish their names by mistake. Tests check the replacement with made-up names.
