"""open_issues: the page's one function, run as the app ("run_as": "app") for every viewer alike. It lists a
repository's open issues through the gh CLI on the rrotor, handed the organisation's token from the vault for that
one command (ctx.cli's env): no viewer signs in, and the page is the same for everyone."""

from __future__ import annotations

import json
from typing import Any

from rrotor import Ctx, Result

REPO = "glyphh-ai/glyphh"
FIELDS = "number,title,author,createdAt,url"


def issues(ctx: Ctx, inputs: dict[str, Any]) -> Result:
    limit = int(inputs.get("limit") or 50)
    args = ["issue", "list", "--repo", REPO, "--state", "open", "--limit", str(limit), "--json", FIELDS]
    # The key goes to gh for this command only, from the vault: a missing one fails the run naming GH_TOKEN.
    out = ctx.cli("gh", args, env={"GH_TOKEN": ctx.secrets["GH_TOKEN"]})
    if out.exit_code != 0:
        return Result.failed("list", out.stderr.strip() or f"gh exited {out.exit_code}")
    rows = [
        {
            "number": issue.get("number"),
            "title": issue.get("title"),
            "author": (issue.get("author") or {}).get("login"),
            "opened": str(issue.get("createdAt") or "")[:10],
            "url": issue.get("url"),
        }
        for issue in json.loads(out.stdout or "[]")
    ]
    ctx.log("listed", repo=REPO, open=len(rows))
    return Result.done({"repo": REPO, "total": len(rows), "issues": rows, "refreshed_at": str(ctx.today())})
