"""The person's runtimes: a local rrotor's runtime token, for the install that starts it; the runtime keys that call a
self-hosted runtime; a self-hosted runtime's check of a Glyphh sign-in; and the link every rrotor holds to the
server."""

import uuid

from fastapi import APIRouter, Request, Response, WebSocket
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.db import tenancy
from glyphh_server.errors import Unauthorized
from glyphh_server.ops import runtime_keys, runtimes
from glyphh_server.ops.connector import tokens
from glyphh_server.ops.link import session
from glyphh_server.ops.link.presence import Refused, bearer, runtime_for
from glyphh_server.ops.runtime_keys import KeyView, MadeKey
from glyphh_server.ops.runtimes import LocalRuntime

router = APIRouter(prefix="/v1/runtime", tags=["runtime"])


@router.post("/local", operation_id="issueLocalRuntime")
async def issue_local_runtime(caller: Caller, conn: Conn) -> LocalRuntime:
    """This install's local rrotor: made the first time, its token rotated every time after. The token is shown
    once; the rrotor sends it on its outbound link."""
    return await runtimes.issue_local(conn, caller)


class NewKey(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S", description="What the key is for")
    expires_in_days: int | None = Field(None, description="Days until the key expires, 1 to 365; left out, never")
    runtime_id: uuid.UUID = Field(description="The self-hosted runtime of yours it calls")


@router.get("/keys", operation_id="listRuntimeKeys")
async def list_runtime_keys(caller: Caller, conn: Conn) -> list[KeyView]:
    """The keys that call your self-hosted runtimes at their addresses, live and revoked; never the keys themselves."""
    return await runtime_keys.list_keys(conn, caller)


@router.post("/keys", operation_id="createRuntimeKey", status_code=201)
async def create_runtime_key(body: NewKey, caller: Caller, conn: Conn, request: Request) -> MadeKey:
    """A new key, shown once: the bearer for your self-hosted runtime's REST API and its /mcp, expiring 1 to 365 days
    on, or never. rrotor gets its hash at once when linked, else in its next welcome."""
    hub = request.app.state.hub
    return await runtime_keys.create_key(conn, hub, caller, body.name.strip(), body.expires_in_days, body.runtime_id)


@router.delete("/keys/{key_id}", operation_id="revokeRuntimeKey")
async def revoke_runtime_key(key_id: uuid.UUID, caller: Caller, conn: Conn, request: Request) -> KeyView:
    """Revoke one key; rrotor stops taking it the same way."""
    return await runtime_keys.revoke_key(conn, request.app.state.hub, caller, key_id)


@router.delete("/keys/{key_id}/record", operation_id="deleteRuntimeKey", status_code=204)
async def delete_runtime_key(key_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    """Delete a revoked or expired key from your list; a live one must be revoked first."""
    await runtime_keys.delete_key(conn, caller, key_id)
    return Response(status_code=204)


class Introspect(BaseModel):
    token: str = Field(min_length=1, max_length=512, description="The bearer the runtime was shown")


@router.post("/introspect", operation_id="introspectRuntimeSignIn", response_model=tokens.Introspection)
async def introspect_sign_in(body: Introspect, request: Request) -> Response:
    """For a self-hosted rrotor, its runtime token as auth: whether a bearer it was shown is a live Glyphh sign-in for
    its own address (`https://<public host>/mcp`: the resource the token was issued for), and whose (RFC 7662's
    shape). Anything else, a local runtime's ask included, is `active: false`."""
    state = request.app.state
    try:
        runtime = await runtime_for(state.engine, bearer(request.headers.get("authorization")))
    except Refused as err:
        raise Unauthorized(str(err)) from None
    answer = tokens.Introspection(active=False)
    resource = runtime.resource()
    if resource is not None:
        async with state.engine.begin() as conn:
            await tenancy.enter(conn, runtime.org_id)
            answer = await tokens.introspect(conn, body.token, resource)
    return JSONResponse(answer.model_dump(exclude_none=True), headers={"cache-control": "no-store"})


@router.websocket("/link")
async def runtime_link(websocket: WebSocket) -> None:
    """The runtime's outbound link (protocol 3), local or self-hosted: `Authorization: Bearer <runtime token>`, then
    `hello`. Licensing goes down it (the licence key, a self-hosted runtime's licence and keys) and the bots' and
    swarms' calls; usage and the calls' results come back."""
    state = websocket.app.state
    ctx = session.Context(state.engine, state.hub, state.bots.landed, state.signing_key)
    await session.serve(websocket, ctx, bearer(websocket.headers.get("authorization")))
