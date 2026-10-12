from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.plan_change_state import PlanChangeState
from ..types import UNSET, Unset

T = TypeVar("T", bound="PlanChange")


@_attrs_define
class PlanChange:
    """
    Attributes:
        state (PlanChangeState):
        applies_at (datetime.datetime | None | Unset):
        cancel_url (None | str | Unset):
        client_secret (None | str | Unset):
        return_url (None | str | Unset):
        stripe_publishable_key (None | str | Unset):
    """

    state: PlanChangeState
    applies_at: datetime.datetime | Unset | None = UNSET
    cancel_url: str | Unset | None = UNSET
    client_secret: str | Unset | None = UNSET
    return_url: str | Unset | None = UNSET
    stripe_publishable_key: str | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        state = self.state.value

        applies_at: str | Unset | None
        if isinstance(self.applies_at, Unset):
            applies_at = UNSET
        elif isinstance(self.applies_at, datetime.datetime):
            applies_at = self.applies_at.isoformat()
        else:
            applies_at = self.applies_at

        cancel_url: str | Unset | None
        if isinstance(self.cancel_url, Unset):
            cancel_url = UNSET
        else:
            cancel_url = self.cancel_url

        client_secret: str | Unset | None
        if isinstance(self.client_secret, Unset):
            client_secret = UNSET
        else:
            client_secret = self.client_secret

        return_url: str | Unset | None
        if isinstance(self.return_url, Unset):
            return_url = UNSET
        else:
            return_url = self.return_url

        stripe_publishable_key: str | Unset | None
        if isinstance(self.stripe_publishable_key, Unset):
            stripe_publishable_key = UNSET
        else:
            stripe_publishable_key = self.stripe_publishable_key

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "state": state,
            }
        )
        if applies_at is not UNSET:
            field_dict["applies_at"] = applies_at
        if cancel_url is not UNSET:
            field_dict["cancel_url"] = cancel_url
        if client_secret is not UNSET:
            field_dict["client_secret"] = client_secret
        if return_url is not UNSET:
            field_dict["return_url"] = return_url
        if stripe_publishable_key is not UNSET:
            field_dict["stripe_publishable_key"] = stripe_publishable_key

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        state = PlanChangeState(d.pop("state"))

        def _parse_applies_at(data: object) -> datetime.datetime | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                applies_at_type_0 = datetime.datetime.fromisoformat(data)

                return applies_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        applies_at = _parse_applies_at(d.pop("applies_at", UNSET))

        def _parse_cancel_url(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        cancel_url = _parse_cancel_url(d.pop("cancel_url", UNSET))

        def _parse_client_secret(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        client_secret = _parse_client_secret(d.pop("client_secret", UNSET))

        def _parse_return_url(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        return_url = _parse_return_url(d.pop("return_url", UNSET))

        def _parse_stripe_publishable_key(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        stripe_publishable_key = _parse_stripe_publishable_key(d.pop("stripe_publishable_key", UNSET))

        plan_change = cls(
            state=state,
            applies_at=applies_at,
            cancel_url=cancel_url,
            client_secret=client_secret,
            return_url=return_url,
            stripe_publishable_key=stripe_publishable_key,
        )

        plan_change.additional_properties = d
        return plan_change

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
