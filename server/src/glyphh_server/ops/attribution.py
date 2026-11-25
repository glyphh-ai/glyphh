"""Where a sign-up came from: the tags of the link a visitor arrived at glyphh.ai on (utm_*, an ad's click id, the page
they landed on), which the website keeps 90 days in its first-party cookie `glyphh_src` on .glyphh.ai (web
middleware.js). The platform reads that cookie when a sign-in finishes and sends its tags here (POST /v1/me/source);
they are kept on the person, and on their org when they made it, once, and only within FRESH of the account being
made: a sign-up's source, never a later visit's. Staff see sign-ups and paid conversions by them
(admin/marketing.py)."""

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Org, User
from glyphh_server.ops.auth.principal import Principal

FRESH: timedelta = timedelta(days=1)


def _tag() -> str | None:
    return Field(None, max_length=200)  # type: ignore[no-any-return]


class Source(BaseModel):
    """The cookie's tags as the website wrote them; anything else in it is ignored."""

    model_config = ConfigDict(extra="ignore")

    utm_source: str | None = _tag()
    utm_medium: str | None = _tag()
    utm_campaign: str | None = _tag()
    utm_content: str | None = _tag()
    utm_term: str | None = _tag()
    fbclid: str | None = _tag()
    rdt_cid: str | None = _tag()
    gclid: str | None = _tag()
    landing: str | None = _tag()


class Stored(BaseModel):
    stored: bool = Field(description="Kept on the person: their account is new and had no source yet")


async def store(conn: AsyncConnection, who: Principal, source: Source) -> Stored:
    tags = {k: v.strip() for k, v in source.model_dump(exclude_none=True).items() if v.strip()}
    if not tags:
        return Stored(stored=False)
    fresh = func.now() - FRESH
    person = update(User).where(User.id == who.user_id, User.source.is_(None), User.created_at > fresh)
    if (await conn.execute(person.values(source=tags).returning(User.id))).first() is None:
        return Stored(stored=False)
    made = (Org.id == who.org_id, Org.admin_user_id == who.user_id, Org.source.is_(None), Org.created_at > fresh)
    await conn.execute(update(Org).where(*made).values(source=tags))  # the org they made as they signed up
    return Stored(stored=True)
