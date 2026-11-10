"""The isometric draws the district at the scale it is given, never a smaller one, and its main centre close up
with use labels from the massing, people and roofs."""
import json, os, subprocess, sys
import pyproj
from shapely.geometry import shape, mapping, box
from shapely.ops import transform, polylabel
from conftest import REPO

SITE = REPO / "competition/site"
ISO = REPO / "plugins/drawings/skills/isometric/isometric.py"


def test_district_at_its_scale_and_the_centre_close_up(tmp_path):
    g = shape(json.loads((SITE / "site.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
    c = g.centroid
    epsg = (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform
    p = polylabel(transform(to_m, g).buffer(-100), 1.0)
    feat = lambda geom, **props: {"type": "Feature", "properties": props, "geometry": mapping(transform(to_ll, geom))}
    out = tmp_path / "proposal"
    (out / "massing").mkdir(parents=True)
    (out / "massing/massing.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        feat(box(p.x - 20, p.y - 20, p.x + 20, p.y + 20), kind="open-space", use="square", name="Square"),
        feat(box(p.x + 25, p.y - 20, p.x + 60, p.y + 10), kind="building", floors=3, height_m=9, use="school",
             ground_floor="school", roof="flat", block=1, part="building"),
        feat(box(p.x - 60, p.y - 20, p.x - 25, p.y + 20), kind="building", floors=5, height_m=15, use="mixed",
             ground_floor="commerce", roof="green", block=2, part="side"),
        feat(box(p.x - 20, p.y + 25, p.x + 20, p.y + 35), kind="building", floors=2, height_m=6, use="housing",
             ground_floor="housing", roof="gable", block=3, part="town house"),
    ]}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ISO), str(SITE), str(out), "3000", "100"], capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode == 0, r.stderr[-2000:]
    iso = out / "isometric"
    assert (iso / "isometric_1-3000.svg").exists()   # wider than the 100 mm panel, still at 1:3000: the panels crop it
    close = (iso / "isometric_centre_1-1000.svg").read_text(encoding="utf-8")
    assert 'width="100mm" height="60mm"' in close   # the panel's width by 0.6 of it, without a frame
    assert ">school<" in close and ">commerce *<" in close and ">Square<" in close   # uses from the massing; * illustrative
    text = (iso / "summary.md").read_text(encoding="utf-8")
    assert "centre Square close up at 1:1000" in text and "people, illustrative" in text and "1 gable" in text


def _two_buildings(tmp_path):
    """Two small buildings far apart along the diagonal that lies across the view from the south-west and north-east."""
    g = shape(json.loads((SITE / "site.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
    epsg = (32600 if g.centroid.y >= 0 else 32700) + int((g.centroid.x + 180) // 6) + 1
    to_m = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform
    c = transform(to_m, g).centroid
    out = tmp_path / "proposal"
    (out / "massing").mkdir(parents=True)
    (out / "massing/massing.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"kind": "building", "floors": 3, "height_m": 9, "use": "housing", "block": i},
         "geometry": mapping(transform(to_ll, box(c.x + d - 10, c.y - d - 10, c.x + d + 10, c.y - d + 10)))}
        for i, d in enumerate((-300, 300))]}), encoding="utf-8")
    return out


def _draw(out, *args):
    r = subprocess.run([sys.executable, str(ISO), str(SITE), str(out), *args], capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode == 0, r.stderr[-2000:]
    return out / "isometric"


def test_fit_draws_the_district_as_large_as_its_frame_holds(tmp_path):
    iso = _draw(_two_buildings(tmp_path), "5000", "100", "--frame", "400", "200", "--fit")
    # 1,074 m across the view and 100 m on each side in 400 mm: 1:3185, rounded to 1:3000; the other sides fill it less
    svg = (iso / "isometric_1-3000.svg").read_text(encoding="utf-8")
    assert 'width="400mm" height="200mm"' in svg
    assert not (iso / "isometric_1-5000.svg").exists()
    text = (iso / "summary.md").read_text(encoding="utf-8")
    assert "south-west" in text or "north-east" in text
    assert "planned at 1:5000" in text


def test_fit_never_draws_smaller_than_planned(tmp_path):
    iso = _draw(_two_buildings(tmp_path), "2000", "100", "--frame", "400", "200", "--fit")
    assert 'width="400mm" height="200mm"' in (iso / "isometric_1-2000.svg").read_text(encoding="utf-8")
    assert "planned at" not in (iso / "summary.md").read_text(encoding="utf-8")


def test_a_frame_without_fit_keeps_the_planned_scale(tmp_path):
    iso = _draw(_two_buildings(tmp_path), "5000", "100", "--frame", "400", "200")
    assert 'width="400mm" height="200mm"' in (iso / "isometric_1-5000.svg").read_text(encoding="utf-8")
