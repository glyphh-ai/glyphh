"""The person's runtimes: a local rrotor's runtime token, for the install that starts it; their first hosted machine
(made on first start, started, stopped and destroyed: the routes from before a person had several, kept for the
clients made then; /v1/runtimes has them all), the keys; and the link every rrotor holds to the Cloud."""

import uuid

from fastapi import APIRouter, Request, Response, WebSocket
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.db import tenancy
from glyphh_server.errors import Unauthorized, Unavailable
from glyphh_server.ops import machines, runtime_keys, runtimes
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
    runtime_id: uuid.UUID | None = Field(
        None, description="A hosted machine or self-hosted runtime of yours; left out, every hosted machine of yours"
    )


@router.get("", operation_id="hostedRuntime")
async def hosted_runtime(caller: Caller, conn: Conn, request: Request) -> HostedRuntime:
    """Your first hosted machine: its address, state and its online time this month."""
    return await runtimes.hosted_view(conn, caller, request.app.state.settings.fly_public_domain)


@router.post("/start", operation_id="startHostedRuntime")
async def start_hosted_runtime(caller: Caller, conn: Conn, request: Request) -> HostedRuntime:
    """Start your first hosted machine, made the first time (`default`, small; metered per second, never paused). It
    is `stopped` until its rrotor links, `online` then; a request to its address starts a stopped one."""
    await machines.start_first(conn, fly(request), caller)
    return await runtimes.hosted_view(conn, caller, request.app.state.settings.fly_public_domain)


@router.post("/stop", operation_id="stopHostedRuntime")
async def stop_hosted_runtime(caller: Caller, conn: Conn, request: Request) -> HostedRuntime:
    """Stop your first hosted machine now (it stops by itself when idle)."""
    client = fly(request)
    await machines.stop(conn, client, caller, await machines.first(conn, caller))
    return await runtimes.hosted_view(conn, caller, request.app.state.settings.fly_public_domain)


@router.get("/keys", operation_id="listRuntimeKeys")
async def list_runtime_keys(caller: Caller, conn: Conn) -> list[KeyView]:
    """The keys that call your runtimes at their addresses, live and revoked; never the keys themselves."""
    return await runtime_keys.list_keys(conn, caller)


@router.post("/keys", operation_id="createRuntimeKey", status_code=201)
async def create_runtime_key(body: NewKey, caller: Caller, conn: Conn, request: Request) -> MadeKey:
    """A new key, shown once: the bearer for your runtime's REST API and its /mcp (the one named, or every hosted
    machine of yours), expiring 1 to 365 days on, or never. rrotor gets its hash at once when linked, else in its next
    welcome."""
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
    """Destroy your first hosted machine: the machine, its volume and every model's data on it. Not undone."""
    client = fly(request)
    await machines.destroy(conn, client, caller, await machines.first(conn, caller))
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
        state.engine, state.redis, state.hub, Routines(state.http), state.secrets_key, state.signing_key
    )
    await session.serve(websocket, ctx, bearer(websocket.headers.get("authorization")))
