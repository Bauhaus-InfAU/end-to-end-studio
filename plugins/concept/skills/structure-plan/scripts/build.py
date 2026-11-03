"""Builds a structure plan from a design file and checks it.

    python build.py <design.py> --site <site folder> --proposal <proposal folder> [--climate <folder>]
                    [--distance 150] [--style style.json]

The design file holds only the plan's decisions, as F.add(...) calls (see design.example.py). It runs with these
names and no others: F (the frame: the site in local metres, its layers, the helpers), Point, LineString, Polygon,
box, unary_union, nearest_points. It must not import or open files itself.

Writes <proposal>/structure-plan/structure-plan.geojson, checks.txt, check-plan.svg and check-plan.png, and prints
the warnings and the checks.
"""
import argparse, os, sys
from pathlib import Path

from shapely.geometry import Point, LineString, Polygon, box
from shapely.ops import unary_union, nearest_points

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frame import Frame
import check

ap = argparse.ArgumentParser(description='Builds a structure plan from a design file and checks it.')
ap.add_argument('design', help='the design file, e.g. <proposal>/structure-plan/design.py')
ap.add_argument('--site', required=True, help='the folder with site.geojson and its layers')
ap.add_argument('--proposal', required=True)
ap.add_argument('--climate', help="the climate folder with rules.geojson (default: the proposal's climate/)")
ap.add_argument('--distance', type=float, default=check.C['distance_m'], help='proximity distance for the checks, m')
ap.add_argument('--style', help="the drawing standard's style.json (default: the proposal's drawing-graphics/)")
A = ap.parse_args()

design = Path(A.design)
if not design.exists():
    sys.exit(f'no design file at {design}')
F = Frame(A.site, check.climate_of(A.proposal, A.climate))
names = {'F': F, 'Point': Point, 'LineString': LineString, 'Polygon': Polygon, 'box': box,
         'unary_union': unary_union, 'nearest_points': nearest_points, '__name__': '__design__'}
exec(compile(design.read_text(encoding='utf-8'), str(design), 'exec'), names)

warnings = F.write(Path(A.proposal) / 'structure-plan' / 'structure-plan.geojson')
for w in warnings:
    print('WARNING:', w)
print(check.run(A.proposal, F, A.distance, A.style))
