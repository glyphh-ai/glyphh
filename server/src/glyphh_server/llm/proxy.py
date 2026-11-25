"""A hosted model's request passed to the inference server (GLYPHH_INFERENCE_URL, OpenAI-compatible: vLLM serving each
model under its registry id) and its answer passed back as it came, its tokens read from the answer's `usage`. A
stream asks the server for its usage (stream_options.include_usage) and is charged from its last chunk; one cut off
before it (the caller gone) is charged from an estimate: its messages' characters / 4 in, its content's / 4 out. A
refusal of the server's (a 4xx) is the caller's 400 E_INVALID with its message; the server down or failing is 503
E_UNAVAILABLE; neither is charged."""

import asyncio
import contextlib
import json
import math
from collections.abc import AsyncIterator
from typing import Any

import httpx

from glyphh_ada.errors import BadRequest
from glyphh_server.config import Settings
from glyphh_server.errors import Unavailable
from glyphh_server.llm import meter
from glyphh_server.llm.meter import Admitted
from glyphh_server.llm.registry import Model

PATH: str = "/v1/chat/completions"
DONE: str = "data: [DONE]"


def request(settings: Settings, http: httpx.AsyncClient, body: dict[str, Any]) -> httpx.Request:
    if not settings.inference_base:
        raise Unavailable("Hosted models are not served on this server yet.", reason="inference_off")
    headers = {"authorization": f"Bearer {settings.inference_key}"} if settings.inference_key else {}
    timeout = httpx.Timeout(settings.inference_timeout, connect=5.0)
    return http.build_request("POST", f"{settings.inference_base}{PATH}", json=body, headers=headers, timeout=timeout)


async def checked(res: httpx.Response) -> None:
    """The server's answer is a good one, else refused: its 4xx the caller's, anything else its being unavailable."""
    if res.status_code == 200:
        return
    said = (await res.aread()).decode(errors="replace")
    await res.aclose()
    if 400 <= res.status_code < 500:
        with contextlib.suppress(ValueError, KeyError, TypeError):
            said = json.loads(said)["error"]["message"]
        raise BadRequest(f"The model refused the request: {said}"[:2000], reason="inference", status=res.status_code)
    raise Unavailable("The model is unavailable for a moment: try again.", reason="inference", status=res.status_code)


async def send(http: httpx.AsyncClient, built: httpx.Request) -> httpx.Response:
    try:
        res = await http.send(built, stream=True)
    except httpx.HTTPError as err:
        raise Unavailable("The model is unavailable for a moment: try again.", reason="inference") from err
    await checked(res)
    return res


def estimate(body: dict[str, Any], out_chars: int) -> tuple[int, int]:
    return math.ceil(len(json.dumps(body.get("messages"))) / 4), math.ceil(out_chars / 4)


def used(answer: dict[str, Any]) -> tuple[int, int] | None:
    """The tokens an answer (or a stream's last chunk) says it used; None when it does not say."""
    said = answer.get("usage")
    if not isinstance(said, dict):
        return None
    return int(said.get("prompt_tokens") or 0), int(said.get("completion_tokens") or 0)


async def complete(state: Any, who: Admitted, model: Model, body: dict[str, Any]) -> dict[str, Any]:
    res = await send(state.http, request(state.settings, state.http, body))
    try:
        answer = json.loads(await res.aread())
    except ValueError as err:
        raise Unavailable("The model answered badly: try again.", reason="inference") from err
    finally:
        await res.aclose()
    content = "".join(str((c.get("message") or {}).get("content") or "") for c in answer.get("choices") or [])
    await meter.record(state.engine, who, model, *(used(answer) or estimate(body, len(content))))
    return dict(answer)


class Seen:
    """What a stream has said so far: its usage, once its last chunk gives it, and its content's characters."""

    def __init__(self) -> None:
        self.usage: tuple[int, int] | None = None
        self.chars = 0

    def line(self, line: str) -> None:
        if not line.startswith("data:") or line == DONE:
            return
        try:
            chunk = json.loads(line.removeprefix("data:"))
        except ValueError:
            return
        self.usage = used(chunk) or self.usage
        for choice in chunk.get("choices") or []:
            self.chars += len(str((choice.get("delta") or {}).get("content") or ""))


async def opened(state: Any, body: dict[str, Any]) -> httpx.Response:
    """The server's stream, open and good (so a refusal is the caller's answer, not a broken stream)."""
    wanted = {**body, "stream_options": {**(body.get("stream_options") or {}), "include_usage": True}}
    return await send(state.http, request(state.settings, state.http, wanted))


async def relay(
    state: Any, who: Admitted, model: Model, body: dict[str, Any], res: httpx.Response
) -> AsyncIterator[bytes]:
    """The stream passed on line by line; charged when it ends however it ends."""
    seen = Seen()
    try:
        async for line in res.aiter_lines():
            seen.line(line)
            yield f"{line}\n".encode()
    finally:
        tokens = seen.usage or estimate(body, seen.chars)
        await asyncio.shield(meter.record(state.engine, who, model, *tokens))
        await res.aclose()
