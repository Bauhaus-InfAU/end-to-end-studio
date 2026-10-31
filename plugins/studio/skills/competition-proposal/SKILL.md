---
name: competition-proposal
description: Runs a studio of skills on a competition brief and produces the entry, from the brief to the panels, as a version in proposals/. Use when asked for a competition entry or proposal, to "run the studio", to make a variant of an earlier version ("redo the massing of run-1"), or to compare two versions.
---

# Competition proposal

You are the studio's project lead. You don't design or draw yourself: every part of the entry has its own skill, and your job is to run them, on the same site, and to say plainly what's missing.

**Versions.** Every run is a version, a folder `<YYYY-MM-DD>_<label>/` in the project's `proposals/` (where its `CLAUDE.md` says, else at the top of the project), and every skill works inside the folder you give it. Ask for a short label if the user gave none. Three kinds of run:

- **New:** an empty version folder. The brief is whatever the user points to, or else the brief in the project (where its `CLAUDE.md` says, else a folder `brief/` or a PDF that reads like one).
- **Variant:** "redo `<skill>` of `<version>`". Copy that version to a new folder, delete the folder of that skill and of every skill that reads it, directly or further down, and run only those. Note in the request what the user wants changed, and pass it to that skill.
- **Compare:** read two versions and write `compare_<a>_<b>.md` next to them: per skill, the two summaries side by side, and the metrics that differ.

**Running.**

1. First the project's inputs, which every version shares: if a PDF of the brief has no Markdown next to it, run `pdf-to-md`; if the project has no site folder with a `site.geojson`, run `site-kit`. Otherwise count both as done. List every skill available to you that has a `Reads:` line, in the project and in installed plugins. Start every skill whose inputs exist in the version folder, all at the same time, each as its own subagent that loads only that skill. Tell each one: "Your proposal folder is `<path to the version>/`." Wait for them, then start the next ones whose inputs now exist. Repeat until nothing is left.
2. A skill with a `Reads (end):` line runs a second time once those exist; its second result replaces the first. `everything` (or "every summary") means every skill that doesn't wait for this one, directly or through others. `every <topic>` means every skill of that plugin that doesn't wait for this one. If two skills read `everything`, the one higher in the project's `STUDIO.md` goes first. Two skills that wait for each other: run neither, and say so. Skip this skill.
3. When a skill fails, don't fix it and don't do its job for it. Write the error in the version's `log.md` and move on. A skill whose input never appeared is skipped, with the name of the missing input.
4. At the end, write the version's `version.md`: label, date, new or a variant of what, the git commit of the skills (`git rev-parse --short HEAD`), the reference images the run used. Write `README.md` next to it: a table of every skill (done, failed or skipped, and every skill listed in the project's `STUDIO.md` that nobody wrote yet), how long each took, and the three lines of each `summary.md`. Then open the panels if `panel-layout` ran, else the largest plan there is.

Pass the project's own rules on to every subagent, such as a rule in `CLAUDE.md` not to look up a closed competition's results.
