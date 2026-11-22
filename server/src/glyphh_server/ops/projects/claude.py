"""Claude with tools, for a project's step on Glyphh cloud (ops/projects/cloud.py): one conversation in which Claude
calls the step's tools (the repo's files, ops/projects/repo.py) until it answers in words. Each request is let in by
the hosted models' meter and its tokens charged after (`metered`, as a bot's agent steps are: ops/bots/goes.py), on
the org's own Anthropic key or Glyphh's."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from glyphh_server.errors import Unavailable

MAX_TOKENS: int = 16_000
ROUNDS: int = 60  # requests in one step
Call = Callable[[str, dict[str, Any]], Awaitable[str]]  # a tool run: what it answers (an error said in words)
Metered = Callable[[Callable[[], Awaitable[Any]]], Awaitable[Any]]  # a request, let in and charged


@dataclass
class Said:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class Claude:
    """Anthropic's Messages API on one key and model (a test sets a fake with the same `create`)."""

    def __init__(self, key: str, model: str) -> None:
        import anthropic

        self.client, self.model = anthropic.AsyncAnthropic(api_key=key, max_retries=2), model

    async def create(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], effort: str | None = None
    ) -> Any:
        import anthropic

        asked = {"model": self.model, "max_tokens": MAX_TOKENS, "system": system, "messages": messages}
        asked |= {"output_config": {"effort": effort}} if effort else {}  # a run's effort: low, medium or high
        try:
            return await self.client.messages.create(**asked, tools=tools)
        except anthropic.APIError as err:
            raise Unavailable(f"Claude did not answer: {err}", reason="claude") from err


def _block(b: Any) -> dict[str, Any]:
    if b.type == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
    return {"type": "text", "text": getattr(b, "text", "")}


async def converse(
    claude: Any, metered: Metered, words: tuple[str, str], tools: list[dict[str, Any]], call: Call, effort: Any = None
) -> Said:
    """The step's conversation (`words`: its system prompt and its prompt): Claude asked, its tool calls run and
    answered, until it says its piece."""
    system, prompt = words
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    said = Said("")

    async def ask() -> Any:
        return await claude.create(system, messages, tools, effort)

    for _ in range(ROUNDS):
        reply = await metered(ask)
        said.input_tokens += int(reply.usage.input_tokens)
        said.output_tokens += int(reply.usage.output_tokens)
        blocks = [_block(b) for b in reply.content if b.type in ("text", "tool_use")]
        uses = [b for b in blocks if b["type"] == "tool_use"]
        if not uses:
            said.text = "\n".join(b["text"] for b in blocks).strip()
            return said
        answers = [
            {"type": "tool_result", "tool_use_id": u["id"], "content": await call(u["name"], dict(u["input"] or {}))}
            for u in uses
        ]
        messages += [{"role": "assistant", "content": blocks}, {"role": "user", "content": answers}]
    raise Unavailable(f"The step did not end within {ROUNDS} requests to Claude.", reason="claude")
