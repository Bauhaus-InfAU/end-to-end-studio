# Analysis

Skills that measure. Each one measures the site as it is, and runs again on the design (`Reads (end): massing`), with the same method, so the two can be compared.

- Input: the project's site folder (`site.geojson` and its layers), and for the second run `massing/massing.geojson`.
- Output: `metrics.csv` with the columns `measure, value, unit, state, source`, where `state` is `today` or `design`, plus a map of each measure as SVG and PNG, drawn to the studio's standard if there is one.
- `analysis` is the general skill of this topic. Its second run also collects every `metrics.csv` in the proposal folder into one comparison: where the design improves on today, where it doesn't. So its end line reads `Reads (end): massing, every analysis`.
- A new skill here: one more measure, such as an isovist, space syntax, solar access or walking reach. Write `metrics.csv` in the shape above and it shows up in the comparison and on the panels.
