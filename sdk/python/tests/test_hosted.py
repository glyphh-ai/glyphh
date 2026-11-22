"""The org's hosted bots (glyphh.hosted) over the Glyphh API: every request as the server's /v1 bots routes take it,
on the same API key Ada takes, every answer read right, a run waited for until it ends or asks, and `glyphh bots`
printing the API's own answers."""

from __future__ import annotations

import json
from typing import Any, List

import pytest

import glyphh.client
from glyphh import DEFAULT_API_URL, Ada, AdaTimeoutError, BotRun, ConflictError, HostedBots, InvalidError, cli

URL = "https://api.test"
BOT = {"id": "b1", "slug": "inbox-cat", "name": "Inbox Cat", "summary": "Answers the mail", "spec": {}, "last_run": None}
ASKS = {
    "question": "send: send the reply. Yes?",
    "options": ["yes", "no"],
    "batch": None,
    "answer_with": None,
    "step": "send",
    "approval": True,
}


def run(status: str = "queued", **over: Any) -> dict:
    return {"id": "r1", "bot_slug": "inbox-cat", "status": status, "input": "x", "output": "", "error": "",
            "log": [], "data": {}, "question": None, **over}


class Api:
    """The Glyphh API, answering from a script of (status, body)."""

    def __init__(self, *answers: Any) -> None:
        self.answers, self.calls = list(answers), []

    def __call__(self, method, url, headers, raw):
        self.calls.append((method, url, dict(headers), None if raw is None else json.loads(raw)))
        status, body = self.answers.pop(0)
        return status, json.dumps(body).encode()


@pytest.fixture(autouse=True)
def no_waits(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(glyphh.client, "_sleep", lambda s: clock.__setitem__(0, clock[0] + s))
    monkeypatch.setattr(glyphh.client, "_now", lambda: clock[0])
    for name in ("GLYPHH_API_URL", "GLYPHH_API_KEY", "GLYPHH_RUNTIME_KEY"):
        monkeypatch.delenv(name, raising=False)


def bots(*answers: Any) -> tuple:
    api = Api(*answers)
    return HostedBots(URL, "glyphh_ak_test", transport=api, retry_deadline=0), api


def test_bots_are_listed_searched_and_read_on_the_ada_key() -> None:
    b, api = bots((200, {"bots": [BOT]}), (200, {"bots": []}), (200, BOT), (200, {"gates": {"worth": {"precedents": 3}}}))
    found = b.list()
    assert [x.slug for x in found] == ["inbox-cat"] and found[0].name == "Inbox Cat"
    assert found[0].summary == "Answers the mail"
    assert b.search("mail cat") == []
    assert b.bot("inbox-cat").info().slug == "inbox-cat"
    assert b.bot("inbox-cat").gates() == {"worth": {"precedents": 3}}
    method, url, headers, _ = api.calls[0]
    assert (method, url) == ("GET", f"{URL}/v1/bots") and headers["authorization"] == "Bearer glyphh_ak_test"
    assert api.calls[1][1] == f"{URL}/v1/bots?q=mail%20cat"
    assert api.calls[2][1] == f"{URL}/v1/bots/inbox-cat" and api.calls[3][1] == f"{URL}/v1/bots/inbox-cat/gates"


def test_a_run_is_started_waited_for_and_answered() -> None:
    b, api = bots(
        (202, run()),
        (200, run("running")),
        (200, run("dispatched")),
        (200, run("needs_input", question=ASKS)),
        (202, run("queued")),
        (200, run("done", output="Sent.")),
    )
    seen: List[str] = []
    started = b.bot("inbox-cat").run("lunch?")
    assert started.going and not started.waiting and api.calls[0][3] == {"input": "lunch?"}
    asked = b.wait(started, on_progress=lambda r: seen.append(r.status))
    assert seen == ["queued", "running", "dispatched", "needs_input"]
    assert asked.waiting and asked.approval and asked.question["step"] == "send" and not asked.ended
    done = b.answer(asked, "yes", wait=True)
    assert done.ended and done.output == "Sent." and done.error == "" and done.bot == "inbox-cat"
    assert api.calls[4][:2] == ("POST", f"{URL}/v1/bot-runs/r1/answer") and api.calls[4][3] == {"answer": "yes"}
    assert "idempotency-key" not in api.calls[0][2]  # a run is sent once, never again


def test_runs_listed_one_read_and_the_approvals_queue() -> None:
    b, api = bots(
        (202, run("done")),
        (200, {"runs": [run("done")]}),
        (200, run("needs_input", question={"question": "Worth answering?", "options": ["answer", "skip"]})),
        (200, {"runs": [run("needs_input", question=ASKS)]}),
    )
    assert b.run("inbox-cat", wait=True).status == "done"  # already ended: not looked at again
    assert [r.id for r in b.bot("inbox-cat").runs()] == ["r1"]
    one = b.get_run("r1")
    assert one.waiting and not one.approval  # a gate's question, not an approval
    assert [r.approval for r in b.approvals()] == [True]
    assert [c[1] for c in api.calls[1:]] == [
        f"{URL}/v1/bots/inbox-cat/runs", f"{URL}/v1/bot-runs/r1", f"{URL}/v1/bot-approvals"
    ]


def test_cancel_wrong_and_a_batch_answer() -> None:
    b, api = bots(
        (202, run("queued")),
        (200, run("failed", error="cancelled")),
        (200, {"gate": "worth", "said": "skip", "now": "answer"}),
        (200, {"gate": "worth", "said": "skip", "now": "answer"}),
    )
    b.answer("r1", {"1": "answer", "rest": "skip"})
    assert api.calls[0][3] == {"answer": {"1": "answer", "rest": "skip"}}
    assert b.cancel("r1").error == "cancelled" and api.calls[1][:2] == ("POST", f"{URL}/v1/bot-runs/r1/cancel")
    assert b.wrong("r1", "answer")["now"] == "answer" and api.calls[2][3] == {"outcome": "answer"}
    b.wrong("r1", "answer", gate="worth", item="m7")
    assert api.calls[3][3] == {"outcome": "answer", "gate": "worth", "item": "m7"}


def test_templates_are_listed_read_and_installed() -> None:
    template = {"slug": "news-brief", "name": "News brief", "apps": ["slack"], "tools": [], "gates": []}
    b, api = bots(
        (200, {"templates": [template]}),
        (200, {"templates": []}),
        (200, template),
        (201, BOT),
        (201, BOT),
    )
    assert [t.slug for t in b.templates()] == ["news-brief"] and b.templates("news") == []
    assert b.template("news-brief").apps == ["slack"]
    assert b.install("news-brief").slug == "inbox-cat" and api.calls[3][3] == {}
    b.install("news-brief", name="Morning news")
    assert api.calls[4][:2] == ("POST", f"{URL}/v1/bot-templates/news-brief/install")
    assert api.calls[4][3] == {"name": "Morning news"} and api.calls[1][1] == f"{URL}/v1/bot-templates?q=news"


def test_refusals_are_typed_and_a_long_run_times_out() -> None:
    conflict = {"error": {"code": "E_CONFLICT", "message": "The bot has a run going.", "slug": "inbox-cat"}}
    misfit = {"error": {"code": "E_INVALID", "message": "Answer with one of yes, no.", "options": ["yes", "no"]}}
    b, _ = bots((409, conflict), (422, misfit), *[(200, run("running"))] * 40)
    with pytest.raises(ConflictError):
        b.run("inbox-cat")
    with pytest.raises(InvalidError) as said:
        b.answer("r1", "maybe")
    assert said.value.detail["options"] == ["yes", "no"]
    with pytest.raises(AdaTimeoutError) as late:
        b.wait("r1", timeout=10, poll=2)
    assert late.value.detail == {"run_id": "r1"}


def test_the_address_and_the_key_come_as_adas_do(monkeypatch) -> None:
    monkeypatch.setenv("GLYPHH_API_KEY", "glyphh_ak_env")
    assert HostedBots().url == DEFAULT_API_URL == "https://api.glyphh.ai"
    monkeypatch.setenv("GLYPHH_API_URL", "http://localhost:8000/")
    assert HostedBots().url == "http://localhost:8000"
    api = Api((200, {"bots": []}))
    ada = Ada("https://ada.test", "glyphh_ak_mine", transport=api)
    assert ada.bots.list() == [] and api.calls[0][1] == "http://localhost:8000/v1/bots"
    assert api.calls[0][2]["authorization"] == "Bearer glyphh_ak_mine"
    assert isinstance(BotRun(run()), dict)


def test_the_bots_command_prints_the_apis_answers(monkeypatch, capsys) -> None:
    api = Api(
        (200, {"bots": [BOT]}),
        (202, run()),
        (200, run("failed", error="boom")),
        (202, run("done")),
        (200, {"runs": []}),
        (200, run("done")),
        (200, {"templates": []}),
    )
    monkeypatch.setenv("GLYPHH_API_KEY", "glyphh_ak_cli")
    monkeypatch.setenv("GLYPHH_API_URL", URL)
    real = glyphh.client.Ada.__init__
    monkeypatch.setattr(glyphh.client.Ada, "__init__", lambda self, url=None, key=None, **kw: real(
        self, url, key, **{**kw, "transport": api}))
    assert cli.main(["bots", "list", "--q", "mail"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["slug"] == "inbox-cat"
    assert cli.main(["bots", "run", "inbox-cat", "--input", "lunch?", "--wait"]) == 1  # it failed
    assert json.loads(capsys.readouterr().out)["error"] == "boom"
    assert cli.main(["bots", "answer", "r1", '{"1": "answer"}']) == 0
    assert api.calls[3][3] == {"answer": {"1": "answer"}}
    capsys.readouterr()
    assert cli.main(["bots", "approvals"]) == 0 and json.loads(capsys.readouterr().out) == []
    assert cli.main(["bots", "status", "r1", "--wait"]) == 0
    assert cli.main(["bots", "templates"]) == 0
    assert [c[1] for c in api.calls] == [
        f"{URL}/v1/bots?q=mail", f"{URL}/v1/bots/inbox-cat/runs", f"{URL}/v1/bot-runs/r1",
        f"{URL}/v1/bot-runs/r1/answer", f"{URL}/v1/bot-approvals", f"{URL}/v1/bot-runs/r1", f"{URL}/v1/bot-templates",
    ]
