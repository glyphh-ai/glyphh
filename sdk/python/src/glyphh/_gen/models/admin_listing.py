from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="AdminListing")


@_attrs_define
class AdminListing:
    """
    Attributes:
        category (None | str):
        created_at (datetime.datetime):
        featured (bool):
        featured_sort (int):
        id (UUID):
        installs (int):
        kind (str):
        maker (str):
        name (str):
        org (str):
        published (bool):
        reach (str):
        unpublished_at (datetime.datetime | None):
    """

    category: str | None
    created_at: datetime.datetime
    featured: bool
    featured_sort: int
    id: UUID
    installs: int
    kind: str
    maker: str
    name: str
    org: str
    published: bool
    reach: str
    unpublished_at: datetime.datetime | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        category: str | None
        category = self.category

        created_at = self.created_at.isoformat()

        featured = self.featured

        featured_sort = self.featured_sort

        id = str(self.id)

        installs = self.installs

        kind = self.kind

        maker = self.maker

        name = self.name

        org = self.org

        published = self.published

        reach = self.reach

        unpublished_at: str | None
        if isinstance(self.unpublished_at, datetime.datetime):
            unpublished_at = self.unpublished_at.isoformat()
        else:
            unpublished_at = self.unpublished_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "category": category,
                "created_at": created_at,
                "featured": featured,
                "featured_sort": featured_sort,
                "id": id,
                "installs": installs,
                "kind": kind,
                "maker": maker,
                "name": name,
                "org": org,
                "published": published,
                "reach": reach,
                "unpublished_at": unpublished_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_category(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        category = _parse_category(d.pop("category"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        featured = d.pop("featured")

        featured_sort = d.pop("featured_sort")

        id = UUID(d.pop("id"))

        installs = d.pop("installs")

        kind = d.pop("kind")

        maker = d.pop("maker")

        name = d.pop("name")

        org = d.pop("org")

        published = d.pop("published")

        reach = d.pop("reach")

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

        admin_listing = cls(
            category=category,
            created_at=created_at,
            featured=featured,
            featured_sort=featured_sort,
            id=id,
            installs=installs,
            kind=kind,
            maker=maker,
            name=name,
            org=org,
            published=published,
            reach=reach,
            unpublished_at=unpublished_at,
        )

        admin_listing.additional_properties = d
        return admin_listing

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
