from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="MarketCard")


@_attrs_define
class MarketCard:
    """
    Attributes:
        added (bool):
        adds (int):
        avatar_color (None | str):
        avatar_variant (int | None):
        by (str):
        category (None | str):
        has_icon (bool):
        id (UUID):
        name (str):
        published_at (datetime.datetime):
        summary (str):
        type_ (str):
        version (str):
    """

    added: bool
    adds: int
    avatar_color: str | None
    avatar_variant: int | None
    by: str
    category: str | None
    has_icon: bool
    id: UUID
    name: str
    published_at: datetime.datetime
    summary: str
    type_: str
    version: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        added = self.added

        adds = self.adds

        avatar_color: str | None
        avatar_color = self.avatar_color

        avatar_variant: int | None
        avatar_variant = self.avatar_variant

        by = self.by

        category: str | None
        category = self.category

        has_icon = self.has_icon

        id = str(self.id)

        name = self.name

        published_at = self.published_at.isoformat()

        summary = self.summary

        type_ = self.type_

        version = self.version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "added": added,
                "adds": adds,
                "avatar_color": avatar_color,
                "avatar_variant": avatar_variant,
                "by": by,
                "category": category,
                "has_icon": has_icon,
                "id": id,
                "name": name,
                "published_at": published_at,
                "summary": summary,
                "type": type_,
                "version": version,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        added = d.pop("added")

        adds = d.pop("adds")

        def _parse_avatar_color(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        avatar_color = _parse_avatar_color(d.pop("avatar_color"))

        def _parse_avatar_variant(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        avatar_variant = _parse_avatar_variant(d.pop("avatar_variant"))

        by = d.pop("by")

        def _parse_category(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        category = _parse_category(d.pop("category"))

        has_icon = d.pop("has_icon")

        id = UUID(d.pop("id"))

        name = d.pop("name")

        published_at = datetime.datetime.fromisoformat(d.pop("published_at"))

        summary = d.pop("summary")

        type_ = d.pop("type")

        version = d.pop("version")

        market_card = cls(
            added=added,
            adds=adds,
            avatar_color=avatar_color,
            avatar_variant=avatar_variant,
            by=by,
            category=category,
            has_icon=has_icon,
            id=id,
            name=name,
            published_at=published_at,
            summary=summary,
            type_=type_,
            version=version,
        )

        market_card.additional_properties = d
        return market_card

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
