from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.version_detail import VersionDetail
    from ..models.version_info import VersionInfo


T = TypeVar("T", bound="ListingView")


@_attrs_define
class ListingView:
    """
    Attributes:
        adds (int):
        by (str):
        category (None | str):
        description (str):
        has_icon (bool):
        history (list[VersionInfo]):
        id (UUID):
        kind (str):
        name (str):
        open_ (None | VersionDetail):
        org (str):
        published (None | VersionInfo):
        reach (str):
        summary (str):
        target_id (None | UUID):
        unpublished_at (datetime.datetime | None):
    """

    adds: int
    by: str
    category: str | None
    description: str
    has_icon: bool
    history: list[VersionInfo]
    id: UUID
    kind: str
    name: str
    open_: VersionDetail | None
    org: str
    published: VersionInfo | None
    reach: str
    summary: str
    target_id: UUID | None
    unpublished_at: datetime.datetime | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.version_detail import VersionDetail
        from ..models.version_info import VersionInfo

        adds = self.adds

        by = self.by

        category: str | None
        category = self.category

        description = self.description

        has_icon = self.has_icon

        history = []
        for history_item_data in self.history:
            history_item = history_item_data.to_dict()
            history.append(history_item)

        id = str(self.id)

        kind = self.kind

        name = self.name

        open_: dict[str, Any] | None
        if isinstance(self.open_, VersionDetail):
            open_ = self.open_.to_dict()
        else:
            open_ = self.open_

        org = self.org

        published: dict[str, Any] | None
        if isinstance(self.published, VersionInfo):
            published = self.published.to_dict()
        else:
            published = self.published

        reach = self.reach

        summary = self.summary

        target_id: str | None
        if isinstance(self.target_id, UUID):
            target_id = str(self.target_id)
        else:
            target_id = self.target_id

        unpublished_at: str | None
        if isinstance(self.unpublished_at, datetime.datetime):
            unpublished_at = self.unpublished_at.isoformat()
        else:
            unpublished_at = self.unpublished_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "adds": adds,
                "by": by,
                "category": category,
                "description": description,
                "has_icon": has_icon,
                "history": history,
                "id": id,
                "kind": kind,
                "name": name,
                "open": open_,
                "org": org,
                "published": published,
                "reach": reach,
                "summary": summary,
                "target_id": target_id,
                "unpublished_at": unpublished_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.version_detail import VersionDetail
        from ..models.version_info import VersionInfo

        d = dict(src_dict)
        adds = d.pop("adds")

        by = d.pop("by")

        def _parse_category(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        category = _parse_category(d.pop("category"))

        description = d.pop("description")

        has_icon = d.pop("has_icon")

        history = []
        _history = d.pop("history")
        for history_item_data in _history:
            history_item = VersionInfo.from_dict(history_item_data)

            history.append(history_item)

        id = UUID(d.pop("id"))

        kind = d.pop("kind")

        name = d.pop("name")

        def _parse_open_(data: object) -> VersionDetail | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                open_type_0 = VersionDetail.from_dict(data)

                return open_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | VersionDetail, data)

        open_ = _parse_open_(d.pop("open"))

        org = d.pop("org")

        def _parse_published(data: object) -> VersionInfo | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                published_type_0 = VersionInfo.from_dict(data)

                return published_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | VersionInfo, data)

        published = _parse_published(d.pop("published"))

        reach = d.pop("reach")

        summary = d.pop("summary")

        def _parse_target_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                target_id_type_0 = UUID(data)

                return target_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        target_id = _parse_target_id(d.pop("target_id"))

        def _parse_unpublished_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                unpublished_at_type_0 = datetime.datetime.fromisoformat(data)

                return unpublished_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        unpublished_at = _parse_unpublished_at(d.pop("unpublished_at"))

        listing_view = cls(
            adds=adds,
            by=by,
            category=category,
            description=description,
            has_icon=has_icon,
            history=history,
            id=id,
            kind=kind,
            name=name,
            open_=open_,
            org=org,
            published=published,
            reach=reach,
            summary=summary,
            target_id=target_id,
            unpublished_at=unpublished_at,
        )

        listing_view.additional_properties = d
        return listing_view

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
