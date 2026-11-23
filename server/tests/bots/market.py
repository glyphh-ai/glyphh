"""The bots marketplace under test: an org's apps connected at the faked Pipedream (any app a template needs, not
only Gmail), and the library changed for a test: a template that runs only on a rrotor (its plugin carries code, or
it needs folders), and a newer version of a template Glyphh ships."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from glyphh_server.ops.bots import packages
from tests.bots.conftest import Served
from tests.bots.fakes import CONNECT, FIND, SEND, account
from tests.db.helpers import Person

TIDY: str = "folder-tidy"
SCRIPT: str = "skills/brief/scripts/tidy.py"


async def linked(s: Served, who: Person, *apps: str, n: int = 1) -> dict[str, dict[str, Any]]:
    """Each app signed in at Pipedream and synced: the org's connection of each, by app (its `n`th account)."""
    for app in apps:
        about = {"name_slug": app, "name": app.replace("_", " ").title(), "description": "", "img_src": ""}
        s.pd.accounts.append(account(f"apn_{app}_{n}", about, name=f"ada{n}@{app}.test"))
    res = await s.http.post("/v1/connections/sync", headers=who.headers)
    assert res.status_code == 200, res.text
    return {c["app"]: c for c in res.json()["connections"] if c["account_id"].endswith(f"_{n}")}


def any_component(s: Served) -> None:
    """Pipedream answers for a tool the fake does not know as it does for any action: its name and its app prop."""
    known = s.pd._connect

    def connect(method: str, path: str, body: Any, query: dict[str, str]) -> httpx.Response:
        key = path.rsplit("/", 1)[1]
        if method == "GET" and path.startswith(f"{CONNECT}/components/") and key not in (SEND["key"], FIND["key"]):
            about = {"key": key, "name": key, "configurable_props": [{"name": "app", "type": "app"}]}
            return httpx.Response(200, json={"data": about})
        return known(method, path, body, query)

    s.pd._connect = connect  # type: ignore[method-assign]


async def installed(s: Served, who: Person, slug: str, **body: Any) -> dict[str, Any]:
    res = await s.http.post(f"/v1/bot-templates/{slug}/install", json=body, headers=who.headers)
    assert res.status_code == 201, res.text
    return dict(res.json())


async def bot_of(s: Served, who: Person, slug: str) -> dict[str, Any]:
    res = await s.http.get(f"/v1/bots/{slug}", headers=who.headers)
    assert res.status_code == 200, res.text
    return dict(res.json())


def files_of(slug: str) -> dict[str, str]:
    """A shipped package's files, as text by path."""
    return dict(packages.library()[slug].files)


def remade(files: dict[str, str], change: Callable[[dict[str, Any], dict[str, Any]], None]) -> packages.Package:
    """The package of these files once `change` has had its manifest and its sidecar, checked as any package is."""
    manifest, side = json.loads(files[packages.MANIFEST]), json.loads(files[packages.SIDECAR])
    change(manifest, side)
    return packages.check({**files, packages.MANIFEST: json.dumps(manifest), packages.SIDECAR: json.dumps(side)})


def shelved(monkeypatch: pytest.MonkeyPatch, *more: packages.Package, only: bool = False) -> None:
    """The library with these packages in it (each in place of the shipped one of its slug); `only`: nothing else."""
    shelf = ({} if only else dict(packages.library())) | {p.slug: p for p in more}
    monkeypatch.setattr(packages, "library", lambda: shelf)


def rrotor_only(folders: bool = False) -> packages.Package:
    """News Brief as a template that runs only on a rrotor: its skill carries a script (or it needs folders)."""

    def change(manifest: dict[str, Any], side: dict[str, Any]) -> None:
        manifest["name"] = TIDY
        side["bot"]["name"] = "Folder Tidy"
        side["runs_on"] = ["rrotor"]
        if folders:
            side["folders"] = True
        else:
            side["code"] = [{"skill": "brief", "scripts": [SCRIPT], "why": "It sorts the files itself."}]

    files = files_of("news-brief") | ({} if folders else {SCRIPT: "print('tidy')\n"})
    return remade(files, change)
