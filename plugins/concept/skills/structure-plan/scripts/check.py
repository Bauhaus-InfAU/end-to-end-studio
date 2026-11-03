"""The checks of a structure plan, and a check plan to look at.

    python check.py --proposal <proposal folder> --site <site folder> [--climate <folder>] [--distance 150]
                    [--style style.json]

Reads <proposal>/structure-plan/structure-plan.geojson, the site and, if there is one, the climate's rules.geojson
(default <proposal>/climate). Writes into <proposal>/structure-plan/: checks.txt, check-plan.svg and check-plan.png.
build.py runs it after every build; it also runs alone.
"""
import argparse, html, json, math, os, subprocess, sys
from pathlib import Path

from shapely.geometry import shape, Point
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frame import Frame, parts

DEFAULTS = {
    'distance_m': 150,          # proximity: new land within this straight-line distance of a centre or public green
    'route_buffer_m': 10,       # a route takes this much land on each side when looking for unassigned land
    'loose_end_m': 20,          # a route end farther than this from every other route, street, gateway and the boundary is loose
    'listed': 10,               # at most this many pieces are listed under a check
    'min_piece_m2': 25,         # pieces smaller than this are left out of the lists
    'check_scale': 10000,       # scale of the check plan
    'margin_m': 60,             # the check plan shows this much around the site
    'png_dpi': 150,             # resolution of the PNG
}
C = DEFAULTS

# fallback look: black on white, greys, one accent. A drawing standard overrides it through --style.
STYLE = {'paper': '#ffffff', 'ink': '#1a1a1a', 'accent': '#c8442b', 'context': '#e4e4e4', 'park': '#c9dcbc',
         'font': 'Arial, Helvetica, sans-serif', 'thin': 0.13, 'mid': 0.25, 'thick': 0.5, 'text': 3.2, 'title': 5.6}
GREY = {'keep': 0.10, 'change': 0.18, 'new': 0.28}          # neighbourhoods: share of ink in the paper, by action
ROUTE = {'main': ('thick', None), 'local': ('mid', None), 'landscape': ('mid', (1.2, 0.8))}


def mix(c1, c2, f):
    a = [int(c1.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    return '#%02x%02x%02x' % tuple(round(x + (y - x) * f) for x, y in zip(a, b))


def ha(g):
    return g.area / 1e4


def at(g):
    p = g.representative_point()
    return f'({p.x:.0f},{p.y:.0f})'


def pieces(g):
    return sorted([q for q in parts(g) if q.area >= C['min_piece_m2']], key=lambda q: -q.area)[:C['listed']]


def read_plan(path, F):
    """The plan's features as (properties, geometry in local metres, problems)."""
    out = []
    for f in json.loads(Path(path).read_text(encoding='utf-8')).get('features') or []:
        p, raw = f.get('properties') or {}, f.get('geometry')
        g0 = shape(raw) if raw else None
        bad = []
        if g0 is None or g0.is_empty:
            bad.append('empty geometry')
        elif not g0.is_valid:
            bad.append('invalid geometry')
        out.append((p, F.local(g0) if g0 is not None and not g0.is_empty else None, bad))
    return out


def checks(feats, F, distance):
    L = []
    by = lambda k: [(p, g) for p, g, b in feats if p.get('kind') == k and g is not None]
    nb, gr, ce, ro, ga = (by(k) for k in ('neighbourhood', 'green', 'centre', 'route', 'gateway'))
    w = max([len(str(p.get('name', ''))) for p, g, b in feats] + [10])
    L.append(f'site {ha(F.site):.1f} ha')
    L.append('')
    L.append('NEIGHBOURHOODS')
    for p, g in nb:
        noise = ''.join(f'  noise {k}: {ha(g.intersection(z)):.2f} ha' for k, z in sorted(F.noise.items()))
        L.append(f"  {p.get('name', ''):<{w}}  {p.get('action', ''):<6} {ha(g):7.2f} ha{noise}")
    for a in ('new', 'change', 'keep'):
        L.append(f"  total {a}: {sum(ha(g) for p, g in nb if p.get('action') == a):.2f} ha")
    for ph in sorted({str(p['phase']) for p, g in nb if p.get('phase') is not None}):
        part = [(p, g) for p, g in nb if str(p.get('phase')) == ph]
        L.append(f"  phase {ph}: {sum(p.get('homes') or 0 for p, g in part)} homes on {sum(ha(g) for p, g in part):.2f} ha")
    if any(p.get('action') in ('new', 'change') and p.get('phase') is None for p, g in nb):
        L.append('  some new or changed neighbourhoods have no phase: the homes per phase cannot be checked')
    taken = unary_union([g for p, g in nb + gr + ce] + [g.buffer(C['route_buffer_m']) for p, g in ro])
    left = F.site.difference(taken)
    L.append(f'  site assigned to nothing (not a neighbourhood, green, centre or within {C["route_buffer_m"]} m of a route): '
             f'{ha(left):.2f} ha')
    for q in pieces(left):
        L.append(f'     {ha(q):.2f} ha at {at(q)}')
    L.append('')
    L.append('GREEN')
    for p, g in gr:
        pub = '' if p.get('public', True) is not False else '  not public'
        L.append(f"  {p.get('name', ''):<{w}}  {p.get('action', ''):<6} {ha(g):7.2f} ha  roles {p.get('roles')}{pub}")
    public = unary_union([g for p, g in gr if p.get('public', True) is not False])
    L.append(f'  total public green: {ha(public):.2f} ha')
    L.append('')
    L.append('CENTRES')
    for p, g in ce:
        holds = p.get('holds') or 'nothing (the massing can build nothing there)'
        L.append(f"  {p.get('name', ''):<{w}}  {p.get('level', ''):<6} {ha(g):7.2f} ha at {at(g)}  holds: {holds}")
    L.append('')
    L.append('PROXIMITY (straight line, not walking access)')
    land = unary_union([g for p, g in nb if p.get('action') in ('new', 'change')])
    near_any = unary_union([public] + [g for p, g in ce]).buffer(distance)
    near_c = unary_union([g for p, g in ce]).buffer(distance)
    if land.is_empty:
        L.append('  no new or changed neighbourhood: no share')
    else:
        for what, near in (('a public green or a centre', near_any), ('a centre', near_c)):
            L.append(f'  share of new and changed neighbourhood area within {distance:g} m of {what}: '
                     f'{100 * land.intersection(near).area / land.area:.0f} %')
        beyond = land.difference(near_any)
        L.append(f'  beyond {distance:g} m of a public green or a centre: {ha(beyond):.2f} ha')
        for q in pieces(beyond):
            L.append(f'     {ha(q):.2f} ha at {at(q)}')
    L.append('')
    L.append('ROUTES')
    for p, g in ro:
        L.append(f"  {p.get('name', ''):<{w}}  {p.get('level', ''):<9} {g.length:7.0f} m")
    gates = unary_union([g for p, g in ga])
    streets = unary_union([g for p, g in F.streets])
    edge, inside = F.site.boundary, F.site.buffer(1)
    loose = []
    for i, (p, g) in enumerate(ro):
        others = unary_union([h for j, (q, h) in enumerate(ro) if j != i])
        for line in parts(g):
            for xy in (line.coords[0], line.coords[-1]):
                e = Point(xy)
                if not inside.contains(e):
                    continue                     # it leaves the site: it joins the city
                d = min(x.distance(e) for x in (others, streets, gates, edge) if not x.is_empty)
                if d > C['loose_end_m']:
                    loose.append(f"     {p.get('name', '')} ends at ({e.x:.0f},{e.y:.0f}), {d:.0f} m from anything")
    L.append(f"  loose ends (more than {C['loose_end_m']} m from every other route, street, gateway and the site "
             f"boundary): {len(loose)}")
    L += loose
    L.append('')
    L.append('GEOMETRY')
    for what in ('invalid geometry', 'empty geometry'):
        hit = [f"{p.get('kind')} {p.get('name')}" for p, g, b in feats if what in b]
        L.append(f'  {what}: {len(hit)}' + (f" ({', '.join(hit)})" if hit else ''))
    counts = {}
    for p, g, b in feats:
        counts[p.get('kind')] = counts.get(p.get('kind'), 0) + 1
    L.append(f'  features: {len(feats)} {counts}')
    return L


# ---------------------------------------------------------------- the check plan
def find_browser():
    for e_ in [r'C:/Program Files/Google/Chrome/Application/chrome.exe',
               r'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
               r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
               r'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
               '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
               '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge']:
        if os.path.exists(e_):
            return e_
    import shutil
    for n in ('google-chrome', 'chromium', 'chromium-browser', 'msedge', 'chrome'):
        if shutil.which(n):
            return shutil.which(n)
    return None


def shot(svg, png, w_mm, h_mm):
    """A PNG of the SVG by a headless Chrome or Edge. Returns a note when it could not be made."""
    browser = find_browser()
    if not browser:
        return 'No Chrome or Edge found: no PNG made.'
    w, h = round(w_mm / 25.4 * C['png_dpi']), round(h_mm / 25.4 * C['png_dpi'])
    page = svg.with_name(svg.stem + '_wrap.html')
    page.write_text(f'<html><body style="margin:0"><img src="{svg.name}" style="width:{w}px;height:{h}px"></body></html>',
                    encoding='utf-8')
    if png.exists():
        png.unlink()
    subprocess.run([browser, '--headless', '--disable-gpu', '--hide-scrollbars', f'--screenshot={png.resolve()}',
                    f'--window-size={w},{h}', page.resolve().as_uri()], capture_output=True, timeout=180)
    page.unlink()
    return None if png.exists() else f'{png.name} was not made: the browser failed.'


def draw(feats, F, S, out_dir):
    k = 1000 / C['check_scale']                         # mm per metre
    fs = max(3.2, float(S.get('text', 3.2)))
    ft = max(fs, float(S.get('title', fs * 1.6)))
    thin, mid, thick = (float(S.get(n, d)) for n, d in (('thin', 0.13), ('mid', 0.25), ('thick', 0.5)))
    lw = {'thin': thin, 'mid': mid, 'thick': thick}
    ink, paper, accent = S['ink'], S['paper'], S['accent']
    x0, y0, x1, y1 = F.site.buffer(C['margin_m']).bounds
    pad = 8.0
    W = (x1 - x0) * k + 2 * pad
    Hm = (y1 - y0) * k + 2 * pad
    X = lambda x: pad + (x - x0) * k
    Y = lambda y: pad + (y1 - y) * k
    esc = lambda s: html.escape(str(s), quote=True)
    tw = lambda s, size=fs: len(str(s)) * size * 0.56

    def path(g):
        d = []
        for q in parts(g):
            if q.geom_type == 'Polygon':
                for ring in [q.exterior, *q.interiors]:
                    d.append('M' + 'L'.join(f'{X(x):.2f},{Y(y):.2f}' for x, y in ring.coords) + 'Z')
            elif 'LineString' in q.geom_type:
                for ln in parts(q):
                    d.append('M' + 'L'.join(f'{X(x):.2f},{Y(y):.2f}' for x, y in ln.coords))
        return ''.join(d)

    def text(x, y, s, size=fs, anchor='start', weight=None, halo=False):
        wt = f' font-weight="{weight}"' if weight else ''
        h = f' stroke="{paper}" stroke-width="{size * 0.25:.2f}" paint-order="stroke"' if halo else ''
        return (f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size:.2f}" text-anchor="{anchor}" fill="{ink}"{wt}{h}>'
                f'{esc(s)}</text>')

    by = lambda kd: [(p, g) for p, g, b in feats if p.get('kind') == kd and g is not None]
    o = [f'<g clip-path="url(#map)">']
    view = F.box(x0, y0, x1, y1)
    ctx = unary_union([g for p, g in F.buildings if g.intersects(view)])
    if not ctx.is_empty:
        o.append(f'<path d="{path(ctx)}" fill="{S.get("context", "#e4e4e4")}" fill-rule="evenodd"/>')
    for p, g in by('neighbourhood'):
        o.append(f'<path d="{path(g)}" fill="{mix(paper, ink, GREY.get(p.get("action"), 0.18))}" fill-opacity="0.85" '
                 f'fill-rule="evenodd" stroke="{ink}" stroke-width="{thin}"/>')
    for p, g in by('green'):
        o.append(f'<path d="{path(g)}" fill="{S.get("park", "#c9dcbc")}" fill-rule="evenodd" stroke="{ink}" '
                 f'stroke-width="{thin}"/>')
    for p, g in by('centre'):
        o.append(f'<path d="{path(g)}" fill="{accent}" fill-opacity="0.8" fill-rule="evenodd" stroke="{accent}" '
                 f'stroke-width="{mid}"/>')
    for p, g in by('route'):
        wd, dash = ROUTE.get(p.get('level'), ('mid', None))
        da = f' stroke-dasharray="{dash[0]} {dash[1]}"' if dash else ''
        o.append(f'<path d="{path(g)}" fill="none" stroke="{ink}" stroke-width="{lw[wd] * 2:.2f}"{da}/>')
    o.append(f'<path d="{path(F.site.boundary)}" fill="none" stroke="{ink}" stroke-width="{mid}" '
             f'stroke-dasharray="3 1.5"/>')
    for p, g in by('gateway'):
        o.append(f'<circle cx="{X(g.x):.2f}" cy="{Y(g.y):.2f}" r="1.6" fill="{paper}" stroke="{accent}" '
                 f'stroke-width="{thick}"/>')
    for kd in ('neighbourhood', 'green', 'centre'):
        for p, g in by(kd):
            q = g.representative_point()
            o.append(text(X(q.x), Y(q.y) + fs * 0.35, p.get('name', ''), anchor='middle', halo=True,
                          weight='bold' if kd == 'centre' else None))
    o.append('</g>')

    # the strip under the map: title, north, scale bar, legend
    s = []
    y = Hm + 2 + ft
    s.append(text(pad, y, f"Structure plan, check plan 1:{C['check_scale']:,}", ft, weight='bold'))
    r = 4.0
    nx, ny = W - pad - r, Hm + 2 + r
    c = F.site.centroid
    lon, lat = F.to_wgs(c).coords[0]
    ux, uy = F.to_local(lon, lat + 0.01)
    a = math.atan2(ux - c.x, uy - c.y)
    s.append(f'<circle cx="{nx:.2f}" cy="{ny:.2f}" r="{r}" fill="none" stroke="{ink}" stroke-width="{thin}"/>'
             f'<path d="M{nx:.2f},{ny:.2f}L{nx + r * math.sin(a):.2f},{ny - r * math.cos(a):.2f}" stroke="{ink}" '
             f'stroke-width="{thin * 2:.2f}"/>')
    # scale bar: one thin line stepping up and down, a tick at every step, numbers under, the unit on the last
    total, n = 500, 5
    seg, hstep = total / n * k, 1.5
    sy = y + 6 + hstep
    pts = []
    for i in range(n):
        yy = sy - (hstep if i % 2 else 0)
        pts += [(pad + i * seg, yy), (pad + (i + 1) * seg, yy)]
    s.append('<path d="M' + 'L'.join(f'{px:.2f},{py:.2f}' for px, py in pts) + f'" fill="none" stroke="{ink}" '
             f'stroke-width="{thin}"/>')
    for i in range(n + 1):
        px = pad + i * seg
        s.append(f'<path d="M{px:.2f},{sy - hstep:.2f}L{px:.2f},{sy + 1.2:.2f}" stroke="{ink}" stroke-width="{thin}"/>')
        if i % 2 == 0 or i == n:
            s.append(text(px, sy + 1.2 + fs, f'{i * total / n:g}' + (' m' if i == n else ''), anchor='middle'))
    # legend
    items = [('fill', mix(paper, ink, GREY[a_]), f'neighbourhood, {a_}') for a_ in ('keep', 'change', 'new')]
    items += [('fill', S.get('park', '#c9dcbc'), 'green'), ('fill', accent, 'centre'),
              ('line', 'thick', 'main route'), ('line', 'mid', 'local route'), ('dash', 'mid', 'landscape route'),
              ('dot', accent, 'gateway'), ('site', 'mid', 'site')]
    lx, ly = pad, sy + 1.2 + fs + 4 + fs
    for kind_, val, lab in items:
        wi = 7.5 + tw(lab) + 5
        if lx + wi > W - pad and lx > pad:
            lx, ly = pad, ly + fs + 3
        top = ly - fs * 0.85
        if kind_ == 'fill':
            s.append(f'<rect x="{lx:.2f}" y="{top:.2f}" width="6" height="3.5" fill="{val}" stroke="{ink}" '
                     f'stroke-width="{thin}"/>')
        elif kind_ == 'dot':
            s.append(f'<circle cx="{lx + 3:.2f}" cy="{top + 1.75:.2f}" r="1.6" fill="{paper}" stroke="{val}" '
                     f'stroke-width="{thick}"/>')
        else:
            da = {'dash': ' stroke-dasharray="1.2 0.8"', 'site': ' stroke-dasharray="3 1.5"'}.get(kind_, '')
            sw = lw[val] * (1 if kind_ == 'site' else 2)
            s.append(f'<path d="M{lx:.2f},{top + 1.75:.2f}h6" stroke="{ink}" stroke-width="{sw:.2f}"{da}/>')
        s.append(text(lx + 7.5, ly, lab))
        lx += wi
    H = ly + pad
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" height="{H:.1f}mm" viewBox="0 0 {W:.2f} {H:.2f}" '
           f'font-family="{esc(S.get("font", "Arial, Helvetica, sans-serif"))}">',
           f'<defs><clipPath id="map"><rect x="{pad}" y="{pad}" width="{W - 2 * pad:.2f}" height="{Hm - 2 * pad:.2f}"/>'
           f'</clipPath></defs>',
           f'<rect width="{W:.2f}" height="{H:.2f}" fill="{paper}"/>', *o, *s, '</svg>']
    out = out_dir / 'check-plan.svg'
    out.write_text('\n'.join(svg), encoding='utf-8')
    return shot(out, out_dir / 'check-plan.png', W, H)


def run(proposal, F, distance=None, style_path=None):
    """Writes checks.txt and the check plan for the proposal's structure plan; returns the checks as text."""
    out = Path(proposal) / 'structure-plan'
    plan = out / 'structure-plan.geojson'
    if not plan.exists():
        raise SystemExit(f'no structure-plan.geojson in {out}: run build.py first')
    distance = C['distance_m'] if distance is None else distance
    feats = read_plan(plan, F)
    L = checks(feats, F, distance)
    style_path = Path(style_path) if style_path else Path(proposal) / 'drawing-graphics' / 'style.json'
    S = dict(STYLE)
    if style_path.exists():
        S.update(json.loads(style_path.read_text(encoding='utf-8')))
    note = draw(feats, F, S, out)
    L.append('')
    L.append('check plan: check-plan.svg' + (f' ({note})' if note else ' and check-plan.png')
             + (f', look from {style_path.name}' if style_path.exists() else ', fallback look'))
    L.append('coordinates: metres from the south-west corner of the site, in its UTM zone')
    if F.missing:
        L.append('missing: ' + ', '.join(F.missing))
    text = '\n'.join(L) + '\n'
    (out / 'checks.txt').write_text(text, encoding='utf-8')
    return text


def climate_of(proposal, climate):
    if climate:
        return climate
    c = Path(proposal) / 'climate'
    return c if (c / 'rules.geojson').exists() else None


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='The checks of a structure plan, and a check plan.')
    ap.add_argument('--proposal', required=True)
    ap.add_argument('--site', required=True, help='the folder with site.geojson and its layers')
    ap.add_argument('--climate', help="the climate folder with rules.geojson (default: the proposal's climate/)")
    ap.add_argument('--distance', type=float, default=C['distance_m'], help='proximity distance, m')
    ap.add_argument('--style', help="the drawing standard's style.json (default: the proposal's drawing-graphics/)")
    A = ap.parse_args()
    print(run(A.proposal, Frame(A.site, climate_of(A.proposal, A.climate)), A.distance, A.style))
