from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.have import Have
    from ..models.my_copy import MyCopy
    from ..models.shot import Shot
    from ..models.version_info import VersionInfo


T = TypeVar("T", bound="MarketDetail")


@_attrs_define
class MarketDetail:
    """
    Attributes:
        added (bool):
        adds (int):
        avatar_color (None | str):
        avatar_variant (int | None):
        by (str):
        category (None | str):
        description (str):
        has_icon (bool):
        id (UUID):
        mine (list[MyCopy]):
        name (str):
        needs (list[Have]):
        published_at (datetime.datetime):
        screenshots (list[Shot]):
        summary (str):
        type_ (str):
        version (str):
        versions (list[VersionInfo]):
    """

    added: bool
    adds: int
    avatar_color: str | None
    avatar_variant: int | None
    by: str
    category: str | None
    description: str
    has_icon: bool
    id: UUID
    mine: list[MyCopy]
    name: str
    needs: list[Have]
    published_at: datetime.datetime
    screenshots: list[Shot]
    summary: str
    type_: str
    version: str
    versions: list[VersionInfo]
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

        description = self.description

        has_icon = self.has_icon

        id = str(self.id)

        mine = []
        for mine_item_data in self.mine:
            mine_item = mine_item_data.to_dict()
            mine.append(mine_item)

        name = self.name

        needs = []
        for needs_item_data in self.needs:
            needs_item = needs_item_data.to_dict()
            needs.append(needs_item)

        published_at = self.published_at.isoformat()

        screenshots = []
        for screenshots_item_data in self.screenshots:
            screenshots_item = screenshots_item_data.to_dict()
            screenshots.append(screenshots_item)

        summary = self.summary

        type_ = self.type_

        version = self.version

        versions = []
        for versions_item_data in self.versions:
            versions_item = versions_item_data.to_dict()
            versions.append(versions_item)

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
                "description": description,
                "has_icon": has_icon,
                "id": id,
                "mine": mine,
                "name": name,
                "needs": needs,
                "published_at": published_at,
                "screenshots": screenshots,
                "summary": summary,
                "type": type_,
                "version": version,
                "versions": versions,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.have import Have
        from ..models.my_copy import MyCopy
        from ..models.shot import Shot
        from ..models.version_info import VersionInfo

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

        description = d.pop("description")

        has_icon = d.pop("has_icon")

        id = UUID(d.pop("id"))

        mine = []
        _mine = d.pop("mine")
        for mine_item_data in _mine:
            mine_item = MyCopy.from_dict(mine_item_data)

            mine.append(mine_item)

        name = d.pop("name")

        needs = []
        _needs = d.pop("needs")
        for needs_item_data in _needs:
            needs_item = Have.from_dict(needs_item_data)

            needs.append(needs_item)

        published_at = datetime.datetime.fromisoformat(d.pop("published_at"))

        screenshots = []
        _screenshots = d.pop("screenshots")
        for screenshots_item_data in _screenshots:
            screenshots_item = Shot.from_dict(screenshots_item_data)

            screenshots.append(screenshots_item)

        summary = d.pop("summary")

        type_ = d.pop("type")

        version = d.pop("version")

        versions = []
        _versions = d.pop("versions")
        for versions_item_data in _versions:
            versions_item = VersionInfo.from_dict(versions_item_data)

            versions.append(versions_item)

        market_detail = cls(
            added=added,
            adds=adds,
            avatar_color=avatar_color,
            avatar_variant=avatar_variant,
            by=by,
            category=category,
            description=description,
            has_icon=has_icon,
            id=id,
            mine=mine,
            name=name,
            needs=needs,
            published_at=published_at,
            screenshots=screenshots,
            summary=summary,
            type_=type_,
            version=version,
            versions=versions,
        )

        market_detail.additional_properties = d
        return market_detail

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
