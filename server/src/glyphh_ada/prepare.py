"""One imported case checked and put in the kernel's terms, as Model.record_many checks each of its cases, but alone, so
a bad row is refused by itself and the rest go in. A case's id is its key parts' (the spec's), else the id it gives,
else one made from the import's job and the row, so an import run twice (a worker died in it) writes each row once.
A case from a model's export is a stored situation, restated for this model."""

import hashlib
from typing import Any

import glyphh_kernel as kernel
import glyphh_spec

from glyphh_ada.situations import restated

FIELDS: frozenset[str] = frozenset({"data", "outcome", "outcomes", "ts", "id"})
ID_MAX: int = 200


def case_id(job: str, row: int) -> str:
    return hashlib.sha256(f"{job}:{row}".encode()).hexdigest()[:12]


def _given(value: Any, at: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str | int) or isinstance(value, bool) or not 0 < len(str(value)) <= ID_MAX:
        raise glyphh_spec.SpecError(at, f"an id is a string of 1 to {ID_MAX} characters")
    return str(value)


def _outcomes(model: glyphh_spec.Model, case: dict[str, Any]) -> tuple[str | None, dict[str, str]]:
    outcome, named = case.get("outcome"), case.get("outcomes") or {}
    if outcome is not None and (not isinstance(outcome, str) or not outcome):
        raise glyphh_spec.SpecError("outcome", "a non-empty string")
    if not isinstance(named, dict):
        raise glyphh_spec.SpecError("outcomes", "an object of {output: value}")
    for name, value in named.items():
        if isinstance(value, str):
            model.spec.check_outcome(model._name(name), value)
    try:
        kernel._named_outcomes(named)
    except ValueError as e:
        raise glyphh_spec.SpecError("outcomes", str(e)) from None
    return outcome, dict(named)


def _ts(value: Any) -> float | None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int | float)):
        raise glyphh_spec.SpecError("ts", "epoch seconds, a number")
    return value


def prepare(model: glyphh_spec.Model, case: dict[str, Any], job: str, row: int) -> dict[str, Any]:
    """The case as Space.record_many takes it; SpecError (path, message) when the spec refuses it."""
    unknown = set(case) - FIELDS
    if unknown or "data" not in case:
        raise glyphh_spec.SpecError("", f"a case is {{data, outcome?, outcomes?, ts?, id?}}: {sorted(unknown)}")
    outcome, named = _outcomes(model, case)
    situation = model.spec.situation(case["data"])
    ts = _ts(case.get("ts"))
    stamp = ts if ts is not None else model.spec.timestamp(case["data"])
    given = _given(case.get("id"), "id")  # a spec's key parts, when it has them, make the id instead
    rid = model.spec.key(situation) or given or case_id(job, row)
    return {"situation": situation, "outcome": outcome, "rid": rid, "ts": stamp, "outcomes": named or None}


def stored(model: glyphh_spec.Model, case: dict[str, Any]) -> dict[str, Any]:
    """A case from an export: its stored situation restated for this model, its id, outcomes and time kept."""
    if not isinstance(case.get("situation"), dict):
        raise glyphh_spec.SpecError("situation", "an export's case holds its situation")
    outcome, named = _outcomes(model, case)
    rid = _given(case.get("id"), "id")
    return {
        "situation": restated(case["situation"], model.spec),
        "outcome": outcome,
        "rid": rid,
        "ts": _ts(case.get("ts")),
        "outcomes": named or None,
        "author": str(case.get("author") or "") or None,  # imported.record writes it, then takes it out
    }
