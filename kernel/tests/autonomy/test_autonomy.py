"""
The autonomy claims, as falsifiable tests.

1. WEANING     LLM consultation falls sharply over the entity's life
2. GROUNDING   success holds (or rises) as reflexes replace the LLM —
               reflexes formed from world-confirmed wins outperform a
               merely-plausible proposer
3. ORDER       two situations identical in attributes and different
               only in event ORDER acquire different reflexes
4. NOVELTY     a never-seen incident kind makes the entity consult
               again — autonomy that knows its own limits
5. RECEIPTS    every reflex is backed by citable precedent
"""

import pytest

from .entity import AutonomousEntity, SimulatedLLM
from .world import ACTIONS, OpsWorld

LIFE = 400


def live(entity: AutonomousEntity, world: OpsWorld, steps: int):
    for _ in range(steps):
        incident = world.next_incident()
        entity.step(incident.situation, incident.events,
                    grade=lambda a, inc=incident: OpsWorld.grade(inc, a))


@pytest.fixture(scope="module")
def grown():
    """One entity, one life, examined by several tests."""
    world = OpsWorld(seed=7)
    # The proposer's oracle peeks at the current incident's truth — it
    # models an LLM that is knowledgeable but noisy, never grounded.
    incidents = []

    def oracle(situation, events):
        return incidents[-1].correct_action

    llm = SimulatedLLM(oracle=oracle, actions=ACTIONS)
    entity = AutonomousEntity(proposer=llm, actions=ACTIONS)
    for _ in range(LIFE):
        incident = world.next_incident()
        incidents.append(incident)
        entity.step(incident.situation, incident.events,
                    grade=lambda a, inc=incident: OpsWorld.grade(inc, a))
    return entity, llm, world, incidents


def test_weaning(grown):
    entity, llm, _, _ = grown
    infancy = entity.history[:30]
    infancy_consult = sum(r.mode == "consult" for r in infancy) / len(infancy)
    assert infancy_consult > 0.5, "infant entity should lean on the LLM"
    q = entity.quartile_stats()
    assert q[3]["consult_rate"] < 0.25 * q[0]["consult_rate"], (
        f"mature entity still consulting: {q}")
    assert llm.calls < LIFE * 0.25, "LLM billed for too much of life"


def test_grounding(grown):
    entity, _, _, _ = grown
    q = entity.quartile_stats()
    assert q[3]["success_rate"] >= q[0]["success_rate"], (
        f"autonomy degraded success: {q}")
    assert q[3]["success_rate"] >= 0.9, f"mature success too low: {q}"


def test_reflexes_beat_the_proposer(grown):
    """World-confirmed habit outperforms the 80%-accurate LLM."""
    entity, _, _, _ = grown
    reflex = [r for r in entity.history if r.mode == "reflex"]
    assert reflex, "no reflexes formed"
    reflex_success = sum(r.success for r in reflex) / len(reflex)
    assert reflex_success > 0.9
    assert reflex_success > 0.8  # the proposer's ceiling


def test_order_disambiguates(grown):
    """flap_up_down vs flap_down_up: same attributes, opposite reflexes."""
    entity, _, _, incidents = grown
    late = list(zip(incidents, entity.history))[LIFE // 2:]
    for kind, expected in [("flap_up_down", "scale_down"),
                           ("flap_down_up", "scale_up")]:
        matching = [r for inc, r in late
                    if inc.kind == kind and r.mode == "reflex"]
        assert matching, f"no mature reflexes for {kind}"
        hit = sum(r.action == expected for r in matching) / len(matching)
        assert hit >= 0.9, f"{kind}: order signal lost ({hit:.2f})"


def test_novelty_reawakens_consultation(grown):
    entity, llm, world, incidents = grown
    calls_before = llm.calls
    novel_world = OpsWorld(seed=99, include_novel=True)
    novel_hits = 0
    for _ in range(40):
        incident = novel_world.next_incident()
        if incident.kind != "cert_expiry":
            continue
        incidents.append(incident)
        result = entity.step(incident.situation, incident.events,
                             grade=lambda a, inc=incident: OpsWorld.grade(inc, a))
        novel_hits += 1
        if novel_hits == 1:
            assert result.mode == "consult", (
                "entity acted on a never-seen incident without consulting")
    assert novel_hits > 0, "novelty probe generated no novel incidents"
    assert llm.calls > calls_before, "novelty did not reach the proposer"


def test_reflexes_have_receipts(grown):
    """A reflex is not a vibe: its precedent is citable."""
    entity, _, _, incidents = grown
    incident = next(i for i in incidents if i.kind == "bad_deploy")
    answer = entity._space.query(incident.situation, events=incident.events)
    assert answer.sufficient
    assert answer.precedents, "no cited precedent behind the reflex"
    tree = answer.fact_tree.to_json()
    assert tree["children"], "empty fact tree"
