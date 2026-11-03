"""Helpers shared by measure.py, draw.py and compare.py."""
import json, os, sys, subprocess
from shapely.geometry import shape
from shapely.ops import transform
import pyproj


def utm_epsg(lon, lat):
    """The UTM zone of a point, as an EPSG code."""
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


def read_config(path, required=()):
    """config.json: {key: {"value": ..., "source": ...}}. A null value or a source still in <brackets> is not filled in."""
    if not os.path.exists(path):
        sys.exit(f'no config at {path}: copy scripts/config.example.json there and fill it from the checklist')
    raw = json.load(open(path, encoding='utf8'))
    raw = {k: v for k, v in raw.items() if not k.startswith('_') and not (isinstance(v, dict) and (
        v.get('value') is None or str(v.get('source', '')).startswith('<')))}
    missing = [k for k in required if k not in raw]
    if missing:
        sys.exit('missing in config.json: ' + ', '.join(missing) + ' (from the brief with its page, or an assumption)')
    values = {k: (v['value'] if isinstance(v, dict) and 'value' in v else v) for k, v in raw.items()}
    sources = {k: (v.get('source', '') if isinstance(v, dict) else '') for k, v in raw.items()}
    return values, sources


def load(path):
    if not os.path.exists(path):
        return []
    return json.load(open(path, encoding='utf8'))['features']


def projector(site_dir, epsg=None):
    """Transformers WGS84 -> metres and back, in the site's UTM zone unless config names one."""
    c = shape(load(os.path.join(site_dir, 'site.geojson'))[0]['geometry']).centroid
    crs = epsg or utm_epsg(c.x, c.y)
    fwd = pyproj.Transformer.from_crs(4326, crs, always_xy=True).transform
    back = pyproj.Transformer.from_crs(crs, 4326, always_xy=True).transform
    return (lambda g: transform(fwd, g)), (lambda g: transform(back, g))


def matches(props, where):
    """where: {property: [values]}; every property must match one of its values. None or {} matches all."""
    return all(str(props.get(k)) in [str(x) for x in (v if isinstance(v, list) else [v])] for k, v in (where or {}).items())


def credit(site_dir):
    src = os.path.join(site_dir, 'SOURCES.md')
    text = open(src, encoding='utf8').read() if os.path.exists(src) else ''
    return 'Map data © OpenStreetMap contributors (ODbL).' if 'OpenStreetMap' in text else ''


def shot(svg, png, w, h):
    """PNG of an SVG through a headless Chrome or Edge. Returns False if none is installed."""
    exes = [r'C:/Program Files/Google/Chrome/Application/chrome.exe',
            r'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
            r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
            r'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
            '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser']
    exe = next((e for e in exes if os.path.exists(e)), None)
    if not exe:
        return False
    html = svg[:-4] + '_wrap.html'
    open(html, 'w', encoding='utf8').write(
        f'<html><body style="margin:0"><img src="{os.path.basename(svg)}" style="width:{w}px;height:{h}px"></body></html>')
    subprocess.run([exe, '--headless', '--disable-gpu', '--hide-scrollbars', f'--screenshot={os.path.abspath(png)}',
                    f'--window-size={w},{h}', 'file:///' + os.path.abspath(html).replace('\\', '/')],
                   capture_output=True, timeout=180)
    os.remove(html)
    return os.path.exists(png)
