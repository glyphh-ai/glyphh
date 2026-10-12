import json

import httpx
import pytest

from glyphh import AsyncGlyphh, Face, Glyphh, InstalledPage, Launch, MachinePage, Settings

SERVER = "http://localhost:8080"
M = "7f0c7b1e-0000-4000-8000-0000000000aa"
S = "7f0c7b1e-0000-4000-8000-0000000000bb"
FACE = {
    "id": S,
    "name": "Inbox Zero",
    "description": "Sorts your email",
    "avatar_variant": 3,
    "avatar_color": "#B49CFF",
    "status": "working",
    "last_active_at": "2026-10-12T12:00:00Z",
}
CARD = {
    "id": M,
    "name": "studio-mac",
    "host": "fly",
    "platform": "macos",
    "version": "1.0.0",
    "online": True,
    "last_seen_at": None,
    "super_powers": [FACE],
    "installed": 1,
    "working": 1,
    "needs_you": 0,
}
INSTALLED = {
    "machine": "studio-mac",
    "super_powers": [{**FACE, "avatar_color": None, "last_active_at": None}],
    "total": 1,
    "counts": {"all": 1, "working": 1},
}
LAUNCH = {
    "url": f"http://platform.test/machines/{M}",
    "ticket": "x",
    "page": "machine",
    "expires_at": "2026-10-12T12:01:00Z",
}
SETTINGS = {"theme": "light", "rail_collapsed": True, "page_sizes": {"members": 25}}


def answering(body: object, seen: list) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handle)


def test_machines_are_listed_searched_and_opened() -> None:
    seen: list = []
    page = Glyphh(
        SERVER, token="t", transport=answering({"machines": [CARD], "total": 1, "online": 1}, seen)
    ).machines.list(2, 6)
    assert isinstance(page, MachinePage) and page.machines[0].super_powers[0] == Face(
        id=S,
        name="Inbox Zero",
        description="Sorts your email",
        avatar_variant=3,
        avatar_color="#B49CFF",
        status="working",
        last_active_at=page.machines[0].super_powers[0].last_active_at,
    )
    assert page.machines[0].last_seen_at is None and page.machines[0].super_powers[0].last_active_at is not None
    found = Glyphh(SERVER, token="t", transport=answering(INSTALLED, seen)).machines.super_powers(
        M, q="rev", status="working"
    )
    assert found == InstalledPage(
        machine="studio-mac",
        super_powers=[
            Face(
                id=S,
                name="Inbox Zero",
                description="Sorts your email",
                avatar_variant=3,
                avatar_color=None,
                status="working",
                last_active_at=None,
            )
        ],
        total=1,
        counts={"all": 1, "working": 1},
    )
    every = Glyphh(SERVER, token="t", transport=answering(INSTALLED, seen)).machines.super_powers(M)
    assert every.total == 1
    launched = Glyphh(SERVER, token="t", transport=answering(LAUNCH, seen)).machines.open(M, S)
    assert isinstance(launched, Launch) and launched.url == LAUNCH["url"]
    Glyphh(SERVER, token="t", transport=answering(LAUNCH, seen)).machines.open(M)
    assert [str(r.url.params) for r in seen[:3]] == [
        "page=2&size=6",
        "q=rev&status=working&page=1&size=24",
        "q=&page=1&size=24",
    ]
    assert [json.loads(r.content) for r in seen[3:]] == [
        {"panel": "machine", "super_power": S},
        {"panel": "machine", "super_power": None},
    ]


async def test_the_async_client_answers_the_same() -> None:
    seen: list = []
    page = await AsyncGlyphh(
        SERVER, token="t", transport=answering({"machines": [], "total": 0, "online": 0}, seen)
    ).machines.list()
    assert page == MachinePage(machines=[], total=0, online=0)
    found = await AsyncGlyphh(SERVER, token="t", transport=answering(INSTALLED, seen)).machines.super_powers(
        M, status="idle"
    )
    assert found.machine == "studio-mac"
    launched = await AsyncGlyphh(SERVER, token="t", transport=answering(LAUNCH, seen)).machines.open(M)
    assert launched.url == LAUNCH["url"]


@pytest.mark.parametrize("client", ["sync", "async"])
async def test_settings_are_read_and_changed(client: str) -> None:
    seen: list = []
    if client == "sync":
        glyphh = Glyphh(SERVER, token="t", transport=answering(SETTINGS, seen))
        read, changed = glyphh.settings(), glyphh.change_settings(theme="light", page_sizes={"members": 25})
    else:
        aglyphh = AsyncGlyphh(SERVER, token="t", transport=answering(SETTINGS, seen))
        read, changed = await aglyphh.settings(), await aglyphh.change_settings(rail_collapsed=True)
    assert read == changed == Settings(theme="light", rail_collapsed=True, page_sizes={"members": 25})
    assert seen[1].method == "PATCH"
    assert json.loads(seen[1].content) in ({"theme": "light", "page_sizes": {"members": 25}}, {"rail_collapsed": True})
