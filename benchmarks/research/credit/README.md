# Benchmark: credit decisions — Ada, Jev and an LLM, on the same hold-out

**The question:** for a structured decision an app would otherwise hand to an LLM, how does an Ada model compare
with Jev and a frontier LLM on accuracy, cost and time?

**The data:** German Credit (UCI Statlog): 1,000 loan applications, 20 typed fields (checking account, credit
history, purpose, amount, duration, savings, employment, housing, age, …) and the bank's real decision, good or
bad. The dataset's own cost matrix: approving a bad loan costs 5, refusing a good one costs 1.

**The split:** one shuffle (seed 7): 800 to learn from, 200 held out. The same 800 and the same 200 for everyone.

**The contestants**

| | How it learned | How it decided |
|---|---|---|
| Ada | `record` of the 800 cases with their outcome, into the spec in `run.py` (3 layers; the applicant's money roles weigh 1.0, their life roles 0.6; hand-set, untuned) | `query` each of the 200; `top`. "Cost-aware": refuse when `outcomes["bad"]` > 1/6 |
| LLM (Claude Fable 5.1, effort medium, two independent runs) | Read `train.jsonl` (the brief is `judge_prompt.md`; no code allowed) | Judged each of the 200 by hand; told the cost matrix |
| Jev (TypeSafe AI, `jev-latest` = jev-1.13.0) | Nothing kept: the precedents travel in every request's state as one table (`jev.py`); 300 is the most that fits its 32k-token question limit, all 800 need its long-context header | One Choice, good or bad, told the cost matrix; "cost-aware": its own P(bad) > 1/6 |

Run on 2026-10-16 (Ada, the LLM) and 2026-10-19 (Jev). Ada rerun on kernel 3.11.0 on 2026-10-20: every answer
the same as before.

## Results, 200 held out

| | Accuracy | Bad loans approved (×5) | Good refused (×1) | Bank's cost | Same answer every time |
|---|---|---|---|---|---|
| Always approve | 67.5% | 65 | 0 | 325 | — |
| **Ada** (min_sim 0.25, k 25) | **77.0%** | 41 | 5 | 210 | yes |
| Ada, cost-aware | 59.5% | 10 | 71 | 121 | yes |
| **LLM, run 1** (read 430 of the 800) | **77.0%** | 16 | 30 | 110 | the two runs agree on |
| **LLM, run 2** (read ~140 of the 800) | **79.0%** | 18 | 24 | 114 | 94% of cases |
| Jev, no precedents | 49.5% | 18 | 83 | 173 | not tested |
| Jev, no precedents, cost-aware | 34.0% | 0 | 132 | 132 | not tested |
| Jev, 300 precedents | 71.0% | 27 | 31 | 166 | not tested |
| Jev, 300 precedents, cost-aware | 48.5% | 5 | 98 | 123 | not tested |
| Jev, all 800 (long context) | 70.5% | 35 | 24 | 199 | not tested |
| Jev, all 800 (long context), cost-aware | 53.0% | 6 | 88 | 118 | not tested |

Other Ada settings on the same split: min_sim 0.35 / k 15 → 76.0%, cost 212; min_sim 0.45 / k 9 → 75.0%, cost 214.
Ada answered (`sufficient`) on 100% of cases at every setting.

## Cost and time

Ada on a hosted runtime machine (Fly shared-cpu, $0.019 an hour). The LLM per token; its price is bracketed by two
public rates because the model's own was not to hand.

| Ada | Time | Cost |
|---|---|---|
| Build the model: record 800 | 0.4 s, once | ~$0.000002 |
| One run: 200 decisions | under 1 s (0.005 s each) | ~$0.000005 |

| LLM | Tokens | Time | at $5/M in, $25/M out | at $15/M in, $75/M out |
|---|---|---|---|---|
| Run 1: read 430 examples + 200 cases, decide | 179,892 | 166 s | ≈ $0.95 | ≈ $2.85 |
| Run 2: read ~140 examples + 200 cases, decide | 116,647 | 119 s | ≈ $0.62 | ≈ $1.85 |
| Both runs, 400 decisions | 296,539 | 285 s | ≈ $1.57 | ≈ $4.70 |
| Per decision, batched like this | ~740 | 0.7 s | ≈ $0.004 | ≈ $0.012 |
| Per decision as an app calls it (the examples resent on every call) | ~100,000 | 1–3 s | ≈ $0.50 | ≈ $1.50 |

| Jev (input tokens only, $0.042/M; output is free) | Tokens per decision | Time per decision | One run: 200 decisions |
|---|---|---|---|
| No precedents | 844 | 0.21 s | $0.007 |
| 300 precedents | 29,434 | 0.47 s | $0.25 |
| All 800, long context | 76,870 | 1.03 s | $0.65 |

Jev and the LLM keep nothing between calls: the precedents are paid for on every call, and neither LLM run read all
800 (430 and ~140). Ada's ingest is paid once; every decision after is a query.

## What it says

- **Accuracy: Ada level with the LLM, ahead of Jev.** Ada 77%, the LLM 77–79%, Jev 71% at best, all from the same
  800 cases.
- **Jev: fast and cheap per call, behind on this task.** 71% at best, only 3.5 points over always-approve's 67.5% and
  six to eight points under Ada and the LLM. Cold (no precedents) it is a coin flip, 49.5%. More precedents past 300
  did not help (800 by long context: 70.5%). Its P(bad) is too pessimistic for the 1/6 rule (88–132 good loans
  refused), though the cost-aware rule still brings its cost to 118–132.
- **The bank's cost:** Ada's `outcomes` is a similarity-weighted vote, not a calibrated probability, so a cost
  threshold over-refuses (71 good loans); learned weights and calibration bring it to 110 (below).
- **Determinism:** the two LLM runs disagreed on 12 of 200 decisions. Ada never does.
- **Cost per decision:** Ada is three to five orders of magnitude cheaper, and keeps the data in the runtime.

## After calibration, the same 200 once more

`calibrate.py`, run after the table above and reported whatever it said. Nothing in it looks at the 200: the
weights and the curve come from the 800 alone, the threshold from the cost matrix alone.

1. **Role weights learned from the 800**: each field's information gain about the decision, scaled so the best
   weighs 1 — `checking` 1.0, `duration_months` 0.51, `history` 0.39, `amount` 0.34, `savings` 0.30, `purpose`
   0.21, `age` 0.16, … `job` 0.01, `dependants` 0.0. The hand-set segment weights are dropped.
2. **Calibration by five-fold cross-validation inside the 800**: every learned case voted on by a model of the
   other four fifths; an isotonic curve (61 steps) from the vote share for "bad" to P(bad).
3. **The rule from the costs**: refuse when 5 × P(bad) > P(good), i.e. P(bad) > 1/6.

| | Accuracy | Bad approved (×5) | Good refused | Bank's cost |
|---|---|---|---|---|
| Ada, learned weights | 76.5% | 38 | 9 | 199 |
| **Ada, learned weights, calibrated, cost rule** | 67.0% | 11 | 55 | **110** |
| for reference: LLM runs 1 and 2 | 77.0% / 79.0% | 16 / 18 | 30 / 24 | 110 / 114 |

Cross-validated accuracy inside the 800 was 71.8%, so this hold-out runs a little easy for every contestant; the
ranking is what to read, not the third digit. On the bank's cost, calibration took Ada from 121 to 110, level with
the LLM, with every choice made before the hold-out was opened.

## Like for like: TypeSafe's measurement

TypeSafe's workflow evals (evals.typesafe.ai) have no real outcomes. Their reference is the average of two frontier
models' predictions (GPT-6 Astra and Fable 5.1), and a contestant scores by agreeing with it: Jev 67.8% there, Opus 5
73.1%, Sonnet 5 67.8%. `consensus.py` builds that reference for our 200: Claude Fable 5.1 and Claude Opus 5.5, each
giving P(bad) per case after reading the 800 (no code; Fable read all 800, Opus read 120 and said it also leaned on
what it knew of this dataset), averaged, "bad" above 0.5. Run on 2026-10-19; Ada's rows rerun on kernel 3.11.0 on
2026-10-20, unchanged.

| | vs what really happened | vs the consensus (TypeSafe's measure) |
|---|---|---|
| **Ada** | 77.0% | **88.5%** |
| Ada, learned weights | 76.5% | 87.0% |
| Jev, all 800 (long context) | 70.5% | 79.0% |
| LLM run 2 | **79.0%** | 78.5% |
| LLM run 1 | 77.0% | 74.5% |
| Jev, 300 precedents | 71.0% | 72.5% |
| Ada, learned weights, calibrated, cost rule | 67.0% | 59.5% |
| Ada, cost-aware | 59.5% | 51.0% |
| Jev, no precedents | 49.5% | 44.0% |

- **On TypeSafe's own measure, Ada leads Jev by 9.5 points** (88.5% to 79.0%); on what really happened, by 6.
- **The consensus is itself wrong a quarter of the time**: 74.5% against the real outcomes, and it calls 28 of the 200
  bad where 65 were. Agreeing with it rewards approving; every cost-aware row, built to refuse, drops on it.
- **So the measure ranks differently**: the LLM runs fall below Ada, and Jev with 800 rises above the LLM. Scores
  against a consensus of models say how model-like a contestant is, not how right.

## Reproduce

From this repo's root, with an ada-private checkout beside it (or `GLYPHH_KERNEL` pointing at one; `ada_kernel.py`
refuses any kernel older than 3.11.0 or without its lexicon):

```sh
credit/fetch.sh                                   # german.data (CC BY 4.0, UCI)
uv run python credit/run.py                       # the split and Ada; seconds
uv run python credit/calibrate.py                 # learned weights, calibration, the cost rule; seconds
TYPESAFE_API_KEY=... uv run python credit/jev.py  # Jev, 200 calls, 300 precedents; --examples 0, or 800 --long-context
uv run python credit/score.py credit/results/llm_run1.json   # any answers file
uv run python credit/consensus.py                 # every answers file vs real outcomes and vs the LLM consensus
```

`run.py` writes `train.jsonl`, `holdout.jsonl` and `holdout_labels.json`; every contestant's answers are in
`results/`.
