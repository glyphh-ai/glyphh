from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="AutoTopUpCheck")


@_attrs_define
class AutoTopUpCheck:
    """
    Attributes:
        charged_cents (int | None):
        reason (str):
    """

    charged_cents: int | None
    reason: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        charged_cents: int | None
        charged_cents = self.charged_cents

        reason = self.reason

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "charged_cents": charged_cents,
                "reason": reason,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_charged_cents(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        charged_cents = _parse_charged_cents(d.pop("charged_cents"))

        reason = d.pop("reason")

        auto_top_up_check = cls(
            charged_cents=charged_cents,
            reason=reason,
        )

        auto_top_up_check.additional_properties = d
        return auto_top_up_check

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
