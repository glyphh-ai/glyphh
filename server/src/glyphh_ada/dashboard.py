"""What the platform's dashboard reads of a model in its store (worker side, a look: nothing counted against the
month): its active version, its precedents by outcome (each named output's too: the most common, and the rest
together), how many it holds by the day of each case (its time: the data's, or when it was recorded; UTC), and its
latest jobs. Its reads by day are the API's (days.py).

A page load stays cheap however big the model: up to EXACT_MAX precedents the outcomes and days are counted, past it
they are estimated from a fixed sample of about SAMPLE precedents (Postgres's block sampling, the same blocks each
time), scaled to the model's count (`estimated`: true). The precedents held are the store's own count, always exact."""

from datetime import UTC, datetime
from typing import Any

import psycopg

from glyphh_ada import catalog
from glyphh_ada.catalog import q
from glyphh_ada.jobs import _KEYS

OUTCOMES_MAX: int = 50  # the most common outcomes of each output; the rest are counted together
JOBS_SHOWN: int = 8
EXACT_MAX: int = 100_000  # past this many precedents, outcomes and days are estimated from a sample
SAMPLE: int = 20_000

_VERSION = "SELECT note, made_by, made_at FROM {s}.spec_versions WHERE model_id = %s AND version = %s"
# Each output's values by how many precedents have them, the top `top` apart and the rest together (shown false):
# the default output's from the precedents (null: ungraded), the named outputs' from their outcomes.
_OUTCOMES = """
    SELECT output, CASE WHEN rank <= %(top)s THEN value END, rank <= %(top)s AS shown, sum(n)::bigint, count(*)
    FROM (SELECT output, value, n, row_number() OVER (PARTITION BY output ORDER BY n DESC, value) AS rank FROM (
        SELECT NULL::text AS output, nullif(outcome, '') AS value, count(*) AS n
            FROM {s}.precedents{sample} WHERE model = %(m)s GROUP BY 2
        UNION ALL
        SELECT output, value, count(*) FROM {s}.outcomes{sample} WHERE model = %(m)s GROUP BY 1, 2) c) t
    GROUP BY 1, 2, 3 ORDER BY 1 NULLS FIRST, 3 DESC, 4 DESC, 2
"""
_GROWTH = (
    "SELECT floor(ts / 86400)::bigint, count(*) FROM {s}.precedents{sample} WHERE model = %s GROUP BY 1 ORDER BY 1"
)
_JOBS = """
    SELECT j.id, m.name, j.kind, j.state, j.percent, j.args, j.result, j.error, j.created_at, j.started_at,
           j.finished_at, j.made_by, j.stage FROM {s}.jobs j JOIN {s}.models m ON m.id = j.model_id
    WHERE j.model_id = %s ORDER BY j.created_at DESC LIMIT %s
"""


def _day(n: int) -> str:
    return datetime.fromtimestamp(n * 86400, UTC).date().isoformat()


def _sampled(text: str, held: int) -> tuple[str, float]:
    """The statement reading every precedent, or a sample of about SAMPLE once there are more than EXACT_MAX; and
    what each counted row stands for."""
    if held <= EXACT_MAX:
        return text.replace("{sample}", ""), 1.0
    percent = min(100.0, 100 * SAMPLE / held)
    return text.replace("{sample}", f" TABLESAMPLE SYSTEM ({percent:.6f}) REPEATABLE (7)"), 100 / percent


def stats(conn: psycopg.Connection, schema: str, name: str) -> dict[str, Any]:
    """The model's name, active version, precedents and when it was made, with `active` (its active version's note,
    maker and time), `outcomes` ([{output: null for the default, value: null for ungraded, n}], the OUTCOMES_MAX
    most common of each output), `others` ([{output, values, n}]: each output's other values, how many and how many
    precedents have them), `growth` ([{day, n}], by the cases' days), `estimated` (outcomes and growth from a sample)
    and `jobs` (its latest, newest first)."""
    found = catalog.live(conn, schema, name)
    note, made_by, made_at = conn.execute(q(schema, _VERSION), (found.id, found.version)).fetchone()  # type: ignore[misc]
    held = catalog.count(conn, schema, found.store)
    outcomes_sql, scale = _sampled(_OUTCOMES, held)
    counted = conn.execute(q(schema, outcomes_sql), {"m": found.store, "top": OUTCOMES_MAX}).fetchall()
    growth_sql, _ = _sampled(_GROWTH, held)
    growth = conn.execute(q(schema, growth_sql), (found.store,)).fetchall()
    jobs = conn.execute(q(schema, _JOBS), (found.id, JOBS_SHOWN)).fetchall()
    return {
        "name": name,
        "version": found.version,
        "precedents": held,
        "created_at": found.made,
        "active": {"version": found.version, "note": note, "made_by": made_by, "made_at": made_at},
        "outcomes": [{"output": o, "value": v, "n": round(n * scale)} for o, v, shown, n, _ in counted if shown],
        "others": [{"output": o, "values": k, "n": round(n * scale)} for o, _, shown, n, k in counted if not shown],
        "growth": [{"day": _day(d), "n": round(n * scale)} for d, n in growth],
        "estimated": held > EXACT_MAX,
        "jobs": [dict(zip(_KEYS, j, strict=True)) for j in jobs],
    }
