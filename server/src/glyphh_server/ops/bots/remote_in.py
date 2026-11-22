"""What a bot's run on a rrotor is sent (glyphh_bot's `run`, docs/specs/bots.md, 9): its package as files by path (as
the cloud writes it, ops/bots/package.py, with the approvals its permission mode adds: cloud.guarded), the runner's
state, what it is given or the answer it carries on with, its Ada by its own key, its Claude (the rrotor's: the org's
Anthropic key set there), and where its tools are: POST tool_url (this server, https) with tool_token, a token
minted for this run alone, short-lived (it is kept in the run's record on the machine): its run and org, signed."""

import base64
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from glyphh_server.config import Settings
from glyphh_server.errors import GlyphhError, Invalid, Unauthorized
from glyphh_server.ops.auth import signed
from glyphh_server.ops.auth.sealed import unseal
from glyphh_server.ops.bots import package

TOKEN_SECONDS: int = 6 * 3600  # a call's tool token: past its run's 30 minutes and its 15-minute waits
KIND: str = "bot-tool"
BAD_TOKEN: str = "That is not a tool token of this run."
NOT_HTTPS: str = "A rrotor reaches this server only over https: its public address and Ada's must be https://."


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


def files(bot: Any) -> dict[str, str]:
    """The bot's package by path (the bot as cloud.guarded gives it), as the cloud writes it, without its state (sent
    beside it)."""
    with tempfile.TemporaryDirectory(prefix="glyphh-bot-") as d:
        folder = package.write(Path(d) / "bot", SimpleNamespace(**{**vars(bot), "state": None}))
        return {
            p.relative_to(folder).as_posix(): p.read_text("utf-8") for p in sorted(folder.rglob("*")) if p.is_file()
        }


def state(bot: Any) -> str | None:
    return base64.b64encode(bot.state).decode() if bot.state else None


def tool_url(settings: Settings, run_id: uuid.UUID) -> str:
    return f"{settings.base_url}/v1/bots/runs/{run_id}/tool"


def inputs(settings: Settings, bot: Any, run_id: uuid.UUID, given: str | None, answer: Any) -> dict[str, Any]:
    """glyphh_bot's inputs for one call: from the bot's first step (`given`), or carrying on with `answer`."""
    url = tool_url(settings, run_id)
    if not url.startswith("https://") or not settings.ada_base.startswith("https://"):
        raise Invalid(NOT_HTTPS, reason="not_https")
    sent: dict[str, Any] = {
        "package": files(bot),
        "state": state(bot),
        "ada_base": settings.ada_base,
        "ada_key": unseal(settings.secret_key, bot.ada_key),
        "tool_url": url,
        "tool_token": mint(settings.secret_key, run_id, bot.org_id),
        "model": bot.model,
        "claude": "api",
    }
    if given:
        sent["given"] = given
    if answer is not None:
        sent["answer"] = answer
    return sent
