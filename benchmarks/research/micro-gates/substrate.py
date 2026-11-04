"""Claude with Ada as its memory: the same ten thin sessions as sessions.py, but Claude itself holds the Ada tools
(ada_mcp.py) and nothing else survives a session. It decides what models to make, what to record and when to ask
them or chain them with the beam. We watch what it does: the questions it gets right, and how its use of the
models changes session by session.

    uv run python substrate.py        # into results/substrate.json and results/substrate.txt
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import sessions

HERE = Path(__file__).parent
HOME = HERE / "results" / "ada_home"
PYTHON = sys.executable
TOOLS = ["ada_models", "ada_make", "ada_record", "ada_ask", "ada_beam", "ada_forget", "ada_note"]
BRIEF = (
    "You have Ada tools (ada_*). Your Ada models are the only thing that survives from one session to the next: this "
    "conversation is gone when it ends, and you cannot write files. Use the models to keep what you learn and to answer; "
    "make them better each session so that later sessions need less work. Start by looking at what you already have."
)


def mcp_config(session: int) -> str:
    config = {
        "mcpServers": {
            "ada": {"command": PYTHON, "args": [str(HERE / "ada_mcp.py")], "env": {"ADA_HOME": str(HOME), "ADA_SESSION": str(session)}}
        }
    }
    path = HOME / "mcp.json"
    path.write_text(json.dumps(config))
    return str(path)


def claude(prompt: str, session: int) -> dict:
    began = time.time()
    with tempfile.TemporaryDirectory() as empty:
        done = subprocess.run(
            ["claude", "-p", "--mcp-config", mcp_config(session), "--strict-mcp-config", "--setting-sources", "",
             "--no-session-persistence", "--allowedTools", ",".join(f"mcp__ada__{t}" for t in TOOLS),
             "--model", "opus", "--output-format", "json", "--max-budget-usd", sessions.BUDGET_USD,
             "--system-prompt", BRIEF],
            input=prompt, capture_output=True, text=True, cwd=empty, timeout=sessions.TIMEOUT * 2,
        )
    try:
        reply = json.loads(done.stdout)
    except json.JSONDecodeError:
        reply = {"result": "", "is_error": True}
    usage = reply.get("usage", {})
    tokens = sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"))
    return {
        "text": reply.get("result") or "",
        "error": bool(reply.get("is_error")),
        "tokens": tokens,
        "usd": reply.get("total_cost_usd", 0),
        "seconds": time.time() - began,
        "turns": reply.get("num_turns", 0),
    }


def calls(session: int) -> Counter:
    log = HOME / "calls.jsonl"
    if not log.exists():
        return Counter()
    return Counter(c["tool"] for c in map(json.loads, log.read_text().splitlines()) if c["session"] == str(session))


def main() -> None:
    all_sessions, _ = sessions.sessions(sessions.SEED)
    shutil.rmtree(HOME, ignore_errors=True)
    HOME.mkdir(parents=True)
    rows = []
    for s in all_sessions:
        prompt = (
            f"Session {s.number} of {sessions.SESSIONS}.\n{sessions.RULES}\n{sessions.lines(s.chains)}\n\n"
            f"Questions:\n{sessions.asked(s.questions)}\n\n{sessions.ANSWERS}"
        )
        call = claude(prompt, s.number)
        answers = sessions.parsed(call["text"])
        right = sum(answers.get(i) == q.end for i, q in enumerate(s.questions, 1))
        used = calls(s.number)
        row = sessions.scored(s.number, "ada", right, call, turns=call["turns"], calls=dict(used))
        rows.append(row)
        print(f"session {s.number:>2}: right {right:>2} of {len(s.questions)}, {call['tokens']:>7} tokens, {call['seconds']:>4.0f}s, calls {dict(used)}", flush=True)
        (HERE / "results/substrate.json").write_text(json.dumps(rows, indent=1) + "\n")
    note = HOME / "note.txt"
    lines = [f"Claude with Ada as its only memory: seed {sessions.SEED}, {sessions.CHAINS_PER_SESSION} chains a session.", ""]
    lines += ["session  right   tokens   sec  turns  " + "".join(f"{t[4:]:>8}" for t in TOOLS)]
    for r in rows:
        lines.append(f"{r['session']:<9}{r['right']:>5}{r['tokens']:>9}{r['seconds']:>6.0f}{r['turns']:>7}  " + "".join(f"{r['calls'].get(t, 0):>8}" for t in TOOLS))
    lines += ["", f"ada: {sum(r['right'] for r in rows)} of {sum(r['of'] for r in rows)} right, {sum(r['tokens'] for r in rows):,} tokens, ${sum(r['usd'] for r in rows):.2f}", ""]
    lines += ["Its note to itself:", note.read_text() if note.exists() else "(none)"]
    (HERE / "results/substrate.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
