"""The org's answers as plain frozen dataclasses."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from glyphh._models import _opt


@dataclass(frozen=True, slots=True)
class OrgView:
    id: str
    name: str
    plan: str
    seats_taken: int
    max_seats: int | None


@dataclass(frozen=True, slots=True)
class Member:
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    disabled: bool
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class InviteView:
    id: str
    email: str
    role: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class CreatedInvite:
    invite: InviteView
    link: str


def org_of(m: Any) -> OrgView:
    seats = m.max_seats if isinstance(m.max_seats, int) else None
    return OrgView(id=str(m.id), name=m.name, plan=m.plan, seats_taken=m.seats_taken, max_seats=seats)


def member_of(m: Any) -> Member:
    return Member(
        id=str(m.id),
        email=m.email,
        first_name=_opt(m.first_name),
        last_name=_opt(m.last_name),
        role=m.role,
        disabled=m.disabled,
        joined_at=m.joined_at,
    )


def invite_of(m: Any) -> InviteView:
    return InviteView(id=str(m.id), email=m.email, role=m.role, expires_at=m.expires_at)


def created_of(m: Any) -> CreatedInvite:
    return CreatedInvite(invite=invite_of(m.invite), link=m.link)
