"""Building types as ensembles: one block of each type, with its yard, trees, roofs, windows, street and notes.

python building_types.py --proposal <proposal folder> [--config <config.json>] [--style <style.json>]

Reads   <proposal>/massing/massing.geojson   (new buildings: footprint, floors, height_m, use, type, and if there
                                              block, part, roof, ground_floor; the courtyards, streets and trees)
        <proposal>/open-space/open-space.geojson (the ground and the trees around the blocks, if there)
        <proposal>/programme/programme.csv   (use, area_m2, plot_m2, homes, residents, source)
        <proposal>/building-types/notes.json (if there: {"<type>": [{"text", "source", "at"}]}, notes from the narrative
                                              and the programme; at: roof, yard, ground, street, trees, tower or wall)
        <proposal>/panel-layout/layout-plan.json, else layout.json (the frame's scale and size, if there)
        <proposal>/drawing-graphics/style.json (the look, if there)
Writes  <proposal>/building-types/building-types_<scale>.svg and .png, types.csv, summary.md

Plain Python, no installs. The PNG needs a headless Chrome, Chromium or Edge.
A missing input never stops it: it draws a stand-in, labelled as one in the drawing.
"""
import argparse, csv, heapq, json, math, os, re, shutil, statistics, subprocess, sys
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

# How the drawing illustrates what the layers don't give; not the brief's numbers. summary.md names each one used.
MARGIN = 14.0                   # m of ground drawn around a block: its street and the trees along it
BAY, WIN_W = 3.0, 1.4           # m: an illustrative window rhythm, one window per bay
PITCH = 35.0                    # degrees of a gable roof: the massing gives the roof, not its pitch
TREE_CROWN, TREE_H = 6.0, 9.0   # m: a tree without crown_m or height_m
PV_ROW, PV_GAP, PV_EDGE = 1.7, 0.9, 1.2   # m: the rows of panels on a PV roof
MAX_TYPES = 6                   # types drawn at most: a sheet of types reads with four to six


def val(cfg, key):
    v = cfg.get(key)
    return v.get('value') if isinstance(v, dict) else v


# ---------- config and scale ----------
cfg_path = Path(a.config) if a.config else OUT / 'config.json'
CFG = json.loads(cfg_path.read_text(encoding='utf8')) if cfg_path.exists() else {}
if not CFG:
    NOTES.append('no config.json: the scale and panel width were not taken from the brief')

scale, scale_src, frame_w, frame_h, file_name = None, None, None, None, None
planned_frame, ROOM_WORD = None, 'frame'
for nm in ('layout-plan.json', 'layout.json'):      # the panels' plan, else the layout; items at the top or per panel
    layout = PROP / 'panel-layout' / nm
    if not layout.exists():
        continue
    try:
        L = json.loads(layout.read_text(encoding='utf8'))
        its = list(L.get('items', [])) + [i for p in L.get('panels', []) for i in p.get('items', [])]
        items = [i for i in its if 'building-types' in str(i.get('file', '')) or 'building-types' in str(i.get('id', ''))]
        if items:
            it = items[0]
            m = re.match(r'\s*1\s*:\s*([\d,.]+)', str(it.get('scale', '')))
            if m:
                scale, scale_src = int(float(m.group(1).replace(',', ''))), 'panel-layout/' + nm
            frame_w = (it.get('frame') or {}).get('w') or None
            frame_h = (it.get('frame') or {}).get('h') or None
            file_name = Path(str(it.get('file'))).stem if it.get('file') else None
            fmt = L.get('format') or {}
            if fmt.get('width_mm') and fmt.get('height_mm'):      # the frame is a first guess: draw to the panel's room and ask for the frame
                planned_frame = {'w': frame_w, 'h': frame_h}
                m_ = fmt.get('margin_mm', 15)
                frame_w, frame_h = fmt['width_mm'] - 2 * m_, fmt['height_mm'] - fmt.get('content_top_mm', m_) - m_
                ROOM_WORD = 'panel'
            break
    except (ValueError, OSError, AttributeError) as e:
        NOTES.append('panel-layout/%s could not be read (%s)' % (nm, e))
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


def hx(c):
    c = str(c).lstrip('#')
    return c if len(c) == 6 else ''.join(ch * 2 for ch in c[:3])


def mix(c1, c2, t):
    """The colour t of the way from c1 to c2."""
    p, q = hx(c1), hx(c2)
    return '#%02x%02x%02x' % tuple(round(int(p[i:i + 2], 16) * (1 - t) + int(q[i:i + 2], 16) * t) for i in (0, 2, 4))


INK, PAPER = ST.get('ink', '#000'), ST.get('paper', '#fff')
ACC = ST.get('accent', '#c8442b')
NEW = ST.get('new', '#ffffff')                       # the buildings white, their left faces in shade
SHADE = mix(ST.get('shadow', '#a8a8a8'), NEW, 0.4)
WIN, WIN_S = mix(NEW, INK, 0.45), mix(SHADE, INK, 0.45)   # windows, on a lit and on a shaded face
PV = mix(NEW, INK, 0.55)
GREEN_ROOF = ST.get('meadow', NEW)
TREE = ST.get('grove', NEW)
TREE_LINE = mix(TREE, INK, 0.3) if 'grove' in ST else INK
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


# ---------- massing, open space and notes ----------
def load(path, what):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf8'))
    except (ValueError, OSError) as e:
        NOTES.append('%s could not be read (%s)' % (what, e))
        return None


FEATS, AROUND, mass_stand_in = [], [], False
MJ = load(PROP / 'massing' / 'massing.geojson', 'massing/massing.geojson')
if MJ:
    for f in MJ.get('features', []):
        p = f.get('properties') or {}
        if not f.get('geometry'):
            continue
        if p.get('kind') != 'building':
            AROUND.append(('massing', f))
        elif not p.get('existing'):
            FEATS.append(f)
    if MJ.get('stand_in') or any(f['properties'].get('stand_in') for f in FEATS):
        mass_stand_in = True
        UNSURE.append('massing/massing.geojson is itself marked as a stand-in')
OJ = load(PROP / 'open-space' / 'open-space.geojson', 'open-space/open-space.geojson')
if OJ:
    AROUND += [('open-space', f) for f in OJ.get('features', []) if f.get('geometry')]
elif FEATS:
    NOTES.append('no open-space/open-space.geojson: the ground and trees around the blocks are the massing\'s only')
GIVEN = load(OUT / 'notes.json', 'building-types/notes.json') or {}
if not isinstance(GIVEN, dict):
    NOTES.append('building-types/notes.json is not an object of types, so it was left out')
    GIVEN = {}


def outer(geom):
    c = geom.get('coordinates') or []
    return c[0] if geom.get('type') == 'Polygon' and c else c[0][0] if geom.get('type') == 'MultiPolygon' and c else []


_c = [q for f in FEATS for q in outer(f['geometry'])]
LON0 = statistics.fmean(q[0] for q in _c) if _c else 0.0
LAT0 = statistics.fmean(q[1] for q in _c) if _c else 0.0
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110540


def to_m(q): return ((q[0] - LON0) * KX, (q[1] - LAT0) * KY)


def polys_m(geom):
    """Every polygon of a (multi)polygon in local metres, as open rings."""
    t, c = geom.get('type'), geom.get('coordinates') or []
    ps = [c] if t == 'Polygon' else c if t == 'MultiPolygon' else []
    return [[[to_m(q) for q in (r[:-1] if len(r) > 1 and r[0] == r[-1] else r)] for r in poly] for poly in ps if poly]


def lines_m(geom):
    t, c = geom.get('type'), geom.get('coordinates') or []
    ls = [c] if t == 'LineString' else c if t == 'MultiLineString' else []
    return [[to_m(q) for q in ln] for ln in ls if len(ln) > 1]


def area(r): return abs(sum(r[i][0] * r[i - 1][1] - r[i - 1][0] * r[i][1] for i in range(len(r)))) / 2


def bbox(ps): return (min(q[0] for q in ps), min(q[1] for q in ps), max(q[0] for q in ps), max(q[1] for q in ps))


BUILD = []
for i, f in enumerate(FEATS):
    p = f['properties']
    ps = polys_m(f['geometry'])
    if not ps:
        continue
    rings = max(ps, key=lambda q: area(q[0]))        # the largest polygon of a multi
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
                      gfa=p.get('gfa_m2') or round(fp * fl), block=p.get('block', 'b%d' % i),
                      part=p.get('part') or 'building', roof=str(p.get('roof') or 'flat').lower(),
                      gf=str(p.get('ground_floor') or '').lower()))

if not BUILD:
    mass_stand_in = True
    UNSURE.append('no massing: four generic stand-in types of assumed size, labelled as such')
    def rect(w, d): return [[(0, 0), (w, 0), (w, d), (0, d)]]
    for j, (key, use, rings, fl) in enumerate([('row houses', 'housing', rect(40, 10), 3),
                                               ('courtyard block', 'mixed', [rect(60, 50)[0], [(14, 14), (14, 36), (46, 36), (46, 14)]], 5),
                                               ('point building', 'housing', rect(20, 20), 6),
                                               ('hall', 'commerce', rect(60, 25), 2)]):
        fp = round(area(rings[0]) - sum(area(r) for r in rings[1:]))
        BUILD.append(dict(key=key, use=use, rings=rings, fp=fp, floors=fl, h=fl * (FLOOR_H or 3.0),
                          h_src='assumed', gfa=fp * fl, block='s%d' % j, part='building', roof='flat', gf=''))

# what lies around the blocks: the ground, the street centre lines at their widths, the paths and the trees
GROUND, STREETS, PATHS, TREES = [], [], [], []
USE_FILL = {'garden': 'lawn', 'square': 'public', 'water': 'water', 'park': 'park'}
for src, f in AROUND:
    p, g = f.get('properties') or {}, f['geometry']
    k, u = p.get('kind'), str(p.get('use') or '').lower()
    if k == 'tree' and g.get('type') == 'Point':
        x, y = to_m(g['coordinates'])
        TREES.append(dict(x=x, y=y, crown=p.get('crown_m'), h=p.get('height_m'), src=src,
                          group=p.get('group') or ('street' if src == 'massing' else 'tree')))
    elif k == 'street':
        for ln in lines_m(g):
            STREETS.append(dict(pts=ln, bb=bbox(ln), w=float(p.get('width') or 0) or None, level=p.get('level') or 'street',
                                name=p.get('name')))
    elif k == 'path':
        PATHS += [(ln, bbox(ln)) for ln in lines_m(g)]
    elif k in ('open-space', 'ground-cover', 'retention'):
        fk = (str(p.get('cover') or '').replace(' ', '-') if k == 'ground-cover' else 'water' if k == 'retention'
              else 'lawn' if p.get('type') == 'courtyard' else 'kept' if u == 'park' and p.get('existing') else USE_FILL.get(u))
        for poly in (polys_m(g) if fk else []):
            GROUND.append(dict(key=fk, rings=poly, bb=bbox(poly[0]), src=src, label=p.get('type'),
                               court=p.get('type') == 'courtyard' or u == 'garden',
                               m2=area(poly[0]) - sum(area(r) for r in poly[1:])))
G_ORDER = {'kept': 0, 'park': 0, 'lawn': 2, 'water': 3, 'public': 4}   # covers (meadow, grove ...) 1

# ---------- one type each: its most complete block, of median footprint among those ----------
TYPES = []
for key in sorted({b['key'] for b in BUILD}):
    bs = [b for b in BUILD if b['key'] == key]
    blocks = {}
    for b in bs:
        blocks.setdefault(b['block'], []).append(b)
    most = max(len(v) for v in blocks.values())
    full = sorted([v for v in blocks.values() if len(v) == most], key=lambda v: sum(b['fp'] for b in v))
    blk = full[len(full) // 2][0]['block']
    mem = [b for b in BUILD if b['block'] == blk]   # the whole block, whatever the type of its other buildings
    TYPES.append(dict(key=key, n=len(bs), blocks=len(blocks), gfa_all=sum(b['gfa'] for b in bs), uses=sorted({b['use'] for b in bs}),
                      block=blk, members=mem, fp=sum(b['fp'] for b in mem), gfa=sum(b['gfa'] for b in mem),
                      floors=max(b['floors'] for b in mem), fl_min=min(b['floors'] for b in mem), h=max(b['h'] for b in mem),
                      h_src=next((b['h_src'] for b in mem if b['h_src'] != 'height_m'), 'height_m')))
TYPES.sort(key=lambda t: (t['h'], t['key']))          # low to high along the rows


def programme_rows(t):
    words = set()
    for u in t['uses']:
        for w in re.split(r'\s*[+/,;&]\s*|\s+and\s+', u.lower()):
            words |= {'housing', 'commerce'} if w.strip() == 'mixed' else {w.strip()}   # mixed: shops below, homes above
    return [r for r in PROG if any(w and (w in r['use'].lower() or r['use'].lower() in w) for w in words)]


def pages(r): return re.findall(r'pp?\.\s*[\d\u2013-]+', r.get('source', ''))


def programme_line(t):
    """The programme rows this type's use answers, with their pages."""
    if prog_stand_in and not FEATS:
        return 'programme: missing (no programme.csv)'
    if prog_stand_in:
        return 'stand-in: %s m\u00b2 floor area of this type in the massing' % f"{t['gfa_all']:,}"
    rows = programme_rows(t)
    if not rows:
        return '%s: not in programme.csv' % ', '.join(t['uses'])
    out = []
    for r in rows:
        bits = []
        if r.get('homes'): bits.append('%s homes' % f"{int(float(r['homes'])):,}")
        if r.get('area_m2'): bits.append('%s m\u00b2' % f"{int(float(r['area_m2'])):,}")
        elif r.get('plot_m2'): bits.append('%s m\u00b2 land' % f"{int(float(r['plot_m2'])):,}")
        pg = pages(r)
        out.append('%s %s%s' % (r['use'], ', '.join(bits) or '(no figure)', (' (%s)' % ', '.join(pg[:2])) if pg else ''))
    return 'programme: ' + '; '.join(out)


# ---------- geometry ----------
C, S = math.cos(math.radians(30)), math.sin(math.radians(30))


def iso(x, y, z):
    """Isometric drawing, true length on all three axes, seen from -x,-y. Print mm, y down."""
    return ((x - y) * C * MM, -(x + y) * S * MM - z * MM)


def P(x, y, z): return '%.2f %.2f' % iso(x, y, z)


def dpath(rings, z=0.0): return ' '.join('M ' + ' L '.join(P(x, y, z) for x, y in r) + ' Z' for r in rings if len(r) > 2)


def is_ccw(r): return sum(r[j][0] * r[j - 1][1] - r[j - 1][0] * r[j][1] for j in range(len(r))) < 0


def orient(rings):
    """Outer ring counter-clockwise, holes clockwise, so every wall's outward normal is (dy, -dx)."""
    return [r if is_ccw(r) == (i == 0) else r[::-1] for i, r in enumerate(rings)]


def clip(ring, box):
    """A ring cut to an axis-parallel box (Sutherland-Hodgman)."""
    out = list(ring)
    for ax, lim, ge in ((0, box[0], True), (0, box[2], False), (1, box[1], True), (1, box[3], False)):
        inp, out = out, []
        for i in range(len(inp)):
            p1, p2 = inp[i - 1], inp[i]
            in1, in2 = (p1[ax] >= lim) == ge or p1[ax] == lim, (p2[ax] >= lim) == ge or p2[ax] == lim
            if in1 != in2:
                t = (lim - p1[ax]) / (p2[ax] - p1[ax])
                out.append((p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])))
            if in2:
                out.append(p2)
        if not out:
            break
    return out


def clip_seg(p1, p2, box):
    """A segment cut to an axis-parallel box (Liang-Barsky), or None."""
    t0, t1 = 0.0, 1.0
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    for pp, qq in ((-dx, p1[0] - box[0]), (dx, box[2] - p1[0]), (-dy, p1[1] - box[1]), (dy, box[3] - p1[1])):
        if pp == 0:
            if qq < 0:
                return None
        elif pp < 0:
            t0 = max(t0, qq / pp)
        else:
            t1 = min(t1, qq / pp)
    return ((p1[0] + t0 * dx, p1[1] + t0 * dy), (p1[0] + t1 * dx, p1[1] + t1 * dy)) if t0 < t1 else None


def inside(pt, rings):
    c = False
    for r in rings:
        for i in range(len(r)):
            (x1, y1), (x2, y2) = r[i - 1], r[i]
            if (y1 > pt[1]) != (y2 > pt[1]) and pt[0] < x1 + (pt[1] - y1) / (y2 - y1) * (x2 - x1):
                c = not c
    return c


def chords(o, w):
    """Where the view line x - y = w crosses a building, as x + y (small = near the viewer), sorted."""
    xs = []
    for r in o['rings']:
        for i in range(len(r)):
            (x1, y1), (x2, y2) = r[i - 1], r[i]
            w1, w2 = x1 - y1, x2 - y2
            if (w1 <= w < w2) or (w2 <= w < w1):
                xs.append(x1 + y1 + (w - w1) / (w2 - w1) * (x2 + y2 - x1 - y1))
    return sorted(xs)


def front(p1, p2):
    """+1 if p1 stands in front of p2 where they overlap on paper, -1 if behind, 0 if they don't overlap."""
    lo, hi = max(p1['w0'], p2['w0']), min(p1['w1'], p2['w1'])
    if hi - lo <= 1e-6:
        return 0
    if p1['tree'] and p2['tree']:
        return 1 if p1['s'] < p2['s'] else -1
    v = 0
    for k in range(7):
        w = lo + (hi - lo) * (k + 0.5) / 7
        s1 = p1['s'] if p1['tree'] else (chords(p1, w) or [None])[0]
        s2 = p2['s'] if p2['tree'] else (chords(p2, w) or [None])[0]
        if s1 is not None and s2 is not None:
            v += 1 if s1 < s2 else -1
    return (v > 0) - (v < 0)


def far_to_near(objs):
    """Painter's order: everything an object hides comes before it; ties and loops by distance."""
    after, deg = [[] for _ in objs], [0] * len(objs)
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            f = front(objs[i], objs[j])
            if f > 0: after[j].append(i); deg[i] += 1
            elif f < 0: after[i].append(j); deg[j] += 1
    heap = [(-o['s'], i) for i, o in enumerate(objs) if deg[i] == 0]
    heapq.heapify(heap)
    done, order = set(), []
    while len(order) < len(objs):
        if not heap:     # a loop: the farthest left goes first
            i = max((i for i in range(len(objs)) if i not in done), key=lambda i: objs[i]['s'])
            deg[i] = 0
            heap = [(-objs[i]['s'], i)]
        _, i = heapq.heappop(heap)
        if i in done:
            continue
        done.add(i); order.append(objs[i])
        for j in after[i]:
            deg[j] -= 1
            if deg[j] == 0 and j not in done:
                heapq.heappush(heap, (-objs[j]['s'], j))
    return order


def walls(o):
    out = []
    for r in o['rings']:
        for i in range(len(r)):
            (x1, y1), (x2, y2) = r[i], r[(i + 1) % len(r)]
            nx, ny = (y2 - y1), -(x2 - x1)                 # outward normal of a counter-clockwise ring
            if -nx - ny > 1e-9:                            # faces the viewer
                out.append(((x1 + x2 + y1 + y2) / 2, (x1, y1), (x2, y2), nx < ny))
    return sorted(out, key=lambda w: -w[0])             # far to near


DRAWN = dict(windows=False, gable=0, gable_flat=0, pv=False, trees=0, unsized=0)


def openings(o, p1, p2, left):
    """The window rhythm of a wall, floor by floor; shop fronts on a ground floor that isn't housing."""
    n, L = o['floors'], math.dist(p1, p2)
    fh = o['h'] / n
    if fh * MM < 0.8:
        return ''
    if fh * MM < 1.8 or L < BAY:                           # too small for windows: the floors as fine lines
        return ''.join('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%.2f"/>'
                       % (*iso(*p1, o['h'] * k / n), *iso(*p2, o['h'] * k / n), INK, THIN) for k in range(1, n))
    DRAWN['windows'] = True
    nb = int(L // BAY)
    off, d = (L - nb * BAY) / 2, []
    for k in range(n):
        shop = k == 0 and o['shop']
        ww, z0, z1 = (BAY * 0.8, k * fh + 0.12 * fh, k * fh + 0.85 * fh) if shop else (WIN_W, k * fh + 0.3 * fh, k * fh + 0.78 * fh)
        for j in range(nb):
            t0 = (off + j * BAY + (BAY - ww) / 2) / L
            t1 = t0 + ww / L
            q0 = (p1[0] + t0 * (p2[0] - p1[0]), p1[1] + t0 * (p2[1] - p1[1]))
            q1 = (p1[0] + t1 * (p2[0] - p1[0]), p1[1] + t1 * (p2[1] - p1[1]))
            d.append('M %s L %s L %s L %s Z' % (P(*q0, z0), P(*q1, z0), P(*q1, z1), P(*q0, z1)))
    return '<path d="%s" fill="%s"/>' % (' '.join(d), WIN_S if left else WIN)


CLIPS = [0]


def roof_svg(o):
    h = o['h']
    if o['gable']:
        along_y, x0, x1, y0, y1, rise = o['gable']
        H = h + rise
        if along_y:
            xm = (x0 + x1) / 2
            back = [(x1, y0, h), (x1, y1, h), (xm, y1, H), (xm, y0, H)]
            fore, tone = [(x0, y0, h), (x0, y1, h), (xm, y1, H), (xm, y0, H)], mix(NEW, SHADE, 0.5)
            end, etone = [(x0, y0, h), (x1, y0, h), (xm, y0, H)], NEW
        else:
            ym = (y0 + y1) / 2
            back = [(x0, y1, h), (x1, y1, h), (x1, ym, H), (x0, ym, H)]
            fore, tone = [(x0, y0, h), (x1, y0, h), (x1, ym, H), (x0, ym, H)], NEW
            end, etone = [(x0, y0, h), (x0, y1, h), (x0, ym, H)], SHADE
        DRAWN['gable'] += 1
        return ''.join('<polygon points="%s" fill="%s" stroke="%s" stroke-width="%.2f" stroke-linejoin="round"/>'
                       % (' '.join('%.2f,%.2f' % iso(*q) for q in poly), fill, INK, MID)
                       for poly, fill in ((back, NEW), (fore, tone), (end, etone)))
    d = dpath(o['rings'], h)
    g = '<path d="%s" fill="%s" fill-rule="evenodd" stroke="%s" stroke-width="%.2f" stroke-linejoin="round"/>' % (
        d, GREEN_ROOF if o['roof'] == 'green' else NEW, INK, MID)
    if o['roof'] == 'pv' and PV_ROW * MM >= 0.5:      # rows of panels along the roof's long side, cut to the roof
        DRAWN['pv'] = True
        CLIPS[0] += 1
        x0, y0, x1, y1 = bbox(o['rings'][0])
        along_y = (y1 - y0) >= (x1 - x0)
        rows, c = [], (x0 if along_y else y0) + PV_EDGE
        while c + PV_ROW <= (x1 if along_y else y1) - PV_EDGE:
            q = ([(c, y0 + PV_EDGE), (c + PV_ROW, y0 + PV_EDGE), (c + PV_ROW, y1 - PV_EDGE), (c, y1 - PV_EDGE)] if along_y else
                 [(x0 + PV_EDGE, c), (x1 - PV_EDGE, c), (x1 - PV_EDGE, c + PV_ROW), (x0 + PV_EDGE, c + PV_ROW)])
            rows.append(q)
            c += PV_ROW + PV_GAP
        g += ('<clipPath id="pv%d"><path d="%s" clip-rule="evenodd"/></clipPath><path d="%s" fill="%s" clip-path="url(#pv%d)"/>'
              % (CLIPS[0], d, dpath(rows, h), PV, CLIPS[0]))
    return g


def building_svg(o):
    g = []
    for _, p1, p2, left in walls(o):
        quad = [(*p1, 0), (*p2, 0), (*p2, o['h']), (*p1, o['h'])]
        g.append('<polygon points="%s" fill="%s" stroke="%s" stroke-width="%.2f" stroke-linejoin="round"/>'
                 % (' '.join('%.2f,%.2f' % iso(*q) for q in quad), SHADE if left else NEW, INK, MID))
        g.append(openings(o, p1, p2, left))
    g.append(roof_svg(o))
    return ''.join(g)


def tree_svg(o):
    u, v = iso(o['x'], o['y'], o['h'] - o['r'])
    g = ''
    if o['h'] - 2 * o['r'] > 0.3:
        g = '<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%.2f"/>' % (
            *iso(o['x'], o['y'], 0), u, v + o['r'] * MM, INK, THIN)
    return g + '<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s" stroke="%s" stroke-width="%.2f"/>' % (
        u, v, o['r'] * MM, TREE, TREE_LINE, THIN)


def esc(s): return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def count(n, word): return '%d %s%s' % (n, word, '' if n == 1 else 's')


def wrap(s, n):
    lines, cur = [], ''
    for w in s.split(' '):
        if cur and len(cur) + 1 + len(w) > n: lines.append(cur); cur = w
        else: cur = (cur + ' ' + w).strip()
    return lines + [cur] if cur else lines


def hull(pts):
    """Convex hull, counter-clockwise on paper (monotone chain)."""
    pts = sorted(set((round(u, 2), round(v, 2)) for u, v in pts))
    if len(pts) < 3:
        return pts
    def half(ps):
        h = []
        for q in ps:
            while len(h) > 1 and (h[-1][0] - h[-2][0]) * (q[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (q[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(q)
        return h[:-1]
    return half(pts) + half(pts[::-1])


def band(hl, y0, y1):
    """The hull's left and right edge between two heights on paper."""
    us = [u for u, v in hl if y0 <= v <= y1]
    for (ua, va), (ub, vb) in zip(hl, hl[1:] + hl[:1]):
        for y in (y0, y1):
            if (va - y) * (vb - y) < 0:
                us.append(ua + (y - va) / (vb - va) * (ub - ua))
    if not us:
        us = [min(hl, key=lambda q: min(abs(q[1] - y0), abs(q[1] - y1)))[0]]
    return min(us), max(us)


M, GAP, CW = 15.0, 10.0, 0.55 * TXT          # margin, gap between types, width of a character
LH = TXT * 1.35
NW = 26                                       # characters on a line of a note


def ensemble(t):
    """One block drawn whole, with the ground, street and trees around it and its notes: svg, extent on paper, notes."""
    mem = t['members']
    pts = [q for b in mem for q in b['rings'][0]]
    cx, cy = statistics.fmean(q[0] for q in pts), statistics.fmean(q[1] for q in pts)
    e = max(((b['rings'][0][i - 1], b['rings'][0][i]) for b in mem for i in range(len(b['rings'][0]))), key=lambda ab: math.dist(*ab))
    base = math.pi / 2 - math.atan2(e[1][1] - e[0][1], e[1][0] - e[0][0])   # the longest edge along y, on the left

    def turn(ang):
        ca, sa = math.cos(ang), math.sin(ang)
        return lambda q: ((q[0] - cx) * ca - (q[1] - cy) * sa, (q[0] - cx) * sa + (q[1] - cy) * ca)

    def window(R):
        x0, y0, x1, y1 = bbox([R(q) for q in pts])
        return (x0 - MARGIN, y0 - MARGIN, x1 + MARGIN, y1 + MARGIN)

    # of the four quarter turns, the one that puts the widest street nearest the viewer, so the street side faces us
    reach = max(math.dist(q, (cx, cy)) for q in pts) + 2 * MARGIN
    near = []
    for s in STREETS:
        if s['bb'][0] > cx + reach or s['bb'][2] < cx - reach or s['bb'][1] > cy + reach or s['bb'][3] < cy - reach:
            continue
        for p1, p2 in zip(s['pts'], s['pts'][1:]):
            k = max(1, int(math.dist(p1, p2) / 2))
            near += [((p1[0] + (p2[0] - p1[0]) * i / k, p1[1] + (p2[1] - p1[1]) * i / k), s['w'] or 0) for i in range(k + 1)]
    best = None
    for k in range(4):
        R = turn(base + k * math.pi / 2)
        bx = window(R)
        inn = [(R(q), w) for q, w in near]
        inn = [(q, w) for q, w in inn if bx[0] <= q[0] <= bx[2] and bx[1] <= q[1] <= bx[3]]
        if inn:
            wmax = max(w for _, w in inn)
            sc = min(q[0] + q[1] for q, w in inn if w == wmax)
            if best is None or sc < best[0] - 1e-6:
                best = (sc, k)
    ang = base + (best[1] if best else 0) * math.pi / 2
    R = turn(ang)
    BOX = window(R)
    ca, sa = math.cos(-ang), math.sin(-ang)
    WB = bbox([(x * ca - y * sa + cx, x * sa + y * ca + cy) for x, y in ((BOX[0], BOX[1]), (BOX[2], BOX[1]), (BOX[2], BOX[3]), (BOX[0], BOX[3]))])

    def hits(bb, pad=0.0):
        return bb[0] <= WB[2] + pad and bb[2] >= WB[0] - pad and bb[1] <= WB[3] + pad and bb[3] >= WB[1] - pad

    # the block's buildings, a gable roof on a footprint that is (nearly) a rectangle
    objs = []
    for b in mem:
        rings = orient([[R(q) for q in r] for r in b['rings']])
        o = dict(tree=False, rings=rings, h=b['h'], floors=b['floors'], roof=b['roof'], part=b['part'], gf=b['gf'],
                 use=b['use'], fp=b['fp'], shop=bool(b['gf']) and not b['gf'].startswith('hous'), gable=None, top=b['h'])
        if b['roof'] == 'gable':
            x0, y0, x1, y1 = bbox(rings[0])
            if len(rings) == 1 and area(rings[0]) >= 0.85 * (x1 - x0) * (y1 - y0):
                o['rings'] = [[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]
                rise = min(x1 - x0, y1 - y0) / 2 * math.tan(math.radians(PITCH))
                o['gable'], o['top'] = ((y1 - y0) >= (x1 - x0), x0, x1, y0, y1, rise), b['h'] + rise
            else:
                DRAWN['gable_flat'] += 1
        objs.append(o)
    blds = list(objs)
    for tr in TREES:
        if not (WB[0] <= tr['x'] <= WB[2] and WB[1] <= tr['y'] <= WB[3]):
            continue
        x, y = R((tr['x'], tr['y']))
        if not (BOX[0] <= x <= BOX[2] and BOX[1] <= y <= BOX[3]) or any(inside((x, y), o['rings']) for o in blds):
            continue
        crown = float(tr['crown'] or TREE_CROWN)
        objs.append(dict(tree=True, x=x, y=y, r=crown / 2, h=max(float(tr['h'] or TREE_H), crown), group=tr['group'], src=tr['src']))
        DRAWN['trees'] += 1
        DRAWN['unsized'] += not (tr['crown'] and tr['h'])
    for o in objs:
        if o['tree']:
            o['w0'], o['w1'], o['s'] = o['x'] - o['y'] - o['r'] / C, o['x'] - o['y'] + o['r'] / C, o['x'] + o['y']
        else:
            ws = [x - y for x, y in o['rings'][0]]
            o['w0'], o['w1'], o['s'] = min(ws), max(ws), statistics.fmean(x + y for x, y in o['rings'][0])

    g, ext = [], []
    # the ground: open space and yards, then the streets with an outline only where they end on the ground
    ground = []
    for gd in GROUND:
        if hits(gd['bb']):
            rr = [r for r in (clip([R(q) for q in ring], BOX) for ring in gd['rings']) if len(r) > 2]
            if rr and area(rr[0]) >= 1:
                ground.append((gd, rr))
    for gd, rr in sorted(ground, key=lambda x: G_ORDER.get(x[0]['key'], 1)):
        fill = ST.get(gd['key'])
        g.append('<path d="%s" fill="%s" fill-rule="evenodd"%s/>' % (
            dpath(rr), fill or PAPER, '' if fill else ' stroke="%s" stroke-width="%.2f"' % (INK, THIN)))
        ext += [iso(x, y, 0) for x, y in rr[0]]
    pieces, segs = [], []
    wide = (BOX[0] - 2, BOX[1] - 2, BOX[2] + 2, BOX[3] + 2)   # cut a little wider, so no edge is drawn where the window cuts
    for s in STREETS:
        hw = (s['w'] or 8.0) / 2
        if not hits(s['bb'], hw):
            continue
        q = [R(p_) for p_ in s['pts']]
        for i, (p1, p2) in enumerate(zip(q, q[1:])):
            L = math.dist(p1, p2)
            c = clip_seg(p1, p2, (BOX[0] - hw, BOX[1] - hw, BOX[2] + hw, BOX[3] + hw))
            if L < 1e-6 or not c:
                continue
            nx, ny = -(p2[1] - p1[1]) / L * hw, (p2[0] - p1[0]) / L * hw
            for ring in ([(p1[0] + nx, p1[1] + ny), (p2[0] + nx, p2[1] + ny), (p2[0] - nx, p2[1] - ny), (p1[0] - nx, p1[1] - ny)],
                         [(p1[0] + hw * math.cos(j * math.pi / 8), p1[1] + hw * math.sin(j * math.pi / 8)) for j in range(16)] if i else []):
                r = clip(ring, wide) if ring else []
                if len(r) > 2:
                    pieces.append(r if is_ccw(r) else r[::-1])
            c = clip_seg(p1, p2, BOX)
            if c:
                segs.append((c, s))
    if pieces:
        CLIPS[0] += 1
        win = [(BOX[0], BOX[1]), (BOX[2], BOX[1]), (BOX[2], BOX[3]), (BOX[0], BOX[3])]
        d = dpath(pieces)
        g.append('<clipPath id="w%d"><path d="%s"/></clipPath><g clip-path="url(#w%d)">'
                 '<path d="%s" fill="none" stroke="%s" stroke-width="%.2f" stroke-linejoin="round"/>'
                 '<path d="%s" fill="%s"/></g>' % (CLIPS[0], dpath([win]), CLIPS[0], d, INK, 2 * THIN, d, ST.get('street', PAPER)))
        ext += [iso(x, y, 0) for r in pieces for x, y in clip(r, BOX)]
    for ln, bb in PATHS:
        if hits(bb):
            q = [R(p_) for p_ in ln]
            for p1, p2 in zip(q, q[1:]):
                c = clip_seg(p1, p2, BOX)
                if c:
                    g.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%.2f" stroke-dasharray="1.2 0.8"/>'
                             % (*iso(*c[0], 0), *iso(*c[1], 0), ST.get('path', INK), THIN))
    for o in far_to_near(objs):
        g.append(tree_svg(o) if o['tree'] else building_svg(o))
        if o['tree']:
            u, v = iso(o['x'], o['y'], o['h'] - o['r'])
            ext += [(u - o['r'] * MM, v - o['r'] * MM), (u + o['r'] * MM, v + o['r'] * MM), iso(o['x'], o['y'], 0)]
        else:
            ext += [iso(x, y, z) for x, y in o['rings'][0] for z in (0, o['top'])]

    # anchors for the notes, and the facts of the layers that a note may tell
    def wall_mid(o, z):
        ws = walls(o)
        _, p1, p2, _ = min(ws, key=lambda w: w[0]) if ws else (0, o['rings'][0][0], o['rings'][0][0], 0)
        return iso((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, z)

    def roof_at(o):
        x0, y0, x1, y1 = bbox(o['rings'][0])
        return iso((x0 + x1) / 2, (y0 + y1) / 2, o['top'])

    big = max(blds, key=lambda o: o['fp'])
    tall = max(blds, key=lambda o: o['top'])
    anchors = {'wall': wall_mid(big, big['h'] * 0.55), 'roof': roof_at(tall)}
    facts = []                                  # (anchor, text, source), in the order the layers offer them
    inner = (BOX[0] + MARGIN, BOX[1] + MARGIN, BOX[2] - MARGIN, BOX[3] - MARGIN)
    own = [(gd, rr) for gd, rr in ground if bbox(rr[0])[0] < inner[2] and bbox(rr[0])[2] > inner[0]
           and bbox(rr[0])[1] < inner[3] and bbox(rr[0])[3] > inner[1]]
    yards = [x for x in own if x[0]['court']] or sorted([x for x in own if x[0]['label']], key=lambda x: -x[0]['m2'])[:1]   # its courtyard, else its own grounds
    if yards:
        gd, rr = max(yards, key=lambda x: area(x[1][0]))
        bx = bbox(rr[0])
        anchors['yard'] = iso((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2, 0)
        facts.append(('yard', '%s, %s m\u00b2' % ('courtyard garden' if gd['court'] else gd['label'],
                                                f"{round(sum(y[0]['m2'] for y in yards), -1):,.0f}"),
                      ' and '.join(sorted({y[0]['src'] for y in yards}))))
    roofs = {}
    for o in blds:
        if o['roof'] != 'flat':
            roofs.setdefault(o['roof'], []).append(o)
    if roofs:
        rf, os_ = max(roofs.items(), key=lambda kv: sum(o['fp'] for o in kv[1]))
        anchors['roof'] = roof_at(max(os_, key=lambda o: o['top']))
        facts.append(('roof', '%s roofs, %s m\u00b2' % ({'pv': 'PV'}.get(rf, rf), f"{sum(o['fp'] for o in os_):,}"), 'massing'))
    shops = [o for o in blds if o['shop'] and o['gf'] not in o['use'].lower()]
    if shops:
        o = max(shops, key=lambda o: o['fp'])
        anchors['ground'] = wall_mid(o, o['h'] / o['floors'] / 2)
        facts.append(('ground', 'ground floor: %s' % ', '.join(sorted({o['gf'] for o in shops})), 'massing'))
    towers = [o for o in blds if o['part'] == 'tower']
    if towers:
        o = max(towers, key=lambda o: o['top'])
        anchors['tower'] = roof_at(o)
        facts.append(('tower', 'tower: %s, %s m' % (count(o['floors'], 'floor'), ('%.1f' % o['h']).rstrip('0').rstrip('.')), 'massing'))
    if segs:
        (c0, c1), s = max(segs, key=lambda x: ((x[1]['w'] or 0), math.dist(*x[0])))
        anchors['street'] = iso((c0[0] + c1[0]) / 2, (c0[1] + c1[1]) / 2, 0)
        name = s['name'] or '%s street' % s['level']
        facts.append(('street', '%s, %s m wide' % (name, ('%.1f' % s['w']).rstrip('0').rstrip('.')) if s['w'] else name, 'massing'))
    trees = [o for o in objs if o['tree']]
    if trees:
        mid = ((BOX[0] + BOX[2]) / 2, (BOX[1] + BOX[3]) / 2)
        o = min(trees, key=lambda o: math.dist((o['x'], o['y']), mid))
        anchors['trees'] = iso(o['x'], o['y'], o['h'] - o['r'])
        by = sorted({o['group'] for o in trees}, key=lambda gr: -sum(o['group'] == gr for o in trees))
        facts.append(('trees', '%s: %s' % (count(len(trees), 'tree'), ', '.join('%d %s' % (sum(o['group'] == gr for o in trees), gr) for gr in by[:2])),
                      ' and '.join(sorted({o['src'] for o in trees}))))
    rows = programme_rows(t) if PROG else []
    if rows:
        r = rows[0]
        pg = pages(r)
        facts.append(('wall', re.split(r'\s*[(;]', r['use'])[0].strip() + (', ' + pg[0] if pg else ''), 'programme'))

    # the notes: those written from the narrative and the programme first, then the layers' facts, three to five
    notes = []
    for n_ in (GIVEN.get(t['key']) or [])[:5]:
        if isinstance(n_, dict) and str(n_.get('text', '')).strip():
            if not n_.get('source'):
                UNSURE.append('a note of %s in notes.json has no source' % t['key'])
            notes.append((anchors.get(n_.get('at')) or anchors['wall'], str(n_['text']).strip(), str(n_.get('source') or 'source not given'), True))
    for at, text, src in facts:
        if len(notes) >= 4:
            break
        notes.append((anchors.get(at, anchors['wall']), text, src, False))

    hl = hull(ext)
    cu = (min(u for u, _ in hl) + max(u for u, _ in hl)) / 2
    sides = {-1: [], 1: []}
    for n_ in notes:
        sides[-1 if n_[0][0] < cu else 1].append(n_)
    for s_ in (-1, 1):
        while len(sides[s_]) > len(sides[-s_]) + 1:     # balance the two sides, the note nearest the middle moves
            sides[s_].sort(key=lambda n_: -s_ * n_[0][0])
            sides[-s_].append(sides[s_].pop())
    out_n, box_n, side_w, side_h = [], [], {-1: 0.0, 1: 0.0}, {-1: 0.0, 1: 0.0}
    for s_ in (-1, 1):
        y = -1e9
        for (au, av), text, src, given in sorted(sides[s_], key=lambda n_: n_[0][1]):
            lines = [[(ln, False)] for ln in wrap(text, NW)]
            tag = '(%s)' % src
            if len(''.join(x for x, _ in lines[-1])) + 1 + len(tag) <= NW + 6:
                lines[-1] += [(' ', False), (tag, True)]
            else:
                lines.append([(tag, True)])
            hgt = len(lines) * LH
            top = max(av - hgt / 2, y + LH * 0.5)
            u0, u1 = band(hl, top - 1, top + hgt + 1)
            x = u0 - 4 if s_ < 0 else u1 + 4
            tw = max(len(''.join(x_ for x_, _ in ln)) for ln in lines) * CW
            for i, ln in enumerate(lines):
                out_n.append('<text x="%.2f" y="%.2f" font-size="%.2f" font-family="%s" fill="%s" text-anchor="%s">%s</text>' % (
                    x, top + TXT + i * LH, TXT, esc(FONT), INK, 'end' if s_ < 0 else 'start',
                    ''.join('<tspan%s>%s</tspan>' % (' font-style="italic"' if it else '', esc(x_)) for x_, it in ln)))
            ly = top + TXT * 0.65
            out_n.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%.2f"/>'
                         '<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s"/>' % (x - s_ * 1.2, ly, au, av, INK, THIN, au, av, 0.5, INK))
            box_n += [(x - tw if s_ < 0 else x, top), (x if s_ < 0 else x + tw, top + hgt)]
            y = top + hgt
            side_w[s_], side_h[s_] = max(side_w[s_], tw + 4), side_h[s_] + hgt + LH * 0.5
    us = [u for u, _ in ext + box_n]
    vs = [v for _, v in ext + box_n]
    return dict(g='<g class="ensemble">%s<g class="notes">%s</g></g>' % (''.join(g), ''.join(out_n)),
                u0=min(us), u1=max(us), v0=min(vs), v1=max(vs), notes=notes,
                dw=max(u for u, _ in ext) - min(u for u, _ in ext), dh=max(v for _, v in ext) - min(v for _, v in ext),
                nw=side_w[-1] + side_w[1], nh=max(side_h.values()))


# ---------- layout: as many types as the frame holds, the most built first, in rows within its width and height ----------
COL_MIN = 34 * CW                             # a label column holds at least ~34 characters
SB_W = 14.0                                    # the scale bar's column
LEFT = M + SB_W + GAP                          # where the types start in every row
head = M + TTL + LH * (2 if mass_stand_in or prog_stand_in else 1) + 6
cols = []
for t in TYPES:
    for k_ in DRAWN:
        DRAWN[k_] = 0
    e = ensemble(t)
    e['drawn'] = dict(DRAWN)                   # what this block draws: windows, gables, trees ...
    w = max(e['u1'] - e['u0'], COL_MIN)
    lab = [(t['key'] + (' (stand-in)' if mass_stand_in else ''), True)]
    lab += [(s, False) for s in wrap(programme_line(t), int(w / CW))]
    parts = sorted({b['part'] for b in t['members']})
    lab += [('block of %s%s: footprint %s m\u00b2' % (count(len(t['members']), 'building'),
                                                     ' (%s)' % ', '.join(parts) if len(parts) > 1 else '', f"{t['fp']:,}"), False),
            ('%s, up to %s m%s' % ('%d\u2013%d floors' % (t['fl_min'], t['floors']) if t['fl_min'] < t['floors'] else count(t['floors'], 'floor'),
                                   ('%.1f' % t['h']).rstrip('0').rstrip('.'), '' if t['h_src'] == 'height_m' else ' \u00b7 height ' + t['h_src']), False),
            ('floor area %s m\u00b2 \u00b7 %s, %s of this type' % (f"{t['gfa']:,}", count(t['blocks'], 'block'), count(t['n'], 'building')), False)]
    cols.append(dict(t=t, e=e, w=w, lab=lab, top=e['v1'] - e['v0']))
avail = float(panel_w) - LEFT - M if panel_w else float('inf')   # room for the types in one row


def legend_for(Wl, dr):
    lg = ['new buildings white, one face in shade' + ('; windows: an illustrative rhythm of %g m bays, shop fronts where the '
                                                     'ground floor is not housing' % BAY if dr['windows'] else '; fine lines: floors')
          + ('; gable roofs at an assumed %g\u00b0 pitch' % PITCH if dr['gable'] else '') + '. True lengths along the three axes.']
    lg += wrap('Ground, streets and trees as the massing%s places them%s. Notes: what each type offers, their source in brackets.' % (
        ' and the open space' if OJ else '', ' (trees without a size drawn %g m wide and %g m high, assumed)' % (TREE_CROWN, TREE_H)
        if dr['unsized'] else ''), int((Wl - 2 * M) / CW))
    lg += wrap('Sources: %s; %s%s%s; the block with the most buildings of each type, of median footprint among those.' % (
        'stand-in shapes (assumed sizes)' if not FEATS else 'massing/massing.geojson' + (' (itself a stand-in)' if mass_stand_in else ''),
        ('no programme' if not FEATS else 'programme stand-in from the massing') if prog_stand_in else 'programme/programme.csv',
        '; open-space/open-space.geojson' if OJ else '', '; building-types/notes.json' if GIVEN else ''), int((Wl - 2 * M) / CW))
    lg[0:1] = wrap(lg[0], int((Wl - 2 * M - TXT * 1.6) / CW))
    return lg


def layout(sel, k=None):
    """Rows, width, height and baselines of these types; with k, about so with their blocks k times their size."""
    per = math.ceil(math.sqrt(len(sel)))       # without a width: a grid about as wide as it is tall
    rows, used = [[]], 0.0
    for c in sel:                              # in order, low to high; a new row when the next type doesn't fit
        w = c['w'] if k is None else max(c['e']['dw'] * k + c['e']['nw'], COL_MIN)
        if rows[-1] and (used + w > avail if panel_w else len(rows[-1]) >= per):
            rows.append([]); used = 0.0
        rows[-1].append((c, w)); used += w + GAP
    nl = max(len(c['lab']) for c in sel)
    Wl = LEFT + max(sum(w for _, w in r) + GAP * (len(r) - 1) for r in rows) + M
    bases, y = [], head                        # each row as tall as its tallest block; one baseline per row
    for r in rows:
        y += max(c['top'] if k is None else max(c['e']['dh'] * k, c['e']['nh']) for c, _ in r)
        bases.append(y)
        y += 6 + nl * LH + 10
    dr = {kk: sum(c['e']['drawn'][kk] for c in sel) for kk in DRAWN}
    Hl = bases[-1] + 6 + nl * LH + 4 + (len(legend_for(Wl, dr)) + 1) * LH + M
    return [[c for c, _ in r] for r in rows], Wl, Hl, bases, nl, dr


def fits(sel, k=None):
    _, Wl, Hl, *_ = layout(sel, k)
    return (not panel_w or Wl <= float(panel_w) + 0.5) and (not frame_h or Hl <= float(frame_h) + 0.5)


def low_to_high(cs): return sorted(cs, key=lambda c: (c['t']['h'], c['t']['key']))


MOST = sorted(cols, key=lambda c: (-c['t']['n'], c['t']['key']))   # the types with the most buildings first
SEL = []
for c in MOST:
    if len(SEL) < MAX_TYPES and fits(low_to_high(SEL + [c])):
        SEL = low_to_high(SEL + [c])
none_fit = not SEL
SEL = SEL or MOST[:1]                          # not even one fits: the most built alone, and the summary says so
LEFT_OUT = [c['t']['key'] for c in MOST if all(c is not s for s in SEL)]
ROWS, W, H, BASES, nlab, DRAWN = layout(SEL)
for row in ROWS:
    x = LEFT
    for c in row:
        c['x'] = x; x += c['w'] + GAP
legend = legend_for(W, DRAWN)


def size_at(k): return layout(SEL, k)[1:3]

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
sx = M + SB_W - 2
for row, BASE in zip(ROWS, BASES):
    nst = max(2, min(6, int(max(c['top'] for c in row) / (step * MM))))
    for c in row:   # each block's lowest point on its row's baseline, centred in its column
        dx = c['x'] + c['w'] / 2 - (c['e']['u0'] + c['e']['u1']) / 2
        svg.append('<g transform="translate(%.2f %.2f)">%s</g>' % (dx, BASE - c['e']['v1'], c['e']['g']))
        for i, (s, bold) in enumerate(c['lab']):
            T(c['x'], BASE + 6 + TXT + i * LH, s, TXT, bold)
    d = 'M %.2f %.2f' % (sx, BASE)
    for k in range(nst):
        off = 1.2 if k % 2 == 0 else 0
        d += ' L %.2f %.2f L %.2f %.2f' % (sx - off, BASE - k * step * MM, sx - off, BASE - (k + 1) * step * MM)
    svg.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.2f"/>' % (d, INK, THIN))
    for k in range(nst + 1):
        yk = BASE - k * step * MM
        svg.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%.2f"/>' % (sx - 2.4, yk, sx, yk, INK, THIN))
        T(sx - 3.2, yk + TXT * 0.35, '%d%s' % (k * step, ' m' if k == nst else ''), TXT, anchor='end')

# legend and source lines
ly = H - M - LH * len(legend)
svg.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s" stroke="%s" stroke-width="%.2f"/>' % (M, ly - TXT * 0.8, TXT, TXT, SHADE, INK, MID))
for i, s in enumerate(legend):
    T(M + (TXT * 1.6 if i == 0 else 0), ly + i * LH, s, TXT)

# ---------- write ----------
tag = '1-%d' % scale
name = file_name or 'building-types_%s' % tag
body = ''.join(svg)
def write(p, w, h):
    Path(p).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %.2f %.2f">%s</svg>'
                       % (w, h, W, H, body), encoding='utf8')
svg_path = OUT / (name + '.svg')
write(svg_path, '%.1fmm' % W, '%.1fmm' % H)

k_px = min(3000 / W, 12000 / H)                # 3000 px wide, unless that makes it taller than 12,000 px
pw, ph = int(round(W * k_px)), int(round(H * k_px))
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
    w.writerow(['type', 'uses', 'buildings', 'footprint_m2', 'floors', 'height_m', 'height_source', 'gfa_m2', 'gfa_all_m2', 'programme', 'stand_in',
                'block', 'block_buildings', 'blocks', 'notes', 'drawn'])
    for c in cols:
        t = c['t']
        w.writerow([t['key'], ' / '.join(t['uses']), t['n'], t['fp'], t['floors'], t['h'], t['h_src'], t['gfa'], t['gfa_all'],
                    programme_line(t), mass_stand_in or prog_stand_in, t['block'], len(t['members']), t['blocks'],
                    ' | '.join('%s (%s)' % (text, src) for _, text, src, _ in c['e']['notes']), t['key'] not in LEFT_OUT])

fits = ''
if len(ROWS) > 1:
    fits = ' Wrapped into %d rows of %s types on a shared baseline grid, at the same scale%s.' % (
        len(ROWS), ', '.join(str(len(r)) for r in ROWS), ', to keep within the %.0f mm %s' % (float(panel_w), ROOM_WORD) if panel_w else '')
if panel_w or frame_h:
    big_w, big_h = panel_w and W > float(panel_w) + 0.5, frame_h and H > float(frame_h) + 0.5
    fits += ' It is %.0f x %.0f mm, %s the %s %s.' % (W, H, 'LARGER than' if big_w or big_h else 'within',
                                                       ' x '.join('%.0f mm' % float(v) for v in (panel_w, frame_h) if v), ROOM_WORD)
    if big_w or big_h:
        nxt = next((s_ for s_ in (750, 1000, 1250, 1500, 2000, 2500, 3000, 5000) if s_ > scale
                    and all(not lim or v <= float(lim) for v, lim in zip(size_at(scale / s_), (panel_w, frame_h)))), None)
        UNSURE.append('not even one type fits its ' + ROOM_WORD + ' at 1:%s, so the one with the most buildings is drawn alone, ' % f"{scale:,}"
                      + ('it would about fit at 1:%d (the scale was not changed)' % nxt if nxt else
                         'and even at 1:5,000 its text alone would need about %.0f x %.0f mm: the frame needs more room' % size_at(scale / 5000)))
if LEFT_OUT:
    fits += ' Left out, %s, all in types.csv: %s.' % (
        'to fit the ' + ROOM_WORD if panel_w or frame_h else 'at most %d types drawn' % MAX_TYPES, ', '.join(LEFT_OUT))
# the frame this drawing needs at its scale, for panel-layout's second run; the format is in the drawings' TOPIC.md
request = {'drawing': svg_path.name, 'scale': '1:%d' % scale, 'needs_mm': {'w': math.ceil(W), 'h': math.ceil(H)},
           'planned_frame_mm': planned_frame, 'by': 'building-types', 'why': '%d of %d types' % (len(SEL), len(TYPES))}
(OUT / (name + '.frame.json')).write_text(json.dumps(request, indent=1) + '\n', encoding='utf8')
if planned_frame:
    fits += ' Asks for a frame of %d x %d mm at 1:%s in %s.frame.json (planned: %s x %s mm).' % (
        request['needs_mm']['w'], request['needs_mm']['h'], f"{scale:,}", name, planned_frame['w'], planned_frame['h'])
n_given = sum(1 for c in SEL for n_ in c['e']['notes'] if n_[3])
n_notes = sum(len(c['e']['notes']) for c in SEL)
illus = ['windows in %g m bays' % BAY] if DRAWN['windows'] else []
illus += ['gable pitch %g\u00b0' % PITCH] if DRAWN['gable'] else []
illus += ['%d trees without a size (%g m crown, %g m high)' % (DRAWN['unsized'], TREE_CROWN, TREE_H)] if DRAWN['unsized'] else []
if DRAWN['gable_flat']:
    NOTES.append('%d gable roofs on footprints that are not rectangles were drawn flat' % DRAWN['gable_flat'])
lines = [
    'Drew %d of %d building types as ensembles, one block of each with its ground, street, %d trees and %d notes (%s), in isometric at 1:%s (%s), in %s.%s' % (
        len(SEL), len(TYPES), DRAWN['trees'], n_notes, ', '.join(c['t']['key'] for c in SEL), f"{scale:,}", scale_src, svg_path.name, fits),
    'Tallest type drawn: %s, %d floors, %s m; the drawing is %.0f x %.0f mm printed; %d notes from notes.json, %d from the layers%s.' % (
        SEL[-1]['t']['key'], SEL[-1]['t']['floors'], ('%.1f' % SEL[-1]['t']['h']).rstrip('0').rstrip('.'), W, H, n_given, n_notes - n_given,
        '; illustrative: ' + ', '.join(illus) if illus else ''),
    'Unsure: ' + ('; '.join(UNSURE + NOTES) if (UNSURE or NOTES) else 'nothing flagged') + '. Look: ' + style_src + '.',
]
(OUT / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
print('\n'.join(lines))
print('wrote', svg_path, png if png.exists() else '(no PNG)', OUT / 'types.csv', OUT / 'summary.md', sep='\n  ')
