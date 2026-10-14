"""The person's runtimes: a local rrotor's runtime token, for the install that starts it, and the link every rrotor
holds to the Cloud."""

from fastapi import APIRouter, WebSocket

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import runtimes
from glyphh_server.ops.link import session
from glyphh_server.ops.link.presence import bearer
from glyphh_server.ops.routines import Routines
from glyphh_server.ops.runtimes import LocalRuntime

router = APIRouter(prefix="/v1/runtime", tags=["runtime"])


@router.post("/local", operation_id="issueLocalRuntime")
async def issue_local_runtime(caller: Caller, conn: Conn) -> LocalRuntime:
    """This install's local rrotor: made the first time, its token rotated every time after. The token is shown
    once; the rrotor sends it on its outbound link."""
    return await runtimes.issue_local(conn, caller)


@router.websocket("/link")
async def runtime_link(websocket: WebSocket) -> None:
    """The runtime's outbound link (protocol 1), hosted or local: `Authorization: Bearer <runtime token>`, then
    `hello`. Calls go down it; results, events and deploys come back."""
    state = websocket.app.state
    ctx = session.Context(state.engine, state.redis, state.hub, Routines(state.http), state.secrets_key)
    await session.serve(websocket, ctx, bearer(websocket.headers.get("authorization")))
