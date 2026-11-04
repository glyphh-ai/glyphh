"""Beam search across models (kernel 3.17.0's `glyphh_spec.beam`, with the same answer): one model's outcome is the
next model's question. Computed here, in the API, over each hop's probabilities read, so a chain may run through
models on different Ada versions, each answered by its own kernel's workers.

Every value holds a mass; the start holds 1. A hop asks its model about each value the beam holds and passes the
mass on by the model's probabilities, summing where paths meet. `values`, with `miss`, is what a model may not know:
`miss` of a hop's mass spreads evenly over them, and all of it when the model has nothing to say. Without them a model
with nothing to say ends that path and its mass goes to `lost`. After every hop but the last only the `width` heaviest
values go on; the cut mass is lost too."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

Asker = Callable[[str], Awaitable[Mapping[str, float]]]  # one hop: its model's probabilities about a value
Held = tuple[float, float, tuple[str, ...]]  # a value's mass, its likeliest path's mass and that path's steps

WIDTH: int = 10


def passed(probabilities: Mapping[str, float], values: Sequence[str], miss: float) -> dict[str, float]:
    """What one hop passes on: the model's probabilities, with `miss` of them (all, when it has none) spread evenly
    over `values`. Without values they pass as they are."""
    if not values:
        return dict(probabilities)
    share = miss if probabilities else 1.0
    out = {v: p * (1.0 - share) for v, p in probabilities.items()}
    for value in values:
        out[value] = out.get(value, 0.0) + share / len(values)
    return out


def _reached(paths: Mapping[str, Held], passed_by: Mapping[str, Mapping[str, float]]) -> tuple[dict[str, Held], float]:
    """Where one hop takes the beam: each value reached with its mass summed over the paths that meet there and its
    likeliest single path; and the mass that went nowhere."""
    reached: dict[str, Held] = {}
    lost = 0.0
    for value, (mass, trail, steps) in paths.items():
        got = passed_by[value]
        lost += mass * (1.0 - sum(got.values()))
        for nxt, p in got.items():
            held = reached.get(nxt, (0.0, 0.0, ()))
            best = (trail * p, (*steps, nxt)) if trail * p > held[1] else held[1:]
            reached[nxt] = (held[0] + mass * p, *best)
    return reached, lost


def _answer(paths: Mapping[str, Held], lost: float) -> dict[str, Any]:
    arrived = sum(mass for mass, _, _ in paths.values())
    ends = {v: mass / arrived for v, (mass, _, _) in paths.items()} if arrived else {}
    found = [
        {"value": v, "p": ends[v], "trail_p": t / arrived, "steps": list(s)}
        for v, (_, t, s) in paths.items()
        if arrived
    ]
    found.sort(key=lambda path: (-path["p"], path["value"]))
    return {
        "outcome": found[0]["value"] if found else None,
        "p": found[0]["p"] if found else 0.0,
        "ends": ends,
        "paths": found,
        "lost": lost,
    }


async def beam(
    start: str, hops: Sequence[Asker], width: int = WIDTH, values: Sequence[str] = (), miss: float = 0.0
) -> dict[str, Any]:
    """The likeliest values carried through the hops, each asked about every value the beam holds.

    Answers {"outcome", "p", "ends", "paths", "lost"}: the heaviest end and its share of the mass that arrived (None
    and 0.0 when none did), every end's share, each end's likeliest path ({"value", "p", "trail_p", "steps"}, best
    first; the steps start at `start`, and trail_p is that one path's share, where p is every path's to that end) and
    the mass that arrived nowhere."""
    if width < 1:
        raise ValueError("a beam is at least 1 wide")
    if not 0.0 <= miss <= 1.0:
        raise ValueError("miss is a share, from 0 to 1")
    paths: dict[str, Held] = {start: (1.0, 1.0, (start,))}
    lost = 0.0
    for i, ask in enumerate(hops):
        passed_by = {value: passed(await ask(value), values, miss) for value in paths}
        reached, gone = _reached(paths, passed_by)
        heaviest = sorted(reached.items(), key=lambda kv: (-kv[1][0], kv[0]))
        kept = heaviest if i == len(hops) - 1 else heaviest[:width]
        lost += gone + sum(held[0] for _, held in heaviest[len(kept) :])
        paths = dict(kept)
    return _answer(paths, lost)
