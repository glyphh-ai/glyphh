"""What is done to a bot's runs besides running them: an answer checked against the question it answers, a gate's
wrong call corrected (learned as a precedent), a waiting run cancelled, and what its gates learned. Each but the
answer is a go of the runner on the bot's state, so none is done while a run of the bot is going."""

import uuid
from typing import Any

from glyphh.bots import BotError, Runner, gate_stats, parse_answers

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, Invalid
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import runs, store
from glyphh_server.ops.bots.goes import Goes
from glyphh_server.ops.bots.views import RunView, WrongIn

NOT_WAITING: str = "That run is not waiting on an answer."
GOING: str = "The bot has a run going: wait for it to end."


def fits(question: dict[str, Any], answer: Any) -> Any:
    """The answer, as the runner takes it, when it answers the question; else Invalid (the run keeps waiting)."""
    options = list(question.get("options") or [])
    if question.get("batch"):
        try:
            return parse_answers(answer, [b["n"] for b in question["batch"]], options)
        except ValueError as err:
            raise Invalid(str(err), reason="answer") from err
    said = " ".join(answer) if isinstance(answer, list) else answer
    if not isinstance(said, str) or said.strip().lower() not in options:
        raise Invalid(f"Answer with one of {', '.join(options)}.", reason="answer", options=options)
    return said.strip().lower()


async def _run(svc: Goes, who: Principal, run_id: uuid.UUID) -> Any:
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        return await runs.row(conn, run_id)


async def _idle(svc: Goes, who: Principal, slug: str) -> Any:
    """The bot, when no run of it is going (its state is the runner's alone while one is)."""
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        bot = await store.row(conn, slug)
        shown = await store.view(conn, bot)
    if shown.last_run is not None and shown.last_run.status in ("queued", "running"):
        raise Conflict(GOING, slug=slug)
    return bot


async def wrong(svc: Goes, who: Principal, run_id: uuid.UUID, body: WrongIn) -> dict[str, Any]:
    found = await _run(svc, who, run_id)
    bot = await _idle(svc, who, found.slug)
    if not found.loop_run:
        raise Invalid("That run passed no gate: there is nothing to correct.", reason="run")
    try:
        left = await svc.go(bot, lambda r: r.wrong(found.loop_run, body.outcome, body.gate, body.item))
    except BotError as err:
        raise Invalid(err.message, reason="wrong") from err
    return dict(left.answer)


async def cancel(svc: Goes, who: Principal, run_id: uuid.UUID) -> RunView:
    found = await _run(svc, who, run_id)
    if found.status != "needs_input":
        raise Conflict(NOT_WAITING, run_id=str(run_id))
    bot = await _idle(svc, who, found.slug)

    def ended(r: Runner) -> None:  # a run that waits on the person is always in the runner's store
        had = r.store.get(found.loop_run)
        r.store.save(found.loop_run, "failed", had["at"], had["data"], {}, "cancelled", had["log"])

    await svc.go(bot, ended)
    await runs.failed(svc.engine, who.org_id, run_id, "cancelled")
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        return await runs.get(conn, run_id)


async def gates(svc: Goes, who: Principal, slug: str) -> dict[str, Any]:
    bot = await _idle(svc, who, slug)
    return dict((await svc.go(bot, lambda r: gate_stats(r))).answer["gates"])
