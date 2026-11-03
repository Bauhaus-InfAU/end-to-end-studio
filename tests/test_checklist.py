import re
import pytest
from conftest import REPO

CHECK = REPO / "competition/brief/checklist.md"
pytestmark = pytest.mark.skipif(not CHECK.exists(), reason="brief-reader has not run on this brief yet")
SECTIONS = ["## Numbers", "## Rules", "## Drawings and scales", "## Panels and format",
            "## Required content", "## What the jury looks for", "## Pages"]


def section(text, head):
    rest = text.split(head, 1)[1]
    return re.split(r"^## ", rest, maxsplit=1, flags=re.M)[0]


def test_checklist_has_sections_in_order():
    t = CHECK.read_text(encoding="utf-8")
    pos = [t.find(h) for h in SECTIONS]
    assert -1 not in pos and pos == sorted(pos)


def test_every_item_has_a_page():
    t = CHECK.read_text(encoding="utf-8")
    for line in re.findall(r"^(?:- |\d+\. ).+$", t, re.M):
        assert re.search(r"p\. ?\d+", line), line


def test_required_content():
    req = section(CHECK.read_text(encoding="utf-8"), "## Required content")
    assert len(re.findall(r"^\d+\. ", req, re.M)) >= 9          # p. 34 lists nine
    assert re.search(r"1:15[ ,.]?000", req) and re.search(r"1:3[ ,.]?000", req)


def test_checklist_numbers():
    t = CHECK.read_text(encoding="utf-8")
    assert re.search(r"2[ ,.]?800", t)       # homes, p. 30
    assert re.search(r"21 ?m", t)            # height, p. 28
    assert re.search(r"12 ?(m²|m2|square)", t)   # green per resident, p. 34
