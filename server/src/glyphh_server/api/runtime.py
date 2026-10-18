"""The person's runtimes: a local rrotor's runtime token, for the install that starts it; the hosted one (Pro and
Team), made on first start, started and stopped; and the link every rrotor holds to the Cloud."""

import uuid

from fastapi import APIRouter, Request, Response, WebSocket
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.db import tenancy
from glyphh_server.errors import Unauthorized, Unavailable
from glyphh_server.ops import hosted, runtime_keys, runtimes
from glyphh_server.ops.connector import tokens
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.link import session
from glyphh_server.ops.link.presence import Refused, bearer, runtime_for
from glyphh_server.ops.routines import Routines
from glyphh_server.ops.runtime_keys import KeyView, MadeKey
from glyphh_server.ops.runtimes import HostedRuntime, LocalRuntime

router = APIRouter(prefix="/v1/runtime", tags=["runtime"])


@router.post("/local", operation_id="issueLocalRuntime")
async def issue_local_runtime(caller: Caller, conn: Conn) -> LocalRuntime:
    """This install's local rrotor: made the first time, its token rotated every time after. The token is shown
    once; the rrotor sends it on its outbound link."""
    return await runtimes.issue_local(conn, caller)


def fly(request: Request) -> Fly:
    state = request.app.state
    if not state.settings.fly_configured:
        raise Unavailable("Hosting isn't set up on this server.", reason="hosting_off")
    return Fly(state.http, state.settings)


class NewKey(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S", description="What the key is for")
    expires_in_days: int | None = Field(None, description="Days until the key expires, 1 to 365; left out, never")
    runtime_id: uuid.UUID | None = Field(None, description="A self-hosted runtime of yours; left out, your hosted one")


@router.get("", operation_id="hostedRuntime")
async def hosted_runtime(caller: Caller, conn: Conn, request: Request) -> HostedRuntime:
    """Your hosted runtime: its address, state, the online time used this month and the plan's hours."""
    return await runtimes.hosted_view(conn, caller, request.app.state.settings.fly_public_domain)


@router.post("/start", operation_id="startHostedRuntime")
async def start_hosted_runtime(caller: Caller, conn: Conn, request: Request) -> HostedRuntime:
    """Start your hosted runtime, made the first time (on any plan; the plan's hours say how long it runs a month).
    It is `stopped` until its rrotor links, `online` then; a request to its address starts a stopped one."""
    return await hosted.start_hosted(conn, fly(request), request.app.state.settings, caller)


@router.post("/stop", operation_id="stopHostedRuntime")
async def stop_hosted_runtime(caller: Caller, conn: Conn, request: Request) -> HostedRuntime:
    """Stop your hosted runtime's machine now (it stops by itself when idle)."""
    return await hosted.stop_hosted(conn, fly(request), caller, request.app.state.settings.fly_public_domain)


@router.get("/keys", operation_id="listRuntimeKeys")
async def list_runtime_keys(caller: Caller, conn: Conn) -> list[KeyView]:
    """The keys that call your runtime at its address, live and revoked; never the keys themselves."""
    return await runtime_keys.list_keys(conn, caller)


@router.post("/keys", operation_id="createRuntimeKey", status_code=201)
async def create_runtime_key(body: NewKey, caller: Caller, conn: Conn, request: Request) -> MadeKey:
    """A new key, shown once: the bearer for your runtime's REST API and its /mcp, expiring 1 to 365 days on, or
    never. rrotor gets its hash at once when linked, else in its next welcome."""
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


@router.delete("", operation_id="destroyHostedRuntime", status_code=204)
async def destroy_hosted_runtime(caller: Caller, conn: Conn, request: Request) -> Response:
    """Destroy your hosted runtime: the machine, its volume and every model's data on it. Not undone."""
    await hosted.destroy_hosted(conn, fly(request), caller)
    return Response(status_code=204)


class Introspect(BaseModel):
    token: str = Field(min_length=1, max_length=512, description="The bearer the runtime was shown")


@router.post("/introspect", operation_id="introspectRuntimeSignIn", response_model=tokens.Introspection)
async def introspect_sign_in(body: Introspect, request: Request) -> Response:
    """For a hosted or self-hosted rrotor, its runtime token as auth: whether a bearer it was shown is a live Glyphh
    sign-in for its own address (`https://<machine>.<domain>/mcp`, or `https://<public host>/mcp`: the resource the
    token was issued for), and whose (RFC 7662's shape). Anything else, a local runtime's ask included, is
    `active: false`."""
    state = request.app.state
    try:
        runtime = await runtime_for(state.engine, bearer(request.headers.get("authorization")))
    except Refused as err:
        raise Unauthorized(str(err)) from None
    answer = tokens.Introspection(active=False)
    resource = runtime.resource(state.settings.fly_public_domain)
    if resource is not None:
        async with state.engine.begin() as conn:
            await tenancy.enter(conn, runtime.org_id)
            answer = await tokens.introspect(conn, body.token, resource)
    return JSONResponse(answer.model_dump(exclude_none=True), headers={"cache-control": "no-store"})


@router.websocket("/link")
async def runtime_link(websocket: WebSocket) -> None:
    """The runtime's outbound link (protocol 1), hosted or local: `Authorization: Bearer <runtime token>`, then
    `hello`. Calls go down it; results, events and deploys come back."""
    state = websocket.app.state
    ctx = session.Context(
        state.engine, state.redis, state.hub, Routines(state.http), state.secrets_key, state.license_key
    )
    await session.serve(websocket, ctx, bearer(websocket.headers.get("authorization")))
