from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="NewModel")


@_attrs_define
class NewModel:
    """From the catalog (`catalog_model_id`), or a model the catalog lacks (`provider` and its `model` id).

    Attributes:
        api_key (str):
        base_url (None | str | Unset):
        catalog_model_id (None | Unset | UUID):
        model (None | str | Unset):
        name (None | str | Unset):
        provider (None | str | Unset):
    """

    api_key: str
    base_url: str | Unset | None = UNSET
    catalog_model_id: Unset | UUID | None = UNSET
    model: str | Unset | None = UNSET
    name: str | Unset | None = UNSET
    provider: str | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        api_key = self.api_key

        base_url: str | Unset | None
        if isinstance(self.base_url, Unset):
            base_url = UNSET
        else:
            base_url = self.base_url

        catalog_model_id: str | Unset | None
        if isinstance(self.catalog_model_id, Unset):
            catalog_model_id = UNSET
        elif isinstance(self.catalog_model_id, UUID):
            catalog_model_id = str(self.catalog_model_id)
        else:
            catalog_model_id = self.catalog_model_id

        model: str | Unset | None
        if isinstance(self.model, Unset):
            model = UNSET
        else:
            model = self.model

        name: str | Unset | None
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        provider: str | Unset | None
        if isinstance(self.provider, Unset):
            provider = UNSET
        else:
            provider = self.provider

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "api_key": api_key,
            }
        )
        if base_url is not UNSET:
            field_dict["base_url"] = base_url
        if catalog_model_id is not UNSET:
            field_dict["catalog_model_id"] = catalog_model_id
        if model is not UNSET:
            field_dict["model"] = model
        if name is not UNSET:
            field_dict["name"] = name
        if provider is not UNSET:
            field_dict["provider"] = provider

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        api_key = d.pop("api_key")

        def _parse_base_url(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        base_url = _parse_base_url(d.pop("base_url", UNSET))

        def _parse_catalog_model_id(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                catalog_model_id_type_0 = UUID(data)

                return catalog_model_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        catalog_model_id = _parse_catalog_model_id(d.pop("catalog_model_id", UNSET))

        def _parse_model(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        model = _parse_model(d.pop("model", UNSET))

        def _parse_name(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_provider(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        provider = _parse_provider(d.pop("provider", UNSET))

        new_model = cls(
            api_key=api_key,
            base_url=base_url,
            catalog_model_id=catalog_model_id,
            model=model,
            name=name,
            provider=provider,
        )

        new_model.additional_properties = d
        return new_model

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
