"""The plans a new Glyphh database starts with, as the products sold them until they were retired (2026-11-18): each
plan with one version, in PLANS' order. Nothing sells them any more: they are kept because every org is on a plan
version (a new person's org on Free's; an org whose subscription ends goes back to it) and the staff view lists
them. A database that has a plan's versions already (production) is left exactly as it is: its versions carry the
Stripe prices the webhook knows a subscription's plan by."""

from dataclasses import asdict, dataclass

from sqlalchemy import func, insert, select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Plan, PlanVersion

FREE: str = "Free"


@dataclass(frozen=True, slots=True)
class PlanSeed:
    name: str
    price_cents: int | None
    billing_interval: str | None
    self_serve: bool
    max_machines: int | None
    precedents: int | None
    sync: bool = False
    ha: bool = False
    offline: bool = False
    sso: bool = False
    cloud_precedents: int | None = None
    cloud_requests: int | None = None
    cloud_rps: int | None = None
    cloud_overage: bool = False
    llm_tokens: int | None = None


def _cloud(precedents: int, requests: int, rps: int, overage: bool, llm_tokens: int) -> dict[str, int | bool]:
    limits = {"cloud_precedents": precedents, "cloud_requests": requests, "cloud_rps": rps}
    return {**limits, "cloud_overage": overage, "llm_tokens": llm_tokens}


PLANS: tuple[PlanSeed, ...] = (
    PlanSeed(FREE, 0, None, True, 1, 5_000, **_cloud(1_000, 5_000, 5, False, 250_000)),
    PlanSeed("Basic", 2_000, "month", True, 1, 5_000, **_cloud(10_000, 50_000, 10, True, 5_000_000)),
    PlanSeed("Pro", 9_900, "month", True, 3, 50_000, sync=True, **_cloud(100_000, 1_000_000, 50, True, 25_000_000)),
    PlanSeed("Team", 29_900, "month", True, 10, 500_000, sync=True, **_cloud(1_000_000, 5_000_000, 200, True, 10**8)),
    PlanSeed("Enterprise", None, "year", False, None, None, sync=True, ha=True, offline=True, sso=True),
)


async def seed_plans(conn: AsyncConnection) -> None:
    for sort, seed in enumerate(PLANS):
        await conn.execute(
            upsert(Plan)
            .values(name=seed.name, sort=sort)
            .on_conflict_do_update(index_elements=[Plan.name], set_={"sort": sort})
        )
        plan_id = (await conn.execute(select(Plan.id).where(Plan.name == seed.name))).scalar_one()
        held = select(func.count()).select_from(PlanVersion).where(PlanVersion.plan_id == plan_id)
        if (await conn.execute(held)).scalar_one() == 0:
            values = {k: v for k, v in asdict(seed).items() if k != "name"}
            await conn.execute(insert(PlanVersion).values(plan_id=plan_id, version=1, **values))
