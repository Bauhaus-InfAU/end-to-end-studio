"""Maps of each measure, from layers_<state>.geojson that measure.py wrote.

    python draw.py --proposal <proposal folder> --site <site folder> --config <proposal>/analysis/config.json --state today|design

Look from <proposal>/drawing-graphics/style.json if it exists, else black lines on white with greys.
Writes <measure>_<state>.svg and .png into <proposal>/analysis/.
"""
import argparse, json, os, sys
from shapely.geometry import shape, box
from shapely.ops import unary_union
sys.path.insert(0, os.path.dirname(__file__))
from common import read_config, load, projector, credit, shot

A = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
A.add_argument('--proposal', required=True)
A.add_argument('--site', required=True)
A.add_argument('--config', required=True)
A.add_argument('--state', choices=['today', 'design'], required=True)
ARGS = A.parse_args()
OUT = os.path.join(ARGS.proposal, 'analysis')
CFG, SRC = read_config(ARGS.config, ['map_scale'])
SCALE = float(CFG['map_scale'])
TO_M, _ = projector(ARGS.site, CFG.get('epsg'))
CREDIT = credit(ARGS.site)

S = {'paper': '#ffffff', 'ink': '#1a1a1a', 'accent': '#1a1a1a', 'context': '#ebebeb', 'building': '#5a5a5a',
     'street': '#ffffff', 'path': '#bdbdbd', 'park': '#cccccc', 'kept': '#7a7a7a', 'grove': '#a3a3a3', 'meadow': '#f4f4f4',
     'water': '#dadada', 'font': 'Arial, sans-serif', 'thin': 0.13, 'mid': 0.25, 'thick': 0.5, 'text': 3.2, 'title': 5.6}
sp = os.path.join(ARGS.proposal, 'drawing-graphics', 'style.json')
if os.path.exists(sp):
    S.update({k: v for k, v in json.load(open(sp, encoding='utf8')).items() if v is not None})
MM = SCALE / 1000          # metres of ground per millimetre of paper
TXT = max(float(S['text']), 3.2) * MM   # never under 3.2 mm printed (12 px)

F = [(f['properties'], TO_M(shape(f['geometry']))) for f in load(os.path.join(OUT, f'layers_{ARGS.state}.geojson'))]
if not F:
    sys.exit(f'no layers_{ARGS.state}.geojson: run measure.py first')
SITE = next(g for p, g in F if p['layer'] == 'site')
X0, Y0, X1, Y1 = SITE.bounds
PAD = 150
X0, Y0, X1, Y1 = X0 - PAD, Y0 - PAD, X1 + PAD, Y1 + PAD
HEAD, FOOT = 16 * MM, 40 * MM
W, H = X1 - X0, Y1 - Y0 + HEAD + FOOT
FRAME = box(X0, Y0, X1, Y1)
CTX_B = [g for p, g in ((p, TO_M(shape(f['geometry']))) for f in load(os.path.join(ARGS.site, 'buildings.geojson')) for p in [f['properties']])
         if g.intersects(FRAME) and not SITE.contains(g.representative_point())]
CTX_S = [g for f in load(os.path.join(ARGS.site, 'streets.geojson')) for g in [TO_M(shape(f['geometry']))] if g.intersects(FRAME)]


def P(x, y): return x - X0, Y1 - y + HEAD


def d(g):
    out = []
    for q in getattr(g, 'geoms', [g]):
        if q.geom_type == 'Polygon':
            for r in [q.exterior, *q.interiors]:
                out.append('M' + 'L'.join('%.1f,%.1f' % P(*c) for c in r.coords) + 'Z')
        elif q.geom_type == 'LineString':
            out.append('M' + 'L'.join('%.1f,%.1f' % P(*c) for c in q.coords))
        elif q.geom_type in ('MultiPolygon', 'MultiLineString', 'GeometryCollection'):
            out.append(d(q))
    return ''.join(out)


def path(g, fill='none', stroke='none', w=0.0, extra=''):
    return f'<path d="{d(g)}" fill="{fill}" stroke="{stroke}" stroke-width="{w * MM:.2f}" fill-rule="evenodd" {extra}/>' if not g.is_empty else ''


def text(x, y, s, size=None, anchor='start', weight='normal'):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{(size or TXT):.1f}" text-anchor="{anchor}" font-weight="{weight}" '
            f'fill="{S["ink"]}">{s}</text>')


def drawing(name, title, layers, legend, note='', outline=True):
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W / MM:.0f}mm" height="{H / MM:.0f}mm" viewBox="0 0 {W:.0f} {H:.0f}" '
         f'font-family="{S["font"]}"><rect width="{W:.0f}" height="{H:.0f}" fill="{S["paper"]}"/>']
    o += [path(g, stroke=S['path'], w=S['thin']) for g in CTX_S]
    o.append(path(unary_union(CTX_B), fill=S['context'])) if CTX_B else None
    o += layers
    if outline:
        o.append(path(SITE, stroke=S['ink'], w=S['thick'], extra='stroke-dasharray="%.0f %.0f"' % (6 * MM, 2 * MM)))
    o.append(text(4 * MM, 10 * MM, title, size=float(S['title']) * MM, weight='bold'))
    # legend
    lx, ly = 4 * MM, Y1 - Y0 + HEAD + 8 * MM
    for i, (fill, stroke, label) in enumerate(legend):
        x, y = lx + (i % 3) * 75 * MM, ly + (i // 3) * 7 * MM
        o.append(f'<rect x="{x:.0f}" y="{y - 3.5 * MM:.0f}" width="{6 * MM:.0f}" height="{4 * MM:.0f}" fill="{fill}" stroke="{stroke}" stroke-width="{S["mid"] * MM:.1f}"/>')
        o.append(text(x + 8 * MM, y, label))
    # scale bar and north
    step = 100
    bx, by = W - 4 * step - 40 * MM, ly + 14 * MM
    for k in range(4):
        o.append(f'<rect x="{bx + k * step:.0f}" y="{by:.0f}" width="{step}" height="{1.5 * MM:.1f}" fill="{S["ink"] if k % 2 == 0 else S["paper"]}" stroke="{S["ink"]}" stroke-width="{S["thin"] * MM:.1f}"/>')
    o += [text(bx, by - 2 * MM, '0'), text(bx + 4 * step, by - 2 * MM, '400 m', anchor='middle'), text(bx + 4 * step + 15 * MM, by + 1.5 * MM, f'1:{SCALE:,.0f}')]
    nx_, ny_ = W - 12 * MM, 12 * MM
    o.append(f'<path d="M{nx_:.0f},{ny_ - 8 * MM:.0f}L{nx_ + 3 * MM:.0f},{ny_:.0f}L{nx_ - 3 * MM:.0f},{ny_:.0f}Z" fill="{S["ink"]}"/>')
    o.append(text(nx_, ny_ + 5 * MM, 'N', anchor='middle'))
    o.append(text(4 * MM, H - 4 * MM, ' '.join(x for x in [note, CREDIT] if x)))
    o.append('</svg>')
    svg = os.path.join(OUT, f'{name}_{ARGS.state}.svg')
    open(svg, 'w', encoding='utf8').write('\n'.join(x for x in o if x))
    ok = shot(svg, svg[:-4] + '.png', int(W / MM * 3), int(H / MM * 3))
    print(svg, '' if ok else '(no Chrome or Edge: no PNG)')


cover = [(p, g) for p, g in F if p['layer'] == 'cover']
SEAL = {'fully': S['ink'], 'partly': S['path'], 'unsealed': S['paper']}
GREEN = {'wooded': S['grove'], 'open green': S['park'], 'farmland': S['meadow']}


def cover_fill(c):
    if c == 'building': return S['building']
    if c in ('street', 'square', 'path', 'railway') or c.startswith('design: street') or c.startswith('design: path'): return S['street']
    if c == 'water': return S['water']
    return None


# uses: buildings, streets, water and green as fills; every other use in grey, labelled where it is large
lay, labels = [], []
for p, g in cover:
    fill = cover_fill(p['class']) or GREEN.get(p.get('green')) or S['paper']
    lay.append(path(g, fill=fill, stroke=S['path'], w=S['thin']))
    if g.area > 15000 and p['class'] not in ('street', 'path', 'building'):
        rp = g.representative_point()
        labels.append(text(*P(rp.x, rp.y), p['class'].replace('leisure:', '').replace('natural:', '').replace('design: ', ''), anchor='middle'))
drawing('uses', 'Land uses' + (' with the design' if ARGS.state == 'design' else ' today'), lay + labels,
        [(S['building'], 'none', 'buildings'), (S['street'], S['path'], 'streets, squares, paths, rail'), (S['water'], 'none', 'water'),
         (S['grove'], 'none', 'woods, scrub'), (S['park'], 'none', 'open green'), (S['meadow'], 'none', 'farmland'),
         (S['paper'], S['path'], 'other uses, named where large')], 'From the site layers' + (' and the massing.' if ARGS.state == 'design' else '.'))

drawing('sealing', 'Sealed ground' + (' with the design' if ARGS.state == 'design' else ' today'),
        [path(g, fill=SEAL.get(p['sealing'], S['paper']), stroke=S['path'], w=S['thin']) for p, g in cover],
        [(S['ink'], 'none', 'fully sealed'), (S['path'], 'none', 'partly sealed'), (S['paper'], S['ink'], 'unsealed')],
        'Classes per land use: ' + SRC.get('sealing', ''))

drawing('green', 'Green' + (' with the design' if ARGS.state == 'design' else ' today'),
        [path(g, fill=GREEN[p['green']]) for p, g in cover if p.get('green') in GREEN],
        [(S['grove'], 'none', 'woods, scrub'), (S['park'], 'none', 'open green'), (S['meadow'], 'none', 'farmland')])

EDGE = {'rail': (S['ink'], '0'), 'main road': (S['ink'], '%.0f %.0f' % (3 * MM, 1.5 * MM)), 'water': (S['water'], '0'),
        'built': (S['building'], '0'), 'open': (S['path'], '0')}
lay = [path(g, stroke=EDGE[p['class']][0], w=2.5, extra=f'stroke-dasharray="{EDGE[p["class"]][1]}"')
       for p, g in F if p['layer'] == 'edge']
lay += [f'<circle cx="{P(g.x, g.y)[0]:.0f}" cy="{P(g.x, g.y)[1]:.0f}" r="{2 * MM:.0f}" fill="{S["accent"]}" stroke="{S["paper"]}" stroke-width="{0.5 * MM:.1f}"/>'
        for p, g in F if p['layer'] == 'crossing']
drawing('edges', 'Edges and crossings' + (' with the design' if ARGS.state == 'design' else ' today'), lay,
        [(EDGE[k][0], 'none', k) for k in EDGE] + [(S['accent'], 'none', 'crossing for people on foot')],
        'What lies within 30 m outside the boundary.', outline=False)

reach = [(p, g) for p, g in F if p['layer'] == 'reach']
for dest in sorted({p['dest'] for p, g in reach}):
    rs = sorted({p['radius'] for p, g in reach if p['dest'] == dest}, reverse=True)
    tones = [S['meadow'], S['park'], S['grove']][-len(rs):] if len(rs) <= 3 else [S['park']] * len(rs)
    lay = [path(g, fill=t) for r, t in zip(rs, tones) for p, g in reach if p['dest'] == dest and p['radius'] == r]
    drawing(f'reach-{dest.replace(" ", "-")}', f'Walking reach to {dest}' + (' with the design' if ARGS.state == 'design' else ' today'), lay,
            [(t, 'none', f'within {r} m on foot') for r, t in zip(rs, tones)], f'Along walkable streets and paths, {CFG.get("walk_side_m")} m either side.')

if ARGS.state == 'today':
    K = [(p, TO_M(shape(f['geometry']))) for f in load(os.path.join(OUT, 'keep.geojson')) for p in [f['properties']]]
    kinds = list(dict.fromkeys(p['what'] for p, g in K))
    tones = [S['building'], S['water'], S['grove'], S['kept'], S['park']]
    drawing('keep', 'What must stay', [path(g, fill=tones[kinds.index(p['what']) % len(tones)], stroke=S['ink'], w=S['thin']) for p, g in K],
            [(tones[i % len(tones)], S['ink'], k) for i, k in enumerate(kinds)], 'Only what the site layers show; see summary.md for the rest.')
