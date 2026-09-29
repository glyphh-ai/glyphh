# glyphh kernel — the AI-native kernel

You are (probably) a model reading this. This document is the complete
interface: if you have read it and `glyphh_kernel.py`, you know
everything there is to know. There is no other documentation, service,
or configuration.

## What this is

A kernel for software whose user is an AI: **your state and execution
layer beyond the context window.** Your context is mortal — it fills,
compacts, and ends. What you record here does not. A Space file is the
part of you that survives into your next context: reopen it and your
graded experience, your vetoes, and your receipts are simply there,
with no re-reading of transcripts and no summarization loss. Record as
you work; the next context (yours, or another agent's) inherits ground
truth instead of prose about it.

There is no service, no server, no protocol between you and this —
you import it and you own the files. Human software optimizes for
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
5. **It knows what it doesn't know — behind TWO gates, not one.**
   `sufficient`/`support` gate on *similarity* (is any precedent close
   enough to speak? controlled by `min_sim`); `confidence` gates on
   *consensus* (do the close precedents agree?). You must check both,
   plus `count`: a consensus of one precedent is confidence 1.0 and
   means almost nothing. Measured on a 2,591-case public replay
   (GitHub issue triage), answers at confidence >= 0.5 were 86%
   accurate versus 50% ungated — but that calibration holds for
   *populated* neighborhoods, not sparse ones. Early in a Space's
   life, gate on `count >= 3` as well.

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
- `sim(a, b)` — cosine in [-1, 1]. Random glyphs sit near 0. For
  situation glyphs, sim approximately tracks the FRACTION OF SHARED
  ATTRIBUTE PAIRS: two 4-attribute situations sharing 2 attributes
  measure ~0.4-0.5 even when the shared attributes are irrelevant to
  the decision. This is the only comparison operator; understand what
  it measures before choosing thresholds.

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
glyphs) fold in as a strand (decay set by `Space(decay=...)`), so
order-carrying situations keep their order. `record` is one write,
permanent, no training run.

**Attribute hygiene — the rule that decides whether a Space works:**
encode ONLY decision-relevant attributes. Because sim tracks attribute
overlap, incidental attributes (regions, hostnames, timestamps, ids)
make unrelated situations measure alike and poison neighborhoods; a
situation sharing only its noise attributes with a precedent can
outscore one sharing the attributes that matter. If you are unsure
whether an attribute is relevant, leave it out and keep it in the
receipts instead. Set `min_sim` to the overlap fraction that should
count as "the same kind of situation" — with 4 attributes of which 3
must match, that is ~0.5-0.75, and the default 0.10 only excludes
near-strangers. Only precedents clearing `min_sim` get a vote;
`count` tells you how many did.

`matches(situation, outcome, events)` returns the max similarity among
precedents with that exact outcome — a direct nearest-case check that
no consensus vote can dilute. It exists because vetoes need it (below).

## The one contract: the grounded loop

Nothing enters a Space ungraded. The canonical pattern for ALL domain
logic — routing, classification, remediation choice, any decision:

```python
wins, vetoes = Space(path="wins.db"), Space(path="vetoes.db")

def decide(situation, events, fallback):
    a = wins.query(situation, events)
    if a.sufficient and a.confidence >= 0.5 and a.count >= 3:
        # veto: is the nearest recorded FAILURE of this exact action
        # as close as the wins that recommend it? Then don't trust it.
        if vetoes.matches(situation, a.top, events) < a.support:
            return a.top, "reflex"            # free, cited, calibrated
    return fallback(situation, events), "consult"  # LLM / human / rule

action, mode = decide(situation, events, fallback)
success = world_grades(action)                # the world, not a human
(wins if success else vetoes).record(situation, action, events)
```

Wins become permanent reflexes. Failures become vetoes. Be precise
about what a veto is: it SUPPRESSES a reflex whenever a recorded
failure of that action sits as close to the situation as the wins
recommending it — it is not a guarantee that a discredited reflex
never fires again. Old wins for the same action remain precedent, so
after the world changes (drift), a reflex can fire wrongly a few more
times while failures accumulate to parity; use `matches` (above)
rather than a `vetoes.query` consensus vote, or unrelated failures
will dilute the veto and stretch that window. The fallback chain is
the cost model: reflex (free) → smarter consultant (paid) → human
(last resort, and the answer is itself a grade). Over a lifetime the
consult rate is your product metric; it should fall as precedent
covers the world.

## What this kernel is NOT for

- Invariants. Auth, money conservation, state-machine legality stay as
  hand-written checks. Precedent never overrides a proof.
- Guarantees off-distribution. A Space only knows what its grading
  world confirmed. Trust `confidence`, and when it is low, fall back.
- Long exact recall inside vectors. The vector keeps the gist; exact
  reconstruction comes from the receipts and the SQLite rows.

## More than one agent: the three-kernel topology

The kernel is built for teams of agents, and the working pattern is:
**each agent keeps its own kernel, and the team keeps a shared one.**

- **Private kernels** (per agent): your own wins/vetoes — your
  competence, your mistakes, tuned to your role. Nobody else writes
  here; your reflexes stay yours.
- **The shared kernel** (one per team/task): Spaces every agent reads
  and writes. Construct with `author="<your name>"` — every precedent
  carries its author, and every receipt shows who contributed it, so
  a surprising answer is checkable back to the agent that grounded it.

Sharing works two ways, both first-class:

1. **Same file, live.** Spaces open in WAL mode; several agents can
   write one file concurrently. Call `refresh()` to pull in rows other
   agents wrote since you opened — do it before querying if teammates
   are active.
2. **Separate files, exchanged.** `merge(other_path)` unions another
   Space file into yours by precedent id (duplicates skipped, authors
   preserved, result persisted). Verify before you trust: replay the
   incoming receipts against your own world first; merge is adoption,
   not belief.

Two agents share *meaning* by sharing (seed, dim) — their `symbol()`
calls then produce identical vocabularies; different seeds are
mutually random noise. The escalation path mirrors the fallback
chain: consult your private kernel first (free, yours), then the
shared kernel (free, the team's), then a live consultant. Record your
graded outcome back to whichever kernel should carry it — team-useful
lessons go to the shared one, with your name on them.

Meaning here has an operational definition at every scale: a concept
is meaningful exactly to the degree that its glyph's neighborhood
predicts the world — and a *teammate's* precedent is trustworthy
exactly to the degree its receipts replay.
