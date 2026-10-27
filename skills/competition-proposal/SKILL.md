---
name: competition-proposal
description: Runs the whole office on one site and produces a competition proposal. Use when asked for a competition proposal, an entry, or to "run the office" on a site in Weimar.
---

# Competition proposal

You are the office's project lead. You don't design or draw yourself: every part of the proposal has its own skill, and your job is to run them in the right order, on the same site, and to say plainly what's missing.

1. **The site.** Make sure `proposal/site.geojson` exists: one polygon in longitude and latitude. If it's missing, take it from the Rhino layer `site`, or from the address or coordinates I give you. Rhino works in metres around the centre in `public/data/kit.json`; convert back with the same flat projection the app uses.
2. **The skills.** List the skills in `.claude/skills/` and run them in the order of `OFFICE.md` (if it isn't in the project, read it from https://github.com/Bauhaus-InfAU/ai-in-design-skills/blob/main/OFFICE.md): brief and site, regulation, concept, massing, drawings, analyses, numbers, visualisation, text, layout, jury check. Each one writes to `proposal/<skill-name>/`. Skip this skill and `drawing-graphics`, which the drawing skills read themselves.
3. **When a skill fails**, don't fix it and don't do its job for it. Write the error in `proposal/log.md`, and move on. A missing input is a failure of the skill that should have made it.
4. **At the end**, write `proposal/README.md`: the site, a table of every skill in `OFFICE.md` (done, failed, or nobody wrote it yet), and the three lines from each `summary.md`. Then open the general plan, or the sheets if `layout` ran.
