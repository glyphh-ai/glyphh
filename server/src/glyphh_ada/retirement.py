"""No model is left unanswerable when its Ada version retires (docs/specs/ada-cloud.md, 12.5). Once a version passes
its end date, the latest stable's job workers (process.py, at start and hourly) move every model whose active
version runs it to the latest stable: an upgrade (versions.upgrade), made by `ada-retirement` with the note "Moved
from ada-1-0 (retired) to ada-1-1", whose re-encode job runs on the latest stable's kernel. Until it ends the model
answers on its old kernel, which stays installed. A model busy with an import or another re-encode is moved at the
next sweep."""

import logging

from glyphh_ada import pg, registry, versions
from glyphh_ada.catalog import q
from glyphh_ada.errors import Refusal
from glyphh_ada.protocol import JOBS, STREAM_MAX, Message, kernel_stream
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.ada")
_ON = """
    SELECT m.name, v.ada FROM {s}.models m
    JOIN {s}.spec_versions v ON v.model_id = m.id AND v.version = m.active_version
    WHERE m.deleted_at IS NULL AND v.ada = ANY(%s) ORDER BY m.name
"""


def retired_names(reg: registry.Registry) -> list[str]:
    """Every name, aliases too, of the versions retired today."""
    day = registry.today()
    return [n for v in reg.versions if v.status(day) == "retired" for n in (v.name, *v.aliases)]


def sweep(ctx: object) -> int:
    """Every org's models on a retired version moved to the latest stable. Returns how many moves it started."""
    reg = registry.registry()
    names = retired_names(reg)
    if not names:
        return 0
    conn, redis = ctx.conn, ctx.redis  # type: ignore[attr-defined]
    latest = reg.latest(registry.today())
    found = conn.execute(r"SELECT nspname FROM pg_namespace WHERE nspname ~ '^ada_[0-9a-f]{32}$' ORDER BY 1")
    moved = 0
    for (schema,) in found.fetchall():
        org = pg.org_of(schema)
        pg.enter(conn, org)  # its schema was migrated at this worker's start: its models and versions are there
        for name, old in conn.execute(q(schema, _ON), (names,)).fetchall():
            note = f"Moved from {old} (retired) to {latest.name}"
            try:
                with conn.transaction():
                    made = versions.upgrade(
                        conn, schema, name, latest.name, {"author": registry.MOVED_BY, "note": note}
                    )
            except Refusal as r:  # busy (an import or a re-encode open): the next sweep
                log.warning("not moved yet", extra=fields(org=org, model=name, code=r.code))
                continue
            work = Message(org, name, "reencode", {"job": made["job"]}, author=registry.MOVED_BY)
            redis.xadd(kernel_stream(JOBS, latest.kernel), work.fields(), maxlen=STREAM_MAX, approximate=True)
            moved += 1
    return moved
