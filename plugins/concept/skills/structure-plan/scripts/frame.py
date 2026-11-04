"""The frame a structure plan is designed in: the site in local metres, its layers, and a feature writer that checks
every feature before it is written.

    from frame import Frame
    F = Frame(site_dir, climate_dir)        # climate_dir is optional
    F.add('neighbourhood', 'Field', F.lu('farmland'), 'new', 'mapped', 'plots.geojson')
    warnings = F.write('<proposal>/structure-plan/structure-plan.geojson')

Coordinates are metres from the south-west corner of the site's bounds, in the UTM zone of the site's centroid, so a
designer's numbers stay small. The file is written in WGS84, longitude first.
"""
import json
from pathlib import Path

import pyproj
from shapely.geometry import shape, mapping, box as _box, Point, LineString, MultiLineString
from shapely.ops import transform, unary_union, linemerge
from shapely.validation import make_valid

DEFAULTS = {
    'simplify_m': 0.5,          # features are simplified by this much, so the file stays small
    'min_area_m2': 1.0,         # polygon pieces smaller than this are slivers and dropped
    'min_length_m': 1.0,        # line pieces shorter than this are dropped
}

KINDS = ('neighbourhood', 'centre', 'green', 'route', 'gateway')
POLYGON_KINDS = ('neighbourhood', 'centre', 'green')
ACTIONS = ('keep', 'change', 'new')
BASES = ('documented', 'brief', 'mapped', 'hypothesis')
LEVELS = {'centre': ('main', 'local'), 'route': ('main', 'local', 'landscape')}


def utm_epsg(lon, lat):
    """The UTM zone of a point, as an EPSG code."""
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


def parts(g):
    """The single geometries of a geometry, empty ones left out."""
    if g is None or g.is_empty:
        return []
    return [p for p in (g.geoms if hasattr(g, 'geoms') else [g]) if not p.is_empty]


def read_fc(path):
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8')).get('features') or []


class Frame:
    def __init__(self, site_dir, climate_dir=None):
        self.site_dir = Path(site_dir)
        self.features, self.warnings, self.missing = [], [], []
        site_f = read_fc(self.site_dir / 'site.geojson')
        if not site_f:
            raise SystemExit(f'no site.geojson in {self.site_dir}: ask for the site first')
        site_ll = unary_union([shape(f['geometry']) for f in site_f if f.get('geometry')])
        c = site_ll.centroid
        self.epsg = utm_epsg(c.x, c.y)
        fw = pyproj.Transformer.from_crs(4326, self.epsg, always_xy=True).transform
        bw = pyproj.Transformer.from_crs(self.epsg, 4326, always_xy=True).transform
        self.x0, self.y0 = transform(fw, site_ll).bounds[:2]
        x0, y0 = self.x0, self.y0
        self._to_local = lambda g: transform(lambda x, y, z=None: (x - x0, y - y0), transform(fw, g))
        self._to_wgs = lambda g: transform(bw, transform(lambda x, y, z=None: (x + x0, y + y0), g))
        self.site = self.local(site_ll)
        self.plots = self._layer('plots')
        self.streets = self._layer('streets')
        self.buildings = self._layer('buildings')
        self.rail = unary_union([g for p, g in self._layer('rail')])
        self.water = unary_union([g for p, g in self._layer('water')])
        self.noise = {}
        rules = read_fc(Path(climate_dir) / 'rules.geojson') if climate_dir else None
        if climate_dir and rules is None:
            self.missing.append('rules.geojson in the climate folder')
        for f in rules or []:
            p = f.get('properties') or {}
            if p.get('topic') == 'noise' and f.get('geometry'):
                g = self.local(shape(f['geometry']))
                k = p.get('kind', '?')
                self.noise[k] = unary_union([self.noise[k], g]) if k in self.noise else g

    # ------------------------------------------------------------ coordinates
    def local(self, geom):
        """A WGS84 geometry in local metres, repaired."""
        g = self._to_local(geom)
        return g if g.is_valid else make_valid(g)

    def to_local(self, lon, lat):
        """A WGS84 point as (x, y) in local metres."""
        p = self._to_local(Point(lon, lat))
        return p.x, p.y

    def to_wgs(self, geom):
        """A geometry in local metres, in WGS84."""
        return self._to_wgs(geom)

    def _layer(self, name):
        F = read_fc(self.site_dir / f'{name}.geojson')
        if F is None:
            self.missing.append(f'{name}.geojson in the site folder')
            return []
        out = []
        for f in F:
            if f.get('geometry'):
                g = self.local(shape(f['geometry']))
                if not g.is_empty:
                    out.append((f.get('properties') or {}, g))
        return out

    # ------------------------------------------------------------ helpers
    def lu(self, *landuse):
        """The site's land of these land uses (as in plots.geojson; 'park' also finds 'leisure:park')."""
        def hit(v):
            return isinstance(v, str) and (v in landuse or v.split(':')[-1] in landuse)
        return unary_union([g for p, g in self.plots if hit(p.get('landuse'))]).intersection(self.site)

    def street(self, name_prefix='', highway=None):
        """The street lines whose name starts with name_prefix, of these highway classes if given."""
        if isinstance(highway, str):
            highway = [highway]
        return unary_union([g for p, g in self.streets
                            if (p.get('name') or '').startswith(name_prefix) and (highway is None or p.get('highway') in highway)])

    def strip(self, coords, width):
        """A band of this width along a line through the points, cut to the site."""
        return LineString(coords).buffer(width / 2, cap_style=2, join_style=2).intersection(self.site)

    def box(self, x0, y0, x1, y1):
        return _box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def point(self, x, y):
        return Point(x, y)

    def line(self, coords):
        return LineString(coords)

    # ------------------------------------------------------------ features
    def programme(self, homes, commerce_m2=0, m2_per_home=95, storeys=6, coverage=0.22, source=None):
        """What the plan must hold, for the checks: homes per phase as {phase: homes}, the commerce floor area, the
        floor area of a home, the storey cap and the share of a neighbourhood its buildings cover (own assumption 0.22:
        about what the massing skill's blocks cover once its streets, squares and courtyards are taken). A neighbourhood's own storeys or coverage
        overrides these."""
        self.asked = {'homes': {str(k): v for k, v in dict(homes).items()}, 'commerce_m2': commerce_m2,
                      'm2_per_home': m2_per_home, 'storeys': storeys, 'coverage': coverage, 'source': source}

    def add(self, kind, name, geom, action, basis, source=None, **props):
        """One feature of the plan. Stops with what is wrong on a bad value or an empty geometry."""
        if kind not in KINDS:
            raise SystemExit(f"{kind} {name}: kind '{kind}' is not one of {', '.join(KINDS)}")
        if not isinstance(name, str) or not name.strip():
            raise SystemExit(f'{kind} {name!r}: a feature needs a name')
        who = f'{kind} {name}'
        if action not in ACTIONS:
            raise SystemExit(f"{who}: action '{action}' is not one of {', '.join(ACTIONS)}")
        if basis not in BASES:
            raise SystemExit(f"{who}: basis '{basis}' is not one of {', '.join(BASES)}")
        if kind in LEVELS and props.get('level') not in LEVELS[kind]:
            raise SystemExit(f"{who}: level '{props.get('level')}' is not one of {', '.join(LEVELS[kind])}")
        if kind == 'green' and not (isinstance(props.get('roles'), (list, tuple)) and props['roles']):
            raise SystemExit(f'{who}: a green needs roles as a list, e.g. roles=["ecology", "water"]')
        if kind == 'centre' and not props.get('holds'):
            self.warnings.append(f'centre {name} says nothing it holds; the massing can build nothing there')
        g = self._clean(kind, who, geom)
        p = {'kind': kind, 'name': name, 'action': action, 'basis': basis}
        if source:
            p['source'] = source
        p.update({k: (list(v) if isinstance(v, tuple) else v) for k, v in props.items()})
        if kind in POLYGON_KINDS:
            p['area_ha'] = round(g.area / 1e4, 2)
        elif kind == 'route':
            p['length_m'] = round(g.length)
        self.features.append((p, g))
        return g

    def _clean(self, kind, who, geom):
        if geom is None or geom.is_empty:
            raise SystemExit(f'{who}: the geometry is empty')
        g = geom if geom.is_valid else make_valid(geom)
        if kind in POLYGON_KINDS:
            polys = [q for p in parts(g) if p.geom_type in ('Polygon', 'MultiPolygon') for q in parts(p)]
            polys = [q for q in polys if q.area >= DEFAULTS['min_area_m2']]
            if not polys:
                raise SystemExit(f'{who}: a {kind} is a polygon, and nothing of it is left ({geom.geom_type})')
            g = unary_union(polys).simplify(DEFAULTS['simplify_m'], preserve_topology=True)
            g = g if g.is_valid else make_valid(g)
            g = unary_union([q for q in parts(g) if q.geom_type == 'Polygon'])
        elif kind == 'route':
            lines = [q for p in parts(g) if 'LineString' in p.geom_type for q in parts(p)]
            lines = [q for q in lines if q.length >= DEFAULTS['min_length_m']]
            if not lines:
                raise SystemExit(f'{who}: a route is a line, and nothing of it is left ({geom.geom_type})')
            g = linemerge(MultiLineString(lines)) if len(lines) > 1 else lines[0]
            g = g.simplify(DEFAULTS['simplify_m'])
        elif g.geom_type != 'Point':
            raise SystemExit(f'{who}: a gateway is one point, not a {g.geom_type}')
        if g.is_empty:
            raise SystemExit(f'{who}: the geometry is empty after cleaning')
        return g

    def write(self, path):
        """The plan as GeoJSON in WGS84. Returns the warnings."""
        if not any(p['kind'] == 'centre' and p.get('level') == 'main' for p, g in self.features):
            raise SystemExit('no main centre: give one centre level="main"')
        if not any(p['kind'] == 'neighbourhood' and p['action'] in ('new', 'change') for p, g in self.features):
            raise SystemExit('no neighbourhood with action new or change: the massing would have nothing to build on')
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        feats = [{'type': 'Feature', 'properties': p, 'geometry': mapping(self.to_wgs(g))} for p, g in self.features]
        fc = {'type': 'FeatureCollection', 'crs_note': 'WGS84, longitude first', 'features': feats}
        if getattr(self, 'asked', None):
            fc['programme'] = self.asked
        else:
            self.warnings.append('no F.programme(...): the homes, commerce and floor area cannot be checked')
        path.write_text(json.dumps(fc, ensure_ascii=False), encoding='utf-8')
        return list(self.warnings) + [f'missing: {m}' for m in self.missing]
