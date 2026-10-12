from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="SettingsRow")


@_attrs_define
class SettingsRow:
    """
    Attributes:
        call_cents (int):
        created_at (datetime.datetime):
        effective_from (datetime.datetime):
        seconds_per_charge (int):
        set_by (None | str):
        top_up_max_cents (int):
        top_up_min_cents (int):
    """

    call_cents: int
    created_at: datetime.datetime
    effective_from: datetime.datetime
    seconds_per_charge: int
    set_by: str | None
    top_up_max_cents: int
    top_up_min_cents: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        call_cents = self.call_cents

        created_at = self.created_at.isoformat()

        effective_from = self.effective_from.isoformat()

        seconds_per_charge = self.seconds_per_charge

        set_by: str | None
        set_by = self.set_by

        top_up_max_cents = self.top_up_max_cents

        top_up_min_cents = self.top_up_min_cents

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "call_cents": call_cents,
                "created_at": created_at,
                "effective_from": effective_from,
                "seconds_per_charge": seconds_per_charge,
                "set_by": set_by,
                "top_up_max_cents": top_up_max_cents,
                "top_up_min_cents": top_up_min_cents,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        call_cents = d.pop("call_cents")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        effective_from = datetime.datetime.fromisoformat(d.pop("effective_from"))

        seconds_per_charge = d.pop("seconds_per_charge")

        def _parse_set_by(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        set_by = _parse_set_by(d.pop("set_by"))

        top_up_max_cents = d.pop("top_up_max_cents")

        top_up_min_cents = d.pop("top_up_min_cents")

        settings_row = cls(
            call_cents=call_cents,
            created_at=created_at,
            effective_from=effective_from,
            seconds_per_charge=seconds_per_charge,
            set_by=set_by,
            top_up_max_cents=top_up_max_cents,
            top_up_min_cents=top_up_min_cents,
        )

        settings_row.additional_properties = d
        return settings_row

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
