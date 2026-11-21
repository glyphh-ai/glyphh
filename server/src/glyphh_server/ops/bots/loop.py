"""One run of a bot: Claude given the bot's instructions and the run's input, with the tools the bot may use, turn by
turn until it answers. Each of Claude's turns is let in by the hosted models' meter first (the plan's allowance, then
the org's balance) and accounted after; the run stops at its turns or its dollars. Claude's content is kept as it came
back (its thinking and fallback blocks too); a tool that fails is answered as an error for Claude to work around. Each
step is written to the run as it is taken."""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from fastapi.encoders import jsonable_encoder

from glyphh_server.errors import GlyphhError
from glyphh_server.llm import meter
from glyphh_server.ops.bots import prices, runs
from glyphh_server.ops.bots.tools import Offered

log = logging.getLogger("glyphh.bots")
BETAS: list[str] = ["server-side-fallback-2026-07-01"]
NO_FALLBACK: frozenset[str] = frozenset({"claude-haiku-5-5"})  # Haiku has no server-side fallback
MAX_TOKENS: int = 16_000
RESULT_MAX: int = 50_000
SYSTEM: str = """You are {name}, a Glyphh bot: you do a job for the people of an organization, on your own, with the \
tools you are given. {summary}

What you do, as the people who made you wrote it:

{instructions}

Work until the job is done, then answer with what you did and what came of it. If a tool fails, say what failed and \
work around it where you can. If the job needs a tool you do not have, say so instead of guessing."""


class Stopped(Exception):
    """The run ends here, failed, saying why."""


@dataclass
class Run:
    services: Any  # the bots service (ops/bots/service.py): engine, redis, settings
    client: Any  # an AsyncAnthropic
    who: Any  # the Principal who started it
    bot: Any
    run_id: Any
    offered: Offered
    given: str = ""  # what the run was given to work on
    spent: int = 0  # what its tokens were worth at the model's rates, microdollars

    async def step(self, kind: str, name: str, given: Any, out: Any, is_error: bool = False) -> None:
        taken = {"kind": kind, "name": name, "input": given, "output": out, "is_error": is_error}
        await runs.step(self.services.engine, self.bot.org_id, self.run_id, jsonable_encoder(taken))


def request(run: Run, messages: list[Any]) -> dict[str, Any]:
    bot = run.bot
    system = SYSTEM.format(name=bot.name, summary=bot.summary, instructions=bot.instructions or "(none given)")
    sent: dict[str, Any] = {
        "model": bot.model,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": messages,
        "output_config": {"effort": "high"},
    }
    if run.offered.defs:
        sent["tools"] = run.offered.defs
    if bot.model not in NO_FALLBACK:
        sent |= {"betas": BETAS, "fallbacks": "default"}
    return sent


async def turn(run: Run, messages: list[Any]) -> Any:
    """One of Claude's turns, metered: let in, asked, its tokens accounted."""
    svc, bot = run.services, run.bot
    if run.spent >= bot.usd_per_run_micros:
        raise Stopped(f"The run spent its limit, ${bot.usd_per_run_micros / 1_000_000:,.2f}.")
    admitted = await meter.admit(svc.engine, svc.redis, svc.settings, bot.org_id)
    answer = await run.client.beta.messages.create(**request(run, messages))
    model = prices.priced(getattr(answer, "model", bot.model), bot.model)
    i, o = answer.usage.input_tokens, answer.usage.output_tokens
    charged = await meter.record(svc.engine, admitted, model, i, o)
    run.spent += model.cost_micros(i, o)
    await runs.used(svc.engine, bot.org_id, run.run_id, (i, o, charged))
    return answer


def said(content: list[Any]) -> str:
    return "\n\n".join(b.text for b in content if getattr(b, "type", "") == "text" and b.text).strip()


def _shown(out: Any) -> str:
    text = out if isinstance(out, str) else json.dumps(jsonable_encoder(out), default=str)
    return text[:RESULT_MAX]


async def use(run: Run, block: Any) -> dict[str, Any]:
    """One tool call, answered as its result (an error as one Claude sees)."""
    given = block.input if isinstance(block.input, dict) else {}
    kind = run.offered.calls.get(block.name, ("tool", None))[0]
    try:
        kind, out = await run.offered.call(block.name, given)
        failed = False
    except GlyphhError as err:
        out, failed = {"error": err.message, **err.detail}, True
    except Exception as err:  # a tool's own crash is the tool's failure, not the run's
        log.exception("bot tool %s failed", block.name)
        out, failed = {"error": f"{type(err).__name__}: {err}"}, True
    await run.step(kind, block.name, given, out, failed)
    return {"type": "tool_result", "tool_use_id": block.id, "content": _shown(out), "is_error": failed}


async def answered(run: Run, messages: list[Any]) -> str:
    """Claude's turns until it answers: its final words."""
    for _ in range(run.bot.max_turns):
        answer = await turn(run, messages)
        messages.append({"role": "assistant", "content": answer.content})
        if text := said(answer.content):
            await run.step("text", "claude", None, text)
        reason = answer.stop_reason
        if reason == "tool_use":
            calls = [b for b in answer.content if getattr(b, "type", "") == "tool_use"]
            messages.append({"role": "user", "content": list(await asyncio.gather(*(use(run, b) for b in calls)))})
        elif reason == "pause_turn":
            continue  # the server paused a long turn: sent back as it is, it goes on
        elif reason == "refusal":
            details = getattr(answer, "stop_details", None)
            raise Stopped(f"Claude declined the job ({getattr(details, 'category', None) or 'no reason given'}).")
        elif reason == "max_tokens":
            raise Stopped("Claude's turn ran past its room for one answer.")
        else:
            return text
    raise Stopped(f"The run took its limit of {run.bot.max_turns} turns.")


async def go(run: Run) -> None:
    """The run, from queued to done or failed."""
    engine, org_id, run_id = run.services.engine, run.bot.org_id, run.run_id
    await runs.start(engine, org_id, run_id)
    try:
        output = await answered(run, [{"role": "user", "content": run.given or "Begin."}])
    except Stopped as err:
        await runs.finish(engine, org_id, run_id, "", str(err))
    except GlyphhError as err:
        await runs.finish(engine, org_id, run_id, "", err.message)
    except Exception as err:
        log.exception("bot run %s failed", run_id)
        await runs.finish(engine, org_id, run_id, "", f"The run failed: {type(err).__name__}: {err}")
    else:
        await runs.finish(engine, org_id, run_id, output)
