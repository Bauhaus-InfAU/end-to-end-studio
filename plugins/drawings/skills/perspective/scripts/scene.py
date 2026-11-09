"""Loads a proposal's massing and the project's site data into one metric scene.

Decides each building's status and height, and collects what the views draw, every
assumption in ASSUMED, and every problem in Scene.warnings. Nothing is dropped silently.
"""
import csv
import json
import re
import statistics
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely import STRtree, make_valid, transform as shp_transform
from shapely.geometry import shape
from shapely.ops import unary_union

# Every assumed number the views depend on. Override any of them with --options.
ASSUMED = {
    # height in m of land cover that stands up; the site data gives its place, not its height
    "tall_cover": {"forest": 22, "wood": 22, "natural:wood": 22, "scrub": 4, "natural:scrub": 4},
    # land cover drawn as ground
    "flat_cover": {"meadow": "green", "grass": "green", "leisure:park": "green", "park": "green", "allotments": "green",
                   "leisure:playground": "green", "leisure:pitch": "green", "farmland": "field", "natural:water": "water"},
    # land uses with no cover of their own
    "bare_cover": ["residential", "industrial", "commercial", "retail", "railway", "construction", "brownfield", "landfill",
                   "quarry", "farmyard", "leisure:sports_centre"],
    # street width in m by road class, where no width or lanes are given
    "street_width": {"trunk": 14, "trunk_link": 7, "primary": 10, "secondary": 9, "tertiary": 8, "residential": 7, "living_street": 6,
                     "unclassified": 6, "service": 4, "track": 3, "cycleway": 2.5, "footway": 2, "path": 2, "pedestrian": 4, "steps": 2},
    "street_width_default": 5,
    "lane_width": 3.25,
    "rail_width": 4,
    "new_street_width": 12,
    "shared_street_width": 7,   # m of the public tone along mobility's access-only routes, as the plans draw them
    "tree_height": 12,
    "tree_crown_radius": 3.5,
}
GONE = {"demolished", "removed", "replaced", "to-demolish", "to_demolish"}
DUPLICATE, REPLACED = 0.5, 0.2   # shares of the smaller footprint that overlap


def merge(base, extra):
    out = dict(base)
    for k, v in extra.items():
        out[k] = {**out[k], **v} if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


def find_site(proposal):
    """The project's site folder: next to proposals/, then named in a CLAUDE.md, then site/ further up."""
    proposal = Path(proposal).resolve()
    for up in proposal.parents:
        if (up / "site" / "site.geojson").exists():
            return up / "site"
        claude = up / "CLAUDE.md"
        if claude.exists():
            for m in re.findall(r"`([^`\s]*site/?)`", claude.read_text(encoding="utf-8", errors="replace")):
                if (up / m / "site.geojson").exists():
                    return (up / m).resolve()
    return None


def flag(value):
    """existing as a yes or no; None when the data doesn't say."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in ("true", "yes", "1", "existing", "kept"):
        return True
    if isinstance(value, str) and value.strip().lower() in ("false", "no", "0", "new"):
        return False
    return None


def is_gone(p):
    return str(p.get("status", "")).strip().lower() in GONE or flag(p.get("demolished")) is True


def number(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0 and v == v else None


class Terrain:
    """Heights from a grid CSV with columns lon, lat, ele."""

    def __init__(self, path, to_lonlat):
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        self.path, self.to_lonlat = Path(path), to_lonlat
        self.source = rows[0].get("source", "") if rows else ""
        self.lons = sorted({float(r["lon"]) for r in rows})
        self.lats = sorted({float(r["lat"]) for r in rows})
        grid = np.full((len(self.lats), len(self.lons)), np.nan)
        ix, iy = {v: i for i, v in enumerate(self.lons)}, {v: i for i, v in enumerate(self.lats)}
        for r in rows:
            if r["ele"] not in ("", "None"):
                grid[iy[float(r["lat"])], ix[float(r["lon"])]] = float(r["ele"])
        self.gaps = int(np.isnan(grid).sum())
        self.grid = np.where(np.isnan(grid), np.nanmean(grid), grid)
        self.lons, self.lats = np.array(self.lons), np.array(self.lats)

    def __call__(self, xs, ys):
        lon, lat = self.to_lonlat.transform(np.asarray(xs, float), np.asarray(ys, float))
        fx = np.clip((lon - self.lons[0]) / (self.lons[-1] - self.lons[0]) * (len(self.lons) - 1), 0, len(self.lons) - 1.001)
        fy = np.clip((lat - self.lats[0]) / (self.lats[-1] - self.lats[0]) * (len(self.lats) - 1), 0, len(self.lats) - 1.001)
        i, j = fx.astype(int), fy.astype(int)
        s, t = fx - i, fy - j
        g = self.grid
        return g[j, i] * (1 - s) * (1 - t) + g[j, i + 1] * s * (1 - t) + g[j + 1, i] * (1 - s) * t + g[j + 1, i + 1] * s * t


class Scene:
    def __init__(self, proposal, site=None, options=None, floor_height=None):
        self.proposal = Path(proposal).resolve()
        self.assumed = merge(ASSUMED, options or {})
        self.warnings, self.used, self.absent, self.status_rows = [], [], [], []
        self.buildings, self.flats, self.tall, self.trees = [], [], [], []
        self.terrain = None
        self.floor_height, self.floor_height_source = number(floor_height), "given with --floor-height" if number(floor_height) else None

        massing_path = self.proposal / "massing" / "massing.geojson"
        if not massing_path.exists():
            raise SystemExit(f"No massing at {massing_path}. Nothing to draw: the views need the massing skill's output.")
        collection = json.loads(massing_path.read_text(encoding="utf-8"))
        self.massing = collection.get("features") or []
        if not self.massing:
            raise SystemExit(f"{massing_path} has no features. Nothing to draw.")
        self.used.append("massing/massing.geojson")

        self.is_test = bool(collection.get("standin")) or self.proposal.name == "test"

        self.site_dir = Path(site).resolve() if site else find_site(self.proposal)
        site_features = [f for f in self.read("site.geojson") if f.get("geometry")] if self.site_dir else []
        if not self.site_dir:
            self.warn("No site folder found: the views show the massing alone. Pass it with --site.")
        elif not site_features:
            self.warn("site.geojson gave no site polygon: the massing's outline is used as the site.")
        anchor = shape(site_features[0]["geometry"]) if site_features else unary_union(
            [shape(f["geometry"]) for f in self.massing if f.get("geometry")])
        lon, lat = anchor.centroid.x, anchor.centroid.y
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise SystemExit("The coordinates aren't longitude and latitude in WGS84: the massing has to be GeoJSON in WGS84.")
        crs = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84"
        self.to_local = Transformer.from_crs(4326, crs, always_xy=True)
        self.to_lonlat = Transformer.from_crs(crs, 4326, always_xy=True)
        self.site = self.local(anchor)
        self._narrow()
        self._floor_height()
        self._buildings()
        self._design_ground()
        self._context()
        self.public = unary_union([(g if g.is_valid else g.buffer(0)) for g, _ in self.public_parts]) if self.public_parts else None

    def warn(self, text):
        if text not in self.warnings:
            self.warnings.append(text)

    def local(self, g):
        return shp_transform(g, lambda c: np.column_stack(self.to_local.transform(c[:, 0], c[:, 1])))

    def read(self, name):
        p = self.site_dir / name
        if not p.exists():
            self.absent.append(name)
            return []
        data = json.loads(p.read_text(encoding="utf-8"))
        self.used.append(f"{p.parent.name}/{name}")
        if data.get("type") == "FeatureCollection":
            return data.get("features") or []
        self.warn(f"{name} is a {data.get('type')}, not a FeatureCollection: it was read as one feature; check it.")
        if data.get("type") == "Feature":
            return [data]
        return [{"geometry": data, "properties": {}}] if "coordinates" in data else []

    def geom(self, f, label):
        """A feature's valid metric geometry, else None with a warning."""
        raw = f.get("geometry")
        if not raw:
            self.warn(f"{label}: features with no geometry were left out.")
            return None
        try:
            g = shape(raw)
            if g.is_empty:
                raise ValueError
            g = make_valid(g)
            return self.local(g)
        except Exception:
            self.warn(f"{label}: features with unreadable geometry were left out.")
            return None

    def _narrow(self):
        kinds = {}
        for f in self.massing:
            k = (f.get("properties") or {}).get("kind")
            kinds.setdefault(k, []).append(f)
        self.by_kind = kinds
        if None in kinds:
            self.warn(f"{len(kinds[None])} massing features have no kind and were left out.")
        for k in set(kinds) - {"building", "street", "open-space", "tree", None}:
            self.warn(f"{len(kinds[k])} massing features of kind '{k}' are not drawn: the skill doesn't know this kind.")
        if not kinds.get("building"):
            raise SystemExit("The massing has no features of kind 'building'. Nothing to draw.")

    def _floor_height(self):
        """From the massing's own buildings, else its assumptions.md."""
        if self.floor_height:
            return
        ratios = [number(p.get("height_m")) / number(p.get("floors")) for p in (f["properties"] for f in self.by_kind["building"])
                  if number(p.get("height_m")) and number(p.get("floors"))]
        if ratios:
            self.floor_height = round(statistics.median(ratios), 2)
            self.floor_height_source = f"median of height_m / floors over {len(ratios)} massing buildings"
            return
        notes = self.proposal / "massing" / "assumptions.md"
        if notes.exists():
            m = re.search(r"(\d+(?:\.\d+)?)\s*m\b[^\n]{0,20}(?:a|per|each)\s+(?:floor|storey)", notes.read_text(encoding="utf-8", errors="replace"))
            if m:
                self.floor_height, self.floor_height_source = float(m.group(1)), "massing/assumptions.md"

    def height(self, p, fallback=None):
        """(height, its source); (None, reason) when nothing documented gives one."""
        for key in ("height_m", "height"):
            h = number(p.get(key))
            if h:
                return h, p.get("height_source") or key
        if fallback:
            return fallback, "the matching site building"
        floors = number(p.get("floors"))
        if floors and self.floor_height:
            return floors * self.floor_height, f"floors x {self.floor_height} m"
        return None, "no height, and no floors with a floor height" if not floors else "floors, but no documented floor height"

    def _buildings(self):
        site_features = self.read("buildings.geojson") if self.site_dir else []
        old = []
        for f in site_features:
            g = self.geom(f, "buildings.geojson")
            if g is not None and g.area > 0:
                old.append((g, f.get("properties") or {}))
        tree = STRtree([g for g, _ in old]) if old else None
        matched, removed, unknown, kept = {}, {}, 0, 0
        designed = []
        for f in self.by_kind["building"]:
            g, p = self.geom(f, "massing buildings"), f["properties"]
            if g is None or g.area <= 0:
                continue
            if g.distance(self.site) > 5000:
                self.warn("Massing buildings lie over 5 km from the site and were left out: check their coordinates.")
                continue
            hits = []
            if tree is not None:
                for i in tree.query(g):
                    share = g.intersection(old[i][0]).area / min(g.area, old[i][0].area)
                    hits.append((share, int(i)))
            state = flag(p.get("existing"))
            twins = [i for share, i in hits if share >= DUPLICATE]
            if is_gone(p):
                for i in twins:
                    removed[i] = "marked as gone in the massing"
                self.status_rows.append(["massing", p.get("id", ""), "demolished", "marked in the massing", "", "", "no"])
                continue
            if state is True:
                kept += 1
                for i in twins:
                    matched[i] = "the massing keeps it"
                group, status = "kept", "kept"
            elif state is False:
                group, status = "new", "new"
                for share, i in hits:
                    if share >= REPLACED:
                        removed[i] = "a new building stands on it"
            else:
                unknown += 1
                group, status = ("kept", "unknown") if twins else ("new", "unknown")
                for i in twins:
                    matched[i] = "the massing shows it, with no existing value"
            fallback = next((number(old[i][1].get("height")) for i in twins if number(old[i][1].get("height"))), None)
            h, source = self.height(p, fallback)
            row = ["massing", p.get("id", ""), status, "", h or "", source, "yes" if h else "no"]
            self.status_rows.append(row)
            if h:
                designed.append({"geom": g, "height": h, "floors": number(p.get("floors")), "group": group, "use": p.get("use")})
            else:
                row[3] = source
                self.warn("Massing buildings without a usable height were not drawn: see building_status.csv.")
        self.buildings = designed
        # A short list of kept buildings doesn't say the rest are gone; only a list that covers most of the site's buildings does.
        standing = sum(1 for i, (g, _) in enumerate(old) if self.site.contains(g.centroid) and i not in removed)
        marks_kept = kept > 0 and len(matched) >= 0.5 * standing
        counts ={"replaced": 0, "kept": 0, "removed": 0, "unclear": 0, "context": 0, "no height": 0}
        for i, (g, p) in enumerate(old):
            inside = self.site.contains(g.centroid)
            bid = p.get("id", "")
            if is_gone(p):
                removed[i] = "marked as gone in the site data"
            if i in removed:
                counts["replaced"] += 1
                self.status_rows.append(["site", bid, "replaced", removed[i], "", "", "no"])
                continue
            if i in matched:
                counts["kept"] += 1
                self.status_rows.append(["site", bid, "kept", matched[i] + "; drawn once, from the massing", "", "", "no"])
                continue
            if inside and marks_kept:
                counts["removed"] += 1
                self.status_rows.append(["site", bid, "assumed removed", "inside the site, not among the massing's kept buildings", "", "", "no"])
                continue
            h, source = self.height(p)
            if not h:
                counts["no height"] += 1
                self.status_rows.append(["site", bid, "context", source, "", "", "no"])
                self.warn("Site buildings without a usable height were not drawn: see building_status.csv.")
                continue
            if inside:
                counts["unclear"] += 1
            else:
                counts["context"] += 1
            self.status_rows.append(["site", bid, "unclear" if inside else "context",
                                     "inside the site; the massing doesn't say whether it stays" if inside else "", h, source, "yes"])
            self.buildings.append({"geom": g, "height": h, "floors": number(p.get("floors")), "group": "context", "use": p.get("use"),
                                   "default_height": p.get("height_source") == "default"})
        self.building_counts = counts
        if unknown:
            self.warn(f"{unknown} massing buildings have no existing value: treated as new unless they sit on a site building.")
        if counts["unclear"]:
            self.warn(f"{counts['unclear']} site buildings inside the site are drawn as standing: the massing doesn't list them as kept or removed, and they don't touch new buildings. A massing that marks none as kept, or only a few, can't say they're gone.")
        if counts["removed"]:
            self.warn(f"{counts['removed']} site buildings inside the site are assumed removed: the massing marks others as kept, but not these. No demolished status is defined, so this is inferred.")
        if counts["replaced"]:
            self.warn(f"{counts['replaced']} site buildings were replaced by the design and are not drawn.")
        if not self.floor_height:
            self.warn("No floor height is documented, so buildings with floors but no height can't be drawn.")

    def _street_surface(self):
        """The streets skill's polygons as (properties, metric geometry), or None without its file."""
        path = self.proposal / "streets" / "streets.geojson"
        if not path.exists():
            return None
        feats = json.loads(path.read_text(encoding="utf-8")).get("features") or []
        out = []
        for f in feats:
            p = f.get("properties") or {}
            if p.get("kind") in ("street", "path"):
                g = self.geom(f, "streets/streets.geojson")
                if g is not None and g.geom_type.endswith("Polygon"):
                    out.append((p, g))
        if not out:
            self.warn("streets/streets.geojson holds no street or path polygons: the streets are buffered from their lines instead.")
            return None
        self.used.append("streets/streets.geojson")
        return out

    def _design_ground(self):
        new_parts, self.public_parts, self.streets, self.open_spaces = [], [], [], []
        self.surface = self._street_surface()
        for p, g in self.surface or []:   # the streets skill's new streets come first, over the massing's lines
            if p.get("kind") != "street" or p.get("existing"):
                continue
            new_parts.append(g)
            self.flats.append((70, g, "street"))
            self.public_parts.append((g, "street"))
        for f in self.by_kind.get("street", []):
            g, p = self.geom(f, "massing streets"), f["properties"]
            if g is None:
                continue
            w = number(p.get("width"))
            if g.geom_type in ("LineString", "MultiLineString"):
                if not w:
                    w = self.assumed["new_street_width"]
                    self.warn(f"Massing streets without a width are drawn {w} m wide (assumed).")
                self.streets.append((g, w))
                area = g.buffer(w / 2, cap_style="flat")
            else:
                area = g
            if self.surface is not None:
                continue
            new_parts.append(area)
            self.flats.append((70, area, "street"))
            self.public_parts.append((area, "street"))
        tones = {"park": ("park", 40), "garden": ("garden", 41), "square": ("square", 75), "water": ("water", 50)}   # squares over streets, as on the plans
        for f in self.by_kind.get("open-space", []):
            g, p = self.geom(f, "massing open spaces"), f["properties"]
            if g is None:
                continue
            use = p.get("use")
            if use not in tones:
                self.warn(f"Open spaces of use '{use}' are drawn as park: the massing's uses are park, square, garden and water.")
            tone, order = tones.get(use, tones["park"])
            self.flats.append((order, g, tone))
            self.open_spaces.append((g, use))
            if use in ("park", "square"):
                self.public_parts.append((g, use))
        # the rest of the public ground the plans draw in the public tone: park thresholds and shared (access-only) streets
        for p, g in self.surface or []:
            if p.get("kind") == "path" and p.get("type") == "park threshold":
                self.flats.append((75, g, "square"))
        mob = self.proposal / "mobility" / "mobility.geojson"
        if mob.exists():
            shared = []
            for f in json.loads(mob.read_text(encoding="utf-8")).get("features") or []:
                p = f.get("properties") or {}
                if p.get("kind") == "route" and p.get("access_only"):
                    g = self.geom(f, "mobility/mobility.geojson")
                    if g is not None:
                        shared.append(g.buffer(self.assumed["shared_street_width"] / 2, cap_style="flat"))
            if shared:
                self.flats.append((75, unary_union(shared), "square"))
                self.used.append("mobility/mobility.geojson")
        osp = self.proposal / "open-space" / "open-space.geojson"   # the street trees are the massing's, the rest open-space's
        planted = [f for f in (json.loads(osp.read_text(encoding="utf-8")).get("features") or [] if osp.exists() else [])
                   if (f.get("properties") or {}).get("kind") == "tree"]
        if planted:
            self.used.append("open-space/open-space.geojson")
        for f in self.by_kind.get("tree", []) + planted:
            g, p = self.geom(f, "trees"), f["properties"]
            if g is None:
                continue
            if g.geom_type != "Point":
                self.warn("Trees that aren't single points were left out.")
                continue
            self.trees.append((g.x, g.y, number(p.get("height_m")) or self.assumed["tree_height"],   # x, y, height, crown radius
                               (number(p.get("crown_m")) or 2 * self.assumed["tree_crown_radius"]) / 2))
        built = [b["geom"].buffer(2) for b in self.buildings if b["group"] != "context"]
        self.design_cut = unary_union(built + new_parts) if built or new_parts else None
        self.new_built = unary_union([b["geom"] for b in self.buildings if b["group"] == "new"])

    def _cut(self, g):
        """What's left of existing ground cover and context where the design hasn't built."""
        return g.difference(self.design_cut) if self.design_cut is not None else g

    def _context(self):
        if not self.site_dir:
            return
        unknown = {}
        tall_map, flat_map = self.assumed["tall_cover"], self.assumed["flat_cover"]
        for f in self.read("plots.geojson"):
            value = (f.get("properties") or {}).get("landuse")
            if value in tall_map:
                g = self.geom(f, "plots.geojson")
                if g is None:
                    continue
                g = self._cut(g)
                if not g.is_empty:
                    self.tall.append((g, float(tall_map[value]), "forest" if tall_map[value] > 8 else "scrub"))
            elif value in flat_map:
                g = self.geom(f, "plots.geojson")
                if g is not None:
                    self.flats.append(({"field": 10, "green": 20, "water": 50}[flat_map[value]], self._cut(g), flat_map[value]))
            elif value not in self.assumed["bare_cover"]:
                unknown[value] = unknown.get(value, 0) + 1
        if unknown:
            self.warn("Land uses the skill has no rule for, drawn as bare ground: " + ", ".join(f"{k} ({v})" for k, v in sorted(unknown.items(), key=str)))
        for f in self.read("water.geojson"):
            g = self.geom(f, "water.geojson")
            if g is not None:
                self.flats.append((50, g.buffer(3) if g.geom_type.endswith("String") else g, "water"))
        lanes_used, assumed_w = 0, 0
        widths = self.assumed["street_width"]
        for p, g in self.surface or []:
            if p.get("kind") == "path" or p.get("existing"):
                area = self._cut(g)
                if not area.is_empty:
                    self.flats.append((65, area, "old_street"))
        for f in (self.read("streets.geojson") if self.surface is None else []):
            g, p = self.geom(f, "streets.geojson"), f.get("properties") or {}
            if g is None:
                continue
            lanes = number(p.get("lanes"))
            w = number(p.get("width")) or (lanes * self.assumed["lane_width"] if lanes else None)
            lanes_used += 1 if w else 0
            if not w:
                assumed_w += 1
                w = widths.get(p.get("highway"), self.assumed["street_width_default"])
            area = self._cut(g.buffer(w / 2, cap_style="flat"))
            if not area.is_empty:
                self.flats.append((65, area, "old_street"))
        if assumed_w:
            self.warn(f"{assumed_w} of {assumed_w + lanes_used} existing streets have an assumed width, by road class.")
        for f in self.read("rail.geojson"):
            g = self.geom(f, "rail.geojson")
            if g is not None:
                self.flats.append((66, self._cut(g.buffer(self.assumed["rail_width"] / 2, cap_style="flat")), "rail"))
        self.flats = [(o, (g if g.is_valid else g.buffer(0)), t) for o, g, t in self.flats]
        self.flats = [x for x in self.flats if not x[1].is_empty]
        self.flats.sort(key=lambda x: x[0])
        self.warn("The site data doesn't say what's on a bridge or in a tunnel, so every street and railway lies on the ground.")
        self.warn("The site data has no single existing trees: only areas of forest, scrub and green.")

    def ground(self, xs, ys):
        if self.terrain is None:
            return np.zeros(np.shape(xs))
        return self.terrain(xs, ys)

    def use_terrain(self, path):
        self.terrain = Terrain(path, self.to_lonlat)
        self.used.append(f"{path.parent.name}/{path.name}" + (f" ({self.terrain.source})" if self.terrain.source else ""))
        if self.terrain.gaps:
            self.warn(f"{self.terrain.gaps} terrain points have no height and take the average.")
