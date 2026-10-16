"""Models: the person's models, their versions (one per commit) and deploying a version to a runtime."""

import uuid
from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import models
from glyphh_server.ops.github_app import GitHubApp
from glyphh_server.ops.link.calls import DeployAction
from glyphh_server.ops.link.protocol import Name, Sha
from glyphh_server.ops.models import Deployed, ModelView, VersionView

router = APIRouter(prefix="/v1/models", tags=["models"])


class NewModel(BaseModel):
    name: Name = Field(description="The model's name, as its glyphh.json names it")
    repo: str | None = Field(None, max_length=200, pattern=r"^[\w.-]+/[\w.-]+$", description="owner/name on GitHub")


class NewVersion(BaseModel):
    commit_sha: Sha
    manifest: dict[str, Any] = Field(description="The commit's glyphh.json")


class DeployBody(BaseModel):
    version: int = Field(ge=1)
    runtime_id: uuid.UUID | None = Field(
        None, description="One of your runtimes; default this install's, else the latest seen"
    )
    action: DeployAction = "deploy"


def github_app(request: Request) -> GitHubApp | None:
    """The GitHub App, for the repo token a deploy of a model in git carries; None where it is not set up."""
    state = request.app.state
    if not state.settings.github_app_configured:
        return None
    return GitHubApp(state.http, state.settings, state.github_key)


@router.get("", operation_id="listModels")
async def list_models(caller: Caller, conn: Conn) -> list[ModelView]:
    """Your models, oldest first, each with its versions and where each is active."""
    return await models.list_models(conn, caller)


@router.post("", operation_id="createModel", status_code=201)
async def create_model(body: NewModel, caller: Caller, conn: Conn) -> ModelView:
    """A new model (within Ada's models limit, E_LIMIT past it; E_FORBIDDEN without Ada)."""
    return await models.create_model(conn, caller, body.name, body.repo)


@router.get("/{model_id}", operation_id="getModel")
async def get_model(model_id: uuid.UUID, caller: Caller, conn: Conn) -> ModelView:
    return await models.get_model(conn, caller, model_id)


@router.delete("/{model_id}", operation_id="deleteModel", status_code=204)
async def delete_model(model_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    """Drops the record, its versions, deployments and runs. The rrotor keeps its copy until a `remove` deploy."""
    await models.delete_model(conn, caller, model_id)
    return Response(status_code=204)


@router.post("/{model_id}/versions", operation_id="addModelVersion", status_code=201)
async def add_version(model_id: uuid.UUID, body: NewVersion, caller: Caller, conn: Conn) -> VersionView:
    """The next version: a commit not yet one (E_CONFLICT `commit_known` when it is)."""
    return await models.add_version(conn, caller, model_id, body.commit_sha, body.manifest)


@router.post("/{model_id}/deploy", operation_id="deployModel")
async def deploy_model(model_id: uuid.UUID, body: DeployBody, caller: Caller, conn: Conn, request: Request) -> Deployed:
    """Deploy, activate or remove a version on your runtime. The rrotor answers `deployed` on its link, and only then
    is the version active there. A runtime not connected is E_UNAVAILABLE."""
    hub = request.app.state.hub
    return await models.deploy_version(
        conn, hub, github_app(request), caller, model_id, body.version, body.runtime_id, body.action
    )
