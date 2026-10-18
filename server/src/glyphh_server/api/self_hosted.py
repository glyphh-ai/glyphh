"""Self-hosted runtimes: registered by name and public address (the token shown once, and the environment it runs
with filled in), listed, their token rotated, deleted; and an offline licence for one that is air-gapped."""

import uuid

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import heartbeat, self_hosted
from glyphh_server.ops.heartbeat import Offline, OfflineAsk
from glyphh_server.ops.self_hosted import MadeSelf, SelfRuntime, Token

router = APIRouter(prefix="/v1/runtimes", tags=["runtime"])


class NewSelf(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S", description="What the runtime is called")
    public_url: str = Field(min_length=1, max_length=300, description="https://<host>: where it answers, no path")


@router.post("/self", operation_id="registerSelfRuntime", status_code=201)
async def register_self_runtime(body: NewSelf, caller: Caller, conn: Conn, request: Request) -> MadeSelf:
    """Register a self-hosted runtime: its token, shown once, and its environment (`RROTOR_MODE=self`,
    `RROTOR_SERVER`, `RROTOR_RUNTIME_ID`, `RROTOR_RUNTIME_TOKEN`, `RROTOR_PUBLIC_HOST`) filled in."""
    settings = request.app.state.settings
    return await self_hosted.register(conn, settings, caller, body.name.strip(), body.public_url)


@router.get("/self", operation_id="listSelfRuntimes")
async def list_self_runtimes(caller: Caller, conn: Conn) -> list[SelfRuntime]:
    """Your self-hosted runtimes: each one's address, state, version and when it was last seen and last beat."""
    return await self_hosted.list_self(conn, caller)


@router.post("/self/{runtime_id}/token", operation_id="rotateSelfRuntimeToken")
async def rotate_self_runtime_token(runtime_id: uuid.UUID, caller: Caller, conn: Conn, request: Request) -> Token:
    """A new token for the runtime, shown once; the old one stops working and its link is closed."""
    return await self_hosted.rotate(conn, request.app.state.hub, caller, runtime_id)


@router.delete("/self/{runtime_id}", operation_id="deleteSelfRuntime", status_code=204)
async def delete_self_runtime(runtime_id: uuid.UUID, caller: Caller, conn: Conn, request: Request) -> Response:
    """Delete the runtime from Glyphh: its token stops working and its link is closed; its own volume is untouched."""
    await self_hosted.delete_self(conn, request.app.state.hub, caller, runtime_id)
    return Response(status_code=204)


@router.post("/{runtime_id}/offline-licence", operation_id="issueOfflineLicence")
async def issue_offline_licence(
    runtime_id: uuid.UUID, body: OfflineAsk, caller: Caller, conn: Conn, request: Request
) -> Offline:
    """An offline licence for an air-gapped self-hosted runtime: 1 to 365 days, live 14 days past its expiry, as one
    token (base64url of `{payload, signature}`) for `RROTOR_LICENCE` or `/data/licence.token`."""
    return await heartbeat.offline(conn, request.app.state.license_key, caller, runtime_id, body.days)
