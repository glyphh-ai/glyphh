from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.user import User


T = TypeVar("T", bound="Place")


@_attrs_define
class Place:
    """
    Attributes:
        id (UUID):
        machine (str):
        machine_id (UUID):
        machine_last_seen_at (datetime.datetime | None):
        machine_online (bool):
        name (str):
        path (None | str):
        profile (None | str):
        signed_in_sites (list[str]):
        used_by (list[User]):
    """

    id: UUID
    machine: str
    machine_id: UUID
    machine_last_seen_at: datetime.datetime | None
    machine_online: bool
    name: str
    path: str | None
    profile: str | None
    signed_in_sites: list[str]
    used_by: list[User]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        machine = self.machine

        machine_id = str(self.machine_id)

        machine_last_seen_at: str | None
        if isinstance(self.machine_last_seen_at, datetime.datetime):
            machine_last_seen_at = self.machine_last_seen_at.isoformat()
        else:
            machine_last_seen_at = self.machine_last_seen_at

        machine_online = self.machine_online

        name = self.name

        path: str | None
        path = self.path

        profile: str | None
        profile = self.profile

        signed_in_sites = self.signed_in_sites

        used_by = []
        for used_by_item_data in self.used_by:
            used_by_item = used_by_item_data.to_dict()
            used_by.append(used_by_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "machine": machine,
                "machine_id": machine_id,
                "machine_last_seen_at": machine_last_seen_at,
                "machine_online": machine_online,
                "name": name,
                "path": path,
                "profile": profile,
                "signed_in_sites": signed_in_sites,
                "used_by": used_by,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.user import User

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        machine = d.pop("machine")

        machine_id = UUID(d.pop("machine_id"))

        def _parse_machine_last_seen_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                machine_last_seen_at_type_0 = datetime.datetime.fromisoformat(data)

                return machine_last_seen_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        machine_last_seen_at = _parse_machine_last_seen_at(d.pop("machine_last_seen_at"))

        machine_online = d.pop("machine_online")

        name = d.pop("name")

        def _parse_path(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        path = _parse_path(d.pop("path"))

        def _parse_profile(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        profile = _parse_profile(d.pop("profile"))

        signed_in_sites = cast(list[str], d.pop("signed_in_sites"))

        used_by = []
        _used_by = d.pop("used_by")
        for used_by_item_data in _used_by:
            used_by_item = User.from_dict(used_by_item_data)

            used_by.append(used_by_item)

        place = cls(
            id=id,
            machine=machine,
            machine_id=machine_id,
            machine_last_seen_at=machine_last_seen_at,
            machine_online=machine_online,
            name=name,
            path=path,
            profile=profile,
            signed_in_sites=signed_in_sites,
            used_by=used_by,
        )

        place.additional_properties = d
        return place

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
