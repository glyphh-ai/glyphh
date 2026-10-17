"""A mod bought once (Glyphh Drip): Stripe's finished Payment Link checkout records it, the licence comes by mod and
install and checks with the server's key, a replay changes nothing, a refund takes it back."""

import base64
import json
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Unlock
from tests.api.test_stripe_webhook import _event, _send
from tests.db.helpers import person

MOD = "glyphh-drip"


def _checkout(session: str, mod: str, install: str, intent: str = "pi_1", status: str = "paid") -> dict[str, Any]:
    return {
        "id": session,
        "mode": "payment",
        "payment_status": status,
        "client_reference_id": install,
        "payment_intent": intent,
        "metadata": {"mod": mod},
    }


def _unb64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


async def _licence(client: httpx.AsyncClient, mod: str, install: str) -> dict[str, Any]:
    res = await client.get("/v1/unlock/license", params={"mod": mod, "install": install})
    assert res.status_code == 200
    return res.json()


async def _rows(engine: AsyncEngine) -> int:
    async with engine.connect() as conn:
        return int((await conn.execute(select(func.count()).select_from(Unlock))).scalar_one())


async def test_a_paid_checkout_unlocks_the_mod_for_the_install_and_the_licence_checks(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    assert await _licence(client, MOD, "inst-1") == {"paid": False, "licence": None}
    for _ in range(2):
        assert (
            await _send(client, _event("checkout.session.completed", _checkout("cs_a", MOD, "inst-1")))
        ).status_code == 204
    assert await _rows(engine) == 1
    got = await _licence(client, MOD, "inst-1")
    assert got["paid"] is True
    first, signature = got["licence"].split(".")
    key = (await client.get("/v1/license/key", headers=(await person(engine)).headers)).json()
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public_key"]))
    public.verify(_unb64(signature), first.encode())
    payload = json.loads(_unb64(first))
    assert (payload["v"], payload["mod"], payload["install"], payload["session"]) == (1, MOD, "inst-1", "cs_a")
    assert payload["issued"].endswith("+00:00")
    assert await _licence(client, MOD, "inst-2") == {"paid": False, "licence": None}


async def test_an_unpaid_checkout_an_unknown_mod_or_no_install_records_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    before = await _rows(engine)
    for obj in (
        _checkout("cs_u1", MOD, "inst-u", status="unpaid"),
        _checkout("cs_u2", "drips", "inst-u"),
        _checkout("cs_u3", MOD, ""),
        {"id": "cs_u4", "mode": "payment", "payment_status": "paid", "client_reference_id": "inst-u"},
    ):
        assert (await _send(client, _event("checkout.session.completed", obj))).status_code == 204
    assert await _rows(engine) == before
    assert await _licence(client, MOD, "inst-u") == {"paid": False, "licence": None}


async def test_a_refund_takes_the_licence_back_and_a_new_purchase_gives_it_again(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _send(client, _event("checkout.session.completed", _checkout("cs_r1", MOD, "inst-r", intent="pi_r1")))
    assert (await _licence(client, MOD, "inst-r"))["paid"] is True
    await _send(client, _event("charge.refunded", {"id": "ch_1", "payment_intent": "pi_nobody"}))
    await _send(client, _event("charge.refunded", {"id": "ch_2"}))
    assert (await _licence(client, MOD, "inst-r"))["paid"] is True
    await _send(client, _event("charge.refunded", {"id": "ch_3", "payment_intent": "pi_r1"}))
    assert await _licence(client, MOD, "inst-r") == {"paid": False, "licence": None}
    await _send(client, _event("checkout.session.completed", _checkout("cs_r2", MOD, "inst-r", intent="pi_r2")))
    got = await _licence(client, MOD, "inst-r")
    assert got["paid"] is True and json.loads(_unb64(got["licence"].split(".")[0]))["session"] == "cs_r2"


async def test_the_licence_is_asked_for_a_mod_sold_once_only(client: httpx.AsyncClient) -> None:
    res = await client.get("/v1/unlock/license", params={"mod": "ada", "install": "inst-x"})
    assert (res.status_code, res.json()["error"]["reason"]) == (422, "no_mod")
    res = await client.get("/v1/unlock/license", params={"mod": "games", "install": "inst-x"})
    assert (res.status_code, res.json()["error"]["reason"]) == (422, "no_mod")
    assert (await client.get("/v1/unlock/license", params={"mod": MOD})).status_code == 422
