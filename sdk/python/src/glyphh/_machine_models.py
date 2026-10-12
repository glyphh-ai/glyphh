"""My machines' answers as plain frozen dataclasses."""

from dataclasses import dataclass
from datetime import datetime

from glyphh._gen.models.face import Face as _Face
from glyphh._gen.models.installed_page import InstalledPage as _InstalledPage
from glyphh._gen.models.launch import Launch as _Launch
from glyphh._gen.models.machine_card import MachineCard as _MachineCard
from glyphh._gen.models.machine_page import MachinePage as _MachinePage
from glyphh._models import _opt


@dataclass(frozen=True, slots=True)
class Face:
    """A super power as a machine shows it: its face, its name, what it is doing there."""

    id: str
    name: str
    description: str
    avatar_variant: int
    avatar_color: str | None
    status: str
    last_active_at: datetime | None


@dataclass(frozen=True, slots=True)
class MachineCard:
    id: str
    name: str
    host: str
    platform: str
    version: str
    online: bool
    last_seen_at: datetime | None
    super_powers: list[Face]
    installed: int
    working: int
    needs_you: int


@dataclass(frozen=True, slots=True)
class MachinePage:
    machines: list[MachineCard]
    total: int
    online: int


@dataclass(frozen=True, slots=True)
class InstalledPage:
    machine: str
    super_powers: list[Face]
    total: int
    counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class Launch:
    url: str
    expires_at: datetime


def _when(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def face_of(m: _Face) -> Face:
    return Face(
        id=str(m.id),
        name=m.name,
        description=m.description,
        avatar_variant=m.avatar_variant,
        avatar_color=_opt(m.avatar_color),
        status=m.status,
        last_active_at=_when(m.last_active_at),
    )


def card_of(m: _MachineCard) -> MachineCard:
    return MachineCard(
        id=str(m.id),
        name=m.name,
        host=m.host,
        platform=m.platform,
        version=m.version,
        online=m.online,
        last_seen_at=_when(m.last_seen_at),
        super_powers=[face_of(f) for f in m.super_powers],
        installed=m.installed,
        working=m.working,
        needs_you=m.needs_you,
    )


def machine_page_of(m: _MachinePage) -> MachinePage:
    return MachinePage(machines=[card_of(c) for c in m.machines], total=m.total, online=m.online)


def installed_of(m: _InstalledPage) -> InstalledPage:
    return InstalledPage(
        machine=m.machine,
        super_powers=[face_of(f) for f in m.super_powers],
        total=m.total,
        counts=dict(m.counts.additional_properties),
    )


def launch_of(m: _Launch) -> Launch:
    return Launch(url=m.url, expires_at=m.expires_at)
