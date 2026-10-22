"""What the platform's dashboard reads of a model in its store (worker side, a look: nothing counted against the
month): its active version, its precedents by outcome (each named output's too), how many it holds by the day of
each case (its time: the data's, or when it was recorded; UTC), and its latest jobs. Its reads by day are the API's
(days.py)."""

from datetime import UTC, datetime
from typing import Any

import psycopg

from glyphh_ada import catalog
from glyphh_ada.catalog import q
from glyphh_ada.jobs import _KEYS

OUTCOMES_MAX: int = 50  # the most common outcomes, of each output
JOBS_SHOWN: int = 8

_VERSION = "SELECT note, made_by, made_at FROM {s}.spec_versions WHERE model_id = %s AND version = %s"
_OUTCOMES = """
    SELECT NULL, nullif(outcome, ''), count(*) FROM {s}.precedents WHERE model = %(m)s
    GROUP BY 2 ORDER BY 3 DESC, 2 LIMIT %(top)s
"""
_NAMED = """
    SELECT output, value, n FROM (SELECT output, value, count(*) AS n,
        row_number() OVER (PARTITION BY output ORDER BY count(*) DESC, value) AS rank
        FROM {s}.outcomes WHERE model = %(m)s GROUP BY output, value) t
    WHERE rank <= %(top)s ORDER BY output, n DESC, value
"""
_GROWTH = "SELECT floor(ts / 86400)::bigint, count(*) FROM {s}.precedents WHERE model = %s GROUP BY 1 ORDER BY 1"
_JOBS = """
    SELECT j.id, m.name, j.kind, j.state, j.percent, j.args, j.result, j.error, j.created_at, j.started_at,
           j.finished_at, j.made_by FROM {s}.jobs j JOIN {s}.models m ON m.id = j.model_id
    WHERE j.model_id = %s ORDER BY j.created_at DESC LIMIT %s
"""


def _day(n: int) -> str:
    return datetime.fromtimestamp(n * 86400, UTC).date().isoformat()


def stats(conn: psycopg.Connection, schema: str, name: str) -> dict[str, Any]:
    """The model's name, active version, precedents and when it was made, with `active` (its active version's note,
    maker and time), `outcomes` ([{output: null for the default, value: null for ungraded, n}]), `growth` ([{day,
    n}], by the cases' days) and `jobs` (its latest, newest first)."""
    found = catalog.live(conn, schema, name)
    note, made_by, made_at = conn.execute(q(schema, _VERSION), (found.id, found.version)).fetchone()  # type: ignore[misc]
    args = {"m": found.store, "top": OUTCOMES_MAX}
    outcomes = conn.execute(q(schema, _OUTCOMES), args).fetchall() + conn.execute(q(schema, _NAMED), args).fetchall()
    growth = conn.execute(q(schema, _GROWTH), (found.store,)).fetchall()
    jobs = conn.execute(q(schema, _JOBS), (found.id, JOBS_SHOWN)).fetchall()
    return {
        "name": name,
        "version": found.version,
        "precedents": catalog.count(conn, schema, found.store),
        "created_at": found.made,
        "active": {"version": found.version, "note": note, "made_by": made_by, "made_at": made_at},
        "outcomes": [{"output": o, "value": v, "n": n} for o, v, n in outcomes],
        "growth": [{"day": _day(d), "n": n} for d, n in growth],
        "jobs": [dict(zip(_KEYS, j, strict=True)) for j in jobs],
    }
