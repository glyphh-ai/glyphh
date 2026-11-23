"""A waiting run carried on (docs/specs/bot-agent-loop.md, 2.1, 4, 5): what the person answered is taken where it
belongs before the agent's session resumes, and the agent is told in a sentence. A yes to an approval is kept on the
run as the yes to that very call; answers about items are learned by the decision's Ada model and kept as the run's
decisions; an answer to a bot the orchestrator asked goes to that bot's run."""

import uuid
from typing import Any

from sqlalchemy import select

from glyphh_server.db import tenancy
from glyphh_server.models import BotRun
from glyphh_server.ops.bots import orchestrator, runs
from glyphh_server.ops.bots.agent import permit, prompt
from glyphh_server.ops.bots.agent.desk import PENDING, Desk, answered


async def on(svc: Any, bot: Any, run_id: uuid.UUID, question: dict[str, Any], answer: Any, by: Any) -> str:
    """The words the session resumes with, the answer taken."""
    if question.get("child_run"):
        return await orchestrator.carried(svc, bot, run_id, question, answer, by)
    if question.get("approval"):
        yes = permit.granted(question, answer, by, runs.now().isoformat())
        await runs.put(svc.engine, bot.org_id, run_id, approvals=yes)
        return prompt.approved(question, str(answer))
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, bot.org_id)
        run = (await conn.execute(select(BotRun).where(BotRun.id == run_id))).one()
    pending = run.data.get(PENDING)
    if not question.get("batch") or not pending:  # the agent's own question
        return prompt.heard(answer)
    entries = await answered(Desk(svc, bot, run_id, run.loop_run, {}), pending, answer)
    return prompt.decided(pending["decision"], entries)
