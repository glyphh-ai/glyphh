"""The real thing for the bot that started it (docs/specs/bot-agent-loop.md, 1): PR Review Digest, installed from
its template, on the live Claude Agent SDK. "Hi there" gets words and no tool; "what needs my review?" searches
GitHub, and the pull requests found go through Ada before anything is posted. GitHub, Slack (Pipedream) and Ada are
the tests' fakes. It runs only when LIVE_ANTHROPIC_KEY is set (never in CI):
`LIVE_ANTHROPIC_KEY=... pytest tests/bots/test_live_digest.py -o addopts="" -s`."""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.bots import programs
from tests.bots.conftest import BOTS, Served, answered, ran, serve
from tests.bots.fakes import CONNECT, FakePipedream
from tests.bots.market import installed, linked
from tests.bots.test_live import KEY, Watched, said
from tests.db.helpers import Person

SEARCH: str = "github-search-issues-and-pull-requests"
POST: str = "slack-send-message"
REPOS: str = "https://api.github.com/repos/acme"
PULLS: list[dict[str, Any]] = [
    {
        "id": 101,
        "title": "Fix the release build on arm64",
        "repository_url": f"{REPOS}/api",
        "user": {"login": "grace"},
        "html_url": "https://github.com/acme/api/pull/7",
        "created_at": "2026-11-20T09:00:00Z",
    },
    {
        "id": 102,
        "title": "Tidy the README",
        "repository_url": f"{REPOS}/docs",
        "user": {"login": "alan"},
        "html_url": "https://github.com/acme/docs/pull/3",
        "created_at": "2026-11-22T09:00:00Z",
    },
]
COMPONENTS: dict[str, dict[str, Any]] = {
    SEARCH: {
        "key": SEARCH,
        "name": "Search Issues and Pull Requests",
        "description": "Find issues and pull requests by a GitHub search query",
        "annotations": {"readOnlyHint": True},
        "configurable_props": [
            {"name": "github", "type": "app", "app": "github"},
            {"name": "query", "type": "string", "label": "Query", "description": "A GitHub search query"},
        ],
    },
    POST: {
        "key": POST,
        "name": "Send Message",
        "description": "Send a message to a user or channel",
        "configurable_props": [
            {"name": "slack", "type": "app", "app": "slack"},
            {"name": "conversation", "type": "string", "label": "Channel or user"},
            {"name": "text", "type": "string", "label": "Text"},
        ],
    },
}
pytestmark = pytest.mark.skipif(not KEY, reason="LIVE_ANTHROPIC_KEY is not set: no live check")


class GitHubAndSlack(FakePipedream):
    """Pipedream with GitHub's search (two pull requests wait on review) and Slack's message."""

    def _connect(self, method: str, path: str, body: Any, query: dict[str, str]) -> httpx.Response:
        if method == "GET" and path.startswith(f"{CONNECT}/components/"):
            return httpx.Response(200, json={"data": COMPONENTS[path.rsplit("/", 1)[1]]})
        if (method, path) == ("GET", f"{CONNECT}/actions"):
            return httpx.Response(200, json={"data": [c for k, c in COMPONENTS.items() if k.startswith(query["app"])]})
        if (method, path) == ("POST", f"{CONNECT}/actions/run"):
            self.runs.append(body)
            ret: Any = {"total_count": len(PULLS), "items": PULLS} if body["id"] == SEARCH else {"ok": True}
            return httpx.Response(200, json={"exports": {"$summary": "Done"}, "ret": ret})
        return super()._connect(method, path, body, query)


@pytest.fixture
async def live(engine: AsyncEngine) -> AsyncIterator[tuple[Served, Watched]]:
    async for s in serve(BOTS.model_copy(update={"anthropic_api_key": KEY}), GitHubAndSlack()):
        watched = Watched()
        s.app.state.bots.agent = watched
        yield s, watched


async def test_pr_review_digest_talks_then_searches_through_ada(live: tuple[Served, Watched], ana: Person) -> None:
    s, watched = live
    await linked(s, ana, "github", "slack")
    bot = await installed(s, ana, "pr-review-digest")
    gate = f"bot-{bot['slug']}-gate-today"
    s.ada.rule[gate] = lambda case: ("today", 0.4)  # not sure of either: Ada asks the person

    hello = await ran(s, ana, bot["slug"], "Hi there")
    print("\nHI THERE ->", said(hello), "\n", hello["output"], "\nthe session's tools:", watched.goes[0][1].tools)
    assert hello["status"] == "done" and hello["output"].strip(), hello
    assert hello["steps"] == [] and s.pd.runs == [], "a greeting used a tool"
    assert all(t.startswith("mcp__bot__") or t == "Skill" for t in watched.goes[0][1].tools)

    run = await ran(s, ana, bot["slug"], "what needs my review?")
    asked: list[str] = []
    for _ in range(6):
        if run["status"] != "needs_input":
            break
        q = run["question"]
        asked.append("approval" if q["approval"] else "decision")
        print("ASKED ->", q["question"], "|", q.get("detail") or [b["label"] for b in q["batch"]])
        run = await answered(s, ana, run["id"], "yes" if q["approval"] else "rest=today")
    print("REVIEW ->", said(run), "\n", run["output"], "\nsteps:", [(x["title"], x["ok"]) for x in run["steps"]])
    print("asked:", asked, "| pipedream runs:", [(r["id"], r.get("configured_props")) for r in s.pd.runs])
    searched = [r for r in s.pd.runs if r["id"] == SEARCH]
    assert searched, "it did not search GitHub"
    assert "decision" in asked, asked  # Ada was asked about the pull requests, and asked the person
    assert s.ada.outcomes(gate)[-1] == "today"  # the person's answer was learned
    assert run["status"] == "done" and run["output"].strip(), run


async def test_the_templates_program_runs_end_to_end(live: tuple[Served, Watched], ana: Person) -> None:
    """PR Review Digest's program.py, walked by the server with the real agent doing its bot steps: the digest
    written, the person asked before it is posted, then posted; every step on the run's audit trail."""
    s, _ = live
    await linked(s, ana, "github", "slack")
    bot = await installed(s, ana, "pr-review-digest")
    s.ada.rule[f"bot-{bot['slug']}-gate-today"] = lambda case: ("today", 0.95)  # Ada is sure: nothing to ask
    (program,) = (await s.http.get("/v1/programs", headers=ana.headers)).json()["programs"]
    run = await programs.ran(s, ana, program["slug"], "")
    asked: list[str] = []
    for _ in range(8):
        if run["status"] != "needs_input":
            break
        q = run["question"]
        asked.append(q["kind"])
        print("\nASKED ->", q["kind"], "|", q["question"][:400])
        answer = "Post" if q["kind"] == "ask" else "yes" if q.get("approval") else "rest=today"
        run = await programs.answered(s, ana, run["id"], answer)
    trail = await programs.trail(s, ana, run["id"])
    print("PROGRAM ->", run["status"], run["error"], "\nposted:", run["outputs"].get("post"), "\ntrail:", trail)
    assert run["status"] == "done", run
    assert "ask" in asked and [r["id"] for r in s.pd.runs if r["id"] == POST], (asked, s.pd.runs)
    assert [t[:3] for t in trail if t[0] == "step"] == [
        ("step", "digest", bot["slug"]),
        ("step", "post", bot["slug"]),
    ]
