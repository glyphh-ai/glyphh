"""A tool's call from a bot running on a rrotor (glyphh_bot's HttpProgram: POST /v1/bots/runs/{id}/tool, bearer the
run's tool token, `{tool, input, run_id}`), answered `{result}` or `{error}` as the cloud's program answers its own
steps (ops/bots/cloud.py): `fetch`, a GET of JSON from one of the bot's hosts (https, the host named in its bot.json,
a public address, no redirects, at most 5 MB), or one of its connections' tools, run as the org with the
connection's account (a tool its connection denies fails, saying so). The bot's egress on the rrotor is its manifest's
hosts alone, so its fetches come here. The token opens this run only, while it is out on its rrotor."""

import asyncio
import urllib.parse
import urllib.request
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from glyphh_server.db import tenancy
from glyphh_server.errors import GlyphhError
from glyphh_server.models import Bot
from glyphh_server.ops.bots import cloud, remote_in, runs
from glyphh_server.ops.bots.goes import Goes

AGENT: str = "glyphh-bot (Glyphh's cloud, for a bot on a rrotor)"
NOT_OUT: str = "This run is not out on its rrotor now."


class ToolIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str = Field(min_length=1, max_length=200, description="fetch, or a tool key the bot's scope names")
    input: Any = Field(None, description="The step's input")
    run_id: str | None = Field(None, max_length=200, description="The runner's own id for the run")


def fetched(spec: dict[str, Any], given: Any) -> Any:
    """`fetch` as the SDK's ctx.http_json has it: a URL, or {url, headers}; https on one of the bot's hosts."""
    if isinstance(given, dict) and isinstance(given.get("url"), str):
        url, headers = given["url"], given.get("headers") if isinstance(given.get("headers"), dict) else {}
    elif isinstance(given, str):
        url, headers = given, {}
    else:
        raise ValueError('fetch takes a URL, or {"url": ..., "headers": {...}}')
    hosts = spec.get("hosts") if isinstance(spec.get("hosts"), list) else []
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        raise ValueError(f"{url} is not https on one of the bot's hosts ({', '.join(map(str, hosts)) or 'none'})")
    sent = {"User-Agent": AGENT, "Accept": "application/json", **{str(k): str(v) for k, v in headers.items()}}
    return cloud.fetch(urllib.request.Request(url, headers=sent), cloud.FETCH_SECONDS)


async def _ran(calls: dict[str, cloud.Call], bot: Any, body: ToolIn) -> Any:
    if body.tool == "fetch":
        return await asyncio.to_thread(fetched, bot.spec, body.input)
    if body.tool not in calls:
        raise ValueError(f"{body.tool} is neither fetch nor a tool the bot may use (scope it on a connection)")
    given = body.input if isinstance(body.input, dict) else {}
    return await asyncio.wait_for(calls[body.tool](given), cloud.TOOL_SECONDS)


async def call(svc: Goes, token: str, run_id: uuid.UUID, body: ToolIn) -> dict[str, Any]:
    """The tool's answer: {"result": ...}, or {"error": why} (the step that ran it fails, saying so)."""
    org_id = remote_in.opened(svc.settings.secret_key, token, run_id)
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        run = await runs.row(conn, run_id)
        if run.status != "dispatched" or run.rrotor_id is None:
            return {"error": NOT_OUT}
        bot = (await conn.execute(select(Bot).where(Bot.id == run.bot_id))).one()
        made, _ = await cloud.calls(svc.pd, conn, bot)
    try:
        return {"result": await _ran(made, bot, body)}
    except GlyphhError as err:
        return {"error": err.message}
    except ValueError as err:  # a tool, host or input the bot may not use: said as it is
        return {"error": str(err)}
    except TimeoutError:
        return {"error": f"{body.tool} took longer than {cloud.TOOL_SECONDS:g} seconds"}
    except Exception as err:  # noqa: BLE001  # the step fails saying why, as a step in the cloud does
        return {"error": f"{body.tool}: {err}"}
