"""
Autonomy experiments — a new type of software.

Classic agent software puts the LLM in charge and rewards it (via RLHF
and approval flows) for keeping a human in the loop: the software gets
better at ASKING. The entity under test inverts that: glyphh is the
authority, the LLM is a consultant hired only for novelty, and the
reward is the WORLD's outcome, not a human's approval.

The loop per event:

  SENSE    observation -> glyph (attributes + ordered event strand)
  RECALL   DecisionSpace.query -> precedent, confidence, receipts
  ACT      sufficient precedent -> REFLEX (no LLM, microseconds)
           thin precedent      -> CONSULT the proposer (the LLM's slot)
  GROUND   the environment says whether the action worked
  LEARN    successful (situation -> action) pairs become precedent,
           one-shot, permanently

The measurable claim: over the entity's life, LLM consultation falls
toward zero while task success holds — and spikes again, correctly,
when the world presents something genuinely new. Autonomy that knows
its own limits.
"""
