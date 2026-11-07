"""The figure-ground plan of a district in its city: building footprints as flat tones on white, nothing else.

    python figure_ground.py --proposal <proposal folder> --site <site folder>
                            [--style <style.json>] [--scale N] [--fade-m 500] [--pad-m 500] [--quarter-m 30]
                            [--wall-m 30 2] [--gap-m 0.5] [--title "Figure-ground"]

Reads <site>/site.geojson and <site>/buildings.geojson, and <proposal>/massing/massing.geojson if it exists: the
massing owns the site, so the site's own buildings inside the boundary are replaced by the massing's (its kept ones,
`existing: true`, and its new ones). Tones by style key: the new buildings `ink`, existing quarters (buildings under --quarter-m
apart) that reach within --fade-m of the site `building`, quarters further out `existing`, the paper `paper`; text in `ink` at `text` mm (never under
3.2), lines at `thin` mm, in `font`. The style is --style, else <proposal>/drawing-graphics/style.json, else
drawing-graphics' base.json next to this skill, else black and greys.

Size, scale and centre: the panels' frame for a figure-ground (<proposal>/panel-layout/layout-plan.json, else
layout.json: the item whose file is named figure-ground..., its `scale`, `frame` w and h in mm and an optional
`centre` [lon, lat]); else --scale, else the figure-ground scale in a brief-reader checklist.md (the proposal's, or
next to the site folder), with the site and --pad-m around it. The plan fills the frame and is centred on
the new buildings (else the site); where the site data is smaller than the frame, the drawing is cut to the data
and summary.md says by how much, so no blank paper is printed.

Writes <proposal>/figure-ground/figure-ground_1-<scale>.svg and .png and summary.md.
"""
import argparse, json, math, os, re, shutil, subprocess
from pathlib import Path
from xml.sax.saxutils import escape
from shapely.geometry import shape, box, Point
from shapely.ops import transform, unary_union
from shapely.strtree import STRtree
import pyproj

FALLBACK = {'paper': '#ffffff', 'ink': '#1a1a1a', 'building': '#9a9a9a', 'existing': '#cfcfcf',
            'font': 'Arial, Helvetica, sans-serif', 'text': 3.2, 'thin': 0.13}
TEXT_FLOOR = 3.2      # mm on paper, the studio's floor for any text
PX_PER_MM = 8         # PNG resolution

A = argparse.ArgumentParser(description='The figure-ground plan of a district in its city.')
A.add_argument('--proposal', required=True)
A.add_argument('--site', required=True, help='the folder with site.geojson and buildings.geojson')
A.add_argument('--style')
A.add_argument('--scale', type=int, help="the brief's scale, used when the panels' plan has no frame for it")
A.add_argument('--fade-m', type=float, default=500, help='existing quarters further than this from the site are lighter')
A.add_argument('--pad-m', type=float, default=500, help='ground around the site without a frame, metres')
A.add_argument('--quarter-m', type=float, default=30, help='buildings closer than this form one quarter, which takes one tone')
A.add_argument('--wall-m', type=float, nargs=2, default=(30, 2.0), metavar=('LONG', 'THIN'),
               help='a footprint longer than LONG and on average thinner than THIN is a wall (noise barrier), left out')
A.add_argument('--gap-m', type=float, default=0.5, help='gaps narrower than this between two footprints are shared walls, closed')
A.add_argument('--title', default='Figure-ground')
ARGS = A.parse_args()
GAP_CLOSE, CLUSTER, WALL = ARGS.gap_m, ARGS.quarter_m, tuple(ARGS.wall_m)
RUN, SITE = Path(ARGS.proposal), Path(ARGS.site)
OUT = RUN / 'figure-ground'
OUT.mkdir(parents=True, exist_ok=True)

# the look
S = dict(FALLBACK)
for p in [ARGS.style, RUN / 'drawing-graphics/style.json', Path(__file__).resolve().parents[2] / 'drawing-graphics/base.json']:
    if p and Path(p).exists():
        S.update(json.loads(Path(p).read_text(encoding='utf-8')))
        break
T = max(TEXT_FLOOR, float(S.get('text') or 0))
FONT = escape(str(S['font']), {'"': "'"})


def features(path):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8'))['features'] if path.exists() else []


site_ll = shape(features(SITE / 'site.geojson')[0]['geometry'])
EPSG = (32600 if site_ll.centroid.y >= 0 else 32700) + int((site_ll.centroid.x + 180) // 6) + 1
TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
TO_LL = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform
site = transform(TO_M, site_ll)

def is_wall(g):
    r = list(g.minimum_rotated_rectangle.exterior.coords)
    long = max(math.dist(r[0], r[1]), math.dist(r[1], r[2]))
    return long > WALL[0] and g.area / long < WALL[1]


# the buildings: the site's own, and the massing's on the site; walls modelled as buildings are left out
kit = [transform(TO_M, shape(f['geometry'])) for f in features(SITE / 'buildings.geojson')]
if not kit:
    raise SystemExit('no buildings.geojson in %s: the figure-ground needs the existing buildings' % SITE)
walls = sum(map(is_wall, kit))
kit = [g for g in kit if not is_wall(g)]
data = unary_union(kit).bounds
massing = [f for f in features(RUN / 'massing/massing.geojson') if f['properties'].get('kind') == 'building']
new, kept = [], []
if massing:
    kit = [g for g in kit if not g.representative_point().within(site)]
    for f in massing:
        g = transform(TO_M, shape(f['geometry']))
        if not (f['properties'].get('existing') and is_wall(g)):
            (kept if f['properties'].get('existing') else new).append(g)
# near or far by cluster (buildings under CLUSTER apart), so a quarter that reaches the site stays one tone
joined = unary_union([g.buffer(CLUSTER / 2) for g in kit + kept])
clusters = list(getattr(joined, 'geoms', [joined]))
reach = unary_union([c for c in clusters if c.distance(site) <= ARGS.fade_m] or [site])
near = [g for g in kit + kept if g.intersects(reach)]
far = [g for g in kit if not g.intersects(reach)]


# size, scale and centre
def frame_item():
    for name in ('layout-plan.json', 'layout.json'):
        p = RUN / 'panel-layout' / name
        if p.exists():
            for panel in json.loads(p.read_text(encoding='utf-8')).get('panels', []):
                for it in panel.get('items', []):
                    if Path(str(it.get('file') or '')).name.startswith('figure-ground') and (it.get('frame') or {}).get('w'):
                        return it, name
    return None, None


item, plan_file = frame_item()
m = re.search(r'1\s*:\s*([\d,. ]+)', str((item or {}).get('scale') or ''))
SCALE = int(re.sub(r'\D', '', m.group(1))) if m else ARGS.scale
for c in ([] if SCALE else [RUN / 'brief-reader/checklist.md', SITE.parent / 'brief/checklist.md', SITE.parent / 'brief-reader/checklist.md']):
    hit = c.exists() and re.search(r'figure.?ground[^\n]*?1\s*:\s*([\d,. ]+\d)', c.read_text(encoding='utf-8'), re.I)
    if hit:
        SCALE = int(re.sub(r'\D', '', hit.group(1)))
        break
if not SCALE:
    raise SystemExit("no scale: give the brief's figure-ground scale as --scale, a frame in the panels' plan, "
                     "or a brief-reader checklist that names it")
k = SCALE / 1000.0                                       # metres per mm on paper

# the sources line: the site kit's Attribution lines (SOURCES.md, "> " under "## Attribution"), and the massing
src_md = SITE / 'SOURCES.md'
att = re.search(r'^## Attribution\s*$(.*?)(?=^## |\Z)', src_md.read_text(encoding='utf-8'), re.M | re.S) if src_md.exists() else None
sources = [re.sub(r',\s*https?://[^)\s]*', '', l[1:].strip()).strip(' .') for l in (att.group(1) if att else '').splitlines()
           if l.startswith('>')] or ['site data: %s' % SITE.name]
if massing:
    sources.append("new buildings from the design's massing")
source_text = 'Sources: ' + '; '.join(s.rstrip('.') for s in sources) + '.'
frame_w = float(item['frame']['w']) if item else None


def wrap(s, width_mm):
    rows, cur = [], ''
    for w_ in s.split():
        if cur and len(cur + ' ' + w_) * T * 0.52 > width_mm:
            rows.append(cur)
            cur = w_
        else:
            cur = (cur + ' ' + w_).strip()
    return rows + [cur]


pad_b = site.buffer(ARGS.pad_m).bounds                   # the plan's width decides how many rows the sources take
src_rows = wrap(source_text, min(frame_w * k if item else pad_b[2] - pad_b[0], data[2] - data[0]) / k)
STRIP = 3 + T + 3 + len(src_rows) * (T + 1.5) + 1          # the caption strip under the plan, mm
notes = []
if item:
    centre = Point(TO_M(*item['centre'])) if item.get('centre') else unary_union(new or [site]).centroid
    want = (float(item['frame']['w']) * k, (float(item['frame']['h']) - STRIP) * k)
else:
    centre = unary_union(new or [site]).centroid
    b = site.buffer(ARGS.pad_m).bounds
    want = (b[2] - b[0], b[3] - b[1])
    notes.append("no figure-ground frame in the panels' plan: the site with %d m around it" % ARGS.pad_m)
win = []
for i, (lo, hi) in enumerate(((data[0], data[2]), (data[1], data[3]))):
    size = want[i]
    if size > hi - lo:                                   # the site data is smaller than the frame: cut, don't pad
        notes.append('the site data is %.0f m %s, the frame %.0f m: the plan is %.0f mm %s instead of %.0f mm; '
                     'site-kit can collect a wider margin' % (hi - lo, ('wide', 'tall')[i], size, (hi - lo) / k,
                                                              ('wide', 'tall')[i], size / k))
        size = hi - lo
    a = min(max((centre.x, centre.y)[i] - size / 2, lo), hi - size)
    win.append((a, a + size))
X0, X1, Y0, Y1 = win[0][0], win[0][1], win[1][0], win[1][1]
WIN = box(X0, Y0, X1, Y1)
Wm, Hm = X1 - X0, Y1 - Y0
W, H = Wm / k, Hm / k + STRIP                            # the drawing on paper, mm


def merge(footprints):
    """One mass of touching footprints; gaps under GAP_CLOSE between two of them filled, no source edge moved."""
    footprints = [g for g in footprints if g.intersects(WIN)]
    if not footprints:
        return None
    merged = unary_union(footprints)
    c = GAP_CLOSE / 2
    tree, fills = STRtree(footprints), []
    for f in getattr(merged.buffer(c, join_style=2).buffer(-c, join_style=2).difference(merged), 'geoms', []):
        if f.geom_type != 'Polygon':
            continue
        touch = [footprints[i] for i in tree.query(f.buffer(0.05)) if footprints[i].distance(f) < 0.05]
        if len(touch) >= 2 and f.buffer(-c * 0.99).is_empty and f.difference(unary_union(touch).buffer(0.3)).is_empty:
            fills.append(f)
    return unary_union([merged] + fills).intersection(WIN)


def path(g):
    if g is None or g.is_empty:
        return ''
    if g.geom_type == 'Polygon':
        return ''.join('M' + 'L'.join('%.1f,%.1f' % (x - X0, Y1 - y) for x, y in r.coords) + 'Z'
                       for r in [g.exterior, *g.interiors])
    return ''.join(path(p) for p in getattr(g, 'geoms', []))


def mm(v):
    return '%.2f' % (v * k)


def text(x, y, s, size=T, anchor='start'):
    return (f'<text x="{mm(x)}" y="{mm(y)}" font-size="{size * k:.2f}" text-anchor="{anchor}" '
            f'fill="{S["ink"]}">{escape(s)}</text>')


layers = [f'<rect width="{Wm:.1f}" height="{H * k:.1f}" fill="{S["paper"]}"/>']
for g, key in ((merge(far), 'existing'), (merge(near), 'building'), (merge(new), 'ink')):
    if g is not None:
        layers.append(f'<path d="{path(g)}" fill="{S[key]}" fill-rule="evenodd"/>')

# the caption strip: title and scale at the left, scale bar and north at the right, the sources under them
thin = float(S.get('thin') or 0.13)
y1, y2 = Hm / k + 3 + T, Hm / k + 3 + T + 3 + T
strip = [text(0, y1, ARGS.title), text(len(ARGS.title) * T * 0.56 + 4, y1, '1:{:,}'.format(SCALE))]
bar = next(v for v in (50, 100, 200, 250, 500, 1000, 2000, 5000, 10000) if v / k >= W / 6 or v == 10000)
seg, bx = bar / k / 5, W - 22 - bar / k
sb = [f'<rect x="{mm(bx + i * seg)}" y="{mm(y1 - 1.2)}" width="{mm(seg)}" height="{mm(1.2)}" '
      f'fill="{S["ink"] if i % 2 == 0 else S["paper"]}" stroke="{S["ink"]}" stroke-width="{mm(thin)}"/>' for i in range(5)]
sb += [text(bx, y1 - 2, '0', anchor='middle'), text(bx + bar / k, y1 - 2, '%g m' % bar, anchor='middle')]
strip.append('<g id="scale-bar">' + ''.join(sb) + '</g>')
lon, lat = TO_LL((X0 + X1) / 2, (Y0 + Y1) / 2)           # true north at the plan's centre
nx_, ny_ = TO_M(lon, lat + 0.01)
a = math.atan2(nx_ - (X0 + X1) / 2, ny_ - (Y0 + Y1) / 2)
nx, ny, r = W - 4, y1 - 1.5, 3.0                         # an arrow pointing up, turned to true north
strip.append(f'<path d="M{mm(nx)},{mm(ny - r)}L{mm(nx + 0.55 * r)},{mm(ny + 0.8 * r)}L{mm(nx)},{mm(ny + 0.3 * r)}'
             f'L{mm(nx - 0.55 * r)},{mm(ny + 0.8 * r)}Z" fill="{S["ink"]}" '
             f'transform="rotate({math.degrees(a):.2f} {mm(nx)} {mm(ny)})"/>' + text(nx - r - 1, y1, 'N', anchor='end'))
for i, row in enumerate(wrap(source_text, W)):
    strip.append(text(0, y2 + i * (T + 1.5), row))

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" height="{H:.1f}mm" '
       f'viewBox="0 0 {Wm:.1f} {H * k:.1f}" font-family="{FONT}">\n' + '\n'.join(layers + strip) + '\n</svg>\n')
name = 'figure-ground_1-%d' % SCALE
(OUT / (name + '.svg')).write_text(svg, encoding='utf-8')

# PNG by a headless Chrome or Edge
exe = next((e for e in [shutil.which('chrome'), shutil.which('msedge'), shutil.which('chromium'),
                        shutil.which('google-chrome'),
                        r'C:/Program Files/Google/Chrome/Application/chrome.exe',
                        r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
                        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                        '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'] if e and os.path.exists(e)), None)
if exe:
    pw, ph = round(W * PX_PER_MM), round(H * PX_PER_MM)
    html = OUT / (name + '_wrap.html')
    html.write_text(f'<html><body style="margin:0"><img src="{name}.svg" style="width:{pw}px;height:{ph}px"></body></html>',
                    encoding='utf-8')
    subprocess.run([exe, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
                    f'--screenshot={(OUT / (name + ".png")).resolve()}', f'--window-size={pw},{ph}',
                    html.resolve().as_uri()], capture_output=True, timeout=300)
    html.unlink()
else:
    notes.append('no Chrome or Edge found: SVG only, no PNG')

ha = lambda gs: sum(g.intersection(WIN).area for g in gs) / 1e4
n_new = sum(1 for g in new if g.intersects(WIN))
lines = [
    f'`{name}.svg` and `.png` at 1:{SCALE:,}, {W:.0f} x {H:.0f} mm'
    + (f" (the frame in panel-layout/{plan_file})" if item else '') + ': '
    + (f'{n_new} new buildings dark, ' if massing else 'no massing yet, so only the city as it is: ')
    + f'existing quarters reaching within {ARGS.fade_m:.0f} m of the site in mid grey, those further out light grey; no streets, lines or boundary'
    + (f'; {walls} walls the data models as buildings (over {WALL[0]} m long, under {WALL[1]:g} m wide) left out.' if walls else '.'),
    (f'New footprint {ha(new):.1f} ha against {ha(near + far):.1f} ha existing in the frame.' if massing
     else f'{ha(near + far):.1f} ha of existing footprint in the frame; the design is not shown.'),
    'Unsure: ' + ('; '.join(notes) if notes else 'the site boundary only sorts the buildings (site.geojson as it is)') + '.',
]
(OUT / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines))
