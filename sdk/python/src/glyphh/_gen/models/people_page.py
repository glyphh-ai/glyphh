from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.person import Person


T = TypeVar("T", bound="PeoplePage")


@_attrs_define
class PeoplePage:
    """
    Attributes:
        max_seats (int | None):
        people (list[Person]):
        seats_taken (int):
        total (int):
    """

    max_seats: int | None
    people: list[Person]
    seats_taken: int
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        max_seats: int | None
        max_seats = self.max_seats

        people = []
        for people_item_data in self.people:
            people_item = people_item_data.to_dict()
            people.append(people_item)

        seats_taken = self.seats_taken

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "max_seats": max_seats,
                "people": people,
                "seats_taken": seats_taken,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.person import Person

        d = dict(src_dict)

        def _parse_max_seats(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        max_seats = _parse_max_seats(d.pop("max_seats"))

        people = []
        _people = d.pop("people")
        for people_item_data in _people:
            people_item = Person.from_dict(people_item_data)

            people.append(people_item)

        seats_taken = d.pop("seats_taken")

        total = d.pop("total")

        people_page = cls(
            max_seats=max_seats,
            people=people,
            seats_taken=seats_taken,
            total=total,
        )

        people_page.additional_properties = d
        return people_page

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
