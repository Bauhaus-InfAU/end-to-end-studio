# End-to-end studio

This repo is an architecture studio made of skills. Together they answer one competition, from the brief to the panels: Europan 18, Regensburg. The brief is in `brief/` (`Regensburg_EN_1.pdf`, text in `Regensburg_EN_1.md`). Each skill is one person's part, in `.claude/skills/<name>/SKILL.md`. How they fit together is in `STUDIO.md`: read it before you write or run a skill.

I study architecture or design and don't write code. Explain each step in a sentence or two of plain words. After a change, say which files you changed and what I should look at.

## The competition is closed

Europan 18 has been judged, and its results are published. Never search for, open or use the results, the jury report, or any entry submitted to it, for this site or any other. Don't fetch anything from europan.de: the brief you need is already in `brief/`. If a search or a page shows you an entry or a result anyway, stop reading it, don't use anything from it, and write in `proposal/log.md` that you saw it and where. The point is to find our own answer.

## Skills

- A skill works on whatever site and brief are in the project. Never write a site, a layer name or a path of your own into it.
- It reads `proposal/site.geojson`, the site data in `proposal/site-kit/`, and whatever earlier skills wrote, as `STUDIO.md` lists it. It writes only to `proposal/<its-name>/`, and always leaves a `summary.md` of three lines there.
- Never invent data. Every number has its source or its assumption next to it.
- When I ask you to change a skill, change the fewest lines that fix what I didn't like, and tell me which. Keep it short. If a line no longer changes the result, suggest deleting it.
- To compare, run the same request once without the skill ("don't use any skill") and once with it, and save both results side by side.
- `proposal/` is not committed. A pull request changes only the author's own folder in `.claude/skills/`.

## Keys

Keys live in `.env` and nowhere else: not in a skill, not in a commit.
