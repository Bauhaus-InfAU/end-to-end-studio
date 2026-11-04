"""The plans a brief asks for, composited from the design layers: the site plan, the detail areas, the figure-ground.

    python plans.py --proposal <proposal folder> --site <site folder> --config <proposal>/plans/config.json
                    [--style <proposal>/drawing-graphics/style.json]

config.json holds the brief's values, each as {"value": ..., "source": "<brief file> p. N" or "assumption: ..."}:
site_plan_scale, panel_width_mm and panel_height_mm are required; figure_ground_scale, storeys_on_site_plan,
margin_mm, detail_areas (a list of {"name", "scale", "at", "shows", "page"}, `at` a centre's name in the structure
plan, "phase1", or [lon, lat]) and labels (the legend's words) are optional. Every layer but the massing is
optional: buildings from massing/, the street surface from streets/, the ground from open-space/, stops and hubs
from mobility/, the centres from structure-plan/. A missing layer is left out and named in drawings.json. A detail area or the site plan that
the panels' plan (<proposal>/panel-layout/layout-plan.json, else layout.json) frames takes that frame's scale and is
drawn to its size, the legend strip included. The style's storey_labels writes the storeys roman or arabic (default).
Writes <name>_1-<scale>.svg and .png and drawings.json into <proposal>/plans/.
"""
import argparse, json, math, os, re, subprocess, sys
from xml.sax.saxutils import escape
from shapely.geometry import shape, box, Point, Polygon
from shapely.ops import transform, unary_union
from shapely import affinity
import pyproj


def utm_epsg(lon, lat):
    """The UTM zone of a point, as an EPSG code."""
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


def read_config(path, required=()):
    """config.json: {key: {"value": ..., "source": ...}} or {key: value}. Stops on a missing key."""
    raw = json.load(open(path, encoding='utf8'))
    # a value left empty (null) or a source still in <angle brackets> counts as not filled in
    raw = {k: v for k, v in raw.items() if not (isinstance(v, dict) and (v.get('value') is None
           or str(v.get('source', '')).startswith('<')))}
    missing = [k for k in required if k not in raw]
    if missing:
        sys.exit('missing in config.json: ' + ', '.join(missing) + ' (from the brief, with its page)')
    values = {k: (v['value'] if isinstance(v, dict) and 'value' in v else v) for k, v in raw.items()}
    sources = {k: (v.get('source', '') if isinstance(v, dict) else '') for k, v in raw.items()}
    return values, sources


DEFAULTS = {
    # street widths in metres by the site's street class, used only without the streets skill's surface
    'street_widths': {'motorway': 28, 'trunk': 22, 'trunk_link': 9, 'primary': 18, 'secondary': 15, 'tertiary': 13,
                      'tertiary_link': 8, 'residential': 10, 'unclassified': 8, 'living_street': 7, 'service': 5,
                      'pedestrian': 6, 'track': 3.5, 'cycleway': 3, 'footway': 2.5, 'path': 2, 'steps': 2},
    'street_w_other': 6.0,      # metres for a street class not in the table
    'street_w_new': 10.0,       # metres for a massing street without a width
    'green_landuse': ['forest', 'wood', 'scrub', 'meadow', 'grass', 'park', 'farmland', 'allotments'],  # context green
    'gone_rail': ['abandoned', 'razed', 'dismantled'],   # rail lines no longer there, not drawn
    'tree_crown_m': 6,          # crown diameter of a tree without crown_m, metres
    'tree_shadow': 0.3,         # a crown's shadow falls this share of its diameter away, the way the buildings' fall
    'shadow_az_deg': 135,       # shadows fall to the lower right of the sheet: light from the upper left, the plan convention
    'shared_street_w_m': 7,     # width of the public tone along mobility's access-only streets, metres
    'text_floor_mm': 3.2,       # no text smaller than this on paper (12 px, 9 pt)
    'site_pad_m': 40,           # ground shown around the site on the site plan, metres
    'fg_pad_m': 600,            # ground around the site on the figure-ground without the kit's bbox, metres
    'detail_near_m': 150,       # new buildings this close to a detail area's centre set its window, metres
    'detail_pad_m': 30,         # ground around them, metres
    'detail_min_mm': 150,       # a detail window is never smaller than this on paper, where the panel allows
    'legend_mm': 30,            # the strip under the map for the title, legend, scale bar, north and source
    'caption_room_mm': 60,      # panel height kept free for a caption and the legend strip
    'margin_mm': 15,            # panel margin when neither the brief nor the standard gives one
    'png_px_per_mm': 4,         # PNG resolution, pixels per printed mm
}
LABELS = {'new': 'New buildings', 'existing': 'Kept buildings', 'context': 'Existing buildings',
          'buildings': 'Buildings', 'street': 'Streets and squares', 'path': 'Paths', 'green': 'Fields and woods',
          'park': 'Parks', 'kept': 'Kept green', 'lawn': 'Lawn, gardens', 'meadow': 'Meadow',
          'wet-meadow': 'Wet meadow', 'grove': 'Grove', 'water': 'Water, rain pools', 'playground': 'Playground',
          'rail': 'Rail', 'tree': 'Trees', 'stop': 'Stop', 'hub': 'Mobility hub', 'access': 'Car access',
          'storeys': 'Storeys', 'site': 'Project site', 'window': 'Detail areas', 'landmark': 'Landmark',
          'public': 'Squares, shared streets',
          'site-plan': 'Site plan', 'figure-ground': 'Figure-ground'}
# the look without a drawing standard: black on white, one accent
FALLBACK_STYLE = {'paper': '#ffffff', 'ink': '#1a1a1a', 'accent': '#d9302b', 'new': '#ffffff', 'public': '#f0b8b5',
                  'shadow': '#a8a8a8', 'shadow_len': 1.2,
                  'existing': '#d0d0d0', 'context': '#e4e4e4', 'building': '#9a9a9a', 'street': '#f4f4f4',
                  'path': '#b0b0b0', 'park': '#e2e2e2', 'kept': '#d2d2d2', 'lawn': '#ececec', 'meadow': '#f0f0f0',
                  'wet-meadow': '#e6e6e6', 'grove': '#a8a8a8', 'water': '#cfd8dc',
                  'ramp': ['#f3f3f3', '#d9d9d9', '#bdbdbd', '#8c8c8c', '#4d4d4d'],
                  'font': 'Arial, Helvetica, sans-serif', 'thin': 0.13, 'mid': 0.25, 'thick': 0.5, 'line': 0.25,
                  'line_mm': 0.25, 'outline': 0.35, 'text': 3.2, 'title': 5.6, 'body_pt': 11, 'heading_pt': 20}

A = argparse.ArgumentParser(description='The plans a brief asks for, from the design layers.')
A.add_argument('--proposal', required=True)
A.add_argument('--site', required=True, help='the folder with site.geojson and its layers')
A.add_argument('--config', required=True)
A.add_argument('--style', help='the drawing standard\'s style.json')
ARGS = A.parse_args()
RUN, SITE = ARGS.proposal, ARGS.site
OUT = os.path.join(RUN, 'plans')
os.makedirs(OUT, exist_ok=True)
CFG, SOURCE = read_config(ARGS.config, ['site_plan_scale', 'panel_width_mm', 'panel_height_mm'])
CFG = {**DEFAULTS, **CFG}
LAB = {**LABELS, **(CFG.get('labels') or {})}

style_path = ARGS.style or os.path.join(RUN, 'drawing-graphics', 'style.json')
S = dict(FALLBACK_STYLE)
if os.path.exists(style_path):
    S.update(json.load(open(style_path, encoding='utf8')))
FONT = escape(str(S['font']), {'"': "'"})
TXT = max(float(CFG['text_floor_mm']), float(S.get('text') or 0))       # text size on paper, mm
TITLE = max(TXT, float(S.get('title') or 0))

site_ll = shape(json.load(open(os.path.join(SITE, 'site.geojson'), encoding='utf8'))['features'][0]['geometry'])
EPSG = CFG.get('epsg') or utm_epsg(site_ll.centroid.x, site_ll.centroid.y)
TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
TO_LL = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform
site = transform(TO_M, site_ll)
_src = os.path.join(SITE, 'SOURCES.md')
CREDIT = ('Map data © OpenStreetMap contributors (ODbL, https://www.openstreetmap.org/copyright).'
          if os.path.exists(_src) and 'OpenStreetMap' in open(_src, encoding='utf8').read() else '')


def load(path):
    """[(properties, geometry in metres)] of a GeoJSON, or None when the file is missing."""
    if not os.path.exists(path):
        return None
    out = []
    for f in json.load(open(path, encoding='utf8'))['features']:
        if not f.get('geometry'):
            continue
        g = transform(TO_M, shape(f['geometry']))
        if g.geom_type.endswith('Polygon') and not g.is_valid:
            g = g.buffer(0)
        out.append((f.get('properties') or {}, g))
    return out


MASS = load(os.path.join(RUN, 'massing', 'massing.geojson'))
if MASS is None:
    sys.exit('missing massing/massing.geojson in the proposal: run the massing first')
STREETS = load(os.path.join(RUN, 'streets', 'streets.geojson'))
OPEN = load(os.path.join(RUN, 'open-space', 'open-space.geojson'))
MOB = load(os.path.join(RUN, 'mobility', 'mobility.geojson'))
SP = load(os.path.join(RUN, 'structure-plan', 'structure-plan.geojson'))
CTX = load(os.path.join(SITE, 'buildings.geojson')) or []
PLOTS = load(os.path.join(SITE, 'plots.geojson')) or []
WATER = load(os.path.join(SITE, 'water.geojson')) or []
RAIL = load(os.path.join(SITE, 'rail.geojson')) or []
SITE_STREETS = load(os.path.join(SITE, 'streets.geojson')) or []

BUILD = [(p, g) for p, g in MASS if p.get('kind') == 'building']
NEW = [(p, g) for p, g in BUILD if not p.get('existing')]
KEPT = [(p, g) for p, g in BUILD if p.get('existing')]
CTX_OUT = [(p, g) for p, g in CTX if not site.contains(g.representative_point())]

PW = float(CFG['panel_width_mm']) - 2 * float(CFG['margin_mm'])          # panel room, mm
PH_ALL = float(CFG['panel_height_mm']) - 2 * float(CFG['margin_mm'])
PH = PH_ALL - float(CFG['caption_room_mm'])                               # room for the map itself, mm


# ---------------- windows ----------------
def layout_frames():
    """{plan name: (scale or None, frame w, frame h in mm)} of the plans the panels' plan frames."""
    p = next((q for q in (os.path.join(RUN, 'panel-layout', n) for n in ('layout-plan.json', 'layout.json')) if os.path.exists(q)), None)
    out = {}
    for it in [it for q in (json.load(open(p, encoding='utf8')).get('panels', []) if p else []) for it in q.get('items', [])]:
        f, fr = str(it.get('file') or '').replace('\\', '/'), it.get('frame') or {}
        m = re.search(r'1\s*:\s*([\d,. ]+)', str(it.get('scale') or ''))
        if f.startswith('plans/') and fr.get('w') and fr.get('h'):
            out[re.sub(r'_1-\d+$', '', os.path.splitext(f[6:])[0])] = (
                int(re.sub(r'\D', '', m.group(1))) if m else None, float(fr['w']), float(fr['h']))
    return out


def fitted(name, title, scale, kind, window_of, frame, windows=()):
    """The window of a plan in a frame (w, h mm): the frame's width, and its height less the legend strip under the
    map, which a first drawing without its PNG measures. window_of(room in metres) gives (window, cut)."""
    k = scale / 1000.0
    e = draw_plan(name, title, scale, window_of((frame[0] * k, (frame[1] - CFG['legend_mm']) * k))[0], kind, windows, False)
    return window_of((frame[0] * k, max(frame[1] - e['height_mm'] + e['map_height_mm'], frame[1] / 2) * k))


def clamp(bounds, scale, centre=None, frame_m=None):
    """The window of these bounds, cut to the panel room at this scale; an axis that is cut centres on `centre`.
    With frame_m, a frame's (w, h) in metres, the window is that size, grown around the bounds where they are smaller."""
    k = scale / 1000.0
    x0, y0, x1, y1 = bounds
    full = frame_m or (PW * k, PH * k)
    axes, cut = [], False
    for lo, hi, room, c in ((x0, x1, full[0], centre[0] if centre else None), (y0, y1, full[1], centre[1] if centre else None)):
        if hi - lo <= room:
            axes.append(((lo + hi - room) / 2, (lo + hi + room) / 2) if frame_m else (lo, hi))
            continue
        cut = True
        c = (lo + hi) / 2 if c is None else c
        a = min(max(c - room / 2, lo), hi - room)
        axes.append((a, a + room))
    return (axes[0][0], axes[1][0], axes[0][1], axes[1][1]), cut


def pad(b, m): return (b[0] - m, b[1] - m, b[2] + m, b[3] + m)


def anchor_of(at):
    """The geometry a detail area is around, or (None, why not)."""
    if isinstance(at, (list, tuple)) and len(at) == 2:
        return Point(TO_M(float(at[0]), float(at[1]))), ''
    if at == 'phase1':
        mc = os.path.join(RUN, 'massing', 'config.json')
        names = []
        if os.path.exists(mc):
            v = json.load(open(mc, encoding='utf8')).get('phase1')
            names = (v.get('value') if isinstance(v, dict) else v) or []
        gs = [g for p, g in (SP or []) if p.get('kind') == 'neighbourhood' and p.get('name') in names]
        return (unary_union(gs), '') if gs else (None, 'no phase1 neighbourhoods in massing/config.json and the structure plan')
    if SP is None:
        return None, 'no structure-plan/structure-plan.geojson to find the centre "%s"' % at
    gs = [g for p, g in SP if p.get('kind') == 'centre' and str(p.get('name', '')).lower() == str(at).lower()]
    return (unary_union(gs), '') if gs else (None, 'no centre named "%s" in the structure plan' % at)


def detail_window(anchor, scale, frame_m=None):
    k = scale / 1000.0
    c = anchor.centroid
    full = frame_m or (PW * k, PH * k)
    near = [g for p, g in NEW if g.distance(anchor) <= CFG['detail_near_m']]
    want = pad(unary_union(near + [anchor]).bounds, CFG['detail_pad_m'])
    axes, cut = [], False
    for i, (lo, hi) in enumerate(((want[0], want[2]), (want[1], want[3]))):
        room, mid = full[i], (c.x, c.y)[i]
        if hi - lo > room:                       # more than the panel holds: the whole room, centred on the anchor
            cut = True
            axes.append((mid - room / 2, mid + room / 2))
        else:                                    # smaller: just the new buildings around it, never tiny; a frame filled
            size = room if frame_m else min(room, max(hi - lo, CFG['detail_min_mm'] * k))
            m = (lo + hi) / 2
            axes.append((m - size / 2, m + size / 2))
    return (axes[0][0], axes[1][0], axes[0][1], axes[1][1]), cut


# ---------------- drawing ----------------
def mix(a, b, t):
    a, b = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#%02x%02x%02x' % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lum(c):
    return sum(w * int(c[i:i + 2], 16) / 255 for w, i in ((0.299, 1), (0.587, 3), (0.114, 5)))


def nice(x):
    for v in (10, 20, 40, 50, 100, 200, 400, 500, 1000, 2000, 4000, 5000, 10000):
        if v >= x:
            return v
    return 20000


def tw(s, size, bold=False):
    """An estimate of a text's width on paper."""
    return len(s) * size * (0.6 if bold else 0.56)


def shot(svg, png, w, h):
    exe = next(e for e in [r'C:/Program Files/Google/Chrome/Application/chrome.exe',
                           r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
                           '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                           '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', 'chromium', 'google-chrome'] if os.path.exists(e) or '/' not in e)
    html = svg.replace('.svg', '_wrap.html')
    open(html, 'w', encoding='utf8').write(f'<html><body style="margin:0"><img src="{os.path.basename(svg)}" style="width:{w}px;height:{h}px"></body></html>')
    subprocess.run([exe, '--headless', '--disable-gpu', '--hide-scrollbars', f'--screenshot={os.path.abspath(png)}',
                    f'--window-size={w},{h}', 'file:///' + os.path.abspath(html).replace('\\', '/')], capture_output=True, timeout=180)
    os.remove(html)


def storeys(n):
    """A number of storeys as the standard's storey_labels writes it: arabic (4), or roman (IV)."""
    if str(S.get('storey_labels', 'arabic')).lower() != 'roman':
        return str(n)
    out = ''
    for v, r in ((50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        q, n = divmod(n, v)
        out += r * q
    return out or '0'


def draw_plan(name, title, scale, window, kind, windows=(), shoot=True):
    """One plan as SVG and PNG (without shoot, the SVG only). kind: site, detail or figure-ground. Returns its drawings.json entry."""
    k = scale / 1000.0                                   # metres per mm on paper
    wx0, wy0, wx1, wy1 = window
    Wm, Hm = wx1 - wx0, wy1 - wy0
    W = Wm / k                                           # map width on paper, mm
    fr = box(*window)
    fs = TXT * k
    used, missing, legend = ['massing'], [], {}

    def lw(key): return float(S[key]) * k
    def f2(v): return '%.2f' % v
    def P(x, y): return x - wx0, wy1 - y

    def d(g):
        if g.is_empty:
            return ''
        if g.geom_type == 'Polygon':
            return ''.join('M' + 'L'.join('%.2f,%.2f' % P(*c[:2]) for c in r.coords) + 'Z' for r in [g.exterior, *g.interiors])
        if g.geom_type in ('LineString', 'LinearRing'):
            return 'M' + 'L'.join('%.2f,%.2f' % P(*c[:2]) for c in g.coords)
        if hasattr(g, 'geoms'):
            return ''.join(d(q) for q in g.geoms)
        return ''

    def inside(items):
        return [(p, g) for p, g in items if g.intersects(fr)]

    def fill(g, colour, key=None, stroke=None, sw='thin', extra=''):
        if key:
            legend.setdefault(key, ('fill', colour, stroke, sw))
        st = f' stroke="{stroke}" stroke-width="{f2(lw(sw))}"' if stroke else ' stroke="none"'
        o.append(f'<path d="{d(g)}" fill="{colour}"{st} fill-rule="evenodd"{extra}/>')

    def line(g, colour, sw='thin', dash=None, key=None):
        if key:
            legend.setdefault(key, ('line', colour, sw, dash))
        da = f' stroke-dasharray="{f2(dash[0] * k)} {f2(dash[1] * k)}"' if dash else ''
        o.append(f'<path d="{d(g)}" fill="none" stroke="{colour}" stroke-width="{f2(lw(sw))}"{da} stroke-linejoin="round"/>')

    o = [f'<g clip-path="url(#map)">', f'<rect width="{f2(Wm)}" height="{f2(Hm)}" fill="{S["paper"]}"/>']
    if kind == 'figure-ground':
        used.append('site buildings')
        for p, g in inside(CTX_OUT) + inside(BUILD):
            fill(g, S['ink'], 'buildings')
        line(site, S['accent'], 'thick', (3, 1.5), 'site')
    else:
        # 1. context green and water
        green = set(CFG['green_landuse'])
        for p, g in inside(PLOTS):
            if str(p.get('landuse', '')).split(':')[-1] in green:
                fill(g.intersection(fr), mix(S['context'], S['paper'], 0.5), 'green')
        for p, g in inside(WATER):
            fill(g.intersection(fr), S['water'], 'water')
        # 2. the ground: open-space's layer, else the massing's
        for p, g in inside([(p, g) for p, g in MASS if p.get('kind') == 'open-space' and p.get('use') == 'garden']):
            fill(g, S['lawn'], 'lawn')
        if OPEN is not None:
            used.append('open-space')
            for p, g in inside([x for x in OPEN if x[0].get('kind') == 'open-space']):
                u = p.get('use')
                if u == 'water':
                    fill(g, S['water'], 'water')
                elif u == 'park':
                    fill(g, S['kept'], 'kept') if p.get('existing') else fill(g, S['park'], 'park')
            for p, g in inside([x for x in OPEN if x[0].get('kind') == 'ground-cover']):
                c = str(p.get('cover', '')).replace(' ', '-')
                if c in S and isinstance(S[c], str):
                    fill(g, S[c], c)
            for p, g in inside([x for x in OPEN if x[0].get('kind') == 'retention']):
                fill(g, S['water'], 'water')
            for p, g in inside([x for x in OPEN if x[0].get('kind') == 'open-space' and x[0].get('use') == 'playground']):
                fill(g, 'none', 'playground', S['ink'], 'mid')
        else:
            missing.append('open-space (the ground from the massing)')
            for p, g in inside([(p, g) for p, g in MASS if p.get('kind') == 'open-space']):
                u = p.get('use')
                if u == 'park':
                    fill(g, S['park'], 'park')
                elif u == 'water':
                    fill(g, S['water'], 'water')
        # 3. streets: the streets skill's surface, else lines at their widths
        paths = [g for p, g in (OPEN or []) if p.get('kind') == 'path']
        if STREETS is not None:
            used.append('streets')
            old = [g for p, g in inside(STREETS) if p.get('kind') == 'street' and p.get('existing') and g.geom_type.endswith('Polygon')]
            new = [g for p, g in inside(STREETS) if p.get('kind') == 'street' and not p.get('existing') and g.geom_type.endswith('Polygon')]
            for p, g in inside(STREETS):
                if p.get('kind') == 'path':
                    if g.geom_type.endswith('Polygon'):
                        fill(g, S['street'])
                    else:
                        paths.append(g)
            if old:
                fill(unary_union(old).intersection(fr.buffer(10)), S['street'], 'street', S['path'])
            if new:
                fill(unary_union(new).intersection(fr.buffer(10)), S['street'], 'street', S['ink'])
        else:
            missing.append('streets (street lines at assumed widths)')
            surf, W_ = [], CFG['street_widths']
            for p, g in inside(SITE_STREETS):
                w = None
                try:
                    w = float(p['width']) if p.get('width') else float(p['lanes']) * 3.25 + 4
                except (KeyError, TypeError, ValueError):
                    pass
                surf.append(g.buffer((w or W_.get(p.get('highway'), CFG['street_w_other'])) / 2, cap_style=2, join_style=1))
            for p, g in inside([(p, g) for p, g in MASS if p.get('kind') == 'street']):
                surf.append(g if g.geom_type.endswith('Polygon') else
                            g.buffer(float(p.get('width') or CFG['street_w_new']) / 2, cap_style=2, join_style=1))
            if surf:
                fill(unary_union(surf).intersection(fr.buffer(10)), S['street'], 'street', S['path'])
        # 3b. the public ground in the accent's pale tone: the massing's squares, the shared streets
        pub = [g for p, g in MASS if p.get('kind') == 'open-space' and p.get('use') == 'square']
        pub += [g.buffer(CFG['shared_street_w_m'] / 2, cap_style=2) for p, g in (MOB or [])
                if p.get('kind') == 'route' and p.get('access_only')]
        pub = unary_union([g for g in pub if g.intersects(fr)]) if pub else None
        if pub is not None and not pub.is_empty:
            fill(pub.intersection(fr.buffer(10)), S['public'], 'public')
        for g in paths:
            if g.intersects(fr):
                line(g, S['path'], 'thin', (1.2, 0.8), 'path')
        # 4. rail: four thin lines
        for p, g in inside(RAIL):
            if p.get('railway') in CFG['gone_rail']:
                continue
            for q in getattr(g, 'geoms', [g]):
                for off in (-2.2, -0.8, 0.8, 2.2):
                    try:
                        line(q.offset_curve(off), S['ink'], 'thin', key='rail')
                    except Exception:
                        pass
        # 4b. the buildings' cast shadow, one shape, darkening whatever ground it falls on
        sh = shadows(inside(BUILD))
        if not sh.is_empty:
            o.append(f'<path d="{d(sh)}" fill="{S["shadow"]}" stroke="none" fill-rule="evenodd" style="mix-blend-mode:multiply"/>')
        # 4c. trees at every scale, the massing's and open-space's: a crown over its soft shadow, under the buildings
        trees = [(*P(g.x, g.y), float(p.get('crown_m') or CFG['tree_crown_m']) / 2) for p, g in inside(MASS + (OPEN or []))
                 if p.get('kind') == 'tree' and g.geom_type == 'Point']
        if trees:
            a = math.radians(CFG['shadow_az_deg'])
            dx, dy = 2 * CFG['tree_shadow'] * math.sin(a), -2 * CFG['tree_shadow'] * math.cos(a)
            o.append(f'<g fill="{S["shadow"]}" fill-opacity="0.5" style="mix-blend-mode:multiply">' + ''.join(
                f'<circle cx="{f2(x + dx * r)}" cy="{f2(y + dy * r)}" r="{f2(r)}"/>' for x, y, r in trees) + '</g>')
            o.append(f'<g fill="{S["grove"]}" fill-opacity="0.9" stroke="{mix(S["grove"], S["ink"], 0.3)}" '
                     f'stroke-width="{f2(lw("thin"))}">' + ''.join(
                         f'<circle cx="{f2(x)}" cy="{f2(y)}" r="{f2(r)}"/>' for x, y, r in trees) + '</g>')
            legend.setdefault('tree', ('dot', S['grove']))
        # 5. existing buildings: around the site pale, kept ones in it with an outline
        used.append('site buildings')
        for p, g in inside(CTX_OUT):
            fill(g, S['context'], 'context')
        for p, g in inside(KEPT):
            fill(g, S['existing'], 'existing', S['ink'], 'thin')
        # 6. new buildings
        for p, g in inside(NEW):
            if p.get('landmark'):
                fill(g, S['new'], 'landmark', S['ink'], 'thick')
            else:
                fill(g, S['new'], 'new', S['ink'], 'mid')
        # 8. mobility: stops, hubs, car access; the routes belong to the mobility plan
        if MOB is not None:
            used.append('mobility')
            for p, g in inside([x for x in MOB if x[0].get('kind') in ('stop', 'hub', 'access') and x[1].geom_type == 'Point']):
                o.append(symbol(p['kind'], *P(g.x, g.y), k))
                legend.setdefault(p['kind'], (p['kind'],))
        else:
            missing.append('mobility (no stops or hubs)')
        # 9. storeys on the new buildings
        if kind == 'detail' or CFG.get('storeys_on_site_plan'):
            ink_on_new = S['ink'] if lum(S['new']) > 0.55 else S['paper']   # whichever reads on the new buildings' tone
            for p, g in inside(NEW):
                if p.get('floors') is None:
                    continue
                s = storeys(int(round(float(p['floors']))))
                if g.area < 3 * tw(s, fs) * fs:
                    continue
                c = g.representative_point()
                x, y = P(c.x, c.y)
                o.append(f'<text x="{f2(x)}" y="{f2(y + 0.36 * fs)}" font-size="{f2(fs)}" text-anchor="middle" fill="{ink_on_new}">{s}</text>')
                legend.setdefault('storeys', ('text', ink_on_new))
        # 10. the site boundary, and the detail areas on the site plan
        line(site, S['ink'], 'thick', (3, 1.5), 'site')
        for wname, wb in windows:
            line(box(*wb).exterior, S['ink'], 'thin', (2, 1), 'window')
            x, y = P(wb[0], wb[3])
            o.append(f'<text x="{f2(x + 1.5 * k)}" y="{f2(y + 1.5 * k + fs)}" font-size="{f2(fs)}" fill="{S["ink"]}">{escape(wname)}</text>')
    o.append('</g>')

    # 11. the strip under the map: title, north, scale bar, legend, source (laid out in mm, written in metres)
    strip, H_strip = legend_strip(title, scale, W, legend, k, Hm, window)
    Hs = H_strip * k
    head = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" height="{(Hm + Hs) / k:.1f}mm" '
            f'viewBox="0 0 {f2(Wm)} {f2(Hm + Hs)}" font-family="{FONT}">',
            f'<defs><clipPath id="map"><rect width="{f2(Wm)}" height="{f2(Hm)}"/></clipPath></defs>',
            f'<rect width="{f2(Wm)}" height="{f2(Hm + Hs)}" fill="{S["paper"]}"/>']
    fname = f'{name}_1-{scale}'
    svgp = os.path.join(OUT, fname + '.svg')
    open(svgp, 'w', encoding='utf8').write('\n'.join(head + o + strip + ['</svg>']))
    H = (Hm + Hs) / k
    png = os.path.join(OUT, fname + '.png')
    try:
        px = CFG['png_px_per_mm']
        if shoot:
            shot(svgp, png, int(W * px), int(H * px))
    except Exception as e:
        print('no PNG for', fname, ':', e, file=sys.stderr)
    return dict(name=name, file=fname + '.svg', png=os.path.exists(png), title=title, scale=scale,
                width_mm=round(W, 1), height_mm=round(H, 1), map_width_mm=round(W, 1), map_height_mm=round(Hm / k, 1),
                fits=W <= PW + 0.5 and H <= PH_ALL + 0.5, layers_used=used, layers_missing=missing)


def shadows(items):
    """The ground shadow of buildings, shadow_len metres per floor: each footprint swept along the light (the footprint,
    it moved, and the band each edge sweeps), so a courtyard stays open where no wall shades it."""
    a = math.radians(CFG['shadow_az_deg'])
    out = []
    for p, g in items:
        L = float(S['shadow_len']) * float(p.get('floors') or 1)
        vx, vy = math.sin(a) * L, math.cos(a) * L
        for q in getattr(g, 'geoms', [g]):
            if q.geom_type != 'Polygon':
                continue
            out += [q, affinity.translate(q, vx, vy)]
            for r in [q.exterior, *q.interiors]:
                c = [xy[:2] for xy in r.coords]
                out += [Polygon([(x1, y1), (x2, y2), (x2 + vx, y2 + vy), (x1 + vx, y1 + vy)]) for (x1, y1), (x2, y2) in zip(c, c[1:])]
    return unary_union([q for q in out if q.area > 0]) if out else Polygon()


def symbol(kind, x, y, k):
    ink, paper = S['ink'], S['paper']
    sw = '%.2f' % (float(S['mid']) * k)
    if kind == 'stop':
        return (f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{2.0 * k:.2f}" fill="{paper}" stroke="{ink}" stroke-width="{sw}"/>'
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{1.0 * k:.2f}" fill="{ink}"/>')
    if kind == 'hub':
        return (f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{2.8 * k:.2f}" fill="{paper}" stroke="{ink}" stroke-width="{sw}"/>'
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{1.6 * k:.2f}" fill="none" stroke="{ink}" stroke-width="{sw}"/>')
    r = 1.8 * k
    return f'<path d="M{x:.2f},{y - r:.2f}L{x + r:.2f},{y:.2f}L{x:.2f},{y + r:.2f}L{x - r:.2f},{y:.2f}Z" fill="{paper}" stroke="{ink}" stroke-width="{sw}"/>'


def north_angle(window):
    """The direction of true north at the window's centre, in radians from the map's up."""
    cx, cy = (window[0] + window[2]) / 2, (window[1] + window[3]) / 2
    lon, lat = TO_LL(cx, cy)
    x, y = TO_M(lon, lat + 0.01)
    return math.atan2(x - cx, y - cy)


def legend_strip(title, scale, W, legend, k, Hm, window):
    """The title, north, scale bar, legend and source under the map. Returns (svg lines, strip height in mm)."""
    ink, paper = S['ink'], S['paper']
    o = []
    def m(v): return '%.2f' % (v * k)
    def text(x, y, s, size=TXT, extra=''):
        o.append(f'<text x="{m(x)}" y="{m(Hm / k + y)}" font-size="{size * k:.2f}" fill="{ink}"{extra}>{escape(s)}</text>')
    def Y(y): return Hm / k + y
    thin = float(S['thin'])
    # title, and north at the right
    head = f'{title}, 1:{scale:,}'
    text(4, 3 + TITLE, head, TITLE, ' font-weight="bold"')
    r = 4.0
    nx, ny = W - 4 - r, 3 + r
    a = north_angle(window)
    o.append(f'<circle cx="{m(nx)}" cy="{m(Y(ny))}" r="{m(r)}" fill="none" stroke="{ink}" stroke-width="{m(thin)}"/>'
             f'<path d="M{m(nx)},{m(Y(ny))}L{m(nx + r * math.sin(a))},{m(Y(ny - r * math.cos(a)))}" stroke="{ink}" stroke-width="{m(thin * 2)}"/>')
    # scale bar: one thin line stepping up and down, a tick at every step, numbers under, the unit on the last
    L = nice(W * k / 6)
    n = 5 if L in (10, 50, 500, 5000) else 4
    Lmm, seg, hstep = L / k, L / k / n, 1.5
    nums = [('%g' % (i * L / n)) + (' m' if i == n else '') for i in range(n + 1)]
    gap = tw(max(nums, key=len), TXT) + 1              # numbers that would touch are left out, never the first or last
    show, last = {0, n}, 0
    for i in range(1, n):
        if (i - last) * seg >= gap and (n - i) * seg >= gap:
            show.add(i); last = i
    x_end = nx - r - 6 - tw(' m', TXT)
    row_y = 3 + max(TITLE, 2 * r)
    if x_end - Lmm < 4 + tw(head, TITLE, True) + 6:     # no room beside the title: its own row
        x0, sy, row_y = 4, row_y + 3 + hstep, row_y + 3 + hstep + 1.2 + TXT + 1
    else:
        x0, sy = x_end - Lmm, 3 + TITLE - 1.2 - TXT
    pts = []
    for i in range(n):
        yy = sy - (hstep if i % 2 else 0)
        pts += [(x0 + i * seg, yy), (x0 + (i + 1) * seg, yy)]
    o.append(f'<path d="M' + 'L'.join(f'{m(x)},{m(Y(y))}' for x, y in pts) + f'" fill="none" stroke="{ink}" stroke-width="{m(thin)}"/>')
    for i in range(n + 1):
        x = x0 + i * seg
        o.append(f'<path d="M{m(x)},{m(Y(sy - hstep))}L{m(x)},{m(Y(sy + 1.2))}" stroke="{ink}" stroke-width="{m(thin)}"/>')
        if i in show:
            text(x, sy + 1.2 + TXT, nums[i], extra=' text-anchor="middle"')
    # legend: one swatch per colour used
    y = row_y + 4
    x = 4
    for key, spec in legend.items():
        lab = LAB.get(key, key)
        wi = 6 + 1.5 + tw(lab, TXT) + 5
        if x + wi > W - 4 and x > 4:
            x, y = 4, y + TXT + 3
        top = y - 3.2
        if spec[0] == 'fill':
            st = f' stroke="{spec[2]}" stroke-width="{m(float(S[spec[3]]))}"' if spec[2] else f' stroke="{S["path"]}" stroke-width="{m(thin)}"'
            o.append(f'<rect x="{m(x)}" y="{m(Y(top))}" width="{m(6)}" height="{m(3.5)}" fill="{spec[1]}"{st}/>')
        elif spec[0] == 'line':
            da = f' stroke-dasharray="{m(spec[3][0])} {m(spec[3][1])}"' if spec[3] else ''
            o.append(f'<path d="M{m(x)},{m(Y(top + 1.75))}L{m(x + 6)},{m(Y(top + 1.75))}" stroke="{spec[1]}" stroke-width="{m(float(S[spec[2]]))}"{da}/>')
        elif spec[0] == 'dot':
            o.append(f'<circle cx="{m(x + 3)}" cy="{m(Y(top + 1.75))}" r="{m(1.5)}" fill="{spec[1]}"/>')
        elif spec[0] == 'text':
            o.append(f'<rect x="{m(x)}" y="{m(Y(top - 0.4))}" width="{m(6)}" height="{m(4.3)}" fill="{S["new"]}"/>')
            o.append(f'<text x="{m(x + 3)}" y="{m(Y(top + 3.0))}" font-size="{TXT * k:.2f}" text-anchor="middle" fill="{spec[1]}">{storeys(4)}</text>')
        else:
            o.append(symbol(spec[0], x * k + 3 * k, Y(top + 1.75) * k, k))
        text(x + 7.5, y, lab)
        x += wi
    # source line, wrapped to the width
    y += TXT + 3
    words, cur = CREDIT.split(), ''
    for w_ in words:
        if cur and tw(cur + ' ' + w_, TXT) > W - 8:
            text(4, y, cur)
            y, cur = y + TXT + 1.5, w_
        else:
            cur = (cur + ' ' + w_).strip()
    if cur:
        text(4, y, cur)
    return o, max(float(CFG['legend_mm']), y + 3)


# ---------------- the plans ----------------
made = []
fig_scale = CFG.get('figure_ground_scale')
FRAMES = layout_frames()                                 # a framed plan takes its frame's scale and size
frame = FRAMES.get('site-plan')
site_scale = int(frame and frame[0] or CFG['site_plan_scale'])
cx_new = unary_union([g for p, g in NEW]).centroid if NEW else site.centroid

details = []
for i, a in enumerate(CFG.get('detail_areas') or []):
    name = a.get('name') or 'detail-area-%d' % (i + 1)
    title = a.get('title') or LAB.get(name) or name.replace('-', ' ').capitalize()
    fr = FRAMES.get(name)
    scale = int(fr and fr[0] or a.get('scale') or 0)
    if not scale:
        made.append(dict(name=name, drawn=False, fits=False, reason='no scale given in config.json'))
        continue
    anchor, why = anchor_of(a.get('at'))
    if anchor is None:
        made.append(dict(name=name, drawn=False, fits=False, reason=why))
        continue
    win, cut = (fitted(name, title, scale, 'detail', lambda m: detail_window(anchor, scale, m), fr[1:]) if fr
                else detail_window(anchor, scale))
    details.append((name, title, scale, win, cut, a))

outlines = [(t, w) for n, t, s, w, c, a in details]
sp_of = lambda m: clamp(pad(site.bounds, CFG['site_pad_m']), site_scale, (cx_new.x, cx_new.y), m)
sp_win, sp_cut = fitted('site-plan', LAB['site-plan'], site_scale, 'site', sp_of, frame[1:], outlines) if frame else sp_of(None)
e = draw_plan('site-plan', LAB['site-plan'], site_scale, sp_win, 'site', outlines)
e['cropped'] = sp_cut
made.append(e)

for name, title, scale, win, cut, a in details:
    e = draw_plan(name, title, scale, win, 'detail')
    e.update(cropped=cut, at=a.get('at'), shows=a.get('shows', ''), page=a.get('page', ''))
    made.append(e)

if fig_scale:
    fig_scale = int(fig_scale)
    kb = None
    kp = os.path.join(SITE, 'kit.json')
    if os.path.exists(kp):
        kb = json.load(open(kp, encoding='utf8')).get('bbox')
    want = transform(TO_M, box(*kb)).bounds if kb else pad(site.bounds, CFG['fg_pad_m'])
    fg_win, fg_cut = clamp(want, fig_scale, (site.centroid.x, site.centroid.y))
    e = draw_plan('figure-ground', LAB['figure-ground'], fig_scale, fg_win, 'figure-ground')
    e['cropped'] = fg_cut
    made.append(e)
else:
    made.append(dict(name='figure-ground', drawn=False, fits=False, reason='no figure_ground_scale in config.json'))

for e in made:
    e.setdefault('drawn', True)
json.dump(made, open(os.path.join(OUT, 'drawings.json'), 'w', encoding='utf8'), indent=1, ensure_ascii=False)
print(json.dumps(made, indent=1, ensure_ascii=False))
