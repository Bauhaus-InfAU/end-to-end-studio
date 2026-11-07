# An example structure plan that works on any site. Copy it to <proposal>/structure-plan/design.py, replace each
# decision by the design's own, and run it with build.py. It holds only decisions: no imports, no files.
# F is the frame: F.site is the site in metres from its south-west corner; F.lu, F.street and F.strip give land uses,
# streets and strips; F.box, F.point and F.line make shapes in the same metres.

# What the plan must hold, from programme/ or the brief: homes per phase, commerce floor area, the storey cap.
F.programme({1: 400}, commerce_m2=8000, m2_per_home=95, storeys=6, source='assumption: no programme given')

# The land to build on: the largest piece of farmland in the site, else the whole site.
farm = F.lu('farmland', 'meadow', 'grass')
pieces = list(farm.geoms) if hasattr(farm, 'geoms') else [farm]
land = max(pieces, key=lambda g: g.area) if not farm.is_empty else F.site
x0, y0, x1, y1 = land.bounds
cx = land.representative_point().x

# A green strip runs north to south through it and stays free of building.
strip = F.strip([(cx, y0 - 10), (cx, y1 + 10)], 40).intersection(land)
F.add('green', 'Middle strip', strip, 'new', 'hypothesis',
      'assumption: a strip through the new land carries cool air and rain', roles=['climate', 'water', 'recreation'])

# The neighbourhood is the land around the strip.
field = land.difference(strip.buffer(1))
F.add('neighbourhood', 'Field', field, 'new', 'mapped', 'plots.geojson: farmland',
      phase=1, homes=round(field.area / 1e4 * 60), density='60 homes per ha (assumption)', commerce_m2=8000)

# The main centre stands where the main street meets the new land.
main = F.street('', ['trunk', 'primary', 'secondary', 'tertiary'])
if main.is_empty:
    main = F.street('')
if main.is_empty:
    main = F.site.boundary
meet = nearest_points(land, main)[0]
centre = F.box(meet.x - 30, meet.y - 30, meet.x + 30, meet.y + 30).intersection(land.buffer(30))
F.add('centre', 'Arrival square', centre, 'new', 'hypothesis', 'assumption: the new land is reached from the main street',
      level='main', holds='the stop, shops, a daycare')

# A landscape path follows the strip; a gateway opens where the main street reaches the centre.
F.add('route', 'Strip path', F.line([(cx, y0), (cx, y1)]).intersection(F.site), 'new', 'hypothesis',
      'assumption: the strip carries the path', level='landscape')
F.add('gateway', 'Main street gate', nearest_points(main, meet)[0], 'new', 'mapped', 'streets.geojson')
