# Benchmarks

Ada, Glyphh's precedent store, against Claude and classic models on public data: every system given the same cases
to learn from and scored on the same held-out cases, nothing tuned on them. Each folder has the full write-up, the
judges' brief (`judge_prompt.md`), the published answers in `results/` and the scripts.

| Folder | What |
|---|---|
| [`banking77`](banking77) | Routing a bank customer's message to one of 77 intents from its text alone (Banking77, PolyAI, CC BY 4.0) |
| [`credit`](credit) | Approving or refusing a loan from 20 typed fields, at the bank's own cost (German Credit, UCI Statlog, CC BY 4.0) |
| [`issues`](issues) | GitHub issue triage, free text, Ada's weakest fit; kept for the record |
| [`session`](session) | What a Claude Code turn needs from the turns before it, and what carrying all of them costs |

The scripts that run Ada import its kernel, which ships inside rrotor (Glyphh's runtime) and is not in this
repository; what can be checked from here is the published results, the prompts and the scoring scripts, and the LLM
side can be rerun from them (each folder's README says how). The data sets are fetched by each folder's `fetch.sh`,
not kept here.

## Banking77

Routing 200 real bank messages to one of 77 intents, each message its own call as a chatbot makes them, every
system given the same 10,003 past cases, scored on the same 200 (opaque ids, nothing tuned on them). Dollars at the
models' list prices.

| | Accuracy | Cost for the 200 | Cost per 1,000 messages | Same answer twice? |
|---|---|---|---|---|
| Claude Fable 5.1 alone | 96.5% | $300 | $1,500 | 199 of 200 |
| Claude Opus 5.5 alone | 96.0% | $120 | $600 | |
| Claude Sonnet 5.5 alone | 86.0% | $60 | $300 | |
| Claude Haiku 4.5 alone | 81.0% | $30 | $150 | |
| Ada alone | 90.0% | $0.000006 | $0.00003 | always |
| **Ada, then Fable for the 22% it is unsure of** | **97.5%** | **$0.22** | **$1.10** | Ada's share always |
| Ada, then Opus | 97.0% | $0.09 | $0.44 | |
| Ada, then Sonnet | 94.0% | $0.04 | $0.22 | |
| Ada, then Haiku | 91.5% | $0.02 | $0.11 | |

## Credit

Deciding 200 real loan applications, approve or refuse, from 20 fields each; every system learned the same 800;
the bank's cost counts a bad loan approved as five good ones refused. Dollars for the 200 at list prices.

| | Accuracy | Bank's cost | Cost for the 200 |
|---|---|---|---|
| Always approve | 67.5% | 325 | $0 |
| Claude Fable 5.1, two runs (disagreed on 12 of 200) | 77.0% / 79.0% | 110 / 114 | $4.20 batched, ~$300 one by one |
| Logistic regression, cost-aware | 68.5% | 103 | ~$0 |
| **Ada, learned fields and interactions, calibrated, `decide`** | 70.0% | **100** | $0.00001 |
| Ada, asking a person where every answer is dear (111 of 200 decided) | 81.1% | 45 on those | $0.00001 |

## Data and licences

- Banking77: Casanueva et al., "Efficient Intent Detection with Dual Sentence Encoders" (2020), PolyAI,
  https://github.com/PolyAI-LDN/task-specific-datasets, CC BY 4.0. `banking77/results/` holds a 200-message sample
  of its test split.
- German Credit: Hofmann, H. (1994), Statlog (German Credit Data), UCI Machine Learning Repository,
  https://doi.org/10.24432/C5NC77, CC BY 4.0.

The write-ups, results and scripts here are MIT ([`LICENSE`](LICENSE)).
