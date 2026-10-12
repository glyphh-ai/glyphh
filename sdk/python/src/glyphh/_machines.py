"""My machines: their cards, the super powers installed on each, and opening one."""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from glyphh import _machine_models as models
from glyphh._calls import Call
from glyphh._gen.api.machines import list_installed_super_powers, list_machines, open_machine
from glyphh._gen.models.installed_page import InstalledPage
from glyphh._gen.models.launch import Launch
from glyphh._gen.models.list_installed_super_powers_status_type_0 import ListInstalledSuperPowersStatusType0 as Status
from glyphh._gen.models.machine_page import MachinePage
from glyphh._gen.models.open_in import OpenIn
from glyphh._gen.types import UNSET

LIST = Call(list_machines, lambda r: isinstance(r.parsed, MachinePage), models.machine_page_of)
INSTALLED = Call(list_installed_super_powers, lambda r: isinstance(r.parsed, InstalledPage), models.installed_of)
OPEN = Call(open_machine, lambda r: isinstance(r.parsed, Launch), models.launch_of)


def _query(machine_id: str, q: str, status: str | None, page: int, size: int) -> dict[str, Any]:
    return {
        "machine_id": UUID(machine_id),
        "q": q,
        "status": Status(status) if status else UNSET,
        "page": page,
        "size": size,
    }


def _open(machine_id: str, super_power: str | None) -> dict[str, Any]:
    return {"machine_id": UUID(machine_id), "body": OpenIn(super_power=UUID(super_power) if super_power else None)}


class Machines:
    """`Glyphh(...).machines`: the same calls for ordinary code."""

    def __init__(self, run: Callable[..., Any]) -> None:
        self._run = run

    def list(self, page: int = 1, size: int = 12) -> Any:
        """My machines, connected first, each with its 8 most recently active super powers and their counts."""
        return self._run(LIST, page=page, size=size)

    def super_powers(
        self, machine_id: str, *, q: str = "", status: str | None = None, page: int = 1, size: int = 24
    ) -> Any:
        """Every super power on one machine, searched by name or what it does, filtered by status, a page at a time."""
        return self._run(INSTALLED, **_query(machine_id, q, status, page, size))

    def open(self, machine_id: str, super_power: str | None = None) -> Any:
        """The machine's page on the platform, and a one-minute, one-time ticket for a Claude panel showing it."""
        return self._run(OPEN, **_open(machine_id, super_power))


class AsyncMachines:
    """`AsyncGlyphh(...).machines`: the same calls for asyncio code."""

    def __init__(self, run: Callable[..., Awaitable[Any]]) -> None:
        self._run = run

    async def list(self, page: int = 1, size: int = 12) -> Any:
        return await self._run(LIST, page=page, size=size)

    async def super_powers(
        self, machine_id: str, *, q: str = "", status: str | None = None, page: int = 1, size: int = 24
    ) -> Any:
        return await self._run(INSTALLED, **_query(machine_id, q, status, page, size))

    async def open(self, machine_id: str, super_power: str | None = None) -> Any:
        return await self._run(OPEN, **_open(machine_id, super_power))
