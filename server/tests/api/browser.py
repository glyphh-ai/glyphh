"""A browser in the platform's sign-in, and the server as one of Glyphh's staff sees it. Only staff sign in, and an
email belongs to one person, so each test's staff member is a new email the app under test is told is staff."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.config import Settings
from tests.conftest import PROVIDER_SETTINGS, _client
from tests.db.helpers import Person, an_email, person
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


def staffed(email: str, settings: Settings = PROVIDER_SETTINGS) -> Settings:
    """These settings, with this email Glyphh's staff."""
    return settings.model_copy(update={"staff_emails": email})


@dataclass
class Browser:
    http: httpx.AsyncClient
    email: str


async def open_browser(
    stripe: FakeStripe, settings: Settings = PROVIDER_SETTINGS, staff: bool = True
) -> AsyncIterator[Browser]:
    """A browser whose Google account is a new person's own: one of Glyphh's staff, unless told otherwise."""
    email = an_email()
    over = {("GET", "/v1/userinfo"): {**GOOGLE_ME, "sub": f"g-{email}", "email": email}}
    async for c in _client(create_app(staffed(email, settings) if staff else settings, http=fake_http(stripe, over))):
        yield Browser(c, email)


@dataclass
class Staff:
    http: httpx.AsyncClient
    who: Person


async def open_staff(engine: AsyncEngine, stripe: FakeStripe, plan: str = "Free") -> AsyncIterator[Staff]:
    """A staff member already signed in through the platform, and the server that knows them as staff."""
    who = await person(engine, plan)
    async for c in _client(create_app(staffed(who.email), http=fake_http(stripe))):
        yield Staff(c, who)
