"""Rules for the design: where the climate of the place asks to do or avoid something, from the layers the other scripts made.

python rules.py --site SITE_DIR --out CLIMATE_DIR [--thresholds thresholds.json]

thresholds.json: the noise limits to use, with their source; the brief's or the country's values go here.
{"day_homes": 55, "day_robust": 65, "night_homes": 45, "source": "..."}
Without it: German planning guide values (DIN 18005: general residential 55/45 dB(A) day/night, commercial 65), said so in the output.
"""
import argparse
from pathlib import Path

import numpy as np
import shapely

from common import Site, read, write_json

DEFAULT = dict(day_homes=55, day_robust=65, night_homes=45,
               source="default guide values of DIN 18005 (Germany): general residential 55/45 dB(A) day/night, commercial 65 dB(A) day; "
                      "replace with the brief's or the country's values")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--thresholds")
    a = ap.parse_args()
    S, out = Site(a.site), Path(a.out)
    th = dict(DEFAULT, **(read(a.thresholds) if a.thresholds else {}))
    site = S.poly
    feats, rules, notes, sources = [], [], [], []

    def rule(kind, topic, text, g, reason):
        g = g.intersection(site) if not g.geom_type.endswith("LineString") else g.intersection(site.buffer(1))
        if g.is_empty:
            return
        feats.append((g, {"kind": kind, "topic": topic, "rule": text, "reason": reason}))
        rules.append(dict(kind=kind, topic=topic, rule=text, reason=reason,
                          area_ha=round(g.area / 1e4, 1) if g.area else None, site_share_pct=round(100 * g.area / site.area, 1) if g.area else None))

    noise = S.layer("noise", out)
    day = [(g, p) for g, p in noise if p["period"] == "day"]
    loud = shapely.union_all([g for g, p in day if p["db_min"] >= th["day_robust"]] or [shapely.Polygon()])
    mid = shapely.union_all([g for g, p in day if th["day_homes"] <= p["db_min"] < th["day_robust"]] or [shapely.Polygon()])
    air = shapely.union_all([g for g, p in S.layer("fresh-air", out) if p["kind"] == "corridor"] or [shapely.Polygon()])
    if day:
        rule("dont", "noise", f"No homes, schools, childcare or playgrounds: {th['day_robust']} dB(A) or more by day. "
             "Noise-robust uses (work, parking, mobility) or a building or landform that shields what lies behind.", loud,
             f"noise.geojson, day >= {th['day_robust']} dB(A)")
        rule("careful", "noise", f"Homes only behind a shielding edge ({th['day_homes']}-{th['day_robust']} dB(A) by day): closed side to the road, "
             "bedrooms and outdoor space on the quiet side. Offices, shops and services fit.", mid,
             f"noise.geojson, day {th['day_homes']}-{th['day_robust']} dB(A)")
        night = [(g, p) for g, p in noise if p["period"] == "night" and p["db_min"] >= th["night_homes"]]
        if night:
            notes.append(f"At night {round(100 * shapely.union_all([g for g, _ in night]).intersection(site).area / site.area)} % of the site is "
                         f"at {th['night_homes']} dB(A) or more: bedrooms face away from the roads there.")
        sources.append(f"Noise limits: {th['source']}")
    if not air.is_empty:
        rule("dont", "fresh air", "Keep the air corridor open: no buildings or high walls across it. Green, sport, water and paths fit.", air,
             "fresh-air.geojson, corridor")
    flows = [(g, p) for g, p in S.layer("fresh-air", out) if p["kind"] == "flow" and g.intersects(site)]
    if flows:
        d = np.radians([p["direction_deg"] for _, p in flows])
        mean = round(float(np.degrees(np.arctan2(np.sin(d).mean(), np.cos(d).mean())) % 360))
        rule("do", "fresh air", f"Run streets, green strips and building rows along the air flow (towards about {mean}°), with gaps between buildings.",
             shapely.union_all([g for g, _ in flows]), "fresh-air.geojson, flow")
    sun = read(out / "sun.json") if (out / "sun.json").exists() else None
    if sun:
        hmax = sun["weather"]["sun_hours_open"]
        dark = shapely.union_all([g for g, p in S.layer("sun-hours", out) if p["hours_max"] <= hmax / 2] or [shapely.Polygon()])
        rule("careful", "sun", "Shaded today, under half the possible sun hours: not for playgrounds, gardens or terraces.", dark,
             "sun-hours.geojson")
        sources += sun["sources"][:1]
    if day or not air.is_empty:
        quiet = site.difference(loud).difference(mid).difference(air) if day else site.difference(air)
        rule("do", "noise", f"Quiet and open to the air (under {th['day_homes']} dB(A) by day): best for homes, schools, childcare and play.", quiet,
             "what no other rule covers")
    wind = read(out / "wind.json") if (out / "wind.json").exists() else None
    if wind:
        notes.append(f"Winter wind mostly from {wind['winter']['prevailing']} ({wind['winter']['prevailing_pct']:.0f} % of hours): "
                     f"shelter squares and play areas on that side.")
        notes.append(f"Summer wind mostly from {wind['summer']['prevailing']}: leave streets and green open towards it for cooling.")
        sources.append(wind["sources"][0])
    S.write_geojson(out / "rules.geojson", feats)
    write_json(out / "rules.json", dict(thresholds=th, rules=rules, notes=notes,
                                       sources=sources + ["Rules made from the climate layers of today; they are constraints, the design decides"]))
    for r in rules:
        print(r["kind"], r["topic"], r["site_share_pct"], "%")
    print(*notes, sep="\n")


if __name__ == "__main__":
    main()
