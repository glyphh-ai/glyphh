from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.service import Service


T = TypeVar("T", bound="ServicePage")


@_attrs_define
class ServicePage:
    """
    Attributes:
        after (None | str):
        services (list[Service]):
        total (int):
    """

    after: str | None
    services: list[Service]
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        after: str | None
        after = self.after

        services = []
        for services_item_data in self.services:
            services_item = services_item_data.to_dict()
            services.append(services_item)

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "after": after,
                "services": services,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.service import Service

        d = dict(src_dict)

        def _parse_after(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        after = _parse_after(d.pop("after"))

        services = []
        _services = d.pop("services")
        for services_item_data in _services:
            services_item = Service.from_dict(services_item_data)

            services.append(services_item)

        total = d.pop("total")

        service_page = cls(
            after=after,
            services=services,
            total=total,
        )

        service_page.additional_properties = d
        return service_page

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
