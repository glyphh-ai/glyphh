"""Training a bot's gates from its decisions (docs/specs/bots.md, 12), each through the gate's own Ada model on the
bot's key, as `wrong` is: a decision relabelled (its case recorded with the outcome it should have had, or its own
precedent graded again), one confirmed right (recorded as a precedent, unless it is one already), a labelled case
added by hand, and a precedent forgotten. Each is a go of the runner, so the runner's own record (its runs.sqlite)
says the same, and none is done while a run of the bot is going."""

import uuid
from typing import Any

from glyphh.bots.runner import Runner, held
from sqlalchemy import update

from glyphh_server.db import tenancy
from glyphh_server.errors import Invalid
from glyphh_server.models import BotDecision
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import decisions, mend
from glyphh_server.ops.bots.decision_views import Trained
from glyphh_server.ops.bots.goes import Goes

D = BotDecision


def outcome_of(bot: Any, gate: str, outcome: str) -> None:
    gates = decisions.outcomes(bot)
    if gate not in gates:
        raise Invalid(f"{bot.slug} has no gate {gate} ({', '.join(gates) or 'none'}).", reason="gate")
    if outcome not in gates[gate]:
        raise Invalid(f"{outcome} is not one of gate {gate}'s outcomes ({', '.join(gates[gate])}).", reason="outcome")


def precedent_id(got: Any) -> str:
    """The id Ada gave a case it recorded."""
    data = getattr(got, "data", None) or (got if isinstance(got, dict) else {})
    return str(data.get("id") or "")


def kept(runner: Runner, d: Any) -> dict[str, Any] | None:
    """The runner's own record of a decision."""
    if not d.loop_run:
        return None
    mine = (d.step, d.n, d.key)
    found = runner.store.decisions(run=d.loop_run, gate=d.gate)
    return next((r for r in found if (r["step"], r["n"], r["key"]) == mine), None)


def relearn(runner: Runner, d: Any, outcome: str) -> str:
    """The decision's case learned with `outcome`: its own precedent graded again when known, else recorded."""
    model = runner.ada.model(runner.bot.gate_model(d.gate))
    if d.precedent:
        model.grade(d.precedent, outcome)
        made = d.precedent
    else:
        made = precedent_id(model.record(d.case, outcome))
    if (own := kept(runner, d)) is not None:
        runner.store.mark(own, wrong=outcome, recorded=1)
    return made


def confirmed(runner: Runner, d: Any) -> str:
    """A decision said right: recorded as a precedent with what it is now, unless it is one already."""
    if d.recorded:
        return d.precedent
    made = precedent_id(runner.ada.model(runner.bot.gate_model(d.gate)).record(d.case, d.corrected or d.outcome))
    if (own := kept(runner, d)) is not None:
        runner.store.mark(own, recorded=1)
    return made


async def put(svc: Goes, who: Principal, ids: list[uuid.UUID], **values: Any) -> None:
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        await conn.execute(update(D).where(D.id.in_(ids)).values(**values))


async def shown(svc: Goes, who: Principal, bot: Any, ids: list[uuid.UUID], said: str, precedents: int) -> Trained:
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        found = await decisions.rows(conn, bot, ids)
    gates = decisions.outcomes(bot)
    return Trained(decisions=[decisions.view(r, gates) for r in found], precedents=precedents, said=said)


def one_gate(rows: list[Any]) -> str:
    gates = sorted({d.gate for d in rows})
    if len(gates) != 1:
        raise Invalid(f"Those decisions are of several gates ({', '.join(gates)}): one gate at a time.", reason="gate")
    return gates[0]


def counted(act: Any, gate: str) -> Any:
    """`act` on the runner, and how many precedents the gate holds after it."""

    def both(runner: Runner) -> tuple[Any, int]:
        done = act(runner)
        return done, held(runner.ada, runner.bot.gate_model(gate))

    return both


def plural(n: int) -> str:
    return f"{n} decision{'s' * (n != 1)}"


async def relabel(svc: Goes, who: Principal, bot: Any, rows: list[Any], outcome: str) -> Trained:
    """Each decision relabelled `outcome`, learned by its gate."""
    bot, gate = await mend._idle(svc, who, bot.slug), one_gate(rows)
    outcome_of(bot, gate, outcome)
    act = counted(lambda r: {d.id: relearn(r, d, outcome) for d in rows}, gate)
    made, precedents = (await svc.go(bot, act)).answer
    for d in rows:
        await put(svc, who, [d.id], corrected=outcome, precedent=made[d.id], recorded=True, confirmed=False)
    said = f"{plural(len(rows))} relabelled {outcome}, learned by gate {gate} ({precedents} precedents)"
    return await shown(svc, who, bot, [d.id for d in rows], said, precedents)


async def confirm(svc: Goes, who: Principal, bot: Any, rows: list[Any]) -> Trained:
    """Each decision said right, kept as a precedent of its gate."""
    bot, gate = await mend._idle(svc, who, bot.slug), one_gate(rows)
    made, precedents = (await svc.go(bot, counted(lambda r: {d.id: confirmed(r, d) for d in rows}, gate))).answer
    for d in rows:
        await put(svc, who, [d.id], confirmed=True, recorded=True, precedent=made[d.id])
    said = f"{plural(len(rows))} confirmed right, kept as precedents of gate {gate} ({precedents} precedents)"
    return await shown(svc, who, bot, [d.id for d in rows], said, precedents)
