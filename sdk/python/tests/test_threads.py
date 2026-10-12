import json

import httpx
import pytest

from glyphh import Answered, AsyncGlyphh, CrewFace, Glyphh, QuestionPage, Thread, ThreadDetail, ThreadPage

SERVER = "http://localhost:8080"
M = "7f0c7b1e-0000-4000-8000-0000000000aa"
S = "7f0c7b1e-0000-4000-8000-0000000000bb"
T = "7f0c7b1e-0000-4000-8000-0000000000cc"
Q = "7f0c7b1e-0000-4000-8000-0000000000dd"
FACE = {"id": S, "name": "Clip Studio", "avatar_variant": 7, "avatar_color": None}
ROW = {
    "id": T,
    "machine_id": M,
    "goal": "YouTube to Instagram",
    "status": "working",
    "last_seq": 41,
    "last_event_at": "2026-10-12T12:00:00Z",
    "pinned_at": "2026-10-12T11:30:00Z",
    "archived_at": None,
    "created_at": "2026-10-12T11:00:00Z",
    "super_power": None,
    "crew": [FACE],
    "needs_you": 1,
}
QUESTION = {
    "id": Q,
    "thread_id": T,
    "thread_goal": "Launch note",
    "machine_id": M,
    "machine_name": "studio-mac",
    "super_power": {**FACE, "avatar_color": "#FF8AD8"},
    "kind": "permission",
    "tool": "slack.post",
    "detail": "Post in #launch",
    "asked_at": "2026-10-12T12:00:00Z",
}
PAGE = {"machine": "studio-mac", "threads": [ROW], "total": 1, "crew": [{"super_power": FACE, "threads": 1}]}
DETAIL = {
    "thread": ROW,
    "machine": {"id": M, "name": "studio-mac", "online": False, "last_seen_at": None},
    "questions": [QUESTION],
}
ANSWERED = {"id": Q, "answer": "allow", "answered_at": "2026-10-12T12:01:00Z"}


def answering(body: object, seen: list, status: int = 200) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status) if status == 204 else httpx.Response(status, json=body)

    return httpx.MockTransport(handle)


def test_threads_are_listed_opened_changed_and_deleted() -> None:
    seen: list = []
    page = Glyphh(SERVER, token="t", transport=answering(PAGE, seen)).threads.list(
        M, q="reels", super_power=S, archived=True
    )
    assert isinstance(page, ThreadPage) and page.crew == {"Clip Studio": 1} and page.machine == "studio-mac"
    thread = page.threads[0]
    assert isinstance(thread, Thread) and thread.super_power is None and thread.pinned_at is not None
    assert (
        thread.crew == [CrewFace(id=S, name="Clip Studio", avatar_variant=7, avatar_color=None)]
        and thread.archived_at is None
    )
    Glyphh(SERVER, token="t", transport=answering(PAGE, seen)).threads.list(M)
    detail = Glyphh(SERVER, token="t", transport=answering(DETAIL, seen)).threads.get(T)
    assert isinstance(detail, ThreadDetail) and (
        detail.machine_name,
        detail.machine_online,
        detail.machine_last_seen_at,
    ) == ("studio-mac", False, None)
    assert detail.questions[0].super_power and detail.questions[0].super_power.avatar_color == "#FF8AD8"
    changed = Glyphh(SERVER, token="t", transport=answering(ROW, seen)).threads.change(T, goal="Reels", pinned=True)
    assert changed.goal == "YouTube to Instagram"
    assert Glyphh(SERVER, token="t", transport=answering(None, seen, 204)).threads.delete(T) is None
    assert [str(r.url.params) for r in seen[:2]] == [
        f"q=reels&super_power={S}&archived=true&page=1&size=25",
        "q=&archived=false&page=1&size=25",
    ]
    assert json.loads(seen[3].content) == {"goal": "Reels", "pinned": True}
    assert [r.method for r in seen[2:]] == ["GET", "PATCH", "DELETE"]


def test_questions_are_listed_and_answered() -> None:
    seen: list = []
    page = Glyphh(SERVER, token="t", transport=answering({"questions": [QUESTION], "total": 1}, seen)).needs_you.list(
        2, 5
    )
    assert isinstance(page, QuestionPage) and page.questions[0].tool == "slack.post" and page.total == 1
    done = Glyphh(SERVER, token="t", transport=answering(ANSWERED, seen)).needs_you.answer(Q, False)
    assert isinstance(done, Answered) and done.answer == "allow"
    assert str(seen[0].url.params) == "page=2&size=5" and json.loads(seen[1].content) == {"allow": False}


@pytest.mark.parametrize("archived", [False, True])
async def test_the_async_client_answers_the_same(archived: bool) -> None:
    seen: list = []
    glyphh = lambda body, status=200: AsyncGlyphh(SERVER, token="t", transport=answering(body, seen, status))  # noqa: E731
    page = await glyphh(PAGE).threads.list(M, archived=archived)
    assert page.threads[0].id == T
    assert (await glyphh(DETAIL).threads.get(T)).thread.goal == "YouTube to Instagram"
    assert (await glyphh(ROW).threads.change(T, archived=True)).needs_you == 1
    assert await glyphh(None, 204).threads.delete(T) is None
    assert (await glyphh({"questions": [], "total": 0}).needs_you.list()).total == 0
    assert (await glyphh(ANSWERED).needs_you.answer(Q, True)).id == Q
    assert json.loads(seen[2].content) == {"archived": True}
