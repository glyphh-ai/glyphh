from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.person_kind import PersonKind
from ..models.person_status import PersonStatus

T = TypeVar("T", bound="Person")


@_attrs_define
class Person:
    """
    Attributes:
        email (str):
        id (UUID):
        kind (PersonKind):
        name (None | str):
        role (str):
        since (datetime.datetime):
        status (PersonStatus):
        teams (list[str]):
    """

    email: str
    id: UUID
    kind: PersonKind
    name: str | None
    role: str
    since: datetime.datetime
    status: PersonStatus
    teams: list[str]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        email = self.email

        id = str(self.id)

        kind = self.kind.value

        name: str | None
        name = self.name

        role = self.role

        since = self.since.isoformat()

        status = self.status.value

        teams = self.teams

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "email": email,
                "id": id,
                "kind": kind,
                "name": name,
                "role": role,
                "since": since,
                "status": status,
                "teams": teams,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        email = d.pop("email")

        id = UUID(d.pop("id"))

        kind = PersonKind(d.pop("kind"))

        def _parse_name(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        name = _parse_name(d.pop("name"))

        role = d.pop("role")

        since = datetime.datetime.fromisoformat(d.pop("since"))

        status = PersonStatus(d.pop("status"))

        teams = cast(list[str], d.pop("teams"))

        person = cls(
            email=email,
            id=id,
            kind=kind,
            name=name,
            role=role,
            since=since,
            status=status,
            teams=teams,
        )

        person.additional_properties = d
        return person

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
