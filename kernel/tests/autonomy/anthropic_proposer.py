"""
AnthropicProposer — a real Claude in the entity's consultant slot.

Same contract as SimulatedLLM: (situation, events, actions) -> action.
The entity's behavior does not change; only who answers when precedent
is thin. Requires ANTHROPIC_API_KEY (never stored in this repo); the
pytest that uses it skips when the key is absent.
"""

from __future__ import annotations

import json
import random
from typing import Dict, List

import anthropic

MODEL = "claude-opus-5-5"

SYSTEM = (
    "You are the consultant for an autonomous ops entity. Given an "
    "incident's attributes and its ordered event prelude, choose the "
    "single best remediation. Reply with EXACTLY one action name from "
    "the provided list — no punctuation, no explanation."
)


class AnthropicProposer:
    """Callable proposer backed by the Claude API."""

    def __init__(self, model: str = MODEL):
        self._client = anthropic.Anthropic()
        self._model = model
        self._rng = random.Random(3)
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def __call__(self, situation: Dict[str, str],
                 events: List[Dict[str, str]],
                 actions: List[str]) -> str:
        self.calls += 1
        prompt = (
            f"Incident attributes: {json.dumps(situation, sort_keys=True)}\n"
            f"Event prelude, in order: {json.dumps(events)}\n"
            f"Available actions: {', '.join(actions)}\n"
            f"Best action:"
        )
        try:
            # Thinking is always on for this model and bills as output —
            # give it headroom or the one-word answer gets truncated.
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2000,
                system=SYSTEM,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": prompt}],
            )
            self.input_tokens += response.usage.input_tokens
            self.output_tokens += response.usage.output_tokens
            if response.stop_reason == "refusal":
                return self._rng.choice(actions)
            text = next((b.text for b in response.content
                         if b.type == "text"), "").strip().lower()
            for action in actions:
                if action in text:
                    return action
        except anthropic.APIError:
            pass
        return self._rng.choice(actions)

    @property
    def cost_usd(self) -> float:
        return (self.input_tokens * 4 + self.output_tokens * 20) / 1e6
