"""Reading one run folder into the record the runs site shows."""
import json

from runsite.run import card, discover_runs, read_run

SK = {"plans", "panel-layout", "jury"}
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8ffff3f0005fe02fea7d6a5ea0000000049454e44ae426082")


def test_read_run_full(fixture_proposals):
    r = read_run(fixture_proposals / "2026-01-02_run-1", SK, {}, [])
    assert r["label"] == "run-1" and r["verdict"] == "Special Mention"
    assert r["items"] == [12, 12]
    assert r["usd"] == 3.5 and r["usd_by_model"] == {"opus": 2.0, "sonnet": 1.5}
    assert r["skills"]["plans"]["red"] is True
    assert r["skills"]["plans"]["unsure"].startswith("Stray accent lines")
    it = r["panels"][0]["items"][0]
    assert (it["skill"], round(it["x"], 4), round(it["w"], 4)) == ("plans", round(15/594, 4), round(564/594, 4))
    assert r["headline"]["homes"] == 3237


def test_read_run_details(fixture_proposals):
    r = read_run(fixture_proposals / "2026-01-02_run-1", SK, {}, [])
    assert (r["key"], r["title"], r["date"], r["kind"]) == ("2026-01-02_run-1", "Lantern Yard", "2026-01-02", "run")
    assert (r["start"], r["end"], r["minutes"]) == ("10:00", "10:25", 25)
    assert r["commit"] == "abc1234" and r["new_in_run"] == "the plans skill"
    assert r["usd_lead"] == 2.0 and r["has"] == {"geo": False, "panels": True, "layout": True, "loop": False}
    p = r["skills"]["plans"]
    assert p["model"] == "sonnet" and p["usd"] == 1.5 and p["fixes"] == ["draw every tree"]
    assert p["issues"] == [{"severity": "medium", "issue": "input missing", "fix": "redraw the site plan"}]
    assert p["runs"][0]["kind"] == "first" and p["runs"][0]["t1"] == 8
    assert r["skills"]["panel-layout"]["red"] is False
    assert r["skills"]["jury"]["runs"][0]["t1"] == 25    # in the table, not in the log: a bar ending at the end
    assert r["headline"] == {"homes": 3237, "gfa_m2": 564515, "new_buildings": 253, "green_ha": 32.98}
    assert r["open_problems_md"] == "- The yard has no ground floor."
    assert r["handed_on_md"] == "Nothing else."
    assert r["events"] and r["n_skills"] == len(r["skills"])
    panel = r["panels"][0]
    assert (panel["n"], panel["img"], panel["w_px"], panel["h_px"]) == (1, "img/2026-01-02_run-1/panel-1.jpg", 594, 841)
    assert [i["id"] for i in panel["items"]] == ["site-plan", "other"]      # the text item has no file
    sp, other = panel["items"]
    assert sp["img"] == "img/2026-01-02_run-1/site-plan.jpg" and sp["scale"] == "1:3000"
    assert sp["caption"] == "Site plan" and sp["shows"] == "the site"
    assert round(sp["h"], 4) == round(540/841, 4)
    assert sp["flagged"] == "site-plan_1-3000 fills 40 % of 564 x 540 mm"
    assert other["skill"] == "isometric" and other["flagged"] == "other-drawing 100 x 100 mm"
    assert card(r)["items"] == [12, 12] and "skills" not in card(r)


def test_read_run_minimal(tmp_path):
    f = tmp_path / "2026-01-03_run-2"; (f / "panel-layout").mkdir(parents=True)
    (f / "panel-layout" / "panel-1.png").write_bytes(PNG_1PX)
    r = read_run(f, SK, {}, [])
    assert r["panels"][0]["items"] == [] and r["skills"] == {} and r["usd"] is None and r["verdict"] is None


def test_discover_skips_drafts_and_hidden(fixture_proposals):
    keys = [p.name for p in discover_runs(fixture_proposals, {})]
    assert keys == ["2026-01-02_run-1"]
    assert discover_runs(fixture_proposals, {"2026-01-02_run-1": {"hide": True}}) == []


def test_overrides_win(fixture_proposals):
    r = read_run(fixture_proposals / "2026-01-02_run-1", SK, {"2026-01-02_run-1": {"verdict": "Prize", "kind": "variant"}}, [])
    assert r["verdict"] == "Prize" and r["kind"] == "variant"


def test_jury_links_from_overrides(fixture_proposals):
    ov = {"2026-01-02_run-1": {"jury_links": {"plans": ["a"]}}}
    assert read_run(fixture_proposals / "2026-01-02_run-1", SK, ov, [])["jury"]["links"] == {"plans": ["a"]}


def test_scrub_applied(fixture_proposals):
    r = read_run(fixture_proposals / "2026-01-02_run-1", SK, {}, ["Lantern"])
    assert "Lantern" not in json.dumps(r)
