"""The org's artifacts (docs/specs/artifacts.md, 3.3): listed to anyone in the org by their roles, reviewed by the
admin or a reviewer group's member. The page itself is on the org's rrotor, at each artifact's `url`."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import artifacts
from glyphh_server.ops.artifacts import PER_PAGE, PER_PAGE_MAX, REASON_MAX, ArtifactView, Page

router = APIRouter(prefix="/v1/artifacts", tags=["artifacts"])

State = Literal["draft", "approved", "rejected", "retired"]


class Rejection(BaseModel):
    reason: str = Field(min_length=1, max_length=REASON_MAX, pattern=r"\S")


@router.get("", operation_id="listArtifacts")
async def list_artifacts(
    caller: Caller,
    conn: Conn,
    q: Annotated[str | None, Query(max_length=200, description="Matches the title, description and name")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=PER_PAGE_MAX)] = PER_PAGE,
    state: Annotated[State, Query(description="draft, rejected and retired are the reviewers' to see")] = "approved",
) -> Page:
    """A page of the org's artifacts, the newest change first: the approved ones your roles allow; every one of
    another state for a reviewer (E_FORBIDDEN otherwise)."""
    return await artifacts.list_artifacts(conn, caller, q, page, per_page, state)


@router.get("/{artifact_id}", operation_id="getArtifact")
async def get_artifact(artifact_id: uuid.UUID, caller: Caller, conn: Conn) -> ArtifactView:
    return await artifacts.get_artifact(conn, caller, artifact_id)


@router.post("/{artifact_id}/approve", operation_id="approveArtifact")
async def approve_artifact(artifact_id: uuid.UUID, request: Request, caller: Caller, conn: Conn) -> ArtifactView:
    """Approve a draft (or a rejected one): the rrotor serves it from here on. A reviewer's."""
    return await artifacts.approve(conn, request.app.state.hub, caller, artifact_id)


@router.post("/{artifact_id}/reject", operation_id="rejectArtifact")
async def reject_artifact(
    artifact_id: uuid.UUID, body: Rejection, request: Request, caller: Caller, conn: Conn
) -> ArtifactView:
    """Reject a draft (or an approved one), with the reason. A reviewer's."""
    return await artifacts.reject(conn, request.app.state.hub, caller, artifact_id, body.reason)


@router.post("/{artifact_id}/retire", operation_id="retireArtifact")
async def retire_artifact(artifact_id: uuid.UUID, request: Request, caller: Caller, conn: Conn) -> ArtifactView:
    """Retire an artifact: no longer served or listed. A reviewer's."""
    return await artifacts.retire(conn, request.app.state.hub, caller, artifact_id)
