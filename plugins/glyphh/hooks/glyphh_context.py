#!/usr/bin/env python3
"""Your glyphh in Claude's context: what your installed templates (Agentic memory first) hold about you, put before
Claude by two Claude Code hooks, standard library only:

  session  SessionStart: your personality and your rules, so Claude starts every session as you have grown it
  prompt   UserPromptSubmit: what your glyphh holds that bears on what you just asked

Both ask the Glyphh server (POST /v1/me/glyphh/context, docs/specs/templates.md in glyphh-ai/server) with this
install's token from ~/.glyphh/install.json, at GLYPHH_SERVER_URL or https://api.glyphh.ai. Signed out, with nothing
installed, offline or slow, they say nothing: a hook never stands in the way of a prompt."""

import json
import os
import sys
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("GLYPHH_HOME") or Path.home() / ".glyphh")
SERVER = (os.environ.get("GLYPHH_SERVER_URL") or "https://api.glyphh.ai").rstrip("/")
TIMEOUT = 4.0  # seconds; the hook's own timeout in hooks.json is longer
PROMPT_MAX = 2000
EVENTS = {"session": "SessionStart", "prompt": "UserPromptSubmit"}
# Cloudflare in front of api.glyphh.ai refuses urllib's own User-Agent (error 1010, a 403), so the hook names itself
USER_AGENT = "glyphh-hook/1.19.0"


def token() -> str | None:
    try:
        found = json.loads((HOME / "install.json").read_text())
    except (OSError, ValueError):
        return None
    return found.get("token") if isinstance(found, dict) else None


def context(bearer: str, prompt: str | None) -> str:
    body = json.dumps({"prompt": prompt[:PROMPT_MAX]} if prompt else {}).encode()
    headers = {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    req = urllib.request.Request(f"{SERVER}/v1/me/glyphh/context", body, headers, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return str(json.load(res).get("context") or "")


def main(mode: str) -> None:
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        hook = {}
    bearer = token()
    prompt = (hook.get("prompt") or "").strip() if mode == "prompt" else None
    if not bearer or (mode == "prompt" and not prompt):
        return
    try:
        text = context(bearer, prompt)
    except Exception:  # signed out, Ada Cloud off, offline, slow: nothing to add
        return
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": EVENTS[mode], "additionalContext": text}}))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in EVENTS else "session")
