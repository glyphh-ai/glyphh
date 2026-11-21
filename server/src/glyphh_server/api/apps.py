"""The org's apps (docs/specs/apps.md, 3.3): listed to anyone in the org by their roles, reviewed by the admin or a
reviewer group's member. The app itself is on the org's rrotor, at its `url`."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import apps
from glyphh_server.ops.apps import PER_PAGE, PER_PAGE_MAX, REASON_MAX, AppView, Page

router = APIRouter(prefix="/v1/apps", tags=["apps"])

State = Literal["draft", "approved", "rejected", "retired"]
Type = Literal["page", "dashboard", "doc", "diagram", "deck", "design"]


class Rejection(BaseModel):
    reason: str = Field(min_length=1, max_length=REASON_MAX, pattern=r"\S")


@router.get("", operation_id="listApps")
async def list_apps(
    caller: Caller,
    conn: Conn,
    q: Annotated[str | None, Query(max_length=200, description="Matches the title, description and name")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=PER_PAGE_MAX)] = PER_PAGE,
    state: Annotated[State, Query(description="draft, rejected and retired are the reviewers' to see")] = "approved",
    type: Annotated[Type | None, Query(description="Only apps of this type; absent, every type")] = None,
) -> Page:
    """A page of the org's apps, the newest change first: the approved ones your roles allow; every one of another
    state for a reviewer (E_FORBIDDEN otherwise)."""
    return await apps.list_apps(conn, caller, q, page, per_page, state, type)


@router.get("/{app_id}", operation_id="getApp")
async def get_app(app_id: uuid.UUID, caller: Caller, conn: Conn) -> AppView:
    return await apps.get_app(conn, caller, app_id)


@router.post("/{app_id}/approve", operation_id="approveApp")
async def approve_app(app_id: uuid.UUID, request: Request, caller: Caller, conn: Conn) -> AppView:
    """Approve a draft (or a rejected one): the rrotor serves it from here on. A reviewer's."""
    return await apps.approve(conn, request.app.state.hub, caller, app_id)


@router.post("/{app_id}/reject", operation_id="rejectApp")
async def reject_app(app_id: uuid.UUID, body: Rejection, request: Request, caller: Caller, conn: Conn) -> AppView:
    """Reject a draft (or an approved one), with the reason. A reviewer's."""
    return await apps.reject(conn, request.app.state.hub, caller, app_id, body.reason)


@router.post("/{app_id}/retire", operation_id="retireApp")
async def retire_app(app_id: uuid.UUID, request: Request, caller: Caller, conn: Conn) -> AppView:
    """Retire an app: no longer served or listed. A reviewer's."""
    return await apps.retire(conn, request.app.state.hub, caller, app_id)
