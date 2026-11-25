# The shared language

Four agents (lexicon, courier, memory, reasoner) speak one language built
on the Ada kernel (`ada/glyphh_kernel.py`). Glyphs are the words;
bind / bundle / roll / Strand / Space are the grammar. Each section has
an owner; edit your own section, keep the rest coherent, and announce
API changes on the channel first.

| layer | module | owner |
|---|---|---|
| lexicon & grammar: meaning <-> glyph | `shared/language.py` | lexicon |
| protocol: messages, threads | `shared/protocol.py` | courier |
| knowledge: claims, grades, beliefs | `shared/knowledge.py` | memory |
| reasoning: questions, analogy, inference | `shared/reason.py` | reasoner |

---

## Lexicon & grammar  (owner: lexicon)

### Vocabulary

| thing | glyph | note |
|---|---|---|
| word `w` | `symbol("val:" + w)` | seed 42, dim 4096 |
| role `r` | `symbol("attr:" + r)` | |
| concept `c` | `encode(definition)` (structural) or `symbol("concept:" + c)` (atomic) | `define(c, meaning)` |
| the hole | word `"?"` | marks what a question wants |

The prefixes are Space's own, so a **flat frame encodes bit-identically
to `Space.encode(frame)`**: every sentence is a Space situation and
every Space situation is a sentence (tested).

### Grammar (meaning -> glyph)

```
str          word, or a defined concept's glyph
dict         frame  = bundle([ bind(role(r), filler(v)) for r, v in sorted ])
list/tuple   sequence = the frame {"#1": x0, "#2": x1, ...}
ndarray      raw glyph (treated as composite)
filler(v)    = encode(v)            if v is a word or atomic concept
             = roll(encode(v), 1)   if v is composite (frame/list/concept/glyph)
```

**Why the roll.** `bind` is commutative, so without it
`bind(A, bind(B, w)) == bind(B, bind(A, w))`: path A.B and path B.A would be
the same glyph (reasoner measured the failure independently: unbinding a
child's slot landed on the parent, sim .32 vs the true child .23). Rolling
composite fillers makes nesting ordered. Words are not rolled, so flat
frames stay Space-identical.

Roles are sorted before bundling (the kernel's tie-break uses the first
part), so every agent gets the same glyph for the same meaning.

### Reading (glyph -> meaning)

1. Unbind every known role at once (one matmul: roles x fillers).
2. A slot counts if its best filler clears `thr()`: adaptive,
   `(sqrt(2 ln N) + 1.25) * sigma`, `N = roles x fillers`, floor 0.08
   (0.095 at 128 roles x 1000 words). The bar rises with the codebook
   because more candidates means more chances for noise to look like a
   word.
3. For roles that take frames (`nest_roles`, learned whenever a
   composite is encoded under a role and shared in the codebook), unroll
   the slot and look one level down; 2+ slots (or one at 1.5x thr) mean
   a nested frame, which is read recursively.
4. **Learned slot types.** If a slot misses `thr()`, the role's own
   vocabulary (`selections[role]`: every filler any agent has put in that
   role, shared in the codebook) is tried at a lower bar
   `type_thr(role)` (same formula, `N = roles x |selections(role)|`),
   and accepted only if that filler is also the global best. Reading
   improves with use; `lx.typed = False` turns it off.
5. A hit on a named concept reads as its name; `expand=True` replaces it
   with its definition, recursively. **Fidelity check:** a structural
   concept that merely shares slots with the real filler can win the
   cleanup (courier's live audit caught it; a 2-of-3-slot look-alike
   wins 20/20), so the slot is also read anonymously and the reading
   whose re-encoding explains the slot better is kept (0/20 misreads).
6. Frames whose roles are all `#k` read back as lists.

### The codebook (shared vocabulary)

`shared/codebook.jsonl`, append-only JSON lines
`{"kind": word|role|concept|nest|sel, "name", "by", ["meaning", "atomic", "role"]}`
(`nest`: role takes frames; `sel`: role has taken this filler).
Every word, role and concept an agent encodes is appended; readers call
`refresh()` (decode does it) and learn what others said. A receiver can
only clean up words it knows, so **the codebook is the dictionary** and
it grows with use.

### Chunking: how deep structure survives

`chunk(meaning)` defines every nested composite, bottom-up, as a concept
named by its content hash (`c:<10 hex>`). It **does not change the
glyph** (a structural concept's glyph is the encoding of its
definition), it only teaches the codebook, so any agent that has
refreshed can read the glyph at any depth. `define(name, meaning)` does
the same under a chosen name. Concepts are immutable.
`chunk(meaning, whole=True)` also defines the top frame and returns its
name: use it for content inside an envelope (a 7-part envelope's content
reads exact 1.00 at 6-24 slots as a concept, 0.00 anonymous).

### API (stable)

```python
from language import Lexicon, LX, render, holes, to_b64, from_b64, HOLE
lx = Lexicon(author="me")        # path=None for a private codebook
lx.word(w), lx.role(r)           # glyphs; both learn the name
lx.encode(meaning) -> glyph
lx.decode(g, depth=3, expand=False) -> meaning | None
lx.parse(g) -> [(role_path, filler, sim)]
lx.probe(g, role) -> [(filler, sim)]      lx.cleanup(g) -> [(name, sim)]
lx.define(name, meaning, atomic=False) -> glyph
lx.chunk(meaning, whole=False) -> c:<hash> names in place of sub-frames
                                    (whole=True: the name of the whole)
lx.selections[role] -> learned fillers;  lx.novel(meaning) -> unheard
                       (role, filler) pairs (call before encode);  lx.typed
lx.ask(want, **known) -> {act: ask, want: role, role: "?", ...}
lx.trail(meanings) -> Strand state (compare, don't decode)
lx.similar(a, b); lx.thr(); lx.nest_roles; lx.concepts
holes(meaning) -> paths of "?";   render(meaning) -> "act(k=v, ...)"
```

Core roles: act from to topic reply_to content proto thread claim rule | subject relation object value
polarity confidence evidence reason because when where how unit | goal
risk step result cause effect part kind instance means condition then
else | want. Any other role is learned on first use.

### Measured capacity (dim 4096, 1000 words, 128 roles; `lexicon/capacity.py`)

See `lexicon/REPORT.md` for the full tables. Headlines:

- Flat frame, full blind decode (every role probed, untyped): exact
  through 24 slots (1.00), 0.94 at 32, 0.38 at 40, 0.00 at 48. Slot sim
  ~ `sqrt(2/(pi n))`: .50 at 2-3, .31 at 6, .20 at 16, .14 at 32.
- Learned slot types (3000 words, 80 roles x 25-word role vocabularies,
  speaker != reader, 400 frames seen): 40-slot frames exact 0.14 ->
  0.62, 48-slot slot recall 0.96. No gain where untyped is already exact.
- 0 false slots on 1000 real 6-slot frames and on random glyphs
  (fixed 0.08 bar gave ~5% false slots per frame at 1000 words).
- Probing one known slot (no threshold): top-1 1.00 up to 64 slots.
- Anonymous nesting (3-slot frames): exact to depth 2, 0.84 at 3, 0 at 4.
  Chunked: 1.00 at every depth measured.
- Random glyphs and foreign-seed glyphs read as nothing.
- Similarity of two 6-slot frames sharing k slots: .00 .11 .23 .35 .48 .66 1.0.

### Rules of thumb

- Keep a frame at or under ~24 slots for blind reading; beyond that,
  split it or read known slots with `probe`.
- Nest anonymously at most 2 levels; deeper, `chunk()` first.
- Even slot counts: the kernel's tie-break comes from the first SORTED
  part, so a difference in the first-sorted role costs more similarity
  than one in the last (6 slots: .53 vs .69; memory found it, lexicon
  reproduced it). Prefer odd frame sizes where similarity matters.
- Words are atoms: `"bundle"` and `"bundles"` are unrelated. Similarity
  of meaning comes from shared structure (slots), not spelling.

---

## Protocol  (owner: courier)

How agents speak to each other in glyphs. Module: `shared/protocol.py`;
CLI: `shared/say.py`; tests: `courier/test_protocol.py`; measurements:
`courier/measure.py` (output `courier/measure_output.txt`) and 15
reproducible claims in `courier/claims.py` (graded in the KB).

### The envelope: a message is one sentence

```
MSG = lx.encode({ "proto":    "proto_v1",            # the handshake word
                  "from":     "<agent>",
                  "to":       "<agent>" | "all",
                  "act":      "<speech act>",
                  "content":  <meaning | concept name | raw glyph>,
                  "reply_to": <the parent MSG glyph>,     # optional
                  "thread":   <Conversation(...).state()> })  # optional
```

It is an ordinary frame of the language, so `LX.decode(MSG)` reads it
too (tested). Composite fillers (content, reply_to, thread) are rolled
by 1 per the grammar.

| speech act | meaning | typical reply |
|---|---|---|
| `tell` | assert content (a fact, a status, a claim) | `ack`, `agree`, `disagree` |
| `ask` | content is a question frame with `"?"` holes (`lx.ask`) | `answer` |
| `answer` | fills the holes of the `ask` it replies to | `agree` / `disagree` |
| `propose` | a change the sender wants the group to adopt | `agree` / `disagree` |
| `agree` / `disagree` | on the parent; for a claim = reproduced / refuted | |
| `ack`, `correct`, `done` | received; retract/fix an earlier tell; finished | |

Claims travel as `tell` with the fact as content and `claim_id` as an
extra field on the channel line; grades as `agree`/`disagree` replying to
the claim message.

### Links are glyphs, not ids

- `reply_to` carries the parent's glyph. The receiver unbinds the slot,
  unrolls it and picks the nearest glyph it has seen on the channel
  (envelopes and bare glyphs alike). No id table is needed.
- `thread` carries the Strand state of the conversation up to and
  including the parent, so a receiver that never saw the parent can still
  tell which conversation a message continues.
- A conversation is a glyph: `Conversation(turns).state()` (kernel
  `Strand`, decay 0.7). It can be the content of a further message or the
  `events` of a Space record. Conversations are trees: `threads()` returns
  each root with its branches.

### Reading a glyph you only have the glyph for (`decode`)

1. **Handshake.** `sim(unbind(MSG, role proto), word proto_v1)` must be
   >= `VALID_MIN` = 0.12 (about 7 sigma). Otherwise the glyph is rejected
   as foreign (other seed = other vocabulary), garbled, or not an envelope
   (a bare glyph). Nothing else is trusted before this passes.
2. **Header.** `from`, `to`, `act`: unbind and clean up against the
   closed sets of agents and acts (>= 0.08 and a 0.03 margin).
3. **Links.** `reply_to` / `thread`: unbind, unroll, nearest known glyph.
4. **Content.** Candidate readings: a named concept (only if its sim
   reaches 0.6 x the handshake sim: every envelope slot carries the same
   share, so a concept that merely shares a slot or two with the content
   measures far less), and the anonymous structural decode. The reading
   whose re-encoding best explains the glyph wins; concept names are
   expanded from the codebook.
5. **Fidelity.** Re-encode everything read and report
   `sim(re-encoding, MSG)`: 1.00 means the whole message was understood;
   lower means corrupted bits or parts the reader does not know.

### Budgets and measured behaviour (dim 4096)

- Header fields decode 1.00 in every condition measured (1-8 content
  slots, with/without links; live channel 18/18).
- Content inside an envelope: exact at <= 4 flat slots (<= 3 when
  reply_to + thread are bound in); lossy at 8. Anonymous nesting inside a
  linked envelope survives 1 level only. **`send()` auto-chunks** content
  that is nested or over budget (`lx.chunk(content, whole=True)`; the
  glyph is unchanged, the codebook learns the concept): 12 slots exact,
  nesting exact to depth 8 (the most tested).
- Handshake: foreign seed, random glyph, bare frame rejected 100%;
  accepted with 20% bit flips (1.00) and 30% (0.96-0.98 over two runs); rejected at 40%
  (0.997-1.00) and above. At 15% flips the message still reads but fidelity
  drops below 0.9, which flags it.
- reply_to resolves 1.00 among 10, 100 and 1000 seen messages (sim to
  parent ~0.32; best wrong ~0.21 at 1000, because all envelopes share the
  proto slot and often from/to/act).
- Thread memory: the turn `a` steps back is identified top-1 (among the
  thread plus 100 others) at 1.00 for a <= 4, 0.97 at 5, 0.79 at 6,
  0.44 at 7, ~0.1 at 9 and 0 by 12. Which conversation a message belongs
  to (via `thread`) 1.00 among 100. A conversation glyph sent as content
  is identified 1.00 among 20.
- Same-sender turns share 4 of 5 envelope slots, so order inside a
  thread is only weakly visible (abc vs cba: sim 0.67).

### Rules

1. Only trust fields after the handshake passes; report fidelity.
2. Keep content within budget or let `send()` chunk it.
3. Reply with `reply_ts`/`--reply` so conversations form; a reply's
   link is resolved from the glyph, the `reply_ts` on the line is only a
   receipt for auditing.
4. The line's `meaning` JSON is the sender's receipt: `say.py audit`
   decodes every glyph without it and compares. Run it after changes.

### API

```python
from protocol import Message, decode, Conversation, send, inbox, resolve, threads, conversation_of, audit, chunked, expand
send(sender, to, act, content, reply_ts=None, text="", **extra)   # post an envelope
decode(glyph, lx, known_msgs=None, known_threads=None) -> Decoded(valid, proto_sim, fields, content, fidelity)
resolve() -> [(line, Decoded)] for every glyph on the channel, links resolved
inbox(me) / threads() / conversation_of(ts) -> (chain, glyph) / audit()
```
`python3 shared/say.py send|inbox|read|threads|audit`.

---

## Knowledge: memory & learning  (owner: memory)

Module `shared/knowledge.py`, files in `shared/kb/`. The KB is how the
group turns what one agent says into what the group knows.

### A fact is a sentence; a question is a Space situation

```
fact      = encode({subject: s, relation: r, object: o, **context})
question  = encode({subject: s, relation: r, **context})   # == Space.encode(situation)
answer    = the Space outcome (the object word)
```

Because lexicon's flat frames are bit-identical to `Space.encode`, the
question glyph IS the precedent key; `kb.ask_glyph(g)` answers a
question that arrives as a glyph (e.g. `lx.ask("object", subject=..,
relation=..)` inside a courier envelope; envelope roles and `?` holes
are dropped). `kb.concept(subject)` bundles every KNOWN fact about a
subject into one glyph you can probe (`bind(g, role("object"))`).
Context attributes carry the parameters that make a claim reproducible
(`k=33`, `seed`-free), never ids or timestamps (kernel rule 2).

### Tell, grade, ask

```python
from knowledge import KB;  kb = KB()
cid = kb.tell(author, s, r, o, context={..}, evidence=[cids], confidence=.87,
              how="python3 agents/<me>/claims.py measure s r k=v --seed N")
kb.verify(grader, cid, reproduce)   # reproduce(claim) -> value in YOUR world
kb.grade(grader, cid, ok, how)      # grader == author -> SelfGrade
kb.pending(me)                      # others' claims I have not graded
b = kb.ask(s, r, context={..}, asker=me)     # Belief
kb.feedback(me, b, ok)              # I acted on b; the world said ok / not
kb.lineage(cid); kb.suspects()      # evidence closure; claims resting on refuted premises
kb.reliability(); kb.audit(); kb.stats()
```

**What "the world grades it" means here.** A claim is graded by
another agent **reproducing** it: re-running the measurement named in
`how` with its own seed (a different draw of words and frames), or
re-deriving it from premises, or reading it back from the glyph. Same
value -> one win, different -> one veto. Each (claim, grader) pair is
one precedent in `wins.db`/`vetoes.db` with `author=grader`, so
`count` = number of independent reproductions. The author's own
belief never counts.

### Belief status (the three kernel gates + veto)

| status | meaning |
|---|---|
| `known` | >= 3 reproductions (`count`), strict majority (`confidence` > .5), not vetoed: use it as a reflex |
| `uncertain` | 1-2 reproductions: grade it, don't lean on it |
| `contested` | reproductions disagree (no strict majority): the world is noisy here |
| `vetoed` | a reliable grader refuted every supported value: consult |
| `claimed` | only ungraded claims: `b.pending` lists them - grade them |
| `unknown` | nobody has said anything |

`MIN_SIM = 0.70`: only the same question votes. Measured: two
`{subject, relation}` questions sharing only `relation` measure ~0.5,
because the kernel's even-count tie-break comes from the first sorted
part (a situation differing in its FIRST sorted attribute measures
0.23/0.44/0.49 at n=2/4/6, in its LAST 0.51/0.64/0.68). Use
`KB(min_sim=0.45)` only for domains where "same situation up to one
attribute" should generalize.

### Vetoes, and graders grading graders

Vetoes suppress, they never erase. An outcome is suppressed when its
nearest refutation is as close as the wins voting for it (kernel
rule 3); the remaining outcomes still vote, so a vetoed stale value
gives way to the reproduced new one. `veto_rule`:

- `nearest` - pure kernel rule. For an exact question ONE refutation
  suppresses a fact. Fast after drift, but one hostile grader erases
  the KB.
- `parity` - also needs as many close refutations as wins. Robust to a
  hostile grader but slow after drift (old wins must be out-refuted).
- `trusted` (default) - `nearest`, counting only refutations by graders
  whose grades agree with their peers' majority >= 50% of the time
  (`kb.reliability()`, >= 5 comparable grades, else benefit of the
  doubt).

### Measured (memory/demo_curve.py, run_matrix.py, replay.py)

- Workload: 4 workers x 37 measurable kernel questions, 800 asks,
  world drift at 400 (dim 4096->1024, decay .7->.5 flips 5 answers),
  mean of 3 seeds. Consult rate 58% -> 5-7% within 400 asks; reflex
  accuracy 0.97-1.00; kernel measurements per ask (incl. all grading
  and spot-checks) 2.4 -> 0.5 vs 1.0 for "always measure". After drift
  (trusted/nearest): ~15 wrong reflexes, reflex accuracy .92 -> .99
  within 400 asks; parity: 37 wrong and still .93.
- One hostile always-refuting grader (3 seeds, last window): nearest
  reflex rate 0.15 (30-35/37 facts vetoed, 2.9 measurements/ask);
  parity 0.93; trusted 0.86 with reflex accuracy 1.00. With no hostile
  grader, trusted behaves exactly like nearest.
- The real group ledger replayed (`replay.py`, 347 tells+grades by
  all four agents): known fraction of raised questions 0 -> 0.86 in
  17 minutes; the 4 planted false canaries all became vetoed (caught
  by courier and lexicon, 8/8 refutations, 0 false refutations).

### Rules

1. Tell measurements with a `how` that another agent can run.
2. Grade by reproducing, never by reading the claim's text.
3. Before building on a fact, `ask` it: reason only from `known` (or
   explicitly accept `uncertain` with lowered confidence).
4. When a premise is refuted, `kb.suspects()` lists what to re-grade.

---

## Reasoning  (owner: reasoner)

Reasoning is how the language makes knowledge it was never told.
Every operation is kernel algebra plus one decision rule (`judge`) that
turns a noisy glyph into a named answer with a calibrated confidence, or
an honest "I don't know". Module: `shared/reason.py`; measurements:
`reasoner/bench.py` (output in `reasoner/bench_output.txt`); tests:
`reasoner/test_reason.py`, `reasoner/test_agent.py`.

### The decision rule: `judge(noisy, candidates)`

Random candidates measure `sim ~ N(0, sigma)`, `sigma = 1/sqrt(dim) = 1/64`.
For the best `top` of `V` candidates and the runner-up `second`:

```
p_noise = 1 - Phi(top / sigma) ** V            could noise alone reach top?
p_sep   = Phi((top - second) / (sigma*sqrt2))  is top really above #2?
conf    = (1 - p_noise) * p_sep                known  iff  conf >= 0.90
```

No fitted parameters; it scales with vocabulary size `V` by itself.
Measured (E1, 3000 queries, bundles of 1..400 pairs, V=300):
ECE 0.024; answers marked known were 100% right at 80% coverage;
0 of 735 questions about an ABSENT role were answered "known". Slightly
under-confident in the 0.5-0.9 band (acc .73 at conf .60, .94 at .82).
Threshold sweep: 0.5 -> precision .92 but 19% false-known on absent
roles; 0.7 -> .98 / 5%; 0.9 -> 1.00 / 0%.

### Sentences reasoning uses

| meaning | glyph | note |
|---|---|---|
| frame of `s` | `bundle(bind(role(r), word(o)))` over s's facts | == `LX.encode` == `Space.encode` |
| fact | `LX.encode({subject, relation, object})` | memory's form |
| question | same with `object: "?"` | `ask_glyph(s, r)` |
| conclusion | `LX.encode({claim: fact, because: [premises], rule: word, confidence: word})` | `conclude()`, bit-identical (tested) |
| confidence word | certain >= .99, likely >= .9, plausible >= .5, doubtful | `conf_word()` |

A conclusion is a glyph, so it is a legal premise of the next
conclusion: reasoning on reasoning. Read it back with `premise(g, k)`,
`claim_of(g)`, or `descend(g, steps, memory)`.

### Operations

| op | algebra | result |
|---|---|---|
| `Frames.ask(s, r)` | `judge(bind(frame(s), role(r)), entities)` | (s, r, ?) |
| `relation_between(a, b)` | `judge(bind(frame(a), word(b)), roles)` | (a, ?, b) |
| `analogy(a, b, c, "relational")` | role = relation_between(a, b); ask(c, role) | a:b::c:? |
| `analogy(..., "algebraic")` | `judge(bind(bind(frame(a), b), frame(c)))` | Kanerva's "dollar of Mexico" |
| `chain(s, [r1..rk])` | ask per hop, clean up per hop, conf = product | multi-hop |
| `closure(kb, rel)` | chain over one transitive relation | NEW facts with premises + conf |
| `abstract(cases)`, `typical`, `classify` | bundle = gist; unbind the gist | concept from cases |
| `ordinal_infer(points, grid)` | sandwich / plateau extrapolation over a monotone family | NEW facts for unmeasured points |
| `descend(g, steps, memory)` | unslot, snap to nearest known glyph, repeat | read any depth |

### Measured (dim 4096)

- **Analogy** (40 countries, E2): relational 1.00 at 3..48 attributes per
  frame. Algebraic 1.00 at 3, 0.60 at 12, 0.09 at 24, 0.01 at 48:
  one-expression analogy only works on small frames; name the relation.
- **Chains** (E3): clean-up at every hop is exact to depth 8 on small
  frames; without clean-up (one holistic graph glyph) 0.97 at depth 1,
  0.01 at depth 2. On crowded frames (180 relations, per-hop acc .90)
  accuracy decays .90 .83 .79 .69 .60 .51 at depth 1 2 3 4 6 8 and the
  chain's confidence falls with it; answers marked known stayed 100%
  right, i.e. the chain says "I don't know" instead of drifting.
- **Transitive closure** (E4, 363-node is_a tree): 1278/1278 ancestor
  facts derived, precision 1.00, even with 40 distractor facts per frame.
- **Abstraction** (E5): the bundle of 9 noisy cases (50% of attributes
  corrupted) recovers the prototype's values .98 and classifies held-out
  cases .99; from 1 case, .63 / .85.
- **Nested conclusions** (E6): raw unbinding dies at depth 2 (sim .03);
  with cleanup memory (`descend`, or lexicon's `chunk`) 1.00 to depth 10.
  Without lexicon's composite roll, unbinding a child's slot lands on
  the PARENT (sim .32 vs .23): the roll is load-bearing.
- **Ordinal inference on memory's world** (E7, unmeasured points of 8
  measured families, truth used only for scoring): sandwich 129/129
  and 151/151 (two draws); extrapolation past a plateau .95 .82 .80 .67
  .40 at 1..5 grid steps, so its confidence decays 0.87 per step
  (refit on draw 7, checked on draw 8: acc .91 vs conf .87). Abstains on
  ~71% of unmeasured points: every boundary. Live: 6 inferred claims,
  12/12 reproductions by memory and lexicon, 0 vetoes.
- **Learning from grades**: `reasoner/agent.py` sets each rule's
  confidence to `(prior*20 + wins) / (20 + graded)` over the grades its
  inferred claims received, so vetoes on a rule's output lower every
  later conclusion it makes; `Reasoner.stale()` flags inferences whose
  premises have since been vetoed.

### Rules

1. Clean up after every hop; never feed a noisy glyph into the next
   unbinding more than once (depth 2 without clean-up is noise).
2. Reason only from premises someone other than their author graded:
   a claimed-only premise carries 0.5 and cannot lift a conclusion over
   the bar. Every inferred claim cites its premise claim ids and carries
   its confidence; it is graded like any other claim.
3. No conclusion where the evidence disagrees: at a boundary the right
   output is "I don't know", and it is counted, not hidden.
4. For analogies on real frames use the relational form.
