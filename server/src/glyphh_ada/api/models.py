"""The org's models: list, make one from a JSON spec, read one, delete one (by its name, confirmed)."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from glyphh_ada import limits
from glyphh_ada.api.auth import AdaWho
from glyphh_ada.api.body import bounded
from glyphh_ada.api.call import call
from glyphh_server.errors import Conflict

router = APIRouter(prefix="/v1/models", tags=["models"], dependencies=[Depends(bounded)])


class NewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=limits.NAME_PATTERN, description="Lower case letters, digits, _ . -; at most 63")
    spec: dict[str, Any] = Field(description="The model's spec: layers, segments, roles, output, settings")
    ada: str | None = Field(
        None, max_length=40, description="Its Ada version (GET /v1/ada); left out, the latest stable"
    )


@router.get("", operation_id="listAdaModels")
async def list_models(who: AdaWho, request: Request) -> dict[str, Any]:
    """Every model of the org: its name, active version and how many precedents it holds."""
    return {"models": await call(request, who, "", "models", {})}


@router.post("", operation_id="createAdaModel", status_code=201)
async def create_model(body: NewModel, who: AdaWho, request: Request) -> dict[str, Any]:
    """A model from its spec, checked by the kernel and against the cloud's bounds: version 1, empty, on the Ada
    version named (left out, the latest stable; an unknown, retired, deprecated or closed one is refused)."""
    return dict(await call(request, who, body.name, "create", body.model_dump(exclude={"name"}, exclude_none=True)))


@router.get("/{name}", operation_id="getAdaModel")
async def get_model(name: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """One model: its active spec and version, how many precedents it holds, and its Ada version (`ada`,
    `ada_status`, `ada_notice`: a newer stable or beta out, its version deprecated or retired, or moved)."""
    return dict(await call(request, who, name, "model", {}))


@router.delete("/{name}", operation_id="deleteAdaModel")
async def delete_model(name: str, confirm: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """Delete a model and every precedent it holds; `confirm` repeats its name. Not undone."""
    if confirm != name:
        raise Conflict("Confirm by sending the model's name as ?confirm=.", reason="confirm", model=name)
    return dict(await call(request, who, name, "delete", {}))
