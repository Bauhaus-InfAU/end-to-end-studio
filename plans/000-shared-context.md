# Shared context for every plan in this folder

Every plan in `plans/` is written for an executor that has seen nothing else. This file holds what all of them share. Each plan tells the executor to read it first.

## The repo in five lines

- `plugins/<topic>/skills/<skill>/SKILL.md` is one skill: a short instruction text (two or three paragraphs) for an AI helper that runs it. Its scripts sit in `scripts/` next to it and are called through `${CLAUDE_SKILL_DIR}`.
- `competition/` is this semester's job (Europan 18, Regensburg). `competition/site/` is committed (site.geojson, buildings.geojson, plots.geojson, streets.geojson, street-land.geojson, water.geojson, rail.geojson, buildings-3d.geojson, terrain-dgm1.tif, kit.json, SOURCES.md). `competition/proposals/` and `competition/climate/` are NOT committed; they exist on the owner's computer only. Tests that need them skip when they are missing.
- `STUDIO.md` is the contract (read its sections "Every skill works alone", "The order", "The tools" and "Shared rules" before changing a skill). `plugins/<topic>/TOPIC.md` says what a topic's skills read and write.
- `tests/` is the studio's own checks: `python -m pytest tests -q`. `tests/conftest.py` defines `REPO`. `tests/test_scripts.py` is the pattern for script tests (subprocess, a copy of inputs in `tmp_path / "with space" / ...`, a `FORBIDDEN` regex that fails any script naming the site).
- The repo owner reads plain words, not code. SKILL.md text is for that reader: short sentences, no jargon, no bullet soup.

## Rules every change must keep (from STUDIO.md and CLAUDE.md)

1. Nothing about Europan, Regensburg, A1 or this repo in a skill or a script. The test `tests/test_scripts.py::test_no_site_in_new_scripts` fails on these words in the massing scripts: `Regensburg|Europan|Pilsenallee|Chamer|Brandlberg|Haslbach|Wutzlhofen|run-3|25832|49.0xxxx|12.xxxx|C:\Users|C:\Work`. Add every new script you write to that test's `NEW_SCRIPTS` list.
2. A script's own numbers live in a `DEFAULTS` dict with a one-line meaning each. The brief's numbers come from a `config.json` in the proposal folder, each as `{"value": ..., "source": "<brief file> p. N, or assumption: why"}`. A required value left empty stops the script with that value's name (see `read_config` in `plugins/design/skills/massing/scripts/massing.py:21-33`).
3. Geometry with `shapely` 2 and `pyproj`, in the UTM zone of the site's centroid (`utm_epsg` in massing.py:16-18), written back as WGS84, longitude first. No Rhino, no plotting library.
4. Drawings are SVG written in code with `width="...mm" height="...mm"` at their scale, and a PNG next to each made by a headless Chrome or Edge (`find_browser` in `plugins/design/skills/streets/scripts/streets.py:476-485` is the pattern; `shot` in `plugins/design/skills/massing/scripts/draw.py:82-90` is the Windows-friendly one). Text in a drawing is never smaller than 3.2 mm printed (12 px, 9 pt). North arrow: a circle in outline and one line from its centre to the circle. Scale bar: one thin line that steps up and down, ticks at every step, numbers under the ticks, the unit only on the last.
5. The look comes from `drawing-graphics/style.json` in the proposal folder, when it exists. Its keys: `paper, ink, accent, new, existing, context, building, street, path, park, kept, lawn, meadow, wet-meadow, grove, water, ramp (list of 5), font, thin, mid, thick, line, line_mm, outline, text (mm), title (mm), body_pt, heading_pt`. A script reads it through `--style <style.json>` or by path and falls back to black on white with one accent. A drawing skill never fixes a colour of its own.
6. A skill works alone: with a missing input it says so in `summary.md` and does what it can; it never invents data.
7. Keep SKILL.md short. Change the fewest lines that do the job and keep the author's voice. Don't touch the "Who" column of `STUDIO.md`.
8. `Model: opus` goes only below the `Reads:` line of a skill that judges. `tests/test_order.py` pins the set `{narrative, structure-plan, massing, jury}`; don't change it in these plans.

## Commands

| Purpose | Command (from the repo root `C:\Work\GitHub\end-to-end-studio`) | Expected |
| --- | --- | --- |
| Install | `pip install -r requirements.txt` | exit 0 (already installed on the owner's computer) |
| All tests | `python -m pytest tests -q` | Baseline at planning time: **30 passed, 1 failed**. The failure is `tests/test_scripts.py::test_massing_reproduces_run3` and is pre-existing: the site was remade on 2026-11-03 and run-3 was made on the old site. Plan 001 replaces that test. |
| One test file | `python -m pytest tests/test_scripts.py -q` | see above |
| Site words | `python -m pytest tests/test_scripts.py::test_no_site_in_new_scripts -q` | passed |

Python is 3.11+. Installed and importable here: shapely, pyproj, numpy, trimesh, requests, python-dotenv, PIL (Pillow), networkx 3.4, cv2 (opencv). NOT installed: rasterio. Chrome is at `C:\Program Files\Google\Chrome\Application\chrome.exe`.

## Git workflow (all plans)

- Work in the main working tree, on branch `main`. Do NOT create a branch, do NOT commit, do NOT push: the owner commits. (A worktree is not used because the tests need `competition/proposals/`, which is not in git.)
- The working tree already holds uncommitted edits in six files from the owner's own work: `plugins/delivery/skills/panel-layout/scripts/panels.py`, `plugins/design/skills/massing/scripts/draw.py`, `plugins/drawings/skills/concept-diagrams/scripts/draw_diagrams.py`, `plugins/drawings/skills/drawing-graphics/base.md`, `plugins/drawings/skills/isometric/isometric.py`, `plugins/site/skills/climate/scripts/draw.py`. Leave those edits in place. Never run `git checkout --`, `git stash` or `git reset`.
- Write nothing into `competition/proposals/` except in a folder named `test/` or into `tmp_path` of a test. Never modify `competition/site/`, `competition/brief/` or `competition/climate/`.
- When done, list every file you changed or created, with one line each on what changed, in your report.

## The synthetic proposal used by tests (made by plan 001, reused by 002 to 009)

`tests/synthetic.py` builds a small proposal folder from the committed site, so the tests run on any computer. Its `make_proposal(tmp_path, **options)` returns the proposal folder and writes:

- `<tmp>/site/`: a copy of `competition/site/` (every file).
- `<tmp>/proposals/2026-01-01_t/structure-plan/structure-plan.geojson`: features in WGS84 with `kind`, `name`, `action`, `basis`, `source`: one `neighbourhood` "Field" (`action: new`), a rectangle of about 400 × 300 m inside the site, centred on the pole of inaccessibility (`shapely.ops.polylabel`) of `site.geojson`'s polygon shrunk by 100 m (compute in UTM, rotate nothing); one `centre` "Square" (`level: main`, `holds: "stop, bus station, shops"`), a 60 × 60 m square at the neighbourhood's southern edge, inside it; one `centre` "Corner" (`level: local`, `holds: "school, daycare"`) 60 × 60 m at the north-east corner inside the neighbourhood; one `green` "Strip" (`roles: ["climate"]`), a 50 m wide north–south strip through the middle of the neighbourhood; one `route` "Main road" (`level: main`), a line along the neighbourhood's southern edge; one `route` "Path" (`level: landscape`) through the green strip; one `gateway` "Gate" at the south-west corner. Options: `split_green=True` (default) keeps the strip; `holds=False` writes centres without `holds`.
- `<tmp>/proposals/2026-01-01_t/massing/config.json`: a copy of `tests/fixtures/massing_config_run3.json` with `density` replaced by `{"Field": "medium"}` and `phase1` by `["Field"]`, `site_plan_scale` 3000, every other value kept. (The fixture's numbers are a brief's numbers; the test proposal is a stand-in, not a design.)
- `<tmp>/proposals/2026-01-01_t/drawing-graphics/style.json`: a copy of `plugins/drawings/skills/drawing-graphics/base.json`.

Run the massing on it with `python plugins/design/skills/massing/scripts/massing.py --proposal <that folder> --site <tmp>/site --config <that folder>/massing/config.json`.
