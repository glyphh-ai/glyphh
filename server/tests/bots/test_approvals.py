"""The approvals a bot's runs wait on (docs/specs/bot-agent-loop.md, 5): the org's queue of runs waiting on the person,
oldest first, each with what it asks; and the person's yes, kept on the run as the yes to that very call (its tool
and a digest of its input, who said it and when) until the resumed agent makes that call, which takes it once. A no
keeps nothing, and a yes to one tool is not a yes to another."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import BotRun
from glyphh_server.ops.bots.agent import permit
from tests.bots.agents import play
from tests.bots.conftest import FIND, SEND, Served, answered, asks, connected, made_bot, ran, run_of
from tests.bots.fakes import MAIL
from tests.db.helpers import Person

REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}
TOOLS: list[str] = ["gmail-find-email", "gmail-send-email"]


async def kept(engine: AsyncEngine, run_id: str) -> dict[str, Any]:
    """The yeses the run holds now."""
    async with engine.begin() as conn:
        found = await conn.execute(select(BotRun.approvals).where(BotRun.id == uuid.UUID(run_id)))
        return dict(found.scalar_one())


async def queue(s: Served, who: Person) -> list[dict[str, Any]]:
    res = await s.http.get("/v1/bot-approvals", headers=who.headers)
    assert res.status_code == 200, res.text
    return list(res.json()["runs"])


async def test_the_queue_is_the_runs_waiting_on_the_person_oldest_first(served: Served, ana: Person) -> None:
    gmail = await connected(served, ana, allow=False)
    scopes = [{"connection_id": gmail["id"], "tools": TOOLS}]
    sender = await made_bot(served, ana, name="Sender", connections=scopes)
    sorter = await made_bot(served, ana, name="Sorter", connections=[])
    assert await queue(served, ana) == []
    served.agent.script = [play((SEND, REPLY))]
    first = await ran(served, ana, sender["slug"], "Reply to Grace")
    served.agent.script = [play(asks(MAIL))]
    second = await ran(served, ana, sorter["slug"], "What is worth answering?")
    waiting = await queue(served, ana)
    assert [(w["id"], w["bot_slug"], w["status"]) for w in waiting] == [
        (first["id"], "sender", "needs_input"), (second["id"], "sorter", "needs_input"),
    ]  # fmt: skip
    asked = waiting[0]["question"]
    assert (asked["question"], asked["approval"], asked["tool"]) == ("Send Email in Gmail?", True, "gmail-send-email")
    assert asked["detail"].splitlines()[0] == "to: grace@navy.test" and asked["options"] == ["yes", "no"]
    assert waiting[1]["question"]["approval"] is False and len(waiting[1]["question"]["batch"]) == 2
    served.agent.script = [play(text="Not sent.")]
    await answered(served, ana, first["id"], "no")
    assert [w["id"] for w in await queue(served, ana)] == [second["id"]]
    assert (await served.http.post(f"/v1/bot-runs/{second['id']}/cancel", headers=ana.headers)).status_code == 200
    assert await queue(served, ana) == []


async def test_a_yes_is_kept_as_the_yes_to_that_call_until_the_agent_makes_it(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    gmail = await connected(served, ana, allow=False)
    bot = await made_bot(served, ana, connections=[{"connection_id": gmail["id"], "tools": TOOLS}])
    await served.http.put(
        f"/v1/connections/{gmail['id']}/permissions",
        json={"permissions": {"gmail-find-email": "ask"}},
        headers=ana.headers,
    )
    other = {**REPLY, "to": ["everyone@navy.test"]}
    # asked about the send; then, the yes in hand, the agent tries another tool, another input, and at last the call
    goes = [play((SEND, REPLY)), play((FIND, REPLY)), play((SEND, other)), play((SEND, REPLY))]
    served.agent.script = [*goes, play((SEND, REPLY), text="Sent.")]
    run = await ran(served, ana, bot["slug"], "Reply to Grace")
    assert await kept(engine, run["id"]) == {}
    again = await answered(served, ana, run["id"], "yes")
    assert again["question"]["question"] == "Find Email in Gmail?"  # a yes to one tool is not a yes to another
    held = await kept(engine, run["id"])
    assert list(held) == ["gmail-send-email"] and held["gmail-send-email"]["digest"] == permit.digest(REPLY)
    assert held["gmail-send-email"]["by"] == str(ana.user_id) and held["gmail-send-email"]["at"]
    third = await answered(served, ana, run["id"], "no")
    assert "everyone@navy.test" in third["question"]["detail"] and served.pd.runs == []  # nor to another input
    assert await kept(engine, run["id"]) == {}  # each answer says what the run holds: the no holds nothing
    fourth = await answered(served, ana, run["id"], "no")
    assert fourth["status"] == "needs_input" and fourth["question"]["detail"] == permit.detail(REPLY)
    assert served.pd.runs == []  # the first yes went with the answers since: the very call asks again
    done = await answered(served, ana, run["id"], "yes")
    assert (done["status"], done["output"]) == ("done", "Sent.") and len(served.pd.runs) == 1
    assert await kept(engine, run["id"]) == {} and (await run_of(served, ana, run["id"]))["question"] is None
