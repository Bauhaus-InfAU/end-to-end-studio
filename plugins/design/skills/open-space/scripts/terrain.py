"""Ground heights of a site from its folder: a terrain model (GeoTIFF), else a terrain.csv (lon, lat, ele), else none.

    t, notes = find_terrain(site_dir, bounds_m, to_lonlat)   # to_lonlat: a pyproj Transformer, metric CRS -> WGS84
    if t: z = t.sample(xs, ys); t.source                     # metres above sea level at metric points

The GeoTIFF is the one kit.json names under "terrain", else any terrain*.tif; it is read with Pillow, no GDAL.
"""
import csv, glob, json
from pathlib import Path

import numpy as np
import pyproj

NODATA_BELOW = -1000.0   # a cell lower than this is a gap, not ground


class Terrain:
    def __init__(self, source, sampler):
        self.source, self._sampler = source, sampler

    def sample(self, xs, ys):
        """Heights at metric points; gaps take the height of the nearest point that has one."""
        xs, ys = np.asarray(xs, float).ravel(), np.asarray(ys, float).ravel()
        if not len(xs):
            return np.zeros(0)
        z = np.asarray(self._sampler(xs, ys), float)
        bad = np.isnan(z)
        if bad.all():
            return np.zeros(len(xs))
        if bad.any():
            from shapely import STRtree, points
            good = np.flatnonzero(~bad)
            tree = STRtree(points(xs[good], ys[good]))
            z[bad] = z[good[tree.query_nearest(points(xs[bad], ys[bad]), return_distance=False, all_matches=False)[1]]]
        return z


def find_terrain(site_dir, bounds_m, to_lonlat):
    """(the site folder's terrain covering bounds_m, x0 y0 x1 y1 in the metric CRS, or None; notes on what was skipped)."""
    site_dir, notes = Path(site_dir), []
    for tif in _tifs(site_dir):
        try:
            t = _from_tif(tif, bounds_m, to_lonlat)
            if t:
                return t, notes
            notes.append(f"{tif.name} does not cover the site; not used.")
        except Exception as e:   # a tif Pillow cannot read: say so and go on
            notes.append(f"{tif.name} could not be read ({type(e).__name__}: {e}); not used.")
    p = site_dir / "terrain.csv"
    if p.exists():
        t = _from_csv(p, to_lonlat)
        if t:
            return t, notes
        notes.append("terrain.csv has no usable rows; not used.")
    return None, notes


def _tifs(site_dir):
    found = []
    kit = site_dir / "kit.json"
    if kit.exists():
        try:
            name = json.loads(kit.read_text(encoding="utf-8")).get("terrain")
            if name and (site_dir / name).exists():
                found.append(site_dir / name)
        except ValueError:
            pass
    for p in sorted(glob.glob(str(site_dir / "terrain*.tif")) + glob.glob(str(site_dir / "terrain*.tiff"))):
        if Path(p) not in found:
            found.append(Path(p))
    return found


def _from_tif(path, bounds_m, to_lonlat):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(path)
    tags = im.tag_v2
    sx, sy = tags[33550][0], tags[33550][1]          # ModelPixelScale: cell size
    tie = tags[33922]                                 # ModelTiepoint: raster (i, j) -> model (E, N)
    keys = tags[34735]                                # GeoKeyDirectory: groups of (key, location, count, value)
    geo = {keys[i]: keys[i + 3] for i in range(4, len(keys) - 3, 4)}
    epsg = geo.get(3072) or geo.get(2048)             # projected CRS, else geographic
    if not epsg:
        raise ValueError("no EPSG in the GeoKeyDirectory")
    a = np.array(im, dtype=float)
    nodata = tags.get(42113)                          # GDAL_NODATA, as text
    if nodata is not None:
        try:
            a[a == float(str(nodata).strip("\x00 "))] = np.nan
        except ValueError:
            pass
    a[a < NODATA_BELOW] = np.nan
    half = 0.5 if geo.get(1025, 1) == 1 else 0.0      # pixel is area: values at cell centres
    e0, n0 = tie[3] - tie[0] * sx, tie[4] + tie[1] * sy
    to_tif = pyproj.Transformer.from_crs(to_lonlat.source_crs, epsg, always_xy=True)
    rows, cols = a.shape

    def grid(xs, ys):
        X, Y = to_tif.transform(xs, ys)
        c = (np.asarray(X) - e0) / sx - half
        r = (n0 - np.asarray(Y)) / sy - half
        c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int)
        fc, fr = c - c0, r - r0
        ok = (c0 >= 0) & (r0 >= 0) & (c0 + 1 < cols) & (r0 + 1 < rows)
        z = np.full(len(c), np.nan)
        i, j, u, v = r0[ok], c0[ok], fr[ok], fc[ok]
        z[ok] = (a[i, j] * (1 - u) * (1 - v) + a[i, j + 1] * (1 - u) * v
                 + a[i + 1, j] * u * (1 - v) + a[i + 1, j + 1] * u * v)   # bilinear
        return z

    x0, y0, x1, y1 = bounds_m
    probe = grid(np.array([x0, x1, x0, x1, (x0 + x1) / 2]), np.array([y0, y0, y1, y1, (y0 + y1) / 2]))
    if np.isnan(probe).all():
        return None
    return Terrain(f"{path.name} (EPSG:{epsg}, {sx:g} m)", grid)


def _from_csv(path, to_lonlat):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                rows.append((float(r["lon"]), float(r["lat"]), float(r["ele"])))
            except (KeyError, TypeError, ValueError):
                continue
    if not rows:
        return None
    lon, lat, ele = (np.array(c) for c in zip(*rows))
    ulon, ulat = np.unique(lon), np.unique(lat)
    if len(ulon) * len(ulat) == len(rows) and len(ulon) > 1 and len(ulat) > 1:   # a regular grid: bilinear
        g = np.full((len(ulat), len(ulon)), np.nan)
        g[np.searchsorted(ulat, lat), np.searchsorted(ulon, lon)] = ele

        def grid(xs, ys):
            lo, la = (np.asarray(v) for v in to_lonlat.transform(xs, ys))
            j = np.clip(np.searchsorted(ulon, lo) - 1, 0, len(ulon) - 2)
            i = np.clip(np.searchsorted(ulat, la) - 1, 0, len(ulat) - 2)
            v = np.clip((lo - ulon[j]) / (ulon[j + 1] - ulon[j]), 0, 1)
            u = np.clip((la - ulat[i]) / (ulat[i + 1] - ulat[i]), 0, 1)
            return (g[i, j] * (1 - u) * (1 - v) + g[i, j + 1] * (1 - u) * v
                    + g[i + 1, j] * u * (1 - v) + g[i + 1, j + 1] * u * v)
        return Terrain(f"{path.name} (grid)", grid)

    to_m = pyproj.Transformer.from_crs(4326, to_lonlat.source_crs, always_xy=True).transform
    px, py = (np.asarray(v) for v in to_m(lon, lat))

    def idw(xs, ys):   # inverse distance of the 4 nearest points
        out, k = np.empty(len(xs)), min(4, len(px))
        step = max(1, int(5e6 // len(px)))
        for s in range(0, len(xs), step):
            d = np.hypot(xs[s:s + step, None] - px[None], ys[s:s + step, None] - py[None])
            near = np.argpartition(d, k - 1, axis=1)[:, :k]
            dn = np.take_along_axis(d, near, 1)
            w = 1 / np.maximum(dn, 0.01) ** 2
            out[s:s + step] = (ele[near] * w).sum(1) / w.sum(1)
        return out
    return Terrain(f"{path.name} (points)", idw)
