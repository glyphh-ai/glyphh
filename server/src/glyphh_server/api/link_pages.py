"""Linking Google or GitHub to a signed-in person's account, in a browser. The link the API hands out carries a
signed value naming the person and the provider; it goes through the same provider pages as the device sign-in
(`/auth/{provider}/start` and `/callback`), tied to the browser that opened it by the same short-lived cookie."""

import uuid
from typing import Any
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.requests import Request
from starlette.responses import Response

from glyphh_server.api.browser_session import START_AGAIN, TTL, callback_url, cfg, forget_browser
from glyphh_server.api.pages import page
from glyphh_server.config import Settings
from glyphh_server.errors import Invalid
from glyphh_server.ops import identities
from glyphh_server.ops.auth import signed
from glyphh_server.ops.auth.providers import Provider

LINK: str = "link"


def link_url(settings: Settings, user_id: uuid.UUID, provider: str) -> str:
    value = signed.sign(settings.secret_key, {"k": LINK, "u": str(user_id), "p": provider}, TTL)
    return f"{settings.base_url}/auth/{provider}/start?{urlencode({'link': value})}"


def purpose(settings: Settings, provider: str, link: str) -> dict[str, Any]:
    """What the link's signed value asks for, checked: link this provider to this person."""
    found = signed.verify(settings.secret_key, link)
    if found.get("k") != LINK or found["p"] != provider:
        raise Invalid(START_AGAIN)
    return {"k": LINK, "u": found["u"], "p": provider}


def is_link(state: dict[str, Any]) -> bool:
    return state.get("k") == LINK


async def finish(
    request: Request, conn: AsyncConnection, chosen: Provider, state: dict[str, Any], code: str
) -> Response:
    settings = cfg(request)
    name = state["p"]
    profile = await chosen.profile(request.app.state.http, settings, code, callback_url(settings, name))
    await identities.attach(conn, uuid.UUID(state["u"]), profile)
    done = f"{identities.NAMES[name]} is now linked to your Glyphh account. Go back to Claude."
    return forget_browser(page("Linked", done))
