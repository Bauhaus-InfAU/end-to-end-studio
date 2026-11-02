# A lean studio run

*Design, 2026-11-02. Built on `main` of `end-to-end-studio`.*

## Why

In Session 4 (Wed 04.11.2026) every student gets the whole studio and works out how to make their own version better. Most of them are on the 20 euro Claude Pro plan. Today one full run does not fit it:

- Run-3 cost about **$28 to $34** at API prices (lead $7, 17 helpers $27), measured from its transcripts. Run-1 and run-2 cost about $19 and $22.
- A third-party measurement puts Pro at about **$12 per 5-hour window and $155 per week** in API terms (wokey.ai, week of 26.10.2026; Anthropic publishes no figures).
- So one run takes about three windows. A student hits the limit a third of the way in, and can do at most four or five runs a week, with nothing else.

Improving a version means running it several times. If one run doesn't fit, students can't learn from the loop at all.

## Goal

**One full run of the studio fits one Pro 5-hour window: about $12 at API prices, measured, with a result at least as good as run-3.**

"At least as good as run-3" means, on the same Regensburg brief and site:

- every skill that ran in run-3 runs and leaves its `summary.md`
- panel-layout places at least the 8 of the brief's 11 required items that run-3 placed
- the jury gets at least as far as run-3 (past admission and round 1)

## Non-goals

- The `environment` (one 3D model, the web page, the program that runs the stages). It lives on its own branch and picks up what proves itself here.
- New skills, a new look, or a different design method. The output stays what the skills make today.
- The Session 4 teaching material. That is a separate job, once this works.

## Anti-goals

These would make it a failure even if the number comes down:

- Saving tokens by dropping a skill, the jury, the checks a skill makes on its own drawing, or the end texts.
- A skill that stops working alone, in another project, on another brief (`STUDIO.md`, "Every skill works alone"). Nothing about Regensburg goes into a skill or a script.
- A run that only stays cheap because someone watches it and steps in.
- Opening Europan results or entries. `CLAUDE.md`'s rule stays as it is.

## Where the money goes in run-3

From the 17 helper transcripts:

- **A helper starts at 42k tokens before it works.** The skills themselves are 2 to 6k characters. The rest is Claude Code's setup plus every plugin and MCP tool on the computer that runs it (Miro, Chrome, Notion, Rhino, many global skills). Helpers are generic `general-purpose` agents and inherit all of that.
- **Cache writes are about half the cost.** Each new helper builds its context from zero, and grows it with every step.
- **Reading the brief and upstream files:** about 1.1M characters through `sed`, `grep` and `cat`, often 20 to 40k characters at once, mostly the 88k-character brief Markdown. A one-page `Regensburg_EN_1-summary.md` exists already. Skills don't use it, and `brief-reader`, which half the skills list in `Reads:`, was never written.
- **104 images** read to check drawings. Each stays in the context for every later step.
- **About 500k characters of scripts written during the run,** at output prices: drawing, projection and PNG export, written from scratch in every run.
- **Reruns:** narrative, concept-diagrams, site-section and isometric ran twice. Concept-diagrams' second run was added by the lead because massing doesn't read the narrative, so the narrative's second run changed the idea under the diagrams.
- **The lead, $7:** waiting, 34 shell calls to keep the log, rewriting `usage.csv` by hand after a helper deleted it.
- **All of it on Opus 5.5.** No helper used Sonnet or Haiku.

The run took 70 minutes, so time is not the problem. Money is.

## What changes

The levers, in order of expected savings. The amounts are rough estimates from run-3, to be checked by measuring.

1. **A lean helper (about $5 to 6).** The lead starts each skill as a studio helper defined in the `studio` plugin, with only the tools a skill needs (Bash, Read, Write, Edit, Glob, Grep, Skill) and no MCP tools. Target: a helper starts under 15k tokens. It must work on a student's computer, where the plugin is installed through the repo's `.claude/settings.json`.
2. **The right model per skill (about $6 to 8).** Judgment skills run on Opus 5.5: `narrative`, `structure-plan`, `massing`, `jury`. Every other skill runs on Sonnet 5.5. A skill can name its model in one line next to `Reads:` (`Model: opus`). Without that line it runs on Sonnet. Mechanical helpers also run at lower effort if Claude Code allows it per helper.
3. **The brief read once (about $3 to 4).** `brief-reader` is written. It runs once per brief, not once per run, on Sonnet, and writes a short checklist: the numbers, the required drawings and their scales, the panel format, what the jury looks for, each with its page. Every skill reads the checklist first and opens the brief Markdown only for a page it names. `STUDIO.md` says so in "The inputs".
4. **Scripts that live in the skill (about $3 to 5).** For each skill that wrote a script in run-3, the working script goes into its folder (`scripts/`), stripped of anything about this site, and its `SKILL.md` says: run it, then change only what the brief needs. This is ponytail's ladder: what exists gets reused, not rewritten. It should also make results steadier from run to run. Start with the most expensive helpers: site-section, mobility, structure-plan, massing, climate.
5. **No reruns beyond the `Reads (end):` lines (about $5).** The lead never adds a run of its own. `massing` reads `narrative`, so the blocks follow the idea and concept-diagrams doesn't need a second run. Narrative's second run writes the end text and keeps the idea.
6. **A cheaper lead (about $4 to 5).** The lead waits for helpers without polling. A helper replies with its three `summary.md` lines and nothing else. The log is one appended line per event. Usage and cost are written by a script, not by hand (see Measuring).
7. **Fewer images.** A helper looks at one downscaled preview of each drawing it makes, at most twice, and checks sizes and scales in code (the drawing's width in mm against the panel) rather than by eye. `STUDIO.md` gets this as a shared rule.

## Measuring

Ponytail's lesson: measure before claiming, the same task with and without the change.

- **A cost script** in the `competition-proposal` skill reads a run's transcripts (the lead's and every helper's, in `~/.claude/projects/<project>/`) and writes `cost.csv` into the version folder: per skill, tokens by kind (input, cache write, cache read, output), model, steps and API-price dollars. The lead runs it at the end of every run. Students get the same numbers for their own runs. The scratch version used for this design is `C:\Users\egayd\AppData\Local\Temp\claude\C--Work-JOB-InfAU-Teaching-WiSe-26-27-Pandaemonium\89439d49-32ff-4391-bd03-64fd82b14b50\scratchpad\cost.py`.
- **Run-3 is the baseline:** $28 to $34, 17 helpers, the quality points under Goal.
- **Run-4** is the lean run on the same brief and site. It is done when it costs about $12 or less and meets the quality points. A run costs real money on the user's plan, so the builder asks before starting it.
- If run-4 misses, the cost table shows which helper is still expensive. Fix that and run again, at most twice before Session 4.

## Constraints

- Ready and measured by the evening of Tue 03.11.2026, so students can start from it on Wednesday.
- On `main`, in `C:\Work\GitHub\end-to-end-studio`. Commits, no push unless the user asks.
- Classmates keep pushing pull requests this week. Keep each change to their skills as small as possible, so it merges easily.
- Windows, paths with spaces, Python 3.11+, no Rhino.
- Proposals stay out of git.

## Decided

- **By the user:** build on `main`, committing the open work first (done: `62174cf`). Target the 20 euro plan. Use ponytail and Harness² as sources of method. Edit the students' skill folders directly (scripts, a `Model:` line, the `Reads:` line, reading the checklist), with the fewest lines, although `CLAUDE.md` says a pull request touches only its author's folder. Sonnet is the default for every skill that names no model.
- **My calls, to check:**
  - Opus for four skills (`narrative`, `structure-plan`, `massing`, `jury`), Sonnet for the rest.
  - Writing `brief-reader`, which is open in `STUDIO.md`.
  - "As good as run-3" measured by the three points under Goal.
  - The $12 target from a third-party estimate. If the real Pro limit turns out lower, the target moves down.
  - **Run-4 runs the same skills as run-3, plus `brief-reader`,** from one fixed commit, so the comparison with the baseline is fair. `streets` and skills merged this week are left out of the measured run. A second, unmeasured run can include them.
  - **Measured as a student would run it.** The 15k start and the $12 are measured in a clean Claude Code profile with only the repo's own plugins (for example a separate config folder), not with the user's global plugins and MCP servers. The user's global setup is not changed. A run on the user's own computer as it is gets measured too, for comparison, but doesn't count against the target.
  - **The lead runs on Sonnet.** The lead skill switches to Sonnet itself if Claude Code allows that in a skill. Otherwise the run's instructions say to start it with `/model sonnet`. The repo's `.claude/settings.json` gets no default model, because that would change every classmate's other work in the repo.

## Left to the builder

- How the studio helper is defined (agent file, frontmatter), and whether effort can be set per helper.
- Where `brief-reader` writes its checklist so skills find it in any project, and how the lead knows it's done.
- How each script is generalised, and which skills get one beyond the five named.
- The cost script's exact columns, and how it finds a run's transcripts.
- Whether to test levers one by one on a single skill in `competition/proposals/test/` before run-4. Cheap tests on one skill are welcome, a full run each time is not.
