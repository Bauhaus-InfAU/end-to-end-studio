# End-to-end studio

A studio made of skills. Thirty people each write one skill, and together the skills answer a real competition from the brief to the panels: Europan 18, Regensburg. The brief is in `brief/`. How the skills fit together is in [`STUDIO.md`](STUDIO.md).

A skill is a folder with a `SKILL.md`: a short Markdown file of instructions, with a `name` and a `description` at the top. Claude Code reads the descriptions of all skills in the project, and loads a skill when a task fits its description. In this repo every skill lives in `.claude/skills/`, so all of them are active as soon as you open the project.

## Start

1. Fork this repo on GitHub (the Fork button, top right).
2. Ask your agent to clone your fork, open it in VS Code, and start `claude` in it.
3. Copy `examples/regensburg/proposal/` to `proposal/` in the project root. Now you have the site, its data and a placeholder design to test on, before the skills you depend on exist. `proposal/` is never committed.

## Write your skill

Put it in `.claude/skills/<your-skill>/SKILL.md`. Look at the three examples first: `site-kit`, `drawing-graphics` and `figure-ground`. Near the top, one line says which skills yours reads: `Reads: site-kit, massing`. The studio's lead uses that line to decide when your skill runs.

## Hand it in

Ask your agent to make a branch named after your skill, commit, push to your fork, and open a pull request against this repo with the template filled in. Change only your own folder in `.claude/skills/`. Then no two pull requests touch the same file, and nothing conflicts.

Every two days the studio runs on everything merged so far. The results go on the course board: find your part, see what's wrong, improve your skill, push again. Your pull request updates by itself.

## Run the studio

Ask for "a competition entry for the brief in `brief/`". The skill `competition-proposal` runs every other skill and writes `proposal/README.md`: what's done, what failed, what nobody has written yet.
