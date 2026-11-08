"""publish_site: merge with what is already published, refuse an unsafe build. Made-up names only."""
import json

from publish_site import check, merge, richness


def make_site(root, runs, references=True):
    """A built site with one run per key, `runs[key]` images under img/<key>/."""
    (root / "data/runs").mkdir(parents=True)
    (root / "data/geo").mkdir(parents=True)
    cards = []
    for key, n_img in runs.items():
        (root / "img" / key).mkdir(parents=True)
        for i in range(n_img):
            (root / "img" / key / f"d{i}.jpg").write_bytes(b"x")
        (root / "data/runs" / f"{key}.json").write_text(json.dumps({"key": key, "panels": []}), encoding="utf-8")
        cards.append({"key": key, "date": key, "label": key})
    (root / "data/index.json").write_text(json.dumps({"project": {"name": "p"}, "runs": cards, "ledger": []}),
                                          encoding="utf-8")
    (root / "build.json").write_text(json.dumps({"built": "2026-01-01T00:00", "references": references}),
                                     encoding="utf-8")
    return root


def test_richness_counts_images_geo_and_items(tmp_path):
    s = make_site(tmp_path / "s", {"r1": 3})
    assert richness(s, "r1") == 3
    (s / "data/geo/r1.json").write_text("{}", encoding="utf-8")
    (s / "data/runs/r1.json").write_text(json.dumps({"panels": [{"items": [1, 2]}]}), encoding="utf-8")
    assert richness(s, "r1") == 3 + 50 + 20


def test_merge_keeps_richer_published_run(tmp_path):
    local, pub = make_site(tmp_path / "l", {"r1": 2}), make_site(tmp_path / "p", {"r1": 9, "r0": 3})
    kept = merge(local, pub)
    assert sorted(kept) == ["r0", "r1"]
    assert len(list((local / "img/r1").iterdir())) == 9
    idx = json.loads((local / "data/index.json").read_text(encoding="utf-8"))
    assert [r["key"] for r in idx["runs"]] == ["r0", "r1"]


def test_merge_replaces_poorer_published_run(tmp_path):
    local, pub = make_site(tmp_path / "l", {"r1": 9}), make_site(tmp_path / "p", {"r1": 2})
    assert merge(local, pub) == []
    assert len(list((local / "img/r1").iterdir())) == 9


def test_merge_with_nothing_published(tmp_path):
    local = make_site(tmp_path / "l", {"r1": 1})
    assert merge(local, None) == [] and merge(local, tmp_path / "missing") == []


def test_check_refuses(tmp_path):
    s = make_site(tmp_path / "s", {"r1": 1}, references=False)
    assert check(s, [], False) and not check(s, [], True)
    (s / "data/runs/r1.json").write_text('{"t": "the Northern Lantern plan"}', encoding="utf-8")
    assert any("Northern Lantern" in p for p in check(s, ["Northern Lantern"], True))
    (s / ".compare").mkdir()
    (s / ".compare/x.jpg").write_bytes(b"x")
    assert any(".compare" in p for p in check(s, [], True))


def test_check_finds_names_in_keys_and_paths(tmp_path):
    s = make_site(tmp_path / "s", {"r1": 1})
    (s / "data/geo/r1.json").write_text('{"northern-lantern": {"x": {}}}', encoding="utf-8")
    (s / "img/r1/lantern-plan.jpg").write_bytes(b"x")
    problems = check(s, ["Northern Lantern", "Lantern"], False)
    assert any("r1.json" in p for p in problems) and any("lantern-plan.jpg" in p for p in problems)


def test_check_needs_build_json(tmp_path):
    s = make_site(tmp_path / "s", {"r1": 1})
    (s / "build.json").unlink()
    assert check(s, [], True)
