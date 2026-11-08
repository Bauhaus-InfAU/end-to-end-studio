"""The runs site's allow list and the filter that keeps the reference entries' names off it.

Only made-up names here, never the real references'.
"""
from pathlib import Path

from runsite.safety import forbidden_names, is_allowed, scrub


def _refs(tmp_path):
    w = tmp_path / "references" / "winners" / "3_special-mention_northern-lantern"
    w.mkdir(parents=True)
    (w / "board-1.jpg").write_bytes(b"x")
    return tmp_path / "references"


def test_scrub_variants(tmp_path):
    names = forbidden_names(_refs(tmp_path))
    s = scrub("the Northern Lantern plan; northern-lantern; NORTHERN_LANTERN; "
              "`3_special-mention_northern-lantern`; Lantern's blocks", names)
    assert "antern" not in s.lower()
    assert s.count("a reference") >= 5


def test_scrub_keeps_plain_text(tmp_path):
    names = forbidden_names(_refs(tmp_path))
    assert scrub("the winners' pictures show more people", names) == "the winners' pictures show more people"


def test_common_words_stay_unless_named(tmp_path):
    w = tmp_path / "references" / "winners" / "2_runner-up_green-city-puzzle"
    w.mkdir(parents=True)
    (w / "board-1.jpg").write_bytes(b"x")
    names = forbidden_names(tmp_path / "references")
    assert scrub("a green park in the city", names) == "a green park in the city"
    assert "a reference" in scrub("the Green City Puzzle boards", names)
    extra = tmp_path / "names.txt"
    extra.write_text("Puzzle\n", encoding="utf-8")
    assert scrub("the puzzle", forbidden_names(tmp_path / "references", extra)) == "the a reference"


def test_is_allowed():
    ok = ["README.md", "plans/summary.md", "plans/site-plan_1-3000.png", "massing/massing.geojson",
          "panel-layout/layout.json", "panel-layout/panel-2.png", "jury/report.md", "massing/stats.json"]
    bad = [".compare/plans.jpg", "references/winners/x/board-1.jpg", ".env", ".env.local",
           "plans/scripts/plans.py", "panel-layout/work/x.png", "winners/a.png", "notes.md"]
    assert all(is_allowed(Path(p)) for p in ok)
    assert not any(is_allowed(Path(p)) for p in bad)


def test_no_references_gives_no_names():
    assert forbidden_names(None) == []
