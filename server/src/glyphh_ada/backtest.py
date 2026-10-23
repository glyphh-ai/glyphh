"""A backtest, as a job (docs/specs/ada-cloud.md, 5.3): candidate settings or specs scored on the model's own
held-out precedents before any goes live; the live version is never touched (its store is only read).

The model's graded precedents (the newest limits.JOB_SAMPLE) are split: the held-out ones (the newest `n`, or a seeded
`fraction`) and the rest. For the active version and each candidate (up to limits.CANDIDATES_MAX: settings changed on
the active version, another version, or a whole spec), an in-memory model of the rest learns and calibrates, as the
live one would, then decides every held-out case. Each answers: accuracy (of decide's outcome, and of the vote's top),
log-loss, the cost by the output's costs when it has them, how often it asks a person and its accuracy where it
does not, coverage (a sufficient vote), calibration (the expected calibration error over ten bins of confidence), the
mistakes it makes (truth: {decided: count}), and each number's change against the active version.

A candidate may name an Ada version (`ada`, docs/specs/ada-cloud.md 12.6): it is learned, calibrated and scored by
that version's kernel. A job worker scores the candidates of its own kernel and hands the job on (Handoff) to the next
kernel's, with the split it made, until every candidate is scored; the last one compares them."""

import json
import random
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import glyphh_spec
import psycopg
from glyphh_postgres import PostgresStore

from glyphh_ada import catalog, limits, registry, routing, versions
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
    """A candidate's spec: the active one with settings changed, another version's, one given whole, or the active
    one as it is (a candidate naming only an Ada version)."""
    active = glyphh_spec.Spec.from_json(found.spec)
    try:
        if not {"settings", "spec_version", "spec"} & set(candidate):
            spec = active
        elif "settings" in candidate:
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


class Handoff(Exception):  # noqa: N818: not an error, the job passed on
    """The candidates this kernel could score are scored (`partial`); the rest are another kernel's: the job goes on
    on that kernel's jobs stream (process.py), with the cases it held out, so every candidate is scored on the same
    split."""

    def __init__(self, kernel: str, partial: dict[str, Any]) -> None:
        super().__init__(kernel)
        self.kernel, self.partial = kernel, partial


def ada_of(found: catalog.Live, candidate: dict[str, Any]) -> registry.Version:
    """The Ada version a candidate is scored on: its own `ada`, else the active version's. A retired or unknown one is
    refused (each candidate's own refusal)."""
    reg, name = registry.registry(), candidate.get("ada") or found.ada
    known = reg.find(name)
    latest = reg.latest(registry.today()).name
    if known is None:
        raise Refusal("E_ADA_UNKNOWN", f"There is no Ada version {name}.", 422, ada=name, latest=latest)
    if known.status(registry.today()) == "retired" and name != found.ada:
        raise Refusal("E_ADA_RETIRED", f"{name} was retired.", 410, ada=name, latest=latest)
    return known


def _split(store: PostgresStore, args: dict[str, Any], partial: dict[str, Any]) -> tuple[list[Case], list[Any]]:
    """The split: made here on the first kernel, the same cases again (by id) on each kernel after."""
    output = args.get("output") or "default"
    found = cases(store)
    if "held" not in partial:
        return split(found, output, args.get("holdout") or {"newest": 200})
    by = {c[0]: c for c in found}
    train = [by[i] for i in partial["train"] if i in by]
    held = [(by[i], _truth(by[i], output)) for i in partial["held"] if i in by]
    return train, held


def run(conn: psycopg.Connection, schema: str, job: dict[str, Any], progress: Progress, kernel: str) -> dict[str, Any]:
    args, partial = job["args"], dict(job.get("result") or {})
    found = catalog.live(conn, schema, job["model"])
    dim = glyphh_spec.Spec.from_json(found.spec).dimension
    store = PostgresStore(conn, schema, found.store, dim=dim, readonly=True)
    output, clearance = args.get("output") or "default", float(args.get("clearance", 1.0))
    train, held = _split(store, args, partial)
    if not held:
        raise Refusal("E_BACKTEST", "The model has no graded precedents to hold out for this output.", 422)
    runs = [{"name": "active", "settings": {}}, *list(args["candidates"])]
    done: dict[int, Any] = {int(i): r for i, r in (partial.get("done") or {}).items()}
    kernels: dict[int, str] = {}
    for n, candidate in enumerate(runs):
        if n in done:
            continue
        try:
            ada = ada_of(found, candidate)
            routing.check(ada.kernel)
            kernels[n] = ada.kernel
            if ada.kernel != kernel:
                continue
            spec = spec_of(conn, schema, found, candidate)
            model, notes = build(spec, train)
            done[n] = {"candidate": candidate, "ada": ada.name, **notes, **score(model, held, output, clearance)}
        except Refusal as r:
            error = {"code": r.code, "message": r.message, **r.detail}
            done[n] = {"candidate": candidate, "ada": candidate.get("ada") or found.ada, "error": error}
        progress(100 * len(done) / len(runs))
    left = sorted({kernels[n] for n in range(len(runs)) if n not in done})
    if left:
        ids = {"train": [c[0] for c in train], "held": [c[0] for c, _ in held]}
        raise Handoff(left[0], {"done": done, **ids, "next": left[0]})
    return {
        "version": found.version,
        "ada": found.ada,
        "trained": len(train),
        "held_out": len(held),
        "output": output,
        **compare([done[n] for n in range(len(runs))]),
    }
