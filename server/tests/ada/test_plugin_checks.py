"""The Resume Screener plugin's checks (glyphh-ai/plugins, plugins/resume-screener/checks) run on this suite's real
Ada. Skipped unless GLYPHH_PLUGIN (the plugin's folder) and GLYPHH_CHECK (which check) are set; GLYPHH_CORPUS is the
applicant corpus for the checks that read it. What it measured is written to GLYPHH_CHECK_OUT.

Two more runs are not the plugin's own checks but the plugin itself, end to end, on this suite's Ada:
- GLYPHH_CHECK=sdk: the plugin's seed.py and run.py through the Glyphh SDK over real HTTP (the app served on a port
  inside this container only), as a person without the connector, and as the demo page, runs them.
- GLYPHH_CHECK=mcp: the skill's steps with every Ada call made as the connector's tool call (ada_model_create,
  ada_record_many, ada_facts, ada_decide, ada_record, screener_verdict) against this server's /mcp."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.process import Worker
from tests.ada.conftest import HOST, an_org
from tests.ada.mcp import data, signed_in, tool
from tests.db.helpers import person

PLUGIN: str = os.environ.get("GLYPHH_PLUGIN", "")
CHECK: str = os.environ.get("GLYPHH_CHECK", "")
CORPUS: str = os.environ.get("GLYPHH_CORPUS", "")
OUT: str = os.environ.get("GLYPHH_CHECK_OUT", "/tmp/plugin-check.json")
PORT: int = 8099
HOPS: bytes = (
    b"Received: from a.example by mx.example with ESMTPS id 1; Sun, 22 Nov 2026 17:43:40 +0000\r\n"
    b"Received: from me by a.example with ESMTPSA id 0; Sun, 22 Nov 2026 17:43:30 +0000\r\n"
)
pytestmark = pytest.mark.skipif(not (PLUGIN and CHECK), reason="the plugin's checks are run by hand")


def _done(result: Any) -> None:
    print(json.dumps(result, indent=1), flush=True)
    Path(OUT).write_text(json.dumps(result, indent=1))


async def test_a_plugin_check(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker) -> None:
    if CHECK in ("sdk", "mcp"):
        pytest.skip("run by the tests below")
    sys.path[:0] = [f"{PLUGIN}/skills/screen-application/scripts", f"{PLUGIN}/checks"]
    import checks

    _, key = await an_org(engine, ada)

    async def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        while True:
            got = await ada.request(method, path, json=body, headers=key)
            if got.status_code != 429:  # the plan's rate: wait as it says, ask again
                break
            await asyncio.sleep(float(got.headers.get("retry-after", "1")))
        assert got.status_code in (200, 201, 202), got.text
        return got.json()

    name, _, mode = CHECK.partition("-")
    run = {
        "carried": lambda: checks.carried_over(call, Path(CORPUS)),
        "others": lambda: checks.against_the_others(call, Path(CORPUS), mode),
        "together": lambda: checks.arriving_together(call, mode),
        "timing": lambda: checks.timing_learns(call),
    }[name]
    _done(await run())


def _fixture(name: str) -> bytes:
    return HOPS + (Path(PLUGIN) / "tests" / "fixtures" / name).read_bytes()


async def test_the_plugin_through_the_sdk(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    if CHECK != "sdk":
        pytest.skip("another check")
    import uvicorn

    sys.path[:0] = [f"{PLUGIN}/skills/screen-application/scripts"]
    import run as plugin_run
    import seed
    from glyphh import Ada
    from screener import mail

    _, key = await an_org(engine, ada)
    app = ada._transport.app  # type: ignore[attr-defined]  # the suite's app, served for real inside this container
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, lifespan="off", log_level="warning"))
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    said: list[str] = []

    def through_the_sdk() -> dict[str, Any]:
        client = Ada(url=f"http://{HOST}:{PORT}", key=key["authorization"].removeprefix("Bearer "))
        seed.setup(client, say=said.append)
        seed.setup(client, say=said.append)  # again: nothing doubles
        held = {m.name: m.get("precedents") for m in client.models()}
        first = plugin_run.screen(client, mail.read(_fixture("strong-backend.eml"), "new-1"))
        poor = plugin_run.screen(client, mail.read(_fixture("poor-backend.eml"), "new-2"), keep=True)
        again = plugin_run.screen(client, mail.read(_fixture("poor-backend.eml"), "new-3"))
        after = {m.name: m.get("precedents") for m in client.models()}
        return {"setup said": said, "held": held, "held after one kept": after, "strong fixture": first,
                "poor fixture, kept": poor, "poor fixture, screened again": again}  # fmt: skip

    try:
        _done(await asyncio.to_thread(through_the_sdk))
    finally:
        server.should_exit = True
        await serving


async def test_the_skills_steps_through_the_connector(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    if CHECK != "mcp":
        pytest.skip("another check")
    sys.path[:0] = [f"{PLUGIN}/skills/screen-application/scripts"]
    import seed
    from screener import mail, steps

    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    calls: list[str] = []

    async def called(which: str, /, **arguments: Any) -> dict[str, Any]:
        calls.append(which)
        return data(await tool(ada, auth, which, **arguments))

    have = {m["name"] for m in (await called("ada_models"))["models"]}
    for name, model in steps.models().items():  # the setup, by the connector's tools; 300 examples a model, to be quick
        full = steps.PREFIX + name
        assert full not in have
        await called("ada_model_create", name=full, spec=model["spec"] | {"name": full})
        if cases := seed.examples(name)[:300]:
            await called("ada_record_many", name=full, cases=cases)
    verdicts = {}
    for mid, fixture in (("new-1", "strong-backend.eml"), ("new-2", "poor-backend.eml")):
        made = steps.read(mail.read(_fixture(fixture), mid))  # step 1
        facts = {a["part"]: await called("ada_facts", name=steps.PREFIX + "others", data=a["data"], top=a["top"])
                 for a in steps.asks(made)}  # step 2  # fmt: skip
        app = steps.compare(made, facts)  # step 3
        cases = steps.cases(app)
        answers = {n: await called("ada_decide", name=steps.PREFIX + n, data=c) for n, c in cases.items()}  # step 4
        verdict = steps.verdict(app, answers)  # step 5
        await called("ada_record", name=steps.PREFIX + "others", data=made["others"], outcome="alone")  # step 7
        shown = await tool(ada, auth, "screener_verdict", **verdict)  # step 8
        calls.append("screener_verdict")
        verdicts[fixture] = {"verdict": verdict, "the card's text": shown["content"][0]["text"],
                             "the card got": data(shown)["person"]["verdict"]}  # fmt: skip
    _done({"calls in order": calls, "verdicts": verdicts})
