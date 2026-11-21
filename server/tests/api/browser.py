"""A person signing in through the device flow the way a browser and the mod do it."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx

from glyphh_server.app import create_app
from glyphh_server.config import Settings
from tests.conftest import PROVIDER_SETTINGS, _client
from tests.db.helpers import an_email
from tests.fakes import GOOGLE_ME, FakeStripe, fake_http

PLATFORM: str = "http://localhost:3000"


def went(res: httpx.Response) -> tuple[str, dict[str, str]]:
    """A redirect to the platform: the page's path and its query values."""
    assert res.status_code == 302, res.text
    parts = urlsplit(res.headers["location"])
    assert f"{parts.scheme}://{parts.netloc}" == PLATFORM, res.headers["location"]
    return parts.path, {k: v[0] for k, v in parse_qs(parts.query).items()}


def error_page(res: httpx.Response) -> dict[str, str]:
    """A refusal in a browser flow: the platform's error page's values (code, message, trace)."""
    path, q = went(res)
    assert path == "/error" and q["trace"] == res.headers["x-request-id"], q
    return q


@dataclass
class Browser:
    http: httpx.AsyncClient
    email: str


async def open_browser(stripe: FakeStripe, settings: Settings = PROVIDER_SETTINGS) -> AsyncIterator[Browser]:
    """A browser whose Google account is a new person's own."""
    email = an_email()
    over = {("GET", "/v1/userinfo"): {**GOOGLE_ME, "sub": f"g-{email}", "email": email}}
    async for c in _client(create_app(settings, http=fake_http(stripe, over))):
        yield Browser(c, email)


async def new_code(
    http: httpx.AsyncClient, name: str = "Ada's Mac", surface: str = "desktop", machine_id: str | None = None
) -> dict[str, Any]:
    """A sign-in started from a machine: a new one each time unless its id is given."""
    body = {"machine_id": machine_id or uuid.uuid4().hex, "name": name, "surface": surface, "mod_version": "0.1.0"}
    res = await http.post("/v1/device/code", json=body)
    assert res.status_code == 200, res.text
    return res.json()


async def to_approve(http: httpx.AsyncClient, user_code: str, provider: str = "google") -> tuple[dict[str, Any], str]:
    """Open the link, continue with the provider, come back: what the platform's approve page shows (from
    /auth/consent) and the signed consent it was sent."""
    started = await http.get(f"/auth/{provider}/start", params={"code": user_code})
    assert started.status_code == 302 and "glyphh_signin" in started.headers["set-cookie"], started.text
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    back = await http.get(f"/auth/{provider}/callback", params={"code": "c-1", "state": state})
    path, q = went(back)
    assert path == "/device/approve", path
    shown = await http.get("/auth/consent", params={"consent": q["consent"]})
    assert shown.status_code == 200, shown.text
    return shown.json(), q["consent"]


async def decide(http: httpx.AsyncClient, consent: str, decision: str) -> httpx.Response:
    return await http.get("/auth/approve", params={"consent": consent, "decision": decision})


async def sign_in(http: httpx.AsyncClient, provider: str = "google", machine_id: str | None = None) -> dict[str, str]:
    """The whole flow, approved: the install's Authorization header."""
    code = await new_code(http, machine_id=machine_id)
    _, consent = await to_approve(http, code["user_code"], provider)
    assert went(await decide(http, consent, "approve")) == ("/device/done", {"result": "approved"})
    token = (await http.post("/v1/device/token", json={"device_code": code["device_code"]})).json()
    return {"authorization": f"Bearer {token['access_token']}"}
