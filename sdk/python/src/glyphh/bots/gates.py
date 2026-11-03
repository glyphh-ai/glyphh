"""Learned gates: how each of a bot's gates decides when its Ada model may call a case alone, and when the person is
asked. A gate's policy is in bot.json beside its spec:

  ask_below       ask whenever Ada's top probability is under this (overrides the spec's own)
  min_precedents  how many precedents the gate holds before Ada may decide alone
  audit           a fraction of Ada's sure calls still asked, to keep checking it (agreement or overrule)
  shadow          Ada decides, but the person is always asked (agreement measured before Ada is trusted)
  max_questions   at most this many questions a run; the rest take `default`, or wait for the next run
  default         the outcome for what is not asked this run (never kept as a precedent: it is no one's answer)
  world           the outcome comes later from the world (`glyphh bot outcome`, `ctx.gate(g).record_outcome`):
                  the case is kept until then, and the person's call meanwhile is not kept as a precedent

A gate learns only from the person's answers, their corrections and real outcomes: Ada's own calls and defaults are
never recorded."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

from ..errors import AdaError

if TYPE_CHECKING:  # pragma: no cover
    from .runner import Ctx

#: A gate's policy keys, as bot.json names them.
POLICY = ("ask_below", "min_precedents", "audit", "shadow", "max_questions", "default", "world")
#: Names a per-item gate's step data uses beside its outcomes' lists.
RESERVED = ("decisions", "asked", "decided", "defaulted", "deferred", "dropped", "items")


def fraction(seed: str) -> float:
    """A steady fraction in [0, 1) from a seed: which sure calls an audit asks (the same run asks the same ones)."""
    return int(hashlib.sha256(seed.encode()).hexdigest()[:12], 16) / float(16 ** 12)


@dataclass
class Call:
    """What a gate's policy makes of Ada's answer: `outcome` is Ada's call (its best guess when it is not sure),
    `ask` whether the person is asked, `mode` why: `ada` (sure, decided), `new` (no precedents yet), `few` (under
    min_precedents), `unsure` (under the threshold), `audit` or `shadow` (sure, still asked)."""

    outcome: Optional[str]
    ask: bool
    mode: str
    why: str
    p: Optional[float] = None
    precedents: int = 0
    probabilities: Dict[str, float] = field(default_factory=dict)

    @property
    def sure(self) -> bool:
        return not self.ask

    @property
    def guess(self) -> Optional[str]:
        return self.outcome

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Policy:
    name: str
    outcomes: List[str]
    ask_below: Optional[float] = None
    min_precedents: int = 1
    audit: float = 0.0
    shadow: bool = False
    max_questions: Optional[int] = None
    default: Optional[str] = None
    world: bool = False

    @classmethod
    def of(cls, name: str, gate: Mapping[str, Any]) -> "Policy":
        return cls(
            name=name,
            outcomes=list(gate.get("outcomes") or []),
            ask_below=gate.get("ask_below"),
            min_precedents=max(1, int(gate.get("min_precedents") or 1)),
            audit=float(gate.get("audit") or 0.0),
            shadow=bool(gate.get("shadow", False)),
            max_questions=gate.get("max_questions"),
            default=gate.get("default"),
            world=bool(gate.get("world", False)),
        )

    def judge(self, decision: Any, held: int, seed: str) -> Call:
        """The call on one case, from Ada's decision (None when the gate holds no precedent) and the policy."""
        probs = dict(getattr(decision, "probabilities", None) or {}) if decision is not None else {}
        guess = getattr(decision, "outcome", None) if decision is not None else None
        guess = guess if isinstance(guess, str) and guess in self.outcomes else None
        p = probs.get(guess) if guess else None
        if p is None and probs:
            p = max(probs.values())
        base = {"p": p, "precedents": held, "probabilities": probs}
        if decision is None or held == 0:
            return Call(None, True, "new", "no precedents yet", **base)
        if held < self.min_precedents:
            return Call(guess, True, "few", f"{held} of the {self.min_precedents} precedents it needs to decide alone",
                        **base)
        shown = f"{guess} (P {p:.2f})" if guess and p is not None else str(guess)
        if guess is None:
            sure = False
        elif self.ask_below is not None:
            sure = p is not None and p >= self.ask_below
        else:
            sure = not bool(getattr(decision, "ask", True))
        if not sure:
            return Call(guess, True, "unsure", f"Ada's guess is {shown}, not sure enough", **base)
        if self.shadow:
            return Call(guess, True, "shadow", f"shadow: Ada says {shown}; your call is the one kept", **base)
        if self.audit and fraction(seed) < self.audit:
            return Call(guess, True, "audit", f"an audit: Ada is sure it is {shown}; is it?", **base)
        return Call(guess, False, "ada", f"Ada: {shown}", **base)


def check_policy(name: str, gate: Mapping[str, Any]) -> List[str]:
    """Every problem with a gate's policy keys, one line each."""
    problems: List[str] = []
    outcomes = gate.get("outcomes") if isinstance(gate.get("outcomes"), list) else []

    def number(key: str, low: float, high: float, whole: bool = False) -> None:
        v = gate.get(key)
        if v is None:
            return
        ok = isinstance(v, (int, float)) and not isinstance(v, bool) and low <= v <= high
        if whole:
            ok = ok and isinstance(v, int)
        if not ok:
            problems.append(f"gate {name}: {key} must be {'a whole number' if whole else 'a number'} from {low:g} to {high:g}")

    number("ask_below", 0.0, 1.0)
    number("min_precedents", 0, 100000, whole=True)
    number("audit", 0.0, 1.0)
    number("max_questions", 0, 1000, whole=True)
    for key in ("shadow", "world"):
        if key in gate and not isinstance(gate[key], bool):
            problems.append(f"gate {name}: {key} must be true or false")
    if "default" in gate and gate["default"] not in outcomes:
        problems.append(f"gate {name}: default must be one of its outcomes")
    if gate.get("world") and (gate.get("audit") or gate.get("shadow")):
        problems.append(f"gate {name}: a world-answered gate has no audit or shadow (the world answers, not the person)")
    clash = [o for o in outcomes if o in RESERVED]
    if clash:
        problems.append(f"gate {name}: outcomes may not be named {', '.join(clash)}")
    return problems


class Gate:
    """One of a bot's gates, for a program's code: `ctx.gate(name)`. `decide(case)` is the gate's call under its
    policy (a Call: `outcome`, `ask`, `p`, `probabilities`, `sure`); given an `item`, the case is kept so
    `record_outcome(outcome, item)` can record what really happened later. `record(case, outcome)` keeps a precedent
    the program knows is true (a test that passed, a person's answer it got itself). Anything else is the gate's Ada
    model (`info`, `facts`, ...)."""

    def __init__(self, ctx: "Ctx", name: str) -> None:
        self._ctx, self.name = ctx, name
        self.spec = ctx.bot.gates[name]
        self.policy = Policy.of(name, self.spec)
        self.model = ctx.ada.model(ctx.bot.gate_model(name))

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.model, attr)

    def decide(self, case: Dict[str, Any], item: Optional[Any] = None) -> Call:
        from .runner import held

        n = held(self._ctx.ada, self._ctx.bot.gate_model(self.name))
        try:
            decision = self.model.decide(case) if n else None
        except AdaError:
            decision = None
        call = self.policy.judge(decision, n, f"{self._ctx.run_id}:{self.name}:{item}")
        if item is not None:
            self._ctx._runner.store.keep_decision(
                run=self._ctx.run_id, gate=self.name, step="code", n=0, key=str(item), label=str(item), kind="code",
                case=case, outcome=call.outcome, by="ada" if call.sure else "unsure", p=call.p, guess=call.outcome,
                mode=call.mode, recorded=False, day=self._ctx.today.isoformat(),
            )
        return call

    def record(self, case: Dict[str, Any], outcome: str) -> Any:
        if outcome not in self.policy.outcomes:
            raise ValueError(f"{outcome} is not one of gate {self.name}'s outcomes")
        return self.model.record(case, outcome)

    def record_outcome(self, outcome: str, item: Optional[Any] = None, run: Optional[str] = None) -> Dict[str, Any]:
        """What really happened to a case this gate decided (this run's, unless `run` says another)."""
        return self._ctx._runner.outcome(run or self._ctx.run_id, self.name, None if item is None else str(item), outcome)
