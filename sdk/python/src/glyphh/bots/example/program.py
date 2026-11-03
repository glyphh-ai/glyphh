"""Launch watch's code steps: the work code does better than Claude (fetching, keeping, the gate's case, delivering).
Each is `def name(ctx, inputs) -> dict`; the runner calls them in the loop's order and passes their data on. Change
REPO, PYPI and NPM to watch your own project."""

import datetime as dt

REPO = "glyphh-ai/glyphh"
PYPI = "glyphh"
NPM = "@glyphh-ai/glyphh"


def numbers(ctx, inputs):
    repo = ctx.http_json(f"https://api.github.com/repos/{REPO}")
    since = (ctx.today - dt.timedelta(days=1)).isoformat()
    found = ctx.http_json(f"https://api.github.com/search/issues?q=repo:{REPO}+created:>={since}&per_page=20")
    new = [{"title": i["title"], "url": i["html_url"], "pr": "pull_request" in i} for i in found.get("items", [])]
    pypi = ctx.http_json(f"https://pypistats.org/api/packages/{PYPI}/recent").get("data", {})
    npm = ctx.http_json(f"https://api.npmjs.org/downloads/point/last-day/{NPM}")
    return {
        "date": ctx.today.isoformat(),
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "new_issues": [i for i in new if not i["pr"]],
        "new_prs": [i for i in new if i["pr"]],
        "pypi_day": pypi.get("last_day", 0),
        "pypi_week": pypi.get("last_week", 0),
        "npm_day": npm.get("downloads", 0),
    }


def keep(ctx, inputs):
    """Today's numbers kept beside the earlier days; answers the days before, newest first (at most 14)."""
    db = ctx.db()
    db.execute("CREATE TABLE IF NOT EXISTS days (date TEXT PRIMARY KEY, stars INT, pypi INT, npm INT, issues INT, prs INT)")
    db.execute(
        "INSERT OR REPLACE INTO days VALUES (?, ?, ?, ?, ?, ?)",
        (inputs["date"], inputs["stars"], inputs["pypi_day"], inputs["npm_day"], len(inputs["new_issues"]),
         len(inputs["new_prs"])),
    )
    db.commit()
    rows = db.execute("SELECT * FROM days WHERE date < ? ORDER BY date DESC LIMIT 14", (inputs["date"],)).fetchall()
    return {"days": [dict(zip(["date", "stars", "pypi", "npm", "issues", "prs"], r)) for r in rows]}


def _pct(now, then):
    if not then:
        return 0 if not now else 100
    return round(100 * (now - then) / then)


def worth_case(ctx, data):
    """The worth_sending gate's case: what moved since the day before, and how long since the last summary."""
    today, before = data["numbers"], (data["keep"]["days"] or [None])[0]
    last_sent = ctx.state("last_sent")
    since = (ctx.today - dt.date.fromisoformat(last_sent)).days if last_sent else 14
    return {
        "day": {
            "moved": {
                "stars": max(-5, min(50, today["stars"] - before["stars"])) if before else 0,
                "issues": min(20, len(today["new_issues"])),
                "prs": min(20, len(today["new_prs"])),
                "pypi_pct": max(-100, min(300, _pct(today["pypi_day"], before["pypi"]))) if before else 0,
                "npm_pct": max(-100, min(300, _pct(today["npm_day"], before["npm"]))) if before else 0,
            },
            "when": {"weekday": ctx.today.strftime("%a"), "days_since_sent": min(since, 14), "run": ctx.run_id},
        }
    }


def deliver(ctx, inputs):
    """The summary into out/<date>.md."""
    path = ctx.dir / "out" / f"{ctx.today.isoformat()}.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text(inputs if isinstance(inputs, str) else str(inputs))
    ctx.set_state("last_sent", ctx.today.isoformat())
    return {"path": str(path)}
