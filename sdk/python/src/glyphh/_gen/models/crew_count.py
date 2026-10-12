from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.crew_face import CrewFace


T = TypeVar("T", bound="CrewCount")


@_attrs_define
class CrewCount:
    """
    Attributes:
        super_power (CrewFace): A super power as a thread shows it: its face and its name.
        threads (int):
    """

    super_power: CrewFace
    threads: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        super_power = self.super_power.to_dict()

        threads = self.threads

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "super_power": super_power,
                "threads": threads,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.crew_face import CrewFace

        d = dict(src_dict)
        super_power = CrewFace.from_dict(d.pop("super_power"))

        threads = d.pop("threads")

        crew_count = cls(
            super_power=super_power,
            threads=threads,
        )

        crew_count.additional_properties = d
        return crew_count

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
