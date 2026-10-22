#!/usr/bin/env python3
"""The file ledger: what was last done to each file, and why, kept across turns, compactions and sessions, in
~/.glyphh/ledger/ledger.sqlite. Three Claude Code hooks, standard library only:

  record   PostToolUse on Edit, Write, MultiEdit: one row per change (path, when, session, the request it served,
           what changed), from the hook's JSON on stdin
  recall   PostToolUse on Read: the last changes to that file, as additional context ("this file was last edited
           4 turns ago for 'fix the flaky test': replaced ... with ...")
  prompt   UserPromptSubmit: the files this session touched in its last few turns and their last change, so a turn
           after a compaction still knows what it was doing

Measured, not assumed: benchmarks/session in glyphh-ai/glyphh says what a turn needs from earlier turns is the
last touch of each file it works on, and that recency and request-text search recover a third and a seventh of it.
The ledger recovers it by construction. Whether it saves tokens is the measurement that follows (measure.py)."""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("GLYPHH_HOME") or Path.home() / ".glyphh") / "ledger"
DB = HOME / "ledger.sqlite"
RECALL = 3  # last changes shown on a Read
RECENT_TURNS = 3  # turns of this session whose files are listed on a prompt
SNIP = 90  # characters of old/new text kept per change
SKIP = ("/tmp/", "/.claude/", "/node_modules/", ".sqlite", ".lock")


def db() -> sqlite3.Connection:
    HOME.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=5)
    c.execute(
        "CREATE TABLE IF NOT EXISTS changes (id INTEGER PRIMARY KEY, path TEXT NOT NULL, at REAL NOT NULL,"
        " session TEXT NOT NULL, turn INTEGER NOT NULL, cwd TEXT, request TEXT, tool TEXT, what TEXT)"
    )
    c.execute("CREATE INDEX IF NOT EXISTS changes_path ON changes (path, at)")
    c.execute("CREATE INDEX IF NOT EXISTS changes_session ON changes (session, turn)")
    c.execute("CREATE TABLE IF NOT EXISTS turns (session TEXT NOT NULL, turn INTEGER NOT NULL, at REAL NOT NULL, request TEXT, PRIMARY KEY (session, turn))")
    return c


def last_request(transcript: str | None) -> tuple[int, str]:
    """The current turn's number and the request it serves, from the transcript's user lines."""
    n, text = 0, ""
    if not transcript or not os.path.exists(transcript):
        return n, text
    try:
        with open(transcript, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 400_000))
            tail = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return n, text
    for line in tail:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        c = (r.get("message") or {}).get("content")
        if r.get("type") == "user" and isinstance(c, str) and not c.startswith("<") and not c.startswith("[Request interrupted"):
            n += 1
            text = c
    return n, text[:200].replace("\n", " ")


def ago(seconds: float) -> str:
    m = seconds / 60
    if m < 1:
        return "just now"
    if m < 60:
        return f"{m:.0f} min ago"
    if m < 60 * 24:
        return f"{m / 60:.0f} h ago"
    return f"{m / 1440:.0f} days ago"


def describe(tool: str, inp: dict) -> str:
    if tool == "Write":
        return f"wrote the file ({len(str(inp.get('content', '')).splitlines())} lines)"
    if tool == "MultiEdit":
        edits = inp.get("edits") or []
        return f"{len(edits)} edits" + (f", first: replaced {json.dumps(str(edits[0].get('old_string', ''))[:SNIP])}" if edits else "")
    old, new = str(inp.get("old_string", ""))[:SNIP], str(inp.get("new_string", ""))[:SNIP]
    return f"replaced {json.dumps(old)} with {json.dumps(new)}"


def record(h: dict) -> None:
    path = str((h.get("tool_input") or {}).get("file_path") or "")
    if not path or any(s in path for s in SKIP):
        return
    turn, request = last_request(h.get("transcript_path"))
    c = db()
    c.execute("INSERT OR IGNORE INTO turns VALUES (?, ?, ?, ?)", (h.get("session_id", "?"), turn, time.time(), request))
    c.execute(
        "INSERT INTO changes (path, at, session, turn, cwd, request, tool, what) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (path, time.time(), h.get("session_id", "?"), turn, h.get("cwd"), request, h.get("tool_name"), describe(h.get("tool_name", ""), h.get("tool_input") or {})),
    )
    c.commit()


def context(text: str, event: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def recall(h: dict) -> None:
    path = str((h.get("tool_input") or {}).get("file_path") or "")
    if not path or any(s in path for s in SKIP):
        return
    rows = db().execute("SELECT at, session, turn, request, what FROM changes WHERE path = ? ORDER BY at DESC LIMIT ?", (path, RECALL)).fetchall()
    if not rows:
        return
    me = h.get("session_id")
    now = time.time()
    lines = [f"Ledger for {Path(path).name}, last changes (newest first):"]
    for at, session, turn, request, what in rows:
        where = "this session" if session == me else "an earlier session"
        lines.append(f"- {ago(now - at)}, {where}, for: {request!r}: {what}")
    context("\n".join(lines), "PostToolUse")


def prompt(h: dict) -> None:
    me = h.get("session_id")
    c = db()
    turns = [r[0] for r in c.execute("SELECT DISTINCT turn FROM changes WHERE session = ? ORDER BY turn DESC LIMIT ?", (me, RECENT_TURNS)).fetchall()]
    if not turns:
        return
    rows = c.execute(
        "SELECT path, MAX(at), request, what FROM changes WHERE session = ? AND turn IN (%s) GROUP BY path ORDER BY MAX(at) DESC LIMIT 12" % ",".join("?" * len(turns)),
        (me, *turns),
    ).fetchall()
    now = time.time()
    lines = ["Ledger, files this session changed in its last turns (newest first):"]
    for path, at, request, what in rows:
        lines.append(f"- {path} ({ago(now - at)}, for {request[:80]!r}): {what}")
    context("\n".join(lines), "UserPromptSubmit")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        h = json.load(sys.stdin)
    except ValueError:
        h = {}
    try:
        {"record": record, "recall": recall, "prompt": prompt}[cmd](h)
    except KeyError:
        sys.stderr.write("ledger.py record|recall|prompt\n")
        sys.exit(2)
    except Exception as err:  # a hook must never break a turn
        sys.stderr.write(f"ledger: {type(err).__name__}: {err}\n")


if __name__ == "__main__":
    main()
