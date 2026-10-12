from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.admin_model import AdminModel


T = TypeVar("T", bound="AdminModelPage")


@_attrs_define
class AdminModelPage:
    """
    Attributes:
        models (list[AdminModel]):
        total (int):
    """

    models: list[AdminModel]
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        models = []
        for models_item_data in self.models:
            models_item = models_item_data.to_dict()
            models.append(models_item)

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "models": models,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.admin_model import AdminModel

        d = dict(src_dict)
        models = []
        _models = d.pop("models")
        for models_item_data in _models:
            models_item = AdminModel.from_dict(models_item_data)

            models.append(models_item)

        total = d.pop("total")

        admin_model_page = cls(
            models=models,
            total=total,
        )

        admin_model_page.additional_properties = d
        return admin_model_page

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
