import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops.threads.edit import ThreadChange, change_thread, delete_thread
from glyphh_server.ops.threads.needs import Answered, QuestionPage, answer, open_questions
from glyphh_server.ops.threads.one import ThreadDetail, get_thread
from glyphh_server.ops.threads.recents import ThreadPage, list_threads
from glyphh_server.ops.threads.shape import ThreadRow

router = APIRouter(prefix="/v1", tags=["threads"])
Page = Annotated[int, Query(ge=1)]
Size = Annotated[int, Query(ge=1, le=100)]


class AnswerIn(BaseModel):
    allow: bool


@router.get("/machines/{machine_id}/threads", operation_id="listThreads")
async def threads(
    machine_id: uuid.UUID,
    caller: Caller,
    conn: Conn,
    q: Annotated[str, Query(max_length=200)] = "",
    super_power: uuid.UUID | None = None,
    archived: bool = False,
    page: Page = 1,
    size: Size = 25,
) -> ThreadPage:
    """A machine's threads (Recents): pinned first, then the newest; by goal, by a super power, archived or not."""
    return await list_threads(conn, caller, machine_id, q.strip(), super_power, archived, page, size)


@router.get("/threads/{thread_id}", operation_id="getThread")
async def thread(thread_id: uuid.UUID, caller: Caller, conn: Conn) -> ThreadDetail:
    """One thread's record, its machine and its open questions. Its messages are on the machine."""
    return await get_thread(conn, caller, thread_id)


@router.patch("/threads/{thread_id}", operation_id="changeThread")
async def change(thread_id: uuid.UUID, body: ThreadChange, caller: Caller, conn: Conn) -> ThreadRow:
    """Rename it, pin it to the top of Recents or not, archive it or bring it back."""
    return await change_thread(conn, caller, thread_id, body)


@router.delete("/threads/{thread_id}", operation_id="deleteThread", status_code=204)
async def delete(thread_id: uuid.UUID, caller: Caller, conn: Conn, request: Request) -> Response:
    """Delete an archived thread for good, and its messages on its machine."""
    await delete_thread(conn, caller, request.app.state.hub, thread_id)
    return Response(status_code=204)


@router.get("/needs-you", operation_id="listNeedsYou")
async def needs_you(caller: Caller, conn: Conn, page: Page = 1, size: Size = 25) -> QuestionPage:
    """Every question my super powers are waiting on, across my machines, newest first."""
    return await open_questions(conn, caller, page, size)


@router.post("/needs-you/{question_id}/answer", operation_id="answerNeedsYou")
async def answer_one(question_id: uuid.UUID, body: AnswerIn, caller: Caller, conn: Conn, request: Request) -> Answered:
    """Allow or deny, once: answered anywhere, it is closed everywhere, and the machine is told."""
    return await answer(conn, caller, request.app.state.hub, question_id, body.allow)
