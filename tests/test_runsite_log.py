from runsite.log import parse_log
SK = {"climate", "programme", "narrative", "massing", "site-section", "analysis", "plans", "isometric"}

def test_log_new_form():
    t = ("21:51 start climate, programme, analysis\n"
         "21:51 programme done: 2,800 homes\n"
         "21:54 climate done (project level, remade)\n"
         "22:34 start streets, phasing, analysis second\n"
         "22:41 analysis second run done: design against today\n")
    r = parse_log(t, SK)
    assert r["start"] == "21:51"
    a = [b for b in r["bars"] if b["skill"] == "analysis"]
    assert [(b["kind"], b["t0"], b["t1"]) for b in a] == [("second", 43, 50)]
    assert {(b["skill"], b["t1"]) for b in r["bars"]} >= {("programme", 0), ("climate", 3)}

def test_log_old_forms():
    t = ("- 12:38 round 1 started: narrative, site-section, massing\n"
         "- 12:41 narrative (first run) done: narrative.md written.\n"
         "- Round 1 started 12:42: plans, isometric (first run)\n"
         "- 12:51 massing done: 228 new buildings\n")
    r = parse_log(t, SK)
    assert ("narrative", "first", 0, 3) in {(b["skill"], b["kind"], b["t0"], b["t1"]) for b in r["bars"]}
    assert ("massing", "first", 0, 13) in {(b["skill"], b["kind"], b["t0"], b["t1"]) for b in r["bars"]}

def test_log_reruns_and_checks():
    t = ("22:00 start plans\n22:10 plans done: 4 plans\n"
         "22:47 frames.py: 7 of 23 drawings miss their frame\n"
         "22:47 start reruns: plans, isometric\n"
         "22:51 plans rerun done: all 4 fit\n")
    r = parse_log(t, SK)
    assert ("plans", "rerun", 47, 51) in {(b["skill"], b["kind"], b["t0"], b["t1"]) for b in r["bars"]}
    assert r["events"][0]["kind"] == "check" and r["events"][0]["t"] == 47

def test_log_crosses_midnight():
    r = parse_log("23:29 start climate\n00:36 climate done\n", SK)
    assert r["bars"][0]["t1"] == 67 and r["end"] == "00:36"

def test_log_done_without_start_and_junk():
    r = parse_log("# Log\n\nsome prose 12 of 13\n10:00 start climate\n10:05 massing done: x\n", SK)
    m = [b for b in r["bars"] if b["skill"] == "massing"][0]
    assert m["t0"] == 0 and m["t1"] == 5
