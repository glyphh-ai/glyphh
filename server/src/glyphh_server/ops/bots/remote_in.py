"""What a bot's run on a rrotor is sent (glyphh_bot's `agent`, rrotor 0.9.0; docs/specs/bot-agent-loop.md, 6.2): the
turn itself (the bot's system prompt, the message, its model, effort and limits), the tools that live on this server
(each by name, with what it does and takes: the rrotor calls them at tool_url), its plugins as files by path, and
where its tools are: POST tool_url (this server, https) with tool_token, a token minted for this run alone,
short-lived (it is kept in the run's record on the machine): its run and org, signed."""

import uuid
from typing import Any

from glyphh_server.config import Settings
from glyphh_server.errors import GlyphhError, Invalid, Unauthorized
from glyphh_server.ops.auth import signed
from glyphh_server.ops.bots.agent.turn import Turn

TOKEN_SECONDS: int = 6 * 3600  # a call's tool token: past its run's 30 minutes and its 15-minute waits
KIND: str = "bot-tool"
BAD_TOKEN: str = "That is not a tool token of this run."
NOT_HTTPS: str = "A rrotor reaches this server only over https: its public address must be https://."


def mint(secret: str, run_id: uuid.UUID, org_id: uuid.UUID) -> str:
    return signed.sign(secret, {"k": KIND, "run": str(run_id), "org": str(org_id)}, TOKEN_SECONDS)


def opened(secret: str, token: str, run_id: uuid.UUID) -> uuid.UUID:
    """The org of the run the token was minted for; Unauthorized for any other token, or once it has expired."""
    try:
        said = signed.verify(secret, token)
    except (GlyphhError, ValueError, KeyError):
        raise Unauthorized(BAD_TOKEN) from None
    if said.get("k") != KIND or said.get("run") != str(run_id):
        raise Unauthorized(BAD_TOKEN)
    return uuid.UUID(said["org"])


def tool_url(settings: Settings, run_id: uuid.UUID) -> str:
    return f"{settings.base_url}/v1/bots/runs/{run_id}/tool"


def inputs(settings: Settings, org_id: uuid.UUID, run_id: uuid.UUID, turn: Turn, found: list[Any]) -> dict[str, Any]:
    """glyphh_bot's inputs for one call of `agent`: the turn (`turn.session` set: it carries a waiting run on) and
    the bot's plugins (`found`)."""
    url = tool_url(settings, run_id)
    if not url.startswith("https://"):
        raise Invalid(NOT_HTTPS, reason="not_https")
    tools = [
        {"name": t.name, "description": t.description, "input_schema": t.schema, "read_only": t.read_only}
        for t in turn.tools
    ]
    sent: dict[str, Any] = {
        "system": turn.system,
        "message": turn.message,
        "tools": tools,
        "plugins": [{"name": p.name, "files": p.files, "code": p.code} for p in found],
        "skills": turn.skills,
        "model": turn.model,
        "effort": turn.effort,
        "limits": {"turns": turn.turns, "seconds": int(turn.seconds)},
        "resume": bool(turn.session),
        "tool_url": url,
        "tool_token": mint(settings.secret_key, run_id, org_id),
        "claude": "api",
    }
    return sent
