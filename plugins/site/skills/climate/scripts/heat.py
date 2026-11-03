"""Heat island, simply: how much each place heats up, from what covers the ground (OSM land use in the site folder).

python heat.py --site SITE_DIR --out CLIMATE_DIR [--buildings FILE] [--cell 10] [--radius 50] [--margin 300]

Each cell gets the surface on top: roof, sealed road, built-up land without mapped green, bare ground, open green,
trees, water. A heat index from 0 (cool) to 5 (hot) is the average of the surfaces within --radius, since a place is as
hot as its surroundings. It is a relative index, not a temperature. Land without a tag in the data is its own class.
"""
import argparse
from pathlib import Path

import numpy as np
import shapely

from common import Site, bands, grid, write_json

# surface: (heat score, words); drawn and counted in this order, the first that covers a cell wins
SURFACES = [("roof", 5, "Roofs"), ("road", 4.5, "Sealed roads and squares"), ("water", 0, "Water"), ("trees", 1, "Trees, wood, scrub"),
            ("green", 2, "Open green: grass, meadow, park, fields"), ("bare", 3, "Bare or mixed: construction, yards, rail land"),
            ("built", 3.5, "Built-up land without mapped green"), ("unknown", None, "No land-use data")]
LANDUSE = {"trees": {"forest", "natural:wood", "wood", "natural:scrub", "scrub", "orchard"},
           "green": {"grass", "meadow", "farmland", "leisure:park", "park", "leisure:playground", "leisure:pitch", "allotments", "cemetery",
                     "natural:grassland", "grassland", "village_green", "recreation_ground", "leisure:garden", "natural:heath", "vineyard"},
           "water": {"natural:water", "water", "basin", "reservoir", "natural:wetland"},
           "bare": {"construction", "brownfield", "quarry", "landfill", "farmyard", "railway", "greenfield", "leisure:sports_centre"},
           "built": {"residential", "commercial", "retail", "industrial", "garages", "military", "education", "institutional"}}
ROAD_WIDTH = {"motorway": 20, "trunk": 14, "primary": 12, "secondary": 10, "tertiary": 8, "unclassified": 6, "residential": 6,
              "living_street": 5, "service": 4, "pedestrian": 6, "motorway_link": 7, "trunk_link": 7, "primary_link": 7,
              "secondary_link": 6, "tertiary_link": 6}  # m, typical; paths, tracks and footways are left unsealed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--buildings")
    ap.add_argument("--cell", type=float, default=10)
    ap.add_argument("--radius", type=float, default=50)
    ap.add_argument("--margin", type=float, default=300)
    a = ap.parse_args()
    S, out = Site(a.site, a.buildings), Path(a.out)
    zone = S.poly.buffer(a.margin)
    G, _, _, _ = S.buildings(zone)
    geom = {"roof": shapely.union_all(G) if len(G) else shapely.Polygon()}
    geom["road"] = shapely.union_all([g.buffer(ROAD_WIDTH[p["highway"]] / 2, cap_style="flat") for g, p in S.layer("streets")
                                      if p.get("highway") in ROAD_WIDTH and g.intersects(zone)] or [shapely.Polygon()])
    plots = S.layer("plots")
    for k in ("water", "trees", "green", "bare", "built"):
        geom[k] = shapely.union_all([g for g, p in plots if str(p.get("landuse")) in LANDUSE[k]] or [shapely.Polygon()])
    geom["water"] = shapely.union_all([geom["water"]] + [g if g.geom_type.endswith("Polygon") else g.buffer(3) for g, _ in S.layer("water")])

    xs, ys = grid(zone.buffer(a.radius), a.cell)
    pts = shapely.points(xs, ys)
    cls = np.full(len(xs), len(SURFACES) - 1)
    for i in range(len(SURFACES) - 2, -1, -1):  # paint from the bottom up, so the first in the list ends on top
        cls[shapely.contains(geom[SURFACES[i][0]], pts)] = i
    score = np.array([s[1] if s[1] is not None else np.nan for s in SURFACES])[cls]

    # neighbourhood average over cells with known surface
    n = int(round(a.radius / a.cell))
    ix = np.round((xs - xs.min()) / a.cell).astype(int)
    iy = np.round((ys - ys.min()) / a.cell).astype(int)
    V, C = np.zeros((iy.max() + 1, ix.max() + 1)), np.zeros((iy.max() + 1, ix.max() + 1))
    known = ~np.isnan(score)
    V[iy[known], ix[known]] = score[known]
    C[iy[known], ix[known]] = 1
    disk = [(dy, dx) for dy in range(-n, n + 1) for dx in range(-n, n + 1) if dx * dx + dy * dy <= n * n]
    pv, pc = np.pad(V, n), np.pad(C, n)
    sv, sc = np.zeros_like(V), np.zeros_like(C)
    for dy, dx in disk:
        sv += pv[n + dy:n + dy + V.shape[0], n + dx:n + dx + V.shape[1]]
        sc += pc[n + dy:n + dy + V.shape[0], n + dx:n + dx + V.shape[1]]
    idx = np.where(sc[iy, ix] >= len(disk) / 3, sv[iy, ix] / np.maximum(sc[iy, ix], 1), np.nan)

    clip = zone
    feats = []
    words = ["cool", "mild", "warm", "hot", "very hot"]
    for (lo, hi, g), w in zip(bands(xs, ys, np.nan_to_num(idx, nan=-1), a.cell, [0, 1.5, 2.5, 3.25, 4, 5.1], clip), words):
        feats.append((g, {"kind": "index", "index_min": lo, "index_max": min(hi, 5), "label": f"{w} (index {lo:g}-{min(hi, 5):g})"}))
    unknown = shapely.union_all(shapely.box(xs - a.cell / 2, ys - a.cell / 2, xs + a.cell / 2, ys + a.cell / 2)[np.isnan(idx)]).intersection(clip)
    if not unknown.is_empty:
        feats.append((unknown.simplify(a.cell / 4), {"kind": "unknown", "label": "Too little land-use data to say"}))
    S.write_geojson(out / "heat.geojson", feats)

    in_site = shapely.contains(S.poly, pts)
    share = {SURFACES[i][0]: round(100 * float((cls[in_site] == i).mean()), 1) for i in range(len(SURFACES))}
    hot = round(100 * float((idx[in_site] >= 3.25).mean()), 1)
    write_json(out / "heat.json", dict(
        surface_share_of_site_pct=share, sealed_pct=round(share["roof"] + share["road"], 1), hot_pct=hot,
        cool_pct=round(100 * float((idx[in_site] < 1.5).mean()), 1),
        sources=["Surfaces: the site folder's buildings, streets (sealed width by road type, typical values), plots (OSM land use) and water",
                 f"Heat index: score per surface (roof 5, road 4.5, built-up 3.5, bare 3, green 2, trees 1, water 0), averaged within {a.radius:g} m; "
                 "relative, not a temperature, no weather or materials"]))
    print("surfaces %", share, "hot %", hot)


if __name__ == "__main__":
    main()
