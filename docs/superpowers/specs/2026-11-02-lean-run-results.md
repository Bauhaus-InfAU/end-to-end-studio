# A lean studio run: results

*2026-11-02. Run-4 from commit `01cf893`, the same skills as run-3 plus `brief-reader` (copied from the brief's checklist), `streets` left out. Started from Claude Code with only the repo's settings and plugins (README, "On a Pro plan"), non-interactively, helpers in the foreground. 52 minutes. Spec: `2026-11-02-lean-run-design.md`.*

## Cost

Run-4 cost **$9.01** at API prices against run-3's **$29.69**, 70% less, under the $12 target for one Pro 5-hour window. (The CLI's own count for the session is $8.50.)

| Skill | run-3 (all Opus) | run-4 | run-4 model |
| --- | ---: | ---: | --- |
| lead | $7.15 | $0.40 | sonnet |
| site-section | $3.27 | $0.70 | sonnet |
| structure-plan | $3.11 | $2.21 | opus |
| mobility | $2.24 | $1.28 | sonnet |
| concept-diagrams | $2.23 | $0.15 | sonnet |
| narrative | $2.16 | $0.85 | opus |
| massing | $1.81 | $1.28 | opus |
| climate | $1.66 | $0.45 | sonnet |
| jury | $1.49 | $0.69 | opus |
| isometric | $1.40 | $0.35 | sonnet |
| panel-layout | $1.05 | $0.23 | sonnet |
| programme | $0.76 | $0.11 | sonnet |
| open-space | $0.72 | $0.18 | sonnet |
| perspective | $0.66 | $0.12 | sonnet |
| **total** | **$29.71** | **$9.00** | |

`brief-reader` cost $0.29 once, on 02.11., and is not in run-4: its checklist was copied.

Still the most expensive: `structure-plan` ($2.21, Opus, 58k output tokens), `mobility` ($1.28, 32 steps, 53k output tokens) and `massing` ($1.28, Opus, although it has a script now).

## The quality points

| Point | run-3 | run-4 | Met |
| --- | --- | --- | --- |
| Every run-3 skill ran and left `summary.md` | yes | all ran; `jury/` was never written, and narrative's second `summary.md` was not saved | no, see below |
| Required items on the panels | 8 of 11 (panel-layout's count) | 7 of 13 (against the checklist) | one short |
| The jury gets past admission and round 1 | eliminated in round 2 | eliminated in round 2 (relayed to the lead, not saved) | yes |

**Why the jury's files are missing.** Claude Code refused two writes inside helpers with "Subagents should return findings as text, not write report files": the jury's `report.md` and `summary.md`, and narrative's second-run `summary.md`. Every other helper wrote its files. This run started helpers in the foreground because it was non-interactive; run-3 ran them in the background from an interactive session.

**Why one item fewer.** The 1:1,000 hub plan (detail area 1) came out 660 mm wide, against a panel width of 564 mm, so panel-layout left it off; run-3's was 460 mm and was placed. The 1:3,000 site plan is too wide in both runs (608 and 600 mm).

## What next

- A helper rule: a drawing meant for the panels fits the panel's width from the checklist at its scale, cropped to what the brief asks to show. That fixes both plans.
- The report-file refusal: start run-5 interactively, with helpers in the background as students will, and see whether it happens there.
- The scripts for mobility and structure-plan (plan Tasks 7 and 8) are worth about $1 to $2 more, if needed.
