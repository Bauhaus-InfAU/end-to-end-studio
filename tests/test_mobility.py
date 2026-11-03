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


def test_mobility_missing_hub_stops(massed):
    out, site_dir = massed
    cfg = {k: v for k, v in CONFIG.items() if k != "hub"}
    r = mobility(out, site_dir, cfg, check=False)
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
