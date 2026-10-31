# End-to-end studio

This repo has two halves. `plugins/` holds the tools: skills for architecture competitions in nine topic plugins, each skill one person's part, in `plugins/<topic>/skills/<name>/SKILL.md`. `competition/` holds this semester's job, Europan 18 in Regensburg, which the tools answer. `STUDIO.md` is the contract for writing and running a skill, and each topic's `TOPIC.md` says what its skills read and write. Read both before you write or run one.

## Where things are

- The brief: `competition/brief/`, `Regensburg_EN_1.pdf`. Its Markdown goes next to it, made by `pdf-to-md`.
- The site: `competition/site/`, made by `site-kit`: `site.geojson` and its layers.
- The reference images the drawings take their look from: `competition/references/`.
- The proposals: `competition/proposals/`, one folder per run. They stay on this computer. Test a skill in `competition/proposals/test/`.

I study architecture or design and don't write code. Explain each step in a sentence or two of plain words. After a change, say which files you changed and what I should look at.

## The competition is closed

Europan 18 has been judged, and its results are published. Never search for, open or use the results, the jury report, or any entry submitted to it, for this site or any other. Don't fetch anything from europan.de: the brief you need is already in `competition/brief/`. If a search or a page shows you an entry or a result anyway, stop reading it, don't use anything from it, and write in the proposal folder's `log.md` that you saw it and where. The point is to find our own answer.

## Skills

- A skill must work on its own, in any project, on any brief and site. Never write a site, a competition, a layer name or a path of this repo into it. Its own files sit in its folder and are called through `${CLAUDE_SKILL_DIR}`.
- When I ask you to change a skill, change the fewest lines that fix what I didn't like, and tell me which. Keep it short. If a line no longer changes the result, suggest deleting it.
- To compare, run the same request once without the skill ("don't use any skill") and once with it, and save both results side by side.
- After changing a skill, remind me to type `/reload-plugins`, so the new version is the one that runs.
- A pull request changes only the author's own skill folder.

## Keys

Keys live in `.env` and nowhere else: not in a skill, not in a commit.
