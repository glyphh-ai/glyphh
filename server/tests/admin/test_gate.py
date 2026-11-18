"""Who reaches the staff view: staff, by their verified email, signed in through the platform; anyone else is refused
and the refusal is itself an ops event. Every staff request is audited, a refused one too; tenants still see only
their own org, and never the staff's tables."""

import uuid

import pytest
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.admin import audit
from glyphh_server.admin.staff import is_staff, via_platform
from glyphh_server.api.admin.deps import NOT_STAFF
from glyphh_server.db import tenancy
from glyphh_server.models import AdminAudit, OpsEvent
from glyphh_server.obs.events import QUEUE
from glyphh_server.ops.auth.principal import Principal
from tests.admin.conftest import PLATFORM_ID, Admin
from tests.conftest import SETTINGS
from tests.db.helpers import granted, other_client, person


async def _audit(engine: AsyncEngine, staff: uuid.UUID) -> list[AdminAudit]:
    async with engine.connect() as conn:
        found = select(AdminAudit).where(AdminAudit.staff_user_id == staff).order_by(AdminAudit.at)
        return list(await conn.execute(found))  # type: ignore[arg-type]


async def test_me_says_staff_and_nobody_else_is_answered(admin: Admin, engine: AsyncEngine) -> None:
    me = await admin.http.get("/v1/me", headers=admin.headers)
    assert me.status_code == 200 and me.json()["staff"] is True and me.json()["email"] == admin.staff.email
    other = await person(engine)
    gone = await admin.http.get("/v1/me", headers=other.headers)
    assert gone.status_code == 410 and gone.json()["error"]["code"] == "E_WOUND_DOWN"


async def test_staff_reach_the_view_through_the_platform_only(admin: Admin, engine: AsyncEngine) -> None:
    assert (await admin.get("/plans")).status_code == 200
    _, by_another_client = await granted(engine, admin.staff, client_id=await other_client(engine))
    refused = await admin.http.get("/v1/admin/plans", headers=by_another_client)
    assert refused.status_code == 403 and refused.json()["error"]["reason"] == "not_staff"
    assert refused.json()["error"]["message"] == NOT_STAFF
    _, for_elsewhere = await granted(engine, admin.staff, resource="http://localhost:8080/elsewhere")
    assert (await admin.http.get("/v1/admin/plans", headers=for_elsewhere)).status_code == 401
    assert (await admin.http.get("/v1/admin/plans")).status_code == 401
    wrong = await admin.http.get("/v1/admin/plans", headers={"authorization": "Bearer not-a-token"})
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "E_UNAUTHORIZED"


async def test_anyone_else_is_refused_and_it_is_an_ops_event(admin: Admin, engine: AsyncEngine, redis: Redis) -> None:
    other = await person(engine)
    refused = await admin.http.get("/v1/admin/dashboard", headers=other.headers)
    assert refused.status_code == 403 and refused.json()["error"]["reason"] == "not_staff"
    queued = await redis.lrange(QUEUE, -20, -1)  # type: ignore[misc]
    assert any(str(other.user_id) in line and '"kind": "staff"' in line for line in queued)
    assert await _audit(engine, other.user_id) == []  # no staff request was made: nothing to audit


async def test_every_staff_request_is_audited_a_refused_one_too(admin: Admin, engine: AsyncEngine) -> None:
    org = admin.staff.org_id
    assert (await admin.get(f"/orgs/{org}")).status_code == 200
    missing = uuid.uuid4()
    assert (await admin.get(f"/orgs/{missing}")).status_code == 404
    assert (await admin.get("/orgs", q="x")).status_code == 200
    rows = await _audit(engine, admin.staff.user_id)
    assert [(r.action, r.org_id, r.outcome) for r in rows] == [
        ("adminOrg", org, "ok"),
        ("adminOrg", missing, "E_NOT_FOUND"),
        ("adminOrgs", None, "ok"),
    ]
    assert rows[2].detail == {"path": "/v1/admin/orgs", "query": {"q": "x"}} and rows[2].target == "/v1/admin/orgs"
    assert rows[0].staff_email == admin.staff.email


async def test_a_crash_is_audited_as_internal(
    admin: Admin, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from glyphh_server.api.admin import people

    async def boom(*_: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(people, "plans", boom)
    crashed = await admin.get("/plans")
    assert crashed.status_code == 500 and crashed.json()["error"]["code"] == "E_INTERNAL"
    assert [(r.action, r.outcome) for r in await _audit(engine, admin.staff.user_id)] == [("adminPlans", "E_INTERNAL")]


async def test_an_org_path_that_is_no_uuid_is_audited_without_an_org(admin: Admin, engine: AsyncEngine) -> None:
    assert (await admin.get("/orgs/not-a-uuid")).status_code == 422
    rows = await _audit(engine, admin.staff.user_id)
    assert [(r.action, r.org_id, r.outcome) for r in rows] == [("adminOrg", None, "E_INVALID")]


async def test_an_audit_row_holds_who_what_and_what_it_changed(engine: AsyncEngine) -> None:
    who = Principal(
        user_id=uuid.uuid4(), org_id=uuid.uuid4(), role="admin", grant_id=uuid.uuid4(), client_id=PLATFORM_ID
    )
    who = who.model_copy(update={"email": " Support@Glyphh.ai "})
    org = uuid.uuid4()
    async with engine.begin() as conn:
        entry = await audit.record(conn, who, "adminSuspendOrg", org)
        await audit.add(conn, entry, {"reason": "abuse"})
        await audit.add(conn, entry, {"acknowledged": 2})
        [found] = (await audit.listing(conn, org_id=org)).entries
    assert (found.staff_email, found.action, found.target, found.outcome) == (
        "support@glyphh.ai",
        "adminSuspendOrg",
        None,
        "ok",
    )
    assert found.detail == {"reason": "abuse", "acknowledged": 2}


async def test_tenants_never_see_the_staff_tables(engine: AsyncEngine, admin: Admin) -> None:
    await admin.get("/plans")
    other = await person(engine)
    async with engine.begin() as conn:
        assert (await conn.execute(select(AdminAudit.id))).first() is not None
        await tenancy.enter(conn, other.org_id)
        assert (await conn.execute(select(AdminAudit.id))).first() is None
        assert (await conn.execute(select(OpsEvent.id))).first() is None
        assert (await conn.execute(text("SELECT count(*) FROM orgs"))).scalar_one() == 1


def test_staff_is_the_email_and_the_platform_is_its_client() -> None:
    settings = SETTINGS.model_copy(update={"staff_emails": " A@x.test ,, b@x.test", "platform_client_id": ""})
    who = Principal(
        user_id=uuid.uuid4(), org_id=uuid.uuid4(), role="admin", grant_id=uuid.uuid4(), client_id=PLATFORM_ID
    )
    who = who.model_copy(update={"email": "a@X.test"})
    assert settings.staff_set == frozenset({"a@x.test", "b@x.test"})
    assert is_staff(settings, who) and not is_staff(settings, who.model_copy(update={"email": ""}))
    assert not is_staff(settings, who.model_copy(update={"email": "c@x.test"}))
    assert not via_platform(settings, who)  # no platform client set: nobody is through it
    platform = settings.model_copy(update={"platform_client_id": str(PLATFORM_ID)})
    assert via_platform(platform, who)
    assert not via_platform(platform, who.model_copy(update={"client_id": uuid.uuid4()}))
