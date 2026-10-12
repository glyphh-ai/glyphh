from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.model_in_type import ModelInType
from ..types import UNSET, Unset

T = TypeVar("T", bound="ModelIn")


@_attrs_define
class ModelIn:
    """
    Attributes:
        model (str):
        name (str):
        provider_id (UUID):
        description (None | str | Unset):
        type_ (ModelInType | Unset):  Default: ModelInType.CHAT.
    """

    model: str
    name: str
    provider_id: UUID
    description: str | Unset | None = UNSET
    type_: ModelInType | Unset = ModelInType.CHAT
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        model = self.model

        name = self.name

        provider_id = str(self.provider_id)

        description: str | Unset | None
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        type_: str | Unset = UNSET
        if not isinstance(self.type_, Unset):
            type_ = self.type_.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "model": model,
                "name": name,
                "provider_id": provider_id,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if type_ is not UNSET:
            field_dict["type"] = type_

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        model = d.pop("model")

        name = d.pop("name")

        provider_id = UUID(d.pop("provider_id"))

        def _parse_description(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))

        _type_ = d.pop("type", UNSET)
        type_: ModelInType | Unset
        if isinstance(_type_, Unset):
            type_ = UNSET
        else:
            type_ = ModelInType(_type_)

        model_in = cls(
            model=model,
            name=name,
            provider_id=provider_id,
            description=description,
            type_=type_,
        )

        model_in.additional_properties = d
        return model_in

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
