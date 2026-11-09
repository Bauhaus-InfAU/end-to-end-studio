"""The mobility skill's script: routes by mode, stops, hubs and car access, and the walking shares to the main stop."""
import json, os, re, subprocess, sys
import pytest
from conftest import REPO
from synthetic import make_proposal

MOBILITY = REPO / "plugins/design/skills/mobility/scripts/mobility.py"
MASSING = REPO / "plugins/design/skills/massing/scripts/massing.py"
CONFIG = {"hub": "Square", "main_stop": "Square", "walk_limits_m": [400, 800], "car_access": ["Gate"], "scale": 3000}


def run(script, *args, check=True):
    r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONUTF8": "1"})   # the scripts write their text as UTF-8 on Windows too
    if check and r.returncode:
        raise AssertionError(r.stderr[-2000:])
    return r


def mobility(out, site_dir, cfg, check=True):
    path = out / "mobility/config.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({k: {"value": v, "source": "test"} for k, v in cfg.items()}), encoding="utf-8")
    return run(MOBILITY, "--proposal", out, "--site", site_dir, "--config", path,
               "--style", out / "drawing-graphics/style.json", check=check)


def features(out):
    return [f["properties"] for f in json.loads((out / "mobility/mobility.geojson").read_text(encoding="utf-8"))["features"]]


@pytest.fixture(scope="module")
def massed(tmp_path_factory):
    """The synthetic proposal with its massing: (proposal, site folder)."""
    root = tmp_path_factory.mktemp("mobility") / "with space"
    out = make_proposal(root)
    run(MASSING, "--proposal", out, "--site", root / "site", "--config", out / "massing/config.json")
    return out, root / "site"


def test_mobility_runs_on_synthetic(massed):
    out, site_dir = massed
    assert mobility(out, site_dir, CONFIG).returncode == 0
    assert {"route", "stop", "hub", "access"} <= {p["kind"] for p in features(out)}
    walk = json.loads((out / "mobility/walk.json").read_text(encoding="utf-8"))
    for key in ("within_400m", "within_800m", "unreached"):
        assert 0 <= walk[key] <= 1, (key, walk)
    assert walk["within_800m"] >= walk["within_400m"]
    stats = json.loads((out / "mobility/stats.json").read_text(encoding="utf-8"))
    assert stats["walk"]["within_400m"] == walk["within_400m"]
    for ext in (".svg", ".png"):
        assert (out / "mobility" / ("mobility_1-3000" + ext)).exists(), ext
    svg = (out / "mobility/mobility_1-3000.svg").read_text(encoding="utf-8")
    k = 3000 / 1000   # metres of the drawing per mm on paper
    sizes = [float(s) for s in re.findall(r'font-size="([\d.]+)"', svg)]
    assert sizes and min(sizes) / k >= 3.2 - 1e-6, min(sizes) / k


def test_mobility_fills_its_frame(massed):
    """A frame in the panels' plan: the plan is that size at that scale, its legend inside, in the standard's `diagram`."""
    out, site_dir = massed
    plan = out / "panel-layout/layout-plan.json"
    plan.parent.mkdir(exist_ok=True)
    plan.write_text(json.dumps({"panels": [{"items": [{"file": "mobility/mobility_1-5000.svg", "scale": "1:5000",
                                                        "frame": {"w": 150, "h": 120}}]}]}), encoding="utf-8")
    try:
        mobility(out, site_dir, CONFIG)
    finally:
        plan.unlink()
    svg = (out / "mobility/mobility_1-5000.svg").read_text(encoding="utf-8")
    assert 'width="150.0mm" height="120.0mm"' in svg and 'viewBox="0 0 750.00 600.00"' in svg
    k = 5000 / 1000
    assert min(float(s) for s in re.findall(r'font-size="([\d.]+)"', svg)) / k >= 3.2 - 1e-6
    widths = [float(w) for w in re.findall(r'stroke-width="([\d.]+)"', svg)]
    assert not any(abs(w - 3.2 * 25.4 / 96 * k) < 0.01 for w in widths)   # no line at diagram.heavy: the bus is not heavier
    style = json.loads((out / "drawing-graphics/style.json").read_text(encoding="utf-8"))
    bus = style[style["modes"]["bus"]]   # each mode in one of the standard's own colours
    assert f'stroke="{bus}" stroke-width="{1.6 * 1.3 * 25.4 / 96 * k:.2f}"' in svg   # one weight for every main route
    assert "Mobility plan, 1:5,000" not in svg   # on a panel, the panel writes the caption and scale


def test_mobility_without_hub_runs(massed):
    """A brief with no hub: the plan is made without one."""
    out, site_dir = massed
    cfg = {k: v for k, v in CONFIG.items() if k != "hub"}
    assert mobility(out, site_dir, cfg).returncode == 0
    assert not [p for p in features(out) if p["kind"] == "hub" and p.get("level") == "main"]


def test_mobility_unknown_hub_stops(massed):
    """A hub named in config.json but not in the structure plan stops the script with its name."""
    out, site_dir = massed
    r = mobility(out, site_dir, {**CONFIG, "hub": "Nowhere"}, check=False)
    assert r.returncode != 0
    assert "hub" in r.stderr


def test_mobility_mode_words(massed):
    out, site_dir = massed
    sp = out / "structure-plan/structure-plan.geojson"
    held = sp.read_text(encoding="utf-8")
    fc = json.loads(held)
    for f in fc["features"]:
        if f["properties"].get("name") == "Main road":
            f["properties"]["mode"] = "foot and cycle only"
    sp.write_text(json.dumps(fc), encoding="utf-8")
    try:
        mobility(out, site_dir, CONFIG)
    finally:
        sp.write_text(held, encoding="utf-8")
    modes = {p["mode"] for p in features(out) if p["kind"] == "route" and p["name"] == "Main road"}
    assert modes == {"foot", "bike"}, modes


def label_boxes(svg, names):
    """{text: its box in the drawing's units} of the labels with these texts."""
    from shapely.geometry import box
    boxes = {}
    for attrs, s in re.findall(r"<text ([^>]*)>([^<]*)</text>", svg):
        if s in names:
            a = dict(re.findall(r'([\w-]+)="([^"]*)"', attrs))
            x, y, fs = float(a["x"]), float(a["y"]), float(a["font-size"])
            w = len(s) * fs * 0.56
            x0 = {"start": x, "end": x - w, "middle": x - w / 2}[a.get("text-anchor", "start")]
            boxes[s] = box(x0, y - 0.75 * fs, x0 + w, y + 0.25 * fs)
    return boxes


def test_mobility_label_off_bus_line(massed):
    """A labelled point on a straight bus line: its label sits beside the line, not on it, at no less than 12 px."""
    import pyproj
    from shapely.geometry import shape, mapping, Point, LineString
    from shapely.ops import transform
    out, site_dir = massed
    sp = out / "structure-plan/structure-plan.geojson"
    held = sp.read_text(encoding="utf-8")
    fc = json.loads(held)
    road = shape(next(f["geometry"] for f in fc["features"] if f["properties"].get("name") == "Main road"))
    c = road.centroid
    epsg = (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform
    (ax, ay), _ = transform(to_m, road).coords
    on = Point(ax + 60, ay)   # on the line, away from its gateway and the square
    name = "Line point"
    fc["features"].append({"type": "Feature", "geometry": mapping(transform(to_ll, on.buffer(1))),
                           "properties": {"kind": "centre", "name": name, "level": "local", "holds": "mobility point"}})
    sp.write_text(json.dumps(fc), encoding="utf-8")
    try:
        mobility(out, site_dir, CONFIG)
    finally:
        sp.write_text(held, encoding="utf-8")
    svg = (out / "mobility/mobility_1-3000.svg").read_text(encoding="utf-8")
    k = 3000 / 1000
    lab = label_boxes(svg, [name])[name]
    hub = [(float(x), float(y)) for x, y, r in re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)" fill="#?\w+" stroke', svg)
           if abs(float(r) - 2.2 * k) < 0.01]
    assert hub, "no symbol for the point"
    x, y = min(hub, key=lambda h: Point(h).distance(lab))   # its own symbol, not the legend's
    line = LineString([(0, y), (1e6, y)]).buffer(0.5 * k / 2)   # the bus line as drawn: thick, 0.5 mm
    assert not lab.intersects(line), (lab.bounds, y)
    fs = float(re.search(r'font-size="([\d.]+)"[^>]*>%s<' % name, svg).group(1))
    assert fs / k >= 3.2 - 1e-6, fs / k


def test_mobility_labels_apart(massed):
    """Two labelled points 5 m apart: their label boxes overlap neither each other nor the symbols."""
    import pyproj
    from shapely.geometry import shape, mapping, box, Point
    from shapely.ops import transform
    out, site_dir = massed
    sp = out / "structure-plan/structure-plan.geojson"
    held = sp.read_text(encoding="utf-8")
    fc = json.loads(held)
    sq = shape(next(f["geometry"] for f in fc["features"] if f["properties"].get("name") == "Square"))
    c = sq.centroid
    epsg = (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform
    p = transform(to_m, c)
    names = ["West point", "East point"]
    for name, dx in zip(names, (0, 5)):
        fc["features"].append({"type": "Feature", "geometry": mapping(transform(to_ll, Point(p.x + dx, p.y + 20).buffer(1))),
                               "properties": {"kind": "centre", "name": name, "level": "local", "holds": "mobility point"}})
    sp.write_text(json.dumps(fc), encoding="utf-8")
    try:
        mobility(out, site_dir, CONFIG)
    finally:
        sp.write_text(held, encoding="utf-8")
    svg = (out / "mobility/mobility_1-3000.svg").read_text(encoding="utf-8")
    boxes = label_boxes(svg, names)
    assert set(boxes) == set(names), boxes
    assert not boxes[names[0]].intersects(boxes[names[1]]), boxes
    k = 3000 / 1000
    rings = [Point(float(x), float(y)).buffer(float(r)) for x, y, r in
             re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)" fill="#?\w+" stroke', svg) if abs(float(r) - 2.2 * k) < 0.01]
    assert len(rings) >= 2, len(rings)
    for b in boxes.values():
        assert not any(b.intersects(r) for r in rings), b
