"""Jobs: work too long for a request (learn, calibrate, imports, exports, re-encodes, backtests), each a row in the
org's `jobs` table, which is the truth (Redis only carries the work), with its state and progress
({state: awaiting | queued | running | done | failed, percent, result, error}) written as it goes. An import waits
in `awaiting` for its file.

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
from glyphh_postgres import PostgresStore
from psycopg.types.json import Jsonb

from glyphh_ada import catalog, limits
from glyphh_ada.catalog import q
from glyphh_ada.errors import Refusal
from glyphh_ada.restate import restate_rest
from glyphh_ada.sample import Sampled

_VIEW = """
    SELECT j.id, m.name, j.kind, j.state, j.percent, j.args, j.result, j.error, j.created_at, j.started_at,
           j.finished_at, j.made_by FROM {s}.jobs j JOIN {s}.models m ON m.id = j.model_id WHERE j.id = %s
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
    "made_by",
)
_OPEN = """
    SELECT id, kind FROM {s}.jobs WHERE model_id = %s AND kind = ANY(%s)
    AND (state IN ('queued', 'running') OR (state = 'awaiting' AND created_at > now() - make_interval(secs => %s)))
"""
Progress = Callable[[float], None]
BUSY_KINDS: list[str] = ["import", "reencode"]  # at most one of these at a time per model


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


def add(
    conn: psycopg.Connection,
    schema: str,
    model_id: uuid.UUID,
    kind: str,
    args: dict,
    author: str,
    state: str = "queued",
) -> str:
    jid = uuid.uuid4()
    insert = "INSERT INTO {s}.jobs (id, model_id, kind, args, made_by, state) VALUES (%s, %s, %s, %s, %s, %s)"
    conn.execute(q(schema, insert), (jid, model_id, kind, Jsonb(args), author, state))
    return str(jid)


def busy(conn: psycopg.Connection, schema: str, model_id: uuid.UUID, kinds: list[str] = BUSY_KINDS) -> None:
    """Refused (409 E_BUSY) while one of these jobs is open on the model: an import waiting for its file (for as long
    as its upload link works), queued or running."""
    found = conn.execute(q(schema, _OPEN), (model_id, kinds, limits.LINK_TTL)).fetchone()
    if found is not None:
        message = f"This model has a {found[1]} job open ({found[0]}): wait for it to end."
        raise Refusal("E_BUSY", message, 409, job=str(found[0]), kind=found[1])


def open_of(conn: psycopg.Connection, schema: str, model_id: uuid.UUID, kinds: list[str]) -> bool:
    return conn.execute(q(schema, _OPEN), (model_id, kinds, limits.LINK_TTL)).fetchone() is not None


def mark(conn: psycopg.Connection, schema: str, job_id: str, state: str, **values: Any) -> None:
    """The job's state, and its percent, result or error; started and finished stamped as it moves."""
    sets = ["state = %s"] + [f"{k} = %s" for k in values]
    stamp = {"running": ", started_at = now()", "done": ", finished_at = now()", "failed": ", finished_at = now()"}
    text = f"UPDATE {{s}}.jobs SET {', '.join(sets)}{stamp.get(state, '')} WHERE id = %s"
    params = [state, *(Jsonb(v) if k in ("result", "error") else v for k, v in values.items()), job_id]
    conn.execute(q(schema, text), params)


def summary(table: dict[str, Any]) -> dict[str, Any]:
    """What learning found, shortly: each role's weight, how many words each text role weighs, the pairs."""
    roles = {p: v["similarity_weight"] for p, v in table.items() if not p.startswith("~") and "similarity_weight" in v}
    words = {p: len(v.get("value_weights", {})) for p, v in table.items() if not p.startswith("~") and p not in roles}
    pairs = [p.get("roles") or p.get("name") for p in table.get("~interactions", [])]
    return {"roles": roles, "words": words, "pairs": pairs}


def _tables(model: glyphh_spec.Model) -> Any:
    return (model.spec.interactions, glyphh_spec._word_tables(model.spec))


def _learn(
    base: PostgresStore, model: glyphh_spec.Model, spec: glyphh_spec.Spec, total: int, progress: Progress
) -> dict[str, Any]:
    """Learn, then restate what the kernel did not. The kernel keeps what it learned (meta `learned`) before it
    rewrites the store, so a job that died between left the store stated by the old tables under the new: the store
    is marked `restating` until the restatement ends, and a learn that finds it so restates every precedent."""
    dirty = bool(base.meta("restating"))
    base.set_meta("restating", True)
    before = _tables(model)
    try:
        learned = model.learn()
    except ValueError:  # refused before anything was learned: the store is as it was
        base.set_meta("restating", dirty)
        raise
    out: dict[str, Any] = {"learned": {k: summary(v) for k, v in learned.items()} if spec.outputs else summary(learned)}
    progress(60)
    changed = _tables(model) != before  # the kernel restated the precedents it holds (the newest JOB_SAMPLE)
    if dirty or (changed and total > limits.JOB_SAMPLE):
        held = model.space._at if changed else {}
        out["restated"] = restate_rest(base, model, lambda f: progress(60 + 30 * f), held)
    base.set_meta("restating", False)
    return out


def fit(
    conn: psycopg.Connection, schema: str, key: str, spec: glyphh_spec.Spec, kind: str, progress: Progress
) -> dict[str, Any]:
    """learn (then calibrate) or calibrate the store under this key, read through the spec; the job's result."""
    base = catalog.store(conn, schema, key, spec.dimension)
    total = base.count()
    model = glyphh_spec.Model(spec, store=Sampled(base, limits.JOB_SAMPLE))  # type: ignore[arg-type]
    model.refresh_every = None
    model.space.load()
    progress(30)
    out: dict[str, Any] = {"precedents": total, "sampled": min(total, limits.JOB_SAMPLE)}
    try:
        if kind == "learn":
            out.update(_learn(base, model, spec, total, progress))
        out["tau"] = model.calibrate()
    except ValueError as e:  # the spec's (SpecError, naming where), or too few cases to calibrate on
        raise Refusal("E_SPEC", str(e), 422, path=getattr(e, "path", "")) from None
    return json.loads(json.dumps(out, default=str))


def run(conn: psycopg.Connection, schema: str, name: str, kind: str, progress: Progress) -> dict[str, Any]:
    """learn or calibrate one model of the org, on its active version's store; the answer is the job's result."""
    found = catalog.live(conn, schema, name)
    return fit(conn, schema, found.store, glyphh_spec.Spec.from_json(found.spec), kind, progress)
