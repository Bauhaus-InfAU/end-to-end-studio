"""Read a run's log.md into a timeline: bars (one per skill run) and events."""
import re

TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")
START = re.compile(r"\bstart(?:ed)?(?: reruns)?:?\s*(.*)", re.I)
DONE = re.compile(
    r"^(?P<skill>[a-z-]+)(?P<paren> \([^)]*\))?(?: (?P<word>second run|second|rerun|redraw))? done:?\s*(?P<rest>.*)$"
)
CHECKS = (("frames.py", "check"), ("cost.py", "check"), ("side_by_side.py", "lead"))


def _kind(word, paren):
    word = word or ""
    if "rerun" in word or "redraw" in word:
        return "rerun"
    if "second" in word or "second" in (paren or "") or "(end)" in (paren or ""):
        return "second"
    return "first"


def _first_skill(part, skills):
    best = None
    for name in skills:
        m = re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", part)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), name)
    return best[1] if best else None


def parse_log(text, skills):
    bars, events, open_starts = [], [], []
    first = prev = None
    offset = 0
    start_label = end_label = None
    last_start_t = 0
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("- "):
            line = line[2:]
        tm = TIME.search(line)
        if tm:
            label = f"{int(tm.group(1)):02d}:{tm.group(2)}"
            minute = int(tm.group(1)) * 60 + int(tm.group(2)) + offset
            while prev is not None and minute < prev - 600:
                offset += 1440
                minute += 1440
            prev = minute
            if first is None:
                first, start_label = minute, label
            end_label = label
            body = (line[:tm.start()] + line[tm.end():]).strip()
        elif prev is None:
            continue
        else:
            minute, body = prev, line  # no time: the previous timed line's time
        t = minute - first

        rest = body
        d = DONE.match(body.lstrip(": "))
        if d and d.group("skill") in skills:
            skill, kind = d.group("skill"), _kind(d.group("word"), d.group("paren"))
            t0 = last_start_t
            for i in range(len(open_starts) - 1, -1, -1):
                if open_starts[i][:2] == (skill, kind):
                    t0 = open_starts.pop(i)[2]
                    break
            bars.append({"skill": skill, "kind": kind, "t0": t0, "t1": t,
                         "line": d.group("rest").strip(" .:")[:200]})
            rest = d.group("rest")  # a start may follow on the same line
            if not START.search(rest):
                continue
        s = START.search(rest)
        if s:
            last_start_t = t
            for part in s.group(1).split(","):
                skill = _first_skill(part, skills)
                if skill:
                    kind = "rerun" if "reruns" in rest else "second" if re.search(r"second|\(end\)", part) else "first"
                    open_starts.append((skill, kind, t))
            continue
        for name, ev in CHECKS:
            if name in body:
                events.append({"t": t, "kind": ev, "text": body[:200]})
                break
    return {"start": start_label, "end": end_label, "bars": bars, "events": events}
