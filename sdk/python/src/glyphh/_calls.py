"""Each call, once: the generated operation, what success looks like, and the dataclass it becomes.
The sync and async clients both go through here, so they can never answer differently."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from glyphh import _models
from glyphh._errors import refused
from glyphh._gen.api.health import health
from glyphh._gen.api.me import disconnect_host, list_hosts, me
from glyphh._gen.models.health import Health
from glyphh._gen.models.me import Me
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
