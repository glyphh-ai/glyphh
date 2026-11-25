"""The plugin's side of the device flow (RFC 8628): ask for a code, then poll for the install's token."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Conn
from glyphh_server.api.errors import error_body
from glyphh_server.models import MACHINE_ID
from glyphh_server.ops import device, device_token
from glyphh_server.ops.device import DeviceStart, Surface
from glyphh_server.ops.device_token import DeviceToken

router = APIRouter(prefix="/v1/device", tags=["device flow"])

POLL_ERRORS = {400: {"description": "authorization_pending, slow_down, expired_token or access_denied, as error.code"}}


class DeviceCodeIn(BaseModel):
    machine_id: str | None = Field(
        None,
        pattern=MACHINE_ID,
        description="A stable id for this machine, 16 to 128 of A-Z a-z 0-9 _ -. Signing in again on it reuses its"
        " install. Sent by every current plugin; when absent one is made up.",
    )
    name: str = Field(min_length=1, max_length=80, description="What the install is called: the machine's name")
    surface: Surface
    mod_version: str = Field(min_length=1, max_length=40)


class DeviceTokenIn(BaseModel):
    device_code: str = Field(min_length=1, max_length=200)


@router.post("/code", operation_id="startDeviceSignIn")
async def start(body: DeviceCodeIn, request: Request, conn: Conn) -> DeviceStart:
    machine_id = body.machine_id or device.new_machine_id()
    settings = request.app.state.settings
    return await device.start(conn, settings, machine_id, body.name.strip(), body.surface, body.mod_version)


@router.post("/token", operation_id="pollDeviceToken", response_model=DeviceToken, responses=POLL_ERRORS)
async def token(body: DeviceTokenIn, conn: Conn) -> DeviceToken | JSONResponse:
    answer = await device_token.poll(conn, body.device_code)
    if isinstance(answer, DeviceToken):
        return answer
    return JSONResponse(error_body(answer.code, answer.message), status_code=answer.status)
