"""How a bot's decisions are doing, from their rows (docs/specs/bots.md, 12), per decision and day by day: how many
it decided and who decided them, its ask rate (the share the person was asked), its agreement (of the person's answers
where Ada had a guess, the share Ada guessed right) and its accuracy (of Ada's own calls the person checked, by
confirming or correcting, the share that were right). Counting only: nothing here learns."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import BotDecision
from glyphh_server.ops.bots.decision_views import GateDay, GateStats, Stats

D = BotDecision
COUNTS: tuple[str, ...] = ("decisions", "ada", "you", "default", "corrected", "confirmed", "guessed", "agreed",
                           "checked", "right")  # fmt: skip


def _counts() -> list[Any]:
    def n(*when: Any) -> Any:
        return func.count().filter(and_(*when)) if when else func.count()

    wrong = and_(D.corrected.isnot(None), D.corrected != D.outcome)
    checked = and_(D.who == "ada", or_(D.confirmed, D.corrected.isnot(None)))
    return [
        n().label("decisions"), n(D.who == "ada").label("ada"), n(D.who == "you").label("you"),
        n(D.who == "default").label("default"), n(wrong).label("corrected"), n(D.confirmed).label("confirmed"),
        n(D.who == "you", D.guess.isnot(None)).label("guessed"),
        n(D.who == "you", D.guess.isnot(None), D.guess == func.coalesce(D.corrected, D.outcome)).label("agreed"),
        n(checked).label("checked"), n(checked, ~wrong).label("right"),
    ]  # fmt: skip


def _share(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def _rates(c: dict[str, int]) -> dict[str, float | None]:
    return {
        "ask_rate": _share(c["you"], c["decisions"]),
        "agreement": _share(c["agreed"], c["guessed"]),
        "accuracy": _share(c["right"], c["checked"]),
    }


async def stats(conn: AsyncConnection, bot: Any, gate: str | None, days: int) -> Stats:
    since = datetime.now(UTC) - timedelta(days=days)
    day = func.to_char(func.date_trunc("day", D.at), "YYYY-MM-DD").label("day")
    found = select(D.gate, day, *_counts()).where(D.bot_id == bot.id, D.at >= since, D.kind != "case")
    found = found.where(D.gate == gate) if gate else found
    rows = list(await conn.execute(found.group_by(D.gate, day).order_by(D.gate, day)))
    gates: dict[str, list[Any]] = {}
    for r in rows:
        gates.setdefault(r.gate, []).append(r)
    out = []
    for name in sorted(set(gates) | set((bot.spec.get("gates") or {}) if not gate else [gate])):
        days_of = gates.get(name, [])
        total = {k: sum(int(getattr(r, k)) for r in days_of) for k in COUNTS}
        series = [GateDay(day=r.day, decisions=int(r.decisions), **_rates({k: int(getattr(r, k)) for k in COUNTS}))
                  for r in days_of]  # fmt: skip
        by = {"ada": total["ada"], "you": total["you"], "default": total["default"]}
        out.append(GateStats(gate=name, decisions=total["decisions"], by=by, corrected=total["corrected"],
                             confirmed=total["confirmed"], **_rates(total), days=series))  # fmt: skip
    return Stats(gates=out)
