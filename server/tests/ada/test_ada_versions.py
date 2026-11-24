"""Ada versions (docs/specs/ada-cloud.md, 12): the registry and its support policy; models made on, moved to and rolled
back from a version, each answered by its own kernel's workers (here, workers of the venv's kernel run under the
beta's name: what is proved is that each message, job and backtest candidate reaches its kernel's workers); the
headers; the move off a retired version; the connector's tools."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import pg, registry, retirement
from glyphh_ada.errors import Refusal
from glyphh_ada.process import Worker, work
from glyphh_ada.protocol import JOBS, Message
from tests.ada.conftest import ADA, BETA_KERNEL, SHAPES, a_model, an_org, cases, finished, shape
from tests.ada.mcp import signed_in, text, tool
from tests.db.helpers import person

BETA = "ada-1-2-beta"
DATA = shape(7, "r", 2)


def ver(name: str, kernel: str, released: str = "2026-10-01", **kw: Any) -> registry.Version:
    values: dict[str, Any] = {
        "commit": "c" * 40,
        "beta": name.endswith("-beta"),
        "open": True,
        "deprecated": None,
        "ends": None,
        "changes_answers": True,
        "store_format": 1,
        "aliases": (),
        "summary": f"{name} in a line.",
        "notes": f"What {name} changes.",
    } | kw
    return registry.Version(name=name, kernel=kernel, released=date.fromisoformat(released), **values)


def use(monkeypatch: pytest.MonkeyPatch, reg: registry.Registry, day: date) -> None:
    monkeypatch.setattr(registry, "registry", lambda: reg)
    monkeypatch.setattr(registry, "today", lambda: day)


def test_the_registry_as_shipped() -> None:
    reg, day = registry.load(), registry.today()
    assert reg.latest(day).name == "ada-1-0" and reg.kernels() == ["3.17.0", "3.13.0", "3.12.2"]
    assert reg.kernel_of(BETA) == "3.17.0" and reg.kernel_of("ada-0-9") == ""
    assert reg.choose(None, day).name == "ada-1-0" and reg.choose(BETA, day).beta
    shown = reg.view(reg.find(BETA), day)  # type: ignore[arg-type]
    assert shown["status"] == "beta" and shown["kernel"] == "3.17.0" and "drift" in shown["summary"]
    superseded = reg.find("ada-1-1-beta")  # a beta superseded by another: deprecated that day, ends 30 days on
    assert superseded is not None and superseded.ends == superseded.deprecated + timedelta(days=30)  # type: ignore[operator]


def test_a_list_that_breaks_the_support_policy_is_refused() -> None:
    wrong = [
        ver("ada-2", "4.0.0"),
        ver("ada-1-3", "3.15.0", beta=True),
        ver("ada-1-2", "3.14.0", deprecated=date(2026, 1, 1), store_format=2),
        ver("ada-1-1-beta", "3.13.0", aliases=("ada-1-2",)),
    ]
    with pytest.raises(ValueError) as e:
        registry.Registry(wrong)
    for problem in (
        "ada-2: not a name",
        "ada-1-2: named twice",
        "ada-1-3: a beta's name",
        "ada-1-2: deprecated without an end",
        "more than 3 kernels",
        "different store formats",
    ):
        assert problem in str(e.value)
    with pytest.raises(ValueError, match="no stable"):
        registry.Registry([ver("ada-1-1-beta", "3.13.0")])


def test_status_choice_and_notices_follow_the_dates() -> None:
    old = ver("ada-1-0", "3.12.2", deprecated=date(2027, 1, 1), ends=date(2027, 7, 1), aliases=("ada-0-9",))
    closed = ver("ada-1-2-beta", "3.14.0", open=False)
    reg = registry.Registry([closed, ver("ada-1-1", "3.13.0", aliases=("ada-1-1-beta",)), old])
    now, later, gone = date(2026, 11, 1), date(2027, 2, 1), date(2027, 8, 1)
    assert [old.status(d) for d in (now, later, gone)] == ["stable", "deprecated", "retired"]
    assert reg.find("ada-1-1-beta") is reg.find("ada-1-1") and reg.choose("ada-0-9", now) is old
    for name, day, code in (
        ("ada-9-9", now, "E_ADA_UNKNOWN"),
        ("ada-1-0", later, "E_ADA_DEPRECATED"),
        ("ada-1-0", gone, "E_ADA_RETIRED"),
        ("ada-1-2-beta", now, "E_ADA_BETA"),
    ):
        with pytest.raises(Refusal) as e:
            reg.choose(name, day)
        assert (e.value.code, e.value.detail["latest"]) == (code, "ada-1-1")
    moved_at = datetime(2027, 7, 20, tzinfo=UTC)
    assert reg.notice("ada-1-1", registry.MOVED_BY, moved_at, gone)["kind"] == "moved"  # type: ignore[index]
    assert reg.notice("ada-1-1", registry.MOVED_BY, moved_at, gone + timedelta(days=60)) is None
    assert reg.notice("ada-1-0", "me", None, gone) == {
        "kind": "retired",
        "message": "ada-1-0 was retired on 2027-07-01: this model is being moved to ada-1-1.",
        "to": "ada-1-1",
        "ends": "2027-07-01",
    }
    assert reg.notice("ada-1-0", "me", None, later)["kind"] == "deprecated"  # type: ignore[index]
    assert reg.notice("ada-1-0", "me", None, now)["to"] == "ada-1-1"  # type: ignore[index]  # a newer stable
    assert reg.notice("ada-9-9", "me", None, now) is None
    shipped = registry.load()
    assert shipped.notice("ada-1-0", "me", None, now)["kind"] == "beta"  # type: ignore[index]
    assert shipped.notice(BETA, "me", None, now) is None  # the newest: nothing to tell
    unopened = registry.Registry([ver(BETA, BETA_KERNEL, installed=False), ver("ada-1-0", "3.12.2")])
    with pytest.raises(Refusal, match="not running here"):
        unopened.choose(BETA, now)
    assert unopened.kernels() == ["3.12.2"]


async def test_models_on_two_versions_side_by_side_upgraded_and_rolled_back(
    engine: AsyncEngine,
    ada: httpx.AsyncClient,
    worker: Worker,
    jobs_worker: Worker,
    beta_worker: Worker,
    beta_jobs_worker: Worker,
) -> None:
    _who, key = await an_org(engine, ada)
    made = await a_model(ada, key, n=60)
    assert made["ada"] == "ada-1-0" and made["ada_status"] == "stable" and made["ada_notice"]["kind"] == "beta"
    beta = await ada.post("/v1/models", json={"name": "trial", "spec": made["spec"], "ada": BETA}, headers=key)
    assert beta.status_code == 201 and beta.json()["ada"] == BETA and beta.json()["ada_notice"] is None
    assert (await ada.post("/v1/models/trial/record_many", json={"cases": cases(5)}, headers=key)).status_code == 200
    unknown = await ada.post("/v1/models", json={"name": "x", "spec": made["spec"], "ada": "ada-9-9"}, headers=key)
    assert unknown.status_code == 422 and unknown.json()["error"]["latest"] == "ada-1-0"
    decided = await ada.post("/v1/decide", json={"model": "shapes", "data": DATA}, headers=key)
    assert decided.json()["ada"] == "ada-1-0" and decided.headers["glyphh-ada"] == "ada-1-0"
    assert decided.headers["glyphh-contract"] == str(registry.CONTRACT) and "glyphh-ada-notice" not in decided.headers
    assert worker.redis.xlen(f"ada:sync:{BETA_KERNEL}") >= 2  # the beta model's calls went to its kernel's workers
    listed = (await ada.get("/v1/ada", headers=key)).json()
    assert listed["latest_stable"] == "ada-1-0" and listed["contract"] == registry.CONTRACT
    assert {v["name"]: v["models"] for v in listed["versions"]} == {BETA: 1, "ada-1-1-beta": 0, "ada-1-0": 1}
    usage = (await ada.get("/v1/usage", headers=key)).json()
    assert usage["ada"]["versions"] == listed["versions"]

    # Backtest against the beta first: each candidate scored by its own kernel's job worker, on the same split
    body = {"ada": BETA, "candidates": [{"settings": {"k": 5}}, {"ada": "ada-9-9"}], "holdout": {"newest": 20}}
    tried = await finished(ada, key, (await ada.post("/v1/models/shapes/backtest", json=body, headers=key)).json())
    result = tried["result"]
    assert tried["state"] == "done" and result["ada"] == "ada-1-0" and result["active"]["ada"] == "ada-1-0"
    k5, bad, on_beta = result["candidates"]
    assert k5["ada"] == "ada-1-0" and on_beta["ada"] == BETA and on_beta["n"] == result["active"]["n"] == 20
    assert "accuracy" in on_beta["change"] and bad["error"]["code"] == "E_ADA_UNKNOWN"

    # Upgrade: a new version on the beta, re-encoded, learned and calibrated by its kernel, live after the job
    up = await ada.post("/v1/models/shapes/upgrade", json={"ada": BETA, "backtest": tried["id"]}, headers=key)
    assert up.status_code == 202, up.text
    moved = up.json()
    assert (moved["version"], moved["active"], moved["ada"], moved["from"]) == (2, False, BETA, "ada-1-0")
    assert (await finished(ada, key, moved["job"]))["state"] == "done"
    now = (await ada.get("/v1/models/shapes", headers=key)).json()
    assert (now["version"], now["ada"], now["precedents"]) == (2, BETA, 60)
    history = (await ada.get("/v1/models/shapes/versions", headers=key)).json()["versions"]
    assert [(v["ada"], v["kernel"], v["active"]) for v in history] == [
        ("ada-1-0", "3.12.2", False),
        (BETA, BETA_KERNEL, True),
    ]
    eleven = {"ada": BETA, "candidates": [{"settings": {"k": k}} for k in range(1, 11)]}
    assert (await ada.post("/v1/models/shapes/backtest", json=eleven, headers=key)).status_code == 422
    again = await ada.post("/v1/models/shapes/upgrade", json={"ada": BETA}, headers=key)
    assert again.status_code == 409 and again.json()["error"]["latest"] == "ada-1-0"
    asked = await ada.post("/v1/models/shapes/decide", json={"data": DATA}, headers=key)
    assert asked.status_code == 200 and asked.headers["glyphh-ada"] == BETA

    # Roll back: version 1 again, on its own kernel and store, brought up to date by a job
    back = (await ada.post("/v1/models/shapes/versions/1/activate", headers=key)).json()
    assert back["active"] is False and (await finished(ada, key, back["job"]))["state"] == "done"
    assert (await ada.get("/v1/models/shapes", headers=key)).json()["ada"] == "ada-1-0"


@pytest.fixture
def retiring(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[date]]:
    """A registry where ada-1-1 (the beta's kernel) is the latest stable and ada-1-0 was deprecated 30 days ago and
    ends today; the day starts 100 days ago and moves when the test says so. Its workers are made after it: the beta's
    kernel's are the front door's."""
    end = registry.today()
    old = ver("ada-1-0", "3.12.2", deprecated=end - timedelta(days=30), ends=end)
    reg = registry.Registry([ver("ada-1-1", BETA_KERNEL), old])
    day = [end - timedelta(days=100)]
    monkeypatch.setattr(registry, "registry", lambda: reg)
    monkeypatch.setattr(registry, "today", lambda: day[0])
    yield day


async def test_a_retired_versions_models_are_moved_and_never_left_unanswerable(
    retiring: list[date],
    engine: AsyncEngine,
    ada: httpx.AsyncClient,
    worker: Worker,
    jobs_worker: Worker,
    beta_worker: Worker,
    beta_jobs_worker: Worker,
) -> None:
    _who, key = await an_org(engine, ada)
    spec = (await a_model(ada, key, "fresh"))["spec"]
    assert (await ada.get("/v1/models/fresh", headers=key)).json()["ada"] == "ada-1-1"  # the latest stable
    made = await ada.post("/v1/models", json={"name": "shapes", "spec": spec, "ada": "ada-1-0"}, headers=key)
    assert made.status_code == 201 and made.json()["ada_notice"]["kind"] == "upgrade"
    await ada.post("/v1/models/shapes/record_many", json={"cases": cases(30)}, headers=key)
    await ada.post("/v1/models", json={"name": "held", "spec": spec, "ada": "ada-1-0"}, headers=key)
    await ada.post("/v1/models/held/imports", json={"format": "jsonl"}, headers=key)  # waiting for its file: busy

    end = retiring[0] + timedelta(days=100)
    retiring[0] = end - timedelta(days=10)
    deprecated = await ada.get("/v1/models/shapes", headers=key)
    assert (
        deprecated.headers["glyphh-ada-notice"]
        == f"deprecated: ada-1-0 is deprecated and ends on {end}: upgrade to ada-1-1."
    )
    late = await ada.post("/v1/models", json={"name": "late", "spec": spec, "ada": "ada-1-0"}, headers=key)
    assert late.json()["error"]["code"] == "E_ADA_DEPRECATED"

    retiring[0] = end
    still = await ada.post("/v1/models/shapes/decide", json={"data": DATA}, headers=key)  # still answered, by 3.12.2
    assert still.status_code == 200 and still.headers["glyphh-ada-notice"].startswith("retired: ")
    idle = Worker(ADA, JOBS, BETA_KERNEL)
    assert idle.sweep() >= 1 and idle.sweep() == 0  # every org's models on ada-1-0 (other tests' too); not due again
    assert Worker(ADA, JOBS).sweep() == 0  # only the latest stable's job workers sweep
    for _ in range(600):  # the move's job, on the latest stable's kernel
        found = (await ada.get("/v1/models/shapes", headers=key)).json()
        if found["ada"] == "ada-1-1":
            break
        await asyncio.sleep(0.1)
    assert found["ada_notice"]["kind"] == "moved" and found["version"] == 2, found
    versions = (await ada.get("/v1/models/shapes/versions", headers=key)).json()["versions"]
    assert (
        versions[1]["note"] == "Moved from ada-1-0 (retired) to ada-1-1" and versions[1]["made_by"] == "ada-retirement"
    )
    told = await ada.post("/v1/models/shapes/query", json={"data": DATA}, headers=key)
    assert told.headers["glyphh-ada-notice"].startswith("moved: Moved to ada-1-1")
    back = await ada.post("/v1/models/shapes/versions/1/activate", headers=key)
    assert back.status_code == 410 and back.json()["error"]["code"] == "E_ADA_RETIRED"
    gone = await ada.post("/v1/models/shapes/backtest", json={"ada": "ada-1-0"}, headers=key)
    tried = await finished(ada, key, gone.json())
    assert tried["result"]["candidates"][0]["error"]["code"] == "E_ADA_RETIRED"
    retirement.sweep(idle.ctx)
    held = (await ada.get("/v1/models/held", headers=key)).json()
    assert held["ada"] == "ada-1-0" and held["ada_notice"]["kind"] == "retired"  # its import is open: a later sweep
    idle.ctx.conn.close()


async def test_a_kernel_this_deploy_does_not_run_is_refused_not_answered_by_another(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key, n=30)
    up = (await ada.post("/v1/models/shapes/upgrade", json={"ada": BETA}, headers=key)).json()
    beta = ver(BETA, BETA_KERNEL, installed=False)
    use(monkeypatch, registry.Registry([beta, ver("ada-1-0", "3.12.2")]), registry.today())
    idle = Worker(ADA, JOBS)
    work(idle.ctx, Message(str(who.org_id), "shapes", "reencode", {"job": up["job"]["id"]}), idle)
    failed = (await ada.get(f"/v1/jobs/{up['job']['id']}", headers=key)).json()
    assert failed["state"] == "failed" and failed["error"]["code"] == "E_ADA_UNAVAILABLE"
    tried = (await ada.post("/v1/models/shapes/backtest", json={"ada": BETA}, headers=key)).json()
    work(idle.ctx, Message(str(who.org_id), "shapes", "backtest", {"job": tried["id"]}), idle)
    scored = (await ada.get(f"/v1/jobs/{tried['id']}", headers=key)).json()
    assert scored["result"]["candidates"][0]["error"]["code"] == "E_ADA_UNAVAILABLE"
    schema = pg.enter(idle.ctx.conn, str(who.org_id))
    idle.ctx.conn.execute(f'UPDATE "{schema}".spec_versions SET ada = %s', (BETA,))  # a model pinned to it anyway
    refused = await ada.post("/v1/models/shapes/decide", json={"data": DATA}, headers=key)
    assert refused.status_code == 503 and refused.json()["error"]["code"] == "E_ADA_UNAVAILABLE"
    idle.ctx.conn.close()


async def test_the_connector_lists_versions_and_upgrades(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker, beta_jobs_worker: Worker
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    await tool(ada, auth, "ada_model_create", name="shapes", spec=SHAPES, ada="ada-1-0")
    listed = await tool(ada, auth, "ada_releases")
    assert text(listed).startswith("The latest stable is ada-1-0") and "ada-1-2-beta: beta, released" in text(listed)
    # deprecated until its end date, retired from it: the shipped list's own dates say which it is today
    old = registry.registry().find("ada-1-1-beta")
    assert old is not None and old.status(registry.today()) in ("deprecated", "retired")
    assert f"ada-1-1-beta: {old.status(registry.today())} (ends 2026-11-24), released" in text(listed)
    moved = await tool(ada, auth, "ada_upgrade", name="shapes", ada=BETA, note="try the beta")
    assert text(moved).startswith(f"Version 2 of shapes on {BETA} (from ada-1-0) is being made by job ")
