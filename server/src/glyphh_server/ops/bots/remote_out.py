"""A result of a bot's run on a rrotor, back over the link (ops/link/session.py): taken once (its seq past the last the
run took, from the rrotor the run is on, while the run is out there or waits), then kept as the run's end or its
wait. The agent's turn ran on the machine; what it used of this server's (its tools, Ada's decisions, the question it
stopped on) is on the run already (ops/bots/agent/desk.py), so a result adds the bot's final words, the names of the
files it read and changed (never what is in them, ops/bots/files.py), a question about a file's change, and its
tokens: the whole run's so far as the rrotor counts them, so what is new since the run's last result goes on the meter
at the org's own key's rate (the markup alone: it ran on the org's key). A run that waits and whose wait expires on
the rrotor still waits here (its answer then goes as a fresh call); a `continue` the rrotor no longer had a run for
goes as one too."""

import logging
from typing import Any

from sqlalchemy import select, update

from glyphh_server.db import tenancy
from glyphh_server.llm import meter
from glyphh_server.models import BotRun
from glyphh_server.ops.bots import files, prices, runs
from glyphh_server.ops.bots.agent import session
from glyphh_server.ops.bots.agent.run import OUTPUT_MAX, SILENT
from glyphh_server.ops.bots.remote import Remote
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Ran
from glyphh_server.ops.plans import org_version

log = logging.getLogger("glyphh.bots")
OUT: tuple[str, ...] = ("dispatched", "needs_input")
FAILED: str = "The run failed on its rrotor."


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


def _asked(run: Any, result: dict[str, Any], said: dict[str, Any]) -> dict[str, Any]:
    """What the run waits on: the question this server asked (on the run already), else the rrotor's own, about a
    change to a file."""
    if run.question:
        return dict(run.question)
    asked = {"question": str(result.get("prompt") or ""), "options": ["yes", "no"], "approval": True, "step": "file"}
    return asked | {"file": files.change(said.get("file"))}


async def _kept(remote: Remote, run: Any, result: dict[str, Any]) -> None:
    if run.status == "needs_input":  # only its wait expiring there is news: the next answer is a fresh call
        if result.get("status") == "expired":
            await runs.put(remote.svc.engine, run.org_id, run.id, remote={**run.remote, "since": None})
        return
    if _again(result):
        message = str(run.remote.get("message") or "")
        await remote.send(run.org_id, run.id, run.bot_id, run.rrotor_id, message, True)
        return
    said = result["data"] if isinstance(result.get("data"), dict) else {}
    bot = await remote.svc.bot(run.org_id, run.bot_id)
    tokens, again = new_tokens(run, said.get("tokens") if isinstance(said.get("tokens"), dict) else {})
    charged = await bill(remote, bot, tokens)
    began = {**run.remote, "in": run.input_tokens, "out": run.output_tokens} if again else dict(run.remote)
    values: dict[str, Any] = {
        "input_tokens": BotRun.input_tokens + tokens["input_tokens"],
        "output_tokens": BotRun.output_tokens + tokens["output_tokens"],
        "cost_micros": BotRun.cost_micros + charged,
        "remote": began,
    }
    named = files.named(said.get("files"))
    if named is not None:
        values["data"] = {**run.data, files.KEPT: files.merged(run.data.get(files.KEPT), named)}
    status = str(result.get("status") or "failed")
    if status == "needs_input":
        waits = {**began, "since": runs.now().isoformat()}
        values |= {"status": status, "question": _asked(run, result, said), "remote": waits}
    elif status == "done":
        words = str(said.get("output") or "")[:OUTPUT_MAX]
        values |= {"status": "done", "output": words, "error": "" if words else SILENT}
    else:
        values |= {"status": "failed", "error": str(said.get("reason") or FAILED)}
    if status != "needs_input":
        values |= {"question": {}, "finished_at": runs.now()}
    await runs.put(remote.svc.engine, run.org_id, run.id, **values)
    if status != "needs_input":
        await session.drop(remote.svc.engine, run.org_id, run.id)


def new_tokens(run: Any, said: dict[str, Any]) -> tuple[dict[str, int], bool]:
    """What the rrotor's run spent since its last result, and whether the rrotor began it again. The rrotor says the
    run's total so far, through every call of it (it keeps the count with the session); a total under what the run
    has counted of it is a run the rrotor began again (it had lost the session), all of whose tokens are new."""
    got = {k: max(0, int(said.get(f"{k}_tokens") or 0)) for k in ("input", "output")}
    began = {"input": int(run.remote.get("in", 0)), "output": int(run.remote.get("out", 0))}
    had = {"input": run.input_tokens - began["input"], "output": run.output_tokens - began["output"]}
    again = any(got[k] < had[k] for k in got)
    new = got if again else {k: got[k] - had[k] for k in got}
    return {"input_tokens": new["input"], "output_tokens": new["output"]}, again


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
