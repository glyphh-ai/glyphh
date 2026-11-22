"""A bot's folders and effort (docs/specs/bots.md, 13): the folders of its rrotor's machine it may use, their shape
checked here and nothing more, sent with each call of its run there; the effort Claude works at, on each request of
an agent step in the cloud and in the rrotor's call; both through the routes, a template's copy and the connector's
tools. And the ticket a person's browser reads the machine itself with."""

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import anthropic
import pytest
from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Invalid
from glyphh_server.models import Rrotor
from glyphh_server.ops.bots import access, goes
from glyphh_server.ops.bots.access import Folder, WithEffort
from glyphh_server.ops.link.protocol import Call
from tests.bots.conftest import Served, connected, made_bot
from tests.bots.fakes import FakeAnthropic
from tests.bots.remote import OnRrotor, online, result, rrotor_fixture  # noqa: F401 (the fixture)
from tests.connector import granted, rpc, tool
from tests.db.helpers import Person, person
from tests.link import local_runtime, self_runtime

DOCS: dict[str, str] = {"path": "/Users/ana/Documents", "access": "read"}
OUT: dict[str, str] = {"path": "/Users/ana/Documents/out", "access": "write"}
POET: dict[str, Any] = {"name": "Poet", "instructions": "Write.", "spec": {"loop": [{"id": "poem", "agent": "A poem"}]}}


async def _version(engine: AsyncEngine, rrotor_id: uuid.UUID, version: str | None) -> None:
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == rrotor_id).values(image_version=version))


# Their shape


async def test_a_bot_has_no_folders_and_medium_effort_until_its_owner_chooses(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    bot = (await served.http.post("/v1/bots", json=POET, headers=ada.headers)).json()
    assert (bot["folders"], bot["effort"]) == ([], "medium")
    chosen = {"folders": [DOCS, {**OUT, "path": OUT["path"] + "/"}], "effort": "high"}
    res = await served.http.patch("/v1/bots/poet", json=chosen, headers=ada.headers)
    assert res.status_code == 200 and (res.json()["folders"], res.json()["effort"]) == ([DOCS, OUT], "high")
    # kept on Glyphh cloud too (ignored there), and left as they are by a change that names neither
    res = await served.http.patch("/v1/bots/poet", json={"summary": "Poems"}, headers=ada.headers)
    assert (res.json()["folders"], res.json()["effort"], res.json()["runs_on"]) == ([DOCS, OUT], "high", None)
    assert (await served.http.get("/v1/bots/poet", headers=ada.headers)).json()["folders"] == [DOCS, OUT]
    listed = (await served.http.get("/v1/bots", headers=ada.headers)).json()["bots"][0]
    assert (listed["folders"], listed["effort"]) == ([DOCS, OUT], "high")
    # the whole list is replaced; [] clears it
    res = await served.http.patch("/v1/bots/poet", json={"folders": []}, headers=ada.headers)
    assert (res.json()["folders"], res.json()["effort"]) == ([], "high")
    made = await served.http.post(
        "/v1/bots", json={**POET, "name": "Scribe", "folders": [OUT], "effort": "max"}, headers=ada.headers
    )
    assert made.status_code == 201 and (made.json()["folders"], made.json()["effort"]) == ([OUT], "max")


@pytest.mark.parametrize(
    ("folders", "said"),
    [
        ([{"path": "Documents", "access": "read"}], "'Documents' is not an absolute path: a folder is named from /."),
        ([{"path": "~/Documents", "access": "read"}], "is not an absolute path"),
        (
            [{"path": "/Users/ana/../bob", "access": "read"}],
            "/Users/ana/../bob has '..' in it: name the folder itself.",
        ),
        ([DOCS, {**DOCS, "path": DOCS["path"] + "/", "access": "write"}], "is listed twice: give each folder once."),
        ([{"path": f"/srv/{n}", "access": "read"} for n in range(21)], "at most 20 folders: this is 21."),
    ],
)
async def test_folders_of_a_bad_shape_are_refused_in_a_plain_sentence(
    served: Served, engine: AsyncEngine, folders: list[dict[str, str]], said: str
) -> None:
    ada = await person(engine)
    res = await served.http.post("/v1/bots", json={**POET, "folders": folders}, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "folders", res.text
    assert said in res.json()["error"]["message"]
    await served.http.post("/v1/bots", json=POET, headers=ada.headers)
    res = await served.http.patch("/v1/bots/poet", json={"folders": folders}, headers=ada.headers)
    assert res.status_code == 422 and said in res.json()["error"]["message"]
    assert (await served.http.get("/v1/bots/poet", headers=ada.headers)).json()["folders"] == []


async def test_a_folder_or_an_effort_that_is_not_one_is_refused(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    for bad in (
        {"folders": [{"path": "/srv", "access": "own"}]},
        {"folders": [{"path": "/srv"}]},
        {"folders": [{"path": "", "access": "read"}]},
        {"folders": [{"path": "/srv", "access": "read", "recursive": True}]},
        {"folders": ["/srv"]},
        {"folders": [{"path": "/" + "a" * 1024, "access": "read"}]},
        {"effort": "extreme"},
        {"effort": None},
    ):
        res = await served.http.post("/v1/bots", json={**POET, **bad}, headers=ada.headers)
        assert res.status_code == 422, bad
    assert access.folders([Folder(path="/", access="read")]) == [{"path": "/", "access": "read"}]
    with pytest.raises(Invalid):
        access.folders([Folder(path="/srv/\x00", access="read")])
    with pytest.raises(ValidationError):
        Folder(path="/srv", access="execute")  # type: ignore[arg-type]


async def test_the_models_listing_says_the_efforts(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    said = (await served.http.get("/v1/bots/models", headers=ada.headers)).json()
    assert (said["efforts"], said["default_effort"]) == (["low", "medium", "high", "xhigh", "max"], "medium")


# Effort, on the Claude call


async def test_a_bots_effort_goes_with_each_claude_request_of_its_agent_steps(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    await served.http.post("/v1/bots", json={**POET, "effort": "high"}, headers=ada.headers)
    run = await served.http.post("/v1/bots/poet/runs", json={"input": "the sea"}, headers=ada.headers)
    await served.settled()
    assert (await served.http.get(f"/v1/bot-runs/{run.json()['id']}", headers=ada.headers)).json()["status"] == "done"
    sent = served.claude.requests[-1]
    assert sent["model"] == "claude-opus-5-5" and sent["output_config"] == {"effort": "high"}
    # medium, the default, is said too: a model's own default is not always medium
    await served.http.patch("/v1/bots/poet", json={"effort": "medium"}, headers=ada.headers)
    await served.http.post("/v1/bots/poet/runs", json={"input": "the sea"}, headers=ada.headers)
    await served.settled()
    assert served.claude.requests[-1]["output_config"] == {"effort": "medium"}


def test_effort_is_left_out_where_the_model_takes_none_and_never_fails_a_request() -> None:
    assert access.effort_for("claude-opus-5-5", "xhigh") == "xhigh"
    assert access.effort_for("claude-haiku-5-5", "low") == "low"
    for model, effort in (("claude-haiku-4-5", "high"), ("gpt-9", "high"), ("claude-opus-5-5", None)):
        assert access.effort_for(model, effort) is None
    assert access.effort_for("claude-opus-5-5", "extreme") is None
    fake = FakeAnthropic("ok")
    WithEffort(fake, "max").messages.stream(model="claude-sonnet-5-5", max_tokens=5)
    WithEffort(fake, "max").messages.stream(model="claude-haiku-4-5", max_tokens=5)
    WithEffort(fake, None).messages.stream(model="claude-sonnet-5-5", max_tokens=5)
    WithEffort(fake, "max").messages.stream(model="claude-sonnet-5-5", max_tokens=5, output_config={"format": "x"})
    assert [r.get("output_config") for r in fake.requests] == [{"effort": "max"}, None, None, {"format": "x"}]


def test_the_real_claude_carries_the_bots_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    made: list[dict[str, Any]] = []
    fake = FakeAnthropic("A poem.")

    def client(**kw: Any) -> FakeAnthropic:
        made.append(kw)
        return fake

    monkeypatch.setattr(anthropic, "Anthropic", client)
    claude = goes._claude("sk-ant-own-key-0123456789", "claude-haiku-5-5", "low")
    assert claude.answer("poet", {"prompt": "You write."}, "A poem").text == "A poem."
    assert made == [{"api_key": "sk-ant-own-key-0123456789", "max_retries": 3}]
    assert fake.requests[0]["model"] == "claude-haiku-5-5" and fake.requests[0]["output_config"] == {"effort": "low"}


# On its rrotor


async def _on(r: OnRrotor, engine: AsyncEngine, version: str | None = "0.6.0", **over: Any) -> tuple[Person, Any, Any]:
    ada = await person(engine)
    rt = await online(engine, ada)
    await _version(engine, rt.id, version)
    await made_bot(r.s, ada, runs_on=str(rt.id), **over)
    run = await r.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "lunch"}, headers=ada.headers)
    assert run.status_code == 202, run.text
    return ada, rt, run.json()


async def test_a_run_on_a_rrotor_carries_the_bots_folders_and_effort(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, run = await _on(on_rrotor, engine, folders=[DOCS, OUT], effort="xhigh")
    to, sent = on_rrotor.hub.sent[-1]
    assert to == rt.id and isinstance(sent, Call) and run["status"] == "dispatched"
    assert sent.folders == [DOCS, OUT] and sent.inputs["effort"] == "xhigh"
    assert json.loads(sent.model_dump_json())["folders"] == [DOCS, OUT]  # as the link carries it
    # a folder the machine's owner does not offer: the rrotor's plain sentence is the run's error
    why = "/Users/ana/Documents is not in a folder this rrotor's owner shares with bots: it shares /srv/shared."
    refused = {"status": "failed", "step": "call", "prompt": None, "data": {"code": "E_FOLDER_REFUSED", "reason": why}}
    await on_rrotor.landed(rt, ada, sent.run_id, refused)
    ended = (await on_rrotor.s.http.get(f"/v1/bot-runs/{run['id']}", headers=ada.headers)).json()
    assert ended["status"] == "failed" and why in ended["error"]
    # a fresh call for an answer carries them again
    await on_rrotor.s.http.patch("/v1/bots/inbox-cat", json={"folders": [OUT]}, headers=ada.headers)
    run = (await on_rrotor.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)).json()
    assert on_rrotor.hub.last().folders == [OUT] and run["status"] == "dispatched"


async def test_a_bot_with_no_folders_sends_none(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    _, _, run = await _on(on_rrotor, engine)
    sent = on_rrotor.hub.last()
    assert run["status"] == "dispatched" and sent.folders is None and sent.inputs["effort"] == "medium"


@pytest.mark.parametrize("version", ["0.5.0", None, "dev"])
async def test_a_rrotor_before_folders_is_sent_no_effort_and_a_bot_with_folders_fails_saying_to_update(
    on_rrotor: OnRrotor, engine: AsyncEngine, version: str | None
) -> None:
    ada, rt, run = await _on(on_rrotor, engine, version, effort="high")
    assert run["status"] == "dispatched" and "effort" not in on_rrotor.hub.last().inputs  # never fails over effort
    await on_rrotor.landed(rt, ada, uuid.UUID(run["id"]), result())
    await on_rrotor.s.http.patch("/v1/bots/inbox-cat", json={"folders": [DOCS]}, headers=ada.headers)
    sent = len(on_rrotor.hub.sent)
    run = (await on_rrotor.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)).json()
    assert run["status"] == "failed" and len(on_rrotor.hub.sent) == sent
    assert run["error"] == (
        f"Acme runs rrotor {version or 'an earlier version'}, which cannot give a bot folders: update it to "
        "rrotor 0.6.0 or later, or take the folders off the bot."
    )


def test_which_rrotors_take_folders() -> None:
    assert [access.takes(v) for v in ("0.6.0", "0.6.1-rc1", "0.10.2", "1.0.0")] == [True] * 4
    assert [access.takes(v) for v in ("0.5.0", "0.5.9", "", None, "latest")] == [False] * 5


# A template's copy, and the connector's tools


async def test_a_templates_copy_has_its_effort_and_no_folders(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await connected(served, ada)
    one = (await served.http.get("/v1/bot-templates/inbox-triage", headers=ada.headers)).json()
    assert one["effort"] == "medium" and "folders" not in one  # a template knows no machine
    res = await served.http.post("/v1/bot-templates/inbox-triage/install", json={"name": "Mail"}, headers=ada.headers)
    assert res.status_code == 201 and (res.json()["folders"], res.json()["effort"]) == ([], "medium")
    # the copy is the org's: its owner chooses after
    res = await served.http.patch("/v1/bots/mail", json={"folders": [DOCS], "effort": "low"}, headers=ada.headers)
    assert (res.json()["folders"], res.json()["effort"]) == ([DOCS], "low")


async def test_folders_and_effort_through_the_connector(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    given = {**POET, "folders": [DOCS, OUT], "effort": "low"}
    made = (await rpc(served.http, auth, "tools/call", name="bot_create", arguments=given))["result"]
    assert not made.get("isError"), made
    assert (made["structuredContent"]["folders"], made["structuredContent"]["effort"]) == ([DOCS, OUT], "low")
    said = made["content"][0]["text"]
    assert "claude-opus-5-5 at low effort" in said
    assert "folders: /Users/ana/Documents (read only); /Users/ana/Documents/out (read and change)" in said
    got = await tool(served.http, auth, "bot", slug="poet")
    assert (got["structuredContent"]["folders"], got["structuredContent"]["effort"]) == ([DOCS, OUT], "low")
    changed = await tool(served.http, auth, "bot_update", slug="poet", folders=[], effort="max")
    assert (changed["structuredContent"]["folders"], changed["structuredContent"]["effort"]) == ([], "max")
    assert "folders:" not in changed["content"][0]["text"] and "at max effort" in changed["content"][0]["text"]
    bad = await tool(served.http, auth, "bot_update", slug="poet", folders=[{"path": "docs", "access": "read"}])
    assert bad["isError"] and "is not an absolute path" in bad["content"][0]["text"]
    listed = await tool(served.http, auth, "bot_models")
    assert listed["structuredContent"]["efforts"] == ["low", "medium", "high", "xhigh", "max"]
    assert "effort" in (await tool(served.http, auth, "bot_guide"))["content"][0]["text"]


# Where the browser reads the machine itself


def _payload(token: str) -> dict[str, Any]:
    raw = token.split(".")[0]
    return dict(json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))))


async def test_a_place_says_where_the_browser_reads_the_machine_and_a_ticket_lets_the_person_in(
    served: Served, engine: AsyncEngine
) -> None:
    ada, other = await person(engine), await person(engine)
    acme, mine = await self_runtime(engine, ada), await local_runtime(engine, ada)
    theirs = await self_runtime(engine, other, "https://rrotor.other.test")
    await _version(engine, acme.id, "0.6.0")
    shown = {p["name"]: p for p in (await served.http.get("/v1/bots/places", headers=ada.headers)).json()["places"]}
    assert (shown["Glyphh cloud"]["url"], shown["Glyphh cloud"]["version"]) == (None, None)
    assert (shown["Acme"]["url"], shown["Acme"]["version"]) == ("https://rrotor.acme.test", "0.6.0")
    assert (shown["Mac"]["url"], shown["Mac"]["version"]) == ("http://127.0.0.1:7777", None)

    before = datetime.now(UTC).replace(microsecond=0)
    res = await served.http.post(f"/v1/bots/places/{acme.id}/ticket", headers=ada.headers)
    assert res.status_code == 200, res.text
    ticket = res.json()
    assert (ticket["url"], ticket["expires_in"]) == ("https://rrotor.acme.test", 600)
    said = _payload(ticket["token"])
    assert (said["kind"], said["runtime_id"], said["sub"]) == ("work", str(acme.id), str(ada.user_id))
    until = datetime.fromisoformat(said["expires_at"].replace("Z", "+00:00"))
    assert said["expires_at"].endswith("Z") and timedelta(0) <= until - before - timedelta(seconds=600) <= timedelta(5)
    # signed as a licence key is: the rrotor checks it with the public key it carries
    raw, signature = (base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)) for p in ticket["token"].split("."))
    served.app.state.signing_key.public_key().verify(signature, raw)
    local = (await served.http.post(f"/v1/bots/places/{mine.id}/ticket", headers=ada.headers)).json()
    assert local["url"] == "http://127.0.0.1:7777" and _payload(local["token"])["runtime_id"] == str(mine.id)
    # only for a rrotor of the person's own org
    for stranger in (theirs.id, uuid.uuid4()):
        res = await served.http.post(f"/v1/bots/places/{stranger}/ticket", headers=ada.headers)
        assert res.status_code == 422 and res.json()["error"]["reason"] == "runs_on"
    assert (await served.http.post(f"/v1/bots/places/{acme.id}/ticket")).status_code == 401
