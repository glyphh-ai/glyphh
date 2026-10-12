from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Comment")


@_attrs_define
class Comment:
    """
    Attributes:
        body (str):
        created_at (datetime.datetime):
        id (UUID):
        who (None | str):
    """

    body: str
    created_at: datetime.datetime
    id: UUID
    who: str | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        body = self.body

        created_at = self.created_at.isoformat()

        id = str(self.id)

        who: str | None
        who = self.who

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "body": body,
                "created_at": created_at,
                "id": id,
                "who": who,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        body = d.pop("body")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        id = UUID(d.pop("id"))

        def _parse_who(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        who = _parse_who(d.pop("who"))

        comment = cls(
            body=body,
            created_at=created_at,
            id=id,
            who=who,
        )

        comment.additional_properties = d
        return comment

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
