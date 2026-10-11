import json
import os

import httpx
import pytest

from glyphh import AsyncGlyphh, CreatedInvite, Glyphh, GlyphhError, InviteView, Member, OrgView

SERVER: str = os.environ.get("GLYPHH_URL") or "http://localhost:8080"
ORG = {"id": "7f0c7b1e-0000-4000-8000-000000000001", "name": "Acme", "plan": "Pro", "seats_taken": 3, "max_seats": None}
MEMBER = {
    "id": "7f0c7b1e-0000-4000-8000-000000000002",
    "email": "ada@acme.test",
    "first_name": "Ada",
    "last_name": None,
    "role": "user",
    "disabled": False,
    "joined_at": "2026-10-11T12:00:00Z",
}
INVITE = {
    "id": "7f0c7b1e-0000-4000-8000-000000000003",
    "email": "new@acme.test",
    "role": "user",
    "expires_at": "2026-10-18T12:00:00Z",
}


def answering(status: int, body: object = None, seen: list | None = None) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status) if body is None else httpx.Response(status, json=body)

    return httpx.MockTransport(handle)


def _sent(seen: list) -> tuple[str, str, object]:
    r = seen[0]
    return r.method, r.url.path, json.loads(r.content) if r.content else None


def test_the_org_without_a_token_is_refused_by_the_real_server() -> None:
    with pytest.raises(GlyphhError) as e:
        Glyphh(SERVER).org.get()
    assert (e.value.status, e.value.code) == (401, "E_UNAUTHORIZED")


def test_the_org_is_read_and_renamed() -> None:
    assert Glyphh(SERVER, token="t", transport=answering(200, ORG)).org.get() == OrgView(
        id=ORG["id"], name="Acme", plan="Pro", seats_taken=3, max_seats=None
    )
    seen: list = []
    Glyphh(SERVER, token="t", transport=answering(200, {**ORG, "max_seats": 100}, seen)).org.rename("Acme Inc")
    assert _sent(seen) == ("PATCH", "/v1/org", {"name": "Acme Inc"})


def test_members_are_listed_changed_and_removed() -> None:
    members = Glyphh(SERVER, token="t", transport=answering(200, [MEMBER])).org.list_members()
    assert isinstance(members[0], Member) and members[0].last_name is None
    seen: list = []
    Glyphh(SERVER, token="t", transport=answering(200, MEMBER, seen)).org.update_member(MEMBER["id"], role="org_admin")
    assert _sent(seen) == ("PATCH", f"/v1/org/members/{MEMBER['id']}", {"role": "org_admin"})
    seen = []
    Glyphh(SERVER, token="t", transport=answering(200, MEMBER, seen)).org.update_member(MEMBER["id"], disabled=True)
    assert _sent(seen)[2] == {"disabled": True}
    seen = []
    Glyphh(SERVER, token="t", transport=answering(204, None, seen)).org.remove_member(MEMBER["id"])
    assert _sent(seen)[0] == "DELETE"


def test_invites_are_made_listed_and_withdrawn() -> None:
    seen: list = []
    made = Glyphh(
        SERVER, token="t", transport=answering(201, {"invite": INVITE, "link": "https://x/join"}, seen)
    ).org.invite("new@acme.test")
    assert isinstance(made, CreatedInvite) and made.link == "https://x/join"
    assert _sent(seen) == ("POST", "/v1/org/invites", {"email": "new@acme.test", "role": "user"})
    assert isinstance(Glyphh(SERVER, token="t", transport=answering(200, [INVITE])).org.list_invites()[0], InviteView)
    seen = []
    Glyphh(SERVER, token="t", transport=answering(204, None, seen)).org.revoke_invite(INVITE["id"])
    assert _sent(seen)[1] == f"/v1/org/invites/{INVITE['id']}"


async def test_async_org_matches_sync() -> None:
    g = lambda status, body=None: AsyncGlyphh(SERVER, token="t", transport=answering(status, body))  # noqa: E731
    assert (await g(200, ORG).org.get()).name == "Acme"
    assert (await g(200, ORG).org.rename("x")).plan == "Pro"
    assert len(await g(200, [MEMBER]).org.list_members()) == 1
    assert (await g(200, MEMBER).org.update_member(MEMBER["id"], disabled=False)).email == "ada@acme.test"
    assert await g(204).org.remove_member(MEMBER["id"]) is None
    assert len(await g(200, [INVITE]).org.list_invites()) == 1
    assert (await g(201, {"invite": INVITE, "link": "l"}).org.invite("a@b.test", "org_admin")).link == "l"
    assert await g(204).org.revoke_invite(INVITE["id"]) is None
    with pytest.raises(GlyphhError) as e:
        await g(403, {"error": {"code": "E_LIMIT", "trace_id": "t-1"}}).org.invite("a@b.test")
    assert (e.value.code, e.value.trace_id) == ("E_LIMIT", "t-1")
