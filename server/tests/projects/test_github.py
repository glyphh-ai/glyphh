"""GitHub for the org's projects, through the Glyphh GitHub App (GitHub faked at the HTTP layer): the crew's project
for a workspace found or made, and connected only where the App is installed and the person may push; the repo
picker's reads; a turn's token, minted for its repo alone; and a run's own model and effort."""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import NotFound, Unavailable
from glyphh_server.models import GitHubInstallation
from glyphh_server.ops import github_repos
from tests.bots.conftest import BOTS, Served, serve
from tests.bots.fakes import FakePipedream
from tests.db.helpers import member
from tests.projects.helpers import (
    INSTALLATION,
    REPO,
    crew,
    faked,
    github_of,
    lead,
    project,
    run_of,
    say,
    signs_in_with_github,
    start,
)

INSTALL_URL: str = "https://github.com/apps/glyphh-test/installations/new"


@pytest.fixture(name="s")
async def served_fixture(engine: AsyncEngine) -> AsyncIterator[Served]:
    async for s in serve(BOTS, FakePipedream()):
        yield s


async def _put(s: Served, who: Any, **body: Any) -> httpx.Response:
    return await s.http.put("/v1/projects/crew", json=body, headers=who.headers)


async def test_the_crews_project_is_found_or_made_for_a_workspace(s: Served, engine: AsyncEngine) -> None:
    faked(s)
    ada, bots = await crew(s, engine)
    ids = [b["id"] for b in bots]
    res = await _put(s, ada, repo="acme/site", members=ids[:1])
    assert res.status_code == 200, res.text
    made = res.json()
    assert made["slug"].startswith("crew-") and made["name"] == "acme/site (main)" and made["github_connected"] is True
    assert (made["repo_url"], made["base_branch"], [m["slug"] for m in made["members"]]) == (REPO, "main", ["ada-cat"])
    assert (made["review"], made["turn_mode"], made["runs_on"], made["max_turns"]) == ("each_turn", "wait", None, 30)
    mine = (await lead(s, ada))["id"]  # the org's orchestrator bot leads every project: one given is not read
    assert made["orchestrator"] == mine
    settings = {"review": "end", "turn_mode": "orchestrator", "narrate": True}
    settings |= {"max_turns": 5, "max_spend_cents": 100, "runs_on": None}
    again = (await _put(s, ada, repo=REPO + "/", branch="main", members=ids, orchestrator=ids[1], **settings)).json()
    assert (again["id"], again["slug"]) == (made["id"], made["slug"])  # the same project, set to what is given
    assert {k: again[k] for k in settings} == settings and len(again["members"]) == 2
    assert again["orchestrator"] == mine
    kept = (await _put(s, ada, repo="acme/site", members=ids)).json()  # a setting left out is left as it is
    assert {k: kept[k] for k in settings} == settings
    other = (await _put(s, ada, repo="acme/site", branch="dev", members=ids, orchestrator=ids[0])).json()
    assert other["slug"] != made["slug"] and other["base_branch"] == "dev" and other["name"] == "acme/site (dev)"
    assert other["orchestrator"] == mine
    listed = (await s.http.get("/v1/projects", headers=ada.headers)).json()["projects"]
    assert sorted(p["slug"] for p in listed) == sorted([made["slug"], other["slug"]])
    for bad in ({"repo": "acme"}, {"repo": "https://gitlab.com/acme/site"}, {"repo": "acme/site", "name": "Mine"}):
        assert (await _put(s, ada, **({"members": ids} | bad))).status_code == 422
    res = await _put(s, ada, repo="../site", members=ids)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "repo"


async def test_a_workspace_is_connected_only_where_the_app_is_and_the_person_may_push(
    s: Served, engine: AsyncEngine
) -> None:
    faked(s)
    ada, bots = await crew(s, engine)
    gh, ids = github_of(s), [b["id"] for b in bots]
    res = await _put(s, ada, repo="acme/other", members=ids)
    said = res.json()["error"]
    assert res.status_code == 404 and (said["reason"], said["install_url"]) == ("github_app_missing", INSTALL_URL)
    grace = await member(engine, ada.org_id)
    res = await _put(s, grace, repo="acme/site", members=ids)
    assert res.status_code == 403 and res.json()["error"]["reason"] == "github_not_linked"
    account = await signs_in_with_github(engine, grace, "grace-gh")
    res = await _put(s, grace, repo="acme/site", members=ids)  # GitHub knows no such collaborator
    assert res.status_code == 403 and res.json()["error"]["reason"] == "github_no_write"
    gh.logins |= dict([account])
    res = await _put(s, grace, repo="acme/site", members=ids)  # she may read it, not push
    assert res.status_code == 403 and res.json()["error"]["reason"] == "github_no_write"
    assert (await s.http.get("/v1/projects", headers=ada.headers)).json()["projects"] == []
    gh.pushers["acme/site"].add("grace-gh")
    assert (await _put(s, grace, repo="acme/site", members=ids)).status_code == 200
    for down in ("permission", "installation", "*"):
        gh.down = {down}
        res = await _put(s, ada, repo="acme/site", members=ids)
        assert res.status_code == 503 and res.json()["error"]["reason"] == "github", res.text


async def test_the_repo_picker_lists_the_persons_installation_and_a_repos_branches(
    s: Served, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    faked(s)
    ada, _ = await crew(s, engine)
    gh = github_of(s)
    none = await s.http.get("/v1/github/repos", headers=ada.headers)
    assert none.status_code == 200 and none.json() == {"account_login": "", "manage_url": "", "repos": []}
    async with engine.begin() as conn:
        values = {"user_id": ada.user_id, "installation_id": INSTALLATION, "account_login": "acme"}
        await conn.execute(insert(GitHubInstallation).values(values))
    for name in ("acme/zed", "acme/Api"):
        gh.install(name, INSTALLATION)
    gh.private.add("acme/Api")
    found = (await s.http.get("/v1/github/repos", headers=ada.headers)).json()
    assert found["account_login"] == "acme"
    assert found["manage_url"] == f"https://github.com/settings/installations/{INSTALLATION}"
    assert [(r["full_name"], r["private"], r["default_branch"]) for r in found["repos"]] == [
        ("acme/Api", True, "main"),
        ("acme/site", False, "main"),
        ("acme/zed", False, "main"),
    ]
    assert found["repos"][1]["url"] == REPO
    looked = list(gh.tokens.values())[-1]  # read with a token that may only look
    assert looked["permissions"] == {"metadata": "read"} and len(looked["repos"]) == 3
    monkeypatch.setattr(github_repos, "PER_PAGE", 1)
    monkeypatch.setattr(github_repos, "PAGES", 2)
    capped = (await s.http.get("/v1/github/repos", headers=ada.headers)).json()
    assert [r["full_name"] for r in capped["repos"]] == ["acme/Api", "acme/site"]
    res = await s.http.get("/v1/github/repos/acme/site/branches", headers=ada.headers)
    assert res.status_code == 200 and res.json() == {"default_branch": "main", "branches": ["main", "dev"]}
    res = await s.http.get("/v1/github/repos/acme/nope/branches", headers=ada.headers)
    assert res.status_code == 404 and res.json()["error"]["install_url"] == INSTALL_URL
    gh.down = {"repositories"}
    assert (await s.http.get("/v1/github/repos", headers=ada.headers)).status_code == 503
    gh.down, gh.installed = set(), {}  # the App removed on GitHub
    gone = await s.http.get("/v1/github/repos", headers=ada.headers)
    assert gone.status_code == 404 and gone.json()["error"]["reason"] == "github_app_missing"


async def test_a_turns_token_is_for_its_repo_and_a_reinstalled_app_is_connected_again(
    s: Served, engine: AsyncEngine
) -> None:
    repo, claude = faked(s)
    ada, bots = await crew(s, engine)
    gh, projects = github_of(s), s.app.state.bots.projects
    await project(s, ada, bots, max_turns=1)
    claude.then(say("Nothing to do.\nPASS"))
    first = await run_of(s, ada, (await start(s, ada)).json()["id"])
    assert first["status"] == "done"
    assert gh.tokens[repo.tokens[-1]]["permissions"]["pull_requests"] == "write"
    assert gh.tokens[repo.tokens[-1]]["installation"] == INSTALLATION
    gh.installed["acme/site"] = INSTALLATION + 1  # removed, and installed again: another installation
    claude.then(say("Still nothing.\nPASS"))
    await run_of(s, ada, (await start(s, ada)).json()["id"])
    assert gh.tokens[repo.tokens[-1]]["installation"] == INSTALLATION + 1
    for installation_id, name in ((None, "acme/site"), (INSTALLATION + 1, "acme/elsewhere"), (99, "acme/site")):
        with pytest.raises(NotFound, match="not installed on") as refused:
            await projects.github.token(installation_id, name)
        assert refused.value.detail["install_url"] == INSTALL_URL


async def test_a_run_has_its_own_model_and_effort(s: Served, engine: AsyncEngine) -> None:
    _, claude = faked(s)
    ada, bots = await crew(s, engine)
    await project(s, ada, bots, max_turns=1, turn_mode="orchestrator")
    post, path = s.http.post, "/v1/projects/site-crew/runs"
    for bad, reason in (({"model": "gpt-9"}, "model"), ({"effort": "extreme"}, None)):
        res = await post(path, json={"task": "Go"} | bad, headers=ada.headers)
        assert res.status_code == 422 and (reason is None or res.json()["error"]["reason"] == reason), res.text
    claude.then(say('{"next": "bo-cat", "why": "Their part."}'), say("Nothing to do.\nPASS"))
    given = {"task": "Go", "model": "claude-haiku-5-5", "effort": "low"}
    run = await run_of(s, ada, (await post(path, json=given, headers=ada.headers)).json()["id"])
    assert (run["status"], run["model"], run["effort"]) == ("done", "claude-haiku-5-5", "low")
    assert {model for _, model in claude.keys} == {"claude-haiku-5-5"}  # the pick's and the turn's alike
    assert [a["effort"] for a in claude.asked] == ["low", "low"]
    assert run["cost_micros"] == 2 * (1000 * 10 + 200 * 50) // 100  # at that model's rate
    claude.then(say('{"next": "bo-cat"}'), say("Nothing to do.\nPASS"))
    plain = await run_of(s, ada, (await post(path, json={}, headers=ada.headers)).json()["id"])
    assert (plain["model"], plain["effort"]) == (None, None) and claude.asked[-1]["effort"] is None
    assert claude.keys[-1][1] == "claude-opus-5-5"


async def test_githubs_reads_fail_closed() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    async with httpx.AsyncClient(transport=httpx.MockTransport(down)) as http:
        with pytest.raises(Unavailable, match="didn't answer"):
            await github_repos.ask(http, "ghs_x", "/installation/repositories")
    garbled = httpx.MockTransport(lambda r: httpx.Response(200, text="<html>"))
    async with httpx.AsyncClient(transport=garbled) as http:
        with pytest.raises(Unavailable):
            await github_repos.branches(http, "ghs_x", "acme/site")
    refused = httpx.MockTransport(lambda r: httpx.Response(500, json={"message": "Server Error"}))
    async with httpx.AsyncClient(transport=refused) as http:
        with pytest.raises(Unavailable, match="500"):
            await github_repos.branches(http, "ghs_x", "acme/site")
        with pytest.raises(Unavailable, match="500"):
            await github_repos.may_push(http, "ghs_x", "acme/site", "ada-gh", "1")
