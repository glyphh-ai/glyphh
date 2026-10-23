"""Glyphh's public repositories' traffic for staff, from what the hourly GitHub pull kept (ops/traffic/github.py), never
GitHub itself: each repository's last 14 days as GitHub counts them (views and unique visitors, clones and unique
cloners), the same added up day by day since tracking began, its days since then (at most a year, for a sparkline),
and its popular referrers and paths as the latest pull found them."""

from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import GitHubTrafficDay, GitHubTrafficRepo, GitHubTrafficTop

HISTORY: int = 366  # the most days of a repository's series


class GitHubCounts(BaseModel):
    views: int = 0
    view_uniques: int = 0
    clones: int = 0
    clone_uniques: int = 0


class GitHubDay(GitHubCounts):
    day: date


class GitHubTop(BaseModel):
    key: str
    count: int
    uniques: int


class GitHubRepo(BaseModel):
    name: str
    pulled_at: datetime
    last_14: GitHubCounts
    total: GitHubCounts
    since: date | None
    series: list[GitHubDay]
    referrers: list[GitHubTop]
    paths: list[GitHubTop]


class GitHubTraffic(BaseModel):
    connected: bool
    repos: list[GitHubRepo]


COUNTS: tuple[str, ...] = tuple(GitHubCounts.model_fields)


def _counts(row: Any) -> GitHubCounts:
    return GitHubCounts(**{c: int(getattr(row, c) or 0) for c in COUNTS})


async def _repo(conn: AsyncConnection, r: Any, today: date) -> GitHubRepo:
    days = GitHubTrafficDay
    total = (
        await conn.execute(
            select(func.min(days.day).label("since"), *(func.sum(getattr(days, c)).label(c) for c in COUNTS)).where(
                days.repo == r.repo
            )
        )
    ).one()
    start = max(total.since or today, today - timedelta(days=HISTORY - 1))
    kept = {d.day: d for d in await conn.execute(select(days.__table__).where(days.repo == r.repo, days.day >= start))}
    series = [
        GitHubDay(day=d, **(_counts(kept[d]).model_dump() if d in kept else {}))
        for d in (start + timedelta(days=i) for i in range((today - start).days + 1))
    ]
    tops = GitHubTrafficTop
    latest = select(func.max(tops.pulled_on)).where(tops.repo == r.repo).scalar_subquery()
    rows = await conn.execute(
        select(tops.kind, tops.key, tops.count, tops.uniques)
        .where(tops.repo == r.repo, tops.pulled_on == latest)
        .order_by(tops.count.desc(), tops.key)
    )
    found: dict[str, list[GitHubTop]] = {"referrer": [], "path": []}
    for kind, key, count, uniques in rows:
        found.setdefault(kind, []).append(GitHubTop(key=key, count=int(count), uniques=int(uniques)))
    return GitHubRepo(
        name=r.repo,
        pulled_at=r.pulled_at,
        last_14=_counts(r),
        total=_counts(total),
        since=total.since,
        series=series,
        referrers=found["referrer"],
        paths=found["path"],
    )


async def github_traffic(conn: AsyncConnection, connected: bool, today: date) -> GitHubTraffic:
    listed = await conn.execute(select(GitHubTrafficRepo.__table__).order_by(GitHubTrafficRepo.repo))
    return GitHubTraffic(connected=connected, repos=[await _repo(conn, r, today) for r in list(listed)])
