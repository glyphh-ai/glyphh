"""The Python SDK against a real Ada Cloud (run.sh: glyphh-ai/server with its workers, Postgres with pgvector and Redis,
in Docker): a model made, its history imported, learned, decided, backtested, tuned, rolled back, exported and
imported again; every live answer checked against contract/contract.json, and each fixture of contract/fixtures.json
against the live answer to the same call (its schema, and the same keys)."""

from __future__ import annotations

import io
import json
import os
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from jsonschema import validate

from glyphh import (
    Ada,
    AdaVersions,
    AdaVersionUnknownError,
    AuthError,
    BusyError,
    Decision,
    Job,
    LimitError,
    ModelInfo,
    ModelMissingError,
    NoChangeError,
    RateError,
    Result,
    SpecReadingError,
)
from glyphh.client import _urllib

CONTRACT = json.loads(Path("/contract/contract.json").read_text())
FIXTURES = json.loads(Path("/contract/fixtures.json").read_text())

SPEC: Dict[str, Any] = {
    "name": "tickets",
    "seed": 5,
    "dimension": 2048,
    "layers": [
        {
            "name": "t",
            "segments": [
                {
                    "name": "s",
                    "roles": [
                        {"name": "plan"},
                        {"name": "channel"},
                        {"name": "age", "numeric_config": {"min_value": 0, "max_value": 30, "bin_width": 3}},
                        {"name": "text", "text_encoding": "bag_of_words"},
                        {"name": "owner", "security_weight": 0.9},
                        {"name": "id", "key_part": True, "similarity_weight": 0},
                    ],
                }
            ],
        }
    ],
    "output": {"costs": {"refund": {"keep": 3}, "keep": {"refund": 1}}, "ask_below": 0.6},
}
ROUTING: Dict[str, Any] = {
    "name": "routing",
    "seed": 4,
    "dimension": 1024,
    "layers": [
        {
            "name": "t",
            "segments": [
                {
                    "name": "w",
                    "roles": [
                        {"name": "product"},
                        {"name": "text", "text_encoding": "bag_of_words"},
                        {"name": "ref", "key_part": True, "similarity_weight": 0},
                    ],
                }
            ],
        }
    ],
    "outputs": {"team": {"values": ["billing", "tech"]}, "urgent": {"values": ["yes", "no"]}},
    "settings": {"rare": 1},
}
TEXTS = ["charged twice", "card lost", "app slow", "refund late", "login broken", "invoice wrong"]


def case(i: int) -> Dict[str, Any]:
    plan, channel, age = ["free", "pro", "team"][i % 3], ["mail", "chat"][i % 2], (i * 7) % 31
    text = TEXTS[i % len(TEXTS)]
    refund = (plan == "free") ^ (age > 20) ^ ("twice" in text)
    what = {"plan": plan, "channel": channel, "age": age, "text": text, "owner": f"o{i % 2}", "id": f"c{i}"}
    return {"data": {"t": {"s": what}}, "outcome": "refund" if refund else "keep"}


def asked(i: int) -> Dict[str, Any]:
    data = case(i)["data"]
    data["t"]["s"].pop("id")
    return data


class Recorder:
    """The SDK's transport, recording every exchange: (method, path, status, answer, request body), and the headers the
    contract names (Retry-After, Glyphh-Contract, Glyphh-Ada, Glyphh-Ada-Notice) by its place in `seen`."""

    def __init__(self) -> None:
        self.seen: List[Tuple[str, str, int, Any, Any]] = []
        self.headers: Dict[int, Dict[str, str]] = {}

    def __call__(self, method: str, url: str, headers: Any, body: Optional[bytes]) -> Any:
        status, content, got = _urllib(method, url, headers, body)
        path = re.sub(r"^https?://[^/]+", "", url)
        named = {k.lower(): v for k, v in got.items() if k.lower() == "retry-after" or k.lower().startswith("glyphh-")}
        self.headers[len(self.seen)] = named
        self.seen.append((method, path, status, _json(content), _json(body)))
        return status, content, got

    def last(self, method: str, path: str, status: int, where: Any = None) -> Tuple[Any, Any, str, Dict[str, str]]:
        """The latest answer to such a request: (answer, request body, path, the headers the contract names)."""
        for i in range(len(self.seen) - 1, -1, -1):
            m, p, s, answer, sent = self.seen[i]
            if m == method and re.fullmatch(path, p.split("?")[0]) and s == status and (where is None or where(answer)):
                return answer, sent, p, self.headers.get(i, {})
        raise AssertionError(f"no live answer to {method} {path} {status}")


def _json(content: Optional[bytes]) -> Any:
    try:
        return json.loads(content) if content else None
    except ValueError:
        return None


@pytest.fixture(scope="module")
def flow(tmp_path_factory: pytest.TempPathFactory) -> Dict[str, Any]:
    tmp = tmp_path_factory.mktemp("ada")
    rec = Recorder()
    ada = Ada(transport=rec, retry_deadline=120)  # a laptop's one or two sync workers can be slower than 10 s a read
    out: Dict[str, Any] = {"rec": rec, "ada": ada}
    for name in ("tickets", "tickets-copy", "routing", "tickets-beta"):
        try:
            ada.delete_model(name)
        except ModelMissingError:
            pass

    # make, import (upload link, then the job, with progress), record more, learn
    m = ada.create_model("tickets", SPEC)
    assert m.created is not None and m.created["version"] == 1 and m.created["precedents"] == 0
    history = tmp / "history.jsonl"
    history.write_text("\n".join(json.dumps(case(i)) for i in range(160)) + "\n")
    seen: List[Job] = []
    job = m.import_file(history, on_progress=seen.append)
    assert job.done and job.kind == "import" and job.result["added"] == 160 and job.result["refused"] == 0
    assert seen[-1].done and [j.percent for j in seen] == sorted(j.percent for j in seen)
    out["import"] = job
    many = m.record_many(case(i) for i in range(160, 1210))  # two requests: 1,000 and 50
    assert (many["added"], many["replaced"], many["precedents"], len(many["ids"])) == (1050, 0, 1210, 1050)
    again = m.record_many([case(5)])
    assert (again["added"], again["replaced"], again["precedents"]) == (0, 1, 1210)
    learned = m.learn()
    assert isinstance(learned, Result) and learned.done and learned.data["precedents"] == 1210
    assert m.learn_job().result["precedents"] == 1210

    # decide
    out["decision"] = d = ada.decide("tickets", asked(3), include=["facts"], clearance=0.5)
    assert isinstance(d, Decision) and d.outcome in ("keep", "refund") and d.version == 1 and d.facts
    assert d.done and d.data["outcome"] == d.outcome  # reads as 3.0's Result too

    # backtest, then tune: a live change, a rollback, a re-encode
    bt = m.backtest([{"settings": {"word_evidence": 0}, "name": "no word evidence"}, {"settings": {"k": 5}}], holdout={"newest": 100})
    assert bt.done and bt.result["held_out"] == 100 and len(bt.result["candidates"]) == 2
    assert {"accuracy", "cost", "ask_rate", "log_loss"} <= set(bt.result["active"])
    out["backtest"] = bt
    assert m.settings()["settings"]["word_evidence"] == 2.0
    live = m.settings({"word_evidence": 0}, note="fewer asks on the last 100", backtest=bt.id)
    assert (live["version"], live["active"], live["job"]) == (2, True, None)
    versions = m.versions()
    assert [(v["version"], v["active"], v["backtest"]) for v in versions] == [(1, False, None), (2, True, bt.id)]
    back = m.activate(1)
    assert (back["version"], back["active"]) == (1, True) and m.info()["version"] == 1
    reencoded = m.settings({"word_weights": False}, note="every word as it is")
    assert reencoded["version"] == 3 and isinstance(reencoded["job"], Job) and reencoded["job"].done
    assert m.info()["version"] == 3
    # a case the precedents split on: under the spec's ask_below (0.6), a person decides; the outcome is the guess
    out["asks"] = asks = m.decide({"t": {"s": {"channel": "chat"}}})
    assert asks.ask and asks.outcome in ("keep", "refund") and max(asks.probabilities.values()) < 0.6
    other = json.loads(json.dumps(SPEC))
    other["layers"][0]["segments"][0]["roles"][2] = {"name": "age", "text_encoding": "bag_of_words"}
    with pytest.raises(SpecReadingError) as refused:
        m.set_spec(other)
    assert refused.value.status == 422 and refused.value.detail["roles"] == ["t.s.age"]

    # export, and the export imported into a model of the same spec answers the same
    zipped = tmp / "tickets.zip"
    ex = m.export(to=zipped)
    assert ex.done and ex.download and ex.result["precedents"] == 1210
    names = zipfile.ZipFile(io.BytesIO(zipped.read_bytes())).namelist()
    assert any(n.endswith(".jsonl") for n in names) and "spec.json" in " ".join(names)
    out["export"] = ex
    copy = ada.create_model("tickets-copy", m.spec())
    copied = copy.import_file(zipped)
    assert copied.done and copied.result["added"] == 1210
    a, b = m.decide(asked(7)), copy.decide(asked(7))
    assert (a.outcome, a.probabilities) == (b.outcome, b.probabilities)

    # named outputs from a CSV, decided at once
    r = ada.create_model("routing", ROUTING)
    rows = ["product,text,ref,team,urgent"]
    for i in range(60):
        team = "billing" if i % 2 else "tech"
        words = ["refund charge", "crash login"][i % 2 == 0]
        rows.append(f"{'app' if i % 3 else 'web'},{words} please,r{i},{team},{'yes' if i % 5 == 0 else 'no'}")
    mapping = {"product": "t.w.product", "text": "t.w.text", "ref": "t.w.ref", "team": "outcome.team", "urgent": "outcome.urgent"}
    routed = r.import_file("\n".join(rows).encode(), format="csv", mapping=mapping)
    assert routed.done and routed.result["added"] == 60
    both = r.decide({"t": {"w": {"product": "app", "text": "refund now"}}}, outputs=["team", "urgent"])
    assert both.outputs is not None and both.outputs["team"].outcome == "billing" and set(both.outputs) == {"team", "urgent"}
    out["outputs"] = both

    # 3.0's call shape
    q = m.query(asked(3))
    assert isinstance(q, Result) and q.done and q.data["count"] > 0
    out["query"] = q

    # Ada versions (contract 5): the list, a model's Ada, a backtest on another, an upgrade, a rollback, the refusals
    listed = ada.ada.versions()
    assert isinstance(listed, AdaVersions) and listed.contract == 5 and len(listed) >= 1
    latest = listed.latest_stable
    assert listed.get(latest) is not None and listed.get(latest).status == "stable"
    out["ada_versions"] = listed
    beta = next((v.name for v in listed if v.beta and v.open and v.status == "beta"), None)
    assert beta is not None, "the registry lists a beta open to new models (ada-1-1-beta)"
    assert m.created is not None and m.created.ada == latest  # made with no ada: the latest stable
    info = m.info()
    assert isinstance(info, ModelInfo) and (info.ada, info.ada_status) == (latest, "stable")
    # on the latest stable, the notice is only the quiet one a beta open to try gives: kind beta, to the beta
    assert info.ada_notice is not None and (info.ada_notice.kind, info.ada_notice.to) == ("beta", beta)
    before = info.version
    assert all(v.ada == latest and v.kernel for v in m.versions())
    assert {x.name: x.ada for x in ada.models()}["tickets"] == latest
    assert m.decide(asked(3)).ada == latest
    tried = m.backtest(ada=beta, holdout={"newest": 100})
    assert tried.result["active"]["ada"] == latest and [c["ada"] for c in tried.result["candidates"]] == [beta]
    out["ada_backtest"] = tried
    moved = m.upgrade(beta, note=f"{beta}: on the last 100", backtest=tried.id)
    assert (moved["ada"], moved["from"], moved["active"]) == (beta, latest, True) and moved["job"].done
    assert moved["job"].kind == "reencode" and moved["version"] > before
    on_beta = m.info()
    assert (on_beta.ada, on_beta.ada_status, on_beta.version) == (beta, "beta", moved["version"])
    assert on_beta.ada_notice is None  # running the beta is said by ada_status; no newer stable to offer
    versions = m.versions()
    assert [v.ada for v in versions if v.active] == [beta] and {v.ada for v in versions} == {latest, beta}
    assert m.decide(asked(3)).ada == beta
    with pytest.raises(NoChangeError):
        m.upgrade(beta)
    back = m.activate(before)  # the rollback: on the Ada it ran before
    assert back["version"] == before and (m.info().ada, m.info().version) == (latest, before)
    with pytest.raises(AdaVersionUnknownError) as unknown:
        m.upgrade("ada-9-9")
    assert (unknown.value.status, unknown.value.ada, unknown.value.latest) == (422, "ada-9-9", latest)
    trial = ada.create_model("tickets-beta", {**ROUTING, "name": "tickets-beta"}, ada=beta)
    assert trial.created is not None and (trial.created.ada, trial.created.ada_status) == (beta, "beta")
    trial.delete()

    # usage: GET /v1/usage, the final shape (server's ada-cloud-connector)
    out["usage"] = ada.usage()

    # refusals
    # past the plan's calls a second (Basic: 10): 429 E_RATE with Retry-After, raised by a client that does not wait;
    # sent 20 at a time, so a slow laptop's reads still pass the rate
    quick = Ada(transport=rec, retry_deadline=0)
    with pytest.raises(RateError) as rate, ThreadPoolExecutor(20) as pool:
        for done in [pool.submit(quick.decide, "tickets", asked(1)) for _ in range(60)]:
            done.result()
    assert (rate.value.status, rate.value.max, rate.value.detail["reason"]) == (429, 10, "rate")
    assert rate.value.retry_after is not None and rate.value.retry_after >= 1
    out["rate"] = rate.value
    # a client that waits as Retry-After says goes on
    assert Ada(transport=rec, retry_deadline=30).decide("tickets", asked(1)).outcome
    # past the plan's month (the second org's, used already): 403 E_LIMIT requests, the plan to upgrade to, when it turns
    full = Ada(key=os.environ["ADA_FULL_KEY"], transport=rec, retry_deadline=0)
    with pytest.raises(LimitError) as month:
        full.decide("tickets", asked(1))
    err = month.value
    assert (err.status, err.reason, err.plan, err.upgrade, err.max, err.used) == (403, "requests", "Free", "Basic", 5_000, 5_000)
    assert err.resets_at == out["usage"].resets_at
    # a refused read is not counted
    left = full.usage()
    assert (left.requests.used, left.requests.max, left.requests.over, left.requests.overage) == (5_000, 5_000, 0, False)
    out["month"] = err
    with pytest.raises(AuthError) as wrong:
        Ada(key="glyphh_ak_not_a_key", transport=rec).decide("tickets", asked(1))
    assert wrong.value.status == 401
    with pytest.raises(ModelMissingError):
        ada.model("nope").info()
    waiting = Job.of(ada._write("POST", "/v1/models/routing/imports", {"format": "csv", "mapping": mapping}))
    assert waiting.state == "awaiting" and waiting.upload
    with pytest.raises(BusyError) as busy:
        r.import_file(b"product\napp\n", format="csv")
    assert busy.value.detail["job"] == waiting.id
    return out


def test_the_whole_way(flow: Dict[str, Any]) -> None:
    """create model, import, learn, decide, backtest, activate, export: each answer of its contract's shape."""
    validate(flow["decision"].data, CONTRACT["decision"])
    validate(flow["asks"].data, CONTRACT["decision"])
    validate(flow["outputs"].data, CONTRACT["decision"])
    for job in (flow["import"], flow["backtest"], flow["export"]):
        validate(job.data, CONTRACT["job"])
    validate(flow["query"].data, CONTRACT["answer"])
    usage = flow["usage"]
    validate(usage.data, CONTRACT["usage"])
    assert (usage.plan, usage.models, usage.precedents.max, usage.requests_per_second) == ("Basic", 3, 10_000, 10)
    assert usage.precedents.used >= 2480 and usage["models"] == 3
    assert usage.requests.used > 0 and (usage.requests.max, usage.requests.over, usage.requests.overage) == (50_000, 0, True)
    assert re.fullmatch(r"\d{4}-\d{2}", usage.month) and re.fullmatch(r"\d{4}-\d{2}-01", usage.resets_at)
    validate(flow["ada_versions"].data, CONTRACT["ada_versions"])
    validate(flow["ada_backtest"].data, CONTRACT["job"])
    validate(flow["ada_backtest"].result, CONTRACT["backtest"])
    # every answer of the Ada host says the contract it speaks (the signed upload and download links are not its API)
    rec = flow["rec"]
    for i, (method, path, status, _, _) in enumerate(rec.seen):
        if path.startswith("/v1/") and "upload" not in path and "download" not in path:
            assert rec.headers[i].get("glyphh-contract") == "5", (method, path, status, rec.headers[i])


def _plain_backtest(b: Any) -> bool:
    return b["kind"] == "backtest" and b["state"] == "done" and '"ada"' not in json.dumps(b["args"])


LIVE = {
    "a model made from its spec": ("POST", r"/v1/models", 201, lambda b: b["name"] != "tickets-beta"),
    "a model made on a beta Ada": ("POST", r"/v1/models", 201, lambda b: b["name"] == "tickets-beta"),
    "the Ada versions": ("GET", r"/v1/ada", 200, None),
    "the org's models, each with its Ada": ("GET", r"/v1/models", 200, None),
    "a model and its Ada": ("GET", r"/v1/models/[^/]+", 200, lambda b: b.get("ada_status") == "beta"),
    "a model's versions, each with its Ada": ("GET", r"/v1/models/[^/]+/versions", 200, None),
    "a backtest against another Ada, done": ("GET", r"/v1/jobs/.+", 200, lambda b: b["kind"] == "backtest" and b["state"] == "done" and not _plain_backtest(b)),
    "an upgrade to another Ada": ("POST", r"/v1/models/[^/]+/upgrade", 202, None),
    "an Ada that does not exist": ("POST", r"/v1/models/[^/]+/upgrade", 422, None),
    "an upgrade to the Ada the model runs": ("POST", r"/v1/models/[^/]+/upgrade", 409, None),
    "a decision": ("POST", r"/v1/decide", 200, lambda b: "facts" in b),
    "a decision that asks a person": ("POST", r"/v1/decide", 200, lambda b: b.get("ask") is True),
    "a decision of several outputs": ("POST", r"/v1/decide", 200, lambda b: "outputs" in b),
    "an import, waiting for its file": ("POST", r"/v1/models/[^/]+/imports", 202, None),
    "the import's file, sent to its upload link": ("PUT", r"/v1/uploads/.+", 202, None),
    "an import, done": ("GET", r"/v1/jobs/.+", 200, lambda b: b["kind"] == "import" and b["state"] == "done"),
    "a backtest, done": ("GET", r"/v1/jobs/.+", 200, _plain_backtest),
    "a settings change, live at once": ("PATCH", r"/v1/models/[^/]+/settings", 200, lambda b: b["job"] is None),
    "an export, done, with its download link": ("GET", r"/v1/jobs/.+", 200, lambda b: b["kind"] == "export" and b["state"] == "done"),
    "the org's usage": ("GET", r"/v1/usage", 200, lambda b: b["models"] > 0),  # the first org's, not the full one's
    "a query through POST /v1/runs, as SDK 3.0 calls it": ("POST", r"/v1/runs", 200, lambda b: b["function"] == "query"),
    "a wrong key": ("POST", r"/v1/decide", 401, None),
    "a model that is not there": ("GET", r"/v1/models/nope", 404, None),
    "a spec that reads a role another way": ("PUT", r"/v1/models/[^/]+/spec", 422, None),
    "another import open on the model": ("POST", r"/v1/models/[^/]+/imports", 409, None),
    "past the plan's calls a second": ("POST", r"/v1/decide", 429, None),
    "past the plan's month of requests": ("POST", r"/v1/decide", 403, lambda b: b["error"].get("reason") == "requests"),
}
# Refusals a local run cannot reach cheaply: past the plan's precedents (Free's 1,000), and a model over 100,000; and
# what only a registry with a deprecated, retired or closed Ada (or a kernel the deploy lacks) answers.
NOT_LIVE = {
    "cases past the plan's precedents",
    "a big model asked with few of its roles",
    "a model on a deprecated Ada",
    "a decision just after its model was moved off a retired Ada",
    "a retired Ada",
    "a deprecated Ada as an upgrade's target",
    "a beta closed to new models",
    "an Ada this deploy does not have",
}


@pytest.mark.parametrize("fixture", FIXTURES["cases"], ids=lambda c: c["name"])
def test_each_fixture_is_what_the_server_answers(flow: Dict[str, Any], fixture: Dict[str, Any]) -> None:
    name = fixture["name"]
    if name in NOT_LIVE:
        pytest.skip("not reached by a local run")
    method, path, status, where = LIVE[name]
    assert (fixture["request"]["method"], fixture["response"]["status"]) == (method, status)
    live, sent, at, headers = flow["rec"].last(method, path, status, where)
    body = fixture["response"]["body"]
    if status == 429:  # when to ask again, as the header and as the body say
        assert "retry-after" in headers and "retry-after" in fixture["response"].get("headers", {})
        assert float(headers["retry-after"]) == live["error"]["retry_after"] >= 1
    for header, value in fixture["response"].get("headers", {}).items():  # the headers the fixture shows, live too
        assert header in headers, (name, header, headers)
        if header == "glyphh-contract":
            assert headers[header] == value
    if fixture["schema"]:
        validate(live, CONTRACT[fixture["schema"]])
        validate(body, CONTRACT[fixture["schema"]])
    if fixture.get("data_schema"):
        validate(live["data"], CONTRACT[fixture["data_schema"]])
    if fixture.get("result_schema"):
        validate(live["result"], CONTRACT[fixture["result_schema"]])
        validate(body["result"], CONTRACT[fixture["result_schema"]])
    if status >= 400:
        assert live["error"]["code"] == body["error"]["code"]
        assert set(live["error"]) == set(body["error"])
    else:
        assert set(live) == set(body), (sorted(live), sorted(body))
    dump = os.environ.get("ADA_LIVE_DIR")  # the live exchange, to refresh the fixture from
    if dump:
        exchange = {"path": at, "request": sent, "response": live, "headers": headers}
        Path(dump, re.sub(r"\W+", "_", name) + ".json").write_text(json.dumps(exchange, indent=1))
