"""launch_watch: glyphh's launch numbers each morning (GitHub, PyPI, npm), kept in its SQLite database day by day,
and emailed as a summary by the rrotor's signed-in claude CLI, through the owner's claude.ai Gmail connector
(ctx.cli). From Claude it asks before emailing; a scheduled run sends on its own, since nobody is there to answer
before the wait expires."""

from __future__ import annotations

import json
from typing import Any

from rrotor import CliError, Ctx, Result

REPO = "glyphh-ai/glyphh"  # what it watches: change these three to watch your own launch
PYPI = "glyphh"
NPM = "@glyphh-ai/glyphh"
GMAIL_SEND = "mcp__claude_ai_Gmail__send_message"  # the Gmail connector's send tool, as Claude Code names it
ASK = """Send one email with your Gmail connector's send_message tool, exactly as given here, and do nothing else.

To: {to}
Subject: {subject}

{body}

Do not change the subject or the body. Once it is sent, reply with only: SENT <the message id>.
If it cannot be sent, reply with only: FAILED <why>."""
GH = {"Accept": "application/vnd.github+json", "User-Agent": "launch_watch"}
COLS = ("day", "stars", "forks", "open_issues", "pypi_day", "pypi_week", "npm_day", "npm_week", "new_items", "emailed")


def _schema(ctx: Ctx) -> None:
    with ctx.db:
        ctx.db.execute(
            "create table if not exists days (day text primary key, stars int, forks int, open_issues int,"
            " pypi_day int, pypi_week int, npm_day int, npm_week int, new_items text, emailed int default 0)"
        )


def _collect(ctx: Ctx, since: str | None) -> dict[str, Any]:
    repo = ctx.http.get(f"https://api.github.com/repos/{REPO}", headers=GH).raise_for_status().json()
    params = {"state": "all", "per_page": "50", "sort": "created", "direction": "desc"}
    if since:
        params["since"] = f"{since}T00:00:00Z"
    items = ctx.http.get(f"https://api.github.com/repos/{REPO}/issues", params=params, headers=GH)
    new = [
        {"kind": "PR" if "pull_request" in i else "issue", "number": i["number"], "title": i["title"],
         "by": i["user"]["login"], "url": i["html_url"]}
        for i in items.raise_for_status().json()
        if since is None or i["created_at"][:10] >= since
    ]
    pypi = ctx.http.get(f"https://pypistats.org/api/packages/{PYPI}/recent").raise_for_status().json()["data"]
    npm_day = ctx.http.get(f"https://api.npmjs.org/downloads/point/last-day/{NPM}").raise_for_status().json()
    npm_week = ctx.http.get(f"https://api.npmjs.org/downloads/point/last-week/{NPM}").raise_for_status().json()
    return {
        "stars": repo["stargazers_count"], "forks": repo["forks_count"], "open_issues": repo["open_issues_count"],
        "pypi_day": pypi["last_day"], "pypi_week": pypi["last_week"],
        "npm_day": npm_day["downloads"], "npm_week": npm_week["downloads"], "new_items": new,
    }


def _delta(now: int, before: int | None) -> str:
    if before is None:
        return f"{now}"
    d = now - before
    return f"{now} ({'+' if d >= 0 else ''}{d})"


def _summary(day: str, n: dict[str, Any], prev: dict[str, Any] | None) -> tuple[str, str]:
    p = prev or {}
    new = n["new_items"]
    lines = [
        f"Stars: {_delta(n['stars'], p.get('stars'))}",
        f"Forks: {_delta(n['forks'], p.get('forks'))}",
        f"Open issues + PRs: {_delta(n['open_issues'], p.get('open_issues'))}",
        f"PyPI {PYPI}: {n['pypi_day']} yesterday, {n['pypi_week']} this week",
        f"npm {NPM}: {n['npm_day']} yesterday, {n['npm_week']} this week",
        f"New on GitHub since last time: {len(new)}" if new else "Nothing new on GitHub since last time.",
    ]
    lines += [f"  {i['kind']} #{i['number']} {i['title']} (by {i['by']}) {i['url']}" for i in new]
    subject = f"glyphh {day}: {n['stars']} stars, {n['pypi_day']} PyPI, {n['npm_day']} npm, {len(new)} new"
    return subject, "\n".join(lines)


def _send(ctx: Ctx, to: str, subject: str, body: str) -> tuple[bool, str]:
    """The summary emailed by the claude CLI through Gmail (once per run: ctx.cli keeps what it answered). Answers
    whether it was sent, and the message id or why not."""
    prompt = ASK.format(to=to, subject=subject, body=body)
    try:
        got = ctx.cli("claude", ["-p", prompt, "--allowedTools", GMAIL_SEND, "--output-format", "json"])
    except CliError as err:
        return False, f"{err.code}: {err.message}"
    try:
        answer = json.loads(got.stdout)
    except ValueError:
        return False, f"claude exited {got.exit_code}: {(got.stderr or got.stdout).strip()[:500]}"
    said = str(answer.get("result") or "").strip()
    if got.exit_code != 0 or answer.get("is_error") or not said.startswith("SENT"):
        return False, said[:500] or f"claude exited {got.exit_code}"
    return True, said.removeprefix("SENT").strip()


def morning(ctx: Ctx, inputs: dict[str, Any]) -> Result:
    day = str(ctx.today())
    _schema(ctx)
    row = ctx.db.execute(
        "select day, stars, forks, open_issues from days where day < ? order by day desc limit 1", (day,)
    ).fetchone()
    prev = dict(zip(("day", "stars", "forks", "open_issues"), row)) if row else None
    numbers = ctx.checkpoint(f"collect:{day}", lambda: _collect(ctx, prev["day"] if prev else None))
    with ctx.db:
        ctx.db.execute(
            "insert into days (day, stars, forks, open_issues, pypi_day, pypi_week, npm_day, npm_week, new_items)"
            " values (?, ?, ?, ?, ?, ?, ?, ?, ?) on conflict(day) do update set stars=excluded.stars,"
            " forks=excluded.forks, open_issues=excluded.open_issues, pypi_day=excluded.pypi_day,"
            " pypi_week=excluded.pypi_week, npm_day=excluded.npm_day, npm_week=excluded.npm_week,"
            " new_items=excluded.new_items",
            (day, numbers["stars"], numbers["forks"], numbers["open_issues"], numbers["pypi_day"],
             numbers["pypi_week"], numbers["npm_day"], numbers["npm_week"], json.dumps(numbers["new_items"])),
        )
    subject, body = _summary(day, numbers, prev)
    to = inputs["to"]
    if ctx.caller != "schedule" and not ctx.ask_approval("email", f"Email this to {to}?\n\n{subject}\n\n{body}"):
        ctx.log("kept, not emailed: declined", day=day)
        return Result.done({"day": day, "subject": subject, "summary": body, "emailed": False})
    sent, said = _send(ctx, to, subject, body)
    if not sent:
        ctx.log("kept, not emailed: claude could not send it", day=day, why=said)
        return Result.done({"day": day, "subject": subject, "summary": body, "emailed": False, "error": said})
    with ctx.db:
        ctx.db.execute("update days set emailed = 1 where day = ?", (day,))
    ctx.log("emailed", day=day, to=to, id=said)
    return Result.done({"day": day, "subject": subject, "summary": body, "emailed": True, "email_id": said})


def history(ctx: Ctx, inputs: dict[str, Any]) -> Result:
    _schema(ctx)
    rows = ctx.db.execute(f"select {', '.join(COLS)} from days order by day desc limit ?", (inputs.get("days", 30),))
    days = [dict(zip(COLS, r)) | {"new_items": json.loads(r[8] or "[]"), "emailed": bool(r[9])} for r in rows]
    return Result.done({"days": days})
