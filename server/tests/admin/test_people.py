"""People, plans, sign-ups by source and the audit log, for staff."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.admin import audit
from glyphh_server.models import ConnectorGrant, Identity, Org, User
from tests.admin.conftest import Admin
from tests.db.helpers import granted, member, other_client, person, subscribed


async def test_people_are_searched_and_show_how_and_when_they_sign_in(admin: Admin, engine: AsyncEngine) -> None:
    tag = uuid.uuid4().hex[:8]
    ada = await person(engine, email=f"{tag}-ada@people.test")
    grace = await member(engine, ada.org_id, f"{tag}-grace@people.test")
    seen = datetime.now(UTC) - timedelta(hours=1)
    async with engine.begin() as conn:
        await conn.execute(insert(Identity).values(user_id=ada.user_id, provider="google", provider_user_id=tag))
        await conn.execute(insert(Identity).values(user_id=ada.user_id, provider="github", provider_user_id=tag))
        await conn.execute(update(ConnectorGrant).where(ConnectorGrant.id == ada.grant_id).values(last_used_at=seen))
    found = (await admin.get("/users", q=tag)).json()
    rows = {p["email"]: p for p in found["people"]}
    assert found["total"] == 2 and list(rows) == [grace.email, ada.email]  # the newest first
    assert rows[ada.email]["providers"] == ["github", "google"] and rows[grace.email]["providers"] == []
    assert rows[ada.email]["last_seen_at"] is not None and rows[grace.email]["last_seen_at"] is None
    assert rows[ada.email]["org_id"] == str(ada.org_id) and rows[ada.email]["role"] == "admin"
    assert (rows[grace.email]["role"], rows[grace.email]["name"]) == ("member", "Grace Hopper")
    assert [p["email"] for p in (await admin.get("/users", q=tag, provider="github")).json()["people"]] == [ada.email]
    assert [
        p["email"] for p in (await admin.get("/users", q="grace hop", org_id=str(ada.org_id))).json()["people"]
    ] == [grace.email]  # by name too
    assert (await admin.get("/users", org_id=str(ada.org_id))).json()["total"] == 2
    page = (await admin.get("/users", limit=1, offset=1)).json()
    assert (len(page["people"]), page["limit"], page["offset"]) == (1, 1, 1) and page["total"] >= 3
    assert (await admin.get("/users", provider="okta")).status_code == 422


async def test_a_person_was_last_seen_at_the_newest_use_of_any_sign_in(admin: Admin, engine: AsyncEngine) -> None:
    tag = uuid.uuid4().hex[:8]
    ada = await person(engine, email=f"{tag}@people.test")
    older, _ = await granted(engine, ada, client_id=await other_client(engine))
    newest = datetime.now(UTC) - timedelta(minutes=5)
    async with engine.begin() as conn:
        grant = update(ConnectorGrant)
        await conn.execute(grant.where(ConnectorGrant.id == older).values(last_used_at=newest - timedelta(days=9)))
        await conn.execute(grant.where(ConnectorGrant.id == ada.grant_id).values(last_used_at=newest))
    [row] = (await admin.get("/users", q=tag)).json()["people"]
    assert datetime.fromisoformat(row["last_seen_at"]) == newest


async def test_every_plan_version_with_its_orgs(admin: Admin, engine: AsyncEngine) -> None:
    await person(engine, "Team")
    plans = {p["name"]: p for p in (await admin.get("/plans")).json()}
    assert list(plans)[:5] == ["Free", "Basic", "Pro", "Team", "Enterprise"]  # as they were sold, in their order
    team = plans["Team"]
    assert team["orgs"] >= 1 and team["active"] and team["versions"][0]["newest"]
    assert (team["versions"][0]["price_cents"], team["versions"][0]["billing_interval"]) == (29_900, "month")
    assert sum(v["orgs"] for v in team["versions"]) == team["orgs"]
    assert all(not v["newest"] for v in team["versions"][1:])
    assert plans["Enterprise"]["versions"][0]["price_cents"] is None and plans["Enterprise"]["versions"][0]["sso"]


async def test_sign_ups_and_conversions_by_source(admin: Admin, engine: AsyncEngine) -> None:
    campaign = f"c{uuid.uuid4().hex[:8]}"
    tagged = {"utm_source": "reddit", "utm_medium": "cpc", "utm_campaign": campaign}
    paid, free = await person(engine, "Pro"), await person(engine)
    clicked = await person(engine)
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id.in_([paid.org_id, free.org_id])).values(source=tagged))
        await conn.execute(update(User).where(User.id.in_([paid.user_id, free.user_id])).values(source=tagged))
        await conn.execute(update(Org).where(Org.id == paid.org_id).values(first_paid_at=datetime.now(UTC)))
        click = {"gclid": "g1", "utm_campaign": campaign}
        await conn.execute(update(Org).where(Org.id == clicked.org_id).values(source=click))
        joined = {"fbclid": "f1", "utm_campaign": campaign}  # an invited person: their own tags, another's org
        await conn.execute(update(User).where(User.id == clicked.user_id).values(source=joined))
    await subscribed(engine, paid.org_id, f"sub_{paid.org_id.hex}", f"cus_{paid.org_id.hex}")
    rows = [r for r in (await admin.get("/marketing", days=30)).json() if r["campaign"] == campaign]
    assert rows == [
        {"source": "reddit", "medium": "cpc", "campaign": campaign, "people": 2, "orgs": 2, "paid": 1, "paying": 1},
        {"source": "google", "medium": "(none)", "campaign": campaign, "people": 0, "orgs": 1, "paid": 0, "paying": 0},
        {"source": "meta", "medium": "(none)", "campaign": campaign, "people": 1, "orgs": 0, "paid": 0, "paying": 0},
    ]
    untagged = [r for r in (await admin.get("/marketing")).json() if r["source"] == "(none)"]
    assert untagged and untagged[0]["orgs"] >= 1 and untagged[0]["people"] >= 1
    assert (await admin.get("/marketing", days=0)).status_code == 422


async def test_the_audit_log_is_filtered_and_paged(admin: Admin, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "PAGE", 2)
    org = admin.staff.org_id
    for _ in range(3):
        await admin.get(f"/orgs/{org}")
    first = (await admin.get("/audit", by=admin.staff.email.upper(), org_id=str(org), action="adminOrg")).json()
    assert len(first["entries"]) == 2 and first["next_before"]
    assert all((e["action"], e["org_id"], e["outcome"]) == ("adminOrg", str(org), "ok") for e in first["entries"])
    rest = (await admin.get("/audit", by=admin.staff.email, action="adminOrg", before=first["next_before"])).json()
    assert len(rest["entries"]) == 1 and rest["next_before"] is None
    newest = (await admin.get("/audit")).json()["entries"][0]
    assert (newest["action"], newest["staff_email"]) == ("adminAudit", admin.staff.email)  # this very look
    assert (await admin.get("/audit", by="nobody@glyphh.test")).json() == {"entries": [], "next_before": None}
