"""What a model's versions say of themselves (docs/specs/ada-cloud.md, 5.2), for a page of versions and the connector:
what changed against the version before (a diff of spec and settings, each change marked when it rewrites the stored
cases), what each had learned (roles, words, pairs, temperatures), the latest backtest scores of it, and its store:
the active one, kept (from when it may be dropped), being made, or dropped.

The diff is generic: lists of named things (layers, segments, roles) are matched by name, settings are compared lever
by lever as the kernel fills them in, anything else value by value."""

from datetime import timedelta
from typing import Any

import glyphh_spec
import psycopg

from glyphh_ada import catalog, limits
from glyphh_ada.catalog import q
from glyphh_ada.errors import Refusal
from glyphh_ada.jobs import summary
from glyphh_ada.situations import STORED_SETTINGS, learned_of

Change = dict[str, Any]
_ROWS = """
    SELECT v.version, v.note, v.made_by, v.made_at, v.version = m.active_version, v.store, v.backtest, v.ready,
           v.gone, v.retired_at, v.precedents_at, v.spec, v.learned FROM {s}.spec_versions v
    JOIN {s}.models m ON m.id = v.model_id WHERE v.model_id = %s ORDER BY v.version
"""
_KEYS = ("version", "note", "made_by", "made_at", "active", "store", "backtest", "ready", "gone", "retired_at")
_BACKTESTS = """
    SELECT id, finished_at, result FROM {s}.jobs WHERE model_id = %s AND kind = 'backtest' AND state = 'done'
    ORDER BY finished_at DESC LIMIT 100
"""
_SPEC = "SELECT spec FROM {s}.spec_versions WHERE model_id = %s AND version = %s"
SCORES: tuple[str, ...] = ("n", "accuracy", "top_accuracy", "log_loss", "ask_rate", "accuracy_answered")
SCORES += ("coverage", "calibration_error", "cost_mean")
_STORED = ("dimension", "seed", "interactions", *(f"settings.{k}" for k in STORED_SETTINGS))


def _named(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(x, dict) and "name" in x for x in value)


def _walk(path: str, old: Any, new: Any, out: list[Change]) -> None:
    if old == new or (old in (None, []) and new in (None, [])):
        return
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted({*old, *new}):
            _walk(f"{path}.{key}" if path else str(key), old.get(key), new.get(key), out)
        return
    if (_named(old) or old in (None, [])) and (_named(new) or new in (None, [])) and (old or new):
        before, after = {x["name"]: x for x in old or []}, {x["name"]: x for x in new or []}
        for key in [*before, *(k for k in after if k not in before)]:
            _walk(f"{path}[{key}]", before.get(key), after.get(key), out)
        return
    out.append({"path": path, "from": old, "to": new})


def _full(spec_json: Any) -> Any:
    """The spec as the kernel states it, with every lever its settings stand at (a default still compares)."""
    spec = glyphh_spec.Spec.from_json(spec_json)
    return {**spec.to_json(), "settings": spec.settings.to_json(all=True)}


def _restates(change: Change) -> bool:
    """Whether this change rewrites the stored cases (a new store, by a re-encode), as situations.same_store reads."""
    path = change["path"]
    whole = path.endswith("]")  # a layer, segment or role added or taken away
    role = path.startswith("layers[") and (whole or path.endswith(".value_weights") or ".value_weights." in path)
    return role or any(path == p or path.startswith(f"{p}.") or path.startswith(f"{p}[") for p in _STORED)


def diff(old: Any, new: Any) -> list[Change]:
    """Every change from the old spec to the new one: {path, from, to, restates}."""
    out: list[Change] = []
    _walk("", _full(old), _full(new), out)
    return [{**c, "restates": _restates(c)} for c in out]


def learned(kept: dict[str, Any] | None) -> dict[str, Any] | None:
    """A store's learned state, shortly: per output (`default` and each named one) its roles' weights, how many words
    each text role weighs and the pairs; and its temperature. None when nothing was learned."""
    if not kept:
        return None
    out: dict[str, Any] = {}
    for key, value in sorted(kept.items()):
        kind, _, output = key.partition(":")
        entry = out.setdefault(output or "default", {})
        if kind == "learned" and isinstance(value, dict):
            entry.update(summary(value))
        elif kind == "tau":
            entry["tau"] = round(float(value), 4)
    return out


def scores(backtests: list[tuple[Any, Any, Any]], version: int) -> dict[str, Any] | None:
    """The newest backtest that scored this version (as the active one, or as a candidate naming it)."""
    for job_id, at, result in backtests:
        runs = [(result.get("version"), result.get("active") or {})]
        runs += [(c.get("candidate", {}).get("spec_version"), c) for c in result.get("candidates") or []]
        for scored, run in runs:
            if scored == version and "error" not in run:
                kept = {k: run[k] for k in SCORES if k in run}
                return {"job": job_id, "at": at, "output": result.get("output"), **kept}
    return None


def store(row: dict[str, Any], active_store: str, retired: dict[str, Any]) -> dict[str, Any]:
    """The version's store: `active` (it reads the active store, never dropped), `dropped`, `making` (a re-encode not
    finished: dropped by the next), or `kept`, with `drop_after`: from when the next re-encode may drop it."""
    if row["store"] == active_store:
        return {"status": "active", "drop_after": None}
    if row["gone"]:
        return {"status": "dropped", "drop_after": None}
    if not row["ready"]:
        return {"status": "making", "drop_after": None}
    last = retired.get(row["store"])
    return {"status": "kept", "drop_after": last + timedelta(days=limits.KEPT_DAYS) if last else None}


def _entries(conn: psycopg.Connection, schema: str, found: catalog.Live) -> list[tuple[dict[str, Any], Any]]:
    """Every version, oldest first, as listing answers it, with its spec."""
    rows = [
        {**dict(zip(_KEYS, r[:10], strict=True)), "store": r[5], "precedents_at": r[10], "spec": r[11], "kept": r[12]}
        for r in conn.execute(q(schema, _ROWS), (found.id,)).fetchall()
    ]
    tests = conn.execute(q(schema, _BACKTESTS), (found.id,)).fetchall()
    retired: dict[str, Any] = {}
    for row in rows:
        if row["retired_at"] is not None:
            retired[row["store"]] = max(retired.get(row["store"], row["retired_at"]), row["retired_at"])
    live = learned_of(conn, schema, found.store)
    out, before = [], None
    for row in rows:
        entry = {k: row[k] for k in _KEYS if k != "store"}
        entry["reencoded"] = row["store"] != found.id.hex
        entry["new_store"] = before is not None and row["store"] != before["store"]
        entry["changes"] = None if before is None else diff(before["spec"], row["spec"])
        entry["precedents_at"] = row["precedents_at"]
        entry["learned"] = learned(live if row["active"] else row["kept"])
        entry["scores"] = scores(tests, row["version"])
        entry["store"] = store(row, found.store, retired)
        out.append((entry, row["spec"]))
        before = row
    return out


def listing(conn: psycopg.Connection, schema: str, name: str) -> list[dict[str, Any]]:
    """Every version, oldest first: who made it, when and why, which is active, which made a store of its own; what
    changed against the version before; the precedents when it was made; what it had learned; the newest backtest
    of it; its store."""
    return [entry for entry, _ in _entries(conn, schema, catalog.live(conn, schema, name))]


def _spec(conn: psycopg.Connection, schema: str, found: catalog.Live, version: int) -> Any:
    got = conn.execute(q(schema, _SPEC), (found.id, version)).fetchone()
    if got is None:
        raise Refusal("E_VERSION_MISSING", f"This model has no version {version}.", 404, version=version)
    return got[0]


def detail(conn: psycopg.Connection, schema: str, name: str, version: int) -> dict[str, Any]:
    """One version as listing answers it, with its whole spec and every lever its settings stand at."""
    found = catalog.live(conn, schema, name)
    spec = _spec(conn, schema, found, version)
    entry = next(e for e, _ in _entries(conn, schema, found) if e["version"] == version)
    return {**entry, "spec": spec, "settings": glyphh_spec.Spec.from_json(spec).settings.to_json(all=True)}


def compare(conn: psycopg.Connection, schema: str, name: str, version: int, against: int | None) -> dict[str, Any]:
    """What making this version active would change from another (the active one when none is named)."""
    found = catalog.live(conn, schema, name)
    other = found.version if against is None else against
    changes = diff(_spec(conn, schema, found, other), _spec(conn, schema, found, version))
    return {"version": version, "against": other, "changes": changes}
