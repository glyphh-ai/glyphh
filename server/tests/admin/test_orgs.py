"""Orgs for staff: every org, searched and filtered, with its plan and members; one org's account, members and prepaid
balance; and the staff actions left, suspending and lifting it, each audited with what it changed. What the retired
products showed (models, precedents, reads, jobs, API keys, licences) is answered 0 or empty."""

import uuid

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.admin.orgs import label
from glyphh_server.models import AdminAudit, LlmBalance, Org
from tests.admin.conftest import Admin
from tests.db.helpers import member, org_row, person, subscribed


async def _named(engine: AsyncEngine, org_id: uuid.UUID, name: str, **values: object) -> None:
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == org_id).values(name=name, **values))


async def test_orgs_are_searched_by_name_id_or_member_email(admin: Admin, engine: AsyncEngine) -> None:
    tag = uuid.uuid4().hex[:8]
    a = await person(engine, "Pro")
    b = await person(engine)
    await member(engine, a.org_id, f"{tag}-grace@people.test")
    await _named(engine, a.org_id, f"Acme {tag}", source={"utm_source": "reddit", "utm_medium": "cpc"})
    await _named(engine, b.org_id, f"Beta {tag}")
    await subscribed(engine, a.org_id, f"sub_{a.org_id.hex}", f"cus_{a.org_id.hex}")
    found = (await admin.get("/orgs", q=f"  {tag} ")).json()
    rows = {o["name"]: o for o in found["orgs"]}
    assert found["total"] == 2 and list(rows) == [f"Beta {tag}", f"Acme {tag}"]  # the newest first
    acme, beta = rows[f"Acme {tag}"], rows[f"Beta {tag}"]
    assert (acme["plan"], acme["plan_version"], acme["members"], acme["billing_status"]) == ("Pro", 1, 2, "active")
    assert acme["source"] == "reddit / cpc" and acme["suspended"] is False and acme["first_paid_at"] is None
    assert (beta["plan"], beta["members"], beta["source"]) == ("Free", 1, None)
    assert (await admin.get("/orgs", q=f"{tag}-grace")).json()["total"] == 1
    by_id = (await admin.get("/orgs", q=str(b.org_id).upper())).json()
    assert [o["id"] for o in by_id["orgs"]] == [str(b.org_id)]
    pro = (await admin.get("/orgs", q=tag, plan="Pro")).json()
    assert [o["name"] for o in pro["orgs"]] == [f"Acme {tag}"]
    page = (await admin.get("/orgs", q=tag, offset=1, limit=1)).json()
    assert (page["total"], [o["name"] for o in page["orgs"]], page["offset"], page["limit"]) == (
        2,
        [f"Acme {tag}"],
        1,
        1,
    )
    every = (await admin.get("/orgs", q="   ")).json()  # nothing to search for: every org
    assert every["total"] == (await admin.get("/orgs")).json()["total"] >= 3 and every["limit"] == 50
    assert (await admin.get("/orgs", limit=201)).status_code == 422


async def test_what_the_retired_products_counted_of_an_org_is_answered_zero(admin: Admin, engine: AsyncEngine) -> None:
    listed = (await admin.get("/orgs")).json()["orgs"]
    assert listed and all((o["models"], o["precedents"], o["reads_month"]) == (0, 0, 0) for o in listed)
    one = (await admin.get(f"/orgs/{admin.staff.org_id}")).json()
    assert (one["reads_month"], one["api_keys"], one["licences"]) == (0, 0, 0)
    assert one["months"] == one["days"] == one["models"] == one["jobs"] == []


def test_a_source_is_labelled_short() -> None:
    assert label(None) is None and label({}) is None
    assert label({"gclid": "x"}) == "google" and label({"fbclid": "x", "utm_medium": "paid"}) == "meta / paid"
    assert label({"rdt_cid": "x", "utm_source": "newsletter"}) == "newsletter"  # its own tag before the click's
    assert label({"rdt_cid": "x"}) == "reddit"
    assert label({"landing": "/code"}) == "(landing only)"


async def test_one_org_shows_its_account_members_and_balance(admin: Admin, engine: AsyncEngine) -> None:
    org = await person(engine, "Pro")
    joined = await member(engine, org.org_id)
    await _named(engine, org.org_id, "Shown Ltd", source={"utm_source": "reddit"})
    await subscribed(engine, org.org_id, f"sub_{org.org_id.hex}", f"cus_{org.org_id.hex}")
    res = await admin.get(f"/orgs/{org.org_id}")
    assert res.status_code == 200, res.text
    body = res.json()
    account = body["account"]
    assert (account["id"], account["name"], account["plan"], account["plan_version"]) == (
        str(org.org_id),
        "Shown Ltd",
        "Pro",
        1,
    )
    assert (account["billing_status"], account["stripe_subscription_id"]) == ("active", f"sub_{org.org_id.hex}")
    assert account["suspended_at"] is None and account["source"] == {"utm_source": "reddit"}
    assert {m["email"] for m in body["members"]} == {org.email, joined.email}
    assert all(m["org_id"] == str(org.org_id) and m["org_name"] == "Shown Ltd" for m in body["members"])
    assert body["balance"] == {"cents": 0.0, "micros": 0, "low": True}  # none was ever held
    assert [a["action"] for a in body["audit"]] == ["adminOrg"]  # this very look, audited as it is made
    async with engine.begin() as conn:
        await conn.execute(insert(LlmBalance).values(org_id=org.org_id, micros=12_345_600))
    held = (await admin.get(f"/orgs/{org.org_id}")).json()
    assert held["balance"] == {"cents": 1234.56, "micros": 12_345_600, "low": False}  # money held for it
    assert [a["action"] for a in held["audit"]] == ["adminOrg", "adminOrg"]
    missing = await admin.get(f"/orgs/{uuid.uuid4()}")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "E_NOT_FOUND"


async def _audited(engine: AsyncEngine, org_id: uuid.UUID) -> list[tuple[str, dict[str, object], str]]:
    async with engine.connect() as conn:
        rows = await conn.execute(select(AdminAudit).where(AdminAudit.org_id == org_id).order_by(AdminAudit.at))
        return [(r.action, r.detail, r.outcome) for r in rows]


async def test_a_suspended_org_is_refused_everywhere_until_lifted(admin: Admin, engine: AsyncEngine) -> None:
    colleague = await person(engine, email=admin.colleague)  # staff too, in an org of their own
    suspend = f"/orgs/{colleague.org_id}/suspend"
    assert (await admin.http.get("/v1/me", headers=colleague.headers)).status_code == 200
    assert (await admin.post(suspend, {"reason": "ab"})).status_code == 422  # a reason, not a word
    assert (await admin.post(suspend, {"reason": " abuse "})).status_code == 204
    assert (await admin.post(suspend, {"reason": "abuse"})).json()["error"]["reason"] == "suspended"
    for path in ("/v1/me", "/v1/admin/plans"):
        refused = await admin.http.get(path, headers=colleague.headers)
        assert refused.status_code == 403 and refused.json()["error"]["reason"] == "suspended"
        assert "support@glyphh.ai" in refused.json()["error"]["message"]
    row = await org_row(engine, colleague.org_id)
    assert row.suspended_reason == "abuse" and row.suspended_at is not None
    [listed] = (await admin.get("/orgs", q=str(colleague.org_id))).json()["orgs"]
    assert listed["suspended"] is True
    shown = (await admin.get(f"/orgs/{colleague.org_id}")).json()["account"]
    assert shown["suspended_reason"] == "abuse" and shown["suspended_at"] is not None
    assert (await admin.delete(suspend)).status_code == 204
    assert (await admin.delete(suspend)).json()["error"]["reason"] == "not_suspended"
    assert (await admin.http.get("/v1/me", headers=colleague.headers)).status_code == 200
    assert (await admin.http.get("/v1/admin/plans", headers=colleague.headers)).status_code == 200
    row = await org_row(engine, colleague.org_id)
    assert row.suspended_reason is None and row.suspended_at is None
    audited = await _audited(engine, colleague.org_id)
    assert [(a[0], a[2]) for a in audited][:3] == [
        ("adminSuspendOrg", "E_INVALID"),
        ("adminSuspendOrg", "ok"),
        ("adminSuspendOrg", "E_CONFLICT"),
    ]
    assert audited[1][1]["reason"] == " abuse " and "reason" not in audited[2][1]  # what it changed, when it did
    assert [(a[0], a[2]) for a in audited if a[0] == "adminUnsuspendOrg"] == [
        ("adminUnsuspendOrg", "ok"),
        ("adminUnsuspendOrg", "E_CONFLICT"),
    ]


async def test_staff_cannot_suspend_their_own_org_or_one_that_is_not_there(admin: Admin, engine: AsyncEngine) -> None:
    own = await admin.post(f"/orgs/{admin.staff.org_id}/suspend", {"reason": "oops"})
    assert own.status_code == 409 and own.json()["error"]["reason"] == "own_org"
    assert (await org_row(engine, admin.staff.org_id)).suspended_at is None
    assert (await admin.post(f"/orgs/{uuid.uuid4()}/suspend", {"reason": "nobody"})).status_code == 404
    assert (await admin.delete(f"/orgs/{uuid.uuid4()}/suspend")).status_code == 404
