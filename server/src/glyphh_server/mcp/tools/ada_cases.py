"""The connector's Ada case tools: recording what happened (one case, or up to 1,000 in one transaction), grading or
forgetting one, and asking: decide (the headline), query, probabilities and facts, each the kernel's own answer. A
read counts against the org's month (docs/specs/ada-cloud.md, section 7)."""

from typing import Any

from pydantic import Field

from glyphh_ada.api.cases import Case, Cases, Grade
from glyphh_ada.api.reads import Ask, DecideAsk, FactsAsk
from glyphh_server.mcp.panel import DECISION_URI
from glyphh_server.mcp.tools.ada_base import IDEMPOTENCY, NAME, Named, ada, args_of, pct
from glyphh_server.mcp.tools.base import Context, Done, Tool


class Record(Case):
    name: str = NAME
    idempotency_key: str | None = IDEMPOTENCY


class RecordMany(Cases):
    name: str = NAME
    idempotency_key: str | None = IDEMPOTENCY


class GradeArgs(Grade):
    name: str = NAME


class Forget(Named):
    id: str = Field(min_length=1, max_length=200, description="The case's id (record answers it)")


class AskArgs(Ask):
    name: str = NAME


class FactsArgs(FactsAsk):
    name: str = NAME


class DecideArgs(DecideAsk):
    name: str = NAME


async def record(ctx: Context, args: Record) -> Done:
    made, _v = await ada(ctx, args.name, "record", args_of(args), key=args.idempotency_key)
    return Done(f"Recorded {made['id']}: {args.name} holds {made['precedents']:,} precedents.", made)


async def record_many(ctx: Context, args: RecordMany) -> Done:
    made, _v = await ada(ctx, args.name, "record_many", args_of(args), key=args.idempotency_key)
    said = f"{made['added']:,} added, {made['replaced']:,} replaced: {args.name} holds {made['precedents']:,}."
    return Done(said, made)


async def grade(ctx: Context, args: GradeArgs) -> Done:
    made, _v = await ada(ctx, args.name, "grade", args.model_dump(exclude={"name"}))  # a null value takes it away
    return Done(f"Graded {args.id}: {args.value if args.value is not None else 'its outcome taken away'}.", made)


async def forget(ctx: Context, args: Forget) -> Done:
    gone, _v = await ada(ctx, args.name, "forget", {"id": args.id})
    return Done(f"Forgot {args.id}; what was learned from it stays until the next learn.", gone)


def _decided(name: str, d: dict[str, Any]) -> str:
    p = d.get("probabilities", {}).get(d.get("outcome"), 0.0)
    ask = "ask a person first" if d.get("ask") else "no need to ask"
    cost = d.get("expected_cost")
    costs = f", expected cost {cost:g}" if isinstance(cost, int | float) else ""
    return f"{name}: {d.get('outcome')} ({pct(p)}){costs}; {ask}."


async def decide(ctx: Context, args: DecideArgs) -> Done:
    answer, version = await ada(ctx, args.name, "decide", args_of(args), args.clearance)
    outputs = answer.get("outputs")
    lines = [_decided(n, d) for n, d in outputs.items()] if outputs else [_decided(args.name, answer)]
    teach = {"tool": "ada_record", "args": {"name": args.name}}  # how the decision card records the person's verdict
    data = {**answer, "model": args.name, "version": version, "teach": teach}
    return Done("\n".join([*lines, f"Version {version}."]), data)


async def query(ctx: Context, args: AskArgs) -> Done:
    answer, version = await ada(ctx, args.name, "query", args_of(args), args.clearance)
    enough = "" if answer.get("sufficient") else "; not enough alike to go on"
    said = (
        f"{answer.get('top')} at confidence {answer.get('confidence', 0):.2f}, {answer.get('count', 0)} voting{enough}."
    )
    return Done(said, {**answer, "version": version})


async def probabilities(ctx: Context, args: AskArgs) -> Done:
    answer, version = await ada(ctx, args.name, "probabilities", args_of(args), args.clearance)
    said = ", ".join(f"{k} {pct(v)}" for k, v in sorted(answer.items(), key=lambda kv: -kv[1]))
    return Done(said or "Nothing to go on.", {"probabilities": answer, "version": version})


async def facts(ctx: Context, args: FactsArgs) -> Done:
    trees, version = await ada(ctx, args.name, "facts", args_of(args), args.clearance)
    return Done(f"{len(trees)} fact tree{'s' * (len(trees) != 1)}, best first.", {"facts": trees, "version": version})


ASKS = "{data} in the spec's shape (layers, segments, roles); what it leaves out weighs nothing."
TOOLS: tuple[Tool, ...] = (
    Tool(
        "ada_record",
        "Record an Ada case",
        "One case and, when known, its outcome: a precedent the model learns from. A spec with key parts replaces the "
        "case with the same id.",
        Record,
        record,
    ),
    Tool(
        "ada_record_many",
        "Record Ada cases",
        "Up to 1,000 cases ({data, outcome?, outcomes?, ts?} each) in one transaction, all or none. Send a large file "
        "with ada_import instead.",
        RecordMany,
        record_many,
    ),
    Tool("ada_grade", "Grade an Ada case", "One output's outcome on a case already recorded.", GradeArgs, grade),
    Tool("ada_forget", "Forget an Ada case", "Forget one case and every outcome it carries.", Forget, forget),
    Tool(
        "ada_decide",
        "Ada decide",
        "The headline: the outcome of least expected cost, its probabilities, whether a person should decide instead "
        f"(ask), and the precedents it stands on. {ASKS} By an output's kind it adds p (a noul's P(true)), value (a "
        "number's), level (a score's) or a list (many); a union's branch not taken answers applies: false. Counts as "
        "a request (one per output).",
        DecideArgs,
        decide,
        True,
        True,
        DECISION_URI,
    ),
    Tool("ada_query", "Ada query", f"The nearest precedents' vote. {ASKS}", AskArgs, query, True),
    Tool(
        "ada_probabilities", "Ada probabilities", f"P(outcome | data), calibrated. {ASKS}", AskArgs, probabilities, True
    ),
    Tool("ada_facts", "Ada facts", f"The nearest fact trees, best first. {ASKS}", FactsArgs, facts, True),
)
