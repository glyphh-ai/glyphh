"""An org's Ada schema made straight in Postgres for the staff view's tests: its real tables (glyphh_ada/orgschema.py),
the kernel's `counts` beside them, and models, versions and jobs written as the org, through row-level security."""

import json
import uuid
from datetime import datetime
from typing import Any

import psycopg

from glyphh_ada import orgschema, pg
from tests.conftest import DATABASE_URL


def ada_org(org_id: uuid.UUID, models: list[dict[str, Any]], jobs: list[dict[str, Any]] | None = None) -> None:
    """Each model: name, precedents, and optionally created_at, deleted (bool), ada and kernel (columns the Ada
    versions add); each job: kind, state, seconds (or None), model (a model's name)."""
    org = str(org_id)
    with psycopg.connect(pg.libpq_url(DATABASE_URL), autocommit=True) as conn:
        schema = orgschema.ensure(conn, org)
        s = f'"{schema}"'
        with conn.transaction():
            orgschema.lock(conn, schema, org)
            conn.execute(f"CREATE TABLE IF NOT EXISTS {s}.counts (model text PRIMARY KEY, n bigint NOT NULL)")
            if any("ada" in m for m in models):
                conn.execute(f"ALTER TABLE {s}.spec_versions ADD COLUMN IF NOT EXISTS ada text")
                conn.execute(f"ALTER TABLE {s}.spec_versions ADD COLUMN IF NOT EXISTS kernel text")
            orgschema.fence(conn, schema, org)
        pg.enter(conn, org)
        ids = {m["name"]: _model(conn, s, m) for m in models}
        for job in jobs or []:
            _job(conn, s, ids[job["model"]], job)


def _model(conn: psycopg.Connection, s: str, m: dict[str, Any]) -> uuid.UUID:
    model_id, store = uuid.uuid4(), uuid.uuid4().hex
    made = m.get("created_at") or datetime.now().astimezone()
    deleted = made if m.get("deleted") else None
    conn.execute(
        f"INSERT INTO {s}.models (id, name, created_by, created_at, deleted_at) VALUES (%s, %s, 'test', %s, %s)",
        (model_id, m["name"], made, deleted),
    )
    extra = ", ada, kernel" if "ada" in m else ""
    values = ", %s, %s" if "ada" in m else ""
    args = (model_id, json.dumps({"secret": "never shown"}), store) + (
        (m["ada"], m.get("kernel")) if "ada" in m else ()
    )
    columns = f"model_id, version, spec, made_by, store{extra}"
    conn.execute(f"INSERT INTO {s}.spec_versions ({columns}) VALUES (%s, 1, %s, 't', %s{values})", args)
    conn.execute(f"INSERT INTO {s}.counts (model, n) VALUES (%s, %s)", (store, m["precedents"]))
    return model_id


def _job(conn: psycopg.Connection, s: str, model_id: uuid.UUID, job: dict[str, Any]) -> None:
    seconds = job.get("seconds")
    ends = "now()" if seconds is not None else "NULL"
    conn.execute(
        f"""INSERT INTO {s}.jobs (id, model_id, kind, state, made_by, args, started_at, finished_at)
        VALUES (%s, %s, %s, %s, 't', %s, now() - make_interval(secs => %s), {ends})""",
        (uuid.uuid4(), model_id, job["kind"], job["state"], json.dumps({"file": "never shown"}), seconds or 0),
    )
