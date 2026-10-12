from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.model_view_status import ModelViewStatus

if TYPE_CHECKING:
    from ..models.user import User


T = TypeVar("T", bound="ModelView")


@_attrs_define
class ModelView:
    """
    Attributes:
        base_url (None | str):
        catalog_model_id (None | UUID):
        disabled_at (datetime.datetime | None):
        disabled_reason (None | str):
        id (UUID):
        key_added_at (datetime.datetime):
        key_checked_at (datetime.datetime | None):
        key_error (None | str):
        key_last4 (str):
        logo_key (None | str):
        model (str):
        name (str):
        provider (str):
        provider_name (str):
        status (ModelViewStatus):
        type_ (None | str):
        used_by (list[User]):
    """

    base_url: str | None
    catalog_model_id: UUID | None
    disabled_at: datetime.datetime | None
    disabled_reason: str | None
    id: UUID
    key_added_at: datetime.datetime
    key_checked_at: datetime.datetime | None
    key_error: str | None
    key_last4: str
    logo_key: str | None
    model: str
    name: str
    provider: str
    provider_name: str
    status: ModelViewStatus
    type_: str | None
    used_by: list[User]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        base_url: str | None
        base_url = self.base_url

        catalog_model_id: str | None
        if isinstance(self.catalog_model_id, UUID):
            catalog_model_id = str(self.catalog_model_id)
        else:
            catalog_model_id = self.catalog_model_id

        disabled_at: str | None
        if isinstance(self.disabled_at, datetime.datetime):
            disabled_at = self.disabled_at.isoformat()
        else:
            disabled_at = self.disabled_at

        disabled_reason: str | None
        disabled_reason = self.disabled_reason

        id = str(self.id)

        key_added_at = self.key_added_at.isoformat()

        key_checked_at: str | None
        if isinstance(self.key_checked_at, datetime.datetime):
            key_checked_at = self.key_checked_at.isoformat()
        else:
            key_checked_at = self.key_checked_at

        key_error: str | None
        key_error = self.key_error

        key_last4 = self.key_last4

        logo_key: str | None
        logo_key = self.logo_key

        model = self.model

        name = self.name

        provider = self.provider

        provider_name = self.provider_name

        status = self.status.value

        type_: str | None
        type_ = self.type_

        used_by = []
        for used_by_item_data in self.used_by:
            used_by_item = used_by_item_data.to_dict()
            used_by.append(used_by_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "base_url": base_url,
                "catalog_model_id": catalog_model_id,
                "disabled_at": disabled_at,
                "disabled_reason": disabled_reason,
                "id": id,
                "key_added_at": key_added_at,
                "key_checked_at": key_checked_at,
                "key_error": key_error,
                "key_last4": key_last4,
                "logo_key": logo_key,
                "model": model,
                "name": name,
                "provider": provider,
                "provider_name": provider_name,
                "status": status,
                "type": type_,
                "used_by": used_by,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.user import User

        d = dict(src_dict)

        def _parse_base_url(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        base_url = _parse_base_url(d.pop("base_url"))

        def _parse_catalog_model_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                catalog_model_id_type_0 = UUID(data)

                return catalog_model_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        catalog_model_id = _parse_catalog_model_id(d.pop("catalog_model_id"))

        def _parse_disabled_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                disabled_at_type_0 = datetime.datetime.fromisoformat(data)

                return disabled_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        disabled_at = _parse_disabled_at(d.pop("disabled_at"))

        def _parse_disabled_reason(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        disabled_reason = _parse_disabled_reason(d.pop("disabled_reason"))

        id = UUID(d.pop("id"))

        key_added_at = datetime.datetime.fromisoformat(d.pop("key_added_at"))

        def _parse_key_checked_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                key_checked_at_type_0 = datetime.datetime.fromisoformat(data)

                return key_checked_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        key_checked_at = _parse_key_checked_at(d.pop("key_checked_at"))

        def _parse_key_error(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        key_error = _parse_key_error(d.pop("key_error"))

        key_last4 = d.pop("key_last4")

        def _parse_logo_key(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        logo_key = _parse_logo_key(d.pop("logo_key"))

        model = d.pop("model")

        name = d.pop("name")

        provider = d.pop("provider")

        provider_name = d.pop("provider_name")

        status = ModelViewStatus(d.pop("status"))

        def _parse_type_(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        type_ = _parse_type_(d.pop("type"))

        used_by = []
        _used_by = d.pop("used_by")
        for used_by_item_data in _used_by:
            used_by_item = User.from_dict(used_by_item_data)

            used_by.append(used_by_item)

        model_view = cls(
            base_url=base_url,
            catalog_model_id=catalog_model_id,
            disabled_at=disabled_at,
            disabled_reason=disabled_reason,
            id=id,
            key_added_at=key_added_at,
            key_checked_at=key_checked_at,
            key_error=key_error,
            key_last4=key_last4,
            logo_key=logo_key,
            model=model,
            name=name,
            provider=provider,
            provider_name=provider_name,
            status=status,
            type_=type_,
            used_by=used_by,
        )

        model_view.additional_properties = d
        return model_view

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
