from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Period")


@_attrs_define
class Period:
    """
    Attributes:
        closed (bool):
        end (datetime.datetime):
        included_cents (int):
        invoice_id (None | str):
        invoice_url (None | str):
        start (datetime.datetime):
        used_cents (int):
    """

    closed: bool
    end: datetime.datetime
    included_cents: int
    invoice_id: str | None
    invoice_url: str | None
    start: datetime.datetime
    used_cents: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        closed = self.closed

        end = self.end.isoformat()

        included_cents = self.included_cents

        invoice_id: str | None
        invoice_id = self.invoice_id

        invoice_url: str | None
        invoice_url = self.invoice_url

        start = self.start.isoformat()

        used_cents = self.used_cents

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "closed": closed,
                "end": end,
                "included_cents": included_cents,
                "invoice_id": invoice_id,
                "invoice_url": invoice_url,
                "start": start,
                "used_cents": used_cents,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        closed = d.pop("closed")

        end = datetime.datetime.fromisoformat(d.pop("end"))

        included_cents = d.pop("included_cents")

        def _parse_invoice_id(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        invoice_id = _parse_invoice_id(d.pop("invoice_id"))

        def _parse_invoice_url(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        invoice_url = _parse_invoice_url(d.pop("invoice_url"))

        start = datetime.datetime.fromisoformat(d.pop("start"))

        used_cents = d.pop("used_cents")

        period = cls(
            closed=closed,
            end=end,
            included_cents=included_cents,
            invoice_id=invoice_id,
            invoice_url=invoice_url,
            start=start,
            used_cents=used_cents,
        )

        period.additional_properties = d
        return period

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
