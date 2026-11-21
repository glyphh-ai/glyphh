"""The bounds on a request and on a spec (docs/specs/ada-cloud.md, 3.6), and the thresholds kernel 3.12's benchmarks
set (ada-private bench/results.txt): what a request may carry, what a model may be, when a read is refused rather than
answered badly, and how much of a model a job holds in memory."""

from typing import Any

from glyphh_ada.errors import BadRequest, Refusal

BODY_MAX: int = 1 << 20  # a request's body, bytes
RECORD_MANY_BODY_MAX: int = 5 << 20
RECORD_MANY_MAX: int = 1000  # cases in one record_many
FACTS_TOP_MAX: int = 50
SPEC_BYTES_MAX: int = 64 << 10  # a spec's JSON
NAME_PATTERN: str = r"^[a-z0-9][a-z0-9_.-]{0,62}$"

DIMENSION_MAX: int = 8192
ROLES_MAX: int = 64
OUTPUTS_MAX: int = 20
VALUES_MAX: int = 200
K_MAX: int = 200

# Shortlisted reads recall badly when a query gives few of the roles its records carry, and worse the bigger the
# model: at 1M precedents the exact top's recall within a shortlist of 1,000 is 33% for a query giving 2 of 7 roles
# (bench/results.txt). Above this many precedents such a read is refused, never answered from a poor shortlist.
FEW_ROLES_ABOVE: int = 100_000
# learn and calibrate load the newest this many precedents of a model, not all of them: a fully loaded 1M model
# needs about 16 GB (20 to 25 KB a precedent in a Space). A model this size or smaller learns exactly as rrotor does.
JOB_SAMPLE: int = 50_000

IMPORT_FORMATS: tuple[str, ...] = ("jsonl", "csv", "ada_sqlite")
EXPORT_FORMATS: tuple[str, ...] = ("jsonl", "ada_sqlite")
IMPORT_BODY_MAX: int = 5 << 20  # a file sent in the body of POST …/imports; larger ones go to the upload link
BATCH: int = 1000  # cases an import records, or a re-encode restates, in one transaction
REFUSALS_SHOWN: int = 100  # an import's first refused rows, each named
LINK_TTL: int = 3600  # seconds an upload or download link works
CHUNK: int = 1 << 20  # bytes of a file in one row of the org's `files`
CANDIDATES_MAX: int = 10  # a backtest's candidate settings or specs
HOPS_MAX: int = 32  # a beam's hops (POST /v1/beam), each one read
WIDTH_MAX: int = 50  # the values a beam carries from one hop to the next
KEPT_DAYS: int = 7  # an old version's partition is kept this long after it stops being active, for a rollback


def no_nul(value: Any, at: str = "body") -> None:
    """Postgres's jsonb refuses the NUL character (\\u0000) in any string: refused here, as a 400, before a worker."""
    if isinstance(value, str):
        if "\x00" in value:
            raise BadRequest("A string may not hold the NUL character (\\u0000).", reason="nul", at=at)
    elif isinstance(value, dict):
        for k, v in value.items():
            no_nul(k, at)
            no_nul(v, f"{at}.{k}")
    elif isinstance(value, list):
        for n, v in enumerate(value):
            no_nul(v, f"{at}[{n}]")


def _roles(spec: Any) -> list[Any]:
    return [r for layer in spec.layers for seg in layer.segments for r in seg.roles]


def check_spec(spec: Any) -> None:
    """A parsed spec (glyphh_spec.Spec) within the cloud's bounds, else E_SPEC_LIMIT naming the bound."""
    outputs = [spec.output, *(o for _, o in spec.outputs)]
    checks = (
        ("dimension", spec.dimension, DIMENSION_MAX),
        ("roles", len(_roles(spec)), ROLES_MAX),
        ("outputs", len(spec.outputs), OUTPUTS_MAX),
        ("values", max(len(o.values) for o in outputs), VALUES_MAX),
        ("settings.k", spec.settings.k, K_MAX),
    )
    for name, used, most in checks:
        if used > most:
            raise Refusal("E_SPEC_LIMIT", f"A cloud model's {name} is at most {most}.", 422, limit=name, max=most)


def voting_roles(spec: Any) -> list[str]:
    """The roles a query's answer weighs: every role but key parts and those weighing nothing, as layer.segment.role."""
    return [
        f"{layer.name}.{seg.name}.{r.name}"
        for layer in spec.layers
        for seg in layer.segments
        for r in seg.roles
        if not r.key_part and r.similarity_weight > 0
    ]


def given_roles(situation: dict[str, Any]) -> set[str]:
    return {f"{ln}.{sn}.{rn}" for ln, segs in situation.items() for sn, roles in segs.items() for rn in roles}
