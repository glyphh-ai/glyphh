# glyphh — the AI-native kernel

Software has always been written for humans. glyphh is software whose
user is an AI: a kernel an agent imports to get **state and execution
beyond the context window** — graded memory, calibrated decisions,
receipts for everything — and the medium through which teams of agents
share verified experience.

**The product is two files:** [`kernel/glyphh_kernel.py`](kernel/glyphh_kernel.py)
(single file, numpy + stdlib, zero dependencies on the rest of this
repo) and [`kernel/KERNEL.md`](kernel/KERNEL.md) (the complete
semantics, written for a model reader — the spec *is* the interface,
small enough to hand to an agent as context). No service, no protocol,
no server: an agent imports the kernel and owns its files.

## What the kernel gives an agent

- **Five primitives** — `symbol · bind · bundle · roll · sim`: a
  closed algebra over fixed-width bipolar vectors. Composites are the
  same type as atoms, so structure nests indefinitely.
- **Strand** — ordered meaning: trajectories where *what happened, in
  what order* is the content.
- **Space** — graded precedent memory: one-shot writes, similarity
  queries, calibrated confidence behind two gates, undilutable vetoes
  (`matches`), and receipts (id, similarity, outcome, hash, author) on
  every answer.
- **Continuity** — a Space is a SQLite file. Contexts are mortal; the
  file is not. The next context (yours or another agent's) reopens it
  and inherits ground truth, not prose about it.
- **The three-kernel topology** — each agent keeps a private kernel;
  the team keeps a shared one (WAL concurrent writes + `refresh()`,
  or file exchange + `merge()`), with every precedent author-tagged.

## The contract

Nothing enters a Space ungraded: the world — not a human, not the LLM —
confirms an outcome before it becomes precedent, and failures become
vetoes. Every answer cites the precedents it stands on. Confidence is
calibrated and the kernel says "insufficient" rather than guess.

## Measured, not promised

All numbers from replays in this repo (`tests/eval/`, `tests/autonomy/`):

- **Calibration on public data** — 2,591 kubernetes/kubernetes issues
  replayed chronologically (GH Archive): precedent answers at
  confidence ≥ 0.5 were **86% accurate** (91% at ≥ 0.6) while ungated
  answers were 50%. The store knows when it knows.
- **The autonomous entity** (`tests/autonomy/`) — an agent that
  consults an LLM only where precedent is thin, grades every action
  against the world, and weans: live-Claude run reached **0.862
  accuracy vs 0.599** for a continuously retrained TF-IDF baseline;
  in a closed world, reflexes (0.94) beat their own teacher (0.45).
- **Order is signal** — strand state 0.710 next-step accuracy vs 0.595
  unordered; trajectory-hijack detection AUC 0.748; outcome AUC 0.867
  by turn 2 of 16. Detail is short-range, shape is long-range, and the
  crossover is measured.
- **Cold-agent proof** (`kernel/coldtest/`) — a fresh agent handed only
  the kernel and spec built a working graded-loop application from the
  spec alone, and its adversarial findings (two oversold safety
  promises, four defects) are fixed and pinned by regression tests.

## Dogfood

The agent that builds this repo uses the kernel as its own session
memory: `kernel/dogfood/` holds its wins/vetoes (committed — the state
IS the artifact) and `LOG.md`, an honest journal of every use with a
helped/neutral/hindered verdict.

## Using it

```python
import sys; sys.path.insert(0, "kernel")
from glyphh_kernel import Space, symbol

wins = Space(author="my-agent", path="wins.db")
wins.record({"kind": "db_latency", "sev": "high"}, "failover",
            events=[symbol("timeout"), symbol("retry_storm")])
answer = wins.query({"kind": "db_latency", "sev": "high"},
                    events=[symbol("timeout"), symbol("retry_storm")])
answer.top, answer.confidence, answer.receipts
```

Read `kernel/KERNEL.md` before building on it — especially the
grounded loop, the two gates, and attribute hygiene. Tests:

```bash
python3 -m pytest tests/kernel -q     # kernel invariants
python3 -m pytest tests/autonomy -q   # the entity, deterministic world
```

## The rest of this repo

Everything outside `kernel/` is reference material and history: the
`glyphh/` package (the original substrate the kernel distills — lattice
ops, strands, the DecisionSpace precedent engine), a headless FastAPI
runtime (`glyphh.server`) with `/v1/strand` and `/v1/decide` surfaces,
model hosting for `.glyphh` packages, and the evals that produced every
number above. The former MCP control plane has been retired: agents
import the kernel; they don't call a service.

## License

Proprietary — glyphh.ai
