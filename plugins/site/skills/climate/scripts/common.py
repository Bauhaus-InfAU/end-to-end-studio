"""Shared helpers for the climate scripts: the site, a metric projection, buildings, grids, downloads, the sun."""
import datetime as dt
import json
import math
from pathlib import Path

import numpy as np
import requests
import shapely
from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape

UA = {"User-Agent": "climate-skill/1.0"}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


class Site:
    """The project's site folder, in the UTM zone of the site (metres)."""

    def __init__(self, folder, buildings=None):
        self.dir = Path(folder)
        self.poly_ll = shape(read(self.dir / "site.geojson")["features"][0]["geometry"])
        c = self.poly_ll.centroid
        self.lon, self.lat = c.x, c.y
        zone = int((self.lon + 180) // 6) + 1
        self.crs = CRS.from_epsg((32600 if self.lat >= 0 else 32700) + zone)
        self._fw = Transformer.from_crs(4326, self.crs, always_xy=True)
        self._bw = Transformer.from_crs(self.crs, 4326, always_xy=True)
        self.poly = self.to_m(self.poly_ll)
        self.buildings_path = Path(buildings) if buildings else self.dir / "buildings.geojson"

    def to_m(self, g):
        return shapely.transform(g, lambda xy: np.column_stack(self._fw.transform(xy[:, 0], xy[:, 1])))

    def to_ll(self, g):
        return shapely.transform(g, lambda xy: np.round(np.column_stack(self._bw.transform(xy[:, 0], xy[:, 1])), 7))

    def layer(self, name, folder=None):
        """Features of <name>.geojson in the site folder (or another folder) as (geometry in metres, properties)."""
        p = Path(folder or self.dir) / f"{name}.geojson"
        if not p.exists():
            return []
        return [(self.to_m(shape(f["geometry"])), f.get("properties") or {}) for f in read(p)["features"] if f.get("geometry")]

    def buildings(self, zone=None):
        """Footprints and heights. Height from `height`, else floors x 3 m; buildings with neither are skipped and counted."""
        geoms, h, defaulted, missing = [], [], 0, 0
        for g, p in self.layer(self.buildings_path.stem, self.buildings_path.parent):
            if zone is not None and not g.intersects(zone):
                continue
            H = p.get("height") or (p.get("floors") and 3.0 * float(p["floors"]))
            if not H:
                missing += 1
                continue
            geoms.append(g.buffer(0))
            h.append(float(H))
            defaulted += str(p.get("height_source", "")).startswith("default")
        return np.array(geoms, dtype=object), np.array(h, float), defaulted, missing

    def write_geojson(self, path, feats):
        """feats: list of (geometry in metres, properties). Written in WGS84, longitude first, every shape valid."""
        out = []
        for g, p in feats:
            if g is None or g.is_empty:
                continue
            ll = self.to_ll(g)
            if not ll.is_valid:  # rounding to WGS84 can make a ring cross itself; repair, and keep a polygon a polygon
                fixed = shapely.make_valid(ll)
                if g.geom_type.endswith("Polygon"):
                    fixed = polygons(fixed)
                    if abs(fixed.area - ll.buffer(0).area) > 0.001 * max(ll.buffer(0).area, 1e-12):
                        print(f"WARNING {Path(path).name}: repairing a shape changed its area; check {p}")
                ll = fixed
            out.append({"type": "Feature", "geometry": mapping(ll), "properties": p})
        write_json(path, {"type": "FeatureCollection", "features": out})


def polygons(g):
    """Only the polygons of a shape, however deeply they are nested (a collection can hold MultiPolygons)."""
    parts, todo = [], [g]
    while todo:
        q = todo.pop()
        if q.geom_type == "Polygon":
            parts.append(q)
        elif q.geom_type in ("MultiPolygon", "GeometryCollection"):
            todo += list(q.geoms)
    return parts[0] if len(parts) == 1 else shapely.MultiPolygon(parts)


def grid(poly, cell):
    """Centres of square cells of `cell` metres inside poly."""
    x0, y0, x1, y1 = poly.bounds
    xs, ys = np.meshgrid(np.arange(x0 + cell / 2, x1, cell), np.arange(y0 + cell / 2, y1, cell))
    pts = shapely.points(xs.ravel(), ys.ravel())
    keep = shapely.contains(poly, pts)
    return xs.ravel()[keep], ys.ravel()[keep]


def bands(xs, ys, values, cell, edges, clip):
    """Merge grid cells into one (multi)polygon per class [edges[i], edges[i+1])."""
    out = []
    boxes = shapely.box(xs - cell / 2, ys - cell / 2, xs + cell / 2, ys + cell / 2)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (values >= lo) & (values < hi)
        if m.any():
            g = shapely.union_all(boxes[m]).intersection(clip).simplify(cell / 4)
            out.append((lo, hi, g))
    return out


def timezone(lat, lon):
    """IANA time zone of a point (Open-Meteo), or None."""
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=30, headers=UA,
                         params=dict(latitude=lat, longitude=lon, timezone="auto", current="temperature_2m"))
        return r.json()["timezone"]
    except Exception:
        return None


def local_to_utc(date, hour, tzname, lon):
    """Clock time on a date to UTC; without a time zone, local solar time."""
    if tzname:
        from zoneinfo import ZoneInfo
        t = dt.datetime(date.year, date.month, date.day, hour, tzinfo=ZoneInfo(tzname))
        return t.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return dt.datetime(date.year, date.month, date.day, hour) - dt.timedelta(hours=lon / 15)


def sunpos(utc, lat, lon):
    """Sun altitude and azimuth in degrees (NOAA formulas). utc: array of numpy datetime64."""
    utc = np.asarray(utc, dtype="datetime64[s]")
    jd = (utc - np.datetime64("1970-01-01T00:00:00")).astype(float) / 86400 + 2440587.5
    T = (jd - 2451545) / 36525
    L = (280.46646 + T * (36000.76983 + T * 0.0003032)) % 360
    M = np.radians(357.52911 + T * (35999.05029 - 0.0001537 * T))
    e = 0.016708634 - T * (0.000042037 + 0.0000001267 * T)
    C = np.sin(M) * (1.914602 - T * (0.004817 + 0.000014 * T)) + np.sin(2 * M) * (0.019993 - 0.000101 * T) + np.sin(3 * M) * 0.000289
    om = np.radians(125.04 - 1934.136 * T)
    lam = np.radians(L + C - 0.00569 - 0.00478 * np.sin(om))
    eps = np.radians(23 + (26 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60) / 60 + 0.00256 * np.cos(om))
    dec = np.arcsin(np.sin(eps) * np.sin(lam))
    y = np.tan(eps / 2) ** 2
    Lr = np.radians(L)
    eot = 4 * np.degrees(y * np.sin(2 * Lr) - 2 * e * np.sin(M) + 4 * e * y * np.sin(M) * np.cos(2 * Lr)
                         - 0.5 * y * y * np.sin(4 * Lr) - 1.25 * e * e * np.sin(2 * M))
    minutes = (utc - utc.astype("datetime64[D]")).astype(float) / 60
    ha = np.radians(((minutes + eot + 4 * lon) % 1440) / 4 - 180)
    la = math.radians(lat)
    alt = np.arcsin(np.sin(la) * np.sin(dec) + np.cos(la) * np.cos(dec) * np.cos(ha))
    az = np.degrees(np.arctan2(np.sin(ha), np.cos(ha) * np.sin(la) - np.tan(dec) * np.cos(la))) + 180
    return np.degrees(alt), az % 360


def shadow_hulls(geoms, heights, alt_deg, az_deg, max_len=400):
    """Ground shadow of each building as the hull of its footprint and the footprint moved away from the sun."""
    L = np.minimum(heights / math.tan(math.radians(alt_deg)), max_len)
    dx, dy = -math.sin(math.radians(az_deg)) * L, -math.cos(math.radians(az_deg)) * L
    xy, idx = shapely.get_coordinates(geoms, return_index=True)
    allc = np.r_[xy, xy + np.c_[dx[idx], dy[idx]]]
    alli = np.r_[idx, idx]
    o = np.argsort(alli, kind="stable")
    return shapely.convex_hull(shapely.multipoints(allc[o], indices=alli[o]))


def overpass(query):
    """Run an Overpass query, trying mirrors in turn."""
    err = None
    for u in OVERPASS:
        try:
            r = requests.post(u, data={"data": query}, timeout=120, headers=UA)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            err = e
    raise RuntimeError(f"Overpass unreachable: {err}")
