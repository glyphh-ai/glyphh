"""A call to the Ada workers, by the API and the connector alike: the org's plan checked (api/meter.py: calls a
second, reads a month), one message on `ada:sync`, then a blocking wait on its reply list for the call's timeout
(reads GLYPHH_ADA_READ_TIMEOUT, record_many GLYPHH_ADA_WRITE_TIMEOUT), else 504 E_TIMEOUT. A worker's refusal is raised
as the server's, with the worker's code and status. Redis down is 503 E_UNAVAILABLE, never a hang.

`send` takes the Ada app's state (its settings, its database engine, its Redis client, which sets no socket timeout):
the API's routes reach it by their request, the connector by the server's app (app.state.ada)."""

import json
import time
from typing import Any

from fastapi import Request
from redis.exceptions import RedisError

from glyphh_ada import protocol
from glyphh_ada.api.auth import AdaCaller
from glyphh_ada.api.meter import admit
from glyphh_ada.errors import BadRequest, Refused, Timeout
from glyphh_ada.limits import no_nul
from glyphh_server.errors import Unavailable

SLOW: frozenset[str] = frozenset({"record_many", "create", "delete", "spec", "settings", "activate"})
IDEMPOTENCY_MAX: int = 200
# Writes a request makes after its first (an import queued once its file is in): each is once by itself, and the
# caller's Idempotency-Key is its first write's.
SECOND: frozenset[str] = frozenset({"import_go"})


def keyed(given: str) -> str:
    """A caller's Idempotency-Key, as the worker keys its write ("" when none was sent)."""
    if len(given) > IDEMPOTENCY_MAX:
        raise BadRequest(f"An Idempotency-Key is at most {IDEMPOTENCY_MAX} characters.", reason="idempotency_key")
    return f"idem:{given}" if given else ""


def idempotency(request: Request) -> str:
    return keyed(request.headers.get("idempotency-key", ""))


async def call(
    request: Request, who: AdaCaller, model: str, op: str, args: dict[str, Any], clearance: float | None = None
) -> Any:
    """The worker's answer to one op."""
    return (await versioned(request, who, model, op, args, clearance))[0]


async def versioned(
    request: Request, who: AdaCaller, model: str, op: str, args: dict[str, Any], clearance: float | None = None
) -> tuple[Any, int | None]:
    """The worker's answer and the model's active spec version (None for an answer about no one model)."""
    key = idempotency(request) if op in protocol.WRITES - SECOND else ""
    return await send(request.app.state, who, model, op, args, clearance, key)


async def send(
    state: Any,
    who: AdaCaller,
    model: str,
    op: str,
    args: dict[str, Any],
    clearance: float | None = None,
    key: str = "",
) -> tuple[Any, int | None]:
    """One op of one model, through the org's plan checks to a worker and back: (answer, active version)."""
    cfg = state.settings
    no_nul(args)
    await admit(state, who, op, args, model)
    timeout = cfg.ada_write_timeout if op in SLOW else cfg.ada_read_timeout
    msg = protocol.Message(
        org=str(who.org_id),
        model=model,
        op=op,
        args=args,
        clearance=who.clearance_for(clearance),
        author=who.author,
        deadline=time.time() + timeout,
        key=key,
        cap=who.cap,
    )
    try:
        stream = protocol.STREAMS[protocol.SYNC]
        await state.redis.xadd(stream, msg.fields(), maxlen=protocol.STREAM_MAX, approximate=True)
        got = await state.redis.blpop([protocol.reply_key(msg.id)], timeout=timeout)
    except RedisError:
        raise Unavailable("Ada is unreachable for a moment: try again.", reason="queue") from None
    if got is None:
        raise Timeout(f"No answer within {timeout:g} seconds: try again.", op=op, timeout=timeout)
    answer = json.loads(got[1])
    if answer["ok"]:
        return answer["data"], answer["version"]
    error = answer["error"]
    raise Refused(error.pop("code"), error.pop("message"), error.pop("status"), **error)
