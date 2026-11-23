"""The bot's decisions copied from the runner's state (its runs.sqlite) into bot_decisions after each go, on the
cloud and back from a rrotor alike (docs/specs/bots.md, 12): each made readable (the item's fields and a label drawn
from them), who decided it said plainly (Ada, you, or the decision's default), and what it should have been when it was
corrected. What only the server knows of a decision (confirmed, its precedent's id) is never overwritten."""

import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from glyphh.bots.runner import RunStore, _item_key
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import BotDecision
from glyphh_server.ops.bots import package, readable

KEPT_MAX: int = 5_000  # the newest decisions copied each go
CHUNK: int = 500  # rows an insert carries (Postgres takes at most 32,767 values a statement)
WHO: dict[str, str] = {"person": "you", "default": "default"}  # else Ada (its sure call, or its guess in code)
SYNCED: tuple[str, ...] = (
    "label", "fields", "case", "outcome", "who", "mode", "p", "guess", "recorded", "corrected", "body", "at",
)  # fmt: skip


def read(state: bytes) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """The runner's decisions, newest first, and each run's data by its id; none from a state that is not the runner's
    database (a runtime that sent something else keeps its bytes, but has nothing here to read)."""
    with tempfile.TemporaryDirectory(prefix="glyphh-decided-") as tmp:
        (Path(tmp) / package.STATE).write_bytes(state)
        try:
            store = RunStore(Path(tmp))
            rows = sorted(store.decisions(), key=lambda r: r["at"] or 0, reverse=True)[:KEPT_MAX]
            data = {r["id"]: r["data"] for r in store.recent()}
        except sqlite3.DatabaseError:
            return [], {}
    return rows, data


def _items(spec: dict[str, Any], data: dict[str, Any], step: str) -> dict[str, Any]:
    """A per-item decision's items in its run, by the key the runner gave each."""
    shape = next((s for s in spec.get("loop") or [] if isinstance(s, dict) and s.get("id") == step), {})
    out = data.get(step) if isinstance(data.get(step), dict) else {}
    found: dict[str, Any] = {}
    for name, items in out.items():
        if name != "decisions" and isinstance(items, list):
            found |= {_item_key(shape, item): item for item in items}
    return found


def row(bot: Any, d: dict[str, Any], item: Any) -> dict[str, Any]:
    shown = readable.fields(d["case"] if item is None else item)
    named = readable.label(d.get("label"), shown)
    corrected = d.get("wrong") or d.get("world")
    return {
        "org_id": bot.org_id, "bot_id": bot.id, "loop_run": d["run"] or "", "gate": d["gate"], "step": d["step"] or "",
        "n": d["n"] or 0, "key": d["key"] or "", "kind": d["kind"] or "gate", "label": named, "fields": shown,
        "case": d["case"] if d["case"] is not None else {}, "outcome": d["outcome"], "who": WHO.get(d["by"], "ada"),
        "mode": d["mode"] or "", "p": d["p"], "guess": d["guess"], "recorded": bool(d["recorded"]),
        "corrected": corrected, "body": readable.body(named, shown, d["gate"], d["outcome"], corrected),
        "at": datetime.fromtimestamp(d["at"] or 0, UTC),
    }  # fmt: skip


def rows(bot: Any, state: bytes) -> list[dict[str, Any]]:
    decisions, data = read(state)
    items: dict[tuple[str, str], dict[str, Any]] = {}
    out = []
    for d in decisions:
        where = (d["run"], d["step"])
        if d["kind"] == "each" and where not in items:
            items[where] = _items(bot.spec, data.get(d["run"]) or {}, d["step"])
        out.append(row(bot, d, items.get(where, {}).get(d["key"]) if d["kind"] == "each" else None))
    return out


async def sync(conn: AsyncConnection, bot: Any, state: bytes | None) -> int:
    """The bot's decisions in its state, kept: new ones added, changed ones brought up to date."""
    found = rows(bot, state) if state else []
    table, kept = BotDecision.__table__, 0
    keys = ["bot_id", "loop_run", "gate", "step", "n", "key"]
    for at in range(0, len(found), CHUNK):
        made = insert(table).values(found[at : at + CHUNK])
        changed = {c: made.excluded[c] for c in SYNCED}
        differs = or_(*(table.c[c].is_distinct_from(made.excluded[c]) for c in SYNCED))
        done = await conn.execute(made.on_conflict_do_update(index_elements=keys, set_=changed, where=differs))
        kept += int(done.rowcount or 0)
    return kept
