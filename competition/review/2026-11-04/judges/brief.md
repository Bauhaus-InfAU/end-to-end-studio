# Brief for the judges

You are one of three independent judges. A studio of AI agent skills makes architecture competition entries (urban design, three A1 panels). Its last runs are far from the three winners of the same competition site. A review has listed 18 proposed changes to the studio. Your job is to rate every change for its potential to close that gap, and to rank them. You judge alone: you don't see the other judges' verdicts or the reviewer's own ranking, and you must not look for them.

## What to read

Repo root: `C:\Work\GitHub\end-to-end-studio`. All paths below are relative to it.

1. `competition/review/2026-11-04/gaps.md`: the gaps by kind of drawing (G1 to G11) and their causes in the code (K1 to K18).
2. `competition/review/2026-11-04/changes.md`: the 18 changes (C1 to C18), each with its gaps, causes, where it starts in the code and what it depends on. The order there is by layer, not a ranking.
3. The evidence. Look at all nine sheets in `competition/review/2026-11-04/evidence/` (each puts winners' drawings above ours, by kind). For the whole picture, open at least one full winner board and one of our panels: `competition/references/winners/1_prize_zam-wachsn/board-1.jpg` and `competition/proposals/2026-11-03_run-10/panel-layout/panel-2.png`. More boards are in `competition/references/winners/*/board-N.jpg`, and more of our panels are in `competition/proposals/2026-11-03_run-{8,9,10}/panel-layout/`.
4. The code, to check claims yourself: `STUDIO.md`, `plugins/*/TOPIC.md`, `plugins/*/skills/*/SKILL.md` and their `scripts/`, the lead `plugins/studio/skills/competition-proposal/SKILL.md` and its helper `plugins/studio/agents/studio-helper.md`. Run 10's notes are in `competition/proposals/2026-11-03_run-10/` (`README.md`, `log.md`, `cost.csv`, each skill's `summary.md`). Check the claims of at least the changes you put in your top five and your bottom three. If a claim in `changes.md` or `gaps.md` is wrong, say so.

Don't open: `competition/feedback/`, any `jury/` folder in a run, `docs/`, `plans/`, any folder outside the repo, `competition/review/2026-11-04/report.md`, `competition/review/2026-11-04/my-reading.md`, or any other file in `competition/review/2026-11-04/judges/` besides this brief. Don't search the web or fetch anything. Don't change, create or delete any file: you only read, and you reply.

## The studio's constraints

- About 20 students each own one skill. Every skill must work alone, in any project, on any brief and site. No site, competition or repo path goes into a skill.
- A full run costs about $20 to $30 at API prices (run 10: $21.01) and should fit in one 5-hour window of a Pro plan. Skills run on Sonnet. Only a skill that judges gets `Model: opus`.
- The drawings are made in Python as SVG (shapely, pyproj), with a PNG from a headless browser. There's no Rhino. Perspectives use an image model (Gemini) on a base view drawn from the massing.
- The winners' boards are now in the project as references. No run has had them yet.

## How to rate

For every change, C1 to C18:

- **Gap (0 to 5).** How much of the visible gap to the winners it closes on its own, if done well. 5 means a jury would see a different entry.
- **Unlocks and blocks.** Which other changes it makes possible or multiplies, and which it delays, conflicts with or makes unnecessary. Name them by id.
- **Effort (1 to 5).** 1 is an afternoon of one person with an agent; 5 is weeks of several people.
- **Risk (1 to 5).** 5 is the riskiest. Consider cost per run, breaking other skills or the tests, drawings that misstate the design, and conflicts with the rules above.
- **Potential (0 to 10).** Your overall judgement of what the change is worth, weighing all four.
- **Rank (1 to 18).** 1 is the change to do first. Use every rank once. The rank may differ from the order of potential if order matters (a cheap enabler before a large change).

## What to reply

Reply with this and nothing else, in plain English:

1. A table: `id | gap | effort | risk | potential | rank | one-line reason`.
2. **Dependencies.** The unlock and block relations you see that matter for the order, as short lines (`C9 -> C12: ...`).
3. **Top five.** For each, a paragraph: why, what evidence convinced you (name the image or file and line), and what could go wrong.
4. **Bottom three.** Why each is low.
5. **Corrections.** Any claim in `gaps.md` or `changes.md` you found wrong or overstated, with the file and line that shows it. Also any change you would merge, split or reframe, and any change that is missing.
6. A JSON block at the end, exactly in this shape, with all 18 ids:

```json
{"judge": "<your letter>", "ratings": {"C1": {"gap": 0, "effort": 0, "risk": 0, "potential": 0, "rank": 0}}}
```
