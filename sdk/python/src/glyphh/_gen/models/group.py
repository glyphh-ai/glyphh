from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="Group")


@_attrs_define
class Group:
    """
    Attributes:
        id (str):
        name (str):
        share (float):
        accounts (int | None | Unset):
        cached_tokens (int | Unset):  Default: 0.
        connection_calls (int | Unset):  Default: 0.
        cost_cents (int | Unset):  Default: 0.
        duration_ms (int | Unset):  Default: 0.
        errors (int | Unset):  Default: 0.
        input_tokens (int | Unset):  Default: 0.
        kind (None | str | Unset):
        logo (None | str | Unset):
        output_tokens (int | Unset):  Default: 0.
        runs (int | None | Unset):
        sub (None | str | Unset):
        uses (int | Unset):  Default: 0.
    """

    id: str
    name: str
    share: float
    accounts: int | Unset | None = UNSET
    cached_tokens: int | Unset = 0
    connection_calls: int | Unset = 0
    cost_cents: int | Unset = 0
    duration_ms: int | Unset = 0
    errors: int | Unset = 0
    input_tokens: int | Unset = 0
    kind: str | Unset | None = UNSET
    logo: str | Unset | None = UNSET
    output_tokens: int | Unset = 0
    runs: int | Unset | None = UNSET
    sub: str | Unset | None = UNSET
    uses: int | Unset = 0
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        share = self.share

        accounts: int | Unset | None
        if isinstance(self.accounts, Unset):
            accounts = UNSET
        else:
            accounts = self.accounts

        cached_tokens = self.cached_tokens

        connection_calls = self.connection_calls

        cost_cents = self.cost_cents

        duration_ms = self.duration_ms

        errors = self.errors

        input_tokens = self.input_tokens

        kind: str | Unset | None
        if isinstance(self.kind, Unset):
            kind = UNSET
        else:
            kind = self.kind

        logo: str | Unset | None
        if isinstance(self.logo, Unset):
            logo = UNSET
        else:
            logo = self.logo

        output_tokens = self.output_tokens

        runs: int | Unset | None
        if isinstance(self.runs, Unset):
            runs = UNSET
        else:
            runs = self.runs

        sub: str | Unset | None
        if isinstance(self.sub, Unset):
            sub = UNSET
        else:
            sub = self.sub

        uses = self.uses

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "share": share,
            }
        )
        if accounts is not UNSET:
            field_dict["accounts"] = accounts
        if cached_tokens is not UNSET:
            field_dict["cached_tokens"] = cached_tokens
        if connection_calls is not UNSET:
            field_dict["connection_calls"] = connection_calls
        if cost_cents is not UNSET:
            field_dict["cost_cents"] = cost_cents
        if duration_ms is not UNSET:
            field_dict["duration_ms"] = duration_ms
        if errors is not UNSET:
            field_dict["errors"] = errors
        if input_tokens is not UNSET:
            field_dict["input_tokens"] = input_tokens
        if kind is not UNSET:
            field_dict["kind"] = kind
        if logo is not UNSET:
            field_dict["logo"] = logo
        if output_tokens is not UNSET:
            field_dict["output_tokens"] = output_tokens
        if runs is not UNSET:
            field_dict["runs"] = runs
        if sub is not UNSET:
            field_dict["sub"] = sub
        if uses is not UNSET:
            field_dict["uses"] = uses

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        share = d.pop("share")

        def _parse_accounts(data: object) -> int | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        accounts = _parse_accounts(d.pop("accounts", UNSET))

        cached_tokens = d.pop("cached_tokens", UNSET)

        connection_calls = d.pop("connection_calls", UNSET)

        cost_cents = d.pop("cost_cents", UNSET)

        duration_ms = d.pop("duration_ms", UNSET)

        errors = d.pop("errors", UNSET)

        input_tokens = d.pop("input_tokens", UNSET)

        def _parse_kind(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        kind = _parse_kind(d.pop("kind", UNSET))

        def _parse_logo(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        logo = _parse_logo(d.pop("logo", UNSET))

        output_tokens = d.pop("output_tokens", UNSET)

        def _parse_runs(data: object) -> int | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        runs = _parse_runs(d.pop("runs", UNSET))

        def _parse_sub(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        sub = _parse_sub(d.pop("sub", UNSET))

        uses = d.pop("uses", UNSET)

        group = cls(
            id=id,
            name=name,
            share=share,
            accounts=accounts,
            cached_tokens=cached_tokens,
            connection_calls=connection_calls,
            cost_cents=cost_cents,
            duration_ms=duration_ms,
            errors=errors,
            input_tokens=input_tokens,
            kind=kind,
            logo=logo,
            output_tokens=output_tokens,
            runs=runs,
            sub=sub,
            uses=uses,
        )

        group.additional_properties = d
        return group

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
