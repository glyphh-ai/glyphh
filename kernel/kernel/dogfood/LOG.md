# Dogfood log — the kernel as the working agent's own memory

The agent working on this repo (Claude, in the session that built the
kernel) uses `mem.py` — wins.db and vetoes.db, committed alongside —
as session memory: recording graded operational experience and
querying it before repeating a kind of decision. Every use gets an
entry here: what was asked, what the kernel answered, and whether it
helped, was neutral, or got in the way. Failures get logged as
prominently as wins; that is the point of the exercise.

Entry format: **when · situation · kernel's answer · what I did ·
verdict** (helped / neutral / hindered / kernel-was-wrong).

---

## 2026-09-29 · bootstrap

Seeded the stores with this session's genuinely graded experience —
10 wins (patterns that demonstrably worked: detached long runs via
setsid+status-file, the branch-then-ff-main push dance, secrets via
sourced env file, the mcp<2 pin, prequential-with-honest-baselines
eval design, ...) and 4 vetoes (approaches that failed or were
refused: harness-tracked background for >10-min runs, chained sleep
polling, secret literals in commands, tuning parameters against a
simulated teacher after "don't game it").

First live queries, immediately after seeding:

- `query {task: long_background_run, constraint: exceeds_tool_timeout}`
  → `setsid_nohup_with_status_file`, confidence 1.0, count 1, veto 0.0.
  Correct. The seven receipts also showed unrelated precedents at
  sim ~0.26-0.27, all correctly below the 0.40 bar and voteless —
  the cold-test fix (below-min_sim rows don't vote) doing its job on
  real data.
- `veto {task: long_background_run, ...} run_in_background_tool`
  → veto_sim 1.0. The exact mistake this session actually made (a
  10-minute cap killed a 2-hour run mid-flight) is now un-repeatable
  without an explicit warning.

Honest note on the sparse regime, per KERNEL.md's own rule: with one
precedent per situation kind, confidence 1.0 is a consensus of one and
count=1 is below the count>=3 gate — so right now this store is a
*reminder* system with receipts, not yet a calibrated decision system.
It earns calibration the same way the k8s replay did: by accumulating
graded repeats. Verdict on bootstrap: **helped** (setup cost ~5 min;
the veto check alone would have saved one real 2-hour-run loss today).
