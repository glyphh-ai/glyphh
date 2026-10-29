"""
The Glyphh spec — a model's typed config, and how data in that shape
meets the kernel. numpy + stdlib, beside glyphh_kernel.py.

A spec is JSON: a cortex of layers, each layer a cortex of segments,
each segment a cortex of roles. Every level carries a similarity_weight
(its voice in the bundle above it) and a security_weight (the clearance
a reader needs to see it).

    {"name": "tickets", "dimension": 4096, "seed": 42,
     "temporal_source": "meta.time.opened",
     "layers": [
       {"name": "issue", "similarity_weight": 1.0, "segments": [
         {"name": "body", "roles": [
           {"name": "title", "text_encoding": "bag_of_words"},
           {"name": "component", "lexicons": ["area"]},
           {"name": "severity", "numeric_config":
              {"min_value": 0, "max_value": 10, "bin_width": 1}},
           {"name": "id", "key_part": true, "similarity_weight": 0}]}]},
       {"name": "meta", "security_weight": 0.8, "segments": [
         {"name": "time", "roles": [{"name": "opened"}]}]}],
     "output": {"report": ["issue"]}}

Data in that model is the same shape, by name:
    {"issue": {"body": {"title": "pods crash on boot", "area": "kubelet",
                        "severity": 7, "id": "K-1"}},
     "meta": {"time": {"opened": "2026-10-01T12:00:00Z"}}}

How it meets the kernel. The data nests layer > segment > role, and the
kernel's encode() bundles each object weighted by its keys: the role
bindings bundle into the segment's cortex, segments into the layer's,
layers into the model's. A role's value is a symbol by default (an array
is a set of symbols); text_encoding "bag_of_words" makes it the set of its
words; numeric_config makes it a thermometer, the set of every bin edge
at or below the value, so near numbers share most of their bins.
lexicons are other names the role answers to in data. key_part roles
make the record's id (a later record with the same key replaces it).
temporal_source names the role that stamps the record's time; it is a
timestamp beside the glyph, never a part of it.

Reads. A query scores only the roles it gives: a role the query leaves
out weighs 0. clearance (0..1) is the reader's: every layer, segment or
role whose security_weight is above it weighs 0 in the score and is cut
from the fact tree. output.report keeps only the named paths in the
fact trees that come back ("layer", "layer.segment" or
"layer.segment.role"); empty means everything the reader may see.
"""

from __future__ import annotations

import dataclasses
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import glyphh_kernel as kernel
from glyphh_kernel import ReadOnlyError  # noqa: F401  (a read-only model's writes raise it)

SPEC_VERSION = 1
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,63}$")
_WORD = re.compile(r"[a-z0-9']+")


class SpecError(ValueError):
    """A spec, or data offered to one, that does not match it. `path`
    names the offending field."""

    def __init__(self, path: str, message: str):
        super().__init__(f"{path}: {message}" if path else message)
        self.path = path


# ── the spec ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class NumericConfig:
    min_value: float
    max_value: float
    bin_width: float

    def bins(self, x: float) -> list[str]:
        """Thermometer: every bin edge at or below x, clamped to range."""
        x = min(max(x, self.min_value), self.max_value)
        top = int((x - self.min_value) // self.bin_width)
        return [kernel._text(self.min_value + i * self.bin_width) for i in range(top + 1)]


@dataclass(frozen=True)
class Role:
    name: str
    similarity_weight: float = 1.0
    security_weight: float = 0.0
    key_part: bool = False
    numeric_config: NumericConfig | None = None
    text_encoding: str | None = None
    lexicons: tuple[str, ...] = ()
    # how much each value of this role weighs, 0 to 1, on top of similarity_weight: learned from the store
    # (learn()), keyed by the value's text, for a number by its bin's lower edge. A value not named weighs 1.
    value_weights: tuple[tuple[str, float], ...] = ()

    def value_weight(self, value: Any) -> float:
        if not self.value_weights or value is None:
            return 1.0
        key = kernel._text(value[-1]) if self.numeric_config is not None and isinstance(value, list) else None
        if key is None:
            if isinstance(value, list):
                return 1.0  # a set or a bag of words: the role's weight alone
            key = kernel._text(value)
        return dict(self.value_weights).get(key, 1.0)


@dataclass(frozen=True)
class Segment:
    name: str
    roles: tuple[Role, ...]
    similarity_weight: float = 1.0
    security_weight: float = 0.0


@dataclass(frozen=True)
class Layer:
    name: str
    segments: tuple[Segment, ...]
    similarity_weight: float = 1.0
    security_weight: float = 0.0


@dataclass(frozen=True)
class Interaction:
    """Two roles read together: a case's value is the pair of theirs, in a layer the spec adds itself
    (`interactions.pairs.<name>`). What one role means can depend on another (a bad checking account with a long
    loan); learn() finds the pairs that tell more together than apart. Secured as the stricter of its two roles."""

    name: str
    roles: tuple[str, str]
    similarity_weight: float = 1.0
    value_weights: tuple[tuple[str, float], ...] = ()

    def value_weight(self, value: Any) -> float:
        """A pair value's weight. Since 3.13.0 (answer-changing): once learned, a pair value it never learned (never
        seen, or seen fewer than `rare` times) weighs 0, so the pair stays out of that query's vote and its two roles'
        own weights decide. Before, such a value weighed the pair's full weight and matched nothing: on held-out
        combinations of an AND rule a learned model fell below plain kNN (research/compile, REPORT.md)."""
        if not self.value_weights or value is None:
            return 1.0
        return dict(self.value_weights).get(kernel._text(value), 0.0)


@dataclass(frozen=True)
class Settings:
    """The model's levers, in the spec (`settings`) and changeable live (Model.configure): how a query votes, how
    learning weighs words and pairs, how calibration fits, and whether the model refreshes itself. Each is checked
    by name and range; a change to a learning lever relearns."""

    k: int = 15  # nearest precedents a query votes over
    min_sim: float = 0.10  # the weighted similarity a precedent needs to vote
    word_weights: bool = True  # learn a weight per word of a text role
    word_floor: float = 0.35  # the least a learned word weighs (a bag's glyph is a majority vote: keep the quiet words heard)
    interactions: bool = True  # learn pairs of roles that tell more together
    max_interactions: int = 5  # at most this many pairs
    rare: int = 5  # a value, word or pair seen fewer times than this is not learned from
    calibrate_by: str = "loss"  # "loss" (probabilities that mean what they say) or "cost" (that decide best)
    calibrate_sample: int = 200  # the newest precedents a calibration holds out
    refresh_every: int | None = None  # learn and calibrate again every so many graded records; None: on demand
    lexicon: bool = True  # read a text role's words through the kernel's seeds (synonyms, near words, classes)
    word_pairs: bool = False  # learn pairs of words that tell more together than apart (off: on Banking77 it took
    # 0.1 to 0.4 points inside the training set; a lever for a model whose intents are phrases)
    max_word_pairs: int = 20  # at most this many pairs per text role
    word_evidence: float = 2.0  # how much a query's words, by what each says of every outcome, weigh on the vote
    # (0: not at all; 2 chosen on Banking77 inside its training set, 83.4% to 88.0%)
    shortlist: int = kernel.SHORTLIST  # over a store that can shortlist (Postgres): the candidates a read re-ranks
    # exactly; 0 reads every precedent, exactly, at any size
    exact_below: int = kernel.EXACT_BELOW  # a model holding fewer precedents is read whole, exactly
    level_weights: str = "spec"  # "spec": the spec's own weights, every segment of a layer equal whatever its roles
    # tell; "roles" (3.14.0): a segment weighs its roles' weights summed (times its own), a layer its segments', so a
    # role's voice is the same wherever the spec puts it. Not the default: on German Credit it decided worse (cost
    # 125 against 99); a lever to backtest on a model whose segments hold many quiet roles
    recency: bool = True  # calibrate fits a half-life (time weighs the newer precedents more) and keeps it only when
    # it beats none on the held-out newest; false: every precedent's voice is whole, whatever its age

    RANGES = {  # name: (kind, low, high) or (kind, choices)
        "k": (int, 1, 1000),
        "min_sim": (float, 0.0, 1.0),
        "word_weights": (bool,),
        "word_floor": (float, 0.0, 1.0),
        "interactions": (bool,),
        "max_interactions": (int, 0, 50),
        "rare": (int, 1, 100000),
        "calibrate_by": (str, ("loss", "cost")),
        "calibrate_sample": (int, 10, 1000000),
        "refresh_every": (int, 10, 1000000),
        "lexicon": (bool,),
        "word_pairs": (bool,),
        "max_word_pairs": (int, 0, 200),
        "word_evidence": (float, 0.0, 5.0),
        "shortlist": (int, 0, 10000),
        "exact_below": (int, 0, 100000000),
        "level_weights": (str, ("roles", "spec")),
        "recency": (bool,),
    }
    LEARNING = ("word_weights", "word_floor", "interactions", "max_interactions", "rare", "word_pairs", "max_word_pairs")

    def with_changes(self, changes: Mapping[str, Any], at: str = "settings") -> Settings:
        """These settings with the changes put in, each checked; a bad name, kind or value raises SpecError."""
        values = {k: getattr(self, k) for k in self.RANGES}
        for name, value in changes.items():
            if name not in self.RANGES:
                raise SpecError(f"{at}.{name}", f"no such setting; the settings are {', '.join(self.RANGES)}")
            kind = self.RANGES[name][0]
            if name == "refresh_every" and value is None:
                values[name] = None
                continue
            if kind is bool:
                if not isinstance(value, bool):
                    raise SpecError(f"{at}.{name}", "true or false")
            elif kind is str:
                if value not in self.RANGES[name][1]:
                    raise SpecError(f"{at}.{name}", f"one of {', '.join(self.RANGES[name][1])}")
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise SpecError(f"{at}.{name}", "a number")
            else:
                low, high = self.RANGES[name][1], self.RANGES[name][2]
                if kind is int and int(value) != value:
                    raise SpecError(f"{at}.{name}", "a whole number")
                if not low <= value <= high:
                    raise SpecError(f"{at}.{name}", f"from {low} to {high}")
                if name == "shortlist" and 0 < value < 100:
                    raise SpecError(f"{at}.{name}", "0 (read exactly) or from 100 to 10000")
                value = kind(value)
            values[name] = value
        return Settings(**values)

    def to_json(self, all: bool = False) -> dict[str, Any]:
        """The settings as an object; only those that differ from the defaults unless `all`."""
        defaults = Settings()
        return {k: getattr(self, k) for k in self.RANGES if all or getattr(self, k) != getattr(defaults, k)}


INTERACTIONS = "interactions"  # the layer the spec adds; "pairs" its one segment
PAIR_CANDIDATES = 120  # the most common words of a text role among which word pairs are looked for



OUTPUT_KINDS = ("choice", "score", "noul", "number", "many")
NOUL = ("false", "true")


@dataclass(frozen=True)
class Output:
    report: tuple[str, ...] = ()
    # the cost of deciding one outcome when another is true: costs[decided][true]; a pair not named costs 0
    # when they are the same outcome and 1 otherwise. decide() picks the outcome with the least expected cost.
    costs: tuple[tuple[str, tuple[tuple[str, float], ...]], ...] = ()
    # the cost of asking a person instead of deciding; set, decide() asks whenever every outcome's expected cost
    # is above it (the band where either answer is costly). Unset, decide() never asks.
    ask: float | None = None
    # a named output's closed set of outcomes (spec `outputs`); empty: any outcome
    values: tuple[str, ...] = ()
    # a confidence bar: set, decide() asks whenever the most probable outcome's probability is under it (beside
    # `ask`, for people who think in confidence before costs). Unset, confidence alone never asks.
    ask_below: float | None = None
    # what the outcome is (kernel 3.15.0): "choice" one of `values`; "score" one of `values` in order (a mistake
    # costs how many levels it is off); "noul" yes or no ("false", "true": decide() says P(true) as `p`);
    # "number" a value in [min, max] learned by its bin (`values` the bins' midpoints, a mistake costs how many
    # bins it is off; decide() says the expected `value`); "many" any of `values` at once (each value a noul of
    # its own, a member output named <output>--<i>)
    kind: str = "choice"
    number: tuple[float, float, float] | None = None  # a number's (min, max, step)
    # a discriminated union: the output is asked only when another output's outcome is one of these (decide_all
    # answers it {"applies": false} otherwise, and a case may not grade it then)
    when: tuple[str, tuple[str, ...]] | None = None
    of: tuple[str, str] | None = None  # a many output's member: (the many output, the value it stands for)

    def cost(self, decided: str, true: str) -> float:
        table = dict((d, dict(t)) for d, t in self.costs)
        if decided in table and true in table[decided]:
            return table[decided][true]
        if decided == true:
            return 0.0
        if self.kind in ("score", "number") and decided in self.values and true in self.values:
            return float(abs(self.values.index(decided) - self.values.index(true)))
        return 1.0

    def bin_of(self, value: float) -> str:
        """A number's bin: the midpoint label of the step it falls in (clamped to [min, max])."""
        lo, hi, step = self.number  # type: ignore[misc]
        i = min(max(int((min(max(value, lo), hi) - lo) // step), 0), len(self.values) - 1)
        return self.values[i]


@dataclass(frozen=True)
class Spec:
    name: str
    layers: tuple[Layer, ...]
    dimension: int = kernel.DIM
    seed: int = 42
    similarity_weight: float = 1.0
    security_weight: float = 0.0
    temporal_source: str = "auto"
    output: Output = field(default_factory=Output)
    interactions: tuple[Interaction, ...] = ()
    settings: Settings = field(default_factory=Settings)
    # named outputs (spec `outputs`): each a decision of its own about the same case; none: the one default output
    outputs: tuple[tuple[str, Output], ...] = ()

    def with_settings(self, settings: Settings) -> Spec:
        return dataclasses.replace(self, settings=settings)

    def output_of(self, output: str | None) -> Output:
        """An output's costs, ask and values: a named one's from `outputs`, the default's from `output`. An output
        the spec does not name raises SpecError (E_OUTPUT)."""
        name = kernel.DEFAULT if output is None else output
        if name == kernel.DEFAULT:
            return self.output
        found = dict(self.outputs).get(name)
        if found is None:
            raise SpecError(f"outputs.{name}", "E_OUTPUT: the spec names no such output")
        return found

    def check_outcome(self, output: str | None, value: str) -> None:
        """Refuse an outcome outside its output's closed set (E_OUTPUT_VALUE)."""
        values = self.output_of(output).values
        if values and value not in values:
            raise SpecError(f"outputs.{output}", f"E_OUTPUT_VALUE: {value!r} is not one of {', '.join(values)}")

    def declared(self) -> list[str]:
        """The outputs the spec names (a many output's members are not among them)."""
        return [name for name, o in self.outputs if o.of is None]

    def stored(self) -> list[str]:
        """The outputs a precedent carries outcomes for: every declared one but a many output, and its members."""
        return [name for name, o in self.outputs if o.kind != "many"]

    def members(self, output: str) -> list[tuple[str, str]]:
        """A many output's members: (member output, the value it stands for)."""
        return [(name, o.of[1]) for name, o in self.outputs if o.of is not None and o.of[0] == output]

    def outcomes_in(self, named: Mapping[str, Any]) -> dict[str, Any]:
        """A case's named outcomes as the store keeps them: a number as its bin, a noul's true/false (a bool
        too), a many output's list as its members' "true"/"false"; each checked (E_OUTPUT, E_OUTPUT_VALUE), and a
        union's output refused where the case's own outcome of the output it hangs on leaves it out
        (E_OUTPUT_WHEN). None (no outcome) passes as it is."""
        out: dict[str, Any] = {}
        for name, value in named.items():
            o = self.output_of(name)
            if value is None and o.kind == "many":
                out.update({member: None for member, _ in self.members(name)})
            elif value is None or o.of is not None:
                out[name] = value
            elif o.kind == "many":
                if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) for v in value):
                    raise SpecError(f"outputs.{name}", "a many output's outcome is a list of its values")
                for v in value:
                    if v not in o.values:
                        raise SpecError(f"outputs.{name}", f"E_OUTPUT_VALUE: {v!r} is not one of {', '.join(o.values)}")
                for member, v in self.members(name):
                    out[member] = "true" if v in value else "false"
            elif o.kind == "number":
                out[name] = o.bin_of(_number(value, f"outputs.{name}"))
            elif o.kind == "noul" and isinstance(value, bool):
                out[name] = "true" if value else "false"
            else:
                if isinstance(value, str):  # anything else the store refuses (a non-empty string)
                    self.check_outcome(name, value)
                out[name] = value
        for name, value in out.items():
            when = self.output_of(name).when
            if value is not None and when and isinstance(out.get(when[0]), str) and out[when[0]] not in when[1]:
                raise SpecError(
                    f"outputs.{name}",
                    f"E_OUTPUT_WHEN: asked only when {when[0]} is {' or '.join(when[1])}, not {out[when[0]]!r}",
                )
        return out

    # -- JSON in and out --------------------------------------------

    @classmethod
    def from_json(cls, obj: Any) -> Spec:
        """Validated exactly: an unknown field, a missing one or a value
        of the wrong kind raises SpecError naming where."""
        return _parse_spec(obj)

    def to_json(self) -> dict[str, Any]:
        def role(r: Role) -> dict[str, Any]:
            out: dict[str, Any] = {
                "name": r.name,
                "similarity_weight": r.similarity_weight,
                "security_weight": r.security_weight,
                "key_part": r.key_part,
            }
            if r.numeric_config:
                n = r.numeric_config
                out["numeric_config"] = {"min_value": n.min_value, "max_value": n.max_value, "bin_width": n.bin_width}
            if r.text_encoding:
                out["text_encoding"] = r.text_encoding
            if r.lexicons:
                out["lexicons"] = list(r.lexicons)
            if r.value_weights:
                out["value_weights"] = dict(r.value_weights)
            return out

        return {
            "version": SPEC_VERSION,
            "name": self.name,
            "dimension": self.dimension,
            "seed": self.seed,
            "similarity_weight": self.similarity_weight,
            "security_weight": self.security_weight,
            "temporal_source": self.temporal_source,
            "output": {
                "report": list(self.output.report),
                **({"costs": {d: dict(t) for d, t in self.output.costs}} if self.output.costs else {}),
                **({"ask": self.output.ask} if self.output.ask is not None else {}),
                **({"ask_below": self.output.ask_below} if self.output.ask_below is not None else {}),
            },
            **(
                {
                    "outputs": {
                        name: {
                            **({"kind": o.kind} if o.kind != "choice" else {}),
                            **(
                                {"number": dict(zip(("min", "max", "step"), o.number, strict=True))}
                                if o.number
                                else {"values": list(o.values)}
                                if o.values and o.kind != "noul"
                                else {}
                            ),
                            **({"when": {"output": o.when[0], "in": list(o.when[1])}} if o.when else {}),
                            **({"costs": {d: dict(t) for d, t in o.costs}} if o.costs else {}),
                            **({"ask": o.ask} if o.ask is not None else {}),
                            **({"ask_below": o.ask_below} if o.ask_below is not None else {}),
                        }
                        for name, o in self.outputs
                        if o.of is None
                    }
                }
                if self.outputs
                else {}
            ),
            **({"settings": self.settings.to_json()} if self.settings.to_json() else {}),
            **(
                {
                    INTERACTIONS: [
                        {
                            "name": i.name,
                            "roles": list(i.roles),
                            "similarity_weight": i.similarity_weight,
                            **({"value_weights": dict(i.value_weights)} if i.value_weights else {}),
                        }
                        for i in self.interactions
                    ]
                }
                if self.interactions
                else {}
            ),
            "layers": [
                {
                    "name": l.name,
                    "similarity_weight": l.similarity_weight,
                    "security_weight": l.security_weight,
                    "segments": [
                        {
                            "name": s.name,
                            "similarity_weight": s.similarity_weight,
                            "security_weight": s.security_weight,
                            "roles": [role(r) for r in s.roles],
                        }
                        for s in l.segments
                    ],
                }
                for l in self.layers
            ],
        }

    def learned(self, cases: Sequence[tuple[Any, str]]) -> Spec:
        """This spec with its weights learned from graded cases: each role's similarity_weight is how much knowing
        its value tells about the outcome (information gain, scaled so the most telling role weighs 1), and each
        value's weight how far that value moves the outcome from the base rate (scaled so the most telling value
        of a role weighs 1). Key parts, text roles and roles that carry sets keep their weights (a set has no one
        value to weigh). Layers' and segments' weights are left as they are; so are security weights."""
        return self.with_weights(self.learn([(self.situation(data), outcome) for data, outcome in cases]))

    def learn(self, situations: Sequence[tuple[Mapping[str, Any], str]]) -> dict[str, dict[str, Any]]:
        """What graded situations (already in the kernel's terms) teach: per role path, its similarity_weight and
        value_weights, as learned() sets them. A model learns from its own store this way."""
        base = Counter(outcome for _, outcome in situations)
        if len(base) < 2:
            raise SpecError("", "learn needs cases with at least two outcomes")
        h_base = _entropy(base)
        gains: dict[str, float] = {}
        moves: dict[str, dict[str, float]] = {}
        words_learned: dict[str, dict[str, float]] = {}
        text_paths: list[str] = []
        base_rate = {o: n / sum(base.values()) for o, n in base.items()}
        for layer in self.layers:
            for seg in layer.segments:
                for role in seg.roles:
                    path = f"{layer.name}.{seg.name}.{role.name}"
                    if role.text_encoding:
                        text_paths.append(path)
                        if self.settings.word_weights:
                            learned_words = self._learn_words(layer.name, seg.name, role.name, situations, base_rate)
                            if learned_words:
                                words_learned[path] = learned_words
                        continue
                    if role.key_part:
                        continue
                    graded = [
                        (situation.get(layer.name, {}).get(seg.name, {}).get(role.name), outcome)
                        for situation, outcome in situations
                    ]
                    if role.numeric_config is None and any(isinstance(v, list) for v, _ in graded):
                        continue  # a role of sets: no one value to weigh; left alone, as a text role is
                    groups: dict[str, Counter] = defaultdict(Counter)
                    for value, outcome in graded:
                        if value is None:
                            continue
                        key = kernel._text(value[-1]) if role.numeric_config is not None else kernel._text(value)
                        groups[key][outcome] += 1
                    total = sum(sum(g.values()) for g in groups.values())
                    if not total:
                        continue
                    after = sum(sum(g.values()) / total * _entropy(g) for g in groups.values())
                    gains[path] = max(h_base - after, 0.0)
                    moves[path] = {
                        key: max(abs(g[o] / sum(g.values()) - base_rate.get(o, 0.0)) for o in base)
                        for key, g in groups.items()
                    }
        pairs = self._learn_pairs(situations, gains, base, base_rate, h_base) if self.settings.interactions else []
        top = max([*gains.values(), *(p["similarity_weight"] for p in pairs)], default=0.0)  # the strongest weighs 1
        learned: dict[str, Any] = {}
        for path, gain in gains.items():
            if top > 0:
                learned[path] = {"similarity_weight": round(gain / top, 4)}
                best = max(moves[path].values(), default=0.0)
                if best > 0:
                    learned[path]["value_weights"] = {k: round(m / best, 4) for k, m in moves[path].items()}
        if top > 0:
            for pair in pairs:
                pair["similarity_weight"] = round(pair["similarity_weight"] / top, 4)
            learned["~" + INTERACTIONS] = [p for p in pairs if p["similarity_weight"] > 0.1][: self.settings.max_interactions]
        for path, weights in words_learned.items():
            learned[path] = {**learned.get(path, {}), "value_weights": weights}
        evidence = {path: self._learn_evidence(path, situations) for path in text_paths}
        if evidence:
            learned["~evidence"] = evidence
        return learned

    def _learn_evidence(self, path: str, situations: Sequence[tuple[Mapping[str, Any], str]]) -> dict[str, Any]:
        """What each word says of each outcome: the counts a model turns into pointwise mutual information at query
        time (Model.bias), for words seen at least `rare` times. Not a weight in the spec: evidence the store holds."""
        lname, sname, rname = path.split(".")
        outcomes: Counter = Counter()
        words: dict[str, Counter] = defaultdict(Counter)
        total = 0
        for situation, outcome in situations:
            value = situation.get(lname, {}).get(sname, {}).get(rname)
            if value is None:
                continue
            total += 1
            outcomes[outcome] += 1
            for word in set(_words_of(value)):
                words[word][outcome] += 1
        kept = {w: dict(c) for w, c in words.items() if sum(c.values()) >= self.settings.rare}
        return {"total": total, "outcomes": dict(outcomes), "words": kept}

    def _learn_words(
        self,
        lname: str,
        sname: str,
        rname: str,
        situations: Sequence[tuple[Mapping[str, Any], str]],
        base_rate: Mapping[str, float],
    ) -> dict[str, float]:
        """What each word of a text role says about the outcome: how far the word's presence moves some outcome
        from its base rate (the same measure a field's values get; not information gain, which with many outcomes
        crowns the words that split them into big groups, "card", not the ones that name one, "stolen"), scaled
        from the settings' word_floor (tells nothing; 0.35 by default, chosen on Banking77 inside its training set:
        a bag's glyph is a majority vote, and a low floor let the few loud words drown the many quiet ones) to 1
        (the most telling word). Words seen fewer than `rare` times are left out: they get the floor."""
        seen: dict[str, Counter] = defaultdict(Counter)
        total = 0
        for situation, outcome in situations:
            value = situation.get(lname, {}).get(sname, {}).get(rname)
            if value is None:
                continue
            total += 1
            for word in _words_of(value):
                seen[word][outcome] += 1
        if total < self.settings.rare:
            return {}
        moves: dict[str, float] = {}
        for word, present in seen.items():
            n_present = sum(present.values())
            if n_present < self.settings.rare:
                continue
            moves[word] = max(max(present[o] / n_present - base_rate.get(o, 0.0) for o in present), 0.0)
        top = max(moves.values(), default=0.0)
        if top <= 0:
            return {}
        floor = self.settings.word_floor
        table = {word: round(floor + (1 - floor) * move / top, 4) for word, move in sorted(moves.items())}
        if self.settings.word_pairs and self.settings.max_word_pairs:
            common = {w: sum(seen[w].values()) for w in moves}
            table.update(self._learn_word_pairs(lname, sname, rname, situations, base_rate, moves, common, top, floor))
        return table

    def _learn_word_pairs(
        self,
        lname: str,
        sname: str,
        rname: str,
        situations: Sequence[tuple[Mapping[str, Any], str]],
        base_rate: Mapping[str, float],
        moves: Mapping[str, float],
        common: Mapping[str, int],
        top: float,
        floor: float,
    ) -> dict[str, float]:
        """Pairs of words that move the outcome further together than the better of them alone ("top" + "up",
        "card" + "arrive"), among the PAIR_CANDIDATES most common words (the rare ones are telling on their own;
        it is the common, ambiguous ones a partner settles), seen together at least `rare` times: the pair's
        extra move scaled like a word's, the max_word_pairs best kept, keyed "a+b"."""
        candidates = sorted(sorted(common, key=lambda w: -common[w])[:PAIR_CANDIDATES])
        wanted = set(candidates)
        together: dict[tuple[str, str], Counter] = defaultdict(Counter)
        for situation, outcome in situations:
            value = situation.get(lname, {}).get(sname, {}).get(rname)
            if value is None:
                continue
            present = sorted(wanted.intersection(_words_of(value)))
            for pair in itertools.combinations(present, 2):
                together[pair][outcome] += 1
        extras = {}
        for (a, b), counts in together.items():
            n = sum(counts.values())
            if n < self.settings.rare:
                continue
            move = max(counts[o] / n - base_rate.get(o, 0.0) for o in counts)
            extra = move - max(moves[a], moves[b])
            if extra > 0:
                extras[f"{a}+{b}"] = extra
        best = sorted(extras.items(), key=lambda kv: (-kv[1], kv[0]))[: self.settings.max_word_pairs]
        return {pair: round(floor + (1 - floor) * min(extra / top, 1.0), 4) for pair, extra in sorted(best)}

    def _learn_pairs(
        self,
        situations: Sequence[tuple[Mapping[str, Any], str]],
        gains: Mapping[str, float],
        base: Counter,
        base_rate: Mapping[str, float],
        h_base: float,
    ) -> list[dict[str, Any]]:
        """The pairs of roles that tell more together than the better of them alone: each pair's extra information
        gain over its best role (unscaled here; learn() scales it like a role's and keeps the settings'
        max_interactions best over a tenth of the strongest signal), values seen fewer than `rare` times pooled so
        the gain is not sparsity's."""
        paths = list(gains)
        found = []
        for a, b in itertools.combinations(paths, 2):
            groups: dict[str, Counter] = defaultdict(Counter)
            for situation, outcome in situations:
                pair = self._pair_value(situation, a, b)
                if pair is not None:
                    groups[pair][outcome] += 1
            if not groups:
                continue
            counted = Counter({k: sum(g.values()) for k, g in groups.items()})
            pooled: dict[str, Counter] = defaultdict(Counter)
            for k, g in groups.items():
                pooled[k if counted[k] >= self.settings.rare else "~"].update(g)
            total = sum(counted.values())
            after = sum(sum(g.values()) / total * _entropy(g) for g in pooled.values())
            extra = max(h_base - after, 0.0) - max(gains[a], gains[b])
            if extra > 0:
                moves = {
                    k: max(abs(g[o] / sum(g.values()) - base_rate.get(o, 0.0)) for o in base)
                    for k, g in groups.items()
                    if counted[k] >= self.settings.rare
                }
                best = max(moves.values(), default=0.0)
                found.append(
                    {
                        "name": f"{a.rsplit('.', 1)[1]}_x_{b.rsplit('.', 1)[1]}",
                        "roles": [a, b],
                        "similarity_weight": extra,
                        **({"value_weights": {k: round(m / best, 4) for k, m in moves.items()}} if best > 0 else {}),
                    }
                )
        found.sort(key=lambda f: (-f["similarity_weight"], f["name"]))
        return found

    def with_weights(self, learned: Mapping[str, Any]) -> Spec:
        """This spec with learned role weights (learn()'s table) put in, and its interactions replaced by the
        learned ones when the table names them; a path the spec lacks is ignored."""
        obj = self.to_json()
        if "~" + INTERACTIONS in learned:
            obj.pop(INTERACTIONS, None)
            if learned["~" + INTERACTIONS]:
                obj[INTERACTIONS] = [dict(i) for i in learned["~" + INTERACTIONS]]
        for layer in obj["layers"]:
            for seg in layer["segments"]:
                for role in seg["roles"]:
                    found = learned.get(f"{layer['name']}.{seg['name']}.{role['name']}")
                    if found:
                        if "similarity_weight" in found:
                            role["similarity_weight"] = found["similarity_weight"]
                        role.pop("value_weights", None)
                        if found.get("value_weights"):
                            role["value_weights"] = dict(found["value_weights"])
        return Spec.from_json(obj)

    @property
    def spec_id(self) -> str:
        """Content address: the same spec gives the same id anywhere. The settings are not part of it: they are the
        model's levers, not what a case is."""
        text = json.dumps({k: v for k, v in self.to_json().items() if k != "settings"}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    # -- data in the spec's shape -----------------------------------

    def situation(self, data: Any) -> dict[str, Any]:
        """The data, checked against the spec, in the kernel's terms:
        layer > segment > role, each value a symbol, a set of symbols, a
        bag of words or a thermometer. Empty parts are left out."""
        if not isinstance(data, dict):
            raise SpecError("", "data is an object of layers")
        out: dict[str, Any] = {}
        for lname, lval in data.items():
            layer = self._layer(lname)
            if not isinstance(lval, dict):
                raise SpecError(lname, "a layer is an object of segments")
            segs: dict[str, Any] = {}
            for sname, sval in lval.items():
                seg = self._segment(layer, sname, lname)
                if not isinstance(sval, dict):
                    raise SpecError(f"{lname}.{sname}", "a segment is an object of roles")
                roles: dict[str, Any] = {}
                for rname, rval in sval.items():
                    role = self._role(seg, rname, f"{lname}.{sname}")
                    path = f"{lname}.{sname}.{role.name}"
                    if role.name in roles:
                        raise SpecError(path, "given twice (by name and by lexicon)")
                    value = _value(role, rval, path)
                    if value is not None:
                        roles[role.name] = value
                if roles:
                    segs[seg.name] = roles
            if segs:
                out[layer.name] = segs
        if not out:
            raise SpecError("", "no role carries a value")
        return self._crossed(self._weighed(out))

    def _weighed(self, situation: dict[str, Any]) -> dict[str, Any]:
        """The situation with every text role's bag carrying the role's learned word weights ([[word, weight],
        ...]; a word not learned weighs the settings' word_floor), or plain words where the role learned none."""
        out: dict[str, Any] = {}
        for lname, segs in situation.items():
            layer = self._find(self.layers, lname)
            if layer is None:
                out[lname] = segs
                continue
            new_segs: dict[str, Any] = {}
            for sname, roles in segs.items():
                seg = self._find(layer.segments, sname)
                new_roles: dict[str, Any] = {}
                for rname, value in roles.items():
                    role = self._find(seg.roles, rname) if seg else None
                    if role is not None and role.text_encoding and isinstance(value, list):
                        words = _words_of(value)
                        table = dict(role.value_weights)
                        if table:
                            value = [[w, table.get(w, self.settings.word_floor)] for w in words]
                            have = set(words)
                            for pair, weight in table.items():
                                if "+" in pair and all(part in have for part in pair.split("+", 1)):
                                    value.append([pair, weight])
                        elif self.settings.lexicon:
                            value = [[w, 1.0] for w in words]  # a weighted set: read through the lexicon
                        else:
                            value = words
                    new_roles[rname] = value
                new_segs[sname] = new_roles
            out[lname] = new_segs
        return out

    def _crossed(self, situation: dict[str, Any]) -> dict[str, Any]:
        """The situation with the spec's interactions layer (from its roles' values), replacing any it had."""
        out = {k: v for k, v in situation.items() if k != INTERACTIONS}
        pairs = {}
        for i in self.interactions:
            value = self._pair_value(out, *i.roles)
            if value is not None:
                pairs[i.name] = value
        if pairs:
            out[INTERACTIONS] = {"pairs": pairs}
        return out

    def _pair_value(self, situation: Mapping[str, Any], a: str, b: str) -> str | None:
        """The two roles' values as one (a number by its bin), or None when either is missing, a set or a text."""
        texts = []
        for path in (a, b):
            lname, sname, rname = path.split(".")
            layer = self._find(self.layers, lname)
            seg = self._find(layer.segments, sname) if layer else None
            role = self._find(seg.roles, rname) if seg else None
            v = situation.get(lname, {}).get(sname, {}).get(rname)
            if role is None or v is None or role.text_encoding or (isinstance(v, list) and role.numeric_config is None):
                return None
            texts.append(kernel._text(v[-1]) if isinstance(v, list) else kernel._text(v))
        return "|".join(texts)

    def restate(self, situation: Mapping[str, Any]) -> dict[str, Any]:
        """A stored situation brought to this spec's word weights and interactions (for Space.rewrite when they
        change)."""
        return self._crossed(self._weighed(dict(situation)))

    recross = restate

    def weights(self, clearance: float = 1.0, present: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """The kernel weights tree: every level's similarity_weight, 0 for
        whatever the clearance may not see and, given `present` (a
        situation), 0 for every part it leaves out. With level_weights
        "roles" a segment's weight is its own times its roles' summed,
        a layer's its own times its segments', and the pairs layer the
        sum of its pairs: the score is then each role's weighted mean
        wherever it sits."""
        if self.security_weight > clearance:
            raise SpecError("", "this model is above the reader's clearance")
        by_roles = self.settings.level_weights == "roles"
        tree: dict[str, Any] = {}
        for l in self.layers:
            lp = (present or {}).get(l.name) if present is not None else None
            lw = 0.0 if l.security_weight > clearance or (present is not None and lp is None) else l.similarity_weight
            segs: dict[str, Any] = {"*": lw}
            for s in l.segments:
                sp = lp.get(s.name) if isinstance(lp, dict) else None
                sw = (
                    0.0
                    if s.security_weight > clearance or (present is not None and sp is None)
                    else s.similarity_weight
                )
                roles: dict[str, Any] = {"*": sw}
                for r in s.roles:
                    gone = present is not None and not (isinstance(sp, dict) and r.name in sp)
                    if r.security_weight > clearance or gone:
                        roles[r.name] = 0.0
                    else:
                        value = sp.get(r.name) if isinstance(sp, dict) else None
                        roles[r.name] = r.similarity_weight * r.value_weight(value)
                if by_roles:
                    roles["*"] = sw * sum(v for k, v in roles.items() if k != "*")
                segs[s.name] = roles
            if by_roles:
                segs["*"] = lw * sum(v["*"] for k, v in segs.items() if k != "*")
            tree[l.name] = segs
        if self.interactions:
            ip = (present or {}).get(INTERACTIONS) if present is not None else None
            pairs: dict[str, Any] = {}
            for i in self.interactions:
                value = ip["pairs"].get(i.name) if isinstance(ip, dict) else None
                gone = present is not None and value is None
                if gone or self._security_of(i.roles[0]) > clearance or self._security_of(i.roles[1]) > clearance:
                    pairs[i.name] = 0.0
                else:
                    pairs[i.name] = i.similarity_weight * i.value_weight(value)
            own = sum(pairs.values()) if by_roles else max(pairs.values(), default=0.0)
            tree[INTERACTIONS] = {"*": 0.0 if (present is not None and ip is None) else own, "pairs": {"*": 1.0, **pairs}}
        return tree

    def _security_of(self, path: str) -> float:
        lname, sname, rname = path.split(".")
        layer = self._find(self.layers, lname)
        seg = self._find(layer.segments, sname) if layer else None
        role = self._find(seg.roles, rname) if seg else None
        return max(layer.security_weight if layer else 0.0, seg.security_weight if seg else 0.0, role.security_weight if role else 0.0)

    def key(self, situation: Mapping[str, Any]) -> str | None:
        """The record id from its key_part roles, or None if it has none."""
        parts = []
        for l in self.layers:
            for s in l.segments:
                for r in s.roles:
                    if r.key_part:
                        v = situation.get(l.name, {}).get(s.name, {}).get(r.name)
                        if v is None:
                            raise SpecError(f"{l.name}.{s.name}.{r.name}", "a key part is required")
                        parts.append(json.dumps(v, sort_keys=True, ensure_ascii=False))
        if not parts:
            return None
        return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:12]

    def timestamp(self, data: Mapping[str, Any]) -> float | None:
        """Epoch seconds from the temporal_source role, None for "auto"."""
        if self.temporal_source == "auto":
            return None
        lname, sname, rname = self.temporal_source.split(".")
        v = data.get(lname, {}).get(sname, {}).get(rname)
        if v is None:
            return None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass
        raise SpecError(self.temporal_source, "a time is epoch seconds or an ISO 8601 string")

    def report(self, tree: dict[str, Any], clearance: float = 1.0) -> dict[str, Any]:
        """A kernel fact tree (FactTree.to_json()["tree"]) cut to what the
        reader may see and to output.report."""
        keep = self.output.report
        out = dict(tree)
        out["children"] = []
        for lnode in tree.get("children", []):
            layer = self._find(self.layers, lnode["key"])
            if layer is None or layer.security_weight > clearance:
                continue
            ln = dict(lnode)
            ln["children"] = []
            for snode in lnode.get("children", []):
                seg = self._find(layer.segments, snode["key"])
                if seg is None or seg.security_weight > clearance:
                    continue
                sn = dict(snode)
                sn["children"] = [
                    rn
                    for rn in snode.get("children", [])
                    if (r := self._find(seg.roles, rn["key"])) is not None
                    and r.security_weight <= clearance
                    and _kept(keep, f"{layer.name}.{seg.name}.{r.name}")
                ]
                if sn["children"]:
                    ln["children"].append(sn)
            if ln["children"]:
                out["children"].append(ln)
        return out

    # -- lookups ----------------------------------------------------

    @staticmethod
    def _find(items: Sequence[Any], name: str) -> Any:
        return next((x for x in items if x.name == name), None)

    def _layer(self, name: str) -> Layer:
        layer = self._find(self.layers, name)
        if layer is None:
            raise SpecError(name, "no such layer")
        return layer

    def _segment(self, layer: Layer, name: str, at: str) -> Segment:
        seg = self._find(layer.segments, name)
        if seg is None:
            raise SpecError(f"{at}.{name}", "no such segment")
        return seg

    def _role(self, seg: Segment, name: str, at: str) -> Role:
        for r in seg.roles:
            if r.name == name or name in r.lexicons:
                return r
        raise SpecError(f"{at}.{name}", "no such role")


def _words_of(value: Any) -> list[str]:
    """The words of a stored bag, weighted or plain; its pairs ("a+b") are not words."""
    items = [x[0] if isinstance(x, list) else x for x in value]
    return [w for w in items if "+" not in w]


def _word_tables(spec: Spec) -> dict[str, tuple[tuple[str, float], ...]]:
    return {
        f"{l.name}.{s.name}.{r.name}": r.value_weights
        for l in spec.layers
        for s in l.segments
        for r in s.roles
        if r.text_encoding
    }


def _entropy(counts: Counter) -> float:
    n = sum(counts.values())
    return -sum(c / n * math.log2(c / n) for c in counts.values() if c) if n else 0.0


def _kept(keep: Sequence[str], path: str) -> bool:
    return not keep or any(path == k or path.startswith(k + ".") for k in keep)


def _value(role: Role, v: Any, path: str) -> Any:
    """One role's value in kernel terms, or None when it carries nothing."""
    if v is None:
        return None
    if role.numeric_config is not None:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise SpecError(path, "a numeric role takes a finite number")
        return role.numeric_config.bins(float(v))
    if role.text_encoding == "bag_of_words":
        if not isinstance(v, str):
            raise SpecError(path, "a bag_of_words role takes a string")
        words = sorted(set(_WORD.findall(v.lower())))
        return words or None
    if isinstance(v, (list, tuple)):
        items = [x for x in v if x is not None]
        for x in items:
            if isinstance(x, (dict, list, tuple)):
                raise SpecError(path, "a set holds scalars")
        return sorted(set(items), key=kernel._text) or None
    if isinstance(v, dict):
        raise SpecError(path, "a role takes a scalar or a set of scalars")
    return v


# ── parsing ─────────────────────────────────────────────────────────


def _fields(obj: Any, path: str, required: Sequence[str], optional: Sequence[str]) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise SpecError(path, "must be an object")
    unknown = sorted(set(obj) - set(required) - set(optional))
    if unknown:
        raise SpecError(path, f"unknown field(s): {', '.join(unknown)}")
    missing = [k for k in required if k not in obj]
    if missing:
        raise SpecError(path, f"missing field(s): {', '.join(missing)}")
    return obj


def _name(v: Any, path: str) -> str:
    if not isinstance(v, str) or not _NAME.match(v):
        raise SpecError(path, "a name is 1-64 letters, digits, _ or -, not starting with a digit")
    return v


def _unit(v: Any, path: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0.0 <= v <= 1.0:
        raise SpecError(path, "must be a number from 0 to 1")
    return float(v)


def _number(v: Any, path: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise SpecError(path, "must be a finite number")
    return float(v)


def _unique(names: list[str], path: str) -> None:
    seen = set()
    for n in names:
        if n in seen:
            raise SpecError(path, f"'{n}' is named twice")
        seen.add(n)


def _parse_role(obj: Any, path: str) -> Role:
    o = _fields(
        obj,
        path,
        ["name"],
        ["similarity_weight", "security_weight", "key_part", "numeric_config", "text_encoding", "lexicons", "value_weights"],
    )
    name = _name(o["name"], f"{path}.name")
    at = f"{path}({name})"
    numeric = None
    if o.get("numeric_config") is not None:
        n = _fields(o["numeric_config"], f"{at}.numeric_config", ["min_value", "max_value", "bin_width"], [])
        numeric = NumericConfig(
            _number(n["min_value"], f"{at}.numeric_config.min_value"),
            _number(n["max_value"], f"{at}.numeric_config.max_value"),
            _number(n["bin_width"], f"{at}.numeric_config.bin_width"),
        )
        if numeric.max_value <= numeric.min_value or numeric.bin_width <= 0:
            raise SpecError(f"{at}.numeric_config", "needs min_value < max_value and bin_width > 0")
        if (numeric.max_value - numeric.min_value) / numeric.bin_width > 1000:
            raise SpecError(f"{at}.numeric_config", "more than 1000 bins")
    text = o.get("text_encoding")
    if text not in (None, "bag_of_words"):
        raise SpecError(f"{at}.text_encoding", 'is "bag_of_words" or absent')
    if numeric and text:
        raise SpecError(at, "a role is numeric or text, not both")
    lex = o.get("lexicons", [])
    if not isinstance(lex, list):
        raise SpecError(f"{at}.lexicons", "must be a list of names")
    key_part = o.get("key_part", False)
    if not isinstance(key_part, bool):
        raise SpecError(f"{at}.key_part", "must be true or false")
    vw = o.get("value_weights", {})
    if not isinstance(vw, dict) or not all(isinstance(k, str) for k in vw):
        raise SpecError(f"{at}.value_weights", "must be an object of value: weight")
    value_weights = tuple((k, _unit(v, f"{at}.value_weights.{k}")) for k, v in sorted(vw.items()))
    return Role(
        name,
        _unit(o.get("similarity_weight", 1.0), f"{at}.similarity_weight"),
        _unit(o.get("security_weight", 0.0), f"{at}.security_weight"),
        key_part,
        numeric,
        text,
        tuple(_name(x, f"{at}.lexicons") for x in lex),
        value_weights,
    )


def _parse_interactions(obj: Any) -> tuple[Interaction, ...]:
    if not isinstance(obj, list):
        raise SpecError(INTERACTIONS, "must be a list")
    out = []
    for n, io in enumerate(obj):
        at = f"{INTERACTIONS}[{n}]"
        i = _fields(io, at, ["name", "roles"], ["similarity_weight", "value_weights"])
        roles = i["roles"]
        if not isinstance(roles, list) or len(roles) != 2 or not all(isinstance(r, str) for r in roles) or roles[0] == roles[1]:
            raise SpecError(f"{at}.roles", "two different layer.segment.role paths")
        vw = i.get("value_weights", {})
        if not isinstance(vw, dict) or not all(isinstance(k, str) for k in vw):
            raise SpecError(f"{at}.value_weights", "must be an object of value: weight")
        out.append(
            Interaction(
                _name(i["name"], f"{at}.name"),
                (roles[0], roles[1]),
                _unit(i.get("similarity_weight", 1.0), f"{at}.similarity_weight"),
                tuple((k, _unit(v, f"{at}.value_weights.{k}")) for k, v in sorted(vw.items())),
            )
        )
    _unique([i.name for i in out], INTERACTIONS)
    return tuple(out)


def _parse_spec(obj: Any) -> Spec:
    o = _fields(
        obj,
        "",
        ["name", "layers"],
        [
            "version",
            "dimension",
            "seed",
            "similarity_weight",
            "security_weight",
            "temporal_source",
            "output",
            "outputs",
            INTERACTIONS,
            "settings",
        ],
    )
    if o.get("version", SPEC_VERSION) != SPEC_VERSION:
        raise SpecError("version", f"this kernel reads spec version {SPEC_VERSION}")
    dim = o.get("dimension", kernel.DIM)
    if isinstance(dim, bool) or not isinstance(dim, int) or not 256 <= dim <= 65536:
        raise SpecError("dimension", "must be an integer from 256 to 65536")
    seed = o.get("seed", 42)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise SpecError("seed", "must be an integer")
    if not isinstance(o["layers"], list) or not o["layers"]:
        raise SpecError("layers", "at least one layer")
    layers = []
    for i, lo in enumerate(o["layers"]):
        lp = f"layers[{i}]"
        l = _fields(lo, lp, ["name", "segments"], ["similarity_weight", "security_weight"])
        if not isinstance(l["segments"], list) or not l["segments"]:
            raise SpecError(f"{lp}.segments", "at least one segment")
        segs = []
        for j, so in enumerate(l["segments"]):
            sp = f"{lp}.segments[{j}]"
            s = _fields(so, sp, ["name", "roles"], ["similarity_weight", "security_weight"])
            if not isinstance(s["roles"], list) or not s["roles"]:
                raise SpecError(f"{sp}.roles", "at least one role")
            roles = tuple(_parse_role(ro, f"{sp}.roles[{k}]") for k, ro in enumerate(s["roles"]))
            _unique([n for r in roles for n in (r.name, *r.lexicons)], f"{sp}.roles")
            segs.append(
                Segment(
                    _name(s["name"], f"{sp}.name"),
                    roles,
                    _unit(s.get("similarity_weight", 1.0), f"{sp}.similarity_weight"),
                    _unit(s.get("security_weight", 0.0), f"{sp}.security_weight"),
                )
            )
        _unique([s.name for s in segs], f"{lp}.segments")
        layers.append(
            Layer(
                _name(l["name"], f"{lp}.name"),
                tuple(segs),
                _unit(l.get("similarity_weight", 1.0), f"{lp}.similarity_weight"),
                _unit(l.get("security_weight", 0.0), f"{lp}.security_weight"),
            )
        )
    _unique([l.name for l in layers], "layers")
    if any(l.name == INTERACTIONS for l in layers):
        raise SpecError("layers", f'"{INTERACTIONS}" is the layer the spec adds for its interactions')
    out = _fields(o.get("output", {}), "output", [], ["report", "costs", "ask", "ask_below"])
    report = out.get("report", [])
    if not isinstance(report, list) or not all(isinstance(x, str) for x in report):
        raise SpecError("output.report", "must be a list of paths")
    costs, ask = _costs_and_ask(out, "output")
    outputs_in = o.get("outputs", {})
    if not isinstance(outputs_in, dict):
        raise SpecError("outputs", "must be an object: output name -> {values, costs, ask}")
    outputs = []
    for name, spec_of in sorted(outputs_in.items()):
        at = f"outputs.{name}"
        try:
            kernel._output_name(name)
        except ValueError as e:
            raise SpecError(at, str(e)) from None
        if name == kernel.DEFAULT:
            raise SpecError(at, 'the default output is the spec\'s "output"; name the others')
        od = _fields(spec_of, at, [], ["values", "costs", "ask", "ask_below", "kind", "number", "when"])
        kind = od.get("kind", "choice")
        if kind not in OUTPUT_KINDS:
            raise SpecError(f"{at}.kind", f"is one of {', '.join(OUTPUT_KINDS)}")
        values = od.get("values", [])
        if (
            not isinstance(values, list)
            or not all(isinstance(v, str) and v for v in values)
            or len(set(values)) != len(values)
        ):
            raise SpecError(f"{at}.values", "must be a list of distinct, non-empty outcomes")
        number = None
        if kind == "number":
            if "values" in od:
                raise SpecError(f"{at}.values", "a number's outcomes are its bins: give number {min, max, step}")
            nd = _fields(od.get("number"), f"{at}.number", ["min", "max", "step"], [])
            lo, hi, step = (_number(nd[k], f"{at}.number.{k}") for k in ("min", "max", "step"))
            if not (hi > lo and step > 0) or (hi - lo) / step > 1000:
                raise SpecError(f"{at}.number", "needs max above min and a step above 0 (1,000 bins at most)")
            number = (lo, hi, step)
            n = math.ceil((hi - lo) / step - 1e-9)
            values = [f"{lo + (i + 0.5) * step:g}" for i in range(n)]
            if len(set(values)) != len(values):
                raise SpecError(f"{at}.number", "its bins' midpoints must differ as printed (a coarser step)")
        elif "number" in od:
            raise SpecError(f"{at}.number", 'is a number output\'s (kind "number")')
        if kind == "noul":
            if values and values != list(NOUL):
                raise SpecError(f"{at}.values", 'a noul\'s outcomes are "false" and "true"')
            values = list(NOUL)
        if kind in ("score", "many") and len(values) < 2:
            raise SpecError(f"{at}.values", f"a {kind} output names two values or more")
        when = None
        if "when" in od:
            wd = _fields(od["when"], f"{at}.when", ["output", "in"], [])
            if not isinstance(wd["in"], list) or not wd["in"] or not all(isinstance(v, str) for v in wd["in"]):
                raise SpecError(f"{at}.when.in", "must be a list of the other output's outcomes")
            when = (str(wd["output"]), tuple(wd["in"]))
        o_costs, o_ask = _costs_and_ask(od, at)
        if kind == "many" and (o_costs or o_ask is not None or "ask_below" in od):
            raise SpecError(at, "a many output's members decide as nouls: no costs, ask or ask_below")
        named = [d for d, _ in o_costs] + [t for _, table in o_costs for t, _ in table]
        if values and any(v not in values for v in named):
            raise SpecError(f"{at}.costs", "names an outcome outside the output's values")
        outputs.append(
            (name, Output((), o_costs, o_ask, tuple(values), _ask_below(od, at), kind, number, when))
        )
        if kind == "many":
            for i, v in enumerate(values):
                member = f"{name}--{i}"
                if len(member) > 64:
                    raise SpecError(at, "a many output's name leaves room for its members' (<name>--<i>, 64 at most)")
                outputs.append((member, Output((), (), None, NOUL, None, "noul", None, when, (name, v))))
    declared = dict(outputs)
    if len(declared) != len(outputs):
        raise SpecError("outputs", "a many output's member name (<name>--<i>) is named by another output")
    for name, child in outputs:
        if child.when is None or child.of is not None:
            continue
        parent = declared.get(child.when[0])
        if parent is None or parent.of is not None:
            raise SpecError(f"outputs.{name}.when.output", f"names no output of this spec: {child.when[0]!r}")
        if parent.kind in ("number", "many"):
            raise SpecError(f"outputs.{name}.when.output", "hangs on a choice, score or noul output")
        if parent.values and any(v not in parent.values for v in child.when[1]):
            raise SpecError(f"outputs.{name}.when.in", f"names an outcome outside {child.when[0]}'s values")
        seen, at_ = {name}, child.when[0]
        while at_ is not None:
            if at_ in seen:
                raise SpecError(f"outputs.{name}.when", "the outputs' whens go round in a circle")
            seen.add(at_)
            w = declared[at_].when
            at_ = w[0] if w else None
    spec = Spec(
        _name(o["name"], "name"),
        tuple(layers),
        dim,
        seed,
        _unit(o.get("similarity_weight", 1.0), "similarity_weight"),
        _unit(o.get("security_weight", 0.0), "security_weight"),
        str(o.get("temporal_source", "auto")),
        Output(tuple(report), costs, ask, (), _ask_below(out, "output")),
        _parse_interactions(o.get(INTERACTIONS, [])),
        Settings().with_changes(_fields(o.get("settings", {}), "settings", [], list(Settings.RANGES))),
        tuple(outputs),
    )
    for path in report:
        _resolve(spec, path, "output.report")
    for i in spec.interactions:
        for path in i.roles:
            _resolve(spec, path, f"{INTERACTIONS}.{i.name}.roles")
    if spec.temporal_source != "auto":
        if len(spec.temporal_source.split(".")) != 3:
            raise SpecError("temporal_source", 'is "auto" or a layer.segment.role path')
        _resolve(spec, spec.temporal_source, "temporal_source")
    return spec


def _costs_and_ask(obj: Mapping[str, Any], at: str) -> tuple[tuple[tuple[str, tuple[tuple[str, float], ...]], ...], float | None]:
    """An output's costs (decided -> {true: cost}) and ask, checked."""
    costs_in = obj.get("costs", {})
    if not isinstance(costs_in, dict) or not all(isinstance(t, dict) for t in costs_in.values()):
        raise SpecError(f"{at}.costs", "must be an object: decided outcome -> {true outcome: cost}")
    costs = tuple(
        (str(d), tuple((str(t), _number(c, f"{at}.costs.{d}.{t}")) for t, c in sorted(table.items())))
        for d, table in sorted(costs_in.items())
    )
    ask = obj.get("ask")
    return costs, (None if ask is None else _number(ask, f"{at}.ask"))


def _ask_below(obj: Mapping[str, Any], at: str) -> float | None:
    """An output's confidence bar (ask_below), checked: a probability, or absent."""
    value = obj.get("ask_below")
    return None if value is None else _unit(value, f"{at}.ask_below")


def _resolve(spec: Spec, path: str, at: str) -> None:
    parts = path.split(".")
    if not 1 <= len(parts) <= 3:
        raise SpecError(at, f"'{path}' is not a layer, layer.segment or layer.segment.role path")
    layer = spec._find(spec.layers, parts[0])
    seg = spec._find(layer.segments, parts[1]) if layer and len(parts) > 1 else layer
    role = spec._find(seg.roles, parts[2]) if seg and len(parts) > 2 else seg
    if role is None:
        raise SpecError(at, f"'{path}' names nothing in the spec")


# ── a model: a spec over a Space ────────────────────────────────────


class Model:
    """One model: its spec and its precedents. Data goes in the spec's
    shape; reads come back as fact trees in the spec's shape."""

    def __init__(
        self,
        spec: Spec,
        *,
        author: str = "anon",
        path: str | None = None,
        tau: float | None = None,
        k: int | None = None,
        min_sim: float | None = None,
        refresh_every: int | None = None,
        readonly: bool = False,
        store: kernel.Store | None = None,
    ):
        """The levers come from the spec's `settings`, then from what configure() kept with the store, then from
        the arguments given here (k, min_sim, refresh_every), each over the last. readonly opens the store
        read-only (kernel.Space's readonly): query, facts, probabilities, decide and the settings read as ever;
        record, learn, calibrate, refresh and configure raise kernel.ReadOnlyError (E_READ_ONLY) before
        anything is written, and a restatement on open stays in memory.
        store: where the precedents live, instead of path (a kernel.Store). Over a store that can shortlist
        (glyphh_postgres.PostgresStore) the model holds no precedents in memory: writes go to the store, and
        query, probabilities, facts and decide read the store's `shortlist` nearest and re-rank them exactly once
        it holds `exact_below` precedents (settings), the whole store exactly below that; learn, calibrate and
        refresh load it whole. Such a model restates nothing on open: the job that changes what a case carries
        (learn, configure) rewrites the store."""
        self.given = spec
        self.readonly = bool(readonly)
        self.space = kernel.Space(
            dim=spec.dimension,
            k=spec.settings.k,
            min_sim=spec.settings.min_sim,
            seed=spec.seed,
            author=author,
            path=path,
            tau=tau,
            readonly=readonly,
            store=store,
            lexicon=spec.settings.lexicon,
            load=False,
        )
        kept = self.space.meta("settings")
        self.overrides: dict[str, Any] = dict(kept) if isinstance(kept, dict) else {}
        given = {k_: v for k_, v in (("k", k), ("min_sim", min_sim), ("refresh_every", refresh_every)) if v is not None}
        self.settings = spec.settings.with_changes(self.overrides).with_changes(given)
        self.spec = spec.with_settings(self.settings)
        self.space.lexicon = self.settings.lexicon  # before a glyph is made: the model's own reading of words
        if not hasattr(self.space.store, "shortlist"):
            self.space._ensure_loaded()  # a file, or memory: every precedent held, as ever
        learned = self.space.meta("learned")
        self.evidence: dict[str, Any] = {}
        if isinstance(learned, dict):
            self.spec = self.spec.with_weights(learned)
            self.evidence = learned.get("~evidence", {})
        # each named output's own learned spec and word evidence, and the in-memory view of the store it reads
        # through (its word weights and interactions), made when first read
        self._specs: dict[str, Spec] = {}
        self._evidences: dict[str, dict[str, Any]] = {}
        self._views: dict[str, kernel.Space] = {}
        for name, _ in spec.outputs:
            own = self.space.meta(f"learned:{name}")
            if isinstance(own, dict):
                self._specs[name] = spec.with_settings(self.settings).with_weights(own)
                self._evidences[name] = own.get("~evidence", {})
        self._apply()
        if self.space.loaded and len(self.space):
            # a store recorded under other settings: its bags brought to these (in memory only, read-only)
            self.space.rewrite(self.spec.restate, persist=not self.readonly)

    def _apply(self) -> None:
        """The settings into the Space: its levers, and its reading of words (per model, never the process's:
        one worker serves many models one after another)."""
        self.space.k, self.space.min_sim = self.settings.k, self.settings.min_sim
        self.space.shortlist, self.space.exact_below = self.settings.shortlist, self.settings.exact_below
        self.refresh_every = self.settings.refresh_every
        if self.space.lexicon != self.settings.lexicon:
            self.space.relexicon(self.settings.lexicon, persist=not self.readonly)

    def configure(self, **changes: Any) -> dict[str, Any]:
        """Change the levers live: checked, kept with the store (over the spec's `settings`, until changed again),
        and a learning lever moved relearns the store there and then (when it has learned). Returns every
        setting as it now stands. Read-only, configure() with no changes reads them; any change is refused."""
        if self.readonly:
            if changes:
                raise kernel.ReadOnlyError("configure", self.space.path)
            return self.settings.to_json(all=True)
        new = self.settings.with_changes(changes)
        moved = [name for name in Settings.LEARNING if getattr(new, name) != getattr(self.settings, name)]
        self.settings = new
        self.overrides.update(changes)
        self.space.set_meta("settings", self.overrides)
        self.spec = self.spec.with_settings(new)
        self._specs = {name: s.with_settings(new) for name, s in self._specs.items()}
        self._views.clear()
        self._apply()
        if moved and (self.space.meta("learned") is not None or self._specs):
            self.learn()
        return self.settings.to_json(all=True)

    def _writes(self, operation: str) -> None:
        if self.readonly:
            raise kernel.ReadOnlyError(operation, self.space.path)

    # -- outputs: the default one (the spec's `output`) and the named ones (its `outputs`) --

    def _name(self, output: str | None) -> str:
        """An output's name, checked against the spec (E_OUTPUT for one it does not name)."""
        if output is None or output == kernel.DEFAULT:
            return kernel.DEFAULT
        self.spec.output_of(output)
        return output

    def outputs(self) -> list[str]:
        """The outputs this model decides: the spec's named ones, or the default one when it names none."""
        return self.spec.declared() or [kernel.DEFAULT]

    def _stored(self) -> list[str]:
        """The outputs that learn and calibrate: every declared one but a many output, and its members."""
        return self.spec.stored() or [kernel.DEFAULT]

    def _spec_for(self, name: str) -> Spec:
        """The spec an output reads by: the default's own, or a named output's learned one (until it learns: the
        spec as given)."""
        if name == kernel.DEFAULT:
            return self.spec
        return self._specs.get(name) or self.given.with_settings(self.settings)

    def _space_for(self, name: str) -> kernel.Space:
        """The store as this output reads it: the store itself when the output's word weights and interactions are
        the ones the store holds; else the output's view of it (Space.view), kept current."""
        spec = self._spec_for(name)
        if name == kernel.DEFAULT or (
            spec.interactions == self.spec.interactions and _word_tables(spec) == _word_tables(self.spec)
        ):
            return self.space
        self._views[name] = self.space.view(spec.restate, into=self._views.get(name))
        return self._views[name]

    def record(
        self,
        data: Any,
        outcome: str | None = None,
        ts: float | None = None,
        outcomes: Mapping[str, str] | None = None,
    ) -> str:
        """One case, recorded once: its outcome (the default output's) and/or its named outputs' (`outcomes`,
        {output: value}), each checked against the spec's outputs (E_OUTPUT, E_OUTPUT_VALUE). Returns its id."""
        self._writes("record")
        named = self.spec.outcomes_in({self._name(k): v for k, v in (outcomes or {}).items()})
        situation = self.spec.situation(data)
        stamp = ts if ts is not None else self.spec.timestamp(data)
        rid = self.space.record(situation, outcome, rid=self.spec.key(situation), ts=stamp, outcomes=named or None)
        graded = self.space.graded_count() if outcome is not None else len(self.space) if named else 0
        if graded and self.refresh_every and graded % self.refresh_every == 0:
            try:
                self.refresh()
            except SpecError:  # one outcome so far: nothing to learn yet
                pass
        return rid

    def record_many(self, cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Many cases in one write (one transaction in the store): each {"data", "outcome"?, "outcomes"?, "ts"?},
        checked as record() checks one. Any case the spec refuses refuses them all, before anything is written
        (SpecError naming cases[n]). A key_part id held already, or given twice, replaces its row. Returns
        {ids, added, replaced, precedents}: added counts the ids new to the model, replaced the rest. When the
        graded count crosses a multiple of refresh_every, the model refreshes once, after the batch."""
        self._writes("record")
        prepared = []
        for n, case in enumerate(cases):
            at = f"cases[{n}]"
            if not isinstance(case, Mapping) or "data" not in case:
                raise SpecError(at, "a case is an object with data")
            unknown = set(case) - {"data", "outcome", "outcomes", "ts"}
            if unknown:
                raise SpecError(at, f"unknown field(s): {', '.join(sorted(unknown))}")
            outcome, named = case.get("outcome"), dict(case.get("outcomes") or {})
            try:
                if outcome is not None and (not isinstance(outcome, str) or not outcome):
                    raise SpecError("outcome", "a non-empty string")
                named = self.spec.outcomes_in({self._name(k): v for k, v in named.items()})
                situation = self.spec.situation(case["data"])
                stamp = case.get("ts") if case.get("ts") is not None else self.spec.timestamp(case["data"])
                kernel._named_outcomes(named)
            except (SpecError, ValueError) as e:
                raise SpecError(at, str(e)) from None
            rid = self.spec.key(situation)
            prepared.append({"situation": situation, "outcome": outcome, "rid": rid, "ts": stamp, "outcomes": named or None})
        before = self.space.graded_count() if self.refresh_every else 0
        held = self.space.holds([c["rid"] for c in prepared if c["rid"] is not None])
        ids = self.space.record_many(prepared)
        added = len(set(ids) - held)
        after = self.space.graded_count() if self.refresh_every else 0
        if self.refresh_every and after and after // self.refresh_every > before // self.refresh_every:
            try:
                self.refresh()
            except SpecError:
                pass
        return {"ids": ids, "added": added, "replaced": len(ids) - added, "precedents": len(self.space)}

    def forget(self, rid: str) -> None:
        """Delete one case and every outcome it carries (KeyError when the model holds no such id). What the
        model learned from it stays until the next learn()."""
        self._writes("forget")
        self.space.forget(rid)

    def grade(self, rid: str, output: str | None, value: str | None) -> None:
        """One output's outcome on a case already recorded: added, replaced or (None) taken away."""
        self._writes("grade")
        name = self._name(output)
        if name == kernel.DEFAULT:
            self.space.grade(rid, name, value)
            return
        for stored, v in self.spec.outcomes_in({name: value}).items():
            self.space.grade(rid, stored, v)

    def learn(self, output: str | None = None) -> dict[str, Any]:
        """Learn the weights from the store's own graded precedents (every role's similarity_weight and
        value_weights, as Spec.learned does) and keep them with the store, over the spec file's, until the next
        learn. Needs at least ten graded precedents with two outcomes. Returns the learned table.
        A spec with named outputs learns each on its own (kept as 'learned:<output>'; its word weights and
        interactions read through its view of the store, which stays as recorded): `output` names one and returns
        its table; none learns every output that can (ten graded precedents, two outcomes) and returns
        {output: table}."""
        self._writes("learn")
        if output is not None or not self.spec.outputs:
            return self._learn(self._name(output))
        out: dict[str, Any] = {}
        for name in ([kernel.DEFAULT] if self.space.graded() else []) + self._stored():
            try:
                out[name] = self._learn(name)
            except SpecError:  # not enough graded for this output yet
                continue
        return out

    def _learn(self, name: str) -> dict[str, Any]:
        graded = self.space.graded(name)
        if len(graded) < 10:
            raise SpecError("" if name == kernel.DEFAULT else f"outputs.{name}", "learn needs at least 10 precedents with an outcome")
        learned = self.given.with_settings(self.settings).learn(graded)
        if name != kernel.DEFAULT:
            self._specs[name] = self.given.with_settings(self.settings).with_weights(learned)
            self._evidences[name] = learned.get("~evidence", {})
            self._views.pop(name, None)
            self.space.set_meta(f"learned:{name}", learned)
            return learned
        before = self.spec
        self.spec = self.given.with_settings(self.settings).with_weights(learned)
        self.evidence = learned.get("~evidence", {})
        self.space.set_meta("learned", learned)
        if self.spec.interactions != before.interactions or _word_tables(self.spec) != _word_tables(before):
            self.space.rewrite(self.spec.restate)  # every precedent gets the words' weights and the pairs the spec now reads
        return learned

    def refresh(
        self, sample: int | None = None, clearance: float = 1.0, by: str | None = None, output: str | None = None
    ) -> dict[str, Any]:
        """learn() then calibrate(): the weights and the temperature follow the store. Returns both. A spec with
        named outputs refreshes each (or the one named): {output: {learned, tau}}."""
        self._writes("refresh")
        if output is not None or not self.spec.outputs:
            name = self._name(output)
            learned = self._learn(name)
            return {"learned": learned, "tau": self._calibrate(name, sample, clearance, by)}
        return {
            name: {"learned": learned, "tau": self._calibrate(name, sample, clearance, by)}
            for name, learned in self.learn().items()
        }

    def bias(self, situation: Mapping[str, Any], output: str | None = None) -> Callable[[str], float] | None:
        """What the situation's words say of each outcome, as a factor on a vote: exp(word_evidence × the mean
        pointwise mutual information of the words with the outcome), over the text roles the store has evidence
        for (the output's own); None when there is none or the lever is 0."""
        strength = self.settings.word_evidence
        name = self._name(output)
        evidence = self.evidence if name == kernel.DEFAULT else self._evidences.get(name, {})
        if strength <= 0 or not evidence:
            return None
        totals: dict[str, float] = defaultdict(float)
        seen = 0
        for path, table in evidence.items():
            lname, sname, rname = path.split(".")
            value = situation.get(lname, {}).get(sname, {}).get(rname)
            if value is None or not table.get("total"):
                continue
            n = table["total"]
            for word in set(_words_of(value)):
                counts = table["words"].get(word)
                if counts is None:
                    continue
                seen += 1
                p_word = sum(counts.values()) / n
                for outcome, n_outcome in table["outcomes"].items():
                    expected = n_outcome * p_word
                    totals[outcome] += math.log((counts.get(outcome, 0) + 0.1) / (expected + 0.1))
        if not seen:
            return None
        factor = {o: math.exp(strength * max(min(t / seen, 3.0), -3.0)) for o, t in totals.items()}
        return lambda outcome: factor.get(outcome, 1.0)

    def _reader(self, name: str, data: Any, clearance: float) -> tuple[kernel.Space, dict[str, Any], dict[str, Any]]:
        """(the Space a read of this output runs on, the situation, its weights). Every precedent held: the store
        as this output reads it (_space_for). Over a store that shortlists: its nearest precedents to the case,
        by the glyphs the store holds (the default reading's), as this output reads them; the store whole when
        it is small (Space.candidates)."""
        spec = self._spec_for(name)
        situation = spec.situation(data)
        weights = spec.weights(clearance, situation)
        if not self.space.loaded:
            same = name == kernel.DEFAULT or (
                spec.interactions == self.spec.interactions and _word_tables(spec) == _word_tables(self.spec)
            )
            if same:
                near = self.space.candidates(situation, None, weights)
            else:
                base = self.spec.situation(data)
                near = self.space.candidates(base, None, self.spec.weights(clearance, base))
            if near is not self.space:
                return (near if same else near.view(spec.restate)), situation, weights
        return self._space_for(name), situation, weights

    def query(self, data: Any, clearance: float = 1.0, output: str | None = None) -> kernel.Answer:
        name = self._name(output)
        space, situation, weights = self._reader(name, data, clearance)
        now = self._now(data)
        return space.query(situation, weights=weights, bias=self.bias(situation, name), output=name, now=now)

    def _now(self, data: Any) -> float | None:
        """The time a read is asked at, for recency: the case's own (temporal_source) when it carries one, else
        the clock; None when the model's recency is off."""
        if not self.settings.recency:
            return None
        ts = self.spec.timestamp(data) if isinstance(data, Mapping) else None
        return time.time() if ts is None else ts

    def facts(
        self,
        data: Any,
        clearance: float = 1.0,
        top: int | None = None,
        min_score: float | None = None,
        output: str | None = None,
    ) -> list[dict[str, Any]]:
        """The fact trees, best first, each cut to what the reader may see; outcomes and probabilities the
        output's."""
        name = self._name(output)
        spec = self._spec_for(name)
        space, situation, weights = self._reader(name, data, clearance)
        trees = space.facts(situation, weights=weights, top=top, min_score=min_score, output=name)
        return [{**t.to_json(), "tree": spec.report(t.to_json()["tree"], clearance)} for t in trees]

    def probabilities(self, data: Any, clearance: float = 1.0, output: str | None = None) -> dict[str, float]:
        """P(outcome | data) over the nearest precedents, at the output's temperature (calibrate() fits it). A
        many output's: each value's P(true)."""
        name = self._name(output)
        if name != kernel.DEFAULT and self.spec.output_of(name).kind == "many":
            each = {v: self.probabilities(data, clearance, member) for member, v in self.spec.members(name)}
            return {v: p.get("true", 0.0) for v, p in each.items() if p}
        space, situation, weights = self._reader(name, data, clearance)
        now = self._now(data)
        return space.probabilities(situation, weights=weights, bias=self.bias(situation, name), output=name, now=now)

    def calibrate(
        self, sample: int | None = None, clearance: float = 1.0, by: str | None = None, output: str | None = None
    ) -> Any:
        """Fit the store's temperature on its own newest precedents, each held out in turn and scored with the
        weights the spec gives its situation. `by` is "loss" (the least log-loss: probabilities that mean what
        they say) or "cost" (the least cost of deciding by output.costs, log-loss breaking ties: probabilities
        that decide best). Kept in the store. Returns tau. A spec with named outputs fits each its own (or the
        one named) and returns {output: tau}, every output with ten graded precedents."""
        self._writes("calibrate")
        if output is not None or not self.spec.outputs:
            return self._calibrate(self._name(output), sample, clearance, by)
        names = ([kernel.DEFAULT] if self.space.graded() else []) + self._stored()
        return {name: self._calibrate(name, sample, clearance, by) for name in names if len(self.space.graded(name)) >= 10}

    def _calibrate(self, name: str, sample: int | None, clearance: float, by: str | None) -> float:
        by = by or self.settings.calibrate_by
        sample = sample or self.settings.calibrate_sample
        if by not in ("loss", "cost"):
            raise SpecError("", 'calibrate by "loss" or "cost"')
        spec, space = self._spec_for(name), self._space_for(name)
        costs = self.spec.output_of(name)
        tau = space.calibrate(
            sample,
            weights_for=lambda s: spec.weights(clearance, s),
            cost=(lambda p, true: costs.cost(self._least(p, name), true)) if by == "cost" else None,
            bias_for=lambda s: self.bias(s, name),
            output=name,
            recency=self.settings.recency,
        )
        if space is not self.space:
            self.space.set_tau(name, tau)  # fitted on the view; kept by the store
            if self.settings.recency:
                self.space.set_half_life(name, space.half_life(name))
        return tau

    def _least(self, probabilities: Mapping[str, float], output: str | None = None) -> str:
        costs = self.spec.output_of(output)
        expected = {
            decided: sum(p * costs.cost(decided, true) for true, p in probabilities.items())
            for decided in probabilities
        }
        return min(expected, key=lambda o: (expected[o], o))

    def decide(self, data: Any, clearance: float = 1.0, output: str | None = None) -> dict[str, Any]:
        """The outcome with the least expected cost under the output's costs (every mistake costs 1 when the
        spec names none), from the calibrated probabilities. `ask` is true when a person should answer instead:
        nothing is known, or the spec prices asking (the output's ask) below every outcome's expected cost; the
        outcome is then still the best guess, for the person to see. The output's ask_below asks too whenever
        the most probable outcome's probability is under it."""
        name = self._name(output)
        costs = self.spec.output_of(name)
        if costs.kind == "many":
            # each value a noul of its own: the outcome is every value decided true, probabilities each P(true)
            each = {v: self.decide(data, clearance, member) for member, v in self.spec.members(name)}
            known = {v: d for v, d in each.items() if d["outcome"] is not None}
            return {
                "outcome": [v for v, d in each.items() if d["outcome"] == "true"] if known else None,
                "expected_cost": round(sum(d["expected_cost"] for d in known.values()), 4) if known else None,
                "probabilities": {v: d["p"] for v, d in known.items()},
                "ask": not known or any(d["ask"] for d in each.values()),
            }
        probabilities = self.probabilities(data, clearance, name)
        if not probabilities:
            return {"outcome": None, "expected_cost": None, "probabilities": {}, "ask": True}
        expected = {
            decided: sum(p * costs.cost(decided, true) for true, p in probabilities.items())
            for decided in probabilities
        }
        best = self._least(probabilities, name)
        out = {
            "outcome": best,
            "expected_cost": round(expected[best], 4),
            "probabilities": {o: round(p, 4) for o, p in probabilities.items()},
            "ask": (costs.ask is not None and expected[best] > costs.ask)
            or (costs.ask_below is not None and max(probabilities.values()) < costs.ask_below),
        }
        if costs.kind == "noul":
            out["p"] = round(probabilities.get("true", 0.0), 4)
        elif costs.kind == "number":
            out["value"] = round(sum(p * float(o) for o, p in probabilities.items()), 6)
        elif costs.kind == "score":
            out["level"] = round(sum(p * costs.values.index(o) for o, p in probabilities.items() if o in costs.values), 4)
        return out

    def decide_all(
        self, data: Any, clearance: float = 1.0, outputs: Sequence[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Every output's decision about one case (or the named outputs'), in one call: {output: decide()}. A
        union's output (`when`) is decided only when the output it hangs on is decided one of its outcomes (that
        one decided first, asked for or not); otherwise it answers {"outcome": None, "applies": False}."""
        names = [self._name(o) for o in outputs] if outputs is not None else self.outputs()
        done: dict[str, dict[str, Any]] = {}

        def one(name: str) -> dict[str, Any]:
            if name not in done:
                when = self.spec.output_of(name).when if name != kernel.DEFAULT else None
                if when and one(when[0]).get("outcome") not in when[1]:
                    done[name] = {"outcome": None, "expected_cost": None, "probabilities": {}, "ask": False, "applies": False}
                else:
                    done[name] = {**self.decide(data, clearance, name), **({"applies": True} if when else {})}
            return done[name]

        return {name: one(name) for name in names}

    def __len__(self) -> int:
        return len(self.space)
