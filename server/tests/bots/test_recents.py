"""Recents: the org's runs in one list, a bot's own and a crew's alike, searched, filtered and paged; the count of
those that wait on a person; each person's own pins and archive; and a run deleted once it has ended."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import BotRun, ProjectRun, RunMark
from tests.bots.conftest import Served, made_bot
from tests.db.helpers import Person, member, person

FINE: dict[str, Any] = {"loop": [{"id": "a", "agent": "Hi"}]}
T0: datetime = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)


async def _made(s: Served, engine: AsyncEngine) -> tuple[Person, dict[str, str]]:
    """Ada's org with five runs, a minute apart: two of her bot Juno's (one waiting), one of Milo's, and two of a
    crew's on acme/site (one waiting on its pull request). Their ids by a short name, oldest first."""
    ada = await person(engine)
    juno = await made_bot(s, ada, name="Juno", spec=FINE)
    milo = await made_bot(s, ada, name="Milo", spec=FINE)
    crew = {"name": "Site crew", "repo_url": "https://github.com/acme/site", "members": [juno["id"]]}
    made = await s.http.post("/v1/projects", json=crew | {"base_branch": "dev"}, headers=ada.headers)
    assert made.status_code == 201, made.text
    own = {"org_id": ada.org_id, "user_id": ada.user_id}
    rows: list[tuple[str, Any, dict[str, Any]]] = [
        ("old", BotRun, {"bot_id": juno["id"], "input": "\n  Sort the invoices  \nthen file them", "status": "done"}),
        ("crew", ProjectRun, {"task": "Build the pricing page", "status": "failed"}),
        ("milo", BotRun, {"bot_id": milo["id"], "input": "", "status": "failed"}),
        ("asks", BotRun, {"bot_id": juno["id"], "input": "Answer the mail", "status": "needs_input"}),
        ("pr", ProjectRun, {"task": "Fix the footer", "status": "needs_input"}),
    ]
    ids = {}
    async with engine.begin() as conn:
        for n, (name, table, values) in enumerate(rows):
            values |= own | {"created_at": T0 + timedelta(minutes=n)}
            if table is ProjectRun:
                values |= {"project_id": made.json()["id"], "review": "each_turn", "stamp": f"s{n}"}
            ids[name] = str((await conn.execute(insert(table).values(values).returning(table.id))).scalar_one())
    return ada, ids


async def _recents(s: Served, who: Person, **params: Any) -> dict[str, Any]:
    res = await s.http.get("/v1/recents", params=params, headers=who.headers)
    assert res.status_code == 200, res.text
    return dict(res.json())


def _ids(found: dict[str, Any]) -> list[str]:
    return [r["id"] for r in found["recents"]]


async def test_recents_lists_bot_and_crew_runs_together(served: Served, engine: AsyncEngine) -> None:
    ada, ids = await _made(served, engine)
    found = await _recents(served, ada)
    assert _ids(found) == [ids[n] for n in ("pr", "asks", "milo", "crew", "old")]
    assert (found["needs_you"], found["archived_count"], found["next_cursor"]) == (2, 0, None)
    pr, asks, milo, _, old = found["recents"]
    assert pr == {
        "id": ids["pr"],
        "kind": "crew",
        "title": "Fix the footer",
        "bot_slug": None,
        "bot_name": "Crew",
        "project_slug": "site-crew",
        "workspace": "acme/site",
        "branch": "dev",
        "runs_on": None,
        "status": "needs_input",
        "waiting": True,
        "pinned": False,
        "archived": False,
        "created_at": "2026-11-20T10:04:00Z",
    }
    assert (asks["kind"], asks["bot_slug"], asks["bot_name"], asks["waiting"]) == ("bot", "juno", "Juno", True)
    assert (asks["project_slug"], asks["workspace"], asks["branch"]) == (None, None, None)
    assert (milo["title"], milo["waiting"], old["title"]) == ("", False, "Sort the invoices")
    for q, names in (("INVOICE", ["old"]), ("milo", ["milo"]), ("acme/site", ["pr", "crew"]), ("nothing", [])):
        assert _ids(await _recents(served, ada, q=q)) == [ids[n] for n in names]
    waiting = await _recents(served, ada, waiting=1, q=" ")
    assert _ids(waiting) == [ids["pr"], ids["asks"]] and waiting["needs_you"] == 2
    first = await _recents(served, ada, limit=2)
    assert _ids(first) == [ids["pr"], ids["asks"]] and first["next_cursor"] == "2026-11-20T10:03:00Z"
    second = await _recents(served, ada, limit=2, cursor=first["next_cursor"])
    assert _ids(second) == [ids["milo"], ids["crew"]] and second["next_cursor"] is not None
    last = await _recents(served, ada, limit=2, cursor=second["next_cursor"])
    assert _ids(last) == [ids["old"]] and last["next_cursor"] is None
    assert (await served.http.get("/v1/recents?limit=0", headers=ada.headers)).status_code == 422
    elsewhere = await _recents(served, await person(engine))  # another org's
    assert (elsewhere["recents"], elsewhere["needs_you"]) == ([], 0)


async def test_a_person_pins_and_archives_runs_for_themselves(served: Served, engine: AsyncEngine) -> None:
    ada, ids = await _made(served, engine)
    grace = await member(engine, ada.org_id)
    post = served.http.post
    pinned = await post(f"/v1/recents/{ids['old']}/pin", headers=ada.headers)
    assert pinned.status_code == 200 and (pinned.json()["id"], pinned.json()["pinned"]) == (ids["old"], True)
    assert _ids(await _recents(served, ada, pinned=1)) == [ids["old"]]
    assert _ids(await _recents(served, grace, pinned=1)) == []  # hers alone
    gone = await post(f"/v1/recents/{ids['crew']}/archive", headers=ada.headers)
    assert (gone.json()["archived"], gone.json()["kind"]) == (True, "crew")
    await post(f"/v1/recents/{ids['old']}/archive", headers=ada.headers)
    shown = await _recents(served, ada)
    assert _ids(shown) == [ids[n] for n in ("pr", "asks", "milo")] and shown["archived_count"] == 2
    archived = await _recents(served, ada, archived=1)
    assert _ids(archived) == [ids["crew"], ids["old"]] and archived["recents"][1]["pinned"] is True
    theirs = await _recents(served, grace)
    assert len(theirs["recents"]) == 5 and theirs["archived_count"] == 0
    back = await post(f"/v1/recents/{ids['old']}/unarchive", headers=ada.headers)
    assert (back.json()["archived"], back.json()["pinned"]) == (False, True)
    assert (await post(f"/v1/recents/{ids['old']}/unpin", headers=ada.headers)).json()["pinned"] is False
    assert (await post(f"/v1/recents/{uuid.uuid4()}/pin", headers=ada.headers)).status_code == 404
    assert (await post(f"/v1/recents/{ids['old']}/star", headers=ada.headers)).status_code == 422
    outsider = await person(engine)
    assert (await post(f"/v1/recents/{ids['old']}/pin", headers=outsider.headers)).status_code == 404


async def test_a_run_is_deleted_once_it_has_ended(served: Served, engine: AsyncEngine) -> None:
    ada, ids = await _made(served, engine)
    delete = served.http.delete
    for live in ("asks", "pr"):
        res = await delete(f"/v1/recents/{ids[live]}", headers=ada.headers)
        assert res.status_code == 409 and res.json()["error"]["reason"] == "run_live", res.text
    await served.http.post(f"/v1/recents/{ids['old']}/pin", headers=ada.headers)
    for ended in ("old", "crew"):
        assert (await delete(f"/v1/recents/{ids[ended]}", headers=ada.headers)).status_code == 204
    assert (await delete(f"/v1/recents/{ids['old']}", headers=ada.headers)).status_code == 404
    left = await _recents(served, ada)
    assert _ids(left) == [ids[n] for n in ("pr", "asks", "milo")] and left["needs_you"] == 2
    async with engine.connect() as conn:
        assert (await conn.execute(select(RunMark).where(RunMark.user_id == ada.user_id))).first() is None
