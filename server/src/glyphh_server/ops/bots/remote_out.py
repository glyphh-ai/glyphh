"""A result of a bot's run on a rrotor, back over the link (ops/link/session.py): taken once (its seq past the last the
run took, from the rrotor the run is on, while the run is out there or waits), then kept as the run's end or its
question, as a run in the cloud is (runs.ended), the bot's state kept from it. The tokens the rrotor reports (the
whole call's, so each result's are what is new since the last) go on the meter at the org's own key's rate, the
markup alone: the rrotor ran them on the org's key. A run that waits and whose wait expires on the rrotor still waits
here (its answer then goes as a fresh call); a `continue` the rrotor no longer had a run for goes as one too."""

import base64
import logging
from typing import Any

from glyphh.bots import RunResult
from sqlalchemy import select, update

from glyphh_server.db import tenancy
from glyphh_server.llm import meter
from glyphh_server.models import Bot, BotRun
from glyphh_server.ops.bots import decided, prices, runs
from glyphh_server.ops.bots.remote import Remote
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Ran
from glyphh_server.ops.plans import org_version

log = logging.getLogger("glyphh.bots")
OUT: tuple[str, ...] = ("dispatched", "needs_input")


async def _taken(remote: Remote, runtime: Runtime, msg: Ran) -> tuple[bool, Any]:
    """Whether the run is a bot's, and its row when this result is new for it (None: a replay, or not its)."""
    async with remote.svc.engine.begin() as conn:
        await tenancy.enter(conn, runtime.org_id)
        mine = (BotRun.id == msg.run_id, BotRun.rrotor_id == runtime.id, BotRun.status.in_(OUT))
        took = update(BotRun).where(*mine, BotRun.remote_seq < msg.seq).values(remote_seq=msg.seq).returning(BotRun)
        row = (await conn.execute(took)).first()
        if row is not None:
            return True, row
        known = (await conn.execute(select(BotRun.id).where(BotRun.id == msg.run_id))).first()
    return known is not None, None


async def landed(remote: Remote, runtime: Runtime, msg: Ran) -> bool:
    """The result kept on the bot run it answers; False when no bot run has its id (a project's step's, then)."""
    mine, run = await _taken(remote, runtime, msg)
    if run is None:
        if mine:
            log.info("bot run result skipped", extra={"run_id": str(msg.run_id), "seq": msg.seq})
        return mine
    try:
        await _kept(remote, run, msg.result)
    except Exception as err:  # taken: a replay would be skipped, so the run is ended now, saying why
        log.exception("bot run result not kept", extra={"run_id": str(run.id)})
        await runs.failed(remote.svc.engine, run.org_id, run.id, f"The rrotor's result could not be kept: {err}")
    return True


def _again(result: dict[str, Any]) -> bool:
    """A `continue` the rrotor had no run for (it restarted, or let the wait expire): the answer goes as a call."""
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    return result.get("status") == "failed" and result.get("step") == "continue" and data.get("code") == "E_RUN_MISSING"


async def _kept(remote: Remote, run: Any, result: dict[str, Any]) -> None:
    if run.status == "needs_input":  # only its wait expiring there is news: the next answer is a fresh call
        if result.get("status") == "expired":
            await runs.put(remote.svc.engine, run.org_id, run.id, remote={**run.remote, "since": None})
        return
    if _again(result):
        await remote.send(run.org_id, run.id, run.bot_id, run.rrotor_id, None, run.remote.get("answer"))
        return
    ran = RunResult.from_result(result)
    bot = await remote.svc.bot(run.org_id, run.bot_id)
    if ran.state:
        await _state(remote, bot, ran.state)
    tokens = new_tokens(run, ran.tokens or {})
    charged = await bill(remote, bot, tokens)
    since = runs.now().isoformat() if ran.status == "needs_input" else None
    await runs.ended(
        remote.svc.engine, run, ran, ran.output or "", tokens, charged, remote={**run.remote, "since": since}
    )


async def _state(remote: Remote, bot: Any, state: str) -> None:
    async with remote.svc.engine.begin() as conn:
        await tenancy.enter(conn, bot.org_id)
        kept = base64.b64decode(state)
        await conn.execute(update(Bot).where(Bot.id == bot.id).values(state=kept))
        await decided.sync(conn, bot, kept)


def new_tokens(run: Any, said: dict[str, Any]) -> dict[str, int]:
    """What the call spent since its last result: its total so far, past what the run had counted of it."""
    began = run.remote
    got = {k: int(said.get(f"{k}_tokens") or 0) for k in ("input", "output")}
    return {
        "input_tokens": max(0, int(began.get("in", 0)) + got["input"] - run.input_tokens),
        "output_tokens": max(0, int(began.get("out", 0)) + got["output"] - run.output_tokens),
    }


async def bill(remote: Remote, bot: Any, tokens: dict[str, int]) -> int:
    """The tokens on the meter at the org's own key's rate (the markup alone): drawn from the plan's allowance, the
    rest charged. Answers the charge, in microdollars."""
    if not tokens["input_tokens"] and not tokens["output_tokens"]:
        return 0
    async with remote.svc.engine.begin() as conn:
        await tenancy.enter(conn, bot.org_id)
        plan = await org_version(conn, bot.org_id)
    admitted = meter.Admitted(bot.org_id, plan.name, plan.llm_tokens)
    priced = prices.charged(bot.model, own_key=True)
    return await meter.record(remote.svc.engine, admitted, priced, tokens["input_tokens"], tokens["output_tokens"])
