"""How many tokens a studio helper starts with, in a lean session. Spends a few cents.

    python tests/probe_helper.py [agent name]      (default: studio:studio-helper)

Starts Claude Code in the repo with only the repo's settings and plugins and no MCP servers,
asks it to start one helper with a trivial task, and prints the first step of the lead and
of the helper, in tokens.
"""
import json, os, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LEAN = ["--setting-sources", "project,local", "--strict-mcp-config"]


def first_step(path):
    for line in open(path, encoding="utf-8"):
        e = json.loads(line)
        if e.get("type") == "assistant" and not e.get("parent_tool_use_id"):
            u = e["message"]["usage"]
            return u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)


def main():
    agent = sys.argv[1] if len(sys.argv) > 1 else "studio:studio-helper"
    prompt = (f'Use the Agent tool once with subagent_type "{agent}" and the task '
              '"Reply with the word OK and nothing else." Then reply DONE.')
    env = dict(os.environ, ENABLE_CLAUDEAI_MCP_SERVERS="false")
    out = subprocess.run(["claude", "-p", prompt, "--model", "sonnet", *LEAN, "--output-format", "stream-json",
                          "--verbose", "--max-budget-usd", "1"], cwd=REPO, env=env, capture_output=True,
                         text=True, encoding="utf-8")
    session, lead = None, None
    for line in out.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            session = e["session_id"]
            print("agents offered:", ", ".join(a for a in e.get("agents", []) if "studio" in a) or "none with studio")
        if e.get("type") == "assistant" and lead is None and not e.get("parent_tool_use_id"):
            u = e["message"]["usage"]
            lead = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
        if e.get("type") == "result":
            print("result:", (e.get("result") or "")[:80].replace("\n", " "), f"cost ${e.get('total_cost_usd', 0):.2f}")
    projects = Path.home() / ".claude/projects" / "".join(c if c.isalnum() or c == "-" else "-" for c in str(REPO))
    subs = sorted((projects / str(session) / "subagents").glob("agent-*.jsonl")) if session else []
    for s in subs:
        meta = json.loads(s.with_suffix(".meta.json").read_text(encoding="utf-8"))
        print(f"lead {lead} helper {first_step(s)} ({meta.get('agentType')})")
    if not subs:
        print(f"lead {lead} helper none")


if __name__ == "__main__":
    main()
