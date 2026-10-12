"""What the SDK answers with: plain frozen dataclasses, so callers never touch the generated client."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from glyphh._gen.models.health import Health as _Health
from glyphh._gen.models.host import Host as _Host
from glyphh._gen.models.me import Me as _Me
from glyphh._gen.models.me_org import MeOrg as _MeOrg
from glyphh._gen.models.settings import Settings as _Settings
from glyphh._gen.types import Unset


@dataclass(frozen=True, slots=True)
class Health:
    status: Literal["ok", "degraded"]
    version: str
    database: bool


@dataclass(frozen=True, slots=True)
class MeOrg:
    id: str
    name: str
    plan: str
    personal: bool
    role: str
    people: int


@dataclass(frozen=True, slots=True)
class Settings:
    """What the platform remembers for me: the theme, the rail, each list's rows per page."""

    theme: str
    rail_collapsed: bool
    page_sizes: dict[str, int]


@dataclass(frozen=True, slots=True)
class Me:
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    image_url: str | None
    signed_in_with: str | None
    role: str
    org: MeOrg


@dataclass(frozen=True, slots=True)
class Host:
    id: str
    name: str
    connected_at: datetime
    org: str | None


def _opt(value: object) -> str | None:
    return None if value is None or isinstance(value, Unset) else str(value)


def health_of(m: _Health) -> Health:
    return Health(status=m.status.value, version=m.version, database=m.database)


def me_of(m: _Me) -> Me:
    return Me(
        id=str(m.id),
        email=m.email,
        first_name=_opt(m.first_name),
        last_name=_opt(m.last_name),
        image_url=_opt(m.image_url),
        signed_in_with=_opt(m.signed_in_with),
        role=m.role,
        org=org_of(m.org),
    )


def org_of(m: _MeOrg) -> MeOrg:
    return MeOrg(id=str(m.id), name=m.name, plan=m.plan, personal=m.personal, role=m.role, people=m.people)


def settings_of(m: _Settings) -> Settings:
    sizes = m.to_dict()["page_sizes"] if not isinstance(m.page_sizes, Unset) else {}
    return Settings(
        theme=str(m.theme.value if not isinstance(m.theme, Unset) else "system"),
        rail_collapsed=bool(m.rail_collapsed),
        page_sizes={k: int(v) for k, v in sizes.items()},
    )


def host_of(m: _Host) -> Host:
    return Host(id=str(m.id), name=m.name, connected_at=m.connected_at, org=_opt(m.org))
