from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="TopUp")


@_attrs_define
class TopUp:
    """
    Attributes:
        amount_cents (int):
        created_at (datetime.datetime):
        expires_at (datetime.datetime | None):
        failure (None | str):
        id (UUID):
        kind (str):
        status (str):
    """

    amount_cents: int
    created_at: datetime.datetime
    expires_at: datetime.datetime | None
    failure: str | None
    id: UUID
    kind: str
    status: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount_cents = self.amount_cents

        created_at = self.created_at.isoformat()

        expires_at: str | None
        if isinstance(self.expires_at, datetime.datetime):
            expires_at = self.expires_at.isoformat()
        else:
            expires_at = self.expires_at

        failure: str | None
        failure = self.failure

        id = str(self.id)

        kind = self.kind

        status = self.status

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "amount_cents": amount_cents,
                "created_at": created_at,
                "expires_at": expires_at,
                "failure": failure,
                "id": id,
                "kind": kind,
                "status": status,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        amount_cents = d.pop("amount_cents")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        def _parse_expires_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                expires_at_type_0 = datetime.datetime.fromisoformat(data)

                return expires_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        expires_at = _parse_expires_at(d.pop("expires_at"))

        def _parse_failure(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        failure = _parse_failure(d.pop("failure"))

        id = UUID(d.pop("id"))

        kind = d.pop("kind")

        status = d.pop("status")

        top_up = cls(
            amount_cents=amount_cents,
            created_at=created_at,
            expires_at=expires_at,
            failure=failure,
            id=id,
            kind=kind,
            status=status,
        )

        top_up.additional_properties = d
        return top_up

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
