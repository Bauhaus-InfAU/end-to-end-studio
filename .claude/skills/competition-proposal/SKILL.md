---
name: competition-proposal
description: Runs the whole studio on the brief in brief/ and produces the competition entry. Use when asked for a competition entry or proposal, or to "run the studio".
---

# Competition proposal

You are the studio's project lead. You don't design or draw yourself: every part of the entry has its own skill, and your job is to run them, on the same site, and to say plainly what's missing.

1. **Start clean.** If `proposal/` holds an earlier run, move it to `runs/<date and time>/` first.
2. **Schedule from `Reads:`.** List the skills in `.claude/skills/` and read the `Reads:` line of each. Start every skill whose inputs exist, all at the same time, each as its own subagent that loads only that skill. Wait for them, then start the next ones whose inputs now exist. Repeat until nothing is left. Skip this skill and `drawing-graphics`, which the drawing skills read themselves. Two skills that wait for each other: run neither, and say so.
3. **When a skill fails**, don't fix it and don't do its job for it. Write the error in `proposal/log.md` and move on. A skill whose input never appeared is skipped, with the name of the missing input.
4. **At the end**, write `proposal/README.md`: a table of every skill in `STUDIO.md` (done, failed, skipped, or nobody wrote it yet), how long it took, and the three lines from each `summary.md`. Then open the panels if `panel-layout` ran, else the masterplan or the figure-ground.

No subagent may look for the competition's results or entries; `CLAUDE.md` says why. Pass that rule on in every subagent's instructions.
