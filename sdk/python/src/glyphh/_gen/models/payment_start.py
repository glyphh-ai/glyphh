from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="PaymentStart")


@_attrs_define
class PaymentStart:
    """What the page needs to show Stripe's Payment Element and confirm the payment there.

    Attributes:
        amount_cents (int):
        client_secret (str):
        payment_id (UUID):
        stripe_publishable_key (str):
        return_url (None | str | Unset):
    """

    amount_cents: int
    client_secret: str
    payment_id: UUID
    stripe_publishable_key: str
    return_url: str | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount_cents = self.amount_cents

        client_secret = self.client_secret

        payment_id = str(self.payment_id)

        stripe_publishable_key = self.stripe_publishable_key

        return_url: str | Unset | None
        if isinstance(self.return_url, Unset):
            return_url = UNSET
        else:
            return_url = self.return_url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "amount_cents": amount_cents,
                "client_secret": client_secret,
                "payment_id": payment_id,
                "stripe_publishable_key": stripe_publishable_key,
            }
        )
        if return_url is not UNSET:
            field_dict["return_url"] = return_url

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        amount_cents = d.pop("amount_cents")

        client_secret = d.pop("client_secret")

        payment_id = UUID(d.pop("payment_id"))

        stripe_publishable_key = d.pop("stripe_publishable_key")

        def _parse_return_url(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        return_url = _parse_return_url(d.pop("return_url", UNSET))

        payment_start = cls(
            amount_cents=amount_cents,
            client_secret=client_secret,
            payment_id=payment_id,
            stripe_publishable_key=stripe_publishable_key,
            return_url=return_url,
        )

        payment_start.additional_properties = d
        return payment_start

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
