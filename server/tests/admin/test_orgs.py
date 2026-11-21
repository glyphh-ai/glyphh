"""Orgs for staff: every org, searched and filtered, with its plan, members, models, precedents and reads; one org's
account, members, use and models as metadata only; and the staff actions, each audited with what it changed."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
from redis.asyncio import Redis
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import keys, requests
from glyphh_server.admin import adascan
from glyphh_server.admin.orgs import label
from glyphh_server.models import AdaModelDay, AdaUsage, AdminAudit, Org
from glyphh_server.ops.plans import newest_version
from tests.admin.ada import ada_org
from tests.admin.conftest import Admin, platform_headers
from tests.connector import granted
from tests.db.helpers import member, org_row, person, subscribed


async def _named(engine: AsyncEngine, org_id: uuid.UUID, name: str, **values: object) -> None:
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == org_id).values(name=name, **values))


async def test_orgs_are_searched_by_name_id_or_member_email(admin: Admin, engine: AsyncEngine, redis: Redis) -> None:
    tag = uuid.uuid4().hex[:8]
    a = await person(engine, "Pro")
    b = await person(engine)
    await member(engine, a.org_id, f"{tag}-grace@people.test")
    await _named(engine, a.org_id, f"Acme {tag}", source={"utm_source": "reddit", "utm_medium": "cpc"})
    await _named(engine, b.org_id, f"Beta {tag}")
    async with engine.begin() as conn:
        await conn.execute(insert(AdaUsage).values(org_id=a.org_id, period=requests.period(), requests=11))
    await redis.set(requests.total_key(b.org_id, requests.period()), 42)
    ada_org(a.org_id, [{"name": "loans", "precedents": 30}])
    await redis.delete(adascan.SCAN_KEY)
    found = (await admin.get("/orgs", q=tag)).json()
    rows = {o["name"]: o for o in found["orgs"]}
    assert found["total"] == 2 and list(rows) == [f"Beta {tag}", f"Acme {tag}"]
    acme = rows[f"Acme {tag}"]
    assert (acme["plan"], acme["members"], acme["models"], acme["precedents"], acme["reads_month"]) == (
        "Pro",
        2,
        1,
        30,
        11,
    )
    assert acme["source"] == "reddit / cpc" and rows[f"Beta {tag}"]["reads_month"] == 42
    assert (await admin.get("/orgs", q=f"{tag}-grace")).json()["total"] == 1
    by_id = (await admin.get("/orgs", q=str(b.org_id).upper())).json()
    assert [o["id"] for o in by_id["orgs"]] == [str(b.org_id)]
    pro = (await admin.get("/orgs", q=tag, plan="Pro")).json()
    assert [o["name"] for o in pro["orgs"]] == [f"Acme {tag}"]
    page = (await admin.get("/orgs", q=tag, offset=1, limit=1)).json()
    assert (page["total"], len(page["orgs"]), page["offset"]) == (2, 1, 1)
    assert (await admin.get("/orgs")).json()["total"] >= 2


def test_a_source_is_labelled_short() -> None:
    assert label(None) is None and label({}) is None
    assert label({"gclid": "x"}) == "google" and label({"fbclid": "x", "utm_medium": "paid"}) == "meta / paid"
    assert label({"landing": "/code"}) == "(landing only)"


async def test_one_org_shows_metadata_never_contents(admin: Admin, engine: AsyncEngine) -> None:
    org = await person(engine, "Pro")
    await member(engine, org.org_id)
    today = datetime.now(UTC).date()
    async with engine.begin() as conn:
        await conn.execute(insert(AdaUsage).values(org_id=org.org_id, period=requests.period(), requests=9))
        await conn.execute(insert(AdaUsage).values(org_id=org.org_id, period="2025-01", requests=4))
        await conn.execute(
            insert(AdaModelDay).values(org_id=org.org_id, model="m", day=today, metric="read:query", n=6)
        )
        await keys.create(conn, _who(org), "app", None, 0.5)
    ada_org(
        org.org_id,
        [{"name": "loans", "precedents": 3}],
        [{"model": "loans", "kind": "import", "state": "failed", "seconds": 2}],
    )
    res = await admin.get(f"/orgs/{org.org_id}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["account"]["plan"] == "Pro" and body["account"]["suspended_at"] is None
    assert len(body["members"]) == 2 and body["members"][0]["org_id"] == str(org.org_id)
    assert body["reads_month"] == 9 and [m["period"] for m in body["months"]][-1] == "2025-01"
    assert len(body["days"]) == 30 and body["days"][-1] == {"day": today.isoformat(), "reads": 6}
    assert [(m["name"], m["precedents"]) for m in body["models"]] == [("loans", 3)]
    assert [(j["kind"], j["state"]) for j in body["jobs"]] == [("import", "failed")]
    assert (body["api_keys"], body["licences"]) == (1, 0)
    assert "never shown" not in res.text  # a spec's and a job's contents stay in the org's schema
    assert [a["action"] for a in body["audit"]] == ["adminOrg"]  # this very look, audited as it is made
    assert (await admin.get(f"/orgs/{uuid.uuid4()}")).status_code == 404


def _who(p: object):  # type: ignore[no-untyped-def]
    from glyphh_server.ops.auth.principal import Principal

    return Principal(user_id=p.user_id, org_id=p.org_id, role="admin")  # type: ignore[attr-defined]


async def _audited(engine: AsyncEngine, org_id: uuid.UUID) -> list[tuple[str, dict[str, object], str]]:
    async with engine.connect() as conn:
        rows = await conn.execute(select(AdminAudit).where(AdminAudit.org_id == org_id).order_by(AdminAudit.at))
        return [(r.action, r.detail, r.outcome) for r in rows]


async def test_a_plan_version_is_changed_where_billing_cannot_disagree(admin: Admin, engine: AsyncEngine) -> None:
    org = await person(engine)
    async with engine.connect() as conn:
        basic, enterprise = await newest_version(conn, "Basic"), await newest_version(conn, "Enterprise")
        team = await newest_version(conn, "Team")

    async def post(o: uuid.UUID, v: uuid.UUID) -> httpx.Response:
        return await admin.http.post(
            f"/v1/admin/orgs/{o}/plan", json={"plan_version_id": str(v)}, headers=admin.headers
        )

    moved = await post(org.org_id, basic.id)
    assert moved.status_code == 200 and moved.json()["message"].startswith("Moved from Free v")
    assert (await post(org.org_id, enterprise.id)).json()["error"]["reason"] == "enterprise"
    assert (await post(org.org_id, uuid.uuid4())).status_code == 404
    assert (await post(uuid.uuid4(), basic.id)).status_code == 404
    await subscribed(engine, org.org_id, f"sub_{org.org_id.hex}", f"cus_{org.org_id.hex}")
    assert (await post(org.org_id, team.id)).json()["error"]["reason"] == "subscribed"
    assert (await post(org.org_id, basic.id)).status_code == 200  # within its plan
    unpaid = await person(engine)
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == unpaid.org_id).values(plan_version_id=enterprise.id))
    assert (await post(unpaid.org_id, basic.id)).json()["error"]["reason"] == "enterprise"
    audited = await _audited(engine, org.org_id)
    assert audited[0][0] == "adminChangePlan" and audited[0][2] == "ok" and audited[0][1]["to"].startswith("Basic v")
    assert [a[2] for a in audited] == ["ok", "E_CONFLICT", "E_NOT_FOUND", "E_CONFLICT", "ok"]


async def test_a_contract_plan_is_not_set_by_hand(admin: Admin, engine: AsyncEngine) -> None:
    org = await person(engine)
    async with engine.begin() as conn:
        from glyphh_server.models import Plan, PlanVersion

        plan = (
            await conn.execute(insert(Plan).values(name=f"Deal {org.org_id.hex[:6]}", active=False).returning(Plan.id))
        ).scalar_one()
        deal = (
            await conn.execute(
                insert(PlanVersion).values(plan_id=plan, version=1, self_serve=False).returning(PlanVersion.id)
            )
        ).scalar_one()
    res = await admin.http.post(
        f"/v1/admin/orgs/{org.org_id}/plan", json={"plan_version_id": str(deal)}, headers=admin.headers
    )
    assert res.json()["error"]["reason"] == "contract"


async def test_a_suspended_org_is_refused_everywhere_until_lifted(admin: Admin, engine: AsyncEngine) -> None:
    org = await person(engine)
    platform = await platform_headers(engine, org)
    _, connector = await granted(engine, org)
    async with engine.begin() as conn:
        made = await keys.create(conn, _who(org), "app", None, 1.0)
        assert await keys.holder(conn, made.key) is not None
    suspend = f"/v1/admin/orgs/{org.org_id}/suspend"
    assert (await admin.http.post(suspend, json={"reason": "abuse"}, headers=admin.headers)).status_code == 204
    assert (await admin.http.post(suspend, json={"reason": "abuse"}, headers=admin.headers)).json()["error"][
        "reason"
    ] == "suspended"
    for headers in (org.headers, platform):
        refused = await admin.http.get("/v1/me", headers=headers)
        assert refused.status_code == 403 and refused.json()["error"]["reason"] == "suspended"
    rpc = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    assert (await admin.http.post("/mcp", json=rpc, headers=connector)).status_code == 401
    async with engine.connect() as conn:
        assert await keys.holder(conn, made.key) is None
    row = await org_row(engine, org.org_id)
    assert row.suspended_reason == "abuse"
    assert (await admin.http.delete(suspend, headers=admin.headers)).status_code == 204
    assert (await admin.http.delete(suspend, headers=admin.headers)).json()["error"]["reason"] == "not_suspended"
    assert (await admin.http.get("/v1/me", headers=org.headers)).status_code == 200
    own = f"/v1/admin/orgs/{admin.staff.org_id}/suspend"
    assert (await admin.http.post(own, json={"reason": "oops"}, headers=admin.headers)).json()["error"][
        "reason"
    ] == "own_org"
    assert (await admin.http.delete(f"/v1/admin/orgs/{uuid.uuid4()}/suspend", headers=admin.headers)).status_code == 404
    audited = await _audited(engine, org.org_id)
    assert [(a[0], a[2]) for a in audited][:2] == [("adminSuspendOrg", "ok"), ("adminSuspendOrg", "E_CONFLICT")]
    assert audited[0][1]["reason"] == "abuse"


async def test_enterprise_is_granted_and_revoked_by_staff(admin: Admin, engine: AsyncEngine) -> None:
    org = await person(engine, "Pro")
    sub, customer = f"sub_deal{org.org_id.hex}", f"cus_deal_{org.org_id.hex}"
    admin.stripe.sub(sub, customer, "price_deal", 1)
    until = (datetime.now(UTC) + timedelta(days=365)).date()
    body = {"until": until.isoformat(), "subscription": sub}
    granted_ = await admin.http.post(f"/v1/admin/orgs/{org.org_id}/enterprise", json=body, headers=admin.headers)
    assert granted_.status_code == 200, granted_.text
    row = await org_row(engine, org.org_id)
    assert row.plan_until is not None and row.first_paid_at is not None and row.stripe_subscription_id == sub
    revoked = await admin.http.delete(f"/v1/admin/orgs/{org.org_id}/enterprise", headers=admin.headers)
    assert revoked.status_code == 200 and "is on Free" in revoked.json()["message"]
    audited = await _audited(engine, org.org_id)
    assert audited[0][1]["subscription"] == sub and "markup" not in audited[0][1]
    bad = await admin.http.post(
        f"/v1/admin/orgs/{org.org_id}/enterprise", json=body | {"subscription": "nope"}, headers=admin.headers
    )
    assert bad.status_code == 422


async def test_without_billing_enterprise_is_unavailable(engine: AsyncEngine) -> None:
    from glyphh_server.app import create_app
    from tests.admin.conftest import PLATFORM_ID
    from tests.conftest import PROVIDER_SETTINGS, _client
    from tests.fakes import fake_http

    email = f"staff-{uuid.uuid4().hex[:8]}@glyphh.test"
    staff = await person(engine, email=email)
    headers = await platform_headers(engine, staff)
    settings = PROVIDER_SETTINGS.model_copy(
        update={"staff_emails": email, "platform_client_id": str(PLATFORM_ID), "stripe_secret_key": ""}
    )
    org = await person(engine)
    async for http in _client(create_app(settings, http=fake_http())):
        body = {"until": "2030-01-01", "subscription": "sub_x"}
        res = await http.post(f"/v1/admin/orgs/{org.org_id}/enterprise", json=body, headers=headers)
        assert res.status_code == 503
        assert (await http.delete(f"/v1/admin/orgs/{org.org_id}/enterprise", headers=headers)).status_code == 200
