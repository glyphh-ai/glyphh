"""A model's versions (docs/specs/ada-cloud.md, 5.2): the spec is the only truth, so every change of the spec or of a
setting is a new version, kept with who made it and why; one is active.

A change that reads the stored cases as they are (the levers of a read: k, min_sim, word_evidence, shortlist,
exact_below, refresh_every; outputs, costs and asking; weights and security; the calibration's levers) makes the
new version active at once, on the same store: its learned weights and temperatures go on (recalibrated in a job when
the calibration's levers moved). A change of what a stored case carries (the seed, the dimension, roles, declared
pairs, the learning levers, the lexicon) is a re-encode job (reencode.py), which writes a new store beside the old one
while the old one serves, learns, and then makes the version active. A change of how a role reads its values is
refused (situations.check_reading).

Each version keeps, when it stops being active, the learned weights and temperatures it had (`learned`), so making it
active again restores them without learning: at once when it reads the active store; else as a job that brings its
own store up to date with every write made since (reencode.py, `sync`). A store no version has read for
limits.KEPT_DAYS is dropped (prune), and its versions can no longer be made active (410 E_VERSION_GONE)."""

from typing import Any

import glyphh_spec
import psycopg
from psycopg.types.json import Jsonb

from glyphh_ada import catalog, jobs, limits
from glyphh_ada.catalog import q
from glyphh_ada.errors import Refusal
from glyphh_ada.situations import check_reading, learned_of, same_store, set_learned

CALIBRATION: tuple[str, ...] = ("calibrate_by", "calibrate_sample")
_LIST = """
    SELECT v.version, v.note, v.made_by, v.made_at, v.version = m.active_version, v.store, v.backtest, v.ready,
           v.gone, v.retired_at FROM {s}.spec_versions v JOIN {s}.models m ON m.id = v.model_id
    WHERE v.model_id = %s ORDER BY v.version
"""
_ROW = "SELECT spec, store, ready, gone, learned FROM {s}.spec_versions WHERE model_id = %s AND version = %s"
_STALE = """
    SELECT store FROM {s}.spec_versions v WHERE model_id = %(m)s AND NOT gone AND store <> %(keep)s GROUP BY store
    HAVING bool_and(version <> %(active)s AND (NOT ready OR retired_at < now() - make_interval(days => %(days)s)))
"""


def write_lock(schema: str, name: str) -> str:
    """The advisory lock every write to a model's cases holds shared, and a switch of its store holds alone."""
    return f"glyphh:write:{schema}:{name}"


def listing(conn: psycopg.Connection, schema: str, name: str) -> list[dict[str, Any]]:
    found = catalog.live(conn, schema, name)
    keys = ("version", "note", "made_by", "made_at", "active", "store", "backtest", "ready", "gone", "retired_at")
    rows = [dict(zip(keys, r, strict=True)) for r in conn.execute(q(schema, _LIST), (found.id,)).fetchall()]
    for row in rows:
        row["reencoded"] = row.pop("store") != found.id.hex
    return rows


def row(conn: psycopg.Connection, schema: str, found: catalog.Live, version: int) -> tuple[Any, ...]:
    got = conn.execute(q(schema, _ROW), (found.id, version)).fetchone()
    if got is None:
        raise Refusal("E_VERSION_MISSING", f"This model has no version {version}.", 404, version=version)
    return tuple(got)


def retire(conn: psycopg.Connection, schema: str, found: catalog.Live) -> None:
    """The active version keeps what its store learned, and when it stopped being active."""
    kept = learned_of(conn, schema, found.store)
    update = "UPDATE {s}.spec_versions SET learned = %s, retired_at = now() WHERE model_id = %s AND version = %s"
    conn.execute(q(schema, update), (Jsonb(kept), found.id, found.version))


def make_active(conn: psycopg.Connection, schema: str, found: catalog.Live, version: int) -> None:
    conn.execute(q(schema, "UPDATE {s}.models SET active_version = %s WHERE id = %s"), (version, found.id))
    conn.execute(
        q(schema, "UPDATE {s}.spec_versions SET ready = true WHERE model_id = %s AND version = %s"), (found.id, version)
    )


def _insert(
    conn: psycopg.Connection, schema: str, found: catalog.Live, spec_json: Any, args: dict[str, Any], same: bool
) -> int:
    """The next version: on the active store (ready), or on a store of its own that a re-encode will make."""
    top = conn.execute(q(schema, "SELECT max(version) FROM {s}.spec_versions WHERE model_id = %s"), (found.id,))
    version = int(top.fetchone()[0]) + 1  # type: ignore[index]
    insert = (
        "INSERT INTO {s}.spec_versions (model_id, version, spec, note, made_by, store, backtest, ready)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )
    store = found.store if same else f"{found.id.hex}v{version}"
    note, backtest = args.get("note") or "", args.get("backtest")
    conn.execute(q(schema, insert), (found.id, version, Jsonb(spec_json), note, args["author"], store, backtest, same))
    return version


def _recalibrates(old: glyphh_spec.Spec, new: glyphh_spec.Spec) -> bool:
    moved = any(getattr(old.settings, k) != getattr(new.settings, k) for k in CALIBRATION)
    costs = new.settings.calibrate_by == "cost" and (old.output, old.outputs) != (new.output, new.outputs)
    return moved or costs


def propose(conn: psycopg.Connection, schema: str, name: str, spec_json: Any, args: dict[str, Any]) -> dict[str, Any]:
    """A new version from this spec. Returns {version, active, job}: active at once, or after the job (a re-encode;
    or a calibration, the version active already)."""
    found = catalog.live(conn, schema, name)
    new, old = catalog.parse(spec_json), glyphh_spec.Spec.from_json(found.spec)
    if new.to_json() == old.to_json():
        raise Refusal(
            "E_NO_CHANGE", "This spec is the active version's: nothing to change.", 409, version=found.version
        )
    check_reading(old, new)
    jobs.busy(conn, schema, found.id)
    if not same_store(old, new):
        version = _insert(conn, schema, found, spec_json, args, same=False)
        job = jobs.add(conn, schema, found.id, "reencode", {"version": version}, args["author"])
        return {"version": version, "active": False, "job": job}
    version = _insert(conn, schema, found, spec_json, args, same=True)
    retire(conn, schema, found)
    make_active(conn, schema, found, version)
    held = learned_of(conn, schema, found.store)
    job = None
    if held and _recalibrates(old, new):
        job = jobs.add(conn, schema, found.id, "calibrate", {}, args["author"])
    return {"version": version, "active": True, "job": job}


def settings(
    conn: psycopg.Connection, schema: str, name: str, changes: dict[str, Any], args: dict[str, Any]
) -> dict[str, Any]:
    """A new version whose settings are the active version's with these changes (each checked by the kernel)."""
    found = catalog.live(conn, schema, name)
    current = glyphh_spec.Spec.from_json(found.spec).settings
    try:
        moved = current.with_changes(changes)
    except glyphh_spec.SpecError as e:
        raise Refusal("E_SPEC", str(e), 422, path=e.path) from None
    spec_json = {**found.spec, "settings": moved.to_json()}
    return propose(conn, schema, name, spec_json, args)


def levers(conn: psycopg.Connection, schema: str, name: str) -> dict[str, Any]:
    """Every lever as it stands on the active version."""
    found = catalog.live(conn, schema, name)
    return {"version": found.version, "settings": glyphh_spec.Spec.from_json(found.spec).settings.to_json(all=True)}


def activate(conn: psycopg.Connection, schema: str, name: str, version: int, author: str) -> dict[str, Any]:
    """Another version made active: at once on the active store (its learned state restored), else as a job."""
    found = catalog.live(conn, schema, name)
    if version == found.version:
        return {"version": version, "active": True, "job": None}
    _, store, ready, gone, learned = row(conn, schema, found, version)
    if gone:
        raise Refusal("E_VERSION_GONE", f"Version {version}'s store was dropped after {limits.KEPT_DAYS} days.", 410)
    if not ready:
        raise Refusal("E_NOT_READY", f"Version {version} is still being made: wait for its job.", 409)
    jobs.busy(conn, schema, found.id)
    if store != found.store:
        job = jobs.add(conn, schema, found.id, "reencode", {"version": version, "sync": True}, author)
        return {"version": version, "active": False, "job": job}
    retire(conn, schema, found)
    set_learned(
        conn, schema, store, learned or {}
    )  # what it had when it stopped being active (every ready version was)
    make_active(conn, schema, found, version)
    return {"version": version, "active": True, "job": None}


def prune(conn: psycopg.Connection, schema: str, found: catalog.Live, keep: str) -> list[str]:
    """Stores no version has read for limits.KEPT_DAYS, and those of versions a re-encode never finished (one runs at
    a time: the one in hand, whose store is `keep`), dropped, their versions marked gone. Returns them."""
    params = {"m": found.id, "active": found.version, "days": limits.KEPT_DAYS, "keep": keep}
    stale = [r[0] for r in conn.execute(q(schema, _STALE), params).fetchall()]
    for key in stale:
        catalog.drop_store(conn, schema, key)
        conn.execute(
            q(schema, "UPDATE {s}.spec_versions SET gone = true WHERE model_id = %s AND store = %s"), (found.id, key)
        )
    return stale
