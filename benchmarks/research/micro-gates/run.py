"""Can many micro gates reason where one model can't? Every contestant gets the same precedents from a hidden machine
(world.py) and answers chains no precedent holds, up to five times longer than any it saw.

Contestants: the most common end, one Ada model reading the whole chain, the micro gates with no credit (their own
direct precedents only) and the micro gates with credit (gates.py). Seed 0 was the only world looked at while building;
the seeds here were run once. An answer the gates refuse to give counts as wrong.

    uv run python run.py          # the table, into results/
    uv run python run.py llm 0.5  # the LLM contestant's prompt and key at that share of moves shown, into results/
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

import gates
import world

HERE = Path(__file__).parent
SEEDS = (1, 2, 3, 4, 5)
SHOWN = (0.5, 0.25, 0.1, 0.0)  # how many moves have a precedent of their own
LONGEST = max(world.TEST_LENGTHS)
LLM_PER_LENGTH = 10


def whole_spec() -> dict:
    roles = [{"name": "start"}] + [{"name": f"a{i}"} for i in range(1, LONGEST + 1)]
    return {
        "name": "whole_chain",
        "seed": 5,
        "dimension": 4096,
        "layers": [{"name": "chain", "segments": [{"name": "steps", "roles": roles}]}],
    }


def whole_situation(chain: world.Chain) -> dict:
    steps = {"start": chain.start} | {f"a{i}": a for i, a in enumerate(chain.actions, 1)}
    return {"chain": {"steps": steps}}


def whole_model(w: world.World):
    spec = gates.ada_kernel.load()
    model = spec.Model(spec.Spec.from_json(whole_spec()))
    for chain in w.train:
        model.record(whole_situation(chain), chain.end)
    model.refresh()
    return lambda c: model.decide(whole_situation(c))["outcome"]


def score(answer, w: world.World) -> dict[int, float]:
    return {n: sum(answer(c) == c.end for c in cs) / len(cs) for n, cs in w.test.items()}


def one_world(seed: int, shown: float) -> dict:
    w = world.make(seed, shown)
    common = Counter(c.end for c in w.train).most_common(1)[0][0]
    plain = gates.Gates(w.actions, w.states)
    plain.train(list(w.train), random.Random(seed), credit=False)
    full = gates.Gates(w.actions, w.states)
    rounds = full.train(list(w.train), random.Random(seed))
    hidden = [m for m in w.moves if m not in w.direct]
    return {
        "seed": seed,
        "shown": shown,
        "common": score(lambda c: common, w),
        "whole": score(whole_model(w), w),
        "no_credit": score(lambda c: plain.run(c.start, c.actions), w),
        "gates": score(lambda c: full.run(c.start, c.actions), w),
        "answered": score(lambda c: c.end if full.run(c.start, c.actions) else None, w),
        "moves_right": sum(full.answer(*m) == n for m, n in w.moves.items()) / len(w.moves),
        "moves_wrong": sum(full.answer(*m) not in (None, n) for m, n in w.moves.items()) / len(w.moves),
        "hidden_right": sum(full.answer(*m) == w.moves[m] for m in hidden) / len(hidden),
        "rounds": [dict(r) for r in rounds],
    }


def mean(rows: list[dict], key: str, length: int | None = None) -> float:
    values = [r[key] if length is None else r[key][length] for r in rows]
    return sum(values) / len(values)


def report(runs: list[dict]) -> str:
    lines = [f"Chance is {1 / world.STATES:.0%}. Mean of {len(SEEDS)} hidden worlds, {world.TEST_PER_LENGTH} chains a length.", ""]
    for shown in SHOWN:
        rows = [r for r in runs if r["shown"] == shown]
        lines += [f"Moves shown directly: {shown:.0%}"]
        lines += ["contestant        " + "".join(f"{n:>7}" for n in world.TEST_LENGTHS)]
        for key, name in (("common", "most common end"), ("whole", "one Ada model"), ("no_credit", "gates, no credit"), ("gates", "gates, credit")):
            lines += [f"{name:<18}" + "".join(f"{mean(rows, key, n):>7.1%}" for n in world.TEST_LENGTHS)]
        lines += [
            f"moves right {mean(rows, 'moves_right'):.1%}, wrong {mean(rows, 'moves_wrong'):.1%}, "
            f"never-shown moves right {mean(rows, 'hidden_right'):.1%}",
            "",
        ]
    return "\n".join(lines)


def llm_files(shown: float) -> None:
    w = world.make(SEEDS[0], shown)
    rng = random.Random(99)
    lines = [f"{c.start} {' '.join(c.actions)} -> {c.end}" for c in w.train]
    rng.shuffle(lines)
    cases = [(n, c) for n, cs in w.test.items() for c in rng.sample(cs, LLM_PER_LENGTH)]
    rng.shuffle(cases)
    prompt = [
        "A hidden machine has states and actions, all with made-up names. Each action moves every state to one state.",
        "Each line below is a start state, a list of actions applied in order, and the state it ended in. About 5% of",
        "the lines record a wrong end. Work out the machine, then give the end state of each numbered question.",
        "Reply with one line per question: the number, a space, the state.",
        "",
        *lines,
        "",
        "Questions:",
        *(f"{i} {c.start} {' '.join(c.actions)}" for i, (_, c) in enumerate(cases, 1)),
    ]
    (HERE / f"results/llm_prompt_{shown}.txt").write_text("\n".join(prompt) + "\n")
    key = {str(i): {"length": n, "start": c.start, "actions": c.actions, "end": c.end} for i, (n, c) in enumerate(cases, 1)}
    (HERE / f"results/llm_key_{shown}.json").write_text(json.dumps(key, indent=1) + "\n")


def main() -> None:
    (HERE / "results").mkdir(exist_ok=True)
    if sys.argv[1:2] == ["llm"]:
        return llm_files(float(sys.argv[2]))
    runs = [one_world(seed, shown) for shown in SHOWN for seed in SEEDS]
    (HERE / "results/runs.json").write_text(json.dumps(runs, indent=1) + "\n")
    table = report(runs)
    (HERE / "results/table.txt").write_text(table + "\n")
    print(table)


if __name__ == "__main__":
    main()
