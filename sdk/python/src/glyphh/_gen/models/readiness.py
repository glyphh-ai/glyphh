from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.missing import Missing


T = TypeVar("T", bound="Readiness")


@_attrs_define
class Readiness:
    """
    Attributes:
        missing (list[Missing]):
        ready (bool):
    """

    missing: list[Missing]
    ready: bool
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        missing = []
        for missing_item_data in self.missing:
            missing_item = missing_item_data.to_dict()
            missing.append(missing_item)

        ready = self.ready

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "missing": missing,
                "ready": ready,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.missing import Missing

        d = dict(src_dict)
        missing = []
        _missing = d.pop("missing")
        for missing_item_data in _missing:
            missing_item = Missing.from_dict(missing_item_data)

            missing.append(missing_item)

        ready = d.pop("ready")

        readiness = cls(
            missing=missing,
            ready=ready,
        )

        readiness.additional_properties = d
        return readiness

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
