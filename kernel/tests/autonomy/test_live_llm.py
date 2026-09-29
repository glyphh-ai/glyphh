"""
The autonomy experiment with a REAL Claude in the consultant slot.

Runs only when ANTHROPIC_API_KEY is present in the environment (never
stored in this repo); skips otherwise. A 160-step life keeps the API
spend trivial (consultations are a few hundred tokens each and fall
toward zero as the entity weans).
"""

import os

import pytest

from .entity import AutonomousEntity
from .world import ACTIONS, OpsWorld

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="live LLM test requires ANTHROPIC_API_KEY",
)

LIFE = 160


def test_live_weaning_and_grounding():
    from .anthropic_proposer import AnthropicProposer

    world = OpsWorld(seed=7)
    proposer = AnthropicProposer()
    entity = AutonomousEntity(proposer=proposer, actions=ACTIONS)

    for _ in range(LIFE):
        incident = world.next_incident()
        entity.step(incident.situation, incident.events,
                    grade=lambda a, inc=incident: OpsWorld.grade(inc, a))

    q = entity.quartile_stats()
    print("\nlive quartiles:", q)
    print(f"LLM calls: {proposer.calls}, "
          f"tokens {proposer.input_tokens}/{proposer.output_tokens}, "
          f"~${proposer.cost_usd:.3f}")

    # Weaning: the mature entity consults far less than the infant.
    assert q[3]["consult_rate"] < 0.5 * max(q[0]["consult_rate"], 0.05), (
        f"no weaning with live LLM: {q}")
    # Grounding: success holds or improves as reflexes take over.
    assert q[3]["success_rate"] >= q[0]["success_rate"] - 0.05, (
        f"autonomy degraded success: {q}")
    # Economics: the LLM is consulted for a minority of the entity's life.
    assert proposer.calls < LIFE * 0.6
