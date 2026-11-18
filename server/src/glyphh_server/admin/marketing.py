"""Sign-ups and paid conversions by where they came from (the campaign tags kept at sign-up, while there were
sign-ups): orgs made in the last `days` days, grouped by their sign-up's utm_source (else the ad click id it
carried: google, meta, reddit), utm_medium and
utm_campaign; untagged ones as `(none)`. People are counted by their own tags (an invited person joins another org)."""

from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Text, case, func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.admin.money import PAYING
from glyphh_server.models import Org, User

NONE: Any = literal_column("'(none)'", Text)  # inline, not a parameter: the same expression in GROUP BY
BY_POSITION = (text("1"), text("2"), text("3"))


class SourceRow(BaseModel):
    source: str
    medium: str
    campaign: str
    people: int = Field(description="People who signed up")
    orgs: int = Field(description="Orgs made")
    paid: int = Field(description="Of those orgs, how many have paid")
    paying: int = Field(description="Of those orgs, how many pay now")


def _source(tags: Any) -> Any:
    clicked = case(
        (tags.has_key("gclid"), literal_column("'google'", Text)),
        (tags.has_key("fbclid"), literal_column("'meta'", Text)),
        (tags.has_key("rdt_cid"), literal_column("'reddit'", Text)),
        else_=None,
    )
    return func.coalesce(tags["utm_source"].astext, clicked, NONE)


def _tag(tags: Any, name: str) -> Any:
    return func.coalesce(tags[name].astext, NONE)


async def sources(conn: AsyncConnection, days: int) -> list[SourceRow]:
    since = func.now() - timedelta(days=days)
    keys = (_source(Org.source), _tag(Org.source, "utm_medium"), _tag(Org.source, "utm_campaign"))
    paying = Org.billing_status.in_(PAYING)
    orgs = select(*keys, func.count(), func.count().filter(Org.first_paid_at.is_not(None)), func.count().filter(paying))
    rows: dict[tuple[str, str, str], dict[str, int]] = {}
    for s, m, c, n, paid, now in await conn.execute(orgs.where(Org.created_at >= since).group_by(*BY_POSITION)):
        rows[(s, m, c)] = {"orgs": n, "paid": paid, "paying": now}
    who = (_source(User.source), _tag(User.source, "utm_medium"), _tag(User.source, "utm_campaign"))
    people = select(*who, func.count()).where(User.created_at >= since).group_by(*BY_POSITION)
    for s, m, c, n in await conn.execute(people):
        rows.setdefault((s, m, c), {"orgs": 0, "paid": 0, "paying": 0})["people"] = n
    found = [
        SourceRow(
            source=s,
            medium=m,
            campaign=c,
            people=v.get("people", 0),
            orgs=v["orgs"],
            paid=v["paid"],
            paying=v["paying"],
        )
        for (s, m, c), v in rows.items()
    ]
    return sorted(found, key=lambda r: (-r.orgs, -r.people, r.source, r.medium, r.campaign))
