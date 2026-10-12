import os
from uuid import UUID

import httpx

from glyphh._billing import AsyncBilling, Billing
from glyphh._calls import (
    ACCEPT_INVITE,
    CHANGE_ME,
    CHANGE_SETTINGS,
    DECLINE_INVITE,
    DISCONNECT_HOST,
    HEALTH,
    LIST_HOSTS,
    LIST_MY_ORGS,
    ME,
    SETTINGS,
    SIGN_OUT_EVERYWHERE,
    Call,
    answer,
)
from glyphh._errors import unreachable
from glyphh._gen.client import Client
from glyphh._gen.models.invite_answer import InviteAnswer
from glyphh._gen.models.profile_change import ProfileChange
from glyphh._gen.models.settings_change import SettingsChange
from glyphh._machines import AsyncMachines, Machines
from glyphh._models import Health, Host, Me, MeOrg, Settings
from glyphh._org import AsyncOrg, Org
from glyphh._threads import AsyncNeedsYou, AsyncThreads, NeedsYou, Threads


def _change(theme: str | None, rail_collapsed: bool | None, page_sizes: dict[str, int] | None) -> SettingsChange:
    given = {"theme": theme, "rail_collapsed": rail_collapsed, "page_sizes": page_sizes}
    return SettingsChange.from_dict({k: v for k, v in given.items() if v is not None})


def _profile(first_name: str | None, last_name: str | None) -> ProfileChange:
    given = {"first_name": first_name, "last_name": last_name}
    return ProfileChange.from_dict({k: v for k, v in given.items() if v is not None})


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
        self.org = Org(self._run)
        self.machines = Machines(self._run)
        self.threads = Threads(self._run)
        self.needs_you = NeedsYou(self._run)
        self.billing = Billing(self._run)

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

    def change_me(self, *, first_name: str | None = None, last_name: str | None = None) -> Me:
        """Change my first or last name (an empty one clears it); answers me as I am now."""
        return self._run(CHANGE_ME, body=_profile(first_name, last_name))  # type: ignore[return-value]

    def sign_out_everywhere(self) -> None:
        """Sign me out of the platform everywhere: every browser and org; connected AI hosts stay connected."""
        self._run(SIGN_OUT_EVERYWHERE)

    def list_my_orgs(self) -> list[MeOrg]:
        """Every org I belong to, my Personal org first."""
        return self._run(LIST_MY_ORGS)  # type: ignore[return-value]

    def accept_invite(self, invite: str) -> str:
        """Accept an invite sent to me: I join its org and keep every other. Answers the org's name."""
        return self._run(ACCEPT_INVITE, body=InviteAnswer(invite=invite))  # type: ignore[return-value]

    def decline_invite(self, invite: str) -> None:
        """Decline an invite sent to me: it closes, and its seat is free again."""
        self._run(DECLINE_INVITE, body=InviteAnswer(invite=invite))

    def settings(self) -> Settings:
        """What the platform remembers for me: the theme, the rail, each list's rows per page."""
        return self._run(SETTINGS)  # type: ignore[return-value]

    def change_settings(
        self, *, theme: str | None = None, rail_collapsed: bool | None = None, page_sizes: dict[str, int] | None = None
    ) -> Settings:
        """Change any of my settings; a list's rows per page are merged in by the list's name."""
        return self._run(CHANGE_SETTINGS, body=_change(theme, rail_collapsed, page_sizes))  # type: ignore[return-value]

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
        self.org = AsyncOrg(self._run)
        self.machines = AsyncMachines(self._run)
        self.threads = AsyncThreads(self._run)
        self.needs_you = AsyncNeedsYou(self._run)
        self.billing = AsyncBilling(self._run)

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

    async def change_me(self, *, first_name: str | None = None, last_name: str | None = None) -> Me:
        return await self._run(CHANGE_ME, body=_profile(first_name, last_name))  # type: ignore[return-value]

    async def sign_out_everywhere(self) -> None:
        await self._run(SIGN_OUT_EVERYWHERE)

    async def list_my_orgs(self) -> list[MeOrg]:
        """Every org I belong to, my Personal org first."""
        return await self._run(LIST_MY_ORGS)  # type: ignore[return-value]

    async def accept_invite(self, invite: str) -> str:
        """Accept an invite sent to me: I join its org and keep every other. Answers the org's name."""
        return await self._run(ACCEPT_INVITE, body=InviteAnswer(invite=invite))  # type: ignore[return-value]

    async def decline_invite(self, invite: str) -> None:
        """Decline an invite sent to me: it closes, and its seat is free again."""
        await self._run(DECLINE_INVITE, body=InviteAnswer(invite=invite))

    async def settings(self) -> Settings:
        """What the platform remembers for me: the theme, the rail, each list's rows per page."""
        return await self._run(SETTINGS)  # type: ignore[return-value]

    async def change_settings(
        self, *, theme: str | None = None, rail_collapsed: bool | None = None, page_sizes: dict[str, int] | None = None
    ) -> Settings:
        """Change any of my settings; a list's rows per page are merged in by the list's name."""
        return await self._run(CHANGE_SETTINGS, body=_change(theme, rail_collapsed, page_sizes))  # type: ignore[return-value]

    async def list_hosts(self) -> list[Host]:
        """The agent hosts (Claude, Codex, ...) connected to my Glyphh."""
        return await self._run(LIST_HOSTS)  # type: ignore[return-value]

    async def disconnect_host(self, host_id: str) -> None:
        """Disconnect one host: its tokens stop working at once; the others are untouched."""
        await self._run(DISCONNECT_HOST, host_id=UUID(host_id))
