"""deploy_failures: the page's one function. The page calls it at /apps/deploy_failures/call/failures as the person
viewing it; it reads GitHub's failed workflow runs since a date (yesterday a week ago by default) and counts them by
workflow. No connector, no claude.ai in the path: ctx.http to the one host the manifest declares."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from rrotor import Ctx, Result

REPO = "glyphh-ai/glyphh"
RUNS = f"https://api.github.com/repos/{REPO}/actions/runs"


def failures(ctx: Ctx, inputs: dict[str, Any]) -> Result:
    since = inputs.get("since") or str(date.fromisoformat(str(ctx.today())) - timedelta(days=7))
    params = {"status": "failure", "created": f">={since}", "per_page": 100}
    runs = ctx.http.get(RUNS, params=params).raise_for_status().json().get("workflow_runs", [])
    by_workflow: dict[str, int] = {}
    for run in runs:
        name = str(run.get("name") or "unnamed")
        by_workflow[name] = by_workflow.get(name, 0) + 1
    counted = sorted(({"workflow": k, "failures": v} for k, v in by_workflow.items()), key=lambda r: -r["failures"])
    ctx.log("counted", since=since, runs=len(runs))
    return Result.done({"since": since, "total": len(runs), "by_workflow": counted})
