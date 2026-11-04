"""The phasing plan and the panel table, in the drawing standard.

    python draw.py --proposal <proposal folder> --site <site folder> --style <proposal>/drawing-graphics/style.json
                   [--config <proposal>/phasing/config.json] [--size large|small]

Reads phasing/phasing.geojson, phases.csv and stats.json (written by phasing.py), the scales from config.json
(scale_large, scale_small) and the look from style.json; without style.json it stops. Large: every building toned by
its phase; small: only the phases' outlines and numbers. Buildings flagged for review are untoned with a dashed outline
and a mark, invalid footprints dotted with their own mark, buildings that fail a stage check outlined in the accent.
Labels are English unless config.json has "labels": {"value": {...}} in the brief's language.
Writes phasing_<size>.svg and .png and phases_table.svg and .png into phasing/. No text below 3.2 mm (12 px) printed.
Needs shapely and pyproj; the PNG needs Chrome or Edge (or Chromium) for a headless screenshot.
"""
import argparse, csv, json, math, os, re, subprocess, sys
from html import escape
from pathlib import Path

try:
    import pyproj
    from shapely.geometry import shape, box
    from shapely.ops import transform, unary_union
except ImportError as e:
    sys.exit(f'needs shapely and pyproj ({e.name} is missing): pip install shapely pyproj')

FLOOR_MM = 3.2          # 12 px, 9 pt
PX_PER_MM = 4
LABELS = {'title': 'Phasing', 'phase': 'Phase', 'existing': 'Existing buildings', 'review': 'Phase under review',
          'invalid': 'Invalid footprint', 'fails': 'Fails a check while later phases are built', 'street': 'Street of phase',
          'homes': 'Homes', 'residents': 'Residents (estimate)', 'facilities': 'Facilities', 'open_space': 'Open space m2',
          'access': 'Access', 'total': 'Total'}


def die(msg):
    sys.exit('draw: ' + msg)


def shot(svg, png, w, h):
    exe = next((e for e in [r'C:/Program Files/Google/Chrome/Application/chrome.exe',
                            r'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
                            r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
                            r'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
                            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
                            '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome'] if os.path.exists(e)), None)
    if exe is None:
        die('no Chrome, Edge or Chromium found for the PNG; the SVG is written')
    html = str(svg).replace('.svg', '_wrap.html')
    Path(html).write_text(f'<html><body style="margin:0"><img src="{Path(svg).name}" style="width:{w}px;height:{h}px"></body></html>',
                          encoding='utf-8')
    subprocess.run([exe, '--headless', '--disable-gpu', '--hide-scrollbars', f'--screenshot={os.path.abspath(png)}',
                    f'--window-size={w},{h}', 'file:///' + os.path.abspath(html).replace('\\', '/')], capture_output=True, timeout=180)
    os.remove(html)
    if not os.path.exists(png) or os.path.getsize(png) == 0:
        die(f'the PNG {png} was not written')


def tw(s, size):
    return len(s) * size * 0.56


def check_text(svg_lines, k):
    """Every font-size, in mm on paper, at least the floor."""
    for s in svg_lines:
        for v in re.findall(r'font-size="([\d.]+)"', s):
            if float(v) / k < FLOOR_MM - 1e-6:
                die(f'text of {float(v) / k:.2f} mm, below the {FLOOR_MM} mm floor')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proposal', required=True)
    ap.add_argument('--site', required=True)
    ap.add_argument('--style', required=True)
    ap.add_argument('--config')
    ap.add_argument('--size', choices=('large', 'small'), default='large')
    a = ap.parse_args()
    P = Path(a.proposal)
    OUT = P / 'phasing'
    if not Path(a.style).exists():
        die(f'no drawing standard at {a.style}: run the drawing standard first; no plan drawn')
    S = json.loads(Path(a.style).read_text(encoding='utf-8'))
    for k in ('paper', 'ink', 'accent', 'existing', 'context', 'street', 'path', 'ramp', 'font', 'thin', 'mid', 'thick', 'text', 'title'):
        if k not in S:
            die(f'style.json has no {k}')
    for f in ('phasing.geojson', 'phases.csv', 'stats.json'):
        if not (OUT / f).exists():
            die(f'no phasing/{f}: run phasing.py first')
    cfg = json.loads(Path(a.config or OUT / 'config.json').read_text(encoding='utf-8'))
    scale = int(cfg['scale_large' if a.size == 'large' else 'scale_small']['value'])
    lab = dict(LABELS, **((cfg.get('labels') or {}).get('value') or {}))
    stats = json.loads((OUT / 'stats.json').read_text(encoding='utf-8'))
    EPSG = int(stats['epsg'])
    TO_M = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform
    fc = json.loads((OUT / 'phasing.geojson').read_text(encoding='utf-8'))
    F = [(f['properties'], transform(TO_M, shape(f['geometry']))) for f in fc['features'] if f.get('geometry')]
    site = transform(TO_M, unary_union([shape(f['geometry']) for f in
                                        json.loads((Path(a.site) / 'site.geojson').read_text(encoding='utf-8'))['features']]))
    phases = sorted({p['phase'] for p, _ in F if p['kind'] == 'phase'})
    n = max(phases) if phases else 0
    ramp = S['ramp']
    tone = {k: ramp[min(len(ramp) - 1, round((len(ramp) - 1) * (n - k + 1) / max(n, 1)))] for k in range(1, n + 1)}

    k = scale / 1000.0                  # metres per mm on paper
    TXT = max(FLOOR_MM, float(S['text']))
    TITLE = max(TXT, float(S['title']))
    pad = 0.05 * max(site.bounds[2] - site.bounds[0], site.bounds[3] - site.bounds[1])
    x0, y0, x1, y1 = site.buffer(pad).bounds
    Wm, Hm = x1 - x0, y1 - y0
    W = Wm / k
    fr = box(x0, y0, x1, y1)
    Pt = lambda x, y: (x - x0, y1 - y)
    f2 = lambda v: '%.2f' % v
    lw = lambda key: float(S[key]) * k

    def d(g):
        if g.is_empty:
            return ''
        if g.geom_type == 'Polygon':
            return ''.join('M' + 'L'.join('%.2f,%.2f' % Pt(*c[:2]) for c in r.coords) + 'Z' for r in [g.exterior, *g.interiors])
        if g.geom_type in ('LineString', 'LinearRing'):
            return 'M' + 'L'.join('%.2f,%.2f' % Pt(*c[:2]) for c in g.coords)
        return ''.join(d(q) for q in getattr(g, 'geoms', []))

    o = ['<g clip-path="url(#map)">', f'<rect width="{f2(Wm)}" height="{f2(Hm)}" fill="{S["paper"]}"/>']
    legend = []
    # phase land, lightly, then the streets by phase
    for p, g in F:
        if p['kind'] == 'phase':
            op = '0.25' if a.size == 'large' else '0.6'
            o.append(f'<path d="{d(g)}" fill="{tone[p["phase"]]}" fill-opacity="{op}" stroke="{S["ink"]}" stroke-width="{f2(lw("mid"))}"/>')
    for p, g in F:
        if p['kind'] == 'street' and g.intersects(fr):
            col = S['path'] if p['existing'] or p['phase'] is None else tone.get(p['phase'], S['path'])
            o.append(f'<path d="{d(g)}" fill="none" stroke="{col}" stroke-width="{f2(lw("thick"))}" stroke-linecap="round"/>')
    o.append(f'<path d="{d(site.exterior)}" fill="none" stroke="{S["ink"]}" stroke-width="{f2(lw("mid"))}" '
             f'stroke-dasharray="{f2(3 * k)} {f2(1.5 * k)}"/>')
    marks = []
    if a.size == 'large':
        for p, g in F:
            if p['kind'] != 'building' or not g.intersects(fr):
                continue
            if p['existing']:
                o.append(f'<path d="{d(g)}" fill="none" stroke="{S["ink"]}" stroke-width="{f2(lw("thin"))}"/>')
            elif not p['geometry_valid']:
                o.append(f'<path d="{d(g)}" fill="none" stroke="{S["ink"]}" stroke-width="{f2(lw("mid"))}" '
                         f'stroke-dasharray="{f2(0.4 * k)} {f2(0.6 * k)}"/>')
                marks.append(('invalid', g.envelope.centroid))
            elif p['phase'] is None:
                o.append(f'<path d="{d(g)}" fill="none" stroke="{S["ink"]}" stroke-width="{f2(lw("mid"))}" '
                         f'stroke-dasharray="{f2(1.5 * k)} {f2(1 * k)}"/>')
                marks.append(('review', g.representative_point()))
            else:
                o.append(f'<path d="{d(g)}" fill="{tone[p["phase"]]}" stroke="{S["ink"]}" stroke-width="{f2(lw("thin"))}"/>')
            if p.get('fails'):
                o.append(f'<path d="{d(g)}" fill="none" stroke="{S["accent"]}" stroke-width="{f2(lw("thick"))}"/>')
    r = 1.6 * k
    for kind, c in marks:
        x, y = Pt(c.x, c.y)
        if kind == 'review':
            o.append(f'<circle cx="{f2(x)}" cy="{f2(y)}" r="{f2(r)}" fill="{S["paper"]}" stroke="{S["ink"]}" stroke-width="{f2(lw("mid"))}"/>')
        else:
            o.append(f'<path d="M{f2(x - r)},{f2(y - r)}L{f2(x + r)},{f2(y + r)}M{f2(x - r)},{f2(y + r)}L{f2(x + r)},{f2(y - r)}" '
                     f'stroke="{S["ink"]}" stroke-width="{f2(lw("mid"))}"/>')
    for p, g in F:   # the phase numbers
        if p['kind'] == 'phase':
            c = g.representative_point()
            x, y = Pt(c.x, c.y)
            o.append(f'<text x="{f2(x)}" y="{f2(y)}" font-size="{f2(TITLE * k)}" font-weight="bold" text-anchor="middle" '
                     f'fill="{S["ink"]}" paint-order="stroke" stroke="{S["paper"]}" stroke-width="{f2(0.6 * k)}">{p["phase"]}</text>')
    o.append('</g>')

    # the strip under the map: title, scale bar, legend
    st = []
    m_ = lambda v: f2(v * k)
    Yb = lambda y: Hm / k + y

    def text(x, y, s, size=TXT, extra=''):
        st.append(f'<text x="{m_(x)}" y="{m_(Yb(y))}" font-size="{f2(size * k)}" fill="{S["ink"]}"{extra}>{escape(str(s))}</text>')

    text(4, 3 + TITLE, f'{lab["title"]}, 1:{scale:,}', TITLE, ' font-weight="bold"')
    L = next((v for v in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000) if v >= Wm / 6), 10000)
    sx, sy = W - 4 - L / k, 3 + TITLE
    st.append(f'<path d="M{m_(sx)},{m_(Yb(sy))}L{m_(sx + L / k)},{m_(Yb(sy))}" stroke="{S["ink"]}" stroke-width="{m_(float(S["mid"]))}"/>')
    for x in (sx, sx + L / k):
        st.append(f'<path d="M{m_(x)},{m_(Yb(sy - 1.2))}L{m_(x)},{m_(Yb(sy + 1.2))}" stroke="{S["ink"]}" stroke-width="{m_(float(S["thin"]))}"/>')
    text(sx, sy - 1.8, '0', extra=' text-anchor="middle"')
    text(sx + L / k, sy - 1.8, f'{L} m', extra=' text-anchor="middle"')
    # the north arrow: grid north against true north at the site
    c = site.centroid
    back = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True).transform
    lon, lat = back(c.x, c.y)
    nx_, ny_ = TO_M(lon, lat + 0.001)
    ang = math.atan2(nx_ - c.x, ny_ - c.y)
    ax, ay, ar = sx - 10, sy - 2, 3.0
    st.append(f'<path d="M{m_(ax)},{m_(Yb(ay))}L{m_(ax + ar * math.sin(ang))},{m_(Yb(ay - ar * math.cos(ang)))}" '
              f'stroke="{S["ink"]}" stroke-width="{m_(2 * float(S["thin"]))}"/>')
    text(ax + ar * math.sin(ang), ay - ar * math.cos(ang) - 0.8, 'N', extra=' text-anchor="middle"')
    for kk in range(1, n + 1):
        legend.append(('fill', tone[kk], f'{lab["phase"]} {kk}'))
    if a.size == 'large':
        names = {p.get('basis') for p, _ in F if p['kind'] == 'building'}
        if any(p['kind'] == 'building' and p['existing'] for p, _ in F):
            legend.append(('outline', None, lab['existing']))
        if 'review' in names and any(p['kind'] == 'building' and p['phase'] is None and p['geometry_valid'] and not p['existing'] for p, _ in F):
            legend.append(('review', None, lab['review']))
        if any(p['kind'] == 'building' and not p['geometry_valid'] for p, _ in F):
            legend.append(('invalid', None, lab['invalid']))
        if any(p['kind'] == 'building' and p.get('fails') for p, _ in F):
            legend.append(('fails', None, lab['fails']))
    y, x = 3 + TITLE + TXT + 4, 4
    for kind, col, label in legend:
        wi = 8 + 1.5 + tw(label, TXT) + 5
        if x + wi > W - 4 and x > 4:
            x, y = 4, y + TXT + 3
        top = y - TXT * 0.8
        if kind == 'fill':
            st.append(f'<rect x="{m_(x)}" y="{m_(Yb(top))}" width="{m_(8)}" height="{m_(3.5)}" fill="{col}" stroke="{S["ink"]}" stroke-width="{m_(float(S["thin"]))}"/>')
        else:
            dash = {'review': f' stroke-dasharray="{m_(1.5)} {m_(1)}"', 'invalid': f' stroke-dasharray="{m_(0.4)} {m_(0.6)}"'}.get(kind, '')
            colr = S['accent'] if kind == 'fails' else S['ink']
            wd = S['thick'] if kind == 'fails' else S['mid']
            st.append(f'<rect x="{m_(x)}" y="{m_(Yb(top))}" width="{m_(8)}" height="{m_(3.5)}" fill="none" stroke="{colr}" stroke-width="{m_(float(wd))}"{dash}/>')
        text(x + 9.5, y, label)
        x += wi
    Hs = (y + 4) * k
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" height="{(Hm + Hs) / k:.1f}mm" '
           f'viewBox="0 0 {f2(Wm)} {f2(Hm + Hs)}" font-family="{escape(S["font"])}">',
           f'<defs><clipPath id="map"><rect width="{f2(Wm)}" height="{f2(Hm)}"/></clipPath></defs>',
           f'<rect width="{f2(Wm)}" height="{f2(Hm + Hs)}" fill="{S["paper"]}"/>'] + o + st + ['</svg>']
    check_text(svg, k)
    name = f'phasing_{a.size}'
    svgp = OUT / (name + '.svg')
    svgp.write_text('\n'.join(svg), encoding='utf-8')
    shot(svgp, OUT / (name + '.png'), int(W * PX_PER_MM), int((Hm + Hs) / k * PX_PER_MM))

    # ---- the table for the panel, at 1:1 in mm ----
    rows = list(csv.DictReader((OUT / 'phases.csv').open(encoding='utf-8')))
    head = [lab['phase'], lab['homes'], lab['residents'], lab['facilities'], lab['open_space'], lab['access']]
    body = [[lab['total'] if r['phase'] == 'total' else r['phase'], r['homes'], r['residents'], r['facilities'] or '-',
             r['open_space_m2'], r['access']] for r in rows]
    widths = [max(tw(str(row[i]), TXT) for row in [head] + body) + 4 for i in range(len(head))]
    rh = TXT + 2.5
    Wt, Ht = sum(widths) + 2, rh * (len(body) + 1) + 2
    t = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{Wt:.1f}mm" height="{Ht:.1f}mm" viewBox="0 0 {Wt:.2f} {Ht:.2f}" '
         f'font-family="{escape(S["font"])}">', f'<rect width="{Wt:.2f}" height="{Ht:.2f}" fill="{S["paper"]}"/>']
    for ri, row in enumerate([head] + body):
        yy = 1 + rh * (ri + 1) - 1.6
        x = 1
        if 1 <= ri <= n and str(row[0]).isdigit() and int(row[0]) in tone:
            t.append(f'<rect x="1" y="{1 + rh * ri:.2f}" width="3" height="{rh:.2f}" fill="{tone[int(row[0])]}"/>')
        for i, cell in enumerate(row):
            weight = ' font-weight="bold"' if ri == 0 or row[0] == lab['total'] else ''
            t.append(f'<text x="{x + (4 if i == 0 else 0):.2f}" y="{yy:.2f}" font-size="{TXT:.2f}" fill="{S["ink"]}"{weight}>{escape(str(cell))}</text>')
            x += widths[i]
        t.append(f'<path d="M1,{1 + rh * (ri + 1):.2f}H{Wt - 1:.2f}" stroke="{S["ink"]}" stroke-width="{float(S["thin"]) * (2 if ri == 0 else 1):.2f}"/>')
    t.append('</svg>')
    check_text(t, 1.0)
    tp = OUT / 'phases_table.svg'
    tp.write_text('\n'.join(t), encoding='utf-8')
    shot(tp, OUT / 'phases_table.png', int(Wt * PX_PER_MM), int(Ht * PX_PER_MM))
    print(f'wrote {svgp.name}, {name}.png, phases_table.svg and .png into {OUT}')


if __name__ == '__main__':
    main()
