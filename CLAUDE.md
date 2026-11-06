# End-to-end studio

This repo has two halves. `plugins/` holds the tools: skills for architecture competitions in nine topic plugins, each skill one person's part, in `plugins/<topic>/skills/<name>/SKILL.md`. `competition/` holds this semester's job, Europan 18 in Regensburg, which the tools answer. `STUDIO.md` is the contract for writing and running a skill, and each topic's `TOPIC.md` says what its skills read and write. Read both before you write or run one.

## Where things are

- The brief: `competition/brief/`, `Regensburg_EN_1.pdf`. Its Markdown goes next to it, made by `pdf-to-md`, and `checklist.md`, made by `brief-reader`. Read the checklist first, and the brief only at the pages it names.
- The site: `competition/site/`, made by `site-kit`: `site.geojson` and its layers.
- The climate: `competition/climate/`, made once by `climate` and copied into each run. It isn't committed.
- The reference images the drawings take their look from: `competition/references/`. The winners' boards are in `competition/references/winners/<rank>_<entry>/`, as `board-1.jpg` to `board-3.jpg` and cut one drawing per file (`site-plan.jpg`, `detail-area-1.jpg`, `building-types.jpg`, and so on). `competition/references/README.md` says which skill should look at which file.
- What people said about the runs: `competition/feedback/<date>_<run>/`, with every sticky, the marked panels and the issues it became.
- The proposals: `competition/proposals/`, one folder per run. Only their logs, costs, notes, summaries, jury reports and panel PNGs go to git, so others can study the runs; the rest stays on this computer. Test a skill in `competition/proposals/test/`. A map of the site, the climate and every run's geometry: `competition/proposals/preview/index.html`, remade after each run by the lead's `preview.py`.
- The studio's own checks: `tests/`, run with `python -m pytest tests`.

I study architecture or design and don't write code. Explain each step in a sentence or two of plain words. After a change, say which files you changed and what I should look at.

## The winners are references

Europan 18 has been judged. Since 04.11.2026 the three winners of this site are the studio's references: the runs learn their look, their layout and their level of detail, drawing by drawing, the way you learn by copying a master. Their boards are in `competition/references/winners/`. A skill that draws something looks at the winners' drawing of the same kind first and gets as close to it as it can. drawing-graphics reads the nine full boards (`board-N.jpg`, not the `_marked` ones). The jury compares a run with them.

Use only what is in that folder. Don't search the web for other entries or fetch anything from europan.de; the brief is in `competition/brief/`. Don't put the winners' texts, titles or names on our panels.

## Skills

- A skill must work on its own, in any project, on any brief and site. Never write a site, a competition, a layer name or a path of this repo into it. Its own files sit in its folder and are called through `${CLAUDE_SKILL_DIR}`.
- When I ask you to change a skill, change the fewest lines that fix what I didn't like, and tell me which. Keep it short. If a line no longer changes the result, suggest deleting it.
- To compare, run the same request once without the skill ("don't use any skill") and once with it, and save both results side by side.
- After changing a skill, remind me to type `/reload-plugins`, so the new version is the one that runs.
- Code a skill needs in every run goes in its `scripts/` folder, with the brief's numbers in a `config.json`, never in the skill's text.
- A skill runs on Sonnet unless its `Model: opus` line says otherwise. Add that line only to a skill that judges.
- To run the whole studio, start Claude Code as the README's "On a Pro plan" says.
- Everyone owns every part. A pull request answers one issue, changes the fewest files that fix it, wherever they are, and says which issue it answers.

## Keys

Keys live in `.env` and nowhere else: not in a skill, not in a commit.
