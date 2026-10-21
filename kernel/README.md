# Ada

An algebra of thought for AI. One Python file, one dependency (numpy).

Models reason in prose, and prose doesn't compose: you can't take two
conclusions, combine them into a third, and hand that to the next step
as a value. Ada gives a model values it can do that with. A meaning
is a vector (a "glyph"). Five operations build glyphs out of glyphs,
and every operation returns the type it takes, so anything built can
be taken apart, compared, abstracted, and built on again. That closure
is the point: reasoning on top of reasoning, to any depth.

There is no server or service; you import the module. When a result
is worth keeping, it's a plain SQLite file.

```
glyphh_kernel.py    the kernel
glyphh_spec.py      the Glyphh spec: a model's typed config (layers,
                    segments, roles, weights, clearance) over the kernel
glyphh_nsm.py       the NSM default model: bare text in, as semantic primes
glyphh_lexicon.py   the lexicon reader; lexicon/ its two seeds (WordNet, Moby)
glyphh_postgres.py  PostgresStore: a model's precedents in Postgres (Ada Cloud)
test_*.py           the tests
bench/shortlist.py  shortlist recall and read latency on Postgres
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

One install carries everything: the kernel, the spec, the NSM model, the
lexicon reader and its seeds (`lexicon/`, installed as the data package
`glyphh_lexicon_data`), and the Postgres store; `pip install
'glyphh-kernel[postgres]'` adds psycopg 3 for it.

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
| `bundle(parts, weights=None)` | Majority vote. The result is similar to every input, and independent of the order the parts come in (ties are broken by a hash of the parts as a set). With `weights` (one per part, ≥ 0), each part's vote counts that much; 0 drops it. The result is still a glyph, so weighted bundles nest and weights apply at every level. Capacity is limited: past a few dozen parts, individual contributions fade. Keep the source data if you need it back exactly. |
| `roll(v, k)` | Rotate. Encodes order and position; `roll(v, -k)` inverts it. |
| `sim(a, b)` | Cosine in [−1, 1]. Random glyphs measure near 0. For encoded situations, sim tracks the fraction of shared attribute pairs, whichever attributes they are. Measured for 4-attribute situations: sharing 1, 2 or 3 gives 0.14, 0.28 or 0.44. For 2-attribute situations, sharing 1 gives 0.25. That holds even if the shared attributes are irrelevant to the decision. Set thresholds with this in mind. |

## Data, weights and fact trees

`encode(data, weights=None)` turns any JSON-shaped value into one glyph:

- an object is a weighted bundle of `bind(attr:key, child)`;
- an array is the bundle of its items (a set; put order in a `Strand`);
- a scalar is the symbol of its text (`3` and `"3"` match; `true` and
  `"True"` don't).

Nested objects and arrays are rolled once before they bind, so
`{"a": {"b": x}}` and `{"b": {"a": x}}` stay apart. A flat object of
strings encodes exactly as a `Space` situation always has.

Weights mirror the data. A number weighs a key. An object weighs
inside it, with its own weight under `"*"`. Unlisted keys weigh 1.

```python
weights = {"risk": 1.0, "team": 0.1, "region": 0,
           "plan": {"*": 2, "owner": 0}}
```

`explain(query, record, weights)` returns the fact tree, a `Fact` per
key:

- `score`: the exact weighted sim of that subtree;
- `weight`;
- `share`: its part of the parent's score; shares add up to it;
- `sim`: the glyph sim beside it, noise and all;
- `status`: `both`, `query_only` or `record_only`.

`root.score` is the weighted sim. A key on one side only scores 0 at
full weight; weigh it 0 if its absence shouldn't count.

Weights are rule 2 made explicit. Unweighted, two shared incidental
attributes look as close as two shared decisive ones:

```python
q          = {"goal": "move_data", "risk": "downtime",   "team": "infra",    "region": "eu"}
decisive   = {"goal": "move_data", "risk": "downtime",   "team": "platform", "region": "us"}
incidental = {"goal": "other",     "risk": "lock_table", "team": "infra",    "region": "eu"}
w = {"goal": 1, "risk": 1, "team": 0.1, "region": 0}

sim(encode(q), encode(decisive)), sim(encode(q), encode(incidental))   # 0.29, 0.29
explain(q, decisive, w).score, explain(q, incidental, w).score         # 0.95, 0.06
print(explain(q, decisive, w).to_text())
```
```
.  score 0.95 × w 1 → 0.95
  goal = "move_data"  score 1.00 × w 1 → 0.48
  region = "us" (query "eu")  score -0.02 × w 0 → 0.00
  risk = "downtime"  score 1.00 × w 1 → 0.48
  team = "platform" (query "infra")  score -0.01 × w 0.1 → 0.00
```

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
  - A situation is an object of attributes. Values may nest (see
    Data, weights and fact trees).
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
- Every read above, and `decide()`, takes `weights=`. With weights,
  reads rank and gate on the exact weighted sim (the fact-tree score)
  instead of the glyph sim. `min_sim` then means "the weighted share of
  attributes that must agree", and a weight can lift a match over the
  bar, not only lower it. Unweighted reads are unchanged. A weighted
  read scores every row: about 85 ms over 2,000 precedents, against
  3 ms for a glyph read.
- `facts(situation, events=None, weights=None, top=k, min_score=None)`
  → `[FactTree]`: every precedent scored exactly. The best `top` come
  back as fact trees, each with its outcome, glyph sim and citation
  (`id`, `author`, `ts`, `hash`). Events appear as the key `"~events"`.
  Ranked by score, then glyph sim, then newest. Each also carries
  `probability`: P(its outcome | situation).
- `probabilities(situation, events=None, weights=None)` → `{outcome:
  P}`. It's a softmax over the 25 nearest precedents' exact scores at
  temperature `tau`, summed per outcome.
- `calibrate(sample=100, weights=None)` fits `tau` so the probabilities
  mean what they say. It holds out each of the newest `sample`
  precedents in turn, scores it against the rest, and keeps the
  temperature with the least log-loss. The result is saved in the file
  and used on every later open. Until then `tau` is 0.12, the value fit
  on the Kubernetes test (`research/k8s-tickets`). Pass `tau=` to the
  `Space` to override both.
- `refresh()` — load rows other agents wrote to a shared file since
  it was opened.
- `merge(other_path)` — union another Space file by precedent id.
  Authors are preserved and the result is persisted.
- Files open in WAL mode, so several processes can share one. Call
  `close()` or use the Space as a context manager.
- `Space(path=..., readonly=True)` opens the file read-only: a
  follower's copy, or a store on a read-only disk. Every read works
  (`query`, `answers`, `evidence`, `matches`, `facts`,
  `probabilities`, `decide`, `meta`, `refresh`). Every write
  (`record`, `merge`, `calibrate`, `set_meta`, `rewrite`, and
  `reencode_store` on a file that can't be written) raises
  `ReadOnlyError` before the file is touched: `code` is
  `"E_READ_ONLY"`, `operation` names the write.
  - The file opens `mode=ro` with no `journal_mode` pragma and no
    schema made. Nothing is ever created beside it.
  - A WAL file that no writer holds open (no `-wal` and `-shm` beside
    it) is read immutable, since SQLite would otherwise create them,
    or fail in a read-only folder. `refresh()` reconnects, so it still
    sees rows written since.
  - A store from an older encoding is re-encoded in memory only. A
    path with no file yet reads as an empty store.
- **Stores outlive encodings.** Each file records the encoding it was
  written under (`ENCODING`, currently 3).
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
/plugin install ada@ada
```

The memory is one store, the same in every session and directory:
`$GLYPHH_HOME/ada`, else `~/.glyphh/ada`. Hooks read its SQLite files
directly; the MCP server opens it through the kernel.

## Models: the Glyphh spec

`glyphh_spec.py` gives a model a typed config. A spec is a cortex of
layers, each a cortex of segments, each a cortex of roles; every level has
a `similarity_weight` (its voice in the bundle above it) and a
`security_weight` (the clearance a reader needs to see it). Roles may be
`key_part`, numeric (`numeric_config`, a thermometer), text
(`text_encoding: "bag_of_words"`) or symbols and sets, and answer to
`lexicons`. `temporal_source` names the role that stamps a record's time.
`output.report` picks which paths the fact trees return.

```python
from glyphh_spec import Model, Spec
model = Model(Spec.from_json(spec_json))
model.record(data)                     # data in the spec's shape; outcome optional
model.facts(query, clearance=0.5)      # fact trees, cut to what the reader may see
```

A spec can also be taught by its own cases, and decide by cost:

```python
spec = Spec.from_json(spec_json).learned(cases)   # cases: [(data, outcome), ...]
model = Model(spec, k=15, min_sim=0.35)
for data, outcome in cases:
    model.record(data, outcome)
model.calibrate(sample=800)              # fits the temperature on the store's own graded record
model.probabilities(data)                # {outcome: P}, calibrated
model.decide(data)                       # {outcome, expected_cost, probabilities}: least expected cost
```

A model can learn from its own store instead: `model.learn()` fits the same
weights from the graded precedents it holds and keeps them with the store
(over the spec file's, until the next learn); `model.refresh()` is learn then
calibrate, and `Model(..., refresh_every=100)` does it on its own every so
many graded records, so the model follows its cases as they arrive.

### Several answers about one case: named outputs

A spec's `outputs` names several decisions about the same case, each with an
optional closed set of `values` and its own `costs` and `ask`. A case is
recorded once and carries every answer; each output learns, calibrates and
decides on its own (docs/multi-output.md):

```python
spec = Spec.from_json({..., "outputs": {
    "team":   {"values": ["billing", "login", "shipping"]},
    "urgent": {"values": ["yes", "no"], "costs": {"no": {"yes": 5}}, "ask": 0.6}}})
model = Model(spec, path="tickets.db")
rid = model.record(data, outcomes={"team": "login"})   # an answer outside `values`: E_OUTPUT_VALUE
model.grade(rid, "urgent", "yes")                      # an answer given later (None takes it away)
model.refresh()                                        # {output: {learned, tau}}, each its own
model.decide(data, output="team")                      # one output's decision
model.decide_all(data)                                 # {output: decision}, every output
```

Each output's learned weights are kept as `learned:<output>` and its
temperature as `tau:<output>`. The store holds each case once, as recorded;
an output whose learned word weights or interactions differ from the store's
reads it through an in-memory view (`Space.view`) built from those, kept
current as cases arrive. A spec without `outputs` has the one `default`
output, and every call reads as before; `outcome=` is the default output's.

`Model(spec, path=..., readonly=True)` opens the store read-only (see
`Space`). `query`, `facts`, `probabilities`, `decide` and the settings
(`model.settings`, `configure()` with no changes) read as ever. `record`,
`learn`, `calibrate`, `refresh` and `configure(...)` raise
`ReadOnlyError` (`E_READ_ONLY`) before anything is written. A store
restated on open is restated in memory only.

`learned` sets every role's `similarity_weight` to its information gain
about the outcome (scaled so the best weighs 1) and, per role, a
`value_weights` table: how far each value moves the outcome from the base
rate. Key parts, text roles and roles that carry sets are left alone. `output.costs`
(`{decided: {true: cost}}`, default 0 for the same outcome and 1 for a
different one) is the matrix `decide` minimises over the calibrated
probabilities. Every lever is a **setting**: `settings` in the spec (`k`, `min_sim`,
`word_weights`, `word_floor`, `interactions`, `max_interactions`, `rare`,
`calibrate_by`, `calibrate_sample`, `refresh_every`, `lexicon`, `word_pairs`, `max_word_pairs`, `word_evidence`,
`shortlist`, `exact_below`), each checked by name
and range, and `model.configure(k=20, word_floor=0.5)` changes them live,
kept with the store over the spec's; a learning lever moved relearns there
and then. `model.settings.to_json(all=True)` reads them. The settings are not
part of `spec_id`. `model.calibrate(by="cost")` fits the temperature on
what deciding by those costs would have cost over the held-out precedents,
rather than on log-loss. `output.ask` prices asking a person: set, `decide` answers
`ask: true` whenever every outcome's expected cost is above it (the band
where either answer is costly), with the best guess still named. `output.ask_below`
(and each named output's) is a confidence bar beside it: `decide` asks whenever the
most probable outcome's probability is under it. `model.record_many(cases)` records
up to any number of cases (`[{data, outcome?, outcomes?, ts?}]`) in one write, every
case checked before anything is written, and answers `{ids, added, replaced,
precedents}`; `model.forget(id)` deletes one case. The `lexicon` setting is the
model's own (`Space(lexicon=...)`): one process serves models with and without it.
Weighted queries score every precedent exactly as the fact
tree does, in one pass over per-leaf glyph tables (`test_learned.py`
proves the two equal). `learn` also weighs **words**: for a `bag_of_words` role it writes a
`value_weights` table: how far each word's presence moves some outcome from
its base rate, scaled from a floor of 0.35 (tells nothing) to 1 (the most
telling word); the floor is high because a bag's glyph is a majority vote,
and the many quiet words must still be heard beside the few loud ones. A situation then carries the bag as a
weighted set, `[[word, weight], ...]`, which the kernel bundles by weight, so
"stolen" outvotes "my" in every comparison, glyph, fact tree and fast path
alike; a model that learns new word weights rewrites its store. A list of
`[scalar, weight]` pairs with weights in 0..1 is a weighted set anywhere.

Every text role reads through the **lexicon** the kernel ships (`glyphh_lexicon.py`,
`lexicon/`): WordNet 3.0's 77,817 words with their synonyms, near words and
parts of speech, and the Moby list's 192,960 word forms with their classes.
A word's glyph is its own symbol tilted toward its neighbourhood (itself at
1, its synonyms sharing 0.9, its near words 0.6, its classes 0.3), so
"arrive" and "come" correlate and a word no seed knows is its symbol alone.
The `lexicon` setting turns it off. `word_pairs` (off by default) makes
`learn` also keep pairs of common words that tell more together than apart
("top" + "up"), at most `max_word_pairs`, carried in the bag as "a+b".

`learn` also keeps **evidence**: what each word says of each outcome (the
counts), held with the store, not in the spec. At query time a text's words
weigh on the vote by `word_evidence` (2 by default): each voter's weight is
scaled by exp(word_evidence × the mean pointwise mutual information of the
query's words with the voter's outcome), in `query`, `probabilities`,
`decide` and the calibration alike; the similarity bar, support and receipts
stay unbiased. This is the weight per word per outcome a classic text model
has and a similarity lacks.

`learn` also finds **interactions**: pairs of roles that tell more about the
outcome together than the better of them alone (a bad checking account with a
long loan). They go in the spec as `interactions: [{name, roles: [a, b],
similarity_weight, value_weights}]` and the spec reads them as one more layer,
`interactions.pairs.<name>`, whose value is the pair of the roles' values,
added to every situation by `situation()` and to the stored ones by
`Space.rewrite` when a model learns new pairs. Secured as the stricter of
the two roles. A key whose subtree weighs nothing on either side is
out of its parent's mean, not a zero in it: once learning has put a whole
segment to 0 it stops counting, instead of dragging every score down.

Specs are validated exactly: an unknown field or a value of the wrong kind
raises `SpecError` naming where. `glyphh_nsm.py` is the spec every
organization starts with: bare text taken down to the 64 NSM primes, plus
its words.

## Stores: a file, or Postgres

A Space keeps its precedents in a **store** (`glyphh_kernel.Store`, every
read and write the kernel makes of them). `Space(path=...)` is
`Space(store=SqliteStore(path))`, the one file it has always written.
`glyphh_postgres.PostgresStore` keeps a model's precedents in Postgres for
Ada Cloud: a schema per org, given at construction; a `precedents` table
partitioned by model, each partition with an HNSW index on its glyphs as
pgvector `bit(dim)` (`bit_hamming_ops`; a bipolar glyph is its bits, +1 as 1,
and sim = 1 − 2·hamming/dim, so 512 bytes a glyph at 4096); `outcomes`,
`meta` and `counts` keyed by model.

```python
from glyphh_postgres import PostgresStore
store = PostgresStore("postgresql://...", schema="ada_9f2c...", model="tickets")
model = Model(spec, store=store)        # holds no precedents in memory
model.record_many(cases)                # one transaction
model.decide(data)                      # shortlisted once the model is big
```

A model over a store that can **shortlist** holds nothing in memory: writes
go to the store, and `query`, `probabilities`, `facts` and `decide` ask it
for the `shortlist` (1,000) nearest glyphs to the query's weighted glyph by
Hamming distance, then re-rank them with the kernel's exact weighted score
(`Space.candidates`), once it holds `exact_below` (1,000) precedents; below
that, or with `shortlist: 0`, the store is read whole and the answer is the
exact one. A precedent's exact score does not depend on the others, so the
answer is exact whenever the shortlist holds the exact top. `learn`,
`calibrate` and `refresh` load the store whole (`Space.load()`).

What `bench/shortlist.py` measured (pgvector 0.8.7, HNSW m 64,
ef_construction 400; recall = the exact top 15 found in the shortlist;
`bench/results.txt` has every number): Banking77 (10,003) 100% from S 250,
every `decide` identical; credit (800) 99.6% at S 200; a synthetic ticket
store, queries that give every role, 100% at 100k and S 1,000, 97.6% at 1M
and S 1,000, 99.7% at 1M and S 2,000. **Queries that give few of the roles
the records carry shortlist badly at scale**: 99.5% at 100k (S 1,000), 33%
at 1M (81% even by an exact Hamming scan). A worker's read, shortlisted:
Banking77 60 ms p50 at S 1,000, the synthetic store 300 ms at 1M (most of
it the re-rank's Python, not the SQL); read whole, 50 ms at 800 precedents,
280 ms at 5,000, 3 s at 20,000.
`Space.merge` takes a store as well as a path: an rrotor
`precedents.sqlite` merges into Postgres as `SqliteStore(path,
readonly=True)`. `bench/shortlist.py` measures recall and latency.

## Tests

```bash
.venv/bin/python -m pytest -q
```

The same suite on PostgresStore: set `GLYPHH_TEST_POSTGRES` to a
connection string of a Postgres with pgvector, and every path a test opens
is a model in Postgres instead (tests about the SQLite file itself are
marked `sqlite_only` and skipped there):

```bash
GLYPHH_TEST_POSTGRES=postgresql://postgres:pw@localhost/postgres .venv/bin/python -m pytest -q
```

The research stacks carry their own tests; see
`research/agent-language/README.md`.

## License

Proprietary — glyphh.ai
