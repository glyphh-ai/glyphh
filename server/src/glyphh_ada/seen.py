"""A model's stored cases as a reader may see them (worker side, a look: nothing counted against the month): one
precedent by its id, for the platform's 3D view, with every role, segment and layer its reader's clearance may not
see cut away (a pair of roles goes when either of its roles would), as the kernel cuts a fact tree."""

from typing import Any

import glyphh_spec
import psycopg

from glyphh_ada.catalog import Live, q
from glyphh_ada.errors import Refusal

_ONE = "SELECT id, situation, outcome, author, ts FROM {s}.precedents WHERE model = %s AND id = %s"
_NAMED = "SELECT output, value FROM {s}.outcomes WHERE model = %s AND id = %s ORDER BY output"


def readable(spec: glyphh_spec.Spec, clearance: float) -> None:
    """A model above the reader's clearance is refused, as its reads are (422 E_SPEC)."""
    try:
        spec.weights(clearance)
    except glyphh_spec.SpecError as e:
        raise Refusal("E_SPEC", str(e), 422, path=e.path) from None


def _pairs(spec: glyphh_spec.Spec, pairs: dict[str, Any], clearance: float) -> dict[str, Any]:
    roles = {i.name: i.roles for i in spec.interactions}
    return {
        name: v
        for name, v in pairs.items()
        if name in roles and all(spec._security_of(r) <= clearance for r in roles[name])
    }


def visible(spec: glyphh_spec.Spec, situation: dict[str, Any], clearance: float) -> dict[str, Any]:
    """The situation with what this clearance may not see cut away; empty parts are left out."""
    out: dict[str, Any] = {}
    for lname, segs in situation.items():
        if lname == glyphh_spec.INTERACTIONS:
            kept = {"pairs": _pairs(spec, segs.get("pairs", {}), clearance)}
        else:
            kept = {
                sname: {r: v for r, v in roles.items() if spec._security_of(f"{lname}.{sname}.{r}") <= clearance}
                for sname, roles in segs.items()
            }
        kept = {k: v for k, v in kept.items() if v}
        if kept:
            out[lname] = kept
    return out


def precedent(conn: psycopg.Connection, schema: str, found: Live, rid: str, clearance: float) -> dict[str, Any]:
    """One precedent of the model's active store: its case (as stored, in the kernel's terms), its outcome (null
    when ungraded), each named output's, who recorded it and when (epoch seconds)."""
    spec = glyphh_spec.Spec.from_json(found.spec)
    readable(spec, clearance)
    row = conn.execute(q(schema, _ONE), (found.store, rid)).fetchone()
    if row is None:
        raise Refusal("E_PRECEDENT_MISSING", f"This model holds no precedent {rid}.", 404, id=rid)
    named = dict(conn.execute(q(schema, _NAMED), (found.store, rid)).fetchall())
    return {
        "id": row[0],
        "situation": visible(spec, row[1], clearance),
        "outcome": row[2] or None,
        "outcomes": named,
        "author": row[3],
        "ts": row[4],
    }
