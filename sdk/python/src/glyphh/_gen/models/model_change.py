from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.model_change_type_type_0 import ModelChangeTypeType0
from ..types import UNSET, Unset

T = TypeVar("T", bound="ModelChange")


@_attrs_define
class ModelChange:
    """
    Attributes:
        active (bool | None | Unset):
        description (None | str | Unset):
        name (None | str | Unset):
        type_ (ModelChangeTypeType0 | None | Unset):
    """

    active: bool | Unset | None = UNSET
    description: str | Unset | None = UNSET
    name: str | Unset | None = UNSET
    type_: ModelChangeTypeType0 | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        active: bool | Unset | None
        if isinstance(self.active, Unset):
            active = UNSET
        else:
            active = self.active

        description: str | Unset | None
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        name: str | Unset | None
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        type_: str | Unset | None
        if isinstance(self.type_, Unset):
            type_ = UNSET
        elif isinstance(self.type_, ModelChangeTypeType0):
            type_ = self.type_.value
        else:
            type_ = self.type_

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if active is not UNSET:
            field_dict["active"] = active
        if description is not UNSET:
            field_dict["description"] = description
        if name is not UNSET:
            field_dict["name"] = name
        if type_ is not UNSET:
            field_dict["type"] = type_

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_active(data: object) -> bool | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        active = _parse_active(d.pop("active", UNSET))

        def _parse_description(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))

        def _parse_name(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_type_(data: object) -> ModelChangeTypeType0 | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                type_type_0 = ModelChangeTypeType0(data)

                return type_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ModelChangeTypeType0 | None | Unset, data)

        type_ = _parse_type_(d.pop("type", UNSET))

        model_change = cls(
            active=active,
            description=description,
            name=name,
            type_=type_,
        )

        model_change.additional_properties = d
        return model_change

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
