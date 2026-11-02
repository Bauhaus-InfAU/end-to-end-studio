---
name: brief-reader
description: Reads a competition brief once and writes a checklist of what it asks for, each item with its page: the numbers, the rules, the required drawings and their scales, the panel format, the required content and what the jury looks for. Use when asked to read a brief, for a checklist of a brief, or before other skills need the brief's numbers.
---

# Brief reader

Reads: pdf-to-md

The checklist belongs to the brief, not to one version, so it is written once and reused. If `checklist.md` lies next to the brief's Markdown in the project's `brief/` and is newer than every Markdown there, copy it into `brief-reader/` in the proposal folder you are told, write `summary.md`, and stop.

Otherwise read the brief's Markdown in parts, never all at once: list its headings and page markers (`<!-- page N -->`) with `grep`, then read the pages that hold the task, the programme, the rules, the submission and the jury's criteria. Write `checklist.md` next to the brief, in this order, one line per item, each ending with its source as `(<file> p. N)`:

- `## Numbers`: homes, residents, areas per use, green per resident, phases, and every other figure the design must meet.
- `## Rules`: heights, setbacks, what must stay, what is not wanted.
- `## Drawings and scales`: every drawing asked for, with its scale.
- `## Panels and format`: how many panels, their size and orientation, the texts and their length.
- `## Required content`: a numbered list of every item the brief requires on the panels or in the text, in the brief's words.
- `## What the jury looks for`: the criteria, as the brief states them.
- `## Pages`: each topic above and the pages to open for it, so other skills read only those.

Copy it into `brief-reader/` in the proposal folder. Never invent: what the brief doesn't say is written as "not stated". `summary.md`: three lines, the size of the task in one sentence, the number of required items, and what the brief leaves unclear.
