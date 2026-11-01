---
name: programme
description: Turns a brief's programme into tables: homes and household mix, residents, and every use with its area, such as housing, commerce, schools, community and shared uses. Use when asked for the programme, the household mix, the number of homes or residents, or the areas of the uses.
---

# Programme

Reads: brief-reader

1. Read the brief checklist written by `brief-reader` in the proposal folder you are told, else the newest one. If it is missing, read the brief's Markdown in the project's `brief/`; if a figure is in neither, ask or say so in `summary.md`.
2. Take from the brief everything it asks to build, and table it:
   - **Homes and households:** the number of homes or the housing floor area, the household mix and unit types, and the residents. Where the brief gives a total but no mix, say so and leave the mix open; never invent shares.
   - **Uses and their areas:** commerce and ground-floor uses, schools and daycares with their capacity and outdoor space, community and sport, and anything else the brief lists, each with its gross floor area and plot.
   - **Shared and productive space:** uses shared by day and night, gardens and urban agriculture, shared amenities, only where the brief asks for them or gives a number.
3. Never invent data: next to every number, its source in the brief (with its page) or the assumption behind it, such as m² per resident. No drawings; text and tables only.
4. Write everything into `programme/` in the proposal folder and nothing outside it:
   - `programme.csv`: `use, area_m2, plot_m2, homes, residents, source`, one row per use, so `massing` can check its floor area against it.
   - `households.csv`: `household, share, homes, source`, if the brief gives a mix.
   - `programme.md`: what the brief asks for in words, and its open questions.
5. Create a `summary.md` of exactly three lines:
   - What you tabled.
   - The one key number that matters (total homes).
   - The one assumption or uncertainty you're highlighting.
