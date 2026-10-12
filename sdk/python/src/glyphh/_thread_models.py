"""Threads and questions as plain frozen dataclasses: only a thread's record (its messages are on its machine)."""

from dataclasses import dataclass
from datetime import datetime

from glyphh._gen.models.answered import Answered as _Answered
from glyphh._gen.models.crew_face import CrewFace as _CrewFace
from glyphh._gen.models.question import Question as _Question
from glyphh._gen.models.question_page import QuestionPage as _QuestionPage
from glyphh._gen.models.thread_detail import ThreadDetail as _ThreadDetail
from glyphh._gen.models.thread_page import ThreadPage as _ThreadPage
from glyphh._gen.models.thread_row import ThreadRow as _ThreadRow
from glyphh._models import _opt


@dataclass(frozen=True, slots=True)
class CrewFace:
    """A super power as a thread shows it: its face and its name."""

    id: str
    name: str
    avatar_variant: int
    avatar_color: str | None


@dataclass(frozen=True, slots=True)
class Thread:
    id: str
    machine_id: str
    goal: str
    status: str
    last_seq: int
    last_event_at: datetime
    pinned_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    super_power: CrewFace | None
    crew: list[CrewFace]
    needs_you: int


@dataclass(frozen=True, slots=True)
class ThreadPage:
    machine: str
    threads: list[Thread]
    total: int
    crew: dict[str, int]
    """How many threads each super power is in, by its name."""


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    thread_id: str
    thread_goal: str
    machine_id: str
    machine_name: str
    super_power: CrewFace | None
    kind: str
    tool: str
    detail: str
    asked_at: datetime


@dataclass(frozen=True, slots=True)
class ThreadDetail:
    thread: Thread
    machine_name: str
    machine_online: bool
    machine_last_seen_at: datetime | None
    questions: list[Question]


@dataclass(frozen=True, slots=True)
class QuestionPage:
    questions: list[Question]
    total: int


@dataclass(frozen=True, slots=True)
class Answered:
    id: str
    answer: str
    answered_at: datetime


def _when(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def face_of(m: _CrewFace | None) -> CrewFace | None:
    if m is None:
        return None
    return CrewFace(id=str(m.id), name=m.name, avatar_variant=m.avatar_variant, avatar_color=_opt(m.avatar_color))


def thread_of(m: _ThreadRow) -> Thread:
    return Thread(
        id=str(m.id),
        machine_id=str(m.machine_id),
        goal=m.goal,
        status=m.status,
        last_seq=m.last_seq,
        last_event_at=m.last_event_at,
        pinned_at=_when(m.pinned_at),
        archived_at=_when(m.archived_at),
        created_at=m.created_at,
        super_power=face_of(m.super_power),
        crew=[f for f in map(face_of, m.crew) if f],
        needs_you=m.needs_you,
    )


def thread_page_of(m: _ThreadPage) -> ThreadPage:
    crew = {c.super_power.name: c.threads for c in m.crew}
    return ThreadPage(machine=m.machine, threads=[thread_of(t) for t in m.threads], total=m.total, crew=crew)


def question_of(m: _Question) -> Question:
    return Question(
        id=str(m.id),
        thread_id=str(m.thread_id),
        thread_goal=m.thread_goal,
        machine_id=str(m.machine_id),
        machine_name=m.machine_name,
        super_power=face_of(m.super_power),
        kind=m.kind,
        tool=m.tool,
        detail=m.detail,
        asked_at=m.asked_at,
    )


def detail_of(m: _ThreadDetail) -> ThreadDetail:
    return ThreadDetail(
        thread=thread_of(m.thread),
        machine_name=m.machine.name,
        machine_online=m.machine.online,
        machine_last_seen_at=_when(m.machine.last_seen_at),
        questions=[question_of(q) for q in m.questions],
    )


def question_page_of(m: _QuestionPage) -> QuestionPage:
    return QuestionPage(questions=[question_of(q) for q in m.questions], total=m.total)


def answered_of(m: _Answered) -> Answered:
    return Answered(id=str(m.id), answer=str(m.answer.value), answered_at=m.answered_at)
