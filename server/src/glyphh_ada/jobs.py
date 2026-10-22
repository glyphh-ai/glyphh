"""Jobs: work too long for a request (learn, calibrate; imports, backtests and re-encodes later), each a row in the
org's `jobs` table, which is the truth (Redis only carries the work), with its state and progress
({state: queued | running | done | failed, percent, result, error}) written as it goes.

learn weighs the model's roles, values, words and pairs from its graded precedents and then calibrates its
temperature, as rrotor's learn does; calibrate fits the temperature alone. Both read at most limits.JOB_SAMPLE of the
newest precedents (sample.py). When learning changes what a stored case carries (learned word weights or pairs), the
kernel rewrites the sampled precedents; the job rewrites every other one after it, in batches, so the store is
restated whole: on Postgres a model is never restated when it is opened."""

import json
import uuid
from collections.abc import Callable
from typing import Any

import glyphh_spec
import psycopg
from psycopg.types.json import Jsonb

from glyphh_ada import catalog, limits
from glyphh_ada.catalog import q
from glyphh_ada.errors import Refusal, model_missing
from glyphh_ada.restate import restate_rest
from glyphh_ada.sample import Sampled

_VIEW = """
    SELECT j.id, m.name, j.kind, j.state, j.percent, j.args, j.result, j.error, j.created_at, j.started_at,
           j.finished_at FROM {s}.jobs j JOIN {s}.models m ON m.id = j.model_id WHERE j.id = %s
"""
_KEYS = (
    "id",
    "model",
    "kind",
    "state",
    "percent",
    "args",
    "result",
    "error",
    "created_at",
    "started_at",
    "finished_at",
)
Progress = Callable[[float], None]


def view(conn: psycopg.Connection, schema: str, job_id: str) -> dict[str, Any]:
    try:
        jid: uuid.UUID | None = uuid.UUID(job_id)
    except ValueError:
        jid = None
    found = None
    if jid is not None and catalog.has(conn, schema, "jobs"):
        found = conn.execute(q(schema, _VIEW), (jid,)).fetchone()
    if found is None:
        raise Refusal("E_JOB_MISSING", f"No job {job_id} in this org.", 404, job=job_id)
    return dict(zip(_KEYS, found, strict=True))


def add(conn: psycopg.Connection, schema: str, model_id: uuid.UUID, kind: str, args: dict, author: str) -> str:
    jid = uuid.uuid4()
    insert = "INSERT INTO {s}.jobs (id, model_id, kind, args, made_by) VALUES (%s, %s, %s, %s, %s)"
    conn.execute(q(schema, insert), (jid, model_id, kind, Jsonb(args), author))
    return str(jid)


def mark(conn: psycopg.Connection, schema: str, job_id: str, state: str, **values: Any) -> None:
    """The job's state, and its percent, result or error; started and finished stamped as it moves."""
    sets = ["state = %s"] + [f"{k} = %s" for k in values]
    stamp = {"running": ", started_at = now()", "done": ", finished_at = now()", "failed": ", finished_at = now()"}
    text = f"UPDATE {{s}}.jobs SET {', '.join(sets)}{stamp.get(state, '')} WHERE id = %s"
    params = [state, *(Jsonb(v) if k in ("result", "error") else v for k, v in values.items()), job_id]
    conn.execute(q(schema, text), params)


def _summary(table: dict[str, Any]) -> dict[str, Any]:
    """What learning found, shortly: each role's weight, how many words each text role weighs, the pairs."""
    roles = {p: v["similarity_weight"] for p, v in table.items() if not p.startswith("~") and "similarity_weight" in v}
    words = {p: len(v.get("value_weights", {})) for p, v in table.items() if not p.startswith("~") and p not in roles}
    pairs = [p.get("roles") or p.get("name") for p in table.get("~interactions", [])]
    return {"roles": roles, "words": words, "pairs": pairs}


def _tables(model: glyphh_spec.Model) -> Any:
    return (model.spec.interactions, glyphh_spec._word_tables(model.spec))


def run(conn: psycopg.Connection, schema: str, name: str, kind: str, progress: Progress) -> dict[str, Any]:
    """learn or calibrate one model of the org; the answer is the job's result."""
    found = catalog.active(conn, schema, name)
    if found is None:
        raise model_missing(name)
    model_id, _, spec_json, _ = found
    spec = glyphh_spec.Spec.from_json(spec_json)
    base = catalog.store(conn, schema, model_id, spec.dimension)
    total = base.count()
    model = glyphh_spec.Model(spec, store=Sampled(base, limits.JOB_SAMPLE))  # type: ignore[arg-type]
    model.refresh_every = None
    model.space.load()
    progress(30)
    out: dict[str, Any] = {"precedents": total, "sampled": min(total, limits.JOB_SAMPLE)}
    try:
        if kind == "learn":
            before = _tables(model)
            learned = model.learn()
            out["learned"] = {k: _summary(v) for k, v in learned.items()} if spec.outputs else _summary(learned)
            progress(60)
            if total > limits.JOB_SAMPLE and _tables(model) != before:
                out["restated"] = restate_rest(base, model, lambda f: progress(60 + 30 * f))
        out["tau"] = model.calibrate()
    except glyphh_spec.SpecError as e:
        raise Refusal("E_SPEC", str(e), 422, path=e.path) from None
    return json.loads(json.dumps(out, default=str))
