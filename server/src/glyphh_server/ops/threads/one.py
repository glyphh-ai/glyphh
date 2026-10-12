"""One thread, as opening it shows: its record, its machine (so a view can say the messages are on a machine that
is offline), and its open questions. Its messages are read from the machine, through the machine link."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.machines.installed import machine_named
from glyphh_server.ops.threads.needs import Question, open_questions
from glyphh_server.ops.threads.shape import ThreadRow, my_thread


class ThreadMachine(BaseModel):
    id: uuid.UUID
    name: str
    online: bool
    last_seen_at: datetime | None


class ThreadDetail(BaseModel):
    thread: ThreadRow
    machine: ThreadMachine
    questions: list[Question]


async def get_thread(conn: AsyncConnection, who: Principal, thread_id: uuid.UUID) -> ThreadDetail:
    thread = await my_thread(conn, who, thread_id)
    named = await machine_named(conn, who, thread.machine_id)
    machine = ThreadMachine(id=thread.machine_id, **named.model_dump())
    questions = await open_questions(conn, who, thread_id=thread_id)
    return ThreadDetail(thread=thread, machine=machine, questions=questions.questions)
