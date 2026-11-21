"""The connector's `ada_beam`: beam search across models (glyphh_ada/api/beam.py), one model's outcome the next
one's question, computed exactly as `POST /v1/beam` computes it, as the person signed in. Each hop reached counts one
read against the org's month."""

from typing import Any

from glyphh_ada.api.beam import BeamAsk, chain
from glyphh_server.mcp.tools.ada_base import caller, owned
from glyphh_server.mcp.tools.base import Context, Done, Tool


class BeamArgs(BeamAsk):
    pass


def summary(answer: dict[str, Any]) -> str:
    """The beam in a line: its end and share, how many hops, how many other ends, what was lost."""
    hops, lost = len(answer["hops"]), f"lost {answer['lost']:.2f}"
    over = f"over {hops} hop{'s' * (hops != 1)}"
    if answer["outcome"] is None:
        return f"Nothing arrived {over}; {lost}."
    others = len(answer["ends"]) - 1
    return f"End {answer['outcome']} at {answer['p']:.2f} {over}; {others} other end{'s' * (others != 1)}; {lost}."


async def beam_models(ctx: Context, args: BeamArgs) -> Done:
    for hop in args.hops:
        owned(ctx, hop.model)
    answer = await chain(ctx.ada, await caller(ctx), args, {})
    return Done(summary(answer), answer)


TOOLS: tuple[Tool, ...] = (
    Tool(
        "ada_beam",
        "Ada beam",
        "Chain models: one model's outcome is the next one's question. From `start`, each hop asks its model about "
        "every value the beam holds (the value in the hop's `role`, as layer.segment.role, with its `fixed` roles "
        "beside it) and passes the mass on by the model's probabilities, keeping the `width` heaviest values between "
        "hops. `values` with `miss` (0 to 1) is what a model may not know: that share of each hop's mass spreads "
        "over them, all of it when a model has nothing to say. Answers the heaviest end and its share (p), every "
        "end's share (ends), each end's likeliest path (paths: value, p, trail_p, steps) and the mass that arrived "
        "nowhere (lost). Counts as one request per hop.",
        BeamArgs,
        beam_models,
        True,
    ),
)
