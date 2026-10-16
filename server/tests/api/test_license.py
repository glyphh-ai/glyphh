"""The signed license, checked the way the mod checks it: with the public key, over the canonical payload."""

import base64
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.license import load_key
from tests.conftest import SETTINGS
from tests.db.helpers import person, with_addon


def _verify(key: dict, lic: dict) -> None:
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public_key"]))
    body = json.dumps(lic["payload"], sort_keys=True, separators=(",", ":")).encode()
    public.verify(base64.b64decode(lic["signature"]), body)


async def test_the_license_carries_the_plan_and_verifies_with_the_public_key(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Pro")
    await with_addon(engine, ada.org_id, "gateway")
    await with_addon(engine, ada.org_id, "programs")
    lic = (await client.get("/v1/license", headers=ada.headers)).json()
    key = (await client.get("/v1/license/key", headers=ada.headers)).json()
    assert key["alg"] == "Ed25519"
    _verify(key, lic)
    p = lic["payload"]
    assert (p["install_id"], p["user_id"], p["org_id"]) == (str(ada.install_id), str(ada.user_id), str(ada.org_id))
    assert (p["plan"], p["limits"], p["mods"]) == (
        "Pro",
        {"members": 1, "installs": 5},
        {
            "gateway": {"limits": {"keys": 10, "models": 5}},
            "programs": {"limits": {"programs": 25, "runs_per_day": 1000}},
        },
    )
    assert list(p["mods"]) == ["gateway", "programs"]
    assert sorted(p) == ["expires_at", "install_id", "limits", "mods", "org_id", "plan", "user_id"]
    assert p["expires_at"].endswith("Z")
    left = datetime.fromisoformat(p["expires_at"]) - datetime.now(UTC)
    assert timedelta(hours=23, minutes=59) < left <= timedelta(hours=24)
    lic["payload"]["mods"]["gateway"]["limits"]["keys"] = None
    with pytest.raises(InvalidSignature):
        _verify(key, lic)


async def test_free_carries_free_limits_and_the_license_needs_a_token(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    mods = (await client.get("/v1/license", headers=ada.headers)).json()["payload"]["mods"]
    assert mods == {}
    for path in ("/v1/license", "/v1/license/key"):
        assert (await client.get(path)).status_code == 401


def test_the_configured_key_is_the_one_used() -> None:
    made = Ed25519PrivateKey.generate()
    raw = made.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    loaded = load_key(SETTINGS.model_copy(update={"license_key": base64.b64encode(raw).decode()}))
    assert loaded.public_key().public_bytes_raw() == made.public_key().public_bytes_raw()
    first, second = load_key(SETTINGS), load_key(SETTINGS)
    assert first.public_key().public_bytes_raw() != second.public_key().public_bytes_raw()
