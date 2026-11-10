"""The Glyphh-hosted models at the Ada hosts (docs/specs/tokens.md), with GLYPHH_LLM on: `POST /v1/chat/completions`,
OpenAI's body and answer (`stream: true` too), `model` one of GET /v1/llm/models' ids. Called with an API key or a
sign-in exactly as the Ada API is (api/auth.py), limited to the plan's calls a second, let in while the month's
tokens or the overage balance last (402 E_BALANCE), and charged after its reply (llm/meter.py)."""

import json
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from redis.exceptions import RedisError

from glyphh_ada import limits
from glyphh_ada.api.auth import AdaWho
from glyphh_ada.errors import BadRequest, ModelMissing
from glyphh_server.api.llm import list_models
from glyphh_server.errors import TooLarge, Unavailable
from glyphh_server.llm import meter, proxy, registry
from glyphh_server.llm.registry import Model

router = APIRouter(tags=["hosted models"])
router.add_api_route("/v1/llm/models", list_models, methods=["GET"], operation_id="listModelsHere")


async def _body(request: Request) -> tuple[dict[str, Any], Model]:
    raw = await request.body()
    if len(raw) > limits.BODY_MAX:
        raise TooLarge(f"A request's body is at most {limits.BODY_MAX} bytes here.", max=limits.BODY_MAX)
    try:
        body = json.loads(raw)
    except ValueError:
        body = None
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
        raise BadRequest("Send OpenAI's chat body: a JSON object with `model` and `messages`.", reason="body")
    model = registry.find(body.get("model"))
    if model is None:
        raise ModelMissing(f"No hosted model is named {body.get('model')!r}: GET /v1/llm/models lists them.")
    return body, model


@router.post("/v1/chat/completions", operation_id="chatCompletions")
async def chat_completions(who: AdaWho, request: Request) -> Response:
    """A chat completion from a Glyphh-hosted model, as OpenAI answers one; with `stream: true`, as server-sent
    events, its last chunk giving the request's usage."""
    state = request.app.state
    body, model = await _body(request)
    try:
        admitted = await meter.admit(state.engine, state.redis, state.settings, who.org_id)
    except RedisError:
        raise Unavailable("The model is unreachable for a moment: try again.", reason="queue") from None
    if not body.get("stream"):
        return JSONResponse(await proxy.complete(state, admitted, model, body))
    res = await proxy.opened(state, body)
    return StreamingResponse(proxy.relay(state, admitted, model, body, res), media_type="text/event-stream")
