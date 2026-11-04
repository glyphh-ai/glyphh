"""The hidden world: a machine nobody is told. Each action is a shuffle of the states, chosen by the seed, with opaque
names, so no contestant can bring anything to it but the precedents. A chain is a start, some actions and where they
ended. Shuffles keep every state reachable: a long chain stays as hard as a short one, and chance stays 1 in STATES.

A precedent says only where a chain ended, never the states it passed through. Half the single moves are shown
directly; the rest appear only inside longer chains. Every test chain uses at least one move never shown directly and
is not in the training set, so no precedent holds its answer."""

from __future__ import annotations

import random
from dataclasses import dataclass

STATES, ACTIONS = 10, 6
DIRECT = 0.5  # the share of moves with a precedent of their own
CHAINS = 500  # training chains of 2 or 3 actions, ends only
NOISE = 0.05  # training ends recorded wrong
TEST_LENGTHS = (3, 5, 8, 12, 16)
TEST_PER_LENGTH = 200


@dataclass(frozen=True)
class Chain:
    start: str
    actions: tuple[str, ...]
    end: str


@dataclass(frozen=True)
class World:
    moves: dict[tuple[str, str], str]
    states: tuple[str, ...]
    actions: tuple[str, ...]
    direct: frozenset[tuple[str, str]]
    train: tuple[Chain, ...]
    test: dict[int, tuple[Chain, ...]]


def make(seed: int, shown: float = DIRECT) -> World:
    rng = random.Random(seed)
    letters = "bdfgklmnprstvz"
    names = rng.sample([a + b + c for a in letters for b in "aeiou" for c in letters], STATES + ACTIONS)
    states, actions = tuple(names[:STATES]), tuple(names[STATES:])
    moves = {}
    for action in actions:
        moves.update({(s, action): t for s, t in zip(states, rng.sample(states, STATES))})
    every = sorted(moves)
    direct = frozenset(rng.sample(every, int(len(every) * shown)))

    def end_of(start: str, chain: tuple[str, ...]) -> str:
        state = start
        for action in chain:
            state = moves[state, action]
        return state

    def noisy(end: str) -> str:
        return rng.choice([s for s in states if s != end]) if rng.random() < NOISE else end

    def indirect(start: str, chain: tuple[str, ...]) -> bool:
        state = start
        for action in chain:
            if (state, action) not in direct:
                return True
            state = moves[state, action]
        return False

    train = [Chain(s, (a,), noisy(moves[s, a])) for s, a in sorted(direct)]
    for _ in range(CHAINS):
        start, chain = rng.choice(states), tuple(rng.choices(actions, k=rng.choice((2, 3))))
        train.append(Chain(start, chain, noisy(end_of(start, chain))))
    seen = {(c.start, c.actions) for c in train}

    test = {}
    for length in TEST_LENGTHS:
        chains: dict[tuple[str, tuple[str, ...]], Chain] = {}
        while len(chains) < TEST_PER_LENGTH:
            start, chain = rng.choice(states), tuple(rng.choices(actions, k=length))
            if (start, chain) not in seen and indirect(start, chain):
                chains[start, chain] = Chain(start, chain, end_of(start, chain))
        test[length] = tuple(chains.values())
    return World(moves, states, actions, direct, tuple(train), test)
