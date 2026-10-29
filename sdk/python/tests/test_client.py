"""The client against the contract's fixtures (contract/fixtures.json, as a real Ada Cloud answered them): every
request as Ada expects it, every answer read right, every refusal its typed AdaError; jobs waited for with their
progress; what may be sent again, sent again, and nothing else."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import validate

import glyphh
import glyphh.client
from glyphh import (
    DEFAULT_URL,
    Ada,
    AdaError,
    AdaTimeoutError,
    AuthError,
    BusyError,
    Decision,
    FewRolesError,
    HeadLostError,
    Job,
    JobFailedError,
    LimitError,
    ModelMissingError,
    NoHeadError,
    NotCommittedError,
    RateError,
    ReadOnlyError,
    Result,
    RunLostError,
    SpecError,
    SpecReadingError,
    UnavailableError,
    Usage,
)

ROOT = Path(__file__).parents[3]
CONTRACT = json.loads((ROOT / "contract" / "contract.json").read_text())
FIXTURES = json.loads((ROOT / "contract" / "fixtures.json").read_text())
URL = "https://ada.test"


class Fake:
    """Ada, answering from a script of (status, body) or (status, body, headers); an exception is raised. A body
    that is bytes is sent as it is."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, method, url, headers, body):
        sent = body
        if body:
            try:
                sent = json.loads(body)
            except ValueError:
                sent = body
        self.calls.append((method, url, dict(headers), sent))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, content, *got = answer
        return (status, content if isinstance(content, bytes) else json.dumps(content).encode(), *got)


def case(name):
    return next(c for c in FIXTURES["cases"] if c["name"] == name)


def answered(name):
    c = case(name)
    return (c["response"]["status"], c["response"]["body"], c["response"].get("headers", {}))


def ada(*answers, **options):
    fake = Fake(*answers)
    return Ada(URL + "/", "glyphh_ak_test", transport=fake, **options), fake


def paths(fake):
    return [(c[0], c[1].removeprefix(URL)) for c in fake.calls]


@pytest.fixture
def clock(monkeypatch):
    """No real waiting: the client's sleeps recorded, its clock moved by them."""
    slept, now = [], [0.0]

    def sleep(seconds):
        slept.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(glyphh.client, "_sleep", sleep)
    monkeypatch.setattr(glyphh.client, "_now", lambda: now[0])
    return slept


def job(state, kind="learn", percent=None, **more):
    body = {
        "id": "j1",
        "model": "tickets",
        "kind": kind,
        "state": state,
        "percent": percent if percent is not None else (100.0 if state == "done" else 0.0),
        "args": {},
        "result": None,
        "error": None,
        "created_at": "2026-10-22 04:18:43+00:00",
        "started_at": None,
        "finished_at": None,
        "made_by": "u1",
    }
    body.update(more)
    validate(body, CONTRACT["job"])
    return body


# the contract


def test_the_contract_is_5_the_sdks_and_every_fixture_is_its_schemas():
    assert CONTRACT["contract"] == FIXTURES["contract"] == glyphh.SUPPORTED_CONTRACT == 5
    assert {"decision", "usage", "job", "answer", "result", "error", "ada_versions", "model", "models", "versions", "upgrade", "backtest"} <= set(CONTRACT)
    assert {"Glyphh-Contract", "Glyphh-Ada", "Glyphh-Ada-Notice"} == set(CONTRACT["headers"])
    for c in FIXTURES["cases"]:
        if c["schema"]:
            validate(c["response"]["body"], CONTRACT[c["schema"]])
        if c.get("data_schema"):
            validate(c["response"]["body"]["data"], CONTRACT[c["data_schema"]])
        if c.get("result_schema"):
            validate(c["response"]["body"]["result"], CONTRACT[c["result_schema"]])
        if c["response"]["status"] >= 400:
            assert c["schema"] == "error" and c["response"]["body"]["error"]["code"] in CONTRACT["codes"]
        for header in c["response"].get("headers", {}):
            assert header == header.lower(), (c["name"], header)
    # every Ada refusal is typed, and names the latest stable as its fix
    for code in ("E_ADA_UNKNOWN", "E_ADA_RETIRED", "E_ADA_DEPRECATED", "E_ADA_BETA", "E_ADA_UNAVAILABLE"):
        assert code in CONTRACT["codes"] and issubclass(glyphh.errors.TYPED[code], glyphh.AdaVersionError)
    current = next(c for c in FIXTURES["cases"] if c["name"] == "the Ada versions")["response"]["body"]
    assert set(glyphh.SUPPORTED_ADA) == {v["name"] for v in current["versions"]} and current["latest_stable"] == "ada-1-0"


# models


def test_a_model_is_made_from_its_spec_and_written_once():
    c = case("a model made from its spec")
    client, fake = ada(answered(c["name"]))
    name = c["request"]["body"]["name"]
    m = client.create_model(name, c["request"]["body"]["spec"])
    assert m.name == name and m.created == c["response"]["body"] and m.created["version"] == 1
    method, url, headers, body = fake.calls[0]
    assert (method, url, body) == ("POST", f"{URL}/v1/models", c["request"]["body"])
    assert headers["authorization"] == "Bearer glyphh_ak_test" and len(headers["idempotency-key"]) == 32
    client, fake = ada((200, {"models": [{"name": "tickets"}]}), (200, {"name": "tickets", "deleted": True}), (200, {"version": 1, "spec": {"a": 1}}))
    assert client.models() == [{"name": "tickets"}]
    assert client.model("tickets").delete()["deleted"]
    assert client.model("tickets").spec() == {"a": 1}
    assert paths(fake) == [("GET", "/v1/models"), ("DELETE", "/v1/models/tickets?confirm=tickets"), ("GET", "/v1/models/tickets")]


# deciding


def test_a_decision_from_v1_decide_reads_as_3_0s_result_too():
    c = case("a decision")
    client, fake = ada(answered(c["name"]))
    sent = c["request"]["body"]
    d = client.decide("tickets", sent["data"], include=["facts"], clearance=0.5)
    assert isinstance(d, Decision) and fake.calls[0][3] == sent and fake.calls[0][1] == f"{URL}/v1/decide"
    body = c["response"]["body"]
    assert (d.outcome, d.probabilities, d.ask, d.model, d.version, d.ada) == (body["outcome"], body["probabilities"], False, "tickets", body["version"], "ada-1-0")
    assert d.receipts == body["receipts"] and d.facts == body["facts"] and d.outputs is None
    assert d.done and d.status == "done" and not d.waiting and d.data == body and not d.limit_exceeded


def test_a_decision_that_asks_and_one_of_several_outputs():
    asks, several = case("a decision that asks a person"), case("a decision of several outputs")
    client, fake = ada(answered(asks["name"]), answered(several["name"]))
    d = client.model("tickets").decide(asks["request"]["body"]["data"])
    assert d.ask and d.outcome == asks["response"]["body"]["outcome"]
    both = client.decide("routing", several["request"]["body"]["data"], outputs=["team", "urgent"])
    assert set(both.outputs) == {"team", "urgent"} and both.outputs["team"].outcome == "billing"
    assert both.outputs["team"].model == "routing" and not both.ask and both.outcome is None
    assert both.ada == both.outputs["team"].ada == "ada-1-0"
    assert fake.calls[1][3] == several["request"]["body"]


def test_typed_outputs_read_in_their_own_terms():
    body = {
        "model": "tickets",
        "version": 2,
        "ada": "ada-1-2-beta",
        "outputs": {
            "urgent": {"outcome": "true", "probabilities": {"true": 0.9, "false": 0.1}, "ask": False, "p": 0.9},
            "refund": {"outcome": "45", "probabilities": {"45": 1.0}, "ask": False, "value": 41.5, "applies": True},
            "severity": {"outcome": None, "probabilities": {}, "ask": False, "applies": False},
            "tags": {"outcome": ["web", "gold"], "probabilities": {"web": 0.9, "gold": 0.8}, "ask": False},
        },
    }
    d = Decision.of(body).outputs
    assert d["urgent"].p == 0.9 and d["refund"].value == 41.5 and d["refund"].applies
    assert d["severity"].applies is False and d["severity"].outcome is None
    assert d["tags"].outcome == ["web", "gold"] and d["tags"].p is None and d["tags"].applies is None


# jobs


def test_an_import_goes_to_its_upload_link_then_is_waited_for_with_progress(tmp_path, clock):
    waiting, queued, done = (answered(n) for n in ("an import, waiting for its file", "the import's file, sent to its upload link", "an import, done"))
    running = (200, {**done[1], "state": "running", "percent": 40.0, "result": None})
    client, fake = ada(waiting, queued, running, done)
    history = tmp_path / "history.jsonl"
    history.write_bytes(b'{"data": {}, "outcome": "keep"}\n')
    seen = []
    j = client.model("tickets").import_file(history, on_progress=seen.append)
    assert isinstance(j, Job) and j.done and j.result == done[1]["result"]
    assert [(s.state, s.percent) for s in seen] == [("queued", 0.0), ("running", 40.0), ("done", 100.0)]
    upload = waiting[1]["upload"]["url"]
    assert [(c[0], c[1]) for c in fake.calls] == [("POST", f"{URL}/v1/models/tickets/imports"), ("PUT", upload), ("GET", f"{URL}/v1/jobs/{done[1]['id']}"), ("GET", f"{URL}/v1/jobs/{done[1]['id']}")]
    assert fake.calls[0][3] == {"format": "jsonl", "partial": False, "learn": True} and "idempotency-key" in fake.calls[0][2]
    put = fake.calls[1]
    assert put[3] == history.read_bytes() or put[3] == json.loads(history.read_bytes())
    assert "authorization" not in put[2] and put[2]["content-type"] == "application/octet-stream"
    assert clock == [0.25, 0.5]


def test_an_import_of_bytes_says_its_format_and_mapping():
    client, fake = ada(answered("an import, waiting for its file"), answered("the import's file, sent to its upload link"))
    j = client.model("routing").import_file(b"product,team\napp,billing\n", format="csv", mapping={"product": "t.w.product", "team": "outcome.team"}, partial=True, learn=False, wait=False)
    assert j.state == "queued" and fake.calls[1][3] == b"product,team\napp,billing\n"
    assert fake.calls[0][3] == {"format": "csv", "mapping": {"product": "t.w.product", "team": "outcome.team"}, "partial": True, "learn": False}
    for source in (b"x", "cases.txt"):
        with pytest.raises(AdaError) as caught:
            client.model("routing").import_file(source)
        assert caught.value.code == "E_INVALID"
    assert len(fake.calls) == 2


def test_an_export_is_waited_for_and_its_file_written(tmp_path, clock):
    done = answered("an export, done, with its download link")
    client, fake = ada((202, job("queued", "export", args={"format": "ada_sqlite"})), done, (200, b"PK\x03\x04zip"))
    out = tmp_path / "tickets.zip"
    j = client.model("tickets").export(format="ada_sqlite", to=out)
    assert j.done and j.download == done[1]["download"] and out.read_bytes() == b"PK\x03\x04zip"
    assert fake.calls[0][3] == {"format": "ada_sqlite"} and fake.calls[2][1] == done[1]["download"]["url"]
    assert "authorization" not in fake.calls[2][2]
    with pytest.raises(AdaError):
        client.download(Job.of(job("running", "export")))


def test_a_backtest_and_tuning_by_versions(clock):
    bt = answered("a backtest, done")
    live = answered("a settings change, live at once")
    reencode = {"version": 3, "active": False, "job": job("queued", "reencode")}
    client, fake = ada(
        (202, job("queued", "backtest")),
        bt,
        (200, {"version": 1, "settings": {"k": 15}}),
        live,
        (200, reencode),
        (200, job("done", "reencode", result={"store": "made"})),
        (200, {"versions": [{"version": 1, "active": False}, {"version": 2, "active": True}]}),
        (200, {"version": 1, "active": True, "job": None}),
        (200, {"version": 4, "active": True, "job": None}),
    )
    m = client.model("tickets")
    j = m.backtest([{"settings": {"word_evidence": 0}, "name": "no word evidence"}], holdout={"newest": 40})
    assert j.done and j.result["candidates"][0]["accuracy"] == bt[1]["result"]["candidates"][0]["accuracy"]
    assert fake.calls[0][3] == {"candidates": [{"settings": {"word_evidence": 0}, "name": "no word evidence"}], "holdout": {"newest": 40}}
    assert m.settings() == {"version": 1, "settings": {"k": 15}}
    assert m.settings({"word_evidence": 0}, note="why", backtest=j.id) == {"version": 2, "active": True, "job": None}
    assert fake.calls[3][3] == {"changes": {"word_evidence": 0}, "note": "why", "backtest": j.id}
    changed = m.settings({"word_weights": False})
    assert changed["version"] == 3 and isinstance(changed["job"], Job) and changed["job"].done
    assert [v["version"] for v in m.versions()] == [1, 2]
    assert m.activate(1)["active"]
    assert m.set_spec({"name": "tickets"}, note="a cost")["version"] == 4
    assert paths(fake) == [
        ("POST", "/v1/models/tickets/backtest"),
        ("GET", "/v1/jobs/j1"),
        ("GET", "/v1/models/tickets/settings"),
        ("PATCH", "/v1/models/tickets/settings"),
        ("PATCH", "/v1/models/tickets/settings"),
        ("GET", "/v1/jobs/j1"),
        ("GET", "/v1/models/tickets/versions"),
        ("POST", "/v1/models/tickets/versions/1/activate"),
        ("PUT", "/v1/models/tickets/spec"),
    ]
    assert all("idempotency-key" in c[2] for c in fake.calls if c[0] != "GET")


def test_a_job_that_fails_and_one_that_outlasts_the_wait(clock):
    failed = job("failed", error={"code": "E_SPEC", "message": "Too few graded precedents.", "path": "output"})
    client, _ = ada((202, job("queued")), (200, failed))
    with pytest.raises(JobFailedError) as caught:
        client.model("tickets").learn_job()
    assert (caught.value.code, caught.value.message, caught.value.detail["path"]) == ("E_SPEC", "Too few graded precedents.", "output")
    assert caught.value.detail["job"]["state"] == "failed"
    client, _ = ada(*[(200, job("running", percent=10.0))] * 20)
    with pytest.raises(AdaTimeoutError) as late:
        client.wait("j1", timeout=5)
    assert late.value.code == "E_TIMEOUT" and late.value.detail == {"job": "j1"}
    client, fake = ada((202, job("queued", "calibrate")))
    assert client.model("tickets").calibrate(wait=False).state == "queued" and paths(fake) == [("POST", "/v1/models/tickets/calibrate")]


# cases


def test_record_many_sends_a_thousand_a_request_each_made_once():
    def got(n, total):
        return (200, {"ids": [f"i{k}" for k in range(n)], "added": n, "replaced": 0, "precedents": total})

    client, fake = ada(got(1000, 1000), got(1000, 2000), got(500, 2500))
    total = client.model("tickets").record_many(({"data": {"n": i}, "outcome": "keep"} for i in range(2500)), idempotency_key="load-1")
    assert (total["added"], total["precedents"], len(total["ids"])) == (2500, 2500, 2500)
    assert [len(c[3]["cases"]) for c in fake.calls] == [1000, 1000, 500]
    assert [c[2]["idempotency-key"] for c in fake.calls] == ["load-1", "load-1.1", "load-1.2"]
    client, fake = ada((200, {"id": "a1", "value": "keep"}), (200, {"id": "a1", "forgotten": True}))
    client.model("tickets").grade("a1", "keep", output="team")
    client.model("tickets").forget("a1")
    assert paths(fake) == [("POST", "/v1/models/tickets/grade"), ("DELETE", "/v1/models/tickets/precedents/a1")]
    assert fake.calls[0][3] == {"id": "a1", "value": "keep", "output": "team"}


# refusals


@pytest.mark.parametrize(
    ("name", "error"),
    [
        ("a wrong key", AuthError),
        ("a model that is not there", ModelMissingError),
        ("a spec that reads a role another way", SpecReadingError),
        ("cases past the plan's precedents", LimitError),
        ("past the plan's month of requests", LimitError),
        ("past the plan's calls a second", RateError),
        ("a big model asked with few of its roles", FewRolesError),
        ("another import open on the model", BusyError),
    ],
)
def test_a_refusal_is_its_typed_error(name, error):
    c = case(name)
    client, fake = ada(answered(name), retry_deadline=0)
    with pytest.raises(error) as caught:
        client._call(c["request"]["method"], c["request"]["path"], c["request"]["body"])
    err, sent = caught.value, c["response"]["body"]["error"]
    assert isinstance(err, AdaError) and (err.code, err.status, err.message) == (sent["code"], c["response"]["status"], sent["message"])
    assert err.detail == {k: v for k, v in sent.items() if k not in ("code", "message")} and err.trace_id == sent["trace_id"]
    assert len(fake.calls) == 1
    if name == "cases past the plan's precedents":
        assert (err.reason, err.used, err.max, err.upgrade, err.resets_at) == ("precedents", 995, 1000, None, None)
    if name == "past the plan's month of requests":
        assert (err.reason, err.plan, err.upgrade) == ("requests", "Free", "Basic")
        assert (err.used, err.max, err.resets_at) == (sent["used"], sent["max"], sent["resets_at"]) and err.max == 5_000
    if error is RateError:
        assert err.retry_after == float(c["response"]["headers"]["retry-after"]) == sent["retry_after"] and err.max == 5
    if error is SpecReadingError:
        assert isinstance(err, SpecError) and err.path is None


def test_an_answer_that_is_not_json_or_has_no_code_and_ada_unreachable():
    with pytest.raises(AdaError) as caught:
        Ada(URL, "k", transport=lambda *a: (502, b"<html>bad gateway</html>"), retry_deadline=0).models()
    assert (caught.value.code, caught.value.status) == ("E_RUNTIME", 502)

    def gone(*a):
        raise OSError("no route to host")

    with pytest.raises(AdaError) as caught:
        Ada(URL, "k", transport=gone, retry_deadline=0).models()
    assert caught.value.code == "E_UNREACHABLE"
    for status, code in ((401, "E_AUTH"), (402, "E_LIMIT"), (404, "E_NOT_FOUND"), (429, "E_RATE")):
        with pytest.raises(AdaError) as caught:
            Ada(URL, "k", transport=lambda *a, s=status: (s, b"{}"), retry_deadline=0).models()
        assert caught.value.code == code


# what is sent again


def test_a_write_carrying_its_key_is_sent_again_with_the_same_key_and_body(clock):
    client, fake = ada(
        (503, {"error": {"code": "E_UNAVAILABLE", "message": "Ada is unreachable for a moment: try again."}}),
        (504, {"error": {"code": "E_TIMEOUT", "message": "No answer within 30 seconds: try again."}}),
        (200, {"ids": ["a"], "added": 1, "replaced": 0, "precedents": 1}),
    )
    client.model("tickets").record_many([{"data": {"a": 1}}])
    assert len(fake.calls) == 3 and len({c[2]["idempotency-key"] for c in fake.calls}) == 1
    assert len({json.dumps(c[3]) for c in fake.calls}) == 1 and len(clock) == 2


def test_a_read_is_sent_again_and_a_3_0_write_without_a_key_is_not(clock):
    q = case("a query through POST /v1/runs, as SDK 3.0 calls it")
    client, fake = ada(OSError("reset"), (502, {}), answered(q["name"]))
    r = client.model("tickets").query(q["request"]["body"]["inputs"]["data"])
    assert isinstance(r, Result) and r.data == q["response"]["body"]["data"] and len(fake.calls) == 3
    assert 0.125 <= clock[0] <= 0.25 and 0.25 <= clock[1] <= 0.5
    client, fake = ada(OSError("reset"))
    with pytest.raises(AdaError) as caught:
        client.model("tickets").record({"a": 1}, "keep")
    assert caught.value.code == "E_UNREACHABLE" and len(fake.calls) == 1
    client, fake = ada(OSError("reset"))
    with pytest.raises(AdaError):
        client.resume("r1", "yes")
    assert len(fake.calls) == 1


def test_too_many_requests_waits_as_retry_after_says_then_raises(clock):
    rate = (429, {"error": {"code": "E_RATE", "message": "Too many requests a second."}}, {"Retry-After": "3"})
    client, fake = ada(rate, answered("a decision"))
    assert client.decide("tickets", {}).outcome and clock == [3.0]
    client, fake = ada(*[rate] * 5, retry_deadline=7)
    with pytest.raises(glyphh.RateError) as caught:
        client.model("tickets").record({"a": 1})
    assert caught.value.retry_after == 3.0 and len(fake.calls) == 3


# SDK 3.0's calls, through POST /v1/runs


def test_3_0s_calls_name_their_functions_and_a_long_learn_is_waited_for(clock):
    q = case("a query through POST /v1/runs, as SDK 3.0 calls it")
    body = q["response"]["body"]
    client, fake = ada(*[(200, body)] * 6)
    m = client.model("tickets")
    validate(m.query(q["request"]["body"]["inputs"]["data"]).data, CONTRACT["answer"])
    m.record({"a": 1}, "keep")
    m.record({"a": 1}, outcomes={"team": "billing"}, ts=5.0)
    m.facts({"a": 1}, top=2, clearance=0.5)
    m.probabilities({"a": 1}, output="team")
    m.call("decide", {"data": {"a": 1}})
    sent = [(c[3]["function"], c[3]["inputs"], c[3].get("clearance")) for c in fake.calls]
    assert sent == [
        ("query", q["request"]["body"]["inputs"], None),
        ("record", {"data": {"a": 1}, "outcome": "keep"}, None),
        ("record", {"data": {"a": 1}, "ts": 5.0, "outcomes": {"team": "billing"}}, None),
        ("facts", {"data": {"a": 1}, "top": 2}, 0.5),
        ("probabilities", {"data": {"a": 1}, "output": "team"}, None),
        ("decide", {"data": {"a": 1}}, None),
    ]
    still = {**body, "function": "learn", "data": {"job": job("running", percent=60.0)}}
    client, fake = ada((200, still), (200, job("done", result={"precedents": 12, "tau": 0.4})))
    r = client.model("tickets").learn(sample=50)
    assert r.done and r.data == {"precedents": 12, "tau": 0.4} and fake.calls[0][3]["inputs"] == {"sample": 50}


# the address and the key


def test_the_url_defaults_to_ada_cloud_and_the_key_comes_from_the_environment(monkeypatch, tmp_path):
    for name in ("GLYPHH_ADA_URL", "GLYPHH_RUNTIME_URL", "GLYPHH_API_KEY", "GLYPHH_RUNTIME_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))  # no sign-in on this machine
    with pytest.raises(AdaError) as caught:
        Ada()
    assert caught.value.code == "E_CONFIG" and "GLYPHH_API_KEY" in caught.value.message
    assert "glyphh login" in caught.value.message
    glyphh.signin.write_install(glyphh.signin.Install("i1", "glyphh_it_signed_in"))  # glyphh login, or the plugin's
    assert Ada().key == "glyphh_it_signed_in"
    monkeypatch.setenv("GLYPHH_RUNTIME_KEY", "glyphh_rk_old")
    assert Ada().key == "glyphh_rk_old" and Ada().url == DEFAULT_URL == "https://ada.glyphh.ai"
    monkeypatch.setenv("GLYPHH_API_KEY", "glyphh_ak_env")
    monkeypatch.setenv("GLYPHH_RUNTIME_URL", "https://old.example/")
    assert (Ada().key, Ada().url) == ("glyphh_ak_env", "https://old.example")
    monkeypatch.setenv("GLYPHH_ADA_URL", "http://ada:8080/")
    assert Ada().url == "http://ada:8080"


def test_usage_is_typed_in_the_servers_shape():
    c = case("the org's usage")
    client, fake = ada(answered("the org's usage"))
    usage = client.usage()
    assert isinstance(usage, Usage) and paths(fake) == [("GET", "/v1/usage")]
    sent = c["response"]["body"]
    assert (usage.plan, usage.month, usage.resets_at, usage.models) == (sent["plan"], sent["month"], sent["resets_at"], sent["models"])
    assert (usage.precedents.used, usage.precedents.max) == (sent["precedents"]["used"], 1000)
    r = usage.requests
    assert (r.used, r.max, r.over, r.overage, usage.requests_per_second) == (sent["requests"]["used"], 5_000, 0, False, 5)
    assert usage["plan"] == "Free" and usage.data == sent  # reads as the answer's dict too
    assert usage.ada is not None and usage.ada.latest_stable == "ada-1-0" and {v.name: v.models for v in usage.ada} == {"ada-1-1-beta": 0, "ada-1-0": 3}
    assert Usage.of({k: v for k, v in sent.items() if k != "ada"}).ada is None  # a contract 4 server
    # Team past its month, metered; Enterprise, by contract: no caps
    team = {**sent, "plan": "Team", "requests": {"used": 5_012_345, "max": 5_000_000, "over": 12_345, "overage": True}, "requests_per_second": 200}
    enterprise = {**sent, "plan": "Enterprise", "precedents": {"used": 9, "max": None}, "requests": {"used": 3, "max": None, "over": 0, "overage": False}, "requests_per_second": None}
    for body in (team, enterprise):
        validate(body, CONTRACT["usage"])
    client, _ = ada((200, team), (200, enterprise))
    t, e = client.usage(), client.usage()
    assert (t.requests.over, t.requests.overage, t.requests_per_second) == (12_345, True, 200)
    assert (e.precedents.max, e.requests.max, e.requests_per_second) == (None, None, None)


def test_a_rate_refusal_without_the_header_waits_as_its_body_says(clock):
    body = {"error": {"code": "E_RATE", "message": "Your plan allows 5 Ada calls a second: try again in 2 seconds.", "retry_after": 2, "reason": "rate", "max": 5}}
    client, fake = ada((429, body), answered("a decision"))
    assert client.decide("tickets", {}).outcome and clock == [2.0]


# a self-hosted cluster's refusals and read-your-writes, kept from 3.1 (nothing of them reaches the cloud)

NO_HEAD = (503, {"error": {"code": "E_NO_HEAD", "message": "The cluster has no head."}}, {"Retry-After": "2", "Rrotor-Cluster-Seq": "1041"})
DONE = {"run_id": "r1", "model": "incidents", "version": 1, "function": "record", "status": "done", "data": {"id": "a1"}, "step": None, "prompt": None, "seconds": 0.1}


def test_a_clusters_no_head_is_retried_and_its_seq_sent_back(clock):
    client, fake = ada(NO_HEAD, NO_HEAD, (200, DONE, {"Rrotor-Cluster-Seq": "1042"}), (200, {"models": []}))
    assert client.model("incidents").record({"a": 1}).data == {"id": "a1"} and clock == [2.0, 2.0]
    client.models()
    assert client.cluster_seq == 1042 and fake.calls[-1][2]["rrotor-min-seq"] == "1042"
    client, fake = ada(*[NO_HEAD] * 6, retry_deadline=9)
    with pytest.raises(NoHeadError):
        client.model("incidents").record({"a": 1})
    assert len(fake.calls) == 5
    client, fake = ada((200, DONE, {"Rrotor-Cluster-Seq": "9"}), (200, DONE), read_your_writes=False)
    client.model("incidents").record({"a": 1})
    client.model("incidents").record({"a": 1})
    assert "rrotor-min-seq" not in fake.calls[1][2]


@pytest.mark.parametrize(("code", "status", "error"), [("E_HEAD_LOST", 503, HeadLostError), ("E_NOT_COMMITTED", 503, NotCommittedError), ("E_RUN_LOST", 410, RunLostError)])
def test_a_clusters_refusals_are_typed_and_not_sent_again(clock, code, status, error):
    client, fake = ada((status, {"error": {"code": code, "message": "x"}}))
    with pytest.raises(error):
        client.model("incidents").record({"a": 1})
    assert len(fake.calls) == 1 and clock == []
    failed = {**DONE, "function": "query", "status": "failed", "data": {"code": "E_READ_ONLY", "reason": "query writes"}}
    client, _ = ada((200, failed))
    with pytest.raises(ReadOnlyError) as caught:
        client.model("incidents").query({"a": 1})
    assert caught.value.detail == {"run_id": "r1", "function": "query"}
    limited = {**DONE, "data": {"status": "limit_exceeded", "indexed": False, "message": "cap", "cap": 5000}}
    client, _ = ada((200, limited))
    assert client.model("incidents").record({"a": 1}).limit_exceeded


def test_retry_after_as_a_date_and_a_transport_that_answers_no_headers(clock):
    assert glyphh.client._retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0
    assert glyphh.client._retry_after("1.5") == 1.5 and glyphh.client._retry_after("soon") is None
    client, _ = ada((200, {"models": []}))
    assert client.models() == [] and client.cluster_seq == 0


def test_the_docs_tell_the_cloud_story():
    """What a customer and Claude read: Ada Cloud, an API key, no runtime of their own to run."""
    for doc in ("README.md", "sdk/python/README.md", "sdk/typescript/README.md", "plugins/glyphh/skills/ada/SKILL.md"):
        text = (ROOT / doc).read_text()
        assert "ada.glyphh.ai" in text or doc.endswith("SKILL.md"), doc
        for gone in ("rrotor", "self-host", "Self-host", "install.sh", "runtime key", "model.py", "glyphh.app", "licence key", "license key"):
            assert gone not in text, (doc, gone)
    assert "GLYPHH_API_KEY" in (ROOT / "sdk/python/README.md").read_text()
    assert glyphh.__version__ == "3.5.0"
    for doc in ("sdk/python/README.md", "sdk/typescript/README.md", "plugins/glyphh/skills/ada/SKILL.md"):
        text = (ROOT / doc).read_text()
        assert "ada-1-0" in text and "upgrade" in text, doc


# Ada versions (contract 5)


def test_the_ada_versions_are_listed_typed():
    c = case("the Ada versions")
    client, fake = ada(answered(c["name"]))
    found = client.ada.versions()
    assert paths(fake) == [("GET", "/v1/ada")] and isinstance(found, glyphh.AdaVersions)
    assert (found.latest_stable, found.contract, len(found)) == ("ada-1-0", 5, 2)
    beta, stable = found
    assert (beta.name, beta.kernel, beta.status, beta.beta, beta.open, beta.changes_answers, beta.models) == ("ada-1-1-beta", "3.13.0", "beta", True, True, True, 1)
    assert (stable.name, stable.status, stable.deprecated, stable.ends, stable.released) == ("ada-1-0", "stable", None, None, "2026-10-22")
    assert found.get("ada-1-0") is stable and found.get("ada-9-9") is None and stable["kernel"] == "3.12.2"
    moved = {**c["response"]["body"], "versions": [{**c["response"]["body"]["versions"][1], "name": "ada-1-1", "aliases": ["ada-1-1-beta"]}]}
    client, _ = ada((200, moved))
    assert client.ada.versions().get("ada-1-1-beta").name == "ada-1-1"  # a promoted beta's name resolves
    client, _ = ada((200, c["response"]["body"]))
    assert client.ada.latest_stable() == "ada-1-0"


def test_a_model_carries_its_ada_on_its_info_and_on_each_version():
    info, listed, versions = case("a model and its Ada"), case("the org's models, each with its Ada"), case("a model's versions, each with its Ada")
    client, fake = ada(answered(info["name"]), answered(listed["name"]), answered(versions["name"]))
    m = client.model("tickets")
    i = m.info()
    assert isinstance(i, glyphh.ModelInfo) and isinstance(i, dict) and i == info["response"]["body"]  # a dict, as in 3.2
    assert (i.name, i.version, i.ada, i.ada_status, i.ada_notice) == ("tickets", 4, "ada-1-1-beta", "beta", None)
    assert [(x.name, x.ada) for x in client.models()] == [("routing", "ada-1-0"), ("tickets", "ada-1-1-beta")]
    vs = m.versions()
    assert [(v.version, v.active, v.ada, v.kernel) for v in vs] == [(3, False, "ada-1-0", "3.12.2"), (4, True, "ada-1-1-beta", "3.13.0")]
    assert vs[0]["note"] == "every word as it is"
    assert paths(fake) == [("GET", "/v1/models/tickets"), ("GET", "/v1/models"), ("GET", "/v1/models/tickets/versions")]
    client, _ = ada((200, {"name": "old", "version": 1}))
    old = client.model("old").info()
    assert (old.ada, old.ada_status, old.ada_notice) == (None, None, None)  # a contract 4 server: no ada, no notice


def test_a_model_is_made_on_the_latest_stable_unless_an_ada_is_named():
    beta = case("a model made on a beta Ada")
    client, fake = ada(answered("a model made from its spec"), answered(beta["name"]))
    first = client.create_model("routing", {"name": "routing"})
    assert "ada" not in fake.calls[0][3] and first.created.ada == "ada-1-0"
    # on the latest stable, the quiet notice: a beta is open to try
    assert first.created.ada_notice == glyphh.AdaNotice("beta", "ada-1-1-beta is available to try (beta).", "ada-1-1-beta", None)
    sent = beta["request"]["body"]
    made = client.create_model(sent["name"], sent["spec"], ada="ada-1-1-beta")
    assert fake.calls[1][3] == sent and (made.created.ada, made.created.ada_status, made.created.ada_notice) == ("ada-1-1-beta", "beta", None)


def test_a_backtest_against_another_ada_then_an_upgrade_waited_for_then_a_rollback(clock):
    bt, up = answered("a backtest against another Ada, done"), answered("an upgrade to another Ada")
    done = {**up[1]["job"], "state": "done", "percent": 100.0, "result": {"version": 4, "ada": "ada-1-1-beta"}}
    client, fake = ada(
        (202, {**bt[1], "state": "queued", "percent": 0.0, "result": None}),
        bt,
        up,
        (200, {**done, "state": "running", "percent": 50.0, "result": None}),
        (200, done),
        (200, {"version": 3, "active": True, "job": None}),
    )
    m = client.model("tickets")
    j = m.backtest(ada="ada-1-1-beta", holdout={"newest": 200})
    assert fake.calls[0][3] == {"candidates": [], "ada": "ada-1-1-beta", "holdout": {"newest": 200}}
    assert (j.result["active"]["ada"], j.result["candidates"][0]["ada"]) == ("ada-1-0", "ada-1-1-beta")
    assert j.result["candidates"][0]["cost"] < j.result["active"]["cost"]
    seen = []
    moved = m.upgrade("ada-1-1-beta", note="ada-1-1-beta: 2 fewer wrong on the last 200", backtest=j.id, on_progress=seen.append)
    assert fake.calls[2][3] == {"ada": "ada-1-1-beta", "note": "ada-1-1-beta: 2 fewer wrong on the last 200", "backtest": j.id}
    assert (moved["version"], moved["ada"], moved["from"], moved["active"]) == (4, "ada-1-1-beta", "ada-1-0", True)
    assert isinstance(moved["job"], Job) and moved["job"].kind == "reencode" and [s.state for s in seen] == ["queued", "running", "done"]
    assert m.activate(3)["active"]  # the rollback
    assert paths(fake) == [
        ("POST", "/v1/models/tickets/backtest"),
        ("GET", f"/v1/jobs/{bt[1]['id']}"),
        ("POST", "/v1/models/tickets/upgrade"),
        ("GET", f"/v1/jobs/{up[1]['job']['id']}"),
        ("GET", f"/v1/jobs/{up[1]['job']['id']}"),
        ("POST", "/v1/models/tickets/versions/3/activate"),
    ]
    assert all("idempotency-key" in c[2] for c in fake.calls if c[0] == "POST")
    client, fake = ada(up)
    later = client.model("tickets").upgrade(wait=False)
    assert fake.calls[0][3] == {} and later["active"] is False and later["job"].state == "queued"  # no ada: the latest stable
    client, fake = ada((202, job("queued", "backtest")))
    client.model("tickets").backtest([{"ada": "ada-1-1-beta", "settings": {"k": 5}}], wait=False)
    assert fake.calls[0][3] == {"candidates": [{"ada": "ada-1-1-beta", "settings": {"k": 5}}]}


@pytest.mark.parametrize(
    ("name", "error"),
    [
        ("an Ada that does not exist", glyphh.AdaVersionUnknownError),
        ("a retired Ada", glyphh.AdaVersionRetiredError),
        ("a deprecated Ada as an upgrade's target", glyphh.AdaVersionDeprecatedError),
        ("a beta closed to new models", glyphh.AdaBetaClosedError),
        ("an Ada this deploy does not have", glyphh.AdaVersionUnavailableError),
        ("an upgrade to the Ada the model runs", glyphh.NoChangeError),
    ],
)
def test_an_ada_refusal_is_typed_names_the_latest_stable_and_is_never_sent_again(clock, name, error):
    c = case(name)
    client, fake = ada(answered(name))
    with pytest.raises(error) as caught:
        client._call(c["request"]["method"], c["request"]["path"], c["request"]["body"], idempotency_key="k1")
    err, sent = caught.value, c["response"]["body"]["error"]
    assert (err.code, err.status, err.message) == (sent["code"], c["response"]["status"], sent["message"])
    assert len(fake.calls) == 1 and clock == []  # E_ADA_UNAVAILABLE's 503 is not retried: no kernel comes back
    if isinstance(err, glyphh.AdaVersionError):
        assert (err.ada, err.latest) == (sent["ada"], sent["latest"])


def test_a_deprecated_or_moved_model_warns_once_per_client_and_notice():
    deprecated, moved = case("a model on a deprecated Ada"), case("a decision just after its model was moved off a retired Ada")
    client, _ = ada(answered(deprecated["name"]), answered(deprecated["name"]), answered(moved["name"]))
    with pytest.warns(glyphh.AdaDeprecationWarning) as seen:
        info = client.model("claims").info()
        client.model("claims").info()
        d = client.decide("claims", moved["request"]["body"]["data"])
    assert [str(w.message) for w in seen] == [f"Glyphh Ada: {deprecated['response']['headers']['glyphh-ada-notice']}", f"Glyphh Ada: {moved['response']['headers']['glyphh-ada-notice']}"]
    assert info.ada_notice.kind == "deprecated" and (info.ada_notice.to, info.ada_notice.ends) == ("ada-1-1", "2027-04-21")
    assert (d.ada, d.version) == ("ada-1-1", 3) and issubclass(glyphh.AdaDeprecationWarning, FutureWarning)
    client, _ = ada(answered("a model and its Ada"))
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        client.model("tickets").info()  # a beta's notice is in the body, never a warning


def test_a_server_of_a_newer_contract_is_refused_clearly_never_read():
    newer = {"glyphh-contract": "6"}
    for answer in ((200, {"models": []}, newer), (503, {"error": {"code": "E_UNAVAILABLE", "message": "x"}}, newer)):
        client, fake = ada(answer)
        with pytest.raises(glyphh.ClientTooOldError) as caught:
            client.models()
        err = caught.value
        assert (err.code, err.contract, err.supported) == ("E_CLIENT_TOO_OLD", 6, 5) and len(fake.calls) == 1
        assert "pip install -U glyphh" in err.message and "contract 6" in err.message
    client, _ = ada((200, {**case("the Ada versions")["response"]["body"], "contract": 7}))
    with pytest.raises(glyphh.ClientTooOldError):
        client.ada.versions()
    client, _ = ada((200, {"models": []}, {"Glyphh-Contract": "5"}), (200, {"models": []}, {"glyphh-contract": "4"}), (200, {"models": []}))
    assert client.models() == client.models() == client.models() == []  # its own, an older one, or none: read
