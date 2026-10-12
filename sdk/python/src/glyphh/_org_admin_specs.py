"""Org admin, as calls: people and open invites, inviting many, teams and who is in them, the org's and teams'
model and connection limits, and the audit log (in pages, or as CSV); and API keys, mine and the org's. Answers are
the server's JSON as plain dicts (the CSV as text)."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from glyphh._calls import plain_call as _call
from glyphh._gen.api.api_keys import (
    get_member_keys,
    list_api_key_makers,
    list_my_api_keys,
    list_org_api_keys,
    make_api_key,
    revoke_api_key,
    set_member_keys,
)
from glyphh._gen.api.org import (
    add_limit_entries,
    add_team_members,
    change_team,
    create_team,
    delete_team,
    export_audit_log,
    get_limit_impact,
    get_limits,
    get_member_teams,
    get_team,
    invite_many,
    list_audit_log,
    list_people,
    list_teams,
    remove_limit_entries,
    remove_team_member,
    set_limit,
    set_member_teams,
)
from glyphh._gen.models import (
    AddLimitEntriesKind,
    Entries,
    ExportAuditLogTypeType0,
    GetLimitImpactKind,
    GetLimitsKind,
    InviteMany,
    ListAuditLogTypeType0,
    ListPeopleRoleType0,
    MemberKeysChange,
    NewKey,
    People,
    RemoveLimitEntriesKind,
    SetLimitKind,
    Switch,
    TeamChange,
    TeamIn,
    TeamsOf,
)
from glyphh._gen.types import UNSET

Spec = tuple[Any, dict[str, Any]]


def _id(value: str | None) -> Any:
    return UUID(value) if value else UNSET


def _t(team_id: str) -> dict[str, Any]:
    return {"team_id": UUID(team_id)}


def _limit(kind_type: Any, kind: str, team: str | None) -> dict[str, Any]:
    return {"kind": kind_type(kind), "team": _id(team)}


def _filters(
    type_enum: Any,
    since: datetime | None,
    until: datetime | None,
    who: str | None,
    type: str | None,
    target: str | None,
) -> dict[str, Any]:
    return {
        "since": since or UNSET,
        "until": until or UNSET,
        "who": _id(who),
        "type_": type_enum(type) if type else UNSET,
        "target": target or UNSET,
    }


ORG_ADMIN_SPECS: dict[str, Callable[..., Spec]] = {
    "people": lambda q="", role=None, team=None, page=1, size=25: (
        _call(list_people),
        {
            "q": q,
            "role": ListPeopleRoleType0(role) if role else UNSET,
            "team": team or UNSET,
            "page": page,
            "size": size,
        },
    ),
    "invite_many": lambda emails, role="user", team_ids=(): (
        _call(invite_many),
        {"body": InviteMany.from_dict({"emails": list(emails), "role": role, "team_ids": list(team_ids)})},
    ),
    "teams": lambda: (_call(list_teams), {}),
    "team": lambda team_id: (_call(get_team), _t(team_id)),
    "create_team": lambda name: (_call(create_team), {"body": TeamIn(name=name)}),
    "change_team": lambda team_id, **change: (
        _call(change_team),
        {**_t(team_id), "body": TeamChange.from_dict(change)},
    ),
    "delete_team": lambda team_id: (_call(delete_team), _t(team_id)),
    "add_to_team": lambda team_id, user_ids: (
        _call(add_team_members),
        {**_t(team_id), "body": People(user_ids=[UUID(u) for u in user_ids])},
    ),
    "remove_from_team": lambda team_id, user_id: (_call(remove_team_member), {**_t(team_id), "user_id": UUID(user_id)}),
    "member_teams": lambda user_id: (_call(get_member_teams), {"user_id": UUID(user_id)}),
    "set_member_teams": lambda user_id, team_ids: (
        _call(set_member_teams),
        {"user_id": UUID(user_id), "body": TeamsOf(team_ids=[UUID(t) for t in team_ids])},
    ),
    "limits": lambda kind, team=None, q="", page=1, size=25: (
        _call(get_limits),
        {**_limit(GetLimitsKind, kind, team), "q": q, "page": page, "size": size},
    ),
    "limit_impact": lambda kind, team=None: (_call(get_limit_impact), _limit(GetLimitImpactKind, kind, team)),
    "set_limit": lambda kind, on, team=None: (
        _call(set_limit),
        {**_limit(SetLimitKind, kind, team), "body": Switch(on=on)},
    ),
    "add_limit_entries": lambda kind, ids, team=None: (
        _call(add_limit_entries),
        {**_limit(AddLimitEntriesKind, kind, team), "body": Entries(ids=list(ids))},
    ),
    "remove_limit_entries": lambda kind, ids, team=None: (
        _call(remove_limit_entries),
        {**_limit(RemoveLimitEntriesKind, kind, team), "body": Entries(ids=list(ids))},
    ),
    "audit_log": lambda since=None, until=None, who=None, type=None, target=None, page=1, size=25: (
        _call(list_audit_log),
        {**_filters(ListAuditLogTypeType0, since, until, who, type, target), "page": page, "size": size},
    ),
    "export_audit_log": lambda since=None, until=None, who=None, type=None, target=None: (
        _call(export_audit_log),
        _filters(ExportAuditLogTypeType0, since, until, who, type, target),
    ),
}

API_KEY_SPECS: dict[str, Callable[..., Spec]] = {
    "mine": lambda page=1, size=25: (_call(list_my_api_keys), {"page": page, "size": size}),
    "make": lambda name, expires="90d": (
        _call(make_api_key),
        {"body": NewKey.from_dict({"name": name, "expires": expires})},
    ),
    "revoke": lambda key_id: (_call(revoke_api_key), {"key_id": UUID(key_id)}),
    "org": lambda owner=None, page=1, size=25: (
        _call(list_org_api_keys),
        {"owner": _id(owner), "page": page, "size": size},
    ),
    "makers": lambda q="": (_call(list_api_key_makers), {"q": q}),
    "member_keys": lambda: (_call(get_member_keys), {}),
    "set_member_keys": lambda on: (_call(set_member_keys), {"body": MemberKeysChange(on=on)}),
}
