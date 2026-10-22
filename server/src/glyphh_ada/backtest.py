"""A backtest, as a job (docs/specs/ada-cloud.md, 5.3): candidate settings or specs scored on the model's own
held-out precedents before any goes live; the live version is never touched (its store is only read).

The model's graded precedents (the newest limits.JOB_SAMPLE) are split: the held-out ones (the newest `n`, or a seeded
`fraction`) and the rest. For the active version and each candidate (up to limits.CANDIDATES_MAX: settings changed on
the active version, another version, or a whole spec), an in-memory model of the rest learns and calibrates, as the
live one would, then decides every held-out case. Each answers: accuracy (of decide's outcome, and of the vote's top),
log-loss, the cost by the output's costs when it has them, how often it asks a person and its accuracy where it
does not, coverage (a sufficient vote), calibration (the expected calibration error over ten bins of confidence), the
mistakes it makes (truth: {decided: count}), and each number's change against the active version."""

import json
import random
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import glyphh_spec
import psycopg
from glyphh_postgres import PostgresStore

from glyphh_ada import catalog, limits, versions
from glyphh_ada.errors import Refusal
from glyphh_ada.sample import Sampled
from glyphh_ada.scoring import Scores, compare
from glyphh_ada.situations import check_reading, restated

Progress = Callable[[float], None]
Case = tuple[str, dict[str, Any], str | None, dict[str, str], float]  # id, situation, outcome, named, ts


class Held(glyphh_spec.Model):
    """A model that reads a stored situation (restated for its spec) where Model reads a caller's data."""

    def _reader(self, name: str, data: Any, clearance: float) -> tuple[Any, dict[str, Any], dict[str, Any]]:
        spec = self._spec_for(name)
        situation = restated(data, spec)
        return self._space_for(name), situation, spec.weights(clearance, situation)


def cases(store: PostgresStore) -> list[Case]:
    """The newest limits.JOB_SAMPLE precedents, oldest first, with their named outcomes."""
    sample = Sampled(store, limits.JOB_SAMPLE)
    rows = sample.rows()
    named: dict[str, dict[str, str]] = defaultdict(dict)
    for rid, output, value, _ in sample.named():
        named[rid][output] = value
    return [(r[0], json.loads(r[1]), r[2] or None, named.get(r[0], {}), r[6]) for r in rows]


def split(found: list[Case], output: str, holdout: dict[str, Any]) -> tuple[list[Case], list[tuple[Case, str]]]:
    """(the cases to learn from, the held-out graded cases with their truth)."""
    graded = [(c, _truth(c, output)) for c in found if _truth(c, output)]
    if "fraction" in holdout:
        random.Random(holdout.get("seed", 0)).shuffle(graded)
        held = graded[: round(len(graded) * float(holdout["fraction"]))]
    else:
        held = graded[len(graded) - int(holdout.get("newest", 200)) :]
    out = {c[0] for c, _ in held}
    return [c for c in found if c[0] not in out], held  # type: ignore[return-value]


def _truth(case: Case, output: str) -> str | None:
    return case[2] if output == "default" else case[3].get(output)


def spec_of(conn: psycopg.Connection, schema: str, found: catalog.Live, candidate: dict[str, Any]) -> glyphh_spec.Spec:
    """A candidate's spec: the active one with settings changed, another version's, or one given whole."""
    active = glyphh_spec.Spec.from_json(found.spec)
    try:
        if "settings" in candidate:
            spec = active.with_settings(active.settings.with_changes(candidate["settings"]))
        elif "spec_version" in candidate:
            spec = glyphh_spec.Spec.from_json(versions.row(conn, schema, found, int(candidate["spec_version"]))[0])
        else:
            spec = catalog.parse(candidate["spec"])
    except glyphh_spec.SpecError as e:
        raise Refusal("E_SPEC", str(e), 422, path=e.path) from None
    check_reading(active, spec, at="candidate")
    return spec


def build(spec: glyphh_spec.Spec, train: list[Case]) -> tuple[Held, dict[str, Any]]:
    """An in-memory model of the cases to learn from, learned and calibrated as the live one would be."""
    model = Held(spec, author="backtest")
    model.refresh_every = None
    model.space.record_many(
        [
            {"situation": restated(s, spec), "outcome": o, "outcomes": n or None, "rid": i, "ts": t}
            for i, s, o, n, t in train
        ]
    )
    notes: dict[str, Any] = {}
    for step in ("learn", "calibrate"):
        try:
            getattr(model, step)()
            notes[step] = True
        except ValueError as e:  # too few to learn or calibrate from: scored as it stands
            notes[step] = str(e)
    return model, notes


def score(model: Held, held: list[tuple[Case, str]], output: str, clearance: float) -> dict[str, Any]:
    scores = Scores(model.spec.output_of(output))
    for case, truth in held:
        decided = model.decide(case[1], clearance, output)
        voted = model.query(case[1], clearance, output)
        scores.add(decided, voted, truth)
    return scores.result()


def run(conn: psycopg.Connection, schema: str, job: dict[str, Any], progress: Progress) -> dict[str, Any]:
    args = job["args"]
    found = catalog.live(conn, schema, job["model"])
    dim = glyphh_spec.Spec.from_json(found.spec).dimension
    store = PostgresStore(conn, schema, found.store, dim=dim, readonly=True)
    output, clearance = args.get("output") or "default", float(args.get("clearance", 1.0))
    train, held = split(cases(store), output, args.get("holdout") or {"newest": 200})
    if not held:
        raise Refusal("E_BACKTEST", "The model has no graded precedents to hold out for this output.", 422)
    runs = [{"name": "active", "settings": {}}, *list(args["candidates"])]
    results = []
    for n, candidate in enumerate(runs):
        try:
            spec = spec_of(conn, schema, found, candidate)
            model, notes = build(spec, train)
            results.append({"candidate": candidate, **notes, **score(model, held, output, clearance)})
        except Refusal as r:
            results.append({"candidate": candidate, "error": {"code": r.code, "message": r.message, **r.detail}})
        progress(100 * (n + 1) / len(runs))
    return {
        "version": found.version,
        "trained": len(train),
        "held_out": len(held),
        "output": output,
        **compare(results),
    }
