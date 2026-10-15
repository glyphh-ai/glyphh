"""The user's workspace names, for the plan's limit."""

from typing import Annotated

from fastapi import APIRouter, Path, Response
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import workspaces
from glyphh_server.ops.workspaces import WorkspaceView

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])

Name = Annotated[str, Path(min_length=1, max_length=80)]


class WorkspaceName(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S")


@router.get("", operation_id="listWorkspaces")
async def list_workspaces(caller: Caller, conn: Conn) -> list[WorkspaceView]:
    return await workspaces.list_workspaces(conn, caller)


@router.post("", operation_id="createWorkspace", status_code=201)
async def create_workspace(body: WorkspaceName, caller: Caller, conn: Conn) -> WorkspaceView:
    """Register a workspace's name; refused past the plan's limit: the workspaces mod's workspaces."""
    return await workspaces.create_workspace(conn, caller, body.name.strip())


@router.patch("/{name}", operation_id="renameWorkspace")
async def rename_workspace(name: Name, body: WorkspaceName, caller: Caller, conn: Conn) -> WorkspaceView:
    return await workspaces.rename_workspace(conn, caller, name, body.name.strip())


@router.delete("/{name}", operation_id="deleteWorkspace", status_code=204)
async def delete_workspace(name: Name, caller: Caller, conn: Conn) -> Response:
    await workspaces.delete_workspace(conn, caller, name)
    return Response(status_code=204)
