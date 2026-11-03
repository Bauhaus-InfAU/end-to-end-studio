"""Check plan of massing.geojson at the brief's site plan scale, and a bird's-eye check view.
Fallback look (no drawing-graphics standard): black lines on white, greys by height.

    python draw.py --proposal <proposal folder> --site <site folder>

Reads <proposal>/massing/config.json for `site_plan_scale` (the brief's, with its page) and `epsg`.
"""
import argparse, json, math, sys, subprocess, os
from shapely.geometry import shape, box
from shapely.ops import transform
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


A = argparse.ArgumentParser(description='Check drawings of the massing.')
A.add_argument('--proposal', required=True)
A.add_argument('--site', required=True)
ARGS = A.parse_args()
RUN = os.path.join(ARGS.proposal, '')
OUT = os.path.join(RUN, 'massing', '')
SITE = ARGS.site
CFG, _ = read_config(OUT + 'config.json', ['site_plan_scale'])
SCALE = int(CFG['site_plan_scale'])
_c = shape(json.load(open(os.path.join(SITE, 'site.geojson'), encoding='utf8'))['features'][0]['geometry']).centroid
TO_M = pyproj.Transformer.from_crs(4326, CFG.get('epsg') or utm_epsg(_c.x, _c.y), always_xy=True).transform
_src = os.path.join(SITE, 'SOURCES.md')
CREDIT = ('Map data © OpenStreetMap contributors (ODbL, https://www.openstreetmap.org/copyright).'
          if os.path.exists(_src) and 'OpenStreetMap' in open(_src, encoding='utf8').read() else '')

F = json.load(open(OUT + 'massing.geojson', encoding='utf8'))['features']
site = transform(TO_M, shape(json.load(open(os.path.join(SITE, 'site.geojson'), encoding='utf8'))['features'][0]['geometry']))
G = [(f['properties'], transform(TO_M, shape(f['geometry']))) for f in F]
ctx_all = [(f['properties'], transform(TO_M, shape(f['geometry']))) for f in json.load(open(os.path.join(SITE, 'buildings.geojson'), encoding='utf8'))['features']]
pad = 120
X0, Y0, X1, Y1 = site.bounds
X0 -= pad; Y0 -= pad; X1 += pad; Y1 += pad + 60
frame = box(X0, Y0, X1, Y1)
ctx = [(p, g) for p, g in ctx_all if g.intersects(frame) and not site.contains(g.representative_point())]
W, H = X1 - X0, Y1 - Y0


def grey(fl, lo=2, hi=8):
    t = (min(max(fl, lo), hi) - lo) / (hi - lo)
    v = int(225 - t * 175)
    return '#%02x%02x%02x' % (v, v, v)


def P(x, y): return x - X0, Y1 - y


def d(g):
    out = []
    gs = [g] if g.geom_type in ('Polygon', 'LineString', 'Point') else list(g.geoms)
    for q in gs:
        if q.geom_type == 'Polygon':
            for r in [q.exterior, *q.interiors]:
                out.append('M' + 'L'.join('%.1f,%.1f' % P(*c) for c in r.coords) + 'Z')
        elif q.geom_type == 'LineString':
            out.append('M' + 'L'.join('%.1f,%.1f' % P(*c) for c in q.coords))
    return ''.join(out)


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


# ---------------- plan ----------------
sw = SCALE / 3000  # line width in metres, so lines keep their width on paper at any scale
o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W / SCALE * 1000:.0f}mm" height="{H / SCALE * 1000 + 40:.0f}mm" '
     f'viewBox="0 0 {W:.0f} {H + 120:.0f}" font-family="Arial, Helvetica, sans-serif">',
     f'<rect width="{W:.0f}" height="{H + 120:.0f}" fill="#fff"/>']
for p, g in G:
    if p['kind'] == 'open-space':
        fill = {'park': '#f0f0f0', 'garden': '#f6f6f6', 'square': '#ffffff', 'water': '#e4e4e4'}[p['use']]
        o.append(f'<path d="{d(g)}" fill="{fill}" stroke="#999" stroke-width="0.4"/>')
for p, g in G:
    if p['kind'] == 'street':
        wdt = p.get('width', 10)
        o.append(f'<path d="{d(g)}" fill="none" stroke="#bbb" stroke-width="{wdt:.1f}" stroke-linecap="round" stroke-linejoin="round" stroke-opacity="0.35"/>')
for p, g in G:
    if p['kind'] == 'tree':
        o.append(f'<circle cx="{P(g.x, g.y)[0]:.1f}" cy="{P(g.x, g.y)[1]:.1f}" r="2.2" fill="none" stroke="#777" stroke-width="0.4"/>')
for p, g in ctx:
    o.append(f'<path d="{d(g)}" fill="#fff" stroke="#aaa" stroke-width="0.5"/>')
o.append(f'<path d="{d(site)}" fill="none" stroke="#000" stroke-width="1.6" stroke-dasharray="12 5"/>')
for p, g in G:
    if p['kind'] == 'building' and p['existing']:
        o.append(f'<path d="{d(g)}" fill="#fff" stroke="#000" stroke-width="0.6"/>')
labels = []
for p, g in G:
    if p['kind'] == 'building' and not p['existing']:
        o.append(f'<path d="{d(g)}" fill="{grey(p["floors"])}" stroke="#000" stroke-width="0.9"/>')
        c = g.representative_point(); x, y = P(c.x, c.y)
        col = '#fff' if p['floors'] >= 5 else '#000'
        tag = {'school': 'S', 'indoor pool': 'B'}.get(p['use'], '')
        if 'daycare' in p['use']: tag = 'K'
        labels.append(f'<text x="{x:.1f}" y="{y + 2.5:.1f}" font-size="7.5" text-anchor="middle" fill="{col}">{tag}{p["floors"]}</text>')
o += labels
# north arrow, scale bar, legend, title
bx, by = 20, H + 20
o.append(f'<text x="{bx}" y="{by}" font-size="16" font-weight="bold">Massing check plan, 1:{SCALE}</text>')
o.append(f'<text x="{bx}" y="{by + 16}" font-size="8">New buildings grey by height, number = storeys (S school, B indoor pool, K with daycare); kept buildings in outline; dashed: project site. Check drawing, fallback look (no drawing-graphics standard).</text>')
o.append(f'<text x="{bx}" y="{by + 28}" font-size="7">{CREDIT} Structure plan, programme and climate from this proposal.</text>')
sx = bx
for i, fl in enumerate(range(2, 9)):
    o.append(f'<rect x="{sx + i * 34}" y="{by + 38}" width="30" height="12" fill="{grey(fl)}" stroke="#000" stroke-width="0.6"/>'
             f'<text x="{sx + i * 34 + 15}" y="{by + 60}" font-size="7" text-anchor="middle">{fl} fl.</text>')
s0 = bx + 300  # scale bar: 200 m in four 50 m steps, a line that steps up and down, ticks at every step
o.append(f'<path d="{"".join(f"M{s0 + i * 50},{by + 40 + 6 * (i % 2)}h50" for i in range(4))}{"".join(f"M{s0 + i * 50},{by + 40}v6" for i in range(5))}" fill="none" stroke="#000" stroke-width="0.6"/>')
for i in range(5):
    o.append(f'<text x="{s0 + i * 50}" y="{by + 58}" font-size="7" text-anchor="middle">{i * 50}{" m" if i == 4 else ""}</text>')
nx, ny = W - 40, 36  # north: a circle in outline, a line from its centre to the circle, pointing north
o.append(f'<circle cx="{nx}" cy="{ny}" r="14" fill="none" stroke="#000" stroke-width="0.9"/><line x1="{nx}" y1="{ny}" x2="{nx}" y2="{ny - 14}" stroke="#000" stroke-width="0.9"/>')
o.append('</svg>')
svgp = OUT + 'massing.svg'
open(svgp, 'w', encoding='utf8').write('\n'.join(o))
pw = 2600
shot(svgp, OUT + 'massing.png', pw, int(pw * (H + 120) / W))

# ---------------- bird's-eye ----------------
az = math.radians(-30)  # view from the south-south-west, looking north-north-east
el = math.radians(40)
ca, sa = math.cos(az), math.sin(az)


def rot(x, y):
    xr = (x - X0) * ca - (y - Y0) * sa
    yr = (x - X0) * sa + (y - Y0) * ca
    return xr, yr


def proj(x, y, z):
    xr, yr = rot(x, y)
    return xr, -(yr * math.sin(el) + z * math.cos(el))


items = []
for p, g in ctx:
    items.append((g, (p.get('height') or 3.0), 'ctx'))
for p, g in G:
    if p['kind'] == 'building':
        items.append((g, float(p.get('height_m') or 3.0), 'kept' if p['existing'] else 'new'))
pts = [proj(x, y, z) for x, y in [(X0, Y0), (X1, Y0), (X0, Y1), (X1, Y1)] for z in (0, 30)]
mx, Mx = min(q[0] for q in pts), max(q[0] for q in pts)
my, My = min(q[1] for q in pts), max(q[1] for q in pts)
VW, VH = Mx - mx + 40, My - my + 80


def Q(x, y, z):
    a, b = proj(x, y, z)
    return a - mx + 20, b - my + 60


def poly(cs): return 'M' + 'L'.join('%.1f,%.1f' % c for c in cs) + 'Z'


face = {'new': ('#d9d9d9', '#9a9a9a', '#6e6e6e'), 'kept': ('#ffffff', '#e6e6e6', '#cfcfcf'), 'ctx': ('#fafafa', '#ececec', '#dedede')}
items.sort(key=lambda it: -rot(it[0].centroid.x, it[0].centroid.y)[1])
o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{VW:.0f}" height="{VH:.0f}" viewBox="0 0 {VW:.0f} {VH:.0f}" font-family="Arial, Helvetica, sans-serif">',
     f'<rect width="{VW:.0f}" height="{VH:.0f}" fill="#fff"/>',
     f'<path d="{poly([Q(x, y, 0) for x, y in site.exterior.coords])}" fill="#f7f7f7" stroke="#000" stroke-width="1" stroke-dasharray="8 4"/>']
for p, g in G:
    if p['kind'] == 'open-space' and p['use'] in ('park', 'water'):
        for q in ([g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))):
            if q.geom_type == 'Polygon':
                o.append(f'<path d="{poly([Q(x, y, 0) for x, y in q.exterior.coords])}" fill="#ececec" stroke="none"/>')
for g, h, k in items:
    for q in ([g] if g.geom_type == 'Polygon' else list(g.geoms)):
        cs = list(q.exterior.coords)
        if q.exterior.is_ccw is False: cs = cs[::-1]
        roof, lit, dark = face[k]
        lw = 0.5 if k == 'new' else 0.3
        st = '#000' if k == 'new' else '#999'
        walls = []
        for (x1, y1), (x2, y2) in zip(cs[:-1], cs[1:]):
            nxv, nyv = (y2 - y1), -(x2 - x1)  # outward normal for ccw
            nxr, nyr = rot(X0 + nxv, Y0 + nyv)
            if nyr < 0:  # faces the viewer
                shade = lit if nxr < 0 else dark
                walls.append(f'<path d="{poly([Q(x1, y1, 0), Q(x2, y2, 0), Q(x2, y2, h), Q(x1, y1, h)])}" fill="{shade}" stroke="{st}" stroke-width="{lw}"/>')
        o += walls
        o.append(f'<path d="{poly([Q(x, y, h) for x, y in cs])}" fill="{roof}" stroke="{st}" stroke-width="{lw}"/>')
o.append(f'<text x="20" y="28" font-size="18" font-weight="bold">Massing check, bird\'s-eye from the south-south-west</text>')
o.append(f'<text x="20" y="46" font-size="10">New buildings grey, kept buildings white, neighbours pale; heights true to the plan scale, no exaggeration. A check, not a panel drawing. {CREDIT}</text>')
o.append('</svg>')
svgp = OUT + 'massing_3d.svg'
open(svgp, 'w', encoding='utf8').write('\n'.join(o))
pw = 2600
shot(svgp, OUT + 'massing_3d.png', pw, int(pw * VH / VW))
print('ok', W, H, VW, VH)
