from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgView")


@_attrs_define
class OrgView:
    """
    Attributes:
        id (UUID):
        max_seats (int | None): null = no limit
        name (str):
        plan (str):
        seats_taken (int):
    """

    id: UUID
    max_seats: int | None
    name: str
    plan: str
    seats_taken: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        max_seats: int | None
        max_seats = self.max_seats

        name = self.name

        plan = self.plan

        seats_taken = self.seats_taken

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "max_seats": max_seats,
                "name": name,
                "plan": plan,
                "seats_taken": seats_taken,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = UUID(d.pop("id"))

        def _parse_max_seats(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        max_seats = _parse_max_seats(d.pop("max_seats"))

        name = d.pop("name")

        plan = d.pop("plan")

        seats_taken = d.pop("seats_taken")

        org_view = cls(
            id=id,
            max_seats=max_seats,
            name=name,
            plan=plan,
            seats_taken=seats_taken,
        )

        org_view.additional_properties = d
        return org_view

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
