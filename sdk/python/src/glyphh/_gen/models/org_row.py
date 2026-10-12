from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgRow")


@_attrs_define
class OrgRow:
    """
    Attributes:
        created_at (datetime.datetime):
        disabled_at (datetime.datetime | None):
        disabled_reason (None | str):
        family (str):
        id (UUID):
        machines (int):
        members (int):
        name (str):
        personal (bool):
        plan (str):
        status (str):
    """

    created_at: datetime.datetime
    disabled_at: datetime.datetime | None
    disabled_reason: str | None
    family: str
    id: UUID
    machines: int
    members: int
    name: str
    personal: bool
    plan: str
    status: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at = self.created_at.isoformat()

        disabled_at: str | None
        if isinstance(self.disabled_at, datetime.datetime):
            disabled_at = self.disabled_at.isoformat()
        else:
            disabled_at = self.disabled_at

        disabled_reason: str | None
        disabled_reason = self.disabled_reason

        family = self.family

        id = str(self.id)

        machines = self.machines

        members = self.members

        name = self.name

        personal = self.personal

        plan = self.plan

        status = self.status

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "created_at": created_at,
                "disabled_at": disabled_at,
                "disabled_reason": disabled_reason,
                "family": family,
                "id": id,
                "machines": machines,
                "members": members,
                "name": name,
                "personal": personal,
                "plan": plan,
                "status": status,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        def _parse_disabled_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                disabled_at_type_0 = datetime.datetime.fromisoformat(data)

                return disabled_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        disabled_at = _parse_disabled_at(d.pop("disabled_at"))

        def _parse_disabled_reason(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        disabled_reason = _parse_disabled_reason(d.pop("disabled_reason"))

        family = d.pop("family")

        id = UUID(d.pop("id"))

        machines = d.pop("machines")

        members = d.pop("members")

        name = d.pop("name")

        personal = d.pop("personal")

        plan = d.pop("plan")

        status = d.pop("status")

        org_row = cls(
            created_at=created_at,
            disabled_at=disabled_at,
            disabled_reason=disabled_reason,
            family=family,
            id=id,
            machines=machines,
            members=members,
            name=name,
            personal=personal,
            plan=plan,
            status=status,
        )

        org_row.additional_properties = d
        return org_row

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
