from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.new_listing_reach import NewListingReach
from ..types import UNSET, Unset

T = TypeVar("T", bound="NewListing")


@_attrs_define
class NewListing:
    """
    Attributes:
        power_id (None | Unset | UUID):
        reach (NewListingReach | Unset):  Default: NewListingReach.MARKETPLACE.
        super_power_id (None | Unset | UUID):
    """

    power_id: Unset | UUID | None = UNSET
    reach: NewListingReach | Unset = NewListingReach.MARKETPLACE
    super_power_id: Unset | UUID | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        power_id: str | Unset | None
        if isinstance(self.power_id, Unset):
            power_id = UNSET
        elif isinstance(self.power_id, UUID):
            power_id = str(self.power_id)
        else:
            power_id = self.power_id

        reach: str | Unset = UNSET
        if not isinstance(self.reach, Unset):
            reach = self.reach.value

        super_power_id: str | Unset | None
        if isinstance(self.super_power_id, Unset):
            super_power_id = UNSET
        elif isinstance(self.super_power_id, UUID):
            super_power_id = str(self.super_power_id)
        else:
            super_power_id = self.super_power_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if power_id is not UNSET:
            field_dict["power_id"] = power_id
        if reach is not UNSET:
            field_dict["reach"] = reach
        if super_power_id is not UNSET:
            field_dict["super_power_id"] = super_power_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_power_id(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                power_id_type_0 = UUID(data)

                return power_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        power_id = _parse_power_id(d.pop("power_id", UNSET))

        _reach = d.pop("reach", UNSET)
        reach: NewListingReach | Unset
        if isinstance(_reach, Unset):
            reach = UNSET
        else:
            reach = NewListingReach(_reach)

        def _parse_super_power_id(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                super_power_id_type_0 = UUID(data)

                return super_power_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        super_power_id = _parse_super_power_id(d.pop("super_power_id", UNSET))

        new_listing = cls(
            power_id=power_id,
            reach=reach,
            super_power_id=super_power_id,
        )

        new_listing.additional_properties = d
        return new_listing

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
