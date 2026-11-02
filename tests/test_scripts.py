"""The scripts the lean run moved into skill folders: they reproduce run-3 and name no site."""
import json, re, shutil, subprocess, sys
from pathlib import Path
import pytest
from conftest import REPO

RUN3 = REPO / "competition/proposals/2026-11-02_run-3"
SITE = REPO / "competition/site"
FIX = Path(__file__).parent / "fixtures"
MASSING = REPO / "plugins/design/skills/massing/scripts"
NEW_SCRIPTS = [MASSING / "massing.py", MASSING / "draw.py"]
FORBIDDEN = re.compile(r"Regensburg|Europan|Pilsenallee|Chamer|Brandlberg|Haslbach|Wutzlhofen|run-3|25832"
                       r"|\b49\.0\d{3}|\b12\.\d{4}|\b[A-Z]:[\\/](?:Users|Work)", re.I)
needs_run3 = pytest.mark.skipif(not RUN3.exists(), reason="run-3 not on this computer")


def copy_run3(dest, skills):
    dest.mkdir(parents=True)
    for s in skills:
        shutil.copytree(RUN3 / s, dest / s)
    return dest


def run(script, *args, check=True):
    r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode:
        raise AssertionError(r.stderr[-2000:])
    return r


def buildings(path):
    F = json.loads(Path(path).read_text(encoding="utf-8"))["features"]
    return [f["properties"] for f in F if f["properties"].get("kind") == "building" and not f["properties"].get("existing")]


def test_no_site_in_new_scripts():
    for p in NEW_SCRIPTS:
        hits = FORBIDDEN.findall(p.read_text(encoding="utf-8"))
        assert not hits, (p.name, hits)


def massing_run(tmp_path, drop=None):
    out = copy_run3(tmp_path / "with space" / "2026-01-01_t", ["structure-plan", "climate", "programme", "narrative"])
    (out / "massing").mkdir()
    cfg = json.loads((FIX / "massing_config_run3.json").read_text(encoding="utf-8"))
    cfg.pop(drop, None)
    (out / "massing/config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return out


@needs_run3
def test_massing_reproduces_run3(tmp_path):
    out = massing_run(tmp_path)
    run(MASSING / "massing.py", "--proposal", out, "--site", SITE, "--config", out / "massing/config.json")
    run(MASSING / "draw.py", "--proposal", out, "--site", SITE)
    new, old = buildings(out / "massing/massing.geojson"), buildings(RUN3 / "massing/massing.geojson")
    assert len(new) == len(old)
    gfa = lambda b: sum(x.get("gfa_m2") or 0 for x in b)
    assert abs(gfa(new) - gfa(old)) / gfa(old) < 0.01
    for f in ["areas.csv", "assumptions.md", "massing.svg", "massing.png", "massing_3d.svg", "massing_3d.png"]:
        assert (out / "massing" / f).exists(), f


@needs_run3
def test_massing_missing_key_stops(tmp_path):
    out = massing_run(tmp_path, drop="homes_target")
    r = run(MASSING / "massing.py", "--proposal", out, "--site", SITE, "--config", out / "massing/config.json", check=False)
    assert r.returncode != 0 and "homes_target" in r.stderr
