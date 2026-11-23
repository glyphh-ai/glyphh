"""Programs under test (docs/specs/programs.md): made, run and answered through the API as the platform does, each run
read as it stands once nothing of it is going, with its audit trail."""

from typing import Any

from tests.bots.conftest import Served
from tests.db.helpers import Person

FIND_STEP: dict[str, Any] = {"id": "find", "kind": "tool", "tool": "gmail-find-email", "input": {"q": "{input}"}}
SEND_STEP: dict[str, Any] = {
    "id": "send", "kind": "tool", "tool": "gmail-send-email", "title": "Send the reply",
    "input": {"to": ["grace@navy.test"], "subject": "Re: {find.0}", "body": "Found {find}"},
}  # fmt: skip


async def made(s: Served, who: Person, flow: list[dict[str, Any]], **over: Any) -> dict[str, Any]:
    body = {"name": "Mail Round", "summary": "Reads the mail", "flow": flow, "bot": "inbox-cat", **over}
    res = await s.http.post("/v1/programs", json=body, headers=who.headers)
    assert res.status_code == 201, res.text
    return dict(res.json())


async def run_of(s: Served, who: Person, run_id: str) -> dict[str, Any]:
    res = await s.http.get(f"/v1/program-runs/{run_id}", headers=who.headers)
    assert res.status_code == 200, res.text
    return dict(res.json())


async def ran(s: Served, who: Person, slug: str = "mail-round", said: str = "lunch") -> dict[str, Any]:
    res = await s.http.post(f"/v1/programs/{slug}/runs", json={"input": said}, headers=who.headers)
    assert res.status_code == 202, res.text
    await s.settled()
    return await run_of(s, who, res.json()["id"])


async def answered(s: Served, who: Person, run_id: str, answer: Any) -> dict[str, Any]:
    res = await s.http.post(f"/v1/program-runs/{run_id}/answer", json={"answer": answer}, headers=who.headers)
    assert res.status_code == 202, res.text
    await s.settled()
    return await run_of(s, who, run_id)


async def trail(s: Served, who: Person, run_id: str, after: int = 0) -> list[tuple[Any, ...]]:
    """The run's audit trail: (kind, step, bot, by, ok) a line."""
    res = await s.http.get(f"/v1/program-runs/{run_id}/events", params={"after": after}, headers=who.headers)
    assert res.status_code == 200, res.text
    return [(e["kind"], e["step"], e["bot"], e["by"], e["ok"]) for e in res.json()["events"]]
