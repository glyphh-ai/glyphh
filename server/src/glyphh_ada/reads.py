"""The reads a worker answers: query, probabilities, facts and decide, the kernel's own (glyphh_spec.Model), each one
shortlist of the store re-ranked exactly (a model under exact_below precedents is read whole).

A query that gives under half the roles that vote, on a model of more than limits.FEW_ROLES_ABOVE precedents, is
refused (422 E_FEW_ROLES) rather than answered from a shortlist that misses most of the exact top (kernel 3.12's
benchmarks); an exact read of such a model takes minutes and gigabytes, so it is not offered in a request."""

from typing import Any

import glyphh_spec

from glyphh_ada import limits
from glyphh_ada.errors import Refusal


def _few_roles(model: glyphh_spec.Model, data: Any) -> None:
    if len(model) <= limits.FEW_ROLES_ABOVE:
        return
    voting = limits.voting_roles(model.spec)
    given = limits.given_roles(model.spec.situation(data)) & set(voting)
    if 2 * len(given) < len(voting):
        raise Refusal(
            "E_FEW_ROLES",
            f"This model holds over {limits.FEW_ROLES_ABOVE:,} precedents, and a query giving {len(given)} of its "
            f"{len(voting)} voting roles is answered badly from a shortlist: give at least half of them.",
            422,
            given=sorted(given),
            roles=voting,
        )


def _pinned(model: glyphh_spec.Model, output: str, data: Any, clearance: float) -> Any:
    """The read's candidates fetched once, for every kernel call this request makes about this output."""
    reader = model._reader(model._name(output), data, clearance)
    model._reader = lambda *_: reader  # type: ignore[method-assign]
    return reader


def _decide_one(model: glyphh_spec.Model, data: Any, clearance: float, output: str, facts: bool) -> dict[str, Any]:
    _pinned(model, output, data, clearance)
    try:
        out = model.decide(data, clearance, output)
        out["receipts"] = model.query(data, clearance, output).to_json()["receipts"]
        if facts:
            out["facts"] = model.facts(data, clearance, top=1, output=output)
    finally:
        del model._reader
    return out


def decide(model: glyphh_spec.Model, args: dict[str, Any], clearance: float) -> dict[str, Any]:
    """The headline: the outcome of least expected cost, the probabilities, whether to ask a person, and the
    precedents it stands on; `outputs` decides several of the model's outputs at once."""
    data, facts = args["data"], "facts" in (args.get("include") or [])
    if args.get("outputs") is not None:
        names = [model._name(o) for o in args["outputs"]]
        return {"outputs": {name: _decide_one(model, data, clearance, name, facts) for name in names}}
    return _decide_one(model, data, clearance, model._name(args.get("output")), facts)


def read(model: glyphh_spec.Model, op: str, args: dict[str, Any], clearance: float) -> Any:
    data, output = args["data"], args.get("output")
    try:
        _few_roles(model, data)
        if op == "query":
            return model.query(data, clearance, output).to_json()
        if op == "probabilities":
            return {k: round(v, 4) for k, v in model.probabilities(data, clearance, output).items()}
        if op == "facts":
            top, least = args.get("top"), args.get("min_score")
            return model.facts(data, clearance, top=top, min_score=least, output=output)
        return decide(model, args, clearance)
    except glyphh_spec.SpecError as e:
        raise Refusal("E_SPEC", str(e), 422, path=e.path) from None
