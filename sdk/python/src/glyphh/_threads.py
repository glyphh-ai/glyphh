"""My machines' threads, by their record, and the questions my super powers are waiting on."""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from glyphh import _thread_models as models
from glyphh._calls import Call
from glyphh._gen.api.threads import (
    answer_needs_you,
    change_thread,
    delete_thread,
    get_thread,
    list_needs_you,
    list_threads,
)
from glyphh._gen.models.answer_in import AnswerIn
from glyphh._gen.models.answered import Answered
from glyphh._gen.models.question_page import QuestionPage
from glyphh._gen.models.thread_change import ThreadChange
from glyphh._gen.models.thread_detail import ThreadDetail
from glyphh._gen.models.thread_page import ThreadPage
from glyphh._gen.models.thread_row import ThreadRow
from glyphh._gen.types import UNSET

LIST = Call(list_threads, lambda r: isinstance(r.parsed, ThreadPage), models.thread_page_of)
GET = Call(get_thread, lambda r: isinstance(r.parsed, ThreadDetail), models.detail_of)
CHANGE = Call(change_thread, lambda r: isinstance(r.parsed, ThreadRow), models.thread_of)
DELETE = Call(delete_thread, lambda r: int(r.status_code) == 204, lambda _: None)
QUESTIONS = Call(list_needs_you, lambda r: isinstance(r.parsed, QuestionPage), models.question_page_of)
ANSWER = Call(answer_needs_you, lambda r: isinstance(r.parsed, Answered), models.answered_of)


def _list(machine_id: str, q: str, super_power: str | None, archived: bool, page: int, size: int) -> dict[str, Any]:
    sp = UUID(super_power) if super_power else UNSET
    return {"machine_id": UUID(machine_id), "q": q, "super_power": sp, "archived": archived, "page": page, "size": size}


def _change(thread_id: str, goal: str | None, pinned: bool | None, archived: bool | None) -> dict[str, Any]:
    given = {"goal": goal, "pinned": pinned, "archived": archived}
    return {
        "thread_id": UUID(thread_id),
        "body": ThreadChange.from_dict({k: v for k, v in given.items() if v is not None}),
    }


class Threads:
    """`Glyphh(...).threads`: a machine's threads, by their record (their messages are on the machine)."""

    def __init__(self, run: Callable[..., Any]) -> None:
        self._run = run

    def list(
        self,
        machine_id: str,
        *,
        q: str = "",
        super_power: str | None = None,
        archived: bool = False,
        page: int = 1,
        size: int = 25,
    ) -> Any:
        """A machine's threads (Recents): pinned first, then the newest; by goal, by a super power, archived or not."""
        return self._run(LIST, **_list(machine_id, q, super_power, archived, page, size))

    def get(self, thread_id: str) -> Any:
        """One thread's record, its machine (online or not) and its open questions."""
        return self._run(GET, thread_id=UUID(thread_id))

    def change(
        self, thread_id: str, *, goal: str | None = None, pinned: bool | None = None, archived: bool | None = None
    ) -> Any:
        """Rename it, pin it to the top of Recents or not, archive it or bring it back."""
        return self._run(CHANGE, **_change(thread_id, goal, pinned, archived))

    def delete(self, thread_id: str) -> None:
        """Delete an archived thread for good."""
        self._run(DELETE, thread_id=UUID(thread_id))


class AsyncThreads:
    """`AsyncGlyphh(...).threads`: the same calls for asyncio code."""

    def __init__(self, run: Callable[..., Awaitable[Any]]) -> None:
        self._run = run

    async def list(
        self,
        machine_id: str,
        *,
        q: str = "",
        super_power: str | None = None,
        archived: bool = False,
        page: int = 1,
        size: int = 25,
    ) -> Any:
        return await self._run(LIST, **_list(machine_id, q, super_power, archived, page, size))

    async def get(self, thread_id: str) -> Any:
        return await self._run(GET, thread_id=UUID(thread_id))

    async def change(
        self, thread_id: str, *, goal: str | None = None, pinned: bool | None = None, archived: bool | None = None
    ) -> Any:
        return await self._run(CHANGE, **_change(thread_id, goal, pinned, archived))

    async def delete(self, thread_id: str) -> None:
        await self._run(DELETE, thread_id=UUID(thread_id))


class NeedsYou:
    """`Glyphh(...).needs_you`: the questions my super powers are waiting on."""

    def __init__(self, run: Callable[..., Any]) -> None:
        self._run = run

    def list(self, page: int = 1, size: int = 25) -> Any:
        """Every open question across my machines, newest first, a page at a time."""
        return self._run(QUESTIONS, page=page, size=size)

    def answer(self, question_id: str, allow: bool) -> Any:
        """Allow or deny, once: answered anywhere, it is closed everywhere."""
        return self._run(ANSWER, question_id=UUID(question_id), body=AnswerIn(allow=allow))


class AsyncNeedsYou:
    """`AsyncGlyphh(...).needs_you`: the same calls for asyncio code."""

    def __init__(self, run: Callable[..., Awaitable[Any]]) -> None:
        self._run = run

    async def list(self, page: int = 1, size: int = 25) -> Any:
        return await self._run(QUESTIONS, page=page, size=size)

    async def answer(self, question_id: str, allow: bool) -> Any:
        return await self._run(ANSWER, question_id=UUID(question_id), body=AnswerIn(allow=allow))
