---
name: general-plan
description: Draws the general plan (site plan at 1:1000) of a design in its city context. Use when asked for a site plan, general plan, Lageplan, or the general-plan part of a competition proposal.
---

# General plan

Read `drawing-graphics` first. Our general plan is a Schwarzplan, and it answers one question for the jury: how does the new building sit in the city? Every existing building is solid black, all open space is white, and the new building is the only colour on the sheet, solid red `#c8102e`. Nothing grey, no green, no beige. Where our drawing departs from `drawing-graphics`, this file wins.

Inputs: the site in `proposal/site.geojson`, the design in `proposal/massing/` (footprints with floors), the city kit in `public/data/`. Output: `proposal/general-plan/general-plan.svg`, A3 landscape, 1:1000, north up, plus a `summary.md` of three lines.

- Frame: the site in the middle, the city around it cut cleanly at the frame, with a 15 mm white margin all round.
- Existing buildings black, no outline. Leave out any that stand inside the site; the design replaces them.
- The new buildings red, with their floors in white Roman numerals (IV, VI), 2.5 mm. Streets and courtyards inside the design stay white.
- No street network, no plot lines, no trees outside the site, no legend, no figures. Inside the site, trees as red dots 1.5 mm across, no fill around them.
- The site boundary as a thin black dashed line, 0.25 mm.
- Bottom left, in one line: GENERAL PLAN 1:1000, then the place name. Bottom right: a scale bar 0 to 50 m and a plain N with a short line. Attribution in hairline text under the title.
