"""Ground heights at any points of a site: from the site folder's terrain model (GeoTIFF), else a terrain CSV,
else a free elevation service along the points asked for, else flat ground.

    t = Terrain.find(site_dir, out_dir, bounds_utm, to_lonlat)   # to_lonlat: a pyproj Transformer, metric CRS -> WGS84
    z = t.sample(xs, ys)                                          # numpy array of metres above sea level
    t.source, t.flat, t.gaps, t.notes

Needs numpy, pyproj, shapely and Pillow; the download needs requests. The environment variable
SECTION_NO_NETWORK=1 skips the download.
"""
import csv, glob, json, os, time
from pathlib import Path

import numpy as np
import pyproj

URL = "https://api.opentopodata.org/v1/eudem25m,mapzen"   # EU-DEM 25 m where it covers, else a global model
WEB_SOURCE = "EU-DEM 25 m / Mapzen via api.opentopodata.org"
FLAT_SOURCE = "flat (no terrain found)"
BATCH, PAUSE = 100, 1.1          # points per request, seconds between requests (the service's limit)
NODATA_BELOW = -1000.0           # a cell lower than this is a gap, not ground


def _fill_nearest(xs, ys, z):
    """Fills NaN samples with the value of the nearest valid sample. Returns (z, number filled)."""
    bad = np.isnan(z)
    n = int(bad.sum())
    if n == 0 or n == len(z):
        return z, n
    gx, gy, gz = xs[~bad], ys[~bad], z[~bad]
    out = z.copy()
    for i in np.flatnonzero(bad):
        out[i] = gz[np.argmin((gx - xs[i]) ** 2 + (gy - ys[i]) ** 2)]
    return out, n


class Terrain:
    def __init__(self, source, sampler, flat=False, notes=()):
        self.source, self._sampler, self.flat = source, sampler, flat
        self.gaps, self.notes = 0, list(notes)

    def sample(self, xs, ys):
        """Heights at metric points xs, ys (in the CRS of to_lonlat)."""
        xs, ys = np.asarray(xs, float), np.asarray(ys, float)
        if self.flat or len(xs) == 0:
            return np.zeros(len(xs))
        z = np.asarray(self._sampler(xs, ys), float)
        if self.flat:   # the sampler gave up (a download failed)
            return np.zeros(len(xs))
        if np.isnan(z).all():
            self.flat, self.source = True, FLAT_SOURCE
            self.notes.append("The terrain model has no value at any point of the section: the ground is drawn flat.")
            return np.zeros(len(xs))
        z, n = _fill_nearest(xs, ys, z)
        self.gaps += n
        return z

    # ------------------------------------------------------------------ the sources, in order
    @classmethod
    def find(cls, site_dir, out_dir, bounds_utm, to_lonlat):
        site_dir, out_dir = Path(site_dir), Path(out_dir)
        notes = []
        for tif in cls._tifs(site_dir):
            try:
                t = cls._from_tif(tif, bounds_utm, to_lonlat)
                if t:
                    return t
                notes.append(f"{tif.name} does not cover the section; not used.")
            except Exception as e:   # a tif PIL cannot read: say so and go on
                notes.append(f"{tif.name} could not be read ({type(e).__name__}: {e}); not used.")
        csv_path = site_dir / "terrain.csv"
        if csv_path.exists():
            t = cls._from_csv(csv_path, to_lonlat, "terrain.csv")
            t.notes = notes + t.notes
            return t
        return cls._from_web(out_dir, to_lonlat, notes)

    @staticmethod
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

    @classmethod
    def _from_tif(cls, path, bounds_utm, to_lonlat):
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
        e0 = tie[3] - (tie[0] - 0) * sx
        n0 = tie[4] + (tie[1] - 0) * sy
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

        x0, y0, x1, y1 = bounds_utm
        probe = grid(np.array([x0, x1, x0, x1, (x0 + x1) / 2]), np.array([y0, y0, y1, y1, (y0 + y1) / 2]))
        if np.isnan(probe).all():
            return None
        cell = sx if sx == sy else f"{sx} x {sy}"
        cell = f"{cell:g}" if isinstance(cell, float) else cell
        return cls(f"{path.name} (EPSG:{epsg}, {cell} m)", grid)

    @classmethod
    def _from_csv(cls, path, to_lonlat, source):
        rows = []
        with open(path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                try:
                    rows.append((float(r["lon"]), float(r["lat"]), float(r["ele"])))
                except (KeyError, TypeError, ValueError):
                    continue
        if not rows:
            return cls(FLAT_SOURCE, None, flat=True, notes=[f"{path.name} has no usable rows: the ground is drawn flat."])
        lon, lat, ele = (np.array(c) for c in zip(*rows))
        to_ll = to_lonlat.transform
        ulon, ulat = np.unique(lon), np.unique(lat)
        if len(ulon) * len(ulat) == len(rows) and len(ulon) > 1 and len(ulat) > 1:   # a regular grid
            g = np.full((len(ulat), len(ulon)), np.nan)
            g[np.searchsorted(ulat, lat), np.searchsorted(ulon, lon)] = ele

            def grid(xs, ys):
                lo, la = (np.asarray(v) for v in to_ll(xs, ys))
                j = np.clip(np.searchsorted(ulon, lo) - 1, 0, len(ulon) - 2)
                i = np.clip(np.searchsorted(ulat, la) - 1, 0, len(ulat) - 2)
                v = np.clip((lo - ulon[j]) / (ulon[j + 1] - ulon[j]), 0, 1)
                u = np.clip((la - ulat[i]) / (ulat[i + 1] - ulat[i]), 0, 1)
                return (g[i, j] * (1 - u) * (1 - v) + g[i, j + 1] * (1 - u) * v
                        + g[i + 1, j] * u * (1 - v) + g[i + 1, j + 1] * u * v)
            return cls(source, grid)

        from shapely import STRtree, points
        to_m = pyproj.Transformer.from_crs(4326, to_lonlat.source_crs, always_xy=True).transform
        px, py = (np.asarray(v) for v in to_m(lon, lat))
        tree = STRtree(points(px, py))

        def idw(xs, ys):   # inverse distance of the 4 nearest
            out = np.empty(len(xs))
            for k, (x, y) in enumerate(zip(xs, ys)):
                r, hit = 50.0, []
                while len(hit) < min(4, len(px)):
                    hit = tree.query(points(x, y).buffer(r))
                    r *= 2
                d = np.hypot(px[hit] - x, py[hit] - y)
                near = np.argsort(d)[:4]
                w = 1 / np.maximum(d[near], 0.01) ** 2
                out[k] = float((ele[hit][near] * w).sum() / w.sum())
            return out
        return cls(source, idw)

    @classmethod
    def _from_web(cls, out_dir, to_lonlat, notes):
        if os.environ.get("SECTION_NO_NETWORK"):
            return cls(FLAT_SOURCE, None, flat=True, notes=notes + [
                "No terrain model in the site folder and the download is switched off: the ground is drawn flat."])
        cache_path = out_dir / "terrain.csv"
        cache = {}
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    try:
                        cache[(r["lon"], r["lat"])] = float(r["ele"])
                    except (KeyError, TypeError, ValueError):
                        pass
        t = cls(WEB_SOURCE, None, notes=notes + ["No terrain model in the site folder: heights downloaded along the section only."])

        def web(xs, ys):
            import requests
            lo, la = to_lonlat.transform(xs, ys)
            pts = [(f"{a:.6f}", f"{b:.6f}") for a, b in zip(np.atleast_1d(lo), np.atleast_1d(la))]
            need = sorted({p for p in pts if p not in cache})
            new = []
            try:
                for i in range(0, len(need), BATCH):
                    part = need[i:i + BATCH]
                    r = requests.post(URL, json={"locations": "|".join(f"{b},{a}" for a, b in part),
                                                 "interpolation": "bilinear"}, timeout=60)
                    r.raise_for_status()
                    for p, res in zip(part, r.json()["results"]):
                        e = res.get("elevation")
                        cache[p] = float("nan") if e is None else float(e)
                        new.append((*p, e, res.get("dataset")))
                    time.sleep(PAUSE)
            except Exception as e:
                t.flat, t.source = True, FLAT_SOURCE
                t.notes.append(f"The terrain could not be downloaded ({type(e).__name__}): the ground is drawn flat.")
                return np.zeros(len(pts))
            if new:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                head = not cache_path.exists()
                with open(cache_path, "a", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    if head:
                        w.writerow(["lon", "lat", "ele", "source"])
                    w.writerows(new)
            return np.array([cache[p] for p in pts], float)
        t._sampler = web
        return t
