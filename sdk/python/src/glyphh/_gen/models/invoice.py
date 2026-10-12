from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Invoice")


@_attrs_define
class Invoice:
    """
    Attributes:
        amount_cents (int):
        created_at (datetime.datetime):
        description (None | str):
        id (str):
        number (None | str):
        pdf_url (None | str):
        status (str):
        view_url (None | str):
    """

    amount_cents: int
    created_at: datetime.datetime
    description: str | None
    id: str
    number: str | None
    pdf_url: str | None
    status: str
    view_url: str | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount_cents = self.amount_cents

        created_at = self.created_at.isoformat()

        description: str | None
        description = self.description

        id = self.id

        number: str | None
        number = self.number

        pdf_url: str | None
        pdf_url = self.pdf_url

        status = self.status

        view_url: str | None
        view_url = self.view_url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "amount_cents": amount_cents,
                "created_at": created_at,
                "description": description,
                "id": id,
                "number": number,
                "pdf_url": pdf_url,
                "status": status,
                "view_url": view_url,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        amount_cents = d.pop("amount_cents")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        def _parse_description(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        description = _parse_description(d.pop("description"))

        id = d.pop("id")

        def _parse_number(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        number = _parse_number(d.pop("number"))

        def _parse_pdf_url(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        pdf_url = _parse_pdf_url(d.pop("pdf_url"))

        status = d.pop("status")

        def _parse_view_url(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        view_url = _parse_view_url(d.pop("view_url"))

        invoice = cls(
            amount_cents=amount_cents,
            created_at=created_at,
            description=description,
            id=id,
            number=number,
            pdf_url=pdf_url,
            status=status,
            view_url=view_url,
        )

        invoice.additional_properties = d
        return invoice

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
