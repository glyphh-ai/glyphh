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

## 2026-09-29 · retiring the MCP surface

- `query {task: retire_subsystem, constraint: large_deletion}` →
  **insufficient, count 0** (best sim 0.27, below the 0.40 bar). First
  genuinely novel situation since seeding, and the kernel correctly
  declined instead of pattern-matching something irrelevant. Verdict:
  **helped** (a correct "I don't know" is the calibration property
  working; receipts showed exactly why nothing qualified).
- Proceeded by footprint-mapping (grep) → delete wiring, domain,
  tests, dependency pins. Worked; recorded as a win so the next
  retirement starts from precedent instead of insufficiency.

## 2026-09-29 · the final cut

- `query {task: retire_subsystem, constraint: large_deletion}` →
  **sufficient, sim 1.0**: the footprint-first pattern recorded during
  the MCP retirement came back with my own authorship on the receipt.
  Same situation, second occurrence — this is the continuity story
  working inside one session. Verdict: **helped** (count still 1, so
  treated as a cited reminder, not a calibrated decision).
- Executed: archive branch pushed (`archive/full-history`), then the
  repo cut to kernel + README-as-spec + tests + this memory. The
  kernel outlived the codebase that grew it, carrying its receipts.
