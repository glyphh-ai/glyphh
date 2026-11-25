"""The micro gates: one small Ada model per action, each knowing only "from this state, this action leads there". No
gate knows a chain. A chain is answered by a loop: one gate's answer is the next gate's question.

Learning comes from the end of a chain alone. A chain with exactly one step the gates can't answer has a hole: every
state is tried in it (generation), the gates after the hole carry each try forward, and a try that lands on the graded
end is the only one left to credit, so the hole's gate records it (positive credit). A chain the gates answer whole
and rightly backs every step on it with a precedent. A chain they answer whole and wrongly is a contradiction: the
least supported step on it loses one (negative credit). Rounds repeat, each round's new knowledge opening holes in
chains that had too many before."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ada_kernel  # noqa: E402

BAR = 0.6  # a gate knows when its best answer is at least this probable
ROUNDS = 6
WIDTH = 10  # the paths a beam carries
MISS = 0.1  # how far a beam doubts any gate while it learns from a graded end
READ_MISS = 0.01  # and while it answers, when a long chain would otherwise doubt itself away
CLEAR = 0.8  # a path is credited when it holds this share of the mass reaching the graded end
ASK_BELOW = 0.5  # a beam's answer below this goes to Claude


def gate_spec(action: str, aging: bool = False) -> dict:
    roles = [{"name": "state"}]
    spec = {"name": f"gate_{action}", "seed": 5, "dimension": 1024}
    if aging:  # a gate that lets old precedents fade reads each case's time from a role that weighs nothing
        when = {"name": "when", "similarity_weight": 0, "numeric_config": {"min_value": 0, "max_value": 1e9, "bin_width": 1e9}}
        roles.append(when)
        spec |= {"temporal_source": "step.at.when", "settings": {"recency": True}}
    return spec | {"layers": [{"name": "step", "segments": [{"name": "at", "roles": roles}]}]}


class Gates:
    def __init__(self, actions: tuple[str, ...], states: tuple[str, ...], half_life: float | None = None):
        spec = ada_kernel.load()
        self.states = states
        self.models = {a: spec.Model(spec.Spec.from_json(gate_spec(a, half_life is not None))) for a in actions}
        if half_life is not None:
            for model in self.models.values():
                model.space.set_half_life(None, half_life)
        self.kept: dict[tuple[str, str, str], list[str]] = {}  # (state, action, next): its precedents' ids
        self.credited: set[tuple] = set()  # one chain credits one step with one answer once
        self.now: float | None = None  # the time, for gates that age their precedents

    def situation(self, state: str) -> dict:
        at = {"state": state} | ({} if self.now is None else {"when": self.now})
        return {"step": {"at": at}}

    def record(self, state: str, action: str, nxt: str) -> None:
        rid = self.models[action].record(self.situation(state), nxt)
        self.kept.setdefault((state, action, nxt), []).append(rid)

    def answer(self, state: str, action: str) -> str | None:
        """The gate's answer, or None when it doesn't know: nothing near, or nothing clear of the bar."""
        probabilities = self.models[action].probabilities(self.situation(state))
        if not probabilities:
            return None
        best = max(probabilities, key=probabilities.get)
        return best if probabilities[best] >= BAR else None

    def run(self, state: str, actions: tuple[str, ...]) -> str | None:
        for action in actions:
            state = self.answer(state, action)
            if state is None:
                return None
        return state

    def trace(self, start: str, actions: tuple[str, ...]) -> tuple[list[tuple[str, str, str]], int | None, str]:
        """The steps the gates can answer, the index of the first they can't (None: all of them) and where it stands."""
        steps, state = [], start
        for i, action in enumerate(actions):
            nxt = self.answer(state, action)
            if nxt is None:
                return steps, i, state
            steps.append((state, action, nxt))
            state = nxt
        return steps, None, state

    def credit(self, chain) -> str:
        """One chain's end, put to the gates: 'answered', 'blamed', 'credited' or 'open'."""
        steps, at, state = self.trace(chain.start, chain.actions)
        if at is None:
            if state == chain.end:
                for step in steps:  # a chain that came out right backs every step on it, once
                    if (chain, step) not in self.credited:
                        self.credited.add((chain, step))
                        self.record(*step)
                return "answered"
            weakest = min(steps, key=lambda s: len(self.kept.get(s, ())))
            ids = self.kept.get(weakest, [])
            if ids:
                self.models[weakest[1]].forget(ids.pop())
            return "blamed"
        action, rest = chain.actions[at], chain.actions[at + 1 :]
        hits = [s for s in self.states if self.run(s, rest) == chain.end]
        mark = (chain.start, chain.actions, chain.end, state, action, hits[0] if hits else None)
        if len(hits) != 1 or mark in self.credited:
            return "open"
        self.credited.add(mark)
        self.record(state, action, hits[0])
        return "credited"

    def hops(self, actions: tuple[str, ...]) -> list:
        return [ada_kernel.load().Hop(self.models[a], self.situation) for a in actions]

    def train(self, train, rng, credit: bool = True) -> list[Counter]:
        for chain in train:
            if len(chain.actions) == 1:
                self.record(chain.start, chain.actions[0], chain.end)
        chains, rounds = [c for c in train if len(c.actions) > 1], []
        for _ in range(ROUNDS if credit else 0):
            rng.shuffle(chains)
            rounds.append(Counter(self.credit(c) for c in chains))
        return rounds


class BeamGates(Gates):
    """The same gates read by the kernel's beam: no gate has to be sure. A chain carries its likeliest paths through
    every gate, a gate may always be wrong by MISS, and the graded end picks the path. That path's steps are credited
    when it explains the end nearly alone, which is also how a rule that changed is learned again: the one step that
    must have moved is the cheapest way to the end."""

    def beam(self, start: str, actions: tuple[str, ...], miss: float) -> dict:
        return ada_kernel.load().beam(start, self.hops(actions), WIDTH, self.states, miss)

    def run(self, state: str, actions: tuple[str, ...]) -> str | None:
        answer = self.beam(state, actions, READ_MISS)
        return answer["outcome"] if answer["p"] >= ASK_BELOW else None

    def credit(self, chain) -> str:
        paths = self.beam(chain.start, chain.actions, MISS)["paths"]
        path = next((p for p in paths if p["value"] == chain.end), None)
        if path is None or path["trail_p"] < CLEAR * path["p"]:
            return "open"
        steps = list(zip(path["steps"], chain.actions, path["steps"][1:]))
        new = [s for s in steps if (chain, s) not in self.credited]
        for step in new:
            self.credited.add((chain, step))
            self.record(*step)
        return "credited" if new else "answered"
