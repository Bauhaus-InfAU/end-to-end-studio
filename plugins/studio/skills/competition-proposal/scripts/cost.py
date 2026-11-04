"""What a studio run cost, from its Claude Code transcripts, at API prices.

    python cost.py --version <version folder> [--projects <transcripts dir>] [--session <id>] [--ceiling <usd>]

Writes <version>/cost.csv: one row per helper, one for the lead, one total, and prints whether the total is past
the ceiling (default $30), past which the lead skips its revision round. The lead's
transcript is the session that mentions the version folder's name and started the most
helpers named after its label; --session picks one by id instead.
"""
import argparse, csv, json, os, re, sys
from pathlib import Path

# $/MTok: input, 5-minute cache write, 1-hour cache write, cache read, output (2026-11)
PRICES = {
    "opus": (4, 5, 8, 0.20, 20),
    "sonnet": (2, 2.5, 4, 0.20, 10),
    "haiku": (0.10, 0.125, 0.20, 0.01, 0.50),
}
KEYS = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")


def family(model):
    for name in PRICES:
        if name in (model or ""):
            return name
    return "opus"


def tally(path):
    """Tokens and dollars of one transcript, each message id counted once."""
    t = dict.fromkeys(KEYS, 0)
    t.update(model="", steps=0, usd=0.0)
    seen = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            m = e.get("message") if isinstance(e, dict) else None
            if e.get("type") != "assistant" or not isinstance(m, dict) or m.get("id") in seen:
                continue
            seen.add(m.get("id"))
            u = m.get("usage") or {}
            write = u.get("cache_creation_input_tokens") or 0
            split = u.get("cache_creation") or {}
            w5 = split.get("ephemeral_5m_input_tokens")
            w1 = split.get("ephemeral_1h_input_tokens")
            if w5 is None and w1 is None:
                w5, w1 = 0, write
            n = (u.get("input_tokens") or 0, w5 or 0, w1 or 0,
                 u.get("cache_read_input_tokens") or 0, u.get("output_tokens") or 0)
            fam = family(m.get("model"))
            t["model"] = t["model"] or fam
            t["steps"] += 1
            for k, v in zip(KEYS, n):
                t[k] += v
            t["usd"] += sum(v * p for v, p in zip(n, PRICES[fam])) / 1e6
    return t


def default_projects():
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return base / "projects" / re.sub(r"[^A-Za-z0-9-]", "-", str(Path.cwd().resolve()))


def helpers(session_file):
    folder = session_file.with_suffix("") / "subagents"
    return sorted(folder.glob("agent-*.jsonl")) if folder.is_dir() else []


def describe(helper):
    meta = helper.with_suffix(".meta.json")
    try:
        return json.loads(meta.read_text(encoding="utf-8")).get("description") or ""
    except (OSError, ValueError):
        return ""


def labelled(description, label):
    """The lead names each helper `<skill> <label>` or `<skill> <label> second`; the label is a whole word."""
    return label in description.split()[1:]


def find_session(projects, name):
    label = name.split("_", 1)[-1]
    best, best_n = None, -1
    for f in projects.glob("*.jsonl"):
        try:
            if name not in f.read_text(encoding="utf-8", errors="ignore"):
                continue
        except OSError:
            continue
        n = sum(labelled(describe(h), label) for h in helpers(f))
        if n > best_n or (n == best_n and f.stat().st_mtime > best.stat().st_mtime):
            best, best_n = f, n
    return best


def row(skill, run, t):
    return {"skill": skill, "run": run, "model": t["model"], "steps": t["steps"], "input": t["input"],
            "cache_write": t["cache_write_5m"] + t["cache_write_1h"], "cache_read": t["cache_read"],
            "output": t["output"], "usd": f"{t['usd']:.2f}"}


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--version", required=True, help="the version folder")
    a.add_argument("--projects", help="the transcripts folder (default: this project's in ~/.claude/projects)")
    a.add_argument("--session", help="the lead's session id")
    a.add_argument("--ceiling", type=float, default=30.0,
                   help="dollars the run may cost (default 30: what a full run used to cost, about three of a Pro plan's 5-hour windows)")
    args = a.parse_args(argv)
    version = Path(args.version)
    projects = Path(args.projects) if args.projects else default_projects()
    if args.session:
        lead = projects / f"{args.session}.jsonl"
    else:
        lead = find_session(projects, version.name)
    if not lead or not lead.exists():
        sys.exit(f"no transcript in {projects} mentions {version.name}")
    rows, total = [], dict.fromkeys(KEYS, 0)
    total.update(model="", steps=0, usd=0.0)
    label = version.name.split("_", 1)[-1]
    mine = [h for h in helpers(lead) if labelled(describe(h), label)] or helpers(lead)
    for h in mine:
        words = describe(h).split()
        t = tally(h)
        run = "2" if any(w in ("second", "rerun") for w in words) else "1"
        rows.append(row(words[0] if words else h.stem, run, t))
        for k in (*KEYS, "steps", "usd"):
            total[k] += t[k]
    t = tally(lead)
    rows.append(row("lead", "1", t))
    for k in (*KEYS, "steps", "usd"):
        total[k] += t[k]
    rows.append(row("total", "", total))
    version.mkdir(parents=True, exist_ok=True)
    with open(version / "cost.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    side = "past" if total["usd"] > args.ceiling else "under"
    print(f"total ${total['usd']:.2f}, lead ${t['usd']:.2f}, {len(rows) - 2} helpers, {side} its ceiling of ${args.ceiling:.2f}")


if __name__ == "__main__":
    main()
