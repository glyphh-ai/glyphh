"""The template library (docs/specs/templates.md) as Claude and the plugin use it: Agentic memory installed from the
connector, its tools on that person's connector alone, a glyphh grown and read back by them, the hooks' context, and
the template removed with its models."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.process import Worker
from tests.ada.mcp import data, refused, rpc, signed_in, text, tool
from tests.db.helpers import member, person

MINE = {"glyphh_remember", "glyphh_recall", "glyphh_personality", "glyphh_instructions", "glyphh_forget"}
API = "http://api.test"


async def listed(ada: httpx.AsyncClient, auth: dict[str, str]) -> set[str]:
    return {t["name"] for t in (await rpc(ada, auth, "tools/list"))["result"]["tools"]}


async def test_agentic_memory_grows_a_glyphh_and_reads_it_back(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    assert not MINE & await listed(ada, auth)
    shown = await tool(ada, auth, "templates")
    assert text(shown).startswith("agentic-memory: Agentic memory (Memory, version 1). Your glyphh")
    assert data(await tool(ada, auth, "templates", q="nothing like it"))["templates"] == []
    one = await tool(ada, auth, "template", slug="agentic-memory")
    assert "- glyphh_recall: " in text(one) and data(one)["installed"] is False
    made = await tool(ada, auth, "template_install", slug="agentic-memory")
    assert text(made).startswith("Installed Agentic memory: your connector now has glyphh_remember, ")
    assert data(made)["models"][0]["model"] == f"me-{who.user_id.hex[:12]}-agentic-memory-memory"
    assert await listed(ada, auth) >= MINE
    said = (await rpc(ada, auth, "server/discover"))["result"]["instructions"]
    assert said.endswith("When something is wrong or no longer true, glyphh_forget it.")
    kept = await tool(ada, auth, "glyphh_remember", kind="instructions", text="Reply in one sentence", when="replying")
    assert text(kept).startswith("Kept in your glyphh (instructions ")
    await tool(ada, auth, "glyphh_remember", kind="instructions", text="Check the live site before designing")
    await tool(ada, auth, "glyphh_remember", kind="personality", text="Dry humour, no fluff")
    await tool(ada, auth, "glyphh_remember", kind="memory", text="Chris builds Ada at Glyphh", when="work")
    again = data(await tool(ada, auth, "glyphh_remember", kind="instructions", text="reply in  ONE sentence"))
    assert again["id"] == data(kept)["id"] and again["holds"] == 2  # the same text again replaces it
    found = data(await tool(ada, auth, "glyphh_recall", about="should my reply have a table", top=2))["found"]
    assert found[0]["text"] == "reply in  ONE sentence" and found[0]["kind"] == "instructions"
    only = await tool(ada, auth, "glyphh_recall", about="what does Chris do at work", kind="memory")
    assert text(only).startswith("- Chris builds Ada at Glyphh (memory ")
    none = await tool(ada, auth, "glyphh_recall", about="zebra", kind="personality")
    assert text(none) == "Nothing in your glyphh bears on that yet."
    rules = data(await tool(ada, auth, "glyphh_instructions"))["found"]
    assert [r["text"] for r in rules] == ["reply in  ONE sentence", "Check the live site before designing"]
    applies = data(await tool(ada, auth, "glyphh_instructions", about="designing the home page"))["found"]
    assert applies[0]["text"] == "Check the live site before designing"
    assert text(await tool(ada, auth, "glyphh_personality")).startswith("- Dry humour, no fluff (personality ")
    gone = await tool(ada, auth, "glyphh_forget", kind="instructions", id=rules[1]["id"])
    assert text(gone) == f"Forgot instructions {rules[1]['id']}." and data(gone)["forgotten"] is True
    assert len(data(await tool(ada, auth, "glyphh_instructions"))["found"]) == 1


async def test_the_hooks_context_and_the_rest_api(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    who = await person(engine, "Team")
    nothing = await ada.post(f"{API}/v1/me/glyphh/context", json={}, headers=who.headers)
    assert nothing.status_code == 200 and nothing.json() == {"context": ""}
    library = await ada.get(f"{API}/v1/templates", params={"q": "memory"}, headers=who.headers)
    assert [t["slug"] for t in library.json()["templates"]] == ["agentic-memory"]
    made = await ada.post(f"{API}/v1/templates/agentic-memory/install", headers=who.headers)
    assert made.status_code == 200 and made.json()["installed_version"] == 1
    again = await ada.post(f"{API}/v1/templates/agentic-memory/install", headers=who.headers)
    assert again.status_code == 200  # its models are there already: kept as they are
    got = await ada.get(f"{API}/v1/templates/agentic-memory", headers=who.headers)
    assert got.json()["installed"] is True
    empty = await ada.post(f"{API}/v1/me/glyphh/context", json={}, headers=who.headers)
    assert empty.json() == {"context": ""}
    auth = await signed_in(engine, who)
    await tool(ada, auth, "glyphh_remember", kind="personality", text="Be blunt")
    await tool(ada, auth, "glyphh_remember", kind="memory", text="Ships the plugin on Mondays", when="release plugin")
    start = (await ada.post(f"{API}/v1/me/glyphh/context", json={}, headers=who.headers)).json()["context"]
    assert start.startswith("From your glyphh") and "Its personality:\n- Be blunt (personality " in start
    asked = {"prompt": "when do we release the plugin"}
    now = (await ada.post(f"{API}/v1/me/glyphh/context", json=asked, headers=who.headers)).json()["context"]
    assert "What it knows about you:\n- Ships the plugin on Mondays" in now and "Be blunt" not in now
    removed = await ada.delete(f"{API}/v1/templates/agentic-memory/install", headers=who.headers)
    assert removed.status_code == 200 and removed.json()["installed"] is False
    twice = await ada.delete(f"{API}/v1/templates/agentic-memory/install", headers=who.headers)
    assert twice.status_code == 404
    missing = await ada.get(f"{API}/v1/templates/no-such", headers=who.headers)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "E_NOT_FOUND"
    unknown = await ada.post(f"{API}/v1/templates/no-such/install", headers=who.headers)
    assert unknown.status_code == 404


async def test_a_glyphh_is_its_persons_alone(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    alice = await person(engine, "Team")
    bob = await member(engine, alice.org_id)
    mine, theirs = await signed_in(engine, alice), await signed_in(engine, bob)
    model = data(await tool(ada, mine, "template_install", slug="agentic-memory"))["models"][0]["model"]
    assert not MINE & await listed(ada, theirs)  # the tools are on Alice's connector, not her org's
    called = await rpc(ada, theirs, "tools/call", name="glyphh_recall", arguments={"about": "anything"})
    assert called["error"]["message"] == "There is no tool 'glyphh_recall'."
    assert model in text(await tool(ada, mine, "ada_models"))
    assert model not in text(await tool(ada, theirs, "ada_models"))
    hidden = await refused(ada, theirs, "ada_facts", name=model, data={"m": {"s": {"cue": "x"}}})
    assert hidden["code"] == "E_NOT_FOUND"
    wrong = await refused(ada, mine, "glyphh_remember", kind="secrets", text="x")
    assert wrong["code"] == "E_INVALID" and wrong["kinds"] == ["memory", "instructions", "personality"]
    unconfirmed = await refused(ada, mine, "template_remove", slug="agentic-memory", confirm="yes")
    assert unconfirmed["code"] == "E_CONFLICT"
    removed = await tool(ada, mine, "template_remove", slug="agentic-memory", confirm="agentic-memory")
    assert text(removed) == "Removed Agentic memory and deleted its models with everything in them."
    assert not MINE & await listed(ada, mine)
