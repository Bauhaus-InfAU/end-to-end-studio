# End-to-end studio

Skills for architecture and urban design competitions, from the brief to the panels. They come in nine topics: utilities, brief, site, analysis, concept, design, drawings, delivery, and the studio that runs them all. Each topic is a plugin you can install into any project. Run together, they make a whole entry.

This semester the skills are written by the students of AI in Design at Bauhaus-Universität Weimar, one each, and together they answer Europan 18 in Regensburg. How the skills fit together is in [`STUDIO.md`](STUDIO.md), and the flow, round by round, is on [the studio's page](https://bauhaus-infau.github.io/end-to-end-studio/).

## What's where

```
plugins/              the tools: nine topics, one folder per skill
  <topic>/TOPIC.md      what the skills of a topic read and write
  <topic>/skills/<skill>/SKILL.md
competition/          this semester's job: Europan 18, Regensburg
  brief/                the brief as PDF, its Markdown from pdf-to-md, checklist.md from brief-reader
  site/                 the site and its data, from site-kit
  climate/              air, sun, wind and noise, made once by climate, never committed
  references/           the images the drawings take their look from
  proposals/            the runs, never committed
    test/               where you test your skill
    2026-11-02_run-1/   one run of the studio
STUDIO.md             the contract, and who writes which skill
CLAUDE.md             the rules for the agent, and where things are
docs/                 the flow page, and the designs, plans and results of changes to the studio
tests/                checks for the studio's own scripts: python -m pytest tests
```

`plugins/` knows nothing about Europan. Everything that belongs to this one competition is in `competition/`.

## Use it in your own project

In Claude Code:

```
/plugin marketplace add Bauhaus-InfAU/end-to-end-studio
/plugin install drawings@end-to-end-studio
```

Install one topic, or all nine to run the studio. A skill is called by topic and name, such as `/drawings:figure-ground`, and Claude also uses it on its own when a task fits its description. One skill alone works too: copy its folder from `plugins/<topic>/skills/` into your project's `.claude/skills/`.

## Start, as a student

1. Fork this repo on GitHub (the Fork button, top right).
2. Ask your agent to clone your fork, open it in VS Code, and start `claude` in it. Already cloned this repo instead of your fork? Ask your agent: "Point this clone at my fork of end-to-end-studio."
3. The first time, Claude Code asks whether you trust the folder and offers the studio's plugins. Say yes: the nine topics load from the repo itself, and your edits take effect after `/reload-plugins`.
4. Ask your agent to install what's in `requirements.txt`. The skills work in Python and plain files, not in Rhino.
5. Test your skill in `competition/proposals/test/`. The brief and the site are in `competition/` already. For a skill yours reads that doesn't exist yet, ask your agent for a rough stand-in.

## Write your skill

Put it in `plugins/<topic>/skills/<your-skill>/SKILL.md`, in the topic `STUDIO.md` gives it. Read that topic's `TOPIC.md` first, and the two examples: `pdf-to-md` in `utilities` and `site-kit` in `site`. Near the top, one line says which skills yours reads: `Reads: site-kit, massing`. The lead uses it to decide when your skill runs.

Write it so it works anywhere: on another brief, another site, in another project, with other reference images and at other scales. Your skill decides what your part shows. The look comes from `drawing-graphics`, the scales from the brief's checklist, the site from the project's site folder.

Three things keep a run cheap and the same from one run to the next:

- Your skill runs on Sonnet. If it has to judge more than it draws, add `Model: opus` below its `Reads:` line; that costs twice as much.
- Read the brief's `checklist.md` first, and open the brief only at the pages it names.
- Code your skill needs in every run goes in its own `scripts/` folder, and the brief's numbers in a `config.json` that the skill fills from the checklist, each with its page. `massing` shows how. A script never holds a site, a street or a brief's number.

## Hand it in

Ask your agent to make a branch named after your skill, commit only your skill's folder, push it to your fork, and open a pull request against this repo with the template filled in. If the agent can't open the pull request, open your fork on GitHub and press **Compare & pull request**. Change only your own folder. Then no two pull requests touch the same file, and nothing conflicts.

Every two days the studio runs on everything merged so far. The results go on the course board: find your part, see what's wrong, improve your skill, push again to the same branch. Your pull request updates by itself.

## Keep your fork up to date

Before you change your skill, get what others merged: on your fork on GitHub press **Sync fork**, then ask your agent to pull. Your folder is yours alone, so this never conflicts.

## Run the studio

Ask for "a competition entry, label it run-1". `competition-proposal` runs every skill into `competition/proposals/<date>_run-1/` and writes its `README.md`: what's done, what failed, what nobody has written yet. "Redo the massing of run-1 with courtyards" makes a variant; "compare run-1 and courtyards" puts two versions side by side.

How a run works: the lead starts each skill as its own light helper, `studio:studio-helper`, which carries only that skill and the tools to read, write and run code. A skill starts as soon as what its `Reads:` line names exists. The brief's checklist and the climate belong to the project: they are made once, copied into every version, and made again only when the site, the brief or their skill change. A skill runs a second time only when its own `Reads (end):` line says so; the lead never adds a round. What changed and why is in `docs/superpowers/specs/`, the measured costs in `2026-11-02-lean-run-results.md`.

### On a Pro plan

A full run used to cost about $30 at API prices, about three of a Pro plan's 5-hour windows. Started like this, it should fit in one. Open a terminal in the repo and start Claude Code with only the repo's settings and plugins, and none of your own MCP servers:

```
PowerShell:     $env:ENABLE_CLAUDEAI_MCP_SERVERS="false"; claude --model sonnet --setting-sources project,local --strict-mcp-config --permission-mode auto
macOS, Linux:   ENABLE_CLAUDEAI_MCP_SERVERS=false claude --model sonnet --setting-sources project,local --strict-mcp-config --permission-mode auto
```

Your own settings, plugins and permissions are left out for this session only. The lead runs on Sonnet, and every skill runs on Sonnet unless its `Model:` line says otherwise. At the end the lead writes `cost.csv` into the version folder: what each skill cost, in tokens and in dollars. Its total is also in the version's `README.md`. Look there first when you want a run to cost less.
