"""The hourly GitHub traffic pull, a part of the minute tick (ops/tend.py) with GLYPHH_GITHUB_TRAFFIC_TOKEN set: for
each repository in GLYPHH_GITHUB_TRAFFIC_REPOS, its views and clones by day (count and unique visitors or cloners) and
its popular referrers and paths (GitHub's 14-day totals). GitHub keeps only the last 14 days, so each day is kept here
beyond them: a day's numbers are replaced while GitHub still reports it. The referrers and paths are kept under the
day they were pulled, replaced by a later pull that day. A repository whose pull fails (GitHub unreachable, the token
refused, its rate limit) is a warning, so an ops event, and nothing of it is written; the others go on. Once an hour
across every process: a Redis key says one has begun."""

import logging
from datetime import UTC, date, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.models import GitHubTrafficDay, GitHubTrafficRepo, GitHubTrafficTop
from glyphh_server.obs.logs import fields
from glyphh_server.ops.github_traffic import GitHub, GitHubError

log = logging.getLogger("glyphh.traffic")

KEY: str = "traffic:github:pulled"
EVERY: int = 3600
COUNTS: tuple[str, ...] = ("views", "view_uniques", "clones", "clone_uniques")
TOPS: dict[str, str] = {"popular/referrers": "referrer", "popular/paths": "path"}


def repos(listed: str) -> list[str]:
    """GLYPHH_GITHUB_TRAFFIC_REPOS, comma-separated owner/name."""
    return [r.strip() for r in listed.split(",") if r.strip()]


async def hourly(engine: AsyncEngine, redis: Redis, gh: GitHub, listed: list[str], now: datetime | None = None) -> bool:
    """The pull, if no process has begun one this hour: answers whether it ran."""
    if not await redis.set(KEY, "1", nx=True, ex=EVERY):
        return False
    await pull(engine, gh, listed, now)
    return True


async def pull(engine: AsyncEngine, gh: GitHub, listed: list[str], now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    for repo in listed:
        try:
            found = {part: await gh.traffic(repo, part) for part in ("views", "clones", *TOPS)}
        except GitHubError as err:
            log.warning("github traffic pull failed: %s: %s", repo, err, extra=fields(kind=err.kind))
            continue
        async with engine.begin() as conn:
            await _write(conn, repo, found, now)


def _days(found: dict[str, Any]) -> dict[date, dict[str, int]]:
    """Each day either list reports, with all four numbers: one the other list leaves out is none."""
    days: dict[date, dict[str, int]] = {}
    for part, single in (("views", "view"), ("clones", "clone")):
        for entry in found[part].get(part) or []:
            day = datetime.fromisoformat(str(entry["timestamp"]).replace("Z", "+00:00")).date()
            got = days.setdefault(day, dict.fromkeys(COUNTS, 0))
            got[part], got[f"{single}_uniques"] = int(entry.get("count") or 0), int(entry.get("uniques") or 0)
    return days


async def _write(conn: AsyncConnection, repo: str, found: dict[str, Any], now: datetime) -> None:
    views, clones = found["views"], found["clones"]
    totals = {
        "views": int(views.get("count") or 0),
        "view_uniques": int(views.get("uniques") or 0),
        "clones": int(clones.get("count") or 0),
        "clone_uniques": int(clones.get("uniques") or 0),
    }
    row = insert(GitHubTrafficRepo).values(repo=repo, pulled_at=now, **totals)
    await conn.execute(row.on_conflict_do_update(index_elements=["repo"], set_={"pulled_at": now, **totals}))
    days = [{"repo": repo, "day": d, **counts} for d, counts in sorted(_days(found).items())]
    if days:
        stmt = insert(GitHubTrafficDay).values(days)
        set_ = {c: stmt.excluded[c] for c in COUNTS}
        await conn.execute(stmt.on_conflict_do_update(index_elements=["repo", "day"], set_=set_))
    today = now.date()
    await conn.execute(
        delete(GitHubTrafficTop).where(GitHubTrafficTop.repo == repo, GitHubTrafficTop.pulled_on == today)
    )
    tops = [
        {
            "repo": repo,
            "pulled_on": today,
            "kind": kind,
            "key": str(entry.get("referrer") or entry.get("path") or ""),
            "count": int(entry.get("count") or 0),
            "uniques": int(entry.get("uniques") or 0),
        }
        for part, kind in TOPS.items()
        for entry in found[part] or []
    ]
    if tops:
        await conn.execute(insert(GitHubTrafficTop).values(tops).on_conflict_do_nothing())
