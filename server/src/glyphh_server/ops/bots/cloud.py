"""What a bot's code steps reach in Glyphh's cloud, in place of a program.py of its own (the cloud runs no code of a
bot's): `fetch`, a GET of JSON from one of the bot's hosts (https, a public address only, no redirects, at most 5 MB),
and its connections' tools, the Pipedream actions its scope names, each run as the org with the connection's account
filled in. The runner runs in a worker thread (ops/bots/engine.py); a tool's call goes back to the server's own event
loop and waits there for its answer."""

import asyncio
import ipaddress
import json
import socket
import urllib.parse
import urllib.request
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid
from glyphh_server.models import Connection
from glyphh_server.ops.bots import props
from glyphh_server.ops.bots.pipedream import Pipedream

Call = Callable[[dict[str, Any]], Awaitable[Any]]
BUILT_IN: tuple[str, ...] = ("fetch",)
TOOL_SECONDS: float = 120.0
FETCH_SECONDS: float = 20.0
FETCH_MAX: int = 5_000_000
PRIVATE_SUFFIXES: tuple[str, ...] = (".internal", ".local", ".localhost", ".flycast", ".lan", ".home", ".corp")


def public_host(host: str) -> bool:
    """A host name a bot may name: a DNS name with a dot, not an address, not a local or private name."""
    h = host.strip().lower().rstrip(".")
    try:
        ipaddress.ip_address(h.strip("[]"))
        return False
    except ValueError:
        pass
    return "." in h and h != "localhost" and not h.endswith(PRIVATE_SUFFIXES)


def check_hosts(spec: dict[str, Any]) -> None:
    hosts = spec.get("hosts") or []
    bad = [h for h in hosts if isinstance(h, str) and not public_host(h)] if isinstance(hosts, list) else []
    if bad:
        raise Invalid(f"A bot fetches only from public hosts: {', '.join(bad)} is not one.", reason="hosts")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None  # a redirect is answered as the error it is, never followed to another host


def _resolved_public(host: str) -> bool:
    try:
        found = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    return bool(found) and all(ipaddress.ip_address(f[4][0]).is_global for f in found)


def fetch(req: urllib.request.Request, timeout: float) -> Any:
    """The runner's fetch in the cloud: the SDK has checked https and the bot's hosts; here every address the host
    resolves to must be public, nothing redirects, and the answer is JSON of at most FETCH_MAX bytes."""
    host = urllib.parse.urlparse(req.full_url).hostname or ""
    if not public_host(host) or not _resolved_public(host):
        raise ValueError(f"{host} is not a public host")
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(req, timeout=min(timeout, FETCH_SECONDS)) as res:
        body = res.read(FETCH_MAX + 1)
    if len(body) > FETCH_MAX:
        raise ValueError(f"{host} answered more than {FETCH_MAX // 1_000_000} MB")
    return json.loads(body)


class Program:
    """The cloud's program for one bot: `fetch`, and each tool its scope lets it use (`calls`, by key), run on the
    server's event loop (`loop`; None when the bot is only checked, never run)."""

    def __init__(self, calls: dict[str, Call], loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._calls, self._loop = calls, loop

    def fetch(self, ctx: Any, given: Any) -> Any:
        if isinstance(given, str):
            return ctx.http_json(given)
        if isinstance(given, dict) and isinstance(given.get("url"), str):
            headers = given.get("headers") if isinstance(given.get("headers"), dict) else None
            return ctx.http_json(given["url"], headers)
        raise ValueError('fetch takes a URL, or {"url": ..., "headers": {...}}')

    def __getattr__(self, name: str) -> Any:
        calls = self.__dict__.get("_calls") or {}
        if name not in calls:
            raise AttributeError(name)

        def tool(ctx: Any, given: Any) -> Any:
            if self._loop is None:
                raise RuntimeError("the bot is only being checked")
            ask = calls[name](given if isinstance(given, dict) else {})
            return asyncio.run_coroutine_threadsafe(ask, self._loop).result(TOOL_SECONDS)  # type: ignore[arg-type]

        return tool


def named(scopes: list[dict[str, Any]]) -> dict[str, Call]:
    """The tools a bot's scope names, not to be called: for checking its loop against them."""

    async def never(given: dict[str, Any]) -> Any:
        raise RuntimeError("not called")  # pragma: no cover

    return {key: never for s in scopes for key in s["tools"]}


def _action(pd: Pipedream, org_id: uuid.UUID, key: str, defined: list[dict[str, Any]], account: str) -> Call:
    async def call(given: dict[str, Any]) -> Any:
        return await pd.run(org_id, key, props.configured(defined, account, given))

    return call


async def calls(pd: Pipedream, conn: AsyncConnection, bot: Any) -> dict[str, Call]:
    """The tools the bot may use, each ready to call (a connection removed since is left out)."""
    ids = [uuid.UUID(s["connection_id"]) for s in bot.scopes]
    linked = {str(r.id): r for r in await conn.execute(select(Connection).where(Connection.id.in_(ids)))} if ids else {}
    made: dict[str, Call] = {}
    for scope in bot.scopes:
        found = linked.get(scope["connection_id"])
        if found is None:
            continue
        for key in scope["tools"]:
            defined = (await pd.component(key)).get("configurable_props") or []
            made[key] = _action(pd, bot.org_id, key, defined, found.account_id)
    return made
