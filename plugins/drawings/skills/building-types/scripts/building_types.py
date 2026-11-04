"""A row of isometric building types from a massing and a programme.

python building_types.py --proposal <proposal folder> [--config <config.json>] [--style <style.json>]

Reads   <proposal>/massing/massing.geojson   (buildings: footprint, floors, height_m, use, type, existing)
        <proposal>/programme/programme.csv   (use, area_m2, plot_m2, homes, residents, source)
        <proposal>/panel-layout/layout.json  (the frame's scale and width, if there)
        <proposal>/drawing-graphics/style.json (the look, if there)
Writes  <proposal>/building-types/building-types_<scale>.svg and .png, types.csv, summary.md

Plain Python, no installs. The PNG needs a headless Chrome, Chromium or Edge.
A missing input never stops it: it draws a stand-in, labelled as one in the drawing.
"""
import argparse, csv, json, math, os, re, shutil, statistics, subprocess, sys
from pathlib import Path

A = argparse.ArgumentParser(description=__doc__.splitlines()[0])
A.add_argument('--proposal', required=True)
A.add_argument('--config', help='building-types/config.json, filled from the brief')
A.add_argument('--style', help='drawing-graphics/style.json')
a = A.parse_args()
PROP = Path(a.proposal).resolve()
OUT = PROP / 'building-types'
OUT.mkdir(parents=True, exist_ok=True)
NOTES, UNSURE = [], []          # what goes in summary.md


def val(cfg, key):
    v = cfg.get(key)
    return v.get('value') if isinstance(v, dict) else v


# ---------- config and scale ----------
cfg_path = Path(a.config) if a.config else OUT / 'config.json'
CFG = json.loads(cfg_path.read_text(encoding='utf8')) if cfg_path.exists() else {}
if not CFG:
    NOTES.append('no config.json: the scale and panel width were not taken from the brief')

scale, scale_src, frame_w, file_name = None, None, None, None
layout = PROP / 'panel-layout' / 'layout.json'
if layout.exists():
    try:
        L = json.loads(layout.read_text(encoding='utf8'))
        items = [i for i in L.get('items', []) if 'building-types' in str(i.get('file', '')) or 'building-types' in str(i.get('id', ''))]
        if items:
            it = items[0]
            m = re.match(r'\s*1\s*:\s*([\d,.]+)', str(it.get('scale', '')))
            if m:
                scale, scale_src = int(float(m.group(1).replace(',', ''))), 'panel-layout/layout.json'
            frame_w = (it.get('frame') or {}).get('w') or None
            file_name = Path(str(it.get('file'))).stem if it.get('file') else None
    except (ValueError, OSError) as e:
        NOTES.append('panel-layout/layout.json could not be read (%s)' % e)
if scale is None and val(CFG, 'scale'):
    scale, scale_src = int(val(CFG, 'scale')), (CFG['scale'].get('source') if isinstance(CFG.get('scale'), dict) else 'config.json')
if scale is None:
    scale, scale_src = 500, 'default 1:500: no frame in panel-layout/layout.json and no scale in config.json'
    UNSURE.append('the scale is the default 1:500, not the brief\'s')
panel_w = frame_w or val(CFG, 'panel_width_mm')
FLOOR_H = val(CFG, 'floor_height_m')
MM = 1000.0 / scale                      # print mm per metre

# ---------- style ----------
style_path = Path(a.style) if a.style else PROP / 'drawing-graphics' / 'style.json'
if style_path.exists():
    ST = json.loads(style_path.read_text(encoding='utf8'))
    style_src = str(style_path.relative_to(PROP)) if PROP in style_path.parents else str(style_path)
else:
    # only when there is no standard: black lines on white with one accent, as the drawings topic asks
    ST = {'paper': '#ffffff', 'ink': '#000000', 'accent': '#c8442b', 'font': 'Arial, sans-serif',
          'thin': 0.13, 'mid': 0.25, 'thick': 0.5, 'text': 3.2, 'title': 5.6}
    style_src = 'no drawing standard: black on white with one accent'
    UNSURE.append('no drawing-graphics/style.json, so black on white with one accent')
INK, PAPER = ST.get('ink', '#000'), ST.get('paper', '#fff')
ACC = ST.get('accent', '#c8442b')
NEW = ST.get('new', '#ffffff')                       # the buildings white, their left faces in shade
SHADE = '#%02x%02x%02x' % tuple(round(int(NEW[i:i + 2], 16) * 0.4 + int(ST.get('shadow', '#a8a8a8')[i:i + 2], 16) * 0.6)
                                for i in (1, 3, 5))
FONT = ST.get('font', 'Arial, sans-serif')
THIN, MID = float(ST.get('thin', 0.13)), float(ST.get('mid', 0.25))
TXT = max(float(ST.get('text', 3.2)), 3.2)          # never under 12 px printed
TTL = max(float(ST.get('title', 5.6)), TXT)

# ---------- programme ----------
prog_path = PROP / 'programme' / 'programme.csv'
PROG, prog_stand_in = [], False
if prog_path.exists():
    with prog_path.open(encoding='utf8') as fh:
        PROG = [r for r in csv.DictReader(fh) if (r.get('use') or '').strip()]
if not PROG:
    prog_stand_in = True
    UNSURE.append('no programme/programme.csv: the programme line is taken from the massing, or marked missing')

# ---------- massing ----------
mass_path = PROP / 'massing' / 'massing.geojson'
FEATS, mass_stand_in = [], False
if mass_path.exists():
    try:
        MJ = json.loads(mass_path.read_text(encoding='utf8'))
        FEATS = [f for f in MJ.get('features', []) if (f.get('properties') or {}).get('kind') == 'building'
                 and not (f.get('properties') or {}).get('existing') and f.get('geometry')]
        if MJ.get('stand_in') or any(f['properties'].get('stand_in') for f in FEATS):
            mass_stand_in = True
            UNSURE.append('massing/massing.geojson is itself marked as a stand-in')
    except (ValueError, OSError) as e:
        NOTES.append('massing/massing.geojson could not be read (%s)' % e)


def rings_m(geom):
    """WGS84 polygon(s) to local metres around their own centre; the largest polygon of a multi."""
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    poly = max(polys, key=lambda p: len(p[0]))
    lon0 = statistics.fmean(p[0] for p in poly[0]); lat0 = statistics.fmean(p[1] for p in poly[0])
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110540
    return [[((p[0] - lon0) * kx, (p[1] - lat0) * ky) for p in r] for r in poly]


def area(r): return abs(sum(r[i][0] * r[i - 1][1] - r[i - 1][0] * r[i][1] for i in range(len(r)))) / 2


BUILD = []
for f in FEATS:
    p = f['properties']
    rings = rings_m(f['geometry'])
    fp = p.get('footprint_m2') or round(area(rings[0]) - sum(area(h) for h in rings[1:]))
    fl = p.get('floors')
    h = p.get('height_m')
    h_src = 'height_m'
    if h is None and fl:
        h, h_src = fl * (FLOOR_H or 3.0), ('floors x %s m (config)' % FLOOR_H if FLOOR_H else 'floors x 3 m (assumed)')
    if fl is None and h:
        fl = max(1, round(h / (FLOOR_H or 3.0)))
    if not (fl and h):
        NOTES.append('a building without floors or height was left out')
        continue
    use = p.get('use') or 'use not given'
    typ = p.get('type')
    key = use if not typ or typ in ('community', 'building', 'yes') else typ
    BUILD.append(dict(key=key, use=use, rings=rings, fp=fp, floors=int(fl), h=float(h), h_src=h_src,
                      gfa=p.get('gfa_m2') or round(fp * fl)))

if not BUILD:
    mass_stand_in = True
    UNSURE.append('no massing: four generic stand-in types of assumed size, labelled as such')
    def rect(w, d): return [[(0, 0), (w, 0), (w, d), (0, d)]]
    for key, use, rings, fl in [('row houses', 'housing', rect(40, 10), 3),
                                ('courtyard block', 'mixed', [rect(60, 50)[0], [(14, 14), (14, 36), (46, 36), (46, 14)]], 5),
                                ('point building', 'housing', rect(20, 20), 6),
                                ('hall', 'commerce', rect(60, 25), 2)]:
        fp = round(area(rings[0]) - sum(area(r) for r in rings[1:]))
        BUILD.append(dict(key=key, use=use, rings=rings, fp=fp, floors=fl, h=fl * (FLOOR_H or 3.0),
                          h_src='assumed', gfa=fp * fl))

# ---------- one type each: the building of median footprint ----------
TYPES = []
for key in sorted({b['key'] for b in BUILD}, key=lambda k: -max(b['h'] for b in BUILD if b['key'] == k)):
    bs = sorted([b for b in BUILD if b['key'] == key], key=lambda b: b['fp'])
    rep = dict(bs[len(bs) // 2])
    rep.update(n=len(bs), gfa_all=sum(b['gfa'] for b in bs), uses=sorted({b['use'] for b in bs}))
    TYPES.append(rep)
TYPES.sort(key=lambda t: t['h'])          # low to high along the row


def programme_line(t):
    """The programme rows this type's use answers, with their pages."""
    if prog_stand_in and not FEATS:
        return 'programme: missing (no programme.csv)'
    if prog_stand_in:
        return 'stand-in: %s m\u00b2 floor area of this type in the massing' % f"{t['gfa_all']:,}"
    words = set()
    for u in t['uses']:
        for w in re.split(r'\s*[+/,;&]\s*|\s+and\s+', u.lower()):
            words |= {'housing', 'commerce'} if w.strip() == 'mixed' else {w.strip()}   # mixed: shops below, homes above
    rows = [r for r in PROG if any(w and (w in r['use'].lower() or r['use'].lower() in w) for w in words)]
    if not rows:
        return '%s: not in programme.csv' % ', '.join(t['uses'])
    out = []
    for r in rows:
        bits = []
        if r.get('homes'): bits.append('%s homes' % f"{int(float(r['homes'])):,}")
        if r.get('area_m2'): bits.append('%s m\u00b2' % f"{int(float(r['area_m2'])):,}")
        elif r.get('plot_m2'): bits.append('%s m\u00b2 land' % f"{int(float(r['plot_m2'])):,}")
        pages = re.findall(r'pp?\.\s*[\d\u2013-]+', r.get('source', ''))
        out.append('%s %s%s' % (r['use'], ', '.join(bits) or '(no figure)', (' (%s)' % ', '.join(pages[:2])) if pages else ''))
    return 'programme: ' + '; '.join(out)


# ---------- geometry: square each type to the grid, then isometric ----------
C, S = math.cos(math.radians(30)), math.sin(math.radians(30))


def squared(rings):
    """Turn the footprint so its longest edge runs along y, the accent face on the left, and put it at the origin."""
    o = rings[0]
    e = max(range(len(o) - 1), key=lambda i: math.dist(o[i], o[i + 1]))
    ang = math.pi / 2 - math.atan2(o[e + 1][1] - o[e][1], o[e + 1][0] - o[e][0])
    rot = [[(x * math.cos(ang) - y * math.sin(ang), x * math.sin(ang) + y * math.cos(ang)) for x, y in r] for r in rings]
    mx = min(x for x, _ in rot[0]); my = min(y for _, y in rot[0])
    rot = [[(x - mx, y - my) for x, y in r] for r in rot]
    out = []
    for i, r in enumerate(rot):     # outer ring counter-clockwise, holes clockwise
        if r[0] == r[-1]: r = r[:-1]
        ccw = sum(r[j][0] * r[j - 1][1] - r[j - 1][0] * r[j][1] for j in range(len(r))) < 0
        out.append(r if ccw == (i == 0) else r[::-1])
    return out


def iso(x, y, z):
    """Isometric drawing, true length on all three axes, seen from -x,-y. Print mm, y down."""
    return ((x - y) * C * MM, -(x + y) * S * MM - z * MM)


def pts(ps): return ' '.join('%.2f,%.2f' % iso(*p) for p in ps)


def draw(t):
    rings = squared(t['rings'])
    h, n = t['h'], t['floors']
    walls = []
    for r in rings:
        for i in range(len(r)):
            (x1, y1), (x2, y2) = r[i], r[(i + 1) % len(r)]
            nx, ny = (y2 - y1), -(x2 - x1)                 # outward normal of a counter-clockwise ring
            if -nx - ny <= 1e-9: continue                  # faces away from the viewer
            walls.append(((x1 + x2 + y1 + y2) / 2, (x1, y1), (x2, y2), nx < ny))
    g = []
    for _, p1, p2, left in sorted(walls, key=lambda w: -w[0]):   # far to near
        quad = [(*p1, 0), (*p2, 0), (*p2, h), (*p1, h)]
        g.append('<polygon points="%s" fill="%s" stroke="%s" stroke-width="%.2f" stroke-linejoin="round"/>'
                 % (pts(quad), SHADE if left else NEW, INK, MID))
        for k in range(1, n if h / n * MM >= 0.8 else 1):   # floors as fine lines, dropped when they would merge in print
            z = h * k / n
            (u1, v1), (u2, v2) = iso(*p1, z), iso(*p2, z)
            g.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%.2f"/>'
                     % (u1, v1, u2, v2, INK, THIN))
    d = ' '.join('M ' + ' L '.join('%.2f %.2f' % iso(x, y, h) for x, y in r) + ' Z' for r in rings)
    g.append('<path d="%s" fill="%s" fill-rule="evenodd" stroke="%s" stroke-width="%.2f" stroke-linejoin="round"/>'
             % (d, NEW, INK, MID))
    us = [iso(x, y, z)[0] for r in rings for x, y in r for z in (0, h)]
    vs = [iso(x, y, z)[1] for r in rings for x, y in r for z in (0, h)]
    v0 = max(iso(x, y, 0)[1] for r in rings for x, y in r)   # the lowest ground corner
    return ''.join(g), min(us), max(us), min(vs), v0


def esc(s): return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def wrap(s, n):
    lines, cur = [], ''
    for w in s.split(' '):
        if cur and len(cur) + 1 + len(w) > n: lines.append(cur); cur = w
        else: cur = (cur + ' ' + w).strip()
    return lines + [cur] if cur else lines


# ---------- layout: rows on a shared baseline grid, wrapped at the panel's width ----------
M, GAP, CW = 15.0, 10.0, 0.55 * TXT          # margin, gap between types, width of a character
COL_MIN = 34 * CW                             # a label column holds at least ~34 characters
LH = TXT * 1.35
SB_W = 14.0                                    # the scale bar's column
LEFT = M + SB_W + GAP                          # where the types start in every row
cols = []
for t in TYPES:
    g, u0, u1, v_top, v0 = draw(t)
    w = max(u1 - u0, COL_MIN)
    lab = [(t['key'] + (' (stand-in)' if mass_stand_in else ''), True)]
    lab += [(s, False) for s in wrap(programme_line(t), int(w / CW))]
    lab += [('footprint %s m\u00b2 \u00b7 %d floors \u00b7 %s m' % (f"{t['fp']:,}", t['floors'], ('%.1f' % t['h']).rstrip('0').rstrip('.')), False),
            ('floor area %s m\u00b2 \u00b7 %d of this type%s' % (f"{t['gfa']:,}", t['n'], '' if t['h_src'] == 'height_m' else ' \u00b7 height ' + t['h_src']), False)]
    cols.append(dict(t=t, g=g, w=w, u0=u0, u1=u1, v0=v0, top=v0 - v_top, lab=lab))
avail = float(panel_w) - LEFT - M if panel_w else float('inf')   # room for the types in one row
ROWS = [[]]
for c in cols:                                 # in order, low to high; a new row when the next type doesn't fit
    used = sum(k['w'] for k in ROWS[-1]) + GAP * len(ROWS[-1])
    if ROWS[-1] and used + c['w'] > avail:
        ROWS.append([])
    ROWS[-1].append(c)
for row in ROWS:
    x = LEFT
    for c in row:
        c['x'] = x; x += c['w'] + GAP
W = LEFT + max(sum(c['w'] for c in row) + GAP * (len(row) - 1) for row in ROWS) + M
tallest = max(c['top'] for c in cols)
nlab = max(len(c['lab']) for c in cols)
head = M + TTL + LH * (2 if mass_stand_in or prog_stand_in else 1) + 6
PITCH = tallest + 6 + nlab * LH + 10           # every row the same height, so the baselines form a grid
BASES = [head + tallest + r * PITCH for r in range(len(ROWS))]
H = BASES[-1] + 6 + nlab * LH + 4 + 2 * LH + M

svg = []
T = lambda x_, y_, s, size=TXT, bold=False, fill=INK, anchor='start': svg.append(
    '<text x="%.2f" y="%.2f" font-size="%.2f" font-family="%s" font-weight="%s" fill="%s" text-anchor="%s">%s</text>'
    % (x_, y_, size, esc(FONT), 'bold' if bold else 'normal', fill, anchor, esc(s)))
svg.append('<rect width="%.2f" height="%.2f" fill="%s"/>' % (W, H, PAPER))
T(M, M + TTL * 0.8, 'Building types, isometric 1:%s' % f"{scale:,}", TTL, True)
if mass_stand_in or prog_stand_in:
    which = ' and '.join(s for s, on in (('massing', mass_stand_in), ('programme', prog_stand_in)) if on)
    T(M, M + TTL + LH * 0.9, 'STAND-IN: no real %s yet. Shapes or figures marked stand-in are placeholders, not the design.' % which,
      TXT, True, ACC)

# scale bar: heights are true length in an isometric drawing, so it stands upright on each baseline
step = next(s for s in (1, 2, 5, 10, 20, 50, 100) if s * MM >= 4 * TXT * 0.6 and s * MM >= 5)
nst = max(2, min(6, int(tallest / (step * MM))))
sx = M + SB_W - 2
for row, BASE in zip(ROWS, BASES):
    for c in row:   # each type stands on its row's baseline, centred in its column
        dx = c['x'] + c['w'] / 2 - (c['u0'] + c['u1']) / 2
        svg.append('<g transform="translate(%.2f %.2f)">%s</g>' % (dx, BASE - c['v0'], c['g']))
        for i, (s, bold) in enumerate(c['lab']):
            T(c['x'], BASE + 6 + TXT + i * LH, s, TXT, bold)
    svg.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%.2f"/>' % (M + SB_W, BASE, W - M, BASE, INK, THIN))
    d = 'M %.2f %.2f' % (sx, BASE)
    for k in range(nst):
        off = 1.2 if k % 2 == 0 else 0
        d += ' L %.2f %.2f L %.2f %.2f' % (sx - off, BASE - k * step * MM, sx - off, BASE - (k + 1) * step * MM)
    svg.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.2f"/>' % (d, INK, THIN))
    for k in range(nst + 1):
        yk = BASE - k * step * MM
        svg.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%.2f"/>' % (sx - 2.4, yk, sx, yk, INK, THIN))
        T(sx - 3.2, yk + TXT * 0.35, '%d%s' % (k * step, ' m' if k == nst else ''), TXT, anchor='end')

# legend and source line
ly = H - M - LH
svg.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s" stroke="%s" stroke-width="%.2f"/>' % (M, ly - TXT * 0.8, TXT, TXT, SHADE, INK, MID))
T(M + TXT * 1.6, ly, 'new building, one face in shade; fine lines: floors. True lengths along the three axes.', TXT)
src = 'Sources: %s; %s; one building of median footprint per type.' % (
    'stand-in shapes (assumed sizes)' if not FEATS else 'massing/massing.geojson' + (' (itself a stand-in)' if mass_stand_in else ''),
    ('no programme' if not FEATS else 'programme stand-in from the massing') if prog_stand_in else 'programme/programme.csv')
T(M, ly + LH, src, TXT, fill=INK)

# ---------- write ----------
tag = '1-%d' % scale
name = file_name or 'building-types_%s' % tag
body = ''.join(svg)
def write(p, w, h):
    Path(p).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %.2f %.2f">%s</svg>'
                       % (w, h, W, H, body), encoding='utf8')
svg_path = OUT / (name + '.svg')
write(svg_path, '%.1fmm' % W, '%.1fmm' % H)

pw = 3000; ph = int(round(pw * H / W))
prev = OUT / '_preview.svg'; write(prev, pw, ph)
png = OUT / (name + '.png')
if png.exists(): png.unlink()
browsers = [shutil.which(b) for b in ('google-chrome', 'chromium', 'chromium-browser', 'chrome', 'msedge', 'microsoft-edge')]
browsers += ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium',
             '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
             r'C:\Program Files\Google\Chrome\Application\chrome.exe', r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe']
browser = next((b for b in browsers if b and os.path.exists(b)), None)
if browser:
    try:
        subprocess.run([browser, '--headless', '--disable-gpu', '--hide-scrollbars', '--screenshot=' + str(png),
                        '--window-size=%d,%d' % (pw, ph), prev.as_uri()], capture_output=True, timeout=180)
    except Exception as e:
        NOTES.append('PNG failed (%s)' % e)
    if not png.exists(): NOTES.append('PNG failed: the browser wrote no file')
else:
    NOTES.append('no PNG: no Chrome, Chromium or Edge found')
prev.unlink(missing_ok=True)

with (OUT / 'types.csv').open('w', newline='', encoding='utf8') as fh:
    w = csv.writer(fh)
    w.writerow(['type', 'uses', 'buildings', 'footprint_m2', 'floors', 'height_m', 'height_source', 'gfa_m2', 'gfa_all_m2', 'programme', 'stand_in'])
    for t in TYPES:
        w.writerow([t['key'], ' / '.join(t['uses']), t['n'], t['fp'], t['floors'], t['h'], t['h_src'], t['gfa'], t['gfa_all'],
                    programme_line(t), mass_stand_in or prog_stand_in])

fits = ''
if len(ROWS) > 1:
    fits = ' Wrapped into %d rows of %s types on a shared baseline grid, at the same scale, to keep within the %.0f mm frame.' % (
        len(ROWS), ', '.join(str(len(r)) for r in ROWS), float(panel_w))
if panel_w:
    fits += ' It is %.0f mm wide, %s the %.0f mm frame.' % (W, 'within' if W <= float(panel_w) + 0.5 else 'WIDER than', float(panel_w))
    if W > float(panel_w) + 0.5:
        nxt = next((s_ for s_ in (200, 250, 500, 1000, 2000, 2500, 5000) if s_ > scale and W * scale / s_ <= float(panel_w)), None)
        UNSURE.append('one type alone is wider than its frame' + (', it would fit at 1:%d (the scale was not changed)' % nxt if nxt else ''))
lines = [
    'Drew %d building types (%s) in isometric at 1:%s (%s), in %s.%s' % (
        len(TYPES), ', '.join(t['key'] for t in TYPES), f"{scale:,}", scale_src, svg_path.name, fits),
    'Tallest type: %s, %d floors, %s m; the drawing is %.0f x %.0f mm printed.' % (
        TYPES[-1]['key'], TYPES[-1]['floors'], ('%.1f' % TYPES[-1]['h']).rstrip('0').rstrip('.'), W, H),
    'Unsure: ' + ('; '.join(UNSURE + NOTES) if (UNSURE or NOTES) else 'nothing flagged') + '. Look: ' + style_src + '.',
]
(OUT / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
print('\n'.join(lines))
print('wrote', svg_path, png if png.exists() else '(no PNG)', OUT / 'types.csv', OUT / 'summary.md', sep='\n  ')
