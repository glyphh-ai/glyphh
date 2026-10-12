from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.step_step import StepStep
from ..types import UNSET, Unset

T = TypeVar("T", bound="Step")


@_attrs_define
class Step:
    """
    Attributes:
        login (str):
        step (StepStep):
        url (str):
        code (None | str | Unset):
        expires_at (None | str | Unset):
    """

    login: str
    step: StepStep
    url: str
    code: str | Unset | None = UNSET
    expires_at: str | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        login = self.login

        step = self.step.value

        url = self.url

        code: str | Unset | None
        if isinstance(self.code, Unset):
            code = UNSET
        else:
            code = self.code

        expires_at: str | Unset | None
        if isinstance(self.expires_at, Unset):
            expires_at = UNSET
        else:
            expires_at = self.expires_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "login": login,
                "step": step,
                "url": url,
            }
        )
        if code is not UNSET:
            field_dict["code"] = code
        if expires_at is not UNSET:
            field_dict["expires_at"] = expires_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        login = d.pop("login")

        step = StepStep(d.pop("step"))

        url = d.pop("url")

        def _parse_code(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        code = _parse_code(d.pop("code", UNSET))

        def _parse_expires_at(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        expires_at = _parse_expires_at(d.pop("expires_at", UNSET))

        step = cls(
            login=login,
            step=step,
            url=url,
            code=code,
            expires_at=expires_at,
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
