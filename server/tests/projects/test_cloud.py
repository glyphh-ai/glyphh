"""A project on Glyphh cloud (docs/specs/bots.md, 10): no code runs there, so a turn is the bot's Claude step with the
repo's files as tools through GitHub's API (faked: tests/projects/helpers.py), its changes one commit and a pull
request; the orchestrator's pick is Claude reading the repo; pull requests are merged and closed by the server; review
at the end is one pull request of the whole run. The meter lets each request in and charges it."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Unavailable
from glyphh_server.models import LlmUsageDay, ProjectRun
from glyphh_server.ops.bots.runs import machine
from glyphh_server.ops.projects import claude as claude_mod
from glyphh_server.ops.projects import cloud
from tests.bots.conftest import BOTS, Served, serve
from tests.bots.fakes import FakePipedream
from tests.projects.helpers import (
    REPO,
    FakeClaude,
    FakeRepo,
    answer,
    crew,
    faked,
    lead,
    project,
    run_of,
    say,
    start,
    use,
)


@pytest.fixture(name="s")
async def served_fixture(engine: AsyncEngine) -> AsyncIterator[Served]:
    async for s in serve(BOTS, FakePipedream()):
        yield s


async def _set(s: Served, engine: AsyncEngine, **over: Any) -> tuple[Any, FakeRepo, FakeClaude]:
    repo, claude = faked(s)
    ada, bots = await crew(s, engine)
    await project(s, ada, bots, **over)
    return ada, repo, claude


async def test_a_turn_on_glyphh_cloud_reads_and_changes_files_and_opens_a_pull_request(
    s: Served, engine: AsyncEngine
) -> None:
    ada, repo, claude = await _set(s, engine, instructions="Ship a landing page.")
    claude.then(
        [say("Let me look."), use("list_files"), use("read_file", path="docs/a.md")],
        [
            use("write_file", path="index.html", content="<h1>Hi</h1>\n<p>Welcome</p>\n"),
            use("delete_file", path="README.md"),
        ],
        use("write_file", path="docs/a.md", content="one\n2\nthree\n"),
        say("I made the home page. Next, tests."),
    )
    run = (await start(s, ada, "")).json()
    assert (run["status"], run["runs_on"], run["turns"][0]["status"]) == ("running", None, "running")
    waiting = await run_of(s, ada, run["id"])
    turn = waiting["turns"][0]
    assert (waiting["status"], turn["status"], turn["bot_slug"]) == ("needs_input", "open", "ada-cat")
    assert turn["said"] == "I made the home page. Next, tests." and turn["title"] == "Ada Cat: I made the home page."
    assert (turn["pr_url"], turn["number"], turn["head_sha"]) == (f"{REPO}/pull/1", 1, f"c-{turn['branch']}")
    assert turn["files"] == [
        {"path": "README.md", "added": 0, "removed": 1},
        {"path": "docs/a.md", "added": 2, "removed": 1},
        {"path": "index.html", "added": 2, "removed": 0},
    ]
    assert (turn["input_tokens"], turn["output_tokens"], turn["cost_micros"]) == (4000, 800, 32_000)
    asked = claude.asked[0]
    assert asked["tools"] == ["list_files", "read_file", "write_file", "delete_file"]
    assert asked["system"].startswith("You are Ada Cat (they/them)") and "working folder" not in asked["system"]
    prompt = asked["messages"][0]["content"]
    assert (
        prompt.startswith("PROJECT INSTRUCTIONS:\nShip a landing page.") and "through your tools: list_files" in prompt
    )
    assert claude.results()[:2] == ["README.md\ndocs/a.md", "one\ntwo\n"]
    assert claude.keys == [("sk-ant-glyphh-test-key", "claude-opus-5-5")]
    assert repo.files[turn["branch"]] == {"docs/a.md": "one\n2\nthree\n", "index.html": "<h1>Hi</h1>\n<p>Welcome</p>\n"}
    assert ("commit", turn["branch"], "Ada Cat: I made the home page.", "Ada Cat") in repo.asked
    assert repo.pulls[1] | {"body": ""} == {
        "head": turn["branch"],
        "base": "main",
        "title": turn["title"],
        "body": "",
        "state": "open",
    }
    async with engine.begin() as conn:  # every request to Claude went through the meter
        used = (await conn.execute(select(LlmUsageDay).where(LlmUsageDay.org_id == ada.org_id))).one()
    assert (used.requests, used.input_tokens, used.output_tokens) == (4, 4000, 800)
    claude.then(say("Nothing for me yet.\nPASS"), say("All good.\nDONE"))
    res = await answer(s, ada, run["id"], "merge")
    assert res.status_code == 202 and res.json()["turns"][0]["status"] == "merged"
    ended = await run_of(s, ada, run["id"])
    assert (ended["status"], ended["ended"], ended["error"]) == ("done", "done", "")
    assert [(t["bot_slug"], t["status"], t["done"]) for t in ended["turns"]] == [
        ("ada-cat", "merged", False),
        ("bo-cat", "unchanged", False),
        ("ada-cat", "unchanged", True),
    ]
    assert repo.files["main"]["index.html"].startswith("<h1>") and turn["branch"] not in repo.files
    assert "Ada Cat: I made the home page. Next, tests." in claude.asked[-1]["messages"][0]["content"]


async def test_a_turns_tools_say_what_went_wrong_and_claude_goes_on(
    s: Served, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    ada, repo, claude = await _set(s, engine, max_turns=1)
    monkeypatch.setattr(cloud, "FILES_MAX", 1)
    monkeypatch.setattr(cloud, "FILE_MAX", 20)
    monkeypatch.setattr(cloud, "LISTED", 1)
    claude.then(
        [use("read_file", path="../secrets"), use("read_file", path="nope.md"), use("delete_file", path="nope.md")],
        [
            use("run_tests"),
            use("write_file", path=".git/config", content="x"),
            use("write_file", path="a.md", content="y" * 30),
        ],
        [use("write_file", path="README.md", content="# Site\n"), use("write_file", path="b.md", content="b")],
        [use("list_files", under="docs/"), use("list_files"), use("delete_file", path="README.md")],
        [
            use("list_files", under="none"),
            use("write_file", path="README.md", content="# Site\n"),
            use("read_file", path="README.md"),
        ],
        say("I only looked around."),
    )
    run = (await start(s, ada)).json()
    ended = await run_of(s, ada, run["id"])
    assert (ended["error"], ended["status"], ended["ended"]) == ("", "done", "max_turns")
    assert ended["turns"][0]["status"] == "unchanged"
    assert ended["turns"][0]["files"] == [] and repo.pulls == {}  # a file written back as it was is no change
    assert claude.results() == [
        "Error: '../secrets' is not a file's path from the repo's root.",
        "There is no such file.",
        "There is no such file.",
        "Error: there is no tool run_tests here.",
        "Error: '.git/config' is not a file's path from the repo's root.",
        "Error: A file here is at most 0 kB.",
        "Wrote README.md.",
        "Error: A turn on Glyphh cloud changes at most 1 files.",
        "docs/a.md",
        "README.md\n(and 1 more: list a folder)",
        "Deleted README.md.",
        "(no files)",
        "Wrote README.md.",
        "# Site\n",
    ]


async def test_a_pull_request_on_glyphh_cloud_is_rejected_or_conflicts(s: Served, engine: AsyncEngine) -> None:
    ada, repo, claude = await _set(s, engine, max_turns=2)
    claude.then(use("write_file", path="a.md", content="a"), say("Wrote a."))
    run = (await start(s, ada)).json()
    await run_of(s, ada, run["id"])
    repo.fail = "close"
    res = await answer(s, ada, run["id"], "reject")
    assert res.status_code == 503 and res.json()["error"]["reason"] == "github"  # it still waits
    repo.fail = ""
    claude.then(use("write_file", path="b.md", content="b"), say("Wrote b."))
    res = await answer(s, ada, run["id"], "reject")
    assert (
        res.status_code == 202 and res.json()["turns"][0]["status"] == "rejected" and repo.pulls[1]["state"] == "closed"
    )
    waiting = await run_of(s, ada, run["id"])
    assert waiting["status"] == "needs_input" and waiting["turns"][1]["bot_slug"] == "bo-cat"
    repo.mergeable = False
    ended = (await answer(s, ada, run["id"], "merge")).json()
    assert (ended["status"], ended["ended"]) == ("done", "max_turns")
    assert (ended["turns"][1]["status"], ended["turns"][1]["error"]) == ("conflict", "Pull Request is not mergeable")
    assert ended["turns"][1]["branch"] in repo.files  # a conflict's branch stays, its pull request open


async def test_an_orchestrator_on_glyphh_cloud_reads_the_repo_and_says_why(s: Served, engine: AsyncEngine) -> None:
    ada, _, claude = await _set(s, engine, turn_mode="orchestrator")
    await lead(s, ada, name="Maestro", instructions="Pick whoever is behind.", model="claude-sonnet-5-5")
    claude.then(
        use("read_file", path="README.md"),
        say('{"next": "bo-cat", "why": "The README needs a quick start.", "done": false}'),
        use("write_file", path="README.md", content="# Site\n\nRun it.\n"),
        say("Added a quick start."),
    )
    run = (await start(s, ada)).json()
    assert run["turns"][0]["status"] == "picking"
    waiting = await run_of(s, ada, run["id"])
    turn = waiting["turns"][0]
    assert (turn["bot_slug"], turn["picked_by"], turn["why"]) == (
        "bo-cat",
        "orchestrator",
        "The README needs a quick start.",
    )
    assert (turn["status"], turn["input_tokens"]) == ("open", 4000) and len(waiting["turns"]) == 1
    pick = claude.asked[0]
    assert pick["tools"] == ["list_files", "read_file"]
    # the org's orchestrator bot picks: in its own words, on its model (the bot's turn is on the bot's)
    assert pick["system"].startswith("You are Maestro (they/them)") and "Pick whoever is behind." in pick["system"]
    assert [model for _, model in claude.keys] == ["claude-sonnet-5-5", "claude-opus-5-5"]
    assert "through your tools (list_files, read_file)" in pick["messages"][0]["content"]
    assert "The orchestrator chose you: The README needs a quick start." in claude.asked[2]["messages"][0]["content"]
    claude.then(say('{"next": null, "why": "The README is complete.", "done": true}'))
    await answer(s, ada, run["id"], "merge")
    ended = await run_of(s, ada, run["id"])
    assert (ended["status"], ended["ended"]) == ("done", "orchestrator")
    last = ended["turns"][-1]
    assert (last["bot_name"], last["status"], last["said"], last["done"]) == (
        "Orchestrator",
        "unchanged",
        "The README is complete.",
        True,
    )


async def test_review_at_the_end_on_glyphh_cloud(s: Served, engine: AsyncEngine) -> None:
    ada, repo, claude = await _set(s, engine, review="end", max_turns=1)
    claude.then(use("write_file", path="a.md", content="a"), say("Wrote a."))
    run = (await start(s, ada, "Add a page\nand more")).json()
    work = run["work_branch"]
    waiting = await run_of(s, ada, run["id"])
    assert (waiting["status"], waiting["ended"], waiting["turns"][0]["status"]) == (
        "needs_input",
        "max_turns",
        "merged",
    )
    assert repo.pulls[1]["base"] == work and repo.pulls[1]["state"] == "merged"
    assert repo.pulls[2] | {"body": ""} == {
        "head": work,
        "base": "main",
        "title": "Site crew: Add a page",
        "body": "",
        "state": "open",
    }
    assert (waiting["pr_url"], waiting["number"]) == (f"{REPO}/pull/2", 2) and "a.md" not in repo.files["main"]
    res = await answer(s, ada, run["id"], "reject")
    assert (res.json()["status"], res.json()["error"]) == ("failed", "The run's pull request was rejected.")
    assert repo.pulls[2]["state"] == "closed" and work not in repo.files
    claude.then(use("write_file", path="a.md", content="a"), say("Wrote a."))
    run = (await start(s, ada)).json()
    await run_of(s, ada, run["id"])
    repo.mergeable = False
    res = await answer(s, ada, run["id"], "merge")
    assert res.json()["status"] == "failed" and res.json()["error"] == (
        "The run's pull request did not merge: Pull Request is not mergeable. It stays open."
    )
    repo.mergeable = True
    claude.then(say("Nothing to do.\nPASS"))
    run = (await start(s, ada)).json()
    ended = await run_of(s, ada, run["id"])  # nothing merged: no pull request, the run's branch dropped
    assert (ended["status"], ended["ended"], ended["pr_url"]) == ("done", "max_turns", None)
    assert ("drop", ended["work_branch"]) in repo.asked


async def test_review_at_the_end_says_when_github_refuses(s: Served, engine: AsyncEngine) -> None:
    ada, repo, claude = await _set(s, engine, review="end", max_turns=1)
    repo.fail = "branch"
    run = (await start(s, ada)).json()
    assert (run["status"], run["error"], run["turns"]) == ("failed", "GitHub did not branch (500)", [])
    repo.fail, repo.first = "open", 1  # the turn's own pull request opens; the run's does not
    claude.then(use("write_file", path="a.md", content="a"), say("Wrote a."))
    run = (await start(s, ada)).json()
    ended = await run_of(s, ada, run["id"])
    assert (ended["status"], ended["error"]) == ("failed", "GitHub did not open (500)")


async def test_a_step_on_glyphh_cloud_that_fails_ends_the_run_saying_why(
    s: Served, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    ada, _, claude = await _set(s, engine)
    claude.then(Unavailable("Claude did not answer: overloaded", reason="claude"))
    run = (await start(s, ada)).json()
    ended = await run_of(s, ada, run["id"])
    assert (
        ended["status"] == "failed" and ended["error"] == "Ada Cat's turn 1 failed: Claude did not answer: overloaded"
    )
    assert ended["turns"][0]["status"] == "failed"
    claude.then(RuntimeError("boom"))
    run = (await start(s, ada)).json()
    assert (await run_of(s, ada, run["id"]))["error"] == "Ada Cat's turn 1 failed: RuntimeError: boom"
    monkeypatch.setattr(claude_mod, "ROUNDS", 1)
    claude.then(use("list_files"))
    run = (await start(s, ada)).json()
    assert "did not end within 1 requests to Claude" in (await run_of(s, ada, run["id"]))["error"]
    await s.app.state.bots.projects.took(ada.org_id, uuid.uuid4(), {})  # a turn ended meanwhile: nothing to keep


async def test_a_run_on_glyphh_cloud_is_cancelled_or_cut_off_by_a_restart(s: Served, engine: AsyncEngine) -> None:
    ada, _, claude = await _set(s, engine)
    projects = s.app.state.bots.projects
    held = asyncio.Event()

    async def slow(*_: Any) -> Any:
        await held.wait()

    claude.create = slow  # type: ignore[method-assign]
    run = (await start(s, ada)).json()
    await asyncio.sleep(0.01)
    res = await s.http.post(f"/v1/project-runs/{run['id']}/cancel", headers=ada.headers)
    assert (res.json()["status"], res.json()["error"], res.json()["turns"][0]["status"]) == (
        "failed",
        "cancelled",
        "cancelled",
    )
    await projects.wait()
    assert projects.tasks == {}
    run = (await start(s, ada)).json()
    await asyncio.sleep(0.01)
    await projects.close()  # the server stops; at its next start its runs on Glyphh cloud are failed
    assert await s.app.state.bots.recover() == 1
    cut = await run_of(s, ada, run["id"])
    assert (cut["status"], cut["error"], cut["turns"][0]["status"]) == ("failed", "interrupted by a restart", "failed")
    async with engine.begin() as conn:
        kept = (await conn.execute(select(ProjectRun.machine).where(ProjectRun.id == uuid.UUID(run["id"])))).scalar()
    assert kept == machine()


async def test_a_project_on_glyphh_cloud_needs_an_anthropic_key(engine: AsyncEngine) -> None:
    async for s in serve(BOTS.model_copy(update={"anthropic_api_key": ""}), FakePipedream()):
        ada, _, claude = await _set(s, engine)
        res = await start(s, ada)
        assert res.status_code == 503 and res.json()["error"]["reason"] == "anthropic_off"
        own = "sk-ant-own-key-0123456789"
        assert (await s.http.put("/v1/bot-key", json={"key": own}, headers=ada.headers)).status_code == 200
        claude.then(say("PASS"), say("PASS"))
        run = (await start(s, ada)).json()
        assert (await run_of(s, ada, run["id"]))["status"] == "done" and claude.keys[0][0] == own
        await s.http.delete("/v1/bot-key", headers=ada.headers)  # the key gone while a run is live: a step says so
        with pytest.raises(Unavailable, match="Anthropic API key"):
            await s.app.state.bots.projects.claude_of(ada.org_id, "claude-opus-5-5")
