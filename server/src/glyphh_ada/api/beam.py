"""`POST /v1/beam`: beam search across models (glyphh_ada/beam.py), one model's outcome the next one's question. Each
hop names a model and the role its value goes into (`layer.segment.role`), with `fixed` roles (full paths too) merged
beside it and the output to ask; the hop's probabilities come from the workers through the usual call (api/call.py),
so a model the key does not own, or none, refuses as decide does. A beam counts one read per hop the beam reaches
(requests.py), however many values that hop is asked about; a hop nothing reaches is not asked (its version is read
from the catalog, so a missing model refuses either way) and is not counted."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from glyphh_ada import limits, requests
from glyphh_ada.api.auth import AdaCaller, AdaWho
from glyphh_ada.api.body import bounded
from glyphh_ada.api.call import send
from glyphh_ada.api.meter import admit
from glyphh_ada.beam import WIDTH, Asker, beam

router = APIRouter(tags=["reads"], dependencies=[Depends(bounded)])


def _path(role: str) -> tuple[str, str, str]:
    """A role as layer, segment, role; anything else is refused."""
    parts = role.split(".")
    if len(parts) != 3 or not all(p.strip() for p in parts):
        raise ValueError(f"{role!r} is not a role path: layer.segment.role")
    return parts[0], parts[1], parts[2]


class Hop(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=63, description="The model this hop asks")
    role: str = Field(min_length=5, description="Where the value goes in its case: layer.segment.role")
    fixed: dict[str, Any] | None = Field(None, description="Roles given beside the value, {layer.segment.role: value}")
    output: str | None = Field(None, description="A named output; left out, the default one")

    @field_validator("role")
    @classmethod
    def _role(cls, role: str) -> str:
        _path(role)
        return role

    @field_validator("fixed")
    @classmethod
    def _fixed(cls, fixed: dict[str, Any] | None) -> dict[str, Any] | None:
        for key in fixed or {}:
            _path(key)
        return fixed


class BeamAsk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: str = Field(min_length=1, description="The one value the beam starts from, holding all the mass")
    hops: list[Hop] = Field(min_length=1, max_length=limits.HOPS_MAX, description="The models in order")
    width: int = Field(WIDTH, ge=1, le=limits.WIDTH_MAX, description="Values kept after every hop but the last")
    values: list[str] | None = Field(None, max_length=limits.VALUES_MAX, description="What a model may not know")
    miss: float = Field(0.0, ge=0, le=1, description="The share of each hop's mass spread over `values`")
    clearance: float | None = Field(None, ge=0, le=1, description="Read with less clearance than the key's")


def question(hop: Hop, value: str) -> dict[str, Any]:
    """The probabilities read a hop makes about a value: the value in its role, the fixed roles beside it."""
    data: dict[str, Any] = {}
    for path, held in [*(hop.fixed or {}).items(), (hop.role, value)]:
        layer, segment, role = _path(path)
        data.setdefault(layer, {}).setdefault(segment, {})[role] = held
    args: dict[str, Any] = {"data": data}
    if hop.output is not None:
        args["output"] = hop.output
    return args


def _asker(state: Any, who: AdaCaller, body: BeamAsk, hop: Hop, said: dict[str, Any], about: dict[str, Any]) -> Asker:
    """One hop's asker: its first question counts the hop's read (admit), every question goes to the workers
    unmetered, and `said` learns the model's active version."""

    async def ask(value: str) -> dict[str, float]:
        if said["version"] is None:
            await admit(state, who, requests.BEAM, {}, hop.model)
        args = question(hop, value)
        got, version = await send(
            state, who, hop.model, "probabilities", args, body.clearance, about=about, metered=False
        )
        said["version"] = version
        return dict(got)

    return ask


async def chain(state: Any, who: AdaCaller, body: BeamAsk, about: dict[str, Any]) -> dict[str, Any]:
    """The beam through the body's hops: {outcome, p, ends, paths, lost, hops: [{model, version}], ada}, `ada` the
    Ada version of the last hop asked (`about` gets it, for the headers). A hop nothing reached says its active
    version all the same, read from the catalog."""
    hops: list[dict[str, Any]] = [{"model": hop.model, "version": None} for hop in body.hops]
    askers = [_asker(state, who, body, hop, said, about) for hop, said in zip(body.hops, hops, strict=True)]
    answer = await beam(body.start, askers, body.width, body.values or (), body.miss)
    ada = str(about.get("name"))
    for said in hops:
        if said["version"] is None:
            _, said["version"] = await send(state, who, said["model"], "model", {}, metered=False)
    return {**answer, "hops": hops, "ada": ada}


@router.post("/v1/beam", operation_id="beam")
async def search(body: BeamAsk, who: AdaWho, request: Request) -> dict[str, Any]:
    """Beam search across models: the likeliest end of the chain and its share, every end's share, each end's
    likeliest path from `start`, and the mass that arrived nowhere; each hop's model and version, and the Ada
    version of the last hop asked."""
    about: dict[str, Any] = {}
    answer = await chain(request.app.state, who, body, about)
    request.state.ada = about  # the last hop asked's Ada version, for the answer's headers (api/__init__.py)
    return answer
