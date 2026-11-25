"""Jev (TypeSafe AI) on the same 200: one Choice per held-out case, good or bad, over HTTP.

Jev is a decision model, not a learner: it keeps nothing between calls. So the 800 learned cases travel in every
request's state as one compact table ("precedents"), the way the LLM judge read train.jsonl, and the case to decide
sits beside them. 300 is the most that fits Jev's 32k-token question limit; all 800 need `--long-context`.
`--examples 0` sends the case alone (zero-shot); `--examples N` the first N of the 800.

The answer's `probabilities` give P(bad) directly, so the cost-aware rule is the same one the others use: refuse
when P(bad) > 1/6.

    TYPESAFE_API_KEY=... uv run python benchmarks/credit/jev.py [--examples 300] [--model jev-latest] [--long-context]

Writes results/jev_<model>_<examples>.json (the answers, for score.py) and ..._raw.json (every probability, the
tokens and the time of each call).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import run as base  # noqa: E402  (the data, the legend and the scorer; the same split)

PRICE_PER_MTOK = 0.042  # input only; Jev's output tokens are free (docs.typesafe.ai/models)
COLUMNS = [*base.FIELDS, "decision"]
FIELD_NOTES = {
    "checking": "checking account balance in DM",
    "duration_months": "loan duration in months",
    "history": "credit history",
    "purpose": "what the loan is for",
    "amount": "loan amount in DM",
    "savings": "savings in DM",
    "employed_since": "time in current employment",
    "instalment_rate": "instalment as % of disposable income, 1 (low) to 4 (high)",
    "status": "sex and marital status",
    "other_debtors": "other debtors or guarantors",
    "resident_since": "years at present residence, 1 to 4",
    "property": "most valuable property",
    "age": "age in years",
    "other_plans": "other instalment plans",
    "housing": "housing",
    "existing_credits": "number of existing credits at this bank",
    "job": "job",
    "dependants": "number of people liable to provide maintenance for",
    "telephone": "has a telephone in their name",
    "foreign": "foreign worker",
}
QUESTION = {
    "question": "Decide this loan `application` the way the bank decided the `precedents` in the state.",
    "fields": FIELD_NOTES,
    "costs": "Approving a loan that goes bad costs the bank 5; refusing a loan that would have been good costs 1.",
}
CRITERIA = {
    "good": "Approve: the applicant will repay as agreed.",
    "bad": "Refuse: the loan would go bad.",
}


def state(case: dict, precedents: list[dict]) -> dict:
    s: dict = {"application": {k: case[k] for k in base.FIELDS}}
    if precedents:
        s["precedents"] = {
            "about": "Past applications at this bank with the bank's real outcome in `decision`.",
            "columns": COLUMNS,
            "rows": [[c[k] for k in COLUMNS] for c in precedents],
        }
    return s


def ask(url: str, key: str, body: dict, long_context: bool, attempts: int = 6) -> tuple[dict, float]:
    data = json.dumps(body, separators=(",", ":")).encode()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if long_context:
        headers["TypeSafe-Danger-Zone-Long-Context"] = "true"
    for attempt in range(attempts):
        t0 = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data, headers), timeout=120) as r:  # noqa: S310
                return json.loads(r.read()), time.time() - t0
        except urllib.error.HTTPError as e:
            if e.code in (429, 529) and attempt < attempts - 1:
                time.sleep(float(e.headers.get("retry-after") or 2**attempt))
                continue
            raise SystemExit(f"Jev answered {e.code}: {e.read().decode(errors='replace')[:500]}") from None
    raise SystemExit("unreachable")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--examples", type=int, default=300, help="how many of the 800 travel in each state (0 = none)")
    p.add_argument("--model", default="jev-latest")
    p.add_argument("--long-context", action="store_true", help="send TypeSafe's long-context header (262k)")
    a = p.parse_args()
    key = os.environ.get("TYPESAFE_API_KEY") or sys.exit("TYPESAFE_API_KEY is not set")
    url = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/") + "/v1/systemone"

    rows = base.load()
    random.Random(7).shuffle(rows)  # noqa: S311  (the seeded split, not a secret)
    train, test = rows[:800], rows[800:]
    precedents = train[: a.examples]
    truth = [c["decision"] for c in test]

    raw, guesses, careful = {}, [], []
    tokens = 0
    seconds = 0.0
    model = a.model
    for n, c in enumerate(test, 1):
        body = {
            "model": a.model,
            "state": state(c, precedents),
            "questions": {"decision": {"type": "choice", "instructions": QUESTION, "criteria": CRITERIA}},
        }
        reply, took = ask(url, key, body, a.long_context)
        answer = reply["answers"]["decision"]
        p_bad = answer["probabilities"]["bad"]
        guesses.append(answer["choice"])
        careful.append("bad" if p_bad > 1 / 6 else "good")
        tokens += reply["usage"]["input_tokens"]
        seconds += took
        model = reply.get("model", model)
        raw[c["id"]] = {
            "choice": answer["choice"],
            "p_bad": p_bad,
            "confidence": answer.get("confidence"),
            "input_tokens": reply["usage"]["input_tokens"],
            "seconds": round(took, 3),
        }
        print(f"\r{n}/{len(test)}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    label = f"jev_{model}_{a.examples}"
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / f"{label}.json").write_text(
        json.dumps({c["id"]: g for c, g in zip(test, guesses, strict=True)}, indent=0) + "\n"
    )
    (out / f"{label}_raw.json").write_text(
        json.dumps({"model": model, "examples": a.examples, "long_context": a.long_context, "cases": raw}, indent=1)
        + "\n"
    )

    cost = tokens * PRICE_PER_MTOK / 1e6
    note = f"{tokens / len(test):,.0f} tokens and {seconds / len(test):.2f}s per decision, ${cost:.4f} in all"
    base.score(f"{model}, {a.examples} precedents", guesses, truth, seconds, note)
    base.score(f"{model}, cost-aware", careful, truth, seconds, "refuse when P(bad) > 1/6")
    print(f"answers in results/{label}.json")


if __name__ == "__main__":
    main()
