"""Read one run folder (proposals/<date>_<label>/) into the record the runs site shows.

Trust, high to low: overrides (runs.json) > structured files > one regular expression on prose > None.
A thin old run gives empty values, never an error.
"""
import csv
import json
import re
from pathlib import Path

from .log import parse_log
from .safety import scrub

RUN_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}_.+")
HHMM = r"(\d{1,2}):(\d{2})"
OVERRIDABLE = ("title", "verdict", "kind", "usd", "minutes", "items", "commit", "new_in_run")
UNSURE = re.compile(r"(?:Unsure|Least sure|Uncertainty):?[ \t]*(.*?)(?:\n[ \t]*\n|\Z)", re.S)
CARD_KEYS = ("key", "label", "title", "date", "kind", "usd", "minutes", "verdict", "items", "n_skills", "has")


def _text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _json(path):
    try:
        return json.loads(_text(path))
    except ValueError:
        return {}


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _minutes(a, b):
    return (int(b[0]) * 60 + int(b[1]) - int(a[0]) * 60 - int(a[1])) % 1440


def _section(text, heading):
    m = re.search(r"^## " + re.escape(heading) + r"[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else None


def discover_runs(proposals, overrides):
    found = []
    for p in sorted(Path(proposals).iterdir()):
        if (p.is_dir() and RUN_NAME.match(p.name) and not overrides.get(p.name, {}).get("hide")
                and any((p / "panel-layout").glob("panel-*.png"))):
            found.append(p)
    return found


def _cost(folder, readme):
    rows = []
    for name in ("cost.csv", "usage.csv"):
        try:
            with open(folder / name, encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
        except OSError:
            continue
        break
    by_skill, by_model, models, total = {}, {"opus": 0.0, "sonnet": 0.0}, {}, None
    lead = None
    for row in rows:
        skill, usd = (row.get("skill") or "").strip(), _num(row.get("usd"))
        if skill == "total":
            total = usd
        elif usd is not None:
            model = (row.get("model") or "").strip()
            if skill == "lead":
                lead = usd
            else:
                by_skill[skill] = round(by_skill.get(skill, 0) + usd, 4)
                models.setdefault(skill, set()).add(model)
            if model in by_model:
                by_model[model] = round(by_model[model] + usd, 4)
    names = {(r.get("skill") or "").strip() for r in rows} - {"total", "lead", ""}
    usd = total if total is not None else (round(sum(by_skill.values()) + (lead or 0), 4) if by_skill or lead else None)
    if usd is None:
        m = re.search(r"Total:?\s*\*{0,2}\s*\$([\d,]+(?:\.\d+)?)|\*\*\$([\d,]+(?:\.\d+)?)\*\*", readme)
        usd = _num(next(g for g in m.groups() if g).replace(",", "")) if m else None
    m = re.search(r"^\|\s*lead\s*\|.*?\$([\d,.]+)\s*\|\s*$", readme, re.M)
    lead = _num(m.group(1)) if m else lead
    model_of = {s: "opus" if "opus" in ms else "sonnet" if "sonnet" in ms else None for s, ms in models.items()}
    return usd, by_model if rows else {"opus": 0.0, "sonnet": 0.0}, lead, by_skill, model_of, names


def _table(readme):
    """README skill table: skill -> {minutes: last number of minutes or None, usd}."""
    out = {}
    for line in readme.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("|") or len(cells) < 3 or not re.fullmatch(r"`?[a-z][a-z-]*`?", cells[0]):
            continue
        name = cells[0].strip("`")
        if name in ("lead", "skill"):
            continue
        mins = re.findall(r"(\d+)\s*(?:min|\+|$)", cells[2]) if "min" in cells[2] else []
        usd = re.search(r"\$([\d.]+)", cells[-1])
        out[name] = {"minutes": int(mins[-1]) if mins else None, "usd": _num(usd.group(1)) if usd else None}
    return out


def _issues(text):
    """Rows of the tables under '### <skill>' in the studio lead's part of issues.md."""
    part = _section(text, "For the studio lead") or ""
    out = {}
    for sec in re.split(r"^### ", part, flags=re.M)[1:]:
        skill, _, body = sec.partition("\n")
        head = None
        for line in body.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not line.startswith("|") or set("".join(cells)) <= set("-: "):
                continue
            if head is None:
                head = [c.lower() for c in cells]
                continue
            row = dict(zip(head, cells))
            fix = next((v for k, v in row.items() if "fix" in k), "")
            out.setdefault(skill.strip(), []).append(
                {"severity": row.get("severity", ""), "issue": row.get("issue", ""), "fix": fix})
    return out


def _flagged(log_text, stem):
    line = ""
    for raw in log_text.splitlines():
        if "frames.py names:" in raw:
            line = raw.split("frames.py names:", 1)[1]
    short = re.split(r"_\d-", stem)[0]
    for key in dict.fromkeys((stem, short)):
        for part in line.split(";"):
            if re.search(r"(?<![\w-])" + re.escape(key) + r"(?![\w-])", part):
                return part.strip()
    return None


def _items(folder, layout, n, log_text, required):
    fmt = layout.get("format") or {}
    wmm, hmm = fmt.get("width_mm") or 594, fmt.get("height_mm") or 841
    panels = layout.get("panels") or []
    out = []
    for it in (panels[n - 1].get("items") or []) if n <= len(panels) else []:
        file = it.get("file")
        if not file or not it.get("id"):
            continue
        frame = it.get("frame") or {}
        w, h = it.get("w") or frame.get("w"), it.get("h") or frame.get("h")
        if w is None:
            continue
        if h is None:
            h = w
            png = folder / Path(file).with_suffix(".png")
            if png.exists():
                from PIL import Image
                with Image.open(png) as im:
                    h = w * im.size[1] / im.size[0]
        by = next((r.get("by") for r in required if r.get("id") == it["id"] and r.get("by")), None)
        out.append({"id": it["id"], "file": file, "skill": by or Path(file).parts[0],
                    "caption": it.get("caption"), "shows": it.get("shows"), "scale": it.get("scale"),
                    "x": (it.get("x") or 0) / wmm, "y": (it.get("y") or 0) / hmm, "w": w / wmm, "h": h / hmm,
                    "img": "img/%s/%s.jpg" % (folder.name, it["id"]),
                    "flagged": _flagged(log_text, Path(file).stem)})
    return out


def _scrub_all(value, names, skip=("key", "img")):
    if isinstance(value, str):
        return scrub(value, names)
    if isinstance(value, list):
        return [_scrub_all(v, names) for v in value]
    if isinstance(value, dict):
        return {k: v if k in skip else _scrub_all(v, names) for k, v in value.items()}
    return value


def read_run(folder, skills, overrides, names):
    folder = Path(folder)
    key = folder.name
    ov = overrides.get(key, {})
    readme, version = _text(folder / "README.md"), _text(folder / "version.md")
    log_text = _text(folder / "log.md")
    usd, by_model, usd_lead, usd_skill, model_of, cost_names = _cost(folder, readme)
    table = _table(readme)

    # timeline
    parsed = parse_log(log_text, (set(skills) | cost_names | set(table)) - {"lead"})
    pair = re.search(HHMM + r"\s+to\s+" + HHMM, readme) or re.search(HHMM + r"\s+to\s+" + HHMM, version)
    start = parsed["start"] or (("%02d:%s" % (int(pair[1]), pair[2])) if pair else None)
    end = ("%02d:%s" % (int(pair[3]), pair[4])) if pair else parsed["end"]
    minutes = None
    if start and end:
        a, b = start.split(":"), end.split(":")
        minutes = _minutes(a, b)
    bars = {}
    for b in parsed["bars"]:
        bars.setdefault(b["skill"], []).append({k: b[k] for k in ("kind", "t0", "t1", "line")})
    for s, info in table.items():
        if s not in bars and info["minutes"] and minutes:
            bars[s] = [{"kind": "first", "t0": max(minutes - info["minutes"], 0), "t1": minutes, "line": ""}]

    # per-skill files
    fixes = _json(folder / "art-direction" / "fixes.json")
    issues = _issues(_text(folder / "panel-layout" / "issues.md"))
    summaries = {p.parent.name: _text(p) for p in sorted(folder.glob("*/summary.md")) if not p.parent.name.startswith(".")}
    layout = _json(folder / "panel-layout" / "layout.json")
    layout = layout if isinstance(layout, dict) else {}
    pngs = sorted(folder.glob("panel-layout/panel-*.png"), key=lambda p: int(re.search(r"(\d+)", p.stem)[1]))
    panels = []
    for png in pngs:
        n = int(re.search(r"(\d+)", png.stem)[1])
        try:
            from PIL import Image
            with Image.open(png) as im:
                size = im.size
        except Exception:
            size = (None, None)
        panels.append({"n": n, "img": "img/%s/panel-%d.jpg" % (key, n), "w_px": size[0], "h_px": size[1],
                       "items": _items(folder, layout, n, log_text, layout.get("required") or [])})
    flagged = {i["skill"] for p in panels for i in p["items"] if i["flagged"]}

    names_all = set(usd_skill) | set(summaries) | set(fixes) | set(issues) | set(bars) | {
        s for s, i in table.items() if i["minutes"] or i["usd"]}
    skills_out = {}
    for s in sorted(names_all):
        text = summaries.get(s)
        m = UNSURE.search(text) if text else None
        fx = list(fixes.get(s) or [])
        isq = issues.get(s, [])
        skills_out[s] = {"model": model_of.get(s), "usd": usd_skill.get(s, table.get(s, {}).get("usd")),
                         "runs": bars.get(s, []), "summary_md": text, "unsure": m.group(1).strip() if m else None,
                         "fixes": fx, "issues": isq, "red": bool(fx or isq or s in flagged)}

    # prose
    jury = _text(folder / "jury" / "summary.md").strip()
    vm = re.match(r"Verdict:\s*([^.;(]+)", jury)
    pl = _text(folder / "panel-layout" / "summary.md")
    im = re.search(r"(\d+) of the brief['’]s (\d+) required items", pl)
    am = re.search(r"all (\d+) of the brief['’]s required items", pl)
    items = [int(im[1]), int(im[2])] if im else [int(am[1])] * 2 if am else None
    stats = _json(folder / "massing" / "stats.json")
    cm = re.search(r"Skills at commit:\s*`?(\w+)", version) or re.search(r"skills at commit `?(\w+)", readme)
    nm = re.search(r"^- New in this run:\s*(.+)$", version, re.M)
    tm = re.match(r"# [^\n:]*:\s*(.+)", readme)
    label = key.split("_", 1)[1]

    run = {"key": key, "label": label, "title": tm.group(1).strip() if tm else label, "date": key[:10],
           "kind": "run", "usd": usd, "minutes": minutes, "verdict": vm.group(1).strip() if vm else None,
           "items": items, "n_skills": len(skills_out),
           "has": {"geo": any(folder.glob("*/*.geojson")), "panels": bool(panels),
                   "layout": (folder / "panel-layout" / "layout.json").exists(), "loop": False},
           "start": start, "end": end, "commit": cm.group(1) if cm else None,
           "new_in_run": nm.group(1).strip() if nm else None,
           "usd_by_skill": usd_skill, "usd_by_model": by_model, "usd_lead": usd_lead,
           "headline": {"homes": stats.get("homes"), "gfa_m2": stats.get("total_gfa"),
                        "new_buildings": stats.get("n_new"), "green_ha": stats.get("green_ha")},
           "jury": {"verdict": vm.group(1).strip() if vm else None, "summary_md": jury or None,
                    "links": ov.get("jury_links") or {}},
           "skills": skills_out, "events": parsed["events"], "panels": panels,
           "open_problems_md": _section(readme, "Open problems"),
           "handed_on_md": _section(readme, "Handed on by panel-layout")}
    for k in OVERRIDABLE:
        if k in ov:
            run[k] = ov[k]
    if "verdict" in ov:
        run["jury"]["verdict"] = ov["verdict"]
    return _scrub_all(run, names)


def card(run):
    return {k: run[k] for k in CARD_KEYS}
