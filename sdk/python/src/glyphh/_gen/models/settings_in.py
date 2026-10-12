from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="SettingsIn")


@_attrs_define
class SettingsIn:
    """
    Attributes:
        call_cents (int):
        seconds_per_charge (int):
        top_up_max_cents (int):
        top_up_min_cents (int):
        effective_from (datetime.datetime | None | Unset):
    """

    call_cents: int
    seconds_per_charge: int
    top_up_max_cents: int
    top_up_min_cents: int
    effective_from: datetime.datetime | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        call_cents = self.call_cents

        seconds_per_charge = self.seconds_per_charge

        top_up_max_cents = self.top_up_max_cents

        top_up_min_cents = self.top_up_min_cents

        effective_from: str | Unset | None
        if isinstance(self.effective_from, Unset):
            effective_from = UNSET
        elif isinstance(self.effective_from, datetime.datetime):
            effective_from = self.effective_from.isoformat()
        else:
            effective_from = self.effective_from

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "call_cents": call_cents,
                "seconds_per_charge": seconds_per_charge,
                "top_up_max_cents": top_up_max_cents,
                "top_up_min_cents": top_up_min_cents,
            }
        )
        if effective_from is not UNSET:
            field_dict["effective_from"] = effective_from

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        call_cents = d.pop("call_cents")

        seconds_per_charge = d.pop("seconds_per_charge")

        top_up_max_cents = d.pop("top_up_max_cents")

        top_up_min_cents = d.pop("top_up_min_cents")

        def _parse_effective_from(data: object) -> datetime.datetime | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                effective_from_type_0 = datetime.datetime.fromisoformat(data)

                return effective_from_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        effective_from = _parse_effective_from(d.pop("effective_from", UNSET))

        settings_in = cls(
            call_cents=call_cents,
            seconds_per_charge=seconds_per_charge,
            top_up_max_cents=top_up_max_cents,
            top_up_min_cents=top_up_min_cents,
            effective_from=effective_from,
        )

        settings_in.additional_properties = d
        return settings_in

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
