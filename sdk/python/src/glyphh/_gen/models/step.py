from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.step_kind import StepKind
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.step_config import StepConfig


T = TypeVar("T", bound="Step")


@_attrs_define
class Step:
    """
    Attributes:
        id (str):
        kind (StepKind):
        label (str):
        checkpoint (bool | Unset):  Default: False.
        config (StepConfig | Unset):
        x (float | Unset):  Default: 0.0.
        y (float | Unset):  Default: 0.0.
    """

    id: str
    kind: StepKind
    label: str
    checkpoint: bool | Unset = False
    config: StepConfig | Unset = UNSET
    x: float | Unset = 0.0
    y: float | Unset = 0.0
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        kind = self.kind.value

        label = self.label

        checkpoint = self.checkpoint

        config: dict[str, Any] | Unset = UNSET
        if not isinstance(self.config, Unset):
            config = self.config.to_dict()

        x = self.x

        y = self.y

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "kind": kind,
                "label": label,
            }
        )
        if checkpoint is not UNSET:
            field_dict["checkpoint"] = checkpoint
        if config is not UNSET:
            field_dict["config"] = config
        if x is not UNSET:
            field_dict["x"] = x
        if y is not UNSET:
            field_dict["y"] = y

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.step_config import StepConfig

        d = dict(src_dict)
        id = d.pop("id")

        kind = StepKind(d.pop("kind"))

        label = d.pop("label")

        checkpoint = d.pop("checkpoint", UNSET)

        _config = d.pop("config", UNSET)
        config: StepConfig | Unset
        if isinstance(_config, Unset):
            config = UNSET
        else:
            config = StepConfig.from_dict(_config)

        x = d.pop("x", UNSET)

        y = d.pop("y", UNSET)

        step = cls(
            id=id,
            kind=kind,
            label=label,
            checkpoint=checkpoint,
            config=config,
            x=x,
            y=y,
        )

        step.additional_properties = d
        return step

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
