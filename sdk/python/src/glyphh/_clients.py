import os
from uuid import UUID

import httpx

from glyphh._calls import DISCONNECT_HOST, HEALTH, LIST_HOSTS, ME, Call, answer
from glyphh._errors import unreachable
from glyphh._gen.client import Client
from glyphh._models import Health, Host, Me


def _client(base_url: str | None, token: str | None, transport: object | None) -> Client:
    url = base_url or os.environ.get("GLYPHH_URL")
    if not url:
        raise ValueError("Glyphh needs a server: pass base_url or set GLYPHH_URL")
    token = token or os.environ.get("GLYPHH_TOKEN")
    headers = {"authorization": f"Bearer {token}"} if token else {}
    return Client(base_url=url, headers=headers, httpx_args={"transport": transport} if transport else {})


class Glyphh:
    """The Glyphh SDK, for ordinary (synchronous) code."""

    def __init__(
        self, base_url: str | None = None, *, token: str | None = None, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._client = _client(base_url, token, transport)

    def _run(self, call: Call, **args: object) -> object:
        try:
            return answer(call, call.operation.sync_detailed(client=self._client, **args))
        except httpx.TransportError as e:
            raise unreachable(e) from e

    def health(self) -> Health:
        """Is the server up, and can it reach its database?"""
        return self._run(HEALTH)  # type: ignore[return-value]

    def me(self) -> Me:
        """Who am I signed in as: my profile, my role, my org and its plan."""
        return self._run(ME)  # type: ignore[return-value]

    def list_hosts(self) -> list[Host]:
        """The agent hosts (Claude, Codex, ...) connected to my Glyphh."""
        return self._run(LIST_HOSTS)  # type: ignore[return-value]

    def disconnect_host(self, host_id: str) -> None:
        """Disconnect one host: its tokens stop working at once; the others are untouched."""
        self._run(DISCONNECT_HOST, host_id=UUID(host_id))


class AsyncGlyphh:
    """The Glyphh SDK, for asyncio code."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = _client(base_url, token, transport)

    async def _run(self, call: Call, **args: object) -> object:
        try:
            return answer(call, await call.operation.asyncio_detailed(client=self._client, **args))
        except httpx.TransportError as e:
            raise unreachable(e) from e

    async def health(self) -> Health:
        """Is the server up, and can it reach its database?"""
        return await self._run(HEALTH)  # type: ignore[return-value]

    async def me(self) -> Me:
        """Who am I signed in as: my profile, my role, my org and its plan."""
        return await self._run(ME)  # type: ignore[return-value]

    async def list_hosts(self) -> list[Host]:
        """The agent hosts (Claude, Codex, ...) connected to my Glyphh."""
        return await self._run(LIST_HOSTS)  # type: ignore[return-value]

    async def disconnect_host(self, host_id: str) -> None:
        """Disconnect one host: its tokens stop working at once; the others are untouched."""
        await self._run(DISCONNECT_HOST, host_id=UUID(host_id))
