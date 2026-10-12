from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="LedgerEntry")


@_attrs_define
class LedgerEntry:
    """
    Attributes:
        cents (int):
        created_at (datetime.datetime):
        entry (str):
        expires_at (datetime.datetime | None):
        id (UUID):
        note (None | str):
        who (None | str):
    """

    cents: int
    created_at: datetime.datetime
    entry: str
    expires_at: datetime.datetime | None
    id: UUID
    note: str | None
    who: str | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cents = self.cents

        created_at = self.created_at.isoformat()

        entry = self.entry

        expires_at: str | None
        if isinstance(self.expires_at, datetime.datetime):
            expires_at = self.expires_at.isoformat()
        else:
            expires_at = self.expires_at

        id = str(self.id)

        note: str | None
        note = self.note

        who: str | None
        who = self.who

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "cents": cents,
                "created_at": created_at,
                "entry": entry,
                "expires_at": expires_at,
                "id": id,
                "note": note,
                "who": who,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        cents = d.pop("cents")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        entry = d.pop("entry")

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

        id = UUID(d.pop("id"))

        def _parse_note(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        note = _parse_note(d.pop("note"))

        def _parse_who(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        who = _parse_who(d.pop("who"))

        ledger_entry = cls(
            cents=cents,
            created_at=created_at,
            entry=entry,
            expires_at=expires_at,
            id=id,
            note=note,
            who=who,
        )

        ledger_entry.additional_properties = d
        return ledger_entry

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
