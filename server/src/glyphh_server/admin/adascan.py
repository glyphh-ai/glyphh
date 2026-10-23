"""Ada Cloud across every org, for staff: each org's models (name, when made, deleted or not, active version, the
precedents its active store holds) and its jobs of the last JOB_DAYS (kind, state, how long). Each org's schema lets
only a session set to that org read it (glyphh_ada/orgschema.py), so the scan sets each org in turn on the staff
transaction and leaves it again after; it reads counts, names and times only, never a spec, a case, a job's arguments
or its result. The whole scan is kept SCAN_TTL seconds in Redis, so pages shown again do not scan again."""

import json
import uuid
from datetime import datetime

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada.pg import org_of, schema_for
from glyphh_server.db import tenancy

SCAN_KEY: str = "ops:cache:adascan"
SCAN_TTL: int = 60
JOB_DAYS: int = 7
SCHEMAS: str = r"SELECT nspname FROM pg_namespace WHERE nspname ~ '^ada_[0-9a-f]{32}$' ORDER BY 1"
# A version's Ada version and kernel (docs/specs/ada-cloud.md, 12), read so that a schema without those columns yet
# answers null: only those two keys leave the database, never the version's spec or what it learned.
MODELS: str = """
    SELECT m.name, m.created_at, m.deleted_at IS NOT NULL AS deleted, m.active_version, {held} AS precedents,
        to_jsonb(v) ->> 'ada' AS ada, to_jsonb(v) ->> 'kernel' AS kernel
    FROM {s}.models m LEFT JOIN {s}.spec_versions v ON v.model_id = m.id AND v.version = m.active_version {join}
    ORDER BY m.created_at"""
COUNTS_JOIN: str = "LEFT JOIN {s}.counts c ON c.model = v.store"
JOBS: str = f"""
    SELECT kind, state, extract(epoch FROM finished_at - started_at)::float AS seconds, created_at FROM {{s}}.jobs
    WHERE created_at > now() - interval '{JOB_DAYS} days'"""


class AdaModel(BaseModel):
    name: str
    created_at: datetime
    deleted: bool
    active_version: int
    precedents: int
    ada: str | None = None  # its active version's Ada version; null before Ada versions
    kernel: str | None = None


class AdaJob(BaseModel):
    kind: str
    state: str
    seconds: float | None
    created_at: datetime


class OrgAda(BaseModel):
    org_id: uuid.UUID
    models: list[AdaModel]
    jobs: list[AdaJob]

    @property
    def live(self) -> list[AdaModel]:
        return [m for m in self.models if not m.deleted]

    @property
    def precedents(self) -> int:
        return sum(m.precedents for m in self.live)


async def _has(conn: AsyncConnection, table: str) -> bool:
    return (await conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": table})).scalar_one()


async def one(conn: AsyncConnection, org_id: uuid.UUID) -> OrgAda:
    """One org's models and jobs; none before its first model. The transaction is left set to no org."""
    s = f'"{schema_for(str(org_id))}"'
    await tenancy.enter(conn, org_id)
    try:
        if not await _has(conn, f"{s}.models"):
            return OrgAda(org_id=org_id, models=[], jobs=[])
        counted = await _has(conn, f"{s}.counts")
        query = MODELS.format(
            s=s, held="coalesce(c.n, 0)" if counted else "0", join=COUNTS_JOIN.format(s=s) if counted else ""
        )
        models = [AdaModel(**r._mapping) for r in await conn.execute(text(query))]
        jobs = [AdaJob(**r._mapping) for r in await conn.execute(text(JOBS.format(s=s)))]
        return OrgAda(org_id=org_id, models=models, jobs=jobs)
    finally:
        await tenancy.leave(conn)


async def scan(conn: AsyncConnection, redis: Redis) -> list[OrgAda]:
    """Every org with a schema, from Redis when scanned within SCAN_TTL seconds."""
    kept = await redis.get(SCAN_KEY)
    if kept is not None:
        return [OrgAda.model_validate(o) for o in json.loads(kept)]
    orgs = [uuid.UUID(org_of(name)) for name in (await conn.execute(text(SCHEMAS))).scalars()]
    found = [await one(conn, org) for org in orgs]
    await redis.set(SCAN_KEY, json.dumps([o.model_dump(mode="json") for o in found]), ex=SCAN_TTL)
    return found


def by_org(found: list[OrgAda]) -> dict[uuid.UUID, OrgAda]:
    return {o.org_id: o for o in found}
