# glyphh

An algebra of thought for AI. One Python file, one dependency (numpy).

Models reason in prose, and prose doesn't compose: you can't take two
conclusions, combine them into a third, and hand that to the next step
as a value. glyphh gives a model values it can do that with. A meaning
is a vector (a "glyph"). Five operations build glyphs out of glyphs,
and every operation returns the type it takes, so anything built can
be taken apart, compared, abstracted, and built on again. That closure
is the point: reasoning on top of reasoning, to any depth.

There is no server or service; you import the module. When a result
is worth keeping, it's a plain SQLite file.

```
glyphh_kernel.py    the kernel
test_kernel.py      its tests
dogfood/            working state of the agent that develops this repo
```

## Install

Install into a virtual environment. Homebrew and Debian Pythons refuse
a bare `pip install` (`externally-managed-environment`, PEP 668):

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

`-e` keeps the install pointed at this checkout, so edits take effect
without reinstalling. Activate with `source .venv/bin/activate`, or call
`.venv/bin/python` directly. With uv, `uv venv && uv pip install -e
'.[dev]'` does the same.

Or skip packaging: copy `glyphh_kernel.py` into your project and
install `numpy` into that project's environment. The module embeds its own
usage guide: `spec()` returns the full guidance (primitives,
constructs, thresholds), so the file is self-documenting wherever it
ends up:

```python
from glyphh_kernel import spec
print(spec())
```

This README covers the same material with more context.

## Quick start: thinking in glyphs

A thought is a structure: roles bound to fillers, bundled into one
glyph.

```python
from glyphh_kernel import symbol as S, bind, bundle, sim, Strand

def thought(**parts):
    return bundle([bind(S(role), filler) for role, filler in parts.items()])

migrate  = thought(goal=S("move_data"),  risk=S("downtime"),   step=S("dual_write"))
backfill = thought(goal=S("move_data"),  risk=S("lock_table"), step=S("batch_copy"))
refactor = thought(goal=S("clean_code"), risk=S("regression"), step=S("add_tests"))
```

**Compare.** Thoughts that share structure measure close; unrelated
ones measure near zero.

```python
sim(migrate, backfill)             # 0.25  same goal, different plan
sim(migrate, refactor)             # -0.03 unrelated
```

**Ask.** `bind` is its own inverse, so binding a thought with a role
reads that role back out.

```python
sim(bind(migrate, S("risk")), S("downtime"))     # 0.50  yes
sim(bind(migrate, S("risk")), S("lock_table"))   # 0.00  no
```

**Abstract.** Bundle cases into a concept. Detail fades, gist
survives.

```python
data_work = bundle([migrate, backfill])
sim(data_work, migrate)            # 0.62  an instance of the concept
sim(data_work, refactor)           # -0.01 not one
```

**Recurse.** A concept is a value like any other, so it can be a
filler inside a bigger thought and still be queried from inside.

```python
plan  = thought(phase=S("q3"), approach=data_work, owner=S("platform"))
inner = bind(plan, S("approach"))
sim(inner, data_work)                         # 0.51  the concept, recovered
sim(bind(inner, S("goal")), S("move_data"))   # 0.28  its goal, two levels down
sim(bind(inner, S("goal")), S("clean_code"))  # 0.04  not this one
```

**Sequence.** Order is structure too. The same thoughts in a
different order are a different thought.

```python
sim(Strand([migrate, backfill, refactor]).state(),
    Strand([refactor, backfill, migrate]).state())   # 0.25
```

Signal weakens as structures nest (0.50 at one level, 0.28 at two),
which is the algebra's budget: compose freely, but compare against
known candidates rather than expecting exact recovery from deep
inside a bundle.

**Judge.** A `Space` learns a function from graded examples: record
what a situation led to and whether it worked, then query similar
situations later. Composed thoughts ride along as `events`.

```python
from glyphh_kernel import Space

wins = Space(author="my-agent", path="wins.db")
wins.record({"kind": "schema_change", "size": "large"}, "dual_write",
            events=[plan])

a = wins.query({"kind": "schema_change", "size": "large"}, events=[plan])
a.sufficient   # any precedent close enough to count?
a.confidence   # how strongly do the close precedents agree?
a.count        # how many cleared the similarity bar
a.top          # leading outcome
a.receipts     # (id, similarity, outcome, hash, author) per precedent
```

## Primitives

All vectors ("glyphs") are ±1 int8 arrays of one fixed dimension
(default 4096). Every operation returns the same type it takes, so
composed structures can be composed again.

| primitive | behavior |
|---|---|
| `symbol(key, seed=42, dim=4096)` | Deterministic glyph for a key: same inputs produce the identical vector on any machine. Agents that share a seed share a vocabulary; different seeds produce unrelated vectors. |
| `bind(a, b)` | Elementwise multiply. Self-inverse; the result is dissimilar to both inputs. Used for role–value pairs. |
| `bundle(parts)` | Majority vote. The result is similar to every input, and independent of the order the parts come in (ties are broken by a hash of the parts as a set). Capacity is limited: past a few dozen parts, individual contributions fade. Keep the source data if you need it back exactly. |
| `roll(v, k)` | Rotate. Encodes order and position; `roll(v, -k)` inverts it. |
| `sim(a, b)` | Cosine in [−1, 1]. Random glyphs measure near 0. For encoded situations, sim tracks the fraction of shared attribute pairs, whichever attributes they are. Measured for 4-attribute situations: sharing 1, 2 or 3 gives 0.14, 0.28 or 0.44. For 2-attribute situations, sharing 1 gives 0.25. That holds even if the shared attributes are irrelevant to the decision. Set thresholds with this in mind. |

## Constructs

**`Strand`** — an ordered sequence of glyphs. `state(decay=0.7)` folds
it into a single glyph where recent items dominate and order matters:
the same items in a different order produce a different state. Use it
for event trails. Individual items are recoverable a few steps back;
the overall shape of the sequence is distinguishable much longer.

**`Space`** — a judgment defined by example. Each graded record
is part of the definition; each query is a call.

```python
Space(dim=4096, k=15, min_sim=0.10, seed=42, decay=0.7,
      author="anon", path=None)
```

- `record(situation, outcome, events=None, ts=None)` stores one
  case, time-stamped (now, unless `ts` is given).
  - A situation is a flat dict of attributes.
  - The optional `events` (a list of glyphs) are folded in as a strand,
    so order is part of the match. They are stored with the row, so
    re-encoding is lossless.
- `query(situation, events=None)` → `Answer` with `sufficient`,
  `confidence`, `support`, `count`, `top`, `outcomes`, `receipts`.
  Only precedents at or above `min_sim` contribute to the vote.
- `answers(situation, events=None, min_count=1)` → `[Evidence]` for
  every outcome with qualifying precedent, strongest first. Use it
  when a situation genuinely has several true outcomes (a file that
  imports five modules): gate each outcome on its own `count` instead
  of its share of the vote.
- `evidence(situation, outcome, events=None)` → `Evidence(count,
  support, nearest, latest, authors)` for one candidate. It is judged
  over every precedent, not just the top `k`.
- `matches(situation, outcome, events=None)` — max similarity among
  precedents with that exact outcome. A direct nearest-case check
  that a consensus vote cannot dilute; used for vetoes.
- `refresh()` — load rows other agents wrote to a shared file since
  it was opened.
- `merge(other_path)` — union another Space file by precedent id.
  Authors are preserved and the result is persisted.
- Files open in WAL mode, so several processes can share one. Call
  `close()` or use the Space as a context manager.
- **Stores outlive encodings.** Each file records the encoding it was
  written under (`ENCODING`, currently 2).
  - Opening or merging a file from an older encoding re-encodes its
    glyphs from the stored situations and events.
  - Files from before time-stamping read `ts = 0`.
  - `reencode_store(path)` forces a rebuild, for example after changing
    `seed` or `decay`.

## The decision loop

The pattern for using a `Space` as a learned function inside a
program. Route decisions through precedent, fall back when precedent is thin,
and record the graded result either way. Wins become future answers;
failures become vetoes.

```python
from glyphh_kernel import Space, decide

wins, vetoes = Space(path="wins.db"), Space(path="vetoes.db")

d = decide(wins, vetoes, situation, events)   # the contract, as code
action = d.outcome if d.act else fallback(situation, events)
success = world_grades(action)     # graded by outcome, not self-assessed
(wins if success else vetoes).record(situation, action, events)
```

`decide()` applies the three trust gates and then the veto check, and
reports `reason`: `reflex`, `insufficient`, `uncalibrated`,
`low_confidence` or `vetoed`.

The three gates:
- `sufficient`: something clears `min_sim`;
- `confidence >= 0.5`;
- `count >= 3`.

The veto check:
- A recorded failure of the recommended action blocks the reflex when
  it is as close as the wins **and newer than the newest win**.
- A later reproduction lifts an older veto (`lifted=True`), and a later
  failure re-imposes it.
- `min_veto_count=2` demands corroborated failures before blocking.
  That makes it harder for one bad grader to erase a true fact, at the
  cost of reacting more slowly.

The fallback can be anything: a rule, an LLM call, a human. As
precedent accumulates, the fallback is consulted less.

## Usage rules

1. **Check three fields before trusting an answer**: `sufficient`
   (similarity), `confidence` (consensus), `count` (population). One
   precedent yields confidence 1.0; require `count >= 3`.
2. **Encode only decision-relevant attributes.** Incidental fields
   (ids, regions, timestamps) make unrelated situations measure
   similar. Set `min_sim` to the attribute-overlap fraction that
   should count as the same kind of situation.
3. **Vetoes suppress; they don't erase, and the newest evidence
   wins.** A close failure blocks the reflex until a newer success for
   the same action outranks it. Use `matches()` / `decide()` for veto
   checks, not `query()`, because a consensus vote lets unrelated
   failures dilute the veto.
4. **One question can have several true answers.** When confidence
   splits across outcomes that are all correct, that is not
   disagreement. Read `answers()` and gate each outcome on its own
   count.
5. **Don't use precedent for invariants.** Auth checks, money
   conservation, and state-machine legality stay as ordinary code.

## Multiple agents

Give each agent its own Space files and the team one shared set.
Construct with `author=` so receipts show who recorded each
precedent. Share a file directly (WAL plus `refresh()`) or exchange
files and `merge()`. Before merging another agent's file, replay its
receipts against your own data to check the outcomes hold. Agents
share a vocabulary by sharing `(seed, dim)`.

## Measurements

Numbers from the replays this design was validated on:

- 2,591 Kubernetes GitHub issues replayed in chronological order,
  predicting SIG labels: precedent answers at confidence ≥ 0.5 were
  86% accurate (91% at ≥ 0.6); ungated answers were 50%.
- On the same replay, the decision loop with a live LLM fallback
  reached 0.862 accuracy versus 0.599 for a continuously retrained
  TF-IDF + logistic regression baseline.
- Ordered strand state predicted next steps at 0.710 versus 0.595 for
  an unordered bundle; sequence-anomaly detection reached AUC 0.748.
- A separate agent, given only this file and the spec, built a
  working application on the kernel unaided. The problems it found
  are fixed and covered in `test_kernel.py`.
- Four agents given only the kernel built a shared language, a glyph
  protocol, a knowledge base that trusts only independent
  reproductions, and a reasoning layer. A second swarm then used that
  stack to audit a multi-repo codebase: 632 claims and 1,737 grades,
  with all 7 planted claims (3 true, 4 false) judged correctly.
  - A numpy-only control reached comparable tooling.
  - The kernel's contribution was its trust defaults and its fixed
    encoding.
  - The kernel fixes in encoding 2 (time-ordered vetoes, `answers()`,
    `decide()`, unbiased tie-breaks) came from what those agents hit.

  See [`research/agent-language/`](research/agent-language/).

## Claude Code integration

The repo doubles as a plugin marketplace. `plugin/` bundles the
kernel, a `glyphh-think` skill, an MCP server, and three hooks for one
use of the
algebra: a `Space` of graded precedent kept alongside the agent, wired
into its loop rather than left to discretion:

- **SessionStart** injects the memory's state (counts, known
  situation kinds, vetoed approaches) into context at boot.
- **UserPromptSubmit** matches each incoming prompt against stored
  situations and injects relevant precedent, wins and vetoes both.
- **Stop** blocks the end of a turn once per session if the memory
  exists and nothing was recorded, asking for graded outcomes to be
  written or an explicit "nothing was graded."

The **MCP server** (`plugin/mcp/server.py`, registered by
`plugin/.mcp.json`) is how the agent reads and writes the memory:
tools `query`, `record`, `veto`, `check` and `status`. Claude Code
launches it over stdio, outside the agent's shell sandbox, so writes
land without a sandbox exception, a port, or a token. It is stdlib
plus the kernel, and refreshes from disk before every read so rows
other sessions wrote count.

Install:

```
/plugin marketplace add glyphh-ai/ada
/plugin install glyphh@glyphh
```

The memory is one store, the same in every session and directory:
`$GLYPHH_HOME/ada`, else `~/.glyphh/ada`. Hooks read its SQLite files
directly; the MCP server opens it through the kernel.

## Tests

```bash
.venv/bin/python -m pytest test_kernel.py test_plugin.py test_mcp.py -q
```

The research stacks carry their own tests; see
`research/agent-language/README.md`.

## License

Proprietary — glyphh.ai
