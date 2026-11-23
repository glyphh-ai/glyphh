"""Where every tool call of a bot's agent lands (ops/bots/agent/desk.py; docs/specs/bot-agent-loop.md, 3 and 5): a
tool its connection denies is refused and the agent goes on, a tool that fails tells the agent why, an action's result
is kept for its link cards, and a yes is to one call once. Ada's tools are test_agent_desk_ada.py's."""

import asyncio
from typing import Any

from glyphh_server.errors import Invalid
from glyphh_server.ops.bots.agent import desk, permit
from glyphh_server.ops.bots.agent.tools import Tool
from glyphh_server.ops.bots.agent.turn import ASKED, ERROR, RESULT, Ended, Outcome, Turn
from tests.bots.agents import Go, play
from tests.bots.conftest import FIND, SEND, Served, answered, connected, inbox, made_bot, ran
from tests.db.helpers import Person

REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}
PR: str = "https://github.com/acme/app/pull/7"
NOTHING: dict[str, Any] = {"type": "object", "properties": {}}


def tool(name: str, call: Any, read_only: bool = False, seconds: float = 120.0) -> Tool:
    """A tool allowed to run, whose own call is `call`."""
    title = name.replace("_", " ").title()
    return Tool(name, name.replace("_", "-"), title, "", NOTHING, read_only, "", "allow", call, seconds)


def given(*more: Tool, then: Go) -> Go:
    """`then`, with `more` put among the run's tools at its desk first: tools whose own call does as a test says."""

    async def go(turn: Turn) -> Ended:
        turn.call.__self__.tools.update({t.name: t for t in more})  # type: ignore[attr-defined]
        return await then(turn)

    return go


async def scoped(s: Served, who: Person, *tools: str, allow: bool = False, **over: Any) -> dict[str, Any]:
    """The inbox bot with these Gmail tools, none of them set on its connection (unless allowed)."""
    gmail = await connected(s, who, allow=allow)
    scopes = [{"connection_id": gmail["id"], "tools": list(tools)}]
    return {**await made_bot(s, who, connections=scopes, **over), "gmail": gmail["id"]}


async def permitted(s: Served, who: Person, gmail: str, **modes: str) -> None:
    said = {"permissions": {k.replace("_", "-"): v for k, v in modes.items()}}
    res = await s.http.put(f"/v1/connections/{gmail}/permissions", json=said, headers=who.headers)
    assert res.status_code == 200, res.text


async def test_a_tool_its_connection_denies_is_refused_in_every_mode_and_the_agent_goes_on(
    served: Served, ana: Person
) -> None:
    bot = await scoped(served, ana, "gmail-send-email", "gmail-find-email", permission_mode="auto")
    await permitted(served, ana, bot["gmail"], gmail_send_email="deny")
    go = play((SEND, REPLY), (FIND, {"q": "x"}), ("rm_rf", {"path": "/"}), text="I could not send it.")
    served.agent.script = [go]
    run = await ran(served, ana, bot["slug"], "Reply to Grace")
    said = "Send Email is blocked on the Gmail connection. Tell the person; they can allow it on that connection."
    assert go.heard[0] == Outcome(ERROR, said) and go.heard[1].kind == RESULT  # type: ignore[attr-defined]
    assert go.heard[2] == Outcome(ERROR, "There is no tool rm_rf: use only the tools you were given.")  # type: ignore[attr-defined]
    assert (run["status"], run["output"]) == ("done", "I could not send it.")
    assert [(x["title"], x["app"], x["ok"]) for x in run["steps"]] == [
        ("Send Email", "Gmail", False), ("Find Email", "Gmail", True),
    ]  # fmt: skip
    assert run["log"] == ["Send Email (failed)", "Find Email"] and [p["id"] for p in served.pd.runs] == [
        "gmail-find-email"
    ]


async def test_a_read_asks_only_when_its_connection_says_so_and_never_when_the_bot_acts_on_its_own(
    served: Served, ana: Person
) -> None:
    bot = await scoped(served, ana, "gmail-find-email", "gmail-send-email")
    await permitted(served, ana, bot["gmail"], gmail_find_email="ask")
    served.agent.script = [play((FIND, {"q": "is:unread"})), play((FIND, {"q": "is:unread"}), text="Two letters.")]
    run = await ran(served, ana, bot["slug"], "Anything new?")
    assert run["status"] == "needs_input" and run["question"]["question"] == "Find Email in Gmail?"
    assert run["question"]["detail"] == "q: is:unread" and run["question"]["tool"] == "gmail-find-email"
    assert (await answered(served, ana, run["id"], "yes"))["output"] == "Two letters."
    patched = await served.http.patch(f"/v1/bots/{bot['slug']}", json={"permission_mode": "auto"}, headers=ana.headers)
    assert patched.json()["permission_mode"] == "auto"
    served.agent.script = [play((FIND, {"q": "x"}), (SEND, REPLY), text="Sent.")]
    done = await ran(served, ana, bot["slug"], "Reply to Grace")
    assert done["status"] == "done" and [p["id"] for p in served.pd.runs][1:] == [
        "gmail-find-email",
        "gmail-send-email",
    ]


async def test_a_yes_is_used_once_and_the_same_call_again_asks_again(served: Served, ana: Person) -> None:
    bot = await scoped(served, ana, "gmail-send-email")
    served.agent.script = [play((SEND, REPLY)), play((SEND, REPLY), (SEND, REPLY)), play(text="Sent once.")]
    run = await ran(served, ana, bot["slug"], "Reply to Grace")
    again = await answered(served, ana, run["id"], "yes")
    assert again["status"] == "needs_input" and len(served.pd.runs) == 1  # sent once; the second send waits
    assert again["question"]["detail"] == permit.detail(REPLY) and [x["ok"] for x in again["steps"]] == [True]
    assert "digest" not in again["question"]  # the yes names the call by it; it is not the person's to read
    done = await answered(served, ana, run["id"], "no")
    assert done["status"] == "done" and len(served.pd.runs) == 1 and "said no" in served.agent.turns[2].message


async def test_a_tool_that_fails_tells_the_agent_why_and_the_run_goes_on(served: Served, ana: Person) -> None:
    bot = await scoped(served, ana, "gmail-find-email", spec=inbox(hosts=["api.example.com"]))
    served.pd.fail_run = True

    async def refused(_: dict[str, Any]) -> Any:
        raise Invalid("That folder is not one of the bot's.", reason="folders")

    async def outside(_: dict[str, Any]) -> Any:
        raise PermissionError("the bot may not read /etc")

    async def broken(_: dict[str, Any]) -> Any:
        raise RuntimeError("socket closed")

    async def slow(_: dict[str, Any]) -> Any:
        await asyncio.sleep(30)

    more = (tool("refused", refused), tool("outside", outside), tool("broken", broken), tool("slow", slow, True, 0.01))
    calls = [(FIND, {"q": "x"}), ("fetch", {"url": "https://evil.example.org/x"}), ("fetch", {"url": 7})]
    go = play(*calls, *((t.name, {}) for t in more), text="Nothing worked.")
    served.agent.script = [given(*more, then=go)]
    run = await ran(served, ana, bot["slug"], "Try everything")
    assert [(o.kind, o.value) for o in go.heard] == [  # type: ignore[attr-defined]
        (ERROR, 'Pipedream refused: {"error":"the account\'s token was revoked"}'),
        (ERROR, "https://evil.example.org/x is not https on one of the bot's hosts (api.example.com)"),
        (ERROR, 'fetch takes a URL, or {"url": ..., "headers": {...}}'),
        (ERROR, "That folder is not one of the bot's."),
        (ERROR, "the bot may not read /etc"),
        (ERROR, "Broken failed: socket closed"),
        (ERROR, "Slow took longer than 0.01 seconds"),
    ]
    assert (run["status"], run["output"]) == ("done", "Nothing worked.")
    assert [x["ok"] for x in run["steps"]] == [False] * 7 and run["log"][0] == "Find Email (failed)"
    assert [x["title"] for x in run["steps"]][1:4] == ["Read a page", "Read a page", "Refused"]


async def test_what_an_action_made_is_kept_for_its_link_cards_and_what_a_tool_read_is_not(
    served: Served, ana: Person
) -> None:
    bot = await made_bot(served, ana, spec={}, connections=[])

    def answering(value: Any) -> Any:
        async def call(_: dict[str, Any]) -> Any:
            return value

        return call

    opened = {"ret": {"html_url": PR, "title": "Fix the login"}}
    hits = {"ret": {"html_url": "https://github.com/acme/app/pull/1", "title": "What it read"}}
    big = {"ret": {"html_url": "https://github.com/acme/app/pull/2", "body": "x" * desk.MADE_MAX}}
    more = (tool("open_pr", answering(opened)), tool("search", answering(hits), True), tool("dump", answering(big)))
    go = play(("search", {}), ("open_pr", {}), ("dump", {}), text="Opened it.")
    served.agent.script = [given(*more, then=go)]
    run = await ran(served, ana, bot["slug"], "Open the pull request")
    assert go.heard[1] == Outcome(RESULT, opened) and go.heard[2].value == big  # type: ignore[attr-defined]
    assert run["data"] == {"open-pr-2": opened}  # by its tool and where it came in the run
    assert [(k["kind"], k["title"], k["url"]) for k in run["links"]] == [("Pull request", "Fix the login", PR)]
    assert [x["title"] for x in run["steps"]] == ["Search", "Open Pr", "Dump"] and all(x["ok"] for x in run["steps"])


async def test_a_tools_own_call_may_stop_the_run_to_ask_the_person(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana, spec={}, connections=[])

    async def asks(_: dict[str, Any]) -> Any:
        raise desk.Ask({"question": "Scout asks: send the digest?", "options": ["yes", "no"], "approval": True})

    go = play(("ask_scout", {}), ("never", {}))
    served.agent.script = [given(tool("ask_scout", asks), then=go)]
    run = await ran(served, ana, bot["slug"], "Have Scout send the digest")
    assert [o.kind for o in go.heard] == [ASKED] and str(desk.Ask({})) == ""  # type: ignore[attr-defined]
    assert run["status"] == "needs_input" and run["question"]["question"] == "Scout asks: send the digest?"
    assert run["steps"] == [] and run["summary"] == "It is waiting on your answer."
