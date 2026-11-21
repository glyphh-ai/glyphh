"""The hourly GitHub traffic pull against a fake GitHub: each day's views and clones kept beyond GitHub's 14 days and
replaced while GitHub still reports them, the popular referrers and paths kept under the day pulled, and the failures
that stop a repository's pull (a warning, never a crash; the other repositories go on)."""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import GitHubTrafficDay, GitHubTrafficRepo, GitHubTrafficTop
from glyphh_server.ops import tend
from glyphh_server.ops.github_traffic import GitHub, GitHubError
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.traffic import github
from tests.conftest import SETTINGS

TOKEN: str = "gh-test-token"
REPO: str = "glyphh-ai/glyphh"
NOW: datetime = datetime(2026, 10, 23, 12, tzinfo=UTC)
TODAY: date = NOW.date()


def _stamp(day: date) -> str:
    return f"{day}T00:00:00Z"


class FakeGitHub:
    """GitHub's traffic endpoints for each repository in `repos`; `scale` multiplies the counts, `status` answers every
    call, `refuse` one repository with a 404."""

    def __init__(self) -> None:
        self.repos: list[str] = [REPO]
        self.today: date = TODAY
        self.scale: int = 1
        self.status: int | None = None
        self.headers: dict[str, str] = {}
        self.refuse: str | None = None
        self.asked: list[str] = []

    def _days(self, single: str) -> dict[str, Any]:
        n = self.scale * (1 if single == "view" else 2)
        days = [self.today - timedelta(days=i) for i in range(2, -1, -1)]  # GitHub's last few days, oldest first
        entries = [{"timestamp": _stamp(d), "count": 10 * n, "uniques": 3 * n} for d in days]
        if single == "clone":
            entries = entries[1:]  # the oldest day had no clones: GitHub left it out
        return {"count": sum(e["count"] for e in entries), "uniques": 5 * n, f"{single}s": entries}

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        assert request.headers["x-github-api-version"] == "2022-11-28"
        self.asked.append(str(request.url))
        if self.status is not None:
            return httpx.Response(self.status, json={"message": "Bad credentials"}, headers=self.headers)
        path = request.url.path
        repo = path.removeprefix("/repos/").split("/traffic/")[0]
        if repo == self.refuse or repo not in self.repos:
            return httpx.Response(404, json={"message": "Not Found"})
        part = path.split("/traffic/")[1]
        if part in ("views", "clones"):
            assert request.url.params["per"] == "day"
            return httpx.Response(200, json=self._days(part[:-1]))
        if part == "popular/referrers":
            rows = [
                {"referrer": "Google", "count": 7 * self.scale, "uniques": 4},
                {"referrer": "glyphh.ai", "count": 9},
            ]
            return httpx.Response(200, json=rows[: 1 if self.scale > 1 else 2])
        return httpx.Response(200, json=[{"path": f"/{REPO}", "title": "glyphh", "count": 12, "uniques": 6}])


def _gh(fake: FakeGitHub) -> GitHub:
    return GitHub(httpx.AsyncClient(transport=httpx.MockTransport(fake.handle)), TOKEN)


@pytest.fixture
async def clean(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        for table in (GitHubTrafficRepo, GitHubTrafficDay, GitHubTrafficTop):
            await conn.execute(delete(table))
    yield


async def _kept(engine: AsyncEngine) -> tuple[dict[str, Any], dict[tuple[Any, ...], Any], dict[tuple[Any, ...], Any]]:
    async with engine.connect() as conn:
        repos = {r.repo: r for r in await conn.execute(select(GitHubTrafficRepo.__table__))}
        days = {(r.repo, r.day): r for r in await conn.execute(select(GitHubTrafficDay.__table__))}
        tops = {
            (r.repo, r.pulled_on, r.kind, r.key): (r.count, r.uniques)
            for r in await conn.execute(select(GitHubTrafficTop.__table__))
        }
    return repos, days, tops


async def test_a_pull_keeps_each_days_views_and_clones_and_the_popular_lists(engine: AsyncEngine, clean: None) -> None:
    fake = FakeGitHub()
    await github.pull(engine, _gh(fake), [REPO], NOW)
    repos, days, tops = await _kept(engine)
    r = repos[REPO]
    assert (r.pulled_at, r.views, r.view_uniques, r.clones, r.clone_uniques) == (NOW, 30, 5, 40, 10)
    oldest = days[(REPO, TODAY - timedelta(days=2))]
    assert (oldest.views, oldest.view_uniques, oldest.clones, oldest.clone_uniques) == (10, 3, 0, 0)
    t = days[(REPO, TODAY)]
    assert (t.views, t.view_uniques, t.clones, t.clone_uniques) == (10, 3, 20, 6)
    assert tops == {
        (REPO, TODAY, "referrer", "Google"): (7, 4),
        (REPO, TODAY, "referrer", "glyphh.ai"): (9, 0),
        (REPO, TODAY, "path", f"/{REPO}"): (12, 6),
    }


async def test_a_day_is_replaced_while_github_reports_it_and_kept_after(engine: AsyncEngine, clean: None) -> None:
    fake = FakeGitHub()
    await github.pull(engine, _gh(fake), [REPO], NOW)
    fake.scale, fake.today = 2, TODAY + timedelta(days=1)  # a day on: the oldest day has gone from GitHub's window
    await github.pull(engine, _gh(fake), [REPO], NOW)  # the same pull day: its lists replaced
    _, days, tops = await _kept(engine)
    assert days[(REPO, TODAY - timedelta(days=2))].views == 10  # GitHub no longer reports it: kept as it was
    assert days[(REPO, TODAY)].views == 20 and days[(REPO, TODAY + timedelta(days=1))].clones == 40
    assert tops == {(REPO, TODAY, "referrer", "Google"): (14, 4), (REPO, TODAY, "path", f"/{REPO}"): (12, 6)}
    await github.pull(engine, _gh(fake), [REPO], NOW + timedelta(days=1))
    assert len((await _kept(engine))[2]) == 4  # a new pull day keeps the day before's lists


async def test_a_refused_repository_is_a_warning_and_the_rest_go_on(
    engine: AsyncEngine, clean: None, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeGitHub()
    fake.repos.append("glyphh-ai/other")
    fake.refuse = "glyphh-ai/other"
    await github.pull(engine, _gh(fake), ["glyphh-ai/other", REPO], NOW)
    assert list((await _kept(engine))[0]) == [REPO]
    warned = [r for r in caplog.records if r.name == "glyphh.traffic" and r.levelno == logging.WARNING]
    assert warned[0].getMessage() == "github traffic pull failed: glyphh-ai/other: GitHub answered 404: Not Found"


@pytest.mark.parametrize(
    ("answer", "kind", "words"),
    [
        (httpx.Response(401, json={"message": "Bad credentials"}), "auth", "GitHub refused the token: Bad credentials"),
        (httpx.Response(403, json={"message": "Resource not accessible"}), "auth", "Resource not accessible"),
        (httpx.Response(403, json={}, headers={"x-ratelimit-remaining": "0"}), "rate", "GitHub's rate limit"),
        (httpx.Response(429, text="slow down"), "rate", "GitHub's rate limit"),
        (httpx.Response(502, text="<html>bad gateway</html>"), "refused", "GitHub answered 502: "),
        (httpx.Response(200, text="not json"), "refused", "GitHub answered 200: "),
        (httpx.Response(500, json=["not", "an", "object"]), "refused", "GitHub answered 500: "),
    ],
)
async def test_the_client_says_what_kind_of_failure_it_was(answer: httpx.Response, kind: str, words: str) -> None:
    gh = GitHub(httpx.AsyncClient(transport=httpx.MockTransport(lambda _: answer)), TOKEN)
    with pytest.raises(GitHubError) as raised:
        await gh.traffic(REPO, "views")
    assert raised.value.kind == kind and words in str(raised.value) and TOKEN not in str(raised.value)


async def test_github_unreachable_is_a_warning(
    engine: AsyncEngine, clean: None, caplog: pytest.LogCaptureFixture
) -> None:
    def down(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    await github.pull(engine, GitHub(httpx.AsyncClient(transport=httpx.MockTransport(down)), TOKEN), [REPO])
    assert "GitHub could not be reached (ConnectError)" in caplog.text
    assert (await _kept(engine))[0] == {}


async def test_an_empty_answer_keeps_the_totals_only(engine: AsyncEngine, clean: None) -> None:
    def empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[] if "popular" in request.url.path else {"count": 0, "uniques": 0})

    await github.pull(engine, GitHub(httpx.AsyncClient(transport=httpx.MockTransport(empty)), TOKEN), [REPO], NOW)
    repos, days, tops = await _kept(engine)
    assert repos[REPO].views == 0 and days == {} and tops == {}


async def test_the_pull_runs_once_an_hour_from_the_tick(engine: AsyncEngine, clean: None, redis: Redis) -> None:
    await redis.delete(github.KEY)
    fake = FakeGitHub()
    gh = _gh(fake)
    settings = SETTINGS.model_copy(update={"github_traffic_repos": f" {REPO}, "})
    assert await tend.tend(engine, Hub(redis), settings, 60, None, None, gh)
    asked = len(fake.asked)
    assert asked == 4 and list((await _kept(engine))[0]) == [REPO]
    assert not await github.hourly(engine, redis, gh, [REPO])
    assert len(fake.asked) == asked and 0 < await redis.ttl(github.KEY) <= github.EVERY
    await redis.delete(github.KEY)


def test_the_repositories_are_comma_separated() -> None:
    assert github.repos("glyphh-ai/glyphh, glyphh-ai/server,,") == ["glyphh-ai/glyphh", "glyphh-ai/server"]
    assert github.repos("") == []
