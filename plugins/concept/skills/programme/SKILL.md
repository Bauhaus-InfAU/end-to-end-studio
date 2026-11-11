---
name: programme
description: Turns a brief's programme into tables (homes and household mix, residents, every use with its area) and proposes what the brief leaves open, themes with what they offer and who they are for; once the design exists, gives each neighbourhood its theme. Use when asked for the programme, the household mix, the number of homes or residents, the areas of the uses, the themes or users of a district, or what each neighbourhood offers.
---

# Programme

Reads: brief-reader, narrative, analysis
Reads (end): structure-plan, massing

1. Read the brief checklist written by `brief-reader` in the proposal folder you are told, else the newest one. If it is missing, read the brief's Markdown in the project's `brief/`; if a figure is in neither, ask or say so in `summary.md`.
2. Take from the brief everything it asks to build, and table it:
   - **Homes and households:** the number of homes or the housing floor area, the household mix and unit types, and the residents. Where the brief gives a total but no mix, say so and leave the mix open; never invent shares.
   - **Uses and their areas:** commerce and ground-floor uses, schools and daycares with their capacity and outdoor space, community and sport, and anything else the brief lists, each with its gross floor area and plot.
   - **Shared and productive space:** uses shared by day and night, gardens and urban agriculture, shared amenities, only where the brief asks for them or gives a number.
3. Then propose what the brief leaves open, so the district offers more than homes. A proposal is a decision, not data: next to each, the line of the brief, the narrative (`narrative/narrative.md`) or the analysis (`analysis/summary.md`) it answers, and an area only where the brief gives one.
   - **Themes:** four to six, each two plain words for what happens there (making and trading, learning and sport). For each: what it offers, as the uses a visitor finds, ground floors first; who it is for; and the kind of place it belongs to (the main centre, a local centre, the loud edge, the green edge, beside the neighbours), since the neighbourhoods aren't drawn yet. Take them from the narrative's idea and from what the analysis finds missing around the site. Every use the brief asks for belongs to one theme.
   - **Users:** the groups the brief names or its housing types imply, each with the kind of home it needs and what it needs near home. No invented persons, names or shares.
4. Never invent data: next to every number, its source in the brief (with its page) or the assumption behind it, such as m² per resident. No drawings; text and tables only.
5. Write everything into `programme/` in the proposal folder and nothing outside it:
   - `programme.csv`: `use, area_m2, plot_m2, homes, residents, source`, one row per use the brief asks for and no proposal, so `massing` can check its floor area against it.
   - `households.csv`: `household, share, homes, source`, if the brief gives a mix.
   - `themes.csv`: `theme, offers, users, place, answers`, one row per theme.
   - `users.csv`: `user, home, needs, source`, one row per group.
   - `programme.md`: what the brief asks for in words, the themes and why, and the open questions.
6. **Second run**, once `structure-plan/` and `massing/` exist: give each new neighbourhood and each centre of the structure plan one theme, the one whose `place` and offers come closest to where it lies and to the uses the massing put there, and write `zones.csv`: `zone, theme, ground_floor, users`, the zone by its name in the structure plan, the ground floors those of the theme's offers the massing's ground floors there can hold. Leave out an existing area the design doesn't build on. Change no other file but `summary.md`, which names a theme no zone takes, a zone no theme fits, and a zone whose ground floors in the massing don't fit its theme.
7. Create a `summary.md` of exactly three lines:
   - What you tabled and proposed (after the second run: how many zones have a theme).
   - The one key number that matters (total homes).
   - The one assumption or uncertainty you're highlighting.
