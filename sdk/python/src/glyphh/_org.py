"""My org: plan and seats, members, invites. Changes are for org admins."""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from glyphh import _org_calls as calls
from glyphh._calls import Call
from glyphh._gen.models.member_change import MemberChange
from glyphh._gen.models.member_change_role_type_0 import MemberChangeRoleType0
from glyphh._gen.models.new_invite import NewInvite
from glyphh._gen.models.new_invite_role import NewInviteRole
from glyphh._gen.models.rename_org import RenameOrg
from glyphh._gen.types import UNSET


def _change(role: str | None, disabled: bool | None) -> MemberChange:
    return MemberChange(
        role=MemberChangeRoleType0(role) if role else UNSET, disabled=UNSET if disabled is None else disabled
    )


class Org:
    """`Glyphh(...).org`: the same calls for ordinary code."""

    def __init__(self, run: Callable[..., Any]) -> None:
        self._run = run

    def get(self) -> Any:
        return self._run(calls.GET)

    def rename(self, name: str) -> Any:
        return self._run(calls.RENAME, body=RenameOrg(name=name))

    def list_members(self) -> Any:
        return self._run(calls.MEMBERS)

    def update_member(self, member_id: str, *, role: str | None = None, disabled: bool | None = None) -> Any:
        return self._run(calls.UPDATE_MEMBER, member_id=UUID(member_id), body=_change(role, disabled))

    def remove_member(self, member_id: str) -> None:
        self._run(calls.REMOVE_MEMBER, member_id=UUID(member_id))

    def list_invites(self) -> Any:
        return self._run(calls.INVITES)

    def invite(self, email: str, role: str = "user") -> Any:
        """Invite someone by email. The answer's link is shown once: send it to them."""
        return self._run(calls.INVITE, body=NewInvite(email=email, role=NewInviteRole(role)))

    def revoke_invite(self, invite_id: str) -> None:
        self._run(calls.REVOKE_INVITE, invite_id=UUID(invite_id))


class AsyncOrg:
    """`AsyncGlyphh(...).org`: the same calls for asyncio code."""

    def __init__(self, run: Callable[..., Awaitable[Any]]) -> None:
        self._run = run

    async def get(self) -> Any:
        return await self._run(calls.GET)

    async def rename(self, name: str) -> Any:
        return await self._run(calls.RENAME, body=RenameOrg(name=name))

    async def list_members(self) -> Any:
        return await self._run(calls.MEMBERS)

    async def update_member(self, member_id: str, *, role: str | None = None, disabled: bool | None = None) -> Any:
        return await self._run(calls.UPDATE_MEMBER, member_id=UUID(member_id), body=_change(role, disabled))

    async def remove_member(self, member_id: str) -> None:
        await self._run(calls.REMOVE_MEMBER, member_id=UUID(member_id))

    async def list_invites(self) -> Any:
        return await self._run(calls.INVITES)

    async def invite(self, email: str, role: str = "user") -> Any:
        return await self._run(calls.INVITE, body=NewInvite(email=email, role=NewInviteRole(role)))

    async def revoke_invite(self, invite_id: str) -> None:
        await self._run(calls.REVOKE_INVITE, invite_id=UUID(invite_id))


__all__ = ["AsyncOrg", "Call", "Org"]
