"""The writes a worker makes for a request: record, record_many, grade and forget through the kernel's Model, each in
the transaction that also keeps its answer under the request's key (handlers.once), so a message taken again after
its worker died, or a request sent again with the same Idempotency-Key, is answered and never written twice."""

from typing import Any

import glyphh_spec
import psycopg

from glyphh_ada import catalog, limits
from glyphh_ada.errors import Refusal


def _kernel(fn: Any, *args: Any) -> Any:
    """A kernel call, its refusals as the API's: the spec's (E_SPEC, naming where), an id not held (404), a value
    the kernel will not take (E_INVALID)."""
    try:
        return fn(*args)
    except glyphh_spec.SpecError as e:
        raise Refusal("E_SPEC", str(e), 422, path=e.path) from None
    except KeyError as e:
        raise Refusal("E_PRECEDENT_MISSING", str(e.args[0]), 404) from None
    except ValueError as e:
        raise Refusal("E_INVALID", str(e), 422) from None


def record(model: glyphh_spec.Model, args: dict[str, Any]) -> dict[str, Any]:
    """One case, through record_many: the same checks and the same replace by key, without Model.record's count of
    every graded precedent (a scan of the partition), which only inline refresh needs."""
    case = {k: args[k] for k in ("data", "outcome", "outcomes", "ts") if args.get(k) is not None}
    done = _kernel(model.record_many, [case])
    return {"id": done["ids"][0], "precedents": done["precedents"]}


def record_many(model: glyphh_spec.Model, args: dict[str, Any]) -> dict[str, Any]:
    cases = args["cases"]
    if len(cases) > limits.RECORD_MANY_MAX:
        raise Refusal("E_LIMIT", f"record_many takes at most {limits.RECORD_MANY_MAX} cases.", 413, reason="cases")
    return dict(_kernel(model.record_many, cases))


def grade(model: glyphh_spec.Model, args: dict[str, Any]) -> dict[str, Any]:
    _kernel(model.grade, args["id"], args.get("output"), args.get("value"))
    return {"id": args["id"], "output": args.get("output") or "default", "value": args.get("value")}


def forget(model: glyphh_spec.Model, args: dict[str, Any]) -> dict[str, Any]:
    _kernel(model.forget, args["id"])
    return {"id": args["id"], "forgotten": True, "precedents": len(model)}


WRITERS = {"record": record, "record_many": record_many, "grade": grade, "forget": forget}


def adding(model: glyphh_spec.Model, cases: list[Any]) -> int:
    """How many precedents these cases would add: a case whose key parts name a held precedent replaces it."""
    keys: list[str | None] = []
    for case in cases:
        try:
            keys.append(model.spec.key(model.spec.situation(case["data"])))
        except (glyphh_spec.SpecError, KeyError, TypeError):  # the kernel refuses it when it is written
            keys.append(None)
    named = {k for k in keys if k}
    held = model.space.store.has_many(named) if named else set()  # type: ignore[union-attr]
    return keys.count(None) + len(named - held)


def within_cap(
    conn: psycopg.Connection, schema: str, model: glyphh_spec.Model, cases: list[Any], cap: int | None
) -> None:
    """Refused (403 E_LIMIT `precedents`) when these cases would take the org past its plan's cap."""
    if cap is None:
        return
    more = adding(model, cases)
    used = catalog.total(conn, schema)
    if more and used + more > cap:
        message = f"These cases add {more:,} precedents to the {used:,} the org holds: its plan allows {cap:,}."
        raise Refusal("E_LIMIT", message, 403, reason="precedents", used=used, max=cap, adding=more)


def refresh_due(model: glyphh_spec.Model, op: str, answer: dict[str, Any]) -> bool:
    """Whether this write took the model past a multiple of its refresh_every (precedents held, in the cloud)."""
    every = model.settings.refresh_every
    if not every or op not in ("record", "record_many"):
        return False
    added = answer.get("added", 1)
    return bool(added) and answer["precedents"] % every < added
