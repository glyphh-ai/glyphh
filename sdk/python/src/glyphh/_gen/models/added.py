from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.have import Have


T = TypeVar("T", bound="Added")


@_attrs_define
class Added:
    """
    Attributes:
        id (UUID):
        kind (str):
        name (str):
        needs (list[Have]):
    """

    id: UUID
    kind: str
    name: str
    needs: list[Have]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        kind = self.kind

        name = self.name

        needs = []
        for needs_item_data in self.needs:
            needs_item = needs_item_data.to_dict()
            needs.append(needs_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "kind": kind,
                "name": name,
                "needs": needs,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.have import Have

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        kind = d.pop("kind")

        name = d.pop("name")

        needs = []
        _needs = d.pop("needs")
        for needs_item_data in _needs:
            needs_item = Have.from_dict(needs_item_data)

            needs.append(needs_item)

        added = cls(
            id=id,
            kind=kind,
            name=name,
            needs=needs,
        )

        added.additional_properties = d
        return added

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
