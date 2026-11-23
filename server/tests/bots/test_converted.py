"""Bots that exist become agents (docs/specs/bot-agent-loop.md, 9): a bot installed from each template Glyphh
shipped gets that template's plugin, standing task and examples, its decisions and everything the person chose
kept; a bot the person wrote gets a note that says its loop in order; a run that waited is failed, saying why; every
org gets its orchestrator; and running the conversion again changes nothing."""

import hashlib
import uuid
from typing import Any

import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Bot, BotPlugin, BotRun, Project
from glyphh_server.ops.bots import converted, packages
from glyphh_server.ops.bots.agent.tools import named
from tests.bots.conftest import INBOX, Served, made_bot, ran, run_of
from tests.bots.market import any_component, bot_of
from tests.bots.old import SLUGS, a_run, convert, looped, plugins, row, template
from tests.db.helpers import Person

NONE: dict[str, int] = {"orchestrators": 0, "bots": 0}
ONE: dict[str, int] = {"orchestrators": 0, "bots": 1}
WORTH: dict[str, Any] = INBOX["gates"]["worth"]
READY: dict[str, Any] = {**WORTH, "case": {"m": {"s": {"subject": "$draft.title", "id": "$draft.id"}}}}
BOTH: dict[str, Any] = {**WORTH, "case": {"m": {"s": {"subject": "$mail.count of $input", "id": "$item.id"}}}}
OWN: dict[str, Any] = {
    "takes": "what to look for",
    "try": "is:unread",
    "extra": "a key no bot has",
    "touches": "sends",
    "seed": {"personality": ["Short and kind."]},
    "limits": {"seconds": 120, "agent_turns": 3, "max_items": 10},
    "gates": {"worth": WORTH, "ready": READY, "both": BOTH},
    "loop": [
        {"id": "mail", "run": "gmail-find-email", "input": {"q": "$input"}},
        {"id": "worth", "gate": "worth", "each": "$mail.ret", "label": "subject", "key": "id"},
        {"id": "draft", "agent": "  Write a reply to each of $worth.answer.  ", "approval": "draft the replies"},
        {"id": "ready", "gate": "ready"},
        {"id": "send", "run": "gmail-send-email", "approval": "send the reply", "input": {"to": ["$input"]}},
        {"id": "again", "run": "gmail-find-email"},
        {"id": "climb", "ladder": ["a", "b"]},
        "junk",
        {"id": "ghost", "gate": "gone"},
        {"id": "sum", "agent": "Say what you did."},
    ],
}
NOTE: str = (
    "---\nname: how-it-works\ndescription: The job this bot does, step by step, as it was set up. Read it before "
    "doing the job.\n---\n\nDo the job in this order. Use the tool each step names (its key, with - as _), and "
    "decide only with the decide tool.\n\n"
    '1. Use gmail-find-email with {"q": "$input"}.\n'
    "2. Decide `worth` for each item of $mail.ret (the decide tool), and go on with what it answers. Each item "
    "needs its id, subject.\n"
    "3. Write a reply to each of $worth.answer. Ask the person first.\n"
    "4. Decide `ready` for one item, what the steps before found (the decide tool), and go on with what it "
    "answers. Each item needs its id, title.\n"
    '5. Use gmail-send-email with {"to": ["$input"]}. Ask the person first.\n'
    "6. Use gmail-find-email.\n"
    "7. Do the step climb.\n"
    "8. Decide `gone` for one item, what the steps before found (the decide tool), and go on with what it answers.\n"
    "9. Say what you did.\n\n"
    "`$input` is what the person said; `$name` is what that step found.\n"
)
TOOLS: list[dict[str, Any]] = [
    {"name": "triage", "description": "Triage the inbox", "op": "run", "verdicts": "worth", "wait": 5},
    {"name": "drafted", "description": "What it drafted", "op": "runs", "verdicts": "draft"},
    {"name": "fix", "description": "Correct a call", "op": "wrong", "gate": "worth"},
]


@pytest.fixture(autouse=True)
async def settled(engine: AsyncEngine) -> None:
    """Nothing another test left is waiting to be converted: each test counts only its own."""
    await convert(engine)


def test_the_templates_as_they_were_are_known_by_their_steps_and_their_words() -> None:
    known = {slug: (shape, then) for shape, (slug, then) in converted.WERE.items()}
    assert sorted(known) == SLUGS == sorted(packages.library())
    for slug in SLUGS:
        was = template(slug)
        steps = tuple(f"{s['id']}={s['run']}" if "run" in s else s["id"] for s in was["spec"]["loop"])
        assert known[slug] == (steps, hashlib.sha256(was["instructions"].encode()).hexdigest()[:16])
        notes = {hashlib.sha256(said.encode()).hexdigest()[:16] for said in was["skills"].values()}
        assert notes <= converted.THEIR_NOTES


@pytest.mark.parametrize("slug", SLUGS)
async def test_a_bot_from_each_old_template_becomes_an_agent_with_its_plugin(
    served: Served, ana: Person, engine: AsyncEngine, slug: str
) -> None:
    was, side = template(slug), packages.library()[slug].sidecar
    await looped(served, engine, ana, was, permission_mode="auto", effort="high")
    before = await bot_of(served, ana, slug)
    assert (
        before["spec"] == was["spec"]
        and before["skills"] == was["skills"]
        and before["plugins"]
        == ([{"name": "notes", "version": "1.0.0", "latest": "1.0.0", "source": "personal"}] if was["skills"] else [])
    )
    assert await convert(engine) == ONE
    bot = await bot_of(served, ana, slug)
    spec, old = bot["spec"], was["spec"]
    assert not {"loop", "takes", "try", "touches"} & set(spec) and (await row(engine, bot["id"])).old_spec == old
    assert sorted(spec["gates"]) == sorted(old["gates"]) == sorted(side.decisions)
    for name, gate in old["gates"].items():  # each decision as it was, its case read from the item it is handed
        assert spec["gates"][name] == gate | {"case": side.decisions[name]["case"]}
        assert slug == "weekly-report" or spec["gates"][name] == gate
    assert spec.get("hosts", []) == side.hosts and spec.get("builtins", []) == side.builtins
    assert spec.get("seed") == old.get("seed")
    kept = {k: v for k, v in old.get("limits", {}).items() if k in ("seconds", "runs_per_day")}
    assert spec.get("limits", {}) == kept
    assert bot["task"] == side.task and bot["examples"] == side.examples
    assert bot["instructions"] == side.bot.instructions != was["instructions"]
    assert bot["skills"] == {}  # the notes the template gave it are its plugin's skills now
    assert bot["plugins"] == [{"name": slug, "version": "1.0.0", "latest": "1.0.0", "source": f"template:{slug}"}]
    assert (await plugins(engine, bot["id"]))[0].files == packages.library()[slug].files
    assert [t["name"] for t in bot["connector_tools"]] == [t["name"] for t in side.connector_tools]
    assert all(t["verdicts"] is None or t["verdicts"] in spec["gates"] for t in bot["connector_tools"])
    same = ("id", "slug", "name", "summary", "look", "model", "connections", "schedule", "next_run_at", "runs_on")
    same += ("folders", "role", "permission_mode", "effort", "gate_models", "voice", "mascot", "created_at")
    assert {k: bot[k] for k in same} == {k: before[k] for k in same}
    assert (bot["permission_mode"], bot["effort"], bot["model"]) == ("auto", "high", was["model"])
    assert bot["schedule"]["every"] == was.get("schedule", {}).get("every", "off") and bot["look"] == was["look"]
    assert sorted(bot["gate_models"][: len(old["gates"])]) == sorted(f"bot-{slug}-gate-{g}" for g in old["gates"])
    res = await served.http.patch(f"/v1/bots/{slug}", json={"summary": "Still mine to change"}, headers=ana.headers)
    assert res.status_code == 200, res.text  # converted, it is a bot the check holds
    any_component(served)
    run = await ran(served, ana, slug, "Hi there")
    turn = served.agent.turns[-1]
    assert run["status"] == "done" and turn.message == "Hi there"
    assert turn.skills == [f"{slug}:{s}" for s in packages.library()[slug].skills]
    wanted = (
        {named(k) for k in was["tools"]}
        | {"decide", "ask_person", *side.builtins}
        | ({"fetch"} if side.hosts else set())
    )
    assert {t.name for t in turn.tools} == wanted
    assert await convert(engine) == NONE


async def test_the_persons_own_words_notes_and_tools_are_kept(served: Served, ana: Person, engine: AsyncEngine) -> None:
    was = template("inbox-triage")
    was["instructions"] = "You are my mail cat. My own words."
    edited = was["skills"]["digest"].replace("Most urgent first.", "Newest first.")
    was["skills"] = {"digest": edited, "house": "---\nname: house\ndescription: House rules\n---\n\nNo shouting.\n"}
    was["spec"]["hosts"] = ["hn.algolia.com"]
    was["schedule"] = {"every": "day", "at": "07:30", "input": "  me@navy.test "}
    was["connector_tools"] = [TOOLS[0], {**TOOLS[1], "verdicts": "digest"}]
    await looped(served, engine, ana, was)
    assert await convert(engine) == ONE
    bot = await bot_of(served, ana, "inbox-triage")
    assert bot["instructions"] == "You are my mail cat. My own words." and bot["task"] == "me@navy.test"
    assert bot["skills"] == was["skills"]  # a note the person wrote, and the template's one they changed
    assert [p["name"] for p in bot["plugins"]] == ["inbox-triage", "notes"]
    assert bot["spec"]["hosts"] == ["hn.algolia.com"] and bot["schedule"]["input"] == "  me@navy.test "
    assert [(t["name"], t["verdicts"]) for t in bot["connector_tools"]] == [("triage", "worth"), ("drafted", None)]
    assert bot["examples"] == packages.library()["inbox-triage"].sidecar.examples
    await ran(served, ana, "inbox-triage")
    turn = served.agent.turns[-1]
    assert turn.skills == ["inbox-triage:digest", "notes:digest", "notes:house"] and turn.message == "me@navy.test"


async def test_a_bot_the_person_wrote_gets_a_note_of_its_loop_in_order(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    mine = {"name": "Reply Cat", "instructions": "You are Reply Cat.", "model": "claude-sonnet-5-5", "spec": OWN}
    mine |= {"apps": ["gmail"], "tools": ["gmail-find-email", "gmail-send-email"], "connector_tools": TOOLS}
    mine["skills"] = {"replies": "---\nname: replies\ndescription: How\n---\n\nOne paragraph.\n"}
    before = await looped(served, engine, ana, mine)
    assert await convert(engine) == ONE
    bot = await bot_of(served, ana, "reply-cat")
    assert bot["skills"] == mine["skills"] | {"how-it-works": NOTE}
    assert bot["task"] == "Do your job now." and bot["examples"] == [] and bot["instructions"] == "You are Reply Cat."
    assert bot["plugins"] == [{"name": "notes", "version": "1.0.0", "latest": "1.0.0", "source": "personal"}]
    spec = bot["spec"]
    assert sorted(spec) == ["gates", "limits", "seed"] and spec["limits"] == {"seconds": 120}
    assert spec["gates"]["worth"] == WORTH  # one that read its item is as it was
    assert spec["gates"]["ready"] == WORTH | {"case": {"m": {"s": {"subject": "$item.title", "id": "$item.id"}}}}
    assert spec["gates"]["both"]["case"] == {
        "m": {"s": {"subject": "$item.mail.count of $item.input", "id": "$item.id"}}
    }
    assert [(t["name"], t["verdicts"], t["gate"]) for t in bot["connector_tools"]] == [
        ("triage", "worth", None),
        ("drafted", None, None),  # the step it named made no decision
        ("fix", None, "worth"),
    ]
    assert (await row(engine, bot["id"])).old_spec == OWN and bot["connections"] == before["connections"]
    res = await served.http.patch("/v1/bots/reply-cat", json={"summary": "Mine"}, headers=ana.headers)
    assert res.status_code == 200, res.text
    await ran(served, ana, "reply-cat")
    turn = served.agent.turns[-1]
    assert turn.skills == ["notes:how-it-works", "notes:replies"] and turn.message == "Do your job now."
    assert await convert(engine) == NONE


async def test_a_loop_like_a_templates_but_with_other_tools_is_the_persons_own(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    was = template("news-brief")
    was["spec"]["loop"][0]["run"] = "gmail-find-email"  # the same step ids, another tool: not Glyphh's News Brief
    was["schedule"] = {"every": "day", "input": "the front page"}
    await looped(served, engine, ana, was)
    odd = {"name": "Odd Cat", "instructions": "You are Odd Cat.", "model": "claude-haiku-5-5"}
    odd_cat = await looped(served, engine, ana, odd | {"spec": {"loop": "nope", "gates": [], "limits": 5}})
    assert await convert(engine) == {"orchestrators": 0, "bots": 2}
    bot = await bot_of(served, ana, "news-brief")
    assert bot["plugins"] == [{"name": "notes", "version": "1.0.0", "latest": "1.0.0", "source": "personal"}]
    assert sorted(bot["skills"]) == ["brief", "how-it-works"] and bot["task"] == "the front page"
    assert (
        bot["instructions"] == was["instructions"] and "1. Use gmail-find-email with" in bot["skills"]["how-it-works"]
    )
    assert await plugins(engine, bot["id"]) == []
    kept = await row(engine, odd_cat["id"])  # a spec too odd to read is still left without its loop
    assert kept.spec == {"gates": [], "limits": 5} and kept.task == "Do your job now."
    assert kept.skills["how-it-works"].endswith("decide tool.\n\n\n\n`$input` is what the person said; "
                                                "`$name` is what that step found.\n")  # fmt: skip


async def test_a_run_that_waited_is_failed_saying_the_bot_was_updated(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    bot = await looped(served, engine, ana, template("inbox-triage"))
    sent = await looped(served, engine, ana, template("news-brief"))
    other = await made_bot(served, ana, connections=[])  # an agent already: its runs are not the conversion's
    asked = {"question": "Worth your time?", "options": ["read", "skip"]}
    waiting = await a_run(engine, ana, bot["id"], "needs_input", question=asked)
    out = await a_run(engine, ana, sent["id"], "dispatched")  # it was out on a rrotor, walking the loop there
    done = await a_run(engine, ana, bot["id"], "done", output="Sent.")
    theirs = await a_run(engine, ana, other["id"], "needs_input", question=asked)
    queue = (await served.http.get("/v1/bot-approvals", headers=ana.headers)).json()["runs"]
    assert {r["id"] for r in queue} == {str(waiting), str(theirs)}
    assert await convert(engine) == {"orchestrators": 0, "bots": 2}
    for run_id in (waiting, out):
        run = await run_of(served, ana, str(run_id))
        assert run["status"] == "failed" and run["question"] is None and run["finished_at"] is not None
        assert run["error"] == "The bot was updated while this run waited: run it again."
    kept = await run_of(served, ana, str(done))
    assert (kept["status"], kept["output"], kept["error"]) == ("done", "Sent.", "")
    assert (await run_of(served, ana, str(theirs)))["status"] == "needs_input"
    queue = (await served.http.get("/v1/bot-approvals", headers=ana.headers)).json()["runs"]
    assert [r["id"] for r in queue] == [str(theirs)]
    res = await served.http.post(f"/v1/bot-runs/{waiting}/answer", json={"answer": "read"}, headers=ana.headers)
    assert res.status_code == 409  # it no longer waits
    assert (await ran(served, ana, "inbox-triage"))["status"] == "done"  # and the bot runs again


async def test_an_org_with_no_orchestrator_gets_one_and_its_projects_are_pointed_at_it(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    async with engine.begin() as conn:  # an org from before every org had one
        await conn.execute(delete(Bot).where(Bot.org_id == ana.org_id, Bot.role == "orchestrator"))
    taken = await made_bot(served, ana, name="Orchestrator", connections=[])  # a bot of theirs has the slug
    async with engine.begin() as conn:
        values = {"org_id": ana.org_id, "name": "Site", "repo_url": "https://github.com/acme/site"}
        await conn.execute(insert(Project).values(**values, slug="site", orchestrator=uuid.UUID(taken["id"])))
        await conn.execute(insert(Project).values(**values, slug="docs"))
    assert await convert(engine) == {"orchestrators": 1, "bots": 0}
    listed = (await served.http.get("/v1/bots", headers=ana.headers)).json()["bots"]
    assert [(b["slug"], b["role"]) for b in listed] == [("the-orchestrator", "orchestrator"), ("orchestrator", "bot")]
    lead = listed[0]
    assert lead["name"] == "Orchestrator" and lead["task"] and lead["examples"] and lead["plugins"] == []
    async with engine.connect() as conn:
        led = (await conn.execute(select(Project.orchestrator).where(Project.org_id == ana.org_id))).scalars().all()
    assert led == [uuid.UUID(lead["id"])] * 2
    assert await convert(engine) == NONE


async def test_converting_again_changes_nothing(served: Served, ana: Person, engine: AsyncEngine) -> None:
    bot = await looped(served, engine, ana, template("resume-screener"))
    await a_run(engine, ana, bot["id"], "needs_input", question={"question": "?", "options": ["yes", "no"]})
    assert await convert(engine) == ONE

    async def snapshot() -> list[Any]:
        async with engine.connect() as conn:
            found = []
            for table in (Bot, BotPlugin, BotRun, Project):
                rows = await conn.execute(select(table).where(table.org_id == ana.org_id).order_by(table.id))
                found += [tuple(r) for r in rows]
        return found

    first = await snapshot()
    assert await convert(engine) == NONE and await convert(engine) == NONE
    assert await snapshot() == first and len(first) == 4  # the bot, the org's orchestrator, the plugin, the run
