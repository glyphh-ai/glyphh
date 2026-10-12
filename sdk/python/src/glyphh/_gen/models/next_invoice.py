from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="NextInvoice")


@_attrs_define
class NextInvoice:
    """
    Attributes:
        amount_cents (int):
        at (datetime.datetime | None):
        prorated_cents (int):
    """

    amount_cents: int
    at: datetime.datetime | None
    prorated_cents: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount_cents = self.amount_cents

        at: str | None
        if isinstance(self.at, datetime.datetime):
            at = self.at.isoformat()
        else:
            at = self.at

        prorated_cents = self.prorated_cents

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "amount_cents": amount_cents,
                "at": at,
                "prorated_cents": prorated_cents,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        amount_cents = d.pop("amount_cents")

        def _parse_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                at_type_0 = datetime.datetime.fromisoformat(data)

                return at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        at = _parse_at(d.pop("at"))

        prorated_cents = d.pop("prorated_cents")

        next_invoice = cls(
            amount_cents=amount_cents,
            at=at,
            prorated_cents=prorated_cents,
        )

        next_invoice.additional_properties = d
        return next_invoice

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
