"""People, plans, sign-ups by source, models by Ada version and the audit log, for staff; and a sign-up's source,
kept from the website's cookie on a new account only."""

import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.admin import adascan
from glyphh_server.admin.ada_versions import by_version
from glyphh_server.models import ConnectorGrant, Identity, Install, Org, User
from tests.admin.ada import ada_org
from tests.admin.conftest import Admin
from tests.db.helpers import member, org_row, person, subscribed


async def test_people_are_searched_and_show_how_and_when_they_sign_in(admin: Admin, engine: AsyncEngine) -> None:
    tag = uuid.uuid4().hex[:8]
    ada = await person(engine, email=f"{tag}-ada@people.test")
    grace = await member(engine, ada.org_id, f"{tag}-grace@people.test")
    seen = datetime.now(UTC) - timedelta(hours=1)
    async with engine.begin() as conn:
        await conn.execute(insert(Identity).values(user_id=ada.user_id, provider="google", provider_user_id=tag))
        await conn.execute(insert(Identity).values(user_id=ada.user_id, provider="github", provider_user_id=tag))
        await conn.execute(update(Install).where(Install.user_id == ada.user_id).values(last_seen_at=seen))
    found = (await admin.get("/users", q=tag)).json()
    rows = {p["email"]: p for p in found["people"]}
    assert found["total"] == 2
    assert rows[ada.email]["providers"] == ["github", "google"] and rows[grace.email]["providers"] == []
    assert rows[ada.email]["last_seen_at"] is not None and rows[grace.email]["last_seen_at"] is None
    assert rows[ada.email]["org_id"] == str(ada.org_id) and rows[ada.email]["role"] == "admin"
    assert [p["email"] for p in (await admin.get("/users", q=tag, provider="github")).json()["people"]] == [ada.email]
    assert (await admin.get("/users", org_id=str(ada.org_id))).json()["total"] == 2
    assert len((await admin.get("/users", limit=1)).json()["people"]) == 1


async def test_every_plan_version_with_its_orgs(admin: Admin, engine: AsyncEngine) -> None:
    await person(engine, "Team")
    plans = {p["name"]: p for p in (await admin.get("/plans")).json()}
    assert {"Free", "Basic", "Pro", "Team", "Enterprise"} <= set(plans)
    team = plans["Team"]
    assert team["orgs"] >= 1 and team["versions"][0]["newest"] and team["versions"][0]["stripe_price_id"]
    assert sum(v["orgs"] for v in team["versions"]) == team["orgs"]
    assert all(not v["newest"] for v in team["versions"][1:])


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
    await subscribed(engine, paid.org_id, f"sub_{paid.org_id.hex}", f"cus_{paid.org_id.hex}")
    rows = [r for r in (await admin.get("/marketing", days=30)).json() if r["campaign"] == campaign]
    assert rows == [
        {"source": "reddit", "medium": "cpc", "campaign": campaign, "people": 2, "orgs": 2, "paid": 1, "paying": 1},
        {"source": "google", "medium": "(none)", "campaign": campaign, "people": 0, "orgs": 1, "paid": 0, "paying": 0},
    ]
    untagged = [r for r in (await admin.get("/marketing")).json() if r["source"] == "(none)"]
    assert untagged and untagged[0]["orgs"] >= 1


async def test_models_by_ada_version(admin: Admin, engine: AsyncEngine, redis: Redis) -> None:
    old, new = await person(engine), await person(engine)
    ada_org(old.org_id, [{"name": "early", "precedents": 5}])
    ada_org(new.org_id, [{"name": "a", "precedents": 2, "ada": "ada-1-1-beta", "kernel": "3.13.0"}])
    await redis.delete(adascan.SCAN_KEY)
    body = (await admin.get("/ada-versions")).json()
    shown = {v["ada"]: v for v in body["versions"]}
    assert body["versioned"] is True
    assert shown["ada-1-1-beta"] == {
        "ada": "ada-1-1-beta",
        "kernels": ["3.13.0"],
        "models": 1,
        "orgs": 1,
        "precedents": 2,
    }
    assert body["versions"][-1]["ada"] is None and shown[None]["models"] >= 1
    assert by_version([]).model_dump() == {"versioned": False, "versions": []}


async def test_the_audit_log_is_filtered_and_paged(admin: Admin, monkeypatch: object) -> None:
    from glyphh_server.admin import audit

    monkeypatch.setattr(audit, "PAGE", 2)  # type: ignore[attr-defined]
    org = admin.staff.org_id
    for _ in range(3):
        await admin.get(f"/orgs/{org}")
    first = (await admin.get("/audit", by=admin.staff.email.upper(), org_id=str(org), action="adminOrg")).json()
    assert len(first["entries"]) == 2 and first["next_before"]
    rest = (await admin.get("/audit", by=admin.staff.email, action="adminOrg", before=first["next_before"])).json()
    assert len(rest["entries"]) == 1 and rest["next_before"] is None
    assert (await admin.get("/audit")).status_code == 200


async def test_a_new_account_keeps_its_source_once(admin: Admin, engine: AsyncEngine) -> None:
    ada = await person(engine)
    tags = {"utm_source": "reddit", "utm_campaign": "launch", "landing": "/code", "rdt_cid": "r1", "junk": "x"}
    kept = await admin.http.post("/v1/me/source", json=tags, headers=ada.headers)
    assert kept.json() == {"stored": True}
    again = await admin.http.post("/v1/me/source", json={"utm_source": "google"}, headers=ada.headers)
    assert again.json() == {"stored": False}
    row = await org_row(engine, ada.org_id)
    assert row.source == {"utm_source": "reddit", "utm_campaign": "launch", "landing": "/code", "rdt_cid": "r1"}
    assert (await admin.http.post("/v1/me/source", json={"utm_source": "  "}, headers=ada.headers)).json() == {
        "stored": False
    }
    long = await admin.http.post("/v1/me/source", json={"utm_source": "x" * 201}, headers=ada.headers)
    assert long.status_code == 422


async def test_an_old_account_or_a_member_keeps_no_org_source(admin: Admin, engine: AsyncEngine) -> None:
    old = await person(engine)
    async with engine.begin() as conn:
        week_ago = datetime.now(UTC) - timedelta(days=7)
        await conn.execute(update(User).where(User.id == old.user_id).values(created_at=week_ago))
    assert (await admin.http.post("/v1/me/source", json={"utm_source": "x"}, headers=old.headers)).json() == {
        "stored": False
    }
    joined = await member(engine, old.org_id)
    assert (await admin.http.post("/v1/me/source", json={"utm_source": "y"}, headers=joined.headers)).json() == {
        "stored": True
    }
    assert (await org_row(engine, old.org_id)).source is None


async def test_a_grant_counts_as_being_seen(admin: Admin, engine: AsyncEngine) -> None:
    tag = uuid.uuid4().hex[:8]
    ada = await person(engine, email=f"{tag}@people.test")
    from tests.connector import granted

    grant_id, _ = await granted(engine, ada)
    async with engine.begin() as conn:
        await conn.execute(update(Install).where(Install.user_id == ada.user_id).values(last_seen_at=None))
        await conn.execute(
            update(ConnectorGrant).where(ConnectorGrant.id == grant_id).values(last_used_at=datetime.now(UTC))
        )
    [row] = (await admin.get("/users", q=tag)).json()["people"]
    assert row["last_seen_at"] is not None
