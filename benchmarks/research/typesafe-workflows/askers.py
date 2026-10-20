"""Who answers the questions: Jev through TypeSafe's SDK, the reference LLMs through TypeSafe's own LLM adapter
(system-one-adapter), the way TypeSafe ran them. Every asker takes a state and {question id: question} and returns
normalised answers (a noul is P(yes); a choice or a score is its probability per option) with its tokens and time.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import system_one_adapter.providers.anthropic as adapter_anthropic
import system_one_adapter.providers.openai as adapter_openai
from system_one_adapter import SystemOneAdapterClient
from system_one_adapter.providers.anthropic import AnthropicProvider
from system_one_adapter.providers.openai import OpenAIProvider
from typesafe_sdk import TypeSafeClient, TypeSafeError

# $ per million tokens: (input, cache write, cache read, output). Jev bills input only. Astra's is its published
# list price; OpenAI bills no cache writes. Claude Opus 5's cache read is the standard tenth of its input price.
PRICES = {
    "jev": (0.042, 0.042, 0.042, 0.0),
    "claude-fable-5-1": (10.0, 12.5, 0.25, 50.0),
    "claude-opus-5": (5.0, 6.25, 0.5, 25.0),
    "gpt-6-astra": (10.0, 10.0, 1.0, 50.0),
}

# TypeSafe's references ran at high thinking; the adapter sends no effort, so add it to every request it builds.
EFFORT = "high"
_anthropic_kwargs = adapter_anthropic._request_kwargs
_openai_kwargs = adapter_openai._responses_request_kwargs


# No prompt caching: the question travels in each request's output schema, which changes the prompt every time, so a
# cache is written and never read (measured on the pilot) and a write costs 1.25x input.
def _anthropic_with_effort(*args, **kwargs):
    k = _anthropic_kwargs(*args, **kwargs)
    k.setdefault("output_config", {})["effort"] = EFFORT
    return k


def _openai_with_effort(*args, **kwargs):
    k = _openai_kwargs(*args, **kwargs)
    k["reasoning"] = {"effort": EFFORT}
    k["prompt_cache_key"] = hashlib.sha256(str(k["input"]).encode()).hexdigest()[:32]
    return k


adapter_anthropic._request_kwargs = _anthropic_with_effort
adapter_openai._responses_request_kwargs = _openai_with_effort


@dataclass
class Spend:
    """What a run cost: tokens and dollars by model, and the seconds each case took."""

    tokens: dict[str, list[int]] = field(
        default_factory=dict
    )  # model: [input, cache write, cache read, output]
    fallbacks: int = 0

    def add(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        written: int = 0,
        read: int = 0,
    ) -> None:
        t = self.tokens.setdefault(model, [0, 0, 0, 0])
        for i, n in enumerate((tokens_in, written, read, tokens_out)):
            t[i] += n

    def add_attempts(self, model: str, attempts: list[dict]) -> None:
        """Bill every provider call the adapter made, from the provider's own usage."""
        for attempt in attempts:
            u = (attempt.get("llm_response") or {}).get("usage") or {}
            if (
                "cache_read_input_tokens" in u or "cache_creation_input_tokens" in u
            ):  # Anthropic
                self.add(
                    model,
                    u.get("input_tokens") or 0,
                    u.get("output_tokens") or 0,
                    u.get("cache_creation_input_tokens") or 0,
                    u.get("cache_read_input_tokens") or 0,
                )
            else:  # OpenAI Responses: input_tokens includes the cached ones
                cached = (u.get("input_tokens_details") or {}).get("cached_tokens") or 0
                self.add(
                    model,
                    (u.get("input_tokens") or 0) - cached,
                    u.get("output_tokens") or 0,
                    0,
                    cached,
                )

    def dollars(self) -> float:
        return sum(
            sum(n * p for n, p in zip(t, PRICES[m], strict=True)) / 1e6
            for m, t in self.tokens.items()
        )


class Refused(RuntimeError):
    """The reference's model and its fallback both declined this document (a safety refusal on each)."""


class BudgetExceeded(RuntimeError):
    """The run's spend reached its budget: no further request is made."""


class Budget:
    """A hard stop on what the references spend, shared by every process of a run.

    BENCH_BUDGET (dollars) and BENCH_LEDGER (a JSON file) must both be set, or a Reference refuses to start. Every
    request first checks the ledger and raises BudgetExceeded once the total has reached the budget; after it, its
    cost (from the provider's own usage) is added to the ledger. The file is locked while read and written, so two
    references running at once share one total. A request already sent when the budget is reached still completes,
    so the overshoot is at most the requests in flight (cents each)."""

    def __init__(self) -> None:
        budget, ledger = os.environ.get("BENCH_BUDGET"), os.environ.get("BENCH_LEDGER")
        if not budget or not ledger:
            raise SystemExit("set BENCH_BUDGET (dollars) and BENCH_LEDGER (a file) before running a reference")
        self.limit, self.path = float(budget), ledger

    def _update(self, add: float) -> float:
        with open(self.path, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0)
            total = float(json.loads(f.read() or "{}").get("dollars", 0.0)) + add
            if add:
                f.seek(0)
                f.truncate()
                f.write(json.dumps({"dollars": round(total, 6), "limit": self.limit}))
            fcntl.flock(f, fcntl.LOCK_UN)
        return total

    def check(self) -> None:
        spent = self._update(0.0)
        if spent >= self.limit:
            raise BudgetExceeded(f"spent ${spent:.2f} of the ${self.limit:.2f} budget; stopping")

    def charge(self, dollars: float) -> float:
        return self._update(dollars)


def normalised(answer) -> float | dict[str, float]:
    if answer.type == "noul":
        return float(answer.noul)
    return {str(k): float(v) for k, v in answer.probabilities.items()}


class Jev:
    """Jev asks every question of a node in one request, as TypeSafe's own workflow runs did."""

    name = "jev"

    def __init__(self, model: str = "jev-latest") -> None:
        self.client = TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"])
        self.model = model
        self.spend = Spend()

    def ask(self, state, questions: dict[str, dict]) -> dict:
        r = self.client.system_one(state=state, questions=questions, model=self.model)
        self.spend.add("jev", r.usage.input_tokens or 0, 0)
        return {q: normalised(r.answers[q]) for q in questions}


class Reference:
    """A frontier LLM through TypeSafe's adapter: one question per request, probabilities, high thinking."""

    def __init__(
        self,
        name: str,
        provider: str,
        model: str,
        fallback: str | None = None,
        workers: int = 8,
    ) -> None:
        self.name, self.provider, self.model, self.fallback = (
            name,
            provider,
            model,
            fallback,
        )
        self.client = SystemOneAdapterClient(
            structured_outputs=True,
            llm_answer_mode="probabilities",
            normalize_probabilities=True,
        )
        self.pool = ThreadPoolExecutor(workers)
        self.spend = Spend()
        self.refused: set[str] = set()
        self.budget = Budget()
        self.lock = threading.Lock()

    def _llm(self, model: str):
        if self.provider == "anthropic":
            return AnthropicProvider(model, max_tokens=16000)
        return OpenAIProvider(model)

    def _one(self, state, qid: str, question: dict, model: str):
        self.budget.check()
        try:
            r = self.client.system_one(state, {qid: question}, model=self._llm(model))
            attempts = r.debug["llm_attempts"]
        except TypeSafeError as e:  # a refusal is billed too: charge it before the fallback runs
            attempts = (e.debug or {}).get("llm_attempts", [])
            self._bill(model, attempts)
            raise
        self._bill(model, attempts)
        return qid, normalised(r.answers[qid])

    def _bill(self, model: str, attempts: list[dict]) -> None:
        with self.lock:
            before = self.spend.dollars()
            self.spend.add_attempts(model, attempts)
            self.budget.charge(self.spend.dollars() - before)

    def _all(self, state, questions: dict[str, dict], model: str) -> dict:
        return dict(self.pool.map(lambda item: self._one(state, *item, model), questions.items()))

    def ask(self, state, questions: dict[str, dict]) -> dict:
        """Every question on the primary model; if it refuses or fails any question on this document, the whole
        document goes to the fallback, as TypeSafe's reference did (Opus 5 "on the documents Fable refused")."""
        key = json.dumps(state, sort_keys=True)
        if key not in self.refused:
            try:
                return self._all(state, questions, self.model)
            except TypeSafeError:
                if not self.fallback:
                    raise
                self.refused.add(key)
                self.spend.fallbacks += 1
        try:
            return self._all(state, questions, self.fallback)
        except TypeSafeError as e:  # the fallback declined too: this reference cannot answer the document
            raise Refused(f"{self.model} and {self.fallback} both declined: {e}") from e


def timed(ask):
    """Wrap an asker so each call's wall time is added to `seconds`."""
    seconds = [0.0]

    def run(*args):
        t0 = time.time()
        try:
            return ask(*args)
        finally:
            seconds[0] += time.time() - t0

    return run, seconds
