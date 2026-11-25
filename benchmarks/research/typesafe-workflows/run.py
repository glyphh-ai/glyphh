"""Run the Security Incidents workflow over the generated cases.

    uv run python run.py jev                 # Jev runs the workflow end to end
    uv run python run.py ref fable           # Claude Fable 5.1 high (Claude Opus 5 high where Fable refuses)
    uv run python run.py ref astra           # GPT-6 Astra high

The references answer one question per request through TypeSafe's adapter. They answer the triage questions on
every case, and the containment questions only where their consensus (the mean of their probabilities) acts, so run
each reference once for triage and again after the other has finished. Answers are kept in data/answers/ and a rerun
asks only what is missing.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import askers
import published
import security

HERE = Path(__file__).parent
# Two case sets: "dev", the cases every Ada setting was chosen on, and "test", generated and labelled after the
# setup was frozen and scored once. BENCH_SET picks the set a run reads and writes (default dev).
SETS = {
    "dev": (HERE / "data" / "cases" / "security_incidents.jsonl", HERE / "data" / "answers"),
    "test": (HERE / "data" / "cases" / "security_incidents_test.jsonl", HERE / "data" / "answers-test"),
}
SET = os.environ.get("BENCH_SET", "dev")
if SET not in SETS:
    raise SystemExit(f"BENCH_SET is one of {', '.join(SETS)}")
REFERENCES = {
    "fable": ("anthropic", "claude-fable-5-1", "claude-opus-5"),
    "astra": ("openai", "gpt-6-astra", None),
}


def cases(which: str | None = None) -> list[dict]:
    return [json.loads(line) for line in SETS[which or SET][0].open()]


def load(name: str, which: str | None = None) -> dict:
    path = SETS[which or SET][1] / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save(name: str, data: dict, which: str | None = None) -> None:
    folder = SETS[which or SET][1]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(data, indent=1))


def consensus(case_id: str, which: str | None = None) -> dict:
    """The mean of every reference's probabilities, for the questions all of them answered."""
    refs = [load(r, which).get(case_id, {}).get("answers", {}) for r in REFERENCES]
    shared = set.intersection(*(set(a) for a in refs)) if all(refs) else set()
    out: dict = {}
    for q in shared:
        vals = [a[q] for a in refs]
        out[q] = (
            sum(vals) / len(vals)
            if isinstance(vals[0], float)
            else {k: sum(v[k] for v in vals) / len(vals) for k in vals[0]}
        )
    return out


def run_jev() -> None:
    questions = published.questions("security_incidents")
    jev = askers.Jev()
    done = load("jev")
    for case in cases():
        if case["id"] in done:
            continue
        ask, seconds = askers.timed(
            lambda qs: jev.ask(case["state"], {q: questions[q] for q in qs})
        )
        before = jev.spend.dollars()
        action, answers = security.decide(ask, case)
        done[case["id"]] = {
            "action": action,
            "answers": answers,
            "seconds": seconds[0],
            "dollars": jev.spend.dollars() - before,
        }
        save("jev", done)
        print(f"{case['id']}: {action}  {seconds[0]:.2f}s")
    print(f"jev: ${jev.spend.dollars():.4f}  {jev.spend.tokens}")


def run_reference(name: str, parallel: int = 6) -> None:
    provider, model, fallback = REFERENCES[name]
    questions = published.questions("security_incidents")
    ref = askers.Reference(name, provider, model, fallback)
    done = load(name)
    lock = threading.Lock()
    t0 = time.time()

    def one(case: dict) -> None:
        record = done.setdefault(case["id"], {"answers": {}})
        if record.get("refused"):
            return  # both of this reference's models declined it: no consensus, scored for no one
        got = record["answers"]
        wanted = list(security.TRIAGE)
        both = consensus(case["id"])
        if all(q in both for q in security.TRIAGE) and security.disposition(both, case) == "act":
            wanted += list(security.CONTAINMENT)
        missing = [q for q in wanted if q not in got]
        if not missing:
            return
        try:
            answers = ref.ask(case["state"], {q: questions[q] for q in missing})
        except askers.Refused as e:
            with lock:
                record["refused"] = True
                save(name, done)
                print(f"{case['id']}: refused by both models ({e})", flush=True)
            return
        with lock:
            got.update(answers)
            save(name, done)
            print(f"{case['id']}: {len(missing)} answered, ${ref.spend.dollars():.3f} so far", flush=True)

    with ThreadPoolExecutor(parallel) as pool:
        list(pool.map(one, cases()))
    print(
        f"{name}: ${ref.spend.dollars():.4f} in {time.time() - t0:.0f}s  {ref.spend.tokens}  "
        f"documents sent to the fallback: {ref.spend.fallbacks}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("who", choices=["jev", "ref"])
    p.add_argument("reference", nargs="?", choices=list(REFERENCES))
    a = p.parse_args()
    if a.who == "jev":
        run_jev()
    elif a.reference:
        run_reference(a.reference)
    else:
        p.error("ref needs a reference: " + ", ".join(REFERENCES))


if __name__ == "__main__":
    main()
