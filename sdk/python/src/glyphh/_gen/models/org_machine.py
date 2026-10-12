from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgMachine")


@_attrs_define
class OrgMachine:
    """
    Attributes:
        host (str):
        id (UUID):
        last_seen_at (datetime.datetime | None):
        name (str):
        online (bool):
        owner (str):
        platform (str):
        revoked_at (datetime.datetime | None):
        version (None | str):
    """

    host: str
    id: UUID
    last_seen_at: datetime.datetime | None
    name: str
    online: bool
    owner: str
    platform: str
    revoked_at: datetime.datetime | None
    version: str | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        host = self.host

        id = str(self.id)

        last_seen_at: str | None
        if isinstance(self.last_seen_at, datetime.datetime):
            last_seen_at = self.last_seen_at.isoformat()
        else:
            last_seen_at = self.last_seen_at

        name = self.name

        online = self.online

        owner = self.owner

        platform = self.platform

        revoked_at: str | None
        if isinstance(self.revoked_at, datetime.datetime):
            revoked_at = self.revoked_at.isoformat()
        else:
            revoked_at = self.revoked_at

        version: str | None
        version = self.version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "host": host,
                "id": id,
                "last_seen_at": last_seen_at,
                "name": name,
                "online": online,
                "owner": owner,
                "platform": platform,
                "revoked_at": revoked_at,
                "version": version,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        host = d.pop("host")

        id = UUID(d.pop("id"))

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

        online = d.pop("online")

        owner = d.pop("owner")

        platform = d.pop("platform")

        def _parse_revoked_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                revoked_at_type_0 = datetime.datetime.fromisoformat(data)

                return revoked_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        revoked_at = _parse_revoked_at(d.pop("revoked_at"))

        def _parse_version(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        version = _parse_version(d.pop("version"))

        org_machine = cls(
            host=host,
            id=id,
            last_seen_at=last_seen_at,
            name=name,
            online=online,
            owner=owner,
            platform=platform,
            revoked_at=revoked_at,
            version=version,
        )

        org_machine.additional_properties = d
        return org_machine

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
