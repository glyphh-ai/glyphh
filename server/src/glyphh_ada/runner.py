"""What a job worker runs for each kind of job: learn and calibrate (jobs.py), an import (importer.py), an export
(export.py), a re-encode or a rollback across stores (reencode.py), a backtest (backtest.py). Each answers its job's
result; `bump` moves the model's version counter (a re-encode moves it itself, at its switch)."""

from collections.abc import Callable
from typing import Any

import psycopg

from glyphh_ada import backtest, export, importer, jobs, reencode

Progress = Callable[[float], None]


def run(
    conn: psycopg.Connection, schema: str, job: dict[str, Any], progress: Progress, bump: Callable[[], None]
) -> dict[str, Any]:
    kind = job["kind"]
    if kind in ("learn", "calibrate"):
        return jobs.run(conn, schema, job["model"], kind, progress)
    if kind == "reencode":
        return reencode.run(conn, schema, job, progress, bump)
    return {"import": importer.run, "export": export.run, "backtest": backtest.run}[kind](conn, schema, job, progress)
