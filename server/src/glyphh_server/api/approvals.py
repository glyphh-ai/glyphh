"""Approvals, shown in Claude: the person's waiting approvals, their live stream and the answer."""

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from glyphh_server.api.auth import Bearer, Caller, Conn, authenticate
from glyphh_server.ops import approval_stream, approvals
from glyphh_server.ops.approvals import Answer, Answered, ApprovalView

router = APIRouter(prefix="/v1/approvals", tags=["approvals"])

SSE_HEADERS: dict[str, str] = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


class AnswerBody(BaseModel):
    answer: Answer


@router.get("", operation_id="listApprovals")
async def list_approvals(caller: Caller, conn: Conn) -> list[ApprovalView]:
    """The approvals waiting for you, newest first."""
    return await approvals.waiting(conn, caller.user_id)


@router.get(
    "/stream",
    operation_id="streamApprovals",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_approvals(request: Request, creds: Bearer) -> StreamingResponse:
    """Server-sent events while Claude is open: `approval` {id, program, step, prompt, asked_at} (the waiting ones
    first) and `answered` {id, answer}; a comment every 20 seconds. The token is checked once, in a transaction that
    ends before the stream starts, so an open stream holds no database connection."""
    state = request.app.state
    async with state.engine.begin() as conn:
        who = await authenticate(conn, creds)
    events = approval_stream.stream(state.engine, state.redis, who)
    return StreamingResponse(events, media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/{approval_id}", operation_id="answerApproval")
async def answer_approval(
    approval_id: uuid.UUID, body: AnswerBody, caller: Caller, conn: Conn, request: Request
) -> Answered:
    """Approve or decline. The first answer wins; a second is E_CONFLICT. The answer goes to the run's runtime at
    once; a runtime that is not connected is E_UNAVAILABLE, and the approval stays waiting."""
    state = request.app.state
    return await approvals.answer_approval(conn, state.redis, state.hub, caller, approval_id, body.answer)
