"""Each call, once: the generated operation, what success looks like, and the dataclass it becomes.
The sync and async clients both go through here, so they can never answer differently."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from glyphh import _models
from glyphh._errors import refused
from glyphh._gen.api.health import health
from glyphh._gen.api.invites import accept_invite, decline_invite
from glyphh._gen.api.me import change_my_settings, disconnect_host, list_hosts, list_my_orgs, me, my_settings
from glyphh._gen.models.health import Health
from glyphh._gen.models.joined import Joined
from glyphh._gen.models.me import Me
from glyphh._gen.models.settings import Settings
from glyphh._gen.types import Response


@dataclass(frozen=True, slots=True)
class Call:
    operation: Any
    ok: Callable[[Response[Any]], bool]
    convert: Callable[[Any], Any]


def answer(call: Call, response: Response[Any]) -> Any:
    if not call.ok(response):
        raise refused(int(response.status_code), response.content)
    return call.convert(response.parsed)


HEALTH = Call(health, lambda r: isinstance(r.parsed, Health), _models.health_of)
ME = Call(me, lambda r: isinstance(r.parsed, Me), _models.me_of)
LIST_HOSTS = Call(list_hosts, lambda r: isinstance(r.parsed, list), lambda hosts: [_models.host_of(h) for h in hosts])
DISCONNECT_HOST = Call(disconnect_host, lambda r: int(r.status_code) == 204, lambda _: None)
LIST_MY_ORGS = Call(list_my_orgs, lambda r: isinstance(r.parsed, list), lambda orgs: [_models.org_of(o) for o in orgs])
ACCEPT_INVITE = Call(accept_invite, lambda r: isinstance(r.parsed, Joined), lambda joined: joined.org)
DECLINE_INVITE = Call(decline_invite, lambda r: int(r.status_code) == 204, lambda _: None)
SETTINGS = Call(my_settings, lambda r: isinstance(r.parsed, Settings), _models.settings_of)
CHANGE_SETTINGS = Call(change_my_settings, lambda r: isinstance(r.parsed, Settings), _models.settings_of)
