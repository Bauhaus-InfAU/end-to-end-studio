# Studio

The lead. `competition-proposal` runs every other skill on a brief, in the order their `Reads:` lines give, and keeps each run as a version in `proposals/`. It designs and draws nothing itself.

- Each skill runs as `studio:studio-helper` (in `agents/`), on the model its `Model:` line names, else Sonnet.
- Shared inputs that read only the brief and the site, the checklist and the climate, are made once and copied into each version. `scripts/inputs_key.py` tells when their sources changed and they have to be made again.
- At the end, `scripts/cost.py` writes `cost.csv`: what each skill cost, from the run's own records.
