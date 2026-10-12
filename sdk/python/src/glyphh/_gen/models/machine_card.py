from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.face import Face


T = TypeVar("T", bound="MachineCard")


@_attrs_define
class MachineCard:
    """
    Attributes:
        host (str):
        id (UUID):
        installed (int):
        last_seen_at (datetime.datetime | None):
        name (str):
        needs_you (int):
        online (bool):
        platform (str):
        super_powers (list[Face]):
        version (str):
        working (int):
    """

    host: str
    id: UUID
    installed: int
    last_seen_at: datetime.datetime | None
    name: str
    needs_you: int
    online: bool
    platform: str
    super_powers: list[Face]
    version: str
    working: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        host = self.host

        id = str(self.id)

        installed = self.installed

        last_seen_at: None | str
        if isinstance(self.last_seen_at, datetime.datetime):
            last_seen_at = self.last_seen_at.isoformat()
        else:
            last_seen_at = self.last_seen_at

        name = self.name

        needs_you = self.needs_you

        online = self.online

        platform = self.platform

        super_powers = []
        for super_powers_item_data in self.super_powers:
            super_powers_item = super_powers_item_data.to_dict()
            super_powers.append(super_powers_item)

        version = self.version

        working = self.working

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "host": host,
                "id": id,
                "installed": installed,
                "last_seen_at": last_seen_at,
                "name": name,
                "needs_you": needs_you,
                "online": online,
                "platform": platform,
                "super_powers": super_powers,
                "version": version,
                "working": working,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.face import Face

        d = dict(src_dict)
        host = d.pop("host")

        id = UUID(d.pop("id"))

        installed = d.pop("installed")

        def _parse_last_seen_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                last_seen_at_type_0 = datetime.datetime.fromisoformat(data)

                return last_seen_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        last_seen_at = _parse_last_seen_at(d.pop("last_seen_at"))

        name = d.pop("name")

        needs_you = d.pop("needs_you")

        online = d.pop("online")

        platform = d.pop("platform")

        super_powers = []
        _super_powers = d.pop("super_powers")
        for super_powers_item_data in _super_powers:
            super_powers_item = Face.from_dict(super_powers_item_data)

            super_powers.append(super_powers_item)

        version = d.pop("version")

        working = d.pop("working")

        machine_card = cls(
            host=host,
            id=id,
            installed=installed,
            last_seen_at=last_seen_at,
            name=name,
            needs_you=needs_you,
            online=online,
            platform=platform,
            super_powers=super_powers,
            version=version,
            working=working,
        )

        machine_card.additional_properties = d
        return machine_card

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
