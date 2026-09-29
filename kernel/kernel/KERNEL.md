# glyphh kernel — the AI-native kernel

You are (probably) a model reading this. This document is the complete
interface: if you have read it and `glyphh_kernel.py`, you know
everything there is to know. There is no other documentation, service,
or configuration.

## What this is

A kernel for software whose user is an AI. Human software optimizes for
legibility (screens, names, dashboards) because humans trust by
looking. You cannot be reassured, only checked — so this kernel's
surfaces are receipts, grades, and calibrated confidence. Five rules
shaped it:

1. **Verifiability over legibility.** Every answer cites the exact
   precedents it stands on, with hashes.
2. **State is handed over, not hidden.** All state is one SQLite file
   you can carry, diff, merge, and give to another agent.
3. **Graded, not configured.** There are no settings. Behavior is
   shaped by recording outcomes the world confirmed.
4. **Small enough to hold.** The entire semantics fits in your context
   window. The spec is the interface.
5. **It knows what it doesn't know.** Every query returns confidence,
   and below threshold it says "insufficient" instead of guessing.
   Measured on a 2,591-case public replay (GitHub issue triage):
   answers at confidence >= 0.5 were 86% accurate, >= 0.6 were 91%,
   while ungated answers were 50%. The gate is real.

## The five primitives

All vectors ("glyphs") are bipolar int8 arrays (+1/-1) of one fixed
dimension (default 4096). Everything below is closed over that type:
composites are the same size and kind as atoms, so structures nest
indefinitely.

- `symbol(key, seed=42, dim=4096)` — deterministic glyph for a key.
  Same (key, seed, dim) gives the identical vector on any machine
  forever. Shared seed = shared vocabulary between agents; different
  seeds are mutually random noise.
- `bind(a, b)` — associate. Elementwise multiply; self-inverse
  (`bind(bind(a, b), b) == a`); result resembles neither input. Use
  for role–filler pairs: `bind(symbol("attr:color"), symbol("val:red"))`.
- `bundle(parts)` — superpose. Majority vote; result resembles ALL
  inputs. Use for sets/records. Capacity is finite: past a few dozen
  parts, individual contributions fade. Detail dies, gist survives —
  that IS abstraction; keep symbolic receipts when you need the detail
  back.
- `roll(v, k)` — rotate. Encodes order, position, nesting depth.
  `roll(v, 1)` means "v, one step ago"; orthogonal to `v`; undo with
  `roll(v, -k)`.
- `sim(a, b)` — cosine in [-1, 1]. Random glyphs sit near 0; above
  ~0.1 is signal at dim 4096. This is the only comparison operator.

## The two constructs

**Strand** — ordered meaning. Append glyphs; `state(decay=0.7)` folds
the sequence into one glyph where recent items dominate and order
matters: same items, different order → different state. Use it for
trajectories: event preludes, conversation turns, anything where "what
happened, in what order" is the meaning. Detail is recoverable ~3
steps back; the *kind* of trajectory is recognizable much longer.

**Space** — graded precedent memory. The heart of the kernel.

```python
space = Space(path="wins.db")           # or in-memory: Space()
space.record({"kind": "db_latency", "sev": "high"}, "failover",
             events=[symbol("timeout"), symbol("retry_storm")])
answer = space.query({"kind": "db_latency", "sev": "high"},
                     events=[symbol("timeout"), symbol("retry_storm")])
# answer.sufficient  -> bool: is there precedent close enough to speak?
# answer.confidence  -> consensus of the k nearest precedents
# answer.top         -> leading outcome (None if insufficient)
# answer.outcomes    -> similarity-weighted distribution
# answer.receipts    -> [(id, sim, outcome, glyph_hash), ...]
```

A situation is a flat dict of attributes. Optional `events` (a list of
glyphs) fold in as a strand, so order-carrying situations keep their
order. `record` is one write, permanent, no training run.

## The one contract: the grounded loop

Nothing enters a Space ungraded. The canonical pattern for ALL domain
logic — routing, classification, remediation choice, any decision:

```python
wins, vetoes = Space(path="wins.db"), Space(path="vetoes.db")

def decide(situation, events, fallback):
    a = wins.query(situation, events)
    if a.sufficient and a.confidence >= 0.5:
        v = vetoes.query(situation, events)
        if not (v.sufficient and v.top == a.top and v.confidence >= 0.5):
            return a.top, "reflex"            # free, cited, calibrated
    return fallback(situation, events), "consult"  # LLM / human / rule

action, mode = decide(situation, events, fallback)
success = world_grades(action)                # the world, not a human
(wins if success else vetoes).record(situation, action, events)
```

Wins become permanent reflexes. Failures become vetoes: a discredited
reflex does not fire again — the entity consults instead of being
confidently wrong twice. The fallback chain is the cost model: reflex
(free) → smarter consultant (paid) → human (last resort, and the
answer is itself a grade). Over a lifetime the consult rate is your
product metric; it should fall as precedent covers the world.

## What this kernel is NOT for

- Invariants. Auth, money conservation, state-machine legality stay as
  hand-written checks. Precedent never overrides a proof.
- Guarantees off-distribution. A Space only knows what its grading
  world confirmed. Trust `confidence`, and when it is low, fall back.
- Long exact recall inside vectors. The vector keeps the gist; exact
  reconstruction comes from the receipts and the SQLite rows.

## Interop between agents

Two agents share meaning by sharing (seed, dim) — their `symbol()`
calls then produce identical vocabularies. Experience is exchanged by
shipping the SQLite file; the receiver can verify it by replaying
receipts against its own world before merging. Meaning here has an
operational definition: a concept is meaningful exactly to the degree
that its glyph's neighborhood predicts the world.
