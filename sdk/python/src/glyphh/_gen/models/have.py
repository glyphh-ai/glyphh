from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Have")


@_attrs_define
class Have:
    """
    Attributes:
        have (bool):
        kind (str):
        need (str):
        optional (bool):
    """

    have: bool
    kind: str
    need: str
    optional: bool
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        have = self.have

        kind = self.kind

        need = self.need

        optional = self.optional

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "have": have,
                "kind": kind,
                "need": need,
                "optional": optional,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        have = d.pop("have")

        kind = d.pop("kind")

        need = d.pop("need")

        optional = d.pop("optional")

        have = cls(
            have=have,
            kind=kind,
            need=need,
            optional=optional,
        )

        have.additional_properties = d
        return have

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
