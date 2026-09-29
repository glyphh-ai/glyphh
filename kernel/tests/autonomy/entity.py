"""
AutonomousEntity — glyphh is the authority, the LLM is a consultant.

The proposer slot is where an LLM plugs in (any callable
(situation, events, actions) -> action). In these tests it is a
SimulatedLLM: right most of the time, expensive by assumption, and
counting every consultation. Swap in a real model by passing any
callable with the same shape — the entity's behavior contract does not
change.

The entity acts by REFLEX when precedent is sufficient and consults
only when the world presents something its own history cannot ground.
Only actions the WORLD confirmed become precedent: habit forms from
wins, and the reward signal is the outcome, never approval.

Failure teaches without a human: every failed action is remembered in a
failure space, and a reflex whose action is discredited for this
situation is vetoed — the entity consults again instead of being
confidently wrong forever.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from glyphh.decision import DecisionSpace

Proposer = Callable[[Dict[str, str], List[Dict[str, str]], List[str]], str]


@dataclass
class SimulatedLLM:
    """Stands in for an LLM: broadly right, never grounded, always billed."""

    oracle: Callable[[Dict[str, str], List[Dict[str, str]]], str]
    actions: List[str]
    accuracy: float = 0.8
    seed: int = 11
    calls: int = 0
    _rng: random.Random = field(init=False)

    def __post_init__(self):
        self._rng = random.Random(self.seed)

    def __call__(self, situation, events, actions) -> str:
        self.calls += 1
        truth = self.oracle(situation, events)
        if self._rng.random() < self.accuracy:
            return truth
        wrong = [a for a in actions if a != truth]
        return self._rng.choice(wrong)


@dataclass
class StepResult:
    action: str
    mode: str            # "reflex" | "consult"
    success: bool
    confidence: float


class AutonomousEntity:
    """Reflex-first actor over a DecisionSpace of grounded wins."""

    def __init__(
        self,
        proposer: Proposer,
        actions: List[str],
        dimension: int = 2048,
        act_threshold: float = 0.6,
        k: int = 7,
    ):
        self._proposer = proposer
        self._actions = actions
        self._threshold = act_threshold
        self._space = DecisionSpace(dimension=dimension, k=k,
                                    min_precedent_sim=0.55)
        self._failures = DecisionSpace(dimension=dimension, k=k,
                                       min_precedent_sim=0.55)
        self.history: List[StepResult] = []

    # ── the loop ────────────────────────────────────────────────────

    def step(self, situation: Dict[str, str],
             events: List[Dict[str, str]],
             grade: Callable[[str], bool]) -> StepResult:
        """SENSE -> RECALL -> ACT -> GROUND -> LEARN, one event."""
        answer = self._space.query(situation, events=events)

        reflex_ok = (answer.sufficient
                     and answer.top_outcome is not None
                     and answer.confidence >= self._threshold)
        if reflex_ok:
            # Failure veto: a reflex discredited for THIS situation does
            # not fire again — the entity consults instead.
            failed = self._failures.query(situation, events=events)
            if (failed.sufficient
                    and failed.top_outcome == answer.top_outcome
                    and failed.confidence >= 0.5):
                reflex_ok = False

        if reflex_ok:
            action, mode, confidence = answer.top_outcome, "reflex", answer.confidence
        else:
            action = self._proposer(situation, events, self._actions)
            mode, confidence = "consult", answer.confidence

        success = grade(action)

        # LEARN: wins become habit; failures become vetoes. No human.
        if success:
            self._space.record(situation, action, events=events,
                               facts={"mode": mode})
        else:
            self._failures.record(situation, action, events=events,
                                  facts={"mode": mode})

        result = StepResult(action=action, mode=mode,
                            success=success, confidence=confidence)
        self.history.append(result)
        return result

    # ── autonomy accounting ─────────────────────────────────────────

    def quartile_stats(self) -> List[Dict[str, float]]:
        """consult rate / success rate / reflex rate per life-quartile."""
        n = len(self.history)
        out = []
        for q in range(4):
            chunk = self.history[q * n // 4:(q + 1) * n // 4]
            if not chunk:
                continue
            out.append({
                "consult_rate": sum(r.mode == "consult" for r in chunk) / len(chunk),
                "reflex_rate": sum(r.mode == "reflex" for r in chunk) / len(chunk),
                "success_rate": sum(r.success for r in chunk) / len(chunk),
                "n": len(chunk),
            })
        return out

    @property
    def precedents(self) -> int:
        return len(self._space)
