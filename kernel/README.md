# glyphh

**A kernel for software whose user is an AI.**

An agent's context window is mortal — it fills, compacts, and ends.
glyphh is the state and execution layer that survives it: graded
memory, calibrated decisions, and receipts for everything, in one
Python file with one dependency (numpy). State lives in SQLite files
the agent owns — carried between contexts, shared between agents, and
versioned like any other file. There is no server, no service, no
protocol. You import it.

```
glyphh_kernel.py    the kernel (single file, numpy + stdlib)
test_kernel.py      its invariants, as tests
dogfood/            the authoring agent's own working memory, built on
                    the kernel and committed as ordinary repo state
```

Everything this was distilled from — the full HDC substrate, a
runtime, the experiments and evals behind every number below — lives
in git history on the `archive/full-history` branch.

## Install

```bash
pip install numpy   # that's all
```

Copy `glyphh_kernel.py` into your project, or hand this README plus
that file to an agent as context. The file and this document together
are the complete interface.

## Sixty seconds

```python
from glyphh_kernel import Space, symbol

wins = Space(author="my-agent", path="wins.db")

# Record graded experience: one write, permanent, no training run.
wins.record({"kind": "db_latency", "sev": "high"}, "failover",
            events=[symbol("timeout"), symbol("retry_storm")])

# Ask: is there precedent for this situation?
a = wins.query({"kind": "db_latency", "sev": "high"},
               events=[symbol("timeout"), symbol("retry_storm")])
a.sufficient   # is any precedent close enough to speak?
a.confidence   # do the close precedents agree?
a.count        # how many actually voted?
a.top          # the leading outcome
a.receipts     # (id, similarity, outcome, hash, author) — the proof
```

## The five primitives

All vectors ("glyphs") are bipolar ±1 arrays of one fixed dimension
(default 4096). Every operation returns the same type it takes, so
composites nest indefinitely.

| primitive | what it does |
|---|---|
| `symbol(key, seed=42, dim=4096)` | deterministic glyph for a key — same inputs give the identical vector on any machine, forever. Shared seed = shared vocabulary between agents; different seeds are mutually random noise |
| `bind(a, b)` | associate (elementwise multiply). Self-inverse; the result resembles neither input. Use for role–filler pairs |
| `bundle(parts)` | superpose (majority vote). The result resembles ALL inputs. Capacity is finite: past a few dozen parts, detail fades and gist survives — that is abstraction, so keep receipts for the detail |
| `roll(v, k)` | rotate — encodes order, position, depth. `roll(v, 1)` is "v, one step ago"; undo with `roll(v, -k)` |
| `sim(a, b)` | cosine in [−1, 1]. Random glyphs sit near 0. For situations, sim tracks the **fraction of shared attribute pairs** — two 4-attribute situations sharing 2 attributes measure ~0.4–0.5 even when the shared attributes are irrelevant. Understand this before choosing thresholds |

## The two constructs

**`Strand`** — ordered meaning. Append glyphs; `state(decay=0.7)`
folds the sequence into one glyph where recent items dominate and
order matters: same items, different order → different state. Use it
for trajectories. Detail is recoverable a few steps back; the *kind*
of trajectory is recognizable much longer.

**`Space`** — graded precedent memory.

```python
Space(dim=4096, k=15, min_sim=0.10, seed=42, decay=0.7,
      author="anon", path=None)
```

- `record(situation, outcome, events=None)` — one write, permanent. A
  situation is a flat dict of attributes; optional `events` (a list of
  glyphs) fold in as a strand so order-carrying situations keep their
  order.
- `query(situation, events=None)` → `Answer` with `sufficient`,
  `confidence`, `support`, `count`, `top`, `outcomes`, `receipts`.
  Only precedents clearing `min_sim` get a vote.
- `matches(situation, outcome, events=None)` — max similarity among
  precedents with *that exact outcome*. A direct nearest-case check no
  consensus vote can dilute: the veto primitive.
- `refresh()` — pull in rows other agents wrote to a shared file.
- `merge(other_path)` — union another Space file by precedent id;
  authors preserved, result persisted.
- Files open in WAL mode, so several agents can share one. `close()`
  or use as a context manager.

## The contract: nothing ungraded

Every domain decision flows through one loop. Wins become reflexes;
failures become vetoes; the world — not a human, not the LLM — is the
judge.

```python
wins, vetoes = Space(path="wins.db"), Space(path="vetoes.db")

def decide(situation, events, fallback):
    a = wins.query(situation, events)
    if a.sufficient and a.confidence >= 0.5 and a.count >= 3:
        # veto: is the nearest recorded FAILURE of this action as
        # close as the wins recommending it? Then don't trust it.
        if vetoes.matches(situation, a.top, events) < a.support:
            return a.top, "reflex"              # free, cited
    return fallback(situation, events), "consult"   # LLM / human / rule

action, mode = decide(situation, events, fallback)
success = world_grades(action)
(wins if success else vetoes).record(situation, action, events)
```

The fallback chain is the cost model: reflex (free) → smarter
consultant (paid) → human (last resort, and the answer is itself a
grade). Over a lifetime, the consult rate should fall as precedent
covers the world — that curve is the product metric.

## Rules that decide whether it works

1. **Trust needs three gates.** `sufficient` gates on similarity,
   `confidence` on consensus, `count` on population — a consensus of
   one is confidence 1.0 and means almost nothing. Gate on all three.
2. **Attribute hygiene.** Encode ONLY decision-relevant attributes.
   Incidental ones (regions, ids, timestamps) make unrelated
   situations measure alike and poison neighborhoods; keep them in
   receipts instead. Size `min_sim` as the attribute-overlap fraction
   that should count as "the same kind of situation."
3. **Vetoes suppress; they don't erase.** A veto blocks a reflex once
   a recorded failure sits as close as the wins recommending it. After
   the world changes, a reflex can fire wrongly a few times while
   failures accumulate to parity — use `matches`, never a consensus
   vote, or unrelated failures dilute the veto.
4. **Precedent never overrides a proof.** Auth, money conservation,
   state-machine legality stay as hand-written checks.

## More than one agent

Each agent keeps a private kernel (its own wins/vetoes); the team
keeps a shared one. Construct with `author="<name>"` — every receipt
shows who grounded it. Share a file live (WAL + `refresh()`) or ship
files and `merge()` — and verify before you trust: replay incoming
receipts against your own world first. Two agents share *meaning* by
sharing `(seed, dim)`. A concept is meaningful exactly to the degree
that its glyph's neighborhood predicts the world; a teammate's
precedent is trustworthy exactly to the degree its receipts replay.

## Measured, not promised

The numbers behind the design, from replays preserved on
`archive/full-history`:

- **Calibration on public data** — 2,591 kubernetes/kubernetes issues
  replayed chronologically: precedent answers at confidence ≥ 0.5 were
  **86% accurate** (91% at ≥ 0.6); ungated answers were 50%.
- **The grounded loop, live** — an agent consulting a real LLM only
  where precedent was thin reached **0.862 accuracy vs 0.599** for a
  continuously retrained TF-IDF baseline on that replay; in a closed
  world, world-graded reflexes (0.94) beat their own teacher (0.45).
- **Order is signal** — strand state 0.710 next-step accuracy vs 0.595
  unordered; trajectory-anomaly detection AUC 0.748.
- **Cold-agent test** — a fresh agent handed only the kernel and spec
  built a working application unaided; its adversarial findings were
  fixed and are pinned in `test_kernel.py`.

## Tests

```bash
python3 -m pytest test_kernel.py -q
```

## License

Proprietary — glyphh.ai
