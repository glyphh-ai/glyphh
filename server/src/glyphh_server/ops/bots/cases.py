"""A gate's cases by hand (docs/specs/bots.md, 12): a labelled case added (made from an item's fields as a run makes
it, or given as the case itself) and a precedent forgotten, each a go of the runner through the gate's Ada model, so
none is done while a run of the bot is going."""

import uuid
from typing import Any

from glyphh.bots.runner import Runner, fill, held
from sqlalchemy import delete, insert, update

from glyphh_server.db import tenancy
from glyphh_server.errors import Invalid
from glyphh_server.models import BotDecision
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import decisions, mend, readable
from glyphh_server.ops.bots.decision_views import CaseIn, Forgot, Trained
from glyphh_server.ops.bots.goes import Goes
from glyphh_server.ops.bots.training import kept, outcome_of, precedent_id, shown

D = BotDecision


def case_of(bot: Any, body: CaseIn) -> Any:
    if body.case is not None:
        return body.case
    if body.item is None:
        raise Invalid("Give the item (its fields) or the case itself.", reason="item")
    return fill(bot.spec["gates"][body.gate].get("case") or {}, {"item": body.item})


def _row(bot: Any, body: CaseIn, case: Any, made: str) -> dict[str, Any]:
    shown_fields = readable.fields(body.item if body.item is not None else case)
    named = readable.label(body.label or None, shown_fields)
    return {
        "org_id": bot.org_id, "bot_id": bot.id, "gate": body.gate, "key": made or uuid.uuid4().hex, "kind": "case",
        "label": named, "fields": shown_fields, "case": case, "outcome": body.outcome, "who": "you", "recorded": True,
        "confirmed": True, "precedent": made, "body": readable.body(named, shown_fields, body.gate, body.outcome),
    }  # fmt: skip


async def add(svc: Goes, who: Principal, slug: str, body: CaseIn) -> Trained:
    """A labelled case of the gate's, kept as a precedent and listed with its decisions (kind case, by you)."""
    bot = await mend._idle(svc, who, slug)
    outcome_of(bot, body.gate, body.outcome)
    case = case_of(bot, body)

    def act(runner: Runner) -> tuple[str, int]:
        model = runner.bot.gate_model(body.gate)
        made = precedent_id(runner.ada.model(model).record(case, body.outcome))
        return made, held(runner.ada, model)

    made, precedents = (await svc.go(bot, act)).answer
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        new_id = (await conn.execute(insert(D).values(**_row(bot, body, case, made)).returning(D.id))).scalar_one()
    return await shown(svc, who, bot, [new_id], f"Added a {body.outcome} case to gate {body.gate}", precedents)


async def forget(svc: Goes, who: Principal, slug: str, gate: str, precedent: str) -> Forgot:
    """The precedent forgotten by the gate's model; a decision it was is no longer a precedent, and a case added by
    hand is gone."""
    bot = await mend._idle(svc, who, slug)
    if gate not in decisions.outcomes(bot):
        raise Invalid(f"{slug} has no gate {gate}.", reason="gate")
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        was = (await decisions.by_precedent(conn, bot, [precedent])).get(precedent)

    def act(runner: Runner) -> int:
        runner.ada.model(runner.bot.gate_model(gate)).forget(precedent)
        if was is not None and (own := kept(runner, was)) is not None:
            runner.store.mark(own, recorded=0)
        return held(runner.ada, runner.bot.gate_model(gate))

    precedents = (await svc.go(bot, act)).answer
    if was is not None:
        async with svc.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            gone = update(D).where(D.id == was.id).values(recorded=False, precedent="", confirmed=False)
            await conn.execute(delete(D).where(D.id == was.id) if was.kind == "case" else gone)
    return Forgot(gate=gate, id=precedent, precedents=int(precedents))
