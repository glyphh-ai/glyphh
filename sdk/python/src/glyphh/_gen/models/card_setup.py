from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="CardSetup")


@_attrs_define
class CardSetup:
    """
    Attributes:
        client_secret (str):
        stripe_publishable_key (str):
    """

    client_secret: str
    stripe_publishable_key: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        client_secret = self.client_secret

        stripe_publishable_key = self.stripe_publishable_key

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "client_secret": client_secret,
                "stripe_publishable_key": stripe_publishable_key,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        client_secret = d.pop("client_secret")

        stripe_publishable_key = d.pop("stripe_publishable_key")

        card_setup = cls(
            client_secret=client_secret,
            stripe_publishable_key=stripe_publishable_key,
        )

        card_setup.additional_properties = d
        return card_setup

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
