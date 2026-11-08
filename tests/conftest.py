import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugins/studio/skills/competition-proposal/scripts"))


import json
import shutil

import pytest

FIXTURES = REPO / "tests" / "fixtures"


def make_png(path, size=(594, 841)):
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path)


@pytest.fixture
def fixture_proposals(tmp_path):
    dest = tmp_path / "proposals"
    shutil.copytree(FIXTURES / "runsite", dest)
    make_png(dest / "2026-01-02_run-1" / "panel-layout" / "panel-1.png")
    return dest


@pytest.fixture
def fixture_project(tmp_path, fixture_proposals):
    project = tmp_path / "project"
    (project / "site").mkdir(parents=True)
    (project / "climate").mkdir()
    ring = [[[12.0, 49.0], [12.01, 49.0], [12.01, 49.01], [12.0, 49.0]]]
    feature = {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": ring}}
    collection = json.dumps({"type": "FeatureCollection", "features": [feature]})
    (project / "site" / "site.geojson").write_text(collection)
    (project / "climate" / "noise.geojson").write_text(collection)
    shutil.move(str(fixture_proposals), str(project / "proposals"))
    return project
