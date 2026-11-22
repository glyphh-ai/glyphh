"""Reading a bot's decisions (docs/specs/bots.md, 12): one row per item per gate per run, searched (every word, as a
prefix, over its label and fields), filtered (gate, outcome, who, corrected, a time range), sorted (time, confidence,
gate, outcome, either way) and paged by cursor (the last row's sort value and id, so a page never repeats or skips a
row as new ones arrive)."""

import base64
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid, NotFound
from glyphh_server.models import Bot, BotDecision, BotRun
from glyphh_server.ops.bots.decision_views import DecisionPage, DecisionView

MISSING: str = "There is no such decision."
D = BotDecision
SORTS: dict[str, Any] = {
    "time": D.at, "confidence": func.coalesce(D.p, -1.0), "gate": D.gate, "outcome": func.coalesce(D.outcome, ""),
}  # fmt: skip


@dataclass
class Find:
    q: str | None = None
    gate: str | None = None
    outcome: str | None = None
    who: str | None = None
    corrected: bool | None = None
    since: datetime | None = None
    until: datetime | None = None
    sort: str = "time"
    order: str = "desc"
    cursor: str | None = None
    limit: int = 25
    run_id: uuid.UUID | None = None


def outcomes(bot: Any) -> dict[str, list[str]]:
    return {name: list(g.get("outcomes") or []) for name, g in (bot.spec.get("gates") or {}).items()}


def _run_id() -> Any:
    found = select(BotRun.id).where(BotRun.bot_id == D.bot_id, BotRun.loop_run == D.loop_run, D.loop_run != "")
    return found.order_by(BotRun.created_at.desc()).limit(1).scalar_subquery().label("run_id")


def view(row: Any, gates: dict[str, list[str]]) -> DecisionView:
    now = row.corrected or row.outcome
    shown = {k: getattr(row, k) for k in ("id", "gate", "step", "key", "kind", "label", "fields", "outcome", "who")}
    more = {k: getattr(row, k) for k in ("mode", "guess", "recorded", "corrected", "confirmed", "at")}
    run_id = getattr(row, "run_id", None)
    return DecisionView(**shown, **more, run_id=run_id, now=now, confidence=row.p, outcomes=gates.get(row.gate, []))


def query(words: str) -> str | None:
    """Every word of the search, each as a prefix, all of them needed."""
    found = re.findall(r"\w+", words.lower())[:12]
    return " & ".join(f"{w}:*" for w in found) or None


def _filtered(found: Select[Any], f: Find) -> Select[Any]:
    if f.q and (asked := query(f.q)):
        found = found.where(D.search.op("@@")(func.to_tsquery("simple", asked)))
    for column, value in ((D.gate, f.gate), (D.outcome, f.outcome), (D.who, f.who)):
        if value is not None:
            found = found.where(column == value)
    if f.run_id is not None:
        found = found.where(D.loop_run == select(BotRun.loop_run).where(BotRun.id == f.run_id).scalar_subquery())
    if f.corrected is not None:
        found = found.where(D.corrected.isnot(None) if f.corrected else D.corrected.is_(None))
    if f.since is not None:
        found = found.where(D.at >= f.since)
    return found.where(D.at < f.until) if f.until is not None else found


def cursor_of(f: Find, row: Any) -> str:
    value = {"time": row.at.isoformat(), "confidence": -1.0 if row.p is None else row.p}.get(f.sort)
    value = (row.outcome or "") if f.sort == "outcome" else row.gate if f.sort == "gate" else value
    return base64.urlsafe_b64encode(json.dumps([f.sort, value, str(row.id)]).encode()).decode()


def _after(f: Find) -> tuple[Any, uuid.UUID]:
    try:
        sort, value, last = json.loads(base64.urlsafe_b64decode(f.cursor or ""))
        if sort != f.sort:
            raise ValueError(sort)
        return (datetime.fromisoformat(value) if sort == "time" else value), uuid.UUID(last)
    except (ValueError, TypeError) as err:
        raise Invalid("That cursor is not one this listing gave.", reason="cursor") from err


async def listing(conn: AsyncConnection, bot: Any, f: Find) -> DecisionPage:
    key = SORTS[f.sort]
    found = _filtered(select(D, _run_id()).where(D.bot_id == bot.id), f)
    total = (await conn.execute(select(func.count()).select_from(found.subquery()))).scalar_one()
    if f.cursor:
        value, last = _after(f)
        here = tuple_(key, D.id)
        found = found.where(here < tuple_(value, last) if f.order == "desc" else here > tuple_(value, last))
    ordered = (key.desc(), D.id.desc()) if f.order == "desc" else (key.asc(), D.id.asc())
    rows = list(await conn.execute(found.order_by(*ordered).limit(f.limit + 1)))
    gates = outcomes(bot)
    more = len(rows) > f.limit
    page = rows[: f.limit]
    following = cursor_of(f, page[-1]) if more and page else None
    return DecisionPage(decisions=[view(r, gates) for r in page], total=total, next_cursor=following, gates=gates)


async def row(conn: AsyncConnection, decision_id: uuid.UUID) -> tuple[Any, Any]:
    """The decision and its bot."""
    found = (await conn.execute(select(D, _run_id()).where(D.id == decision_id))).first()
    if found is None:
        raise NotFound(MISSING, decision_id=str(decision_id))
    bot = (await conn.execute(select(Bot).where(Bot.id == found.bot_id))).one()
    return found, bot


async def rows(conn: AsyncConnection, bot: Any, ids: list[uuid.UUID]) -> list[Any]:
    """The bot's decisions with these ids, in the order given; one it does not have is NotFound."""
    found = {r.id: r for r in await conn.execute(select(D, _run_id()).where(D.bot_id == bot.id, D.id.in_(ids)))}
    gone = [str(i) for i in ids if i not in found]
    if gone:
        raise NotFound(MISSING, decision_ids=gone)
    return [found[i] for i in ids]


async def by_precedent(conn: AsyncConnection, bot: Any, ids: list[str]) -> dict[str, Any]:
    """The bot's decisions whose precedent is one of these, by precedent id."""
    found = select(D).where(D.bot_id == bot.id, D.precedent.in_(ids), D.precedent != "")
    return {r.precedent: r for r in await conn.execute(found)}
