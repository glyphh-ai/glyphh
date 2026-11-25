"""Run the Agent Trace Observability review over the generated traces.

    uv run python run_traces.py jev          # Jev runs the review end to end, one request per node
    uv run python run_traces.py refs         # both references, one question per request, node by node

The references walk the review together: each node is put to both, their probabilities are averaged, and the
average decides which node comes next, so the consensus path is the one both answered. Answers are kept in
data/answers/ and a rerun asks only what is missing.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import agent_traces
import askers
import published
import run

HERE = Path(__file__).parent
CASES = HERE / "data" / "cases" / "agent_trace_observability.jsonl"


def cases() -> list[dict]:
    return [json.loads(line) for line in CASES.open()]


def questions_for(trace: dict, ids) -> dict[str, dict]:
    qs = published.questions("agent_trace_observability")
    out = {q: dict(qs[q]) for q in ids}
    if "first_bad_step" in out:
        out["first_bad_step"]["criteria"] = agent_traces.first_bad_step_options(trace)
    return out


def mean(answers: list[dict]) -> dict:
    out = {}
    for q in answers[0]:
        vals = [a[q] for a in answers]
        out[q] = sum(vals) / len(vals) if isinstance(vals[0], float) else {k: sum(v[k] for v in vals) / len(vals) for k in vals[0]}
    return out


def run_jev() -> None:
    jev = askers.Jev()
    done = run.load("traces_jev")
    for case in cases():
        if case["id"] in done:
            continue
        trace = case["trace"]
        ask, seconds = askers.timed(
            lambda node, ids, step=None: jev.ask(agent_traces.view(trace, node, step), questions_for(trace, ids))
        )
        before = jev.spend.dollars()
        action, _ = agent_traces.decide(ask, trace)
        done[case["id"]] = {"action": action, "seconds": seconds[0], "dollars": jev.spend.dollars() - before}
        run.save("traces_jev", done)
        print(f"{case['id']}: {action}  {seconds[0]:.2f}s")
    print(f"jev: ${jev.spend.dollars():.4f}")


def run_references() -> None:
    refs = [askers.Reference(name, *run.REFERENCES[name]) for name in run.REFERENCES]
    stored = {r.name: run.load(f"traces_{r.name}") for r in refs}
    consensus = run.load("traces_consensus")
    pool = ThreadPoolExecutor(len(refs))
    for case in cases():
        if case["id"] in consensus:
            continue
        trace = case["trace"]

        def ask(node, ids, step=None, trace=trace, cid=case["id"]):
            key = f"{node}_{step}" if step else node
            state, qs = agent_traces.view(trace, node, step), questions_for(trace, ids)
            got = []
            for r, a in zip(refs, pool.map(lambda r: stored[r.name].get(cid, {}).get(key) or r.ask(state, qs), refs), strict=True):
                stored[r.name].setdefault(cid, {})[key] = a
                got.append(a)
            for r in refs:
                run.save(f"traces_{r.name}", stored[r.name])
            return mean(got)

        action, _ = agent_traces.decide(ask, trace)
        consensus[case["id"]] = {"action": action}
        run.save("traces_consensus", consensus)
        print(f"{case['id']}: {action}  " + "  ".join(f"{r.name} ${r.spend.dollars():.2f}" for r in refs))
    print("references: " + "  ".join(f"{r.name} ${r.spend.dollars():.3f} {r.spend.tokens}" for r in refs))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("who", choices=["jev", "refs"])
    a = p.parse_args()
    run_jev() if a.who == "jev" else run_references()


if __name__ == "__main__":
    main()
