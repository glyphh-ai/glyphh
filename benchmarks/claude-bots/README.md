# Benchmark: a bot that learned its job, then did it for a twentieth of the cost

A Glyphh bot is a Claude agent governed by a program: the program runs the loop and holds the hard gates (budget,
what it may do, approvals) in code; Ada gates (learned models, Ada Cloud) make the judgment calls between steps and
learn from real outcomes; Claude is called only for the steps that need it. Run on 2026-11-03 on a Mac, Claude Code
2.1, every trial `claude -p` in a fresh temp folder, judged by hidden tests Claude never saw.

## 1. The lab: the orchestrator finds out how Claude does coding work best

`bots/lab` is the orchestrator as a bot. Each generation its Claude agent proposed experiments (Haiku, Sonnet or
Opus; a plain prompt, tests first, plan first or edge cases first); its program refused any proposal outside those
arms or changing more than one thing, ranked the rest by its own `promising` gate (an Ada model of which experiments
turn out decisive, recorded from what they really found) and made an experiment bot for each (`bots/exp_e*`). Each
experiment bot's `trial` gate learned which task-and-arm cells were already known and sent trials only where the
outcome was not. 12 tasks in `lab/tasks/` (bugfixes, from-scratch implementations, multi-file changes).

| Experiment | Call |
|---|---|
| e1: Haiku vs Sonnet, bugfix, plain | Haiku matches at 9.7x less cost (6 trials an arm, all passed) |
| e2: Haiku vs Sonnet, implement, plain | Haiku matches at 11.5x less cost (6 an arm, all passed) |
| e3: tests first vs plain, Haiku, bugfix | No difference worth having; tests first cost more (6 an arm) |
| e4-e6 | Open when the lab stopped (3 an arm, all passed) |

After e1-e3, `promising` rated the model-vs-model proposals at P(decisive) 1.00 and 0.95 and a prompting proposal at
0.17, and the lab ran them in that order. 103 trials in all for $3.97 (`results/trials.csv`: every trial, its arm,
outcome, cost and time; mean per trial Haiku $0.0039, Sonnet $0.0395, Opus $0.1011).

## 2. The proof: what the lab learned, applied to work it never saw

`bots/coder` routes each task to a model with its Ada `route` gate, seeded from the lab's trials (each task's cheapest
model that passed every time), escalates Haiku to Sonnet to Opus on a failure, and learns from each task. Five
held-out tasks (`lab/heldout/`: slugify bugfix, token-bucket rate limiter bugfix, topological sort with cycle
reporting, a small template language, a multi-file job queue with retries and dead letters), twice each
(`lab/benchmark.py`):

| Arm | Tasks | Passed | Total $ | vs always-Opus | Total s |
|---|---|---|---|---|---|
| Always Opus | 10 | 10 | 1.057 | 1.00x | 315 |
| Always Sonnet (Claude Code's default) | 10 | 9 | 0.487 | 0.46x | 280 |
| Routed by the coder bot | 10 | 10 | 0.050 | 0.05x | 351 |

The route picked Haiku for every task (P 1.00) and never needed its escalation ladder.

**What it leaves out.** The tasks are small, written for the test, and Python only. Five held-out tasks twice each is
a small sample: read the cost gap, not the pass counts. The hidden tests stand in for a project's own tests. The route
collapsed to one model, so escalation went untested. Haiku was slower. Costs are what Claude Code reports per run.

## Running it

Needs Claude Code signed in, Python 3.11+, the SDK (`pip install glyphh`) and an Ada Cloud API key in
`GLYPHH_API_KEY` (or `~/.glyphh/bots/.env`). The lab's hard budget is `BUDGET_USD` in `lab/trials.py` ($20).

```sh
cd benchmarks/claude-bots
python botrun.py orch install            # the orchestrator's memory and gates
python botrun.py install lab && python botrun.py install coder
python botrun.py run lab --routine       # one generation; repeat to let experiments finish
python lab/benchmark.py                  # the held-out proof: always-Opus, always-Sonnet, routed
```

`botrun.py` and `orch.py` are the proof's runner and orchestrator, kept as they ran; the SDK's `glyphh bot` is the
product version. `BUILDING.md` is what the orchestrator's builder agent follows to write a bot.
