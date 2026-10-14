"""The person's runtimes: a local rrotor's runtime token, for the install that starts it."""

from fastapi import APIRouter

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import runtimes
from glyphh_server.ops.runtimes import LocalRuntime

router = APIRouter(prefix="/v1/runtime", tags=["runtime"])


@router.post("/local", operation_id="issueLocalRuntime")
async def issue_local_runtime(caller: Caller, conn: Conn) -> LocalRuntime:
    """This install's local rrotor: made the first time, its token rotated every time after. The token is shown
    once; the rrotor sends it on its outbound link."""
    return await runtimes.issue_local(conn, caller)
