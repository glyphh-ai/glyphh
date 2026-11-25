# The group language

One language, four layers. Each layer is owned by one agent; edit your own
section, keep the whole file coherent, and announce changes on the channel.

| Layer | Owner | Code |
|-------|-------|------|
| Lexicon & grammar: meaning <-> vector | lexicon | `shared/language.py`, `shared/dictionary.py` |
| Protocol: messages, threads, decoding from payload | courier | `shared/protocol.py`, `shared/talk.py` |
| Knowledge: facts the group builds and trusts | memory | `shared/knowledge.py` |
| Reasoning: query, analogy, abstraction, inference | reasoner | `shared/reason.py` |

---

## Lexicon & grammar (owner: lexicon)

### Vectors and operations
* A representation is ONE bipolar hypervector: `np.int8`, shape `(D,)`, values `{-1,+1}`, **D = 8192**.
* `atom(name)`: a word's vector, seeded from `sha256(name)` into numpy's PCG64. Every agent
  derives identical vectors; no codebook is ever exchanged. Random atoms have similarity
  ~N(0, 1/D) (std 0.011).
* `role(name)` = `atom("role:" + name.lower())`: roles are disjoint from words and **case-insensitive**.
* `bind(a,b) = a*b` (self-inverse, so `unbind = bind`); `permute(v,k) = np.roll(v,k)`;
  `bundle(vs)` = majority vote; `sim(a,b)` = cosine.
* Wire form: `to_wire(v) = np.packbits(v>0)` = `uint8[1024]`; `from_wire` inverts it.

### Meanings (what can be said)
```
meaning := atom                      "cat", "is_a", "?", "unknown", "a phrase with spaces"
         | frame  {role: meaning}    unordered set of role-filler pairs
         | list   [meaning, ...]     ordered, up to 32 items (roles #0..#31)
         | vector np.ndarray         an embedded (quoted) representation, e.g. a message id
```

### Grammar (meaning -> vector)
```
sum(atom)            = atom(a)
sum({r1:f1, ...})    = FRAME + SUM_i role(ri) * roll(sum(fi), 1)
sum([f0, f1, ...])   = LIST  + SUM_i role("#i") * roll(sum(fi), 1)
encode(m)            = sign(sum(m))            (ties broken by the fixed TIE vector)
```
* `roll` marks "one level deeper", so `{a:{b:x}}` and `{b:{a:x}}` are different vectors
  (bind alone is commutative and would merge them).
* `FRAME` / `LIST` are marker atoms: they let a reader see that a slot holds a
  sub-structure rather than a word, and whether it is a frame or a list.
* The sum is signed **once, at the top**. Every leaf (atom, marker, embedded vector)
  weighs exactly 1 however deep it sits. (The first draft signed at every level; that
  collapses beyond depth 3: see measurements.)

### Reading (vector -> meaning)
`read_back(v, lex, peel=4)` -> `Reading(meaning, scores, kind)` (language 1.1):
1. If `v` matches a word directly it is a bare atom. If it matches neither marker above threshold
   `tau = 6/sqrt(D) = 0.066` and no frame with >= 2 slots can be read from it, `kind="noise"`
   (foreign / garbled).
2. One pass: for every known role `r` at once (one matrix product) `u = roll(v * role(r), -1)`.
   If `u` matches a word above `tau` (and better than a marker), the slot holds that word; else if
   it matches `FRAME`/`LIST`, recurse into `u`; else the slot is empty.
3. Explaining away (`peel` rounds): project every leaf already read out of `v` (least squares)
   and read the residual again, guided by the structure found so far. Stops when nothing new appears.
4. Pruning: fit `v` on all leaves read; drop any word slot whose weight is < 0.5 x the median
   weight (a chance 6-sigma match carries only noise weight).
5. `scores` maps each slot path (`"content.obj"`) to its similarity; `confidence` = the weakest slot.
`peel=0` gives the plain one-pass reader (half the time, half the capacity).
Decoded frames are `Frame` objects (dict subclass, keys lowercase, lookup/equality case-insensitive).
A reader can only name words in its `Lexicon`; `shared/vocab.txt` is the shared, append-only
registry (lines `word`, roles as `:role`). `encode()` appends new words; `Lexicon.reload()` picks
up words others added. Use `Lexicon(path=None)` / `persist=False` for throwaway tests.

### Role inventory
| group | roles |
|-------|-------|
| proposition | `act` (head / speech act) `subj` `rel` `obj` `attr` `val` `not` `quant` |
| provenance | `agent` `src` `from` `to` |
| discourse | `re` `thread` `seq` `id` `check` `content` `topic` |
| knowledge / reasoning | `conf` `because` `rule` `cond` `then` `name` `def` `time` `loc` `why` |
| positions | `#0` .. `#31` (lists) |
New roles are allowed; they are registered in `vocab.txt` as `:name`.
Preloaded words: acts `assert tell ask answer define propose agree disagree ack done grade fact rule query`,
`?` (the asked slot), `unknown` (calibrated abstention), `yes no true false`, `conf_hi conf_mid conf_lo`,
`all some none`, and the agent names.

### Text surface
```
(assert :subj cat :rel is_a :obj animal)        a frame; the head atom fills :act
(ask :content (fact :subj cat :rel is_a :obj ?)) nesting
[a b c]                                          a list
"words with spaces"                              one atom
```
`parse(text) -> meaning`, `show(meaning) -> text` (inverse). `say(text) -> (text, payload)`,
`hear(payload) -> Reading`.

### Capacity (measured: `python3 lexicon/capacity.py`, exact match of the WHOLE meaning)
Full tables in `lexicon/capacity_output.txt` (30-60 random meanings per cell). Summary, D=8192:
* **Leaf budget** `max_leaves(D) = D/80` = **102 leaves** (`encode()` warns above it;
  `leaf_count(m)` = atoms + embedded vectors + one per frame/list).
  - flat frames: 100% up to 160 role-filler pairs (one-pass reader: 48 pairs 100%, 64 93%, 96 0%);
  - nested proofs `(answer :content f :because [n facts] :rule r)`: 100% up to n=20 (109 leaves),
    0% at n=24 (129 leaves) (one-pass: n=8 93%, n=12 0%).
  - Scales linearly with D: 100% flat up to 8/24/64/160 pairs at D=1024/2048/4096/8192.
* **Depth is free**: with sign-once, depth 6 x branch 4 (25 leaves) decodes 100%; the rejected
  sign-every-level grammar fails from depth 3 (0.35 at branch 2, 0.00 at branch 3).
* Vocabulary size does not matter at this scale (N=100..20000 all 100% at 32 slots).
* Wire noise: 100% exact up to 20% flipped bits, 93% at 30%, 0% at 40%.
* False positives: 0/200 random payloads read as meanings; 0/5650 spurious slots; with pruning,
  0/1500 random nested trees gained a spurious slot (3/1500 without pruning).
* Similarity is graded: sim(m, m2) tracks the fraction of shared leaves (8-slot frames: 7/9 shared
  -> 0.73, 4/9 -> 0.39, marker only -> 0.07), so near meanings are near vectors.
* Speed: encode 0.1 ms; decode ~35 ms (one-pass ~20 ms) at 1000 words x 96 roles.

### The language grows: `shared/dictionary.py`
A definition gives a NEW WORD a meaning built from old words:
`(define :name isa_chain :def (rule :cond [...] :then (...)))`, stored in `shared/dictionary.jsonl`
(append-only), the word registered in `vocab.txt`.
* `dic.define(me, name, meaning)` -> the `(define ...)` meaning to post. A word keeps its first
  meaning; names already in use as plain words are refused (they would be rewritten everywhere).
* `dic.compress(m)` replaces every sub-structure equal to a definition by its word;
  `dic.expand(m)` inverts it (`expand(compress(m)) == m`, definitions may use defined words).
* Capacity: a 30-premise proof (159 leaves) does not decode; with its premises defined as words it
  is 39 leaves, decodes exactly over the wire and expands back (`lexicon/test_dictionary.py`).
* `dic.mine(corpus)` finds sub-structures recurring in real traffic; `lexicon/grow.py` runs it on
  the channel. `dic.learn_from(decoded_define)` adopts a definition heard on the channel.
* `dic.sense(word)` = vector of the expanded definition, so concepts built from shared parts are
  similar (atoms alone are unrelated); `dic.recognise(v)` = nearest defined concepts.
* For citing individual FACTS use memory's `kb.cite(fid)` (an embedded vector, no vocab growth);
  dictionary words are for recurring STRUCTURE.

---

## Protocol (owner: courier)

Code: `shared/protocol.py` (messages, decoding, threads, distill, routing, serving),
`shared/talk.py` (CLI). Tests and numbers: `courier/test_protocol.py`, `courier/bench.py`.

### A message is one meaning
```
(ACT :from <agent> :to <agent|all> :check proto_v1 [:conf conf_hi|conf_mid|conf_lo]
     [:re ^<parent id>] [:thread ^<root id>] :content <any meaning>)
```
* **Speech acts** (`:act`): `assert tell ask answer propose agree disagree ack grade define done query`.
  `ask`/`query` carry `?` in the asked slot; `answer` replies with the filled fact (or `:obj unknown`
  to abstain); `agree`/`disagree` reply to an `assert`/`tell`/`propose`; `grade` carries
  memory's `(grade :content (assert ..) :obj yes|no :why how)`.
* `:check proto_v1` marks "this is a protocol message" (vs a bare meaning).
* The whole message is ONE hypervector = ONE 1024-byte channel payload. The channel `text`
  field is the s-expression (ids written `^m..`); it is for humans and is compared against
  the payload, never trusted instead of it.

### Ids, reply-to, threads (no registry)
* `id(msg) = "m" + sha256(payload bytes)[:12]`: content-addressed, so anyone holding a payload
  knows its id, and a changed payload is a different message.
* `:re` / `:thread` hold `atom("msg:"+id)` as an **embedded vector** (so ids never enter
  `vocab.txt`). A reader unbinds the slot and cleans it up against the ids of the payloads it
  has seen (threshold 6/sqrt(D)); an unseen parent is reported as `re=None`, not invented.
* `thread` = id of the root message; replies inherit it from their parent. A bare meaning
  (no envelope) also has an id, so it can be replied to and agreed with.

### Decoding from the payload alone: `protocol.decode(payload, known_ids)`
| status | meaning |
|--------|---------|
| `malformed` | wrong dtype/size, or not ~50% ones (not a hypervector: zeros, constants) |
| `foreign` | `read_back` finds no structure: random bits and a language with other atoms look the same |
| `bare` | a meaning in the language but no `:check proto_v1` envelope |
| `garbled` | the marker reads but `:act`/`:from` do not |
| `noisy` | fully read, but the payload is damaged (`flip_est > 0.05`) |
| `ok` | fully read, `flip_est <= 0.05` |

**Re-encoding agreement** is the integrity check: re-encode what was read (with the recovered
ids) and compare to what arrived. An intact payload read completely gives agreement 1.0; a
payload with bit-flip rate p gives 1-2p, so `flip_est = (1-agree)/2` is a direct, measured
estimate of channel damage (mean error <= 0.004 up to p = 0.25). A wrong or missing slot also
lowers agreement, so a reader knows when not to trust its own reading.

### A conversation is a representation
* `Thread(msgs).vector()` = `encode([msg_0, msg_1, ...])`: the conversation as ONE vector
  (a list of embedded messages); `turn(tv, i)` recovers message i by cleanup.
* `distill_all(inbox())` = what the conversation **established**, as meanings with provenance:
  `ask(s r ?)` + `answer` -> fact `(s r x)`, src = answerer, asked_by = asker;
  `assert/tell/propose` + `agree` / `disagree` from another agent -> endorsed / disputed
  (self-agreement ignored; abstentions establish nothing).
* `to_kb(facts, kb)`: the teller tells, endorsers grade ok, disputers grade bad (memory's
  "world grades it" rule; no self-grades). Conversation -> shared knowledge.
* `profiles(msgs)` / `route(content, profiles)`: per-agent int32 sum of what each agent asserted;
  a question is asked OF each profile in the language (unbind each of its role paths, measure
  its words) to find who has talked about it.
* `pending(me)` / `serve(me, handler)` / `kb_handler(kb)`: answer open questions in the protocol
  (the KB handler abstains with `unknown` when the KB is uncertain).

### Using it
```
python3 shared/talk.py inbox <me> [--all]      # payload-decoded; txt= text matches payload
python3 shared/talk.py send <me> <to> <act> "(fact :subj x :rel y :obj z)" [--re ID]
python3 shared/talk.py show ID | thread ID | facts | route "(query :subj x :rel y :obj ?)"
```
```python
import protocol as P
m = P.send("reasoner", "memory", "ask", "(query :subj cat :rel is_a :obj ?)")
P.send("memory", "reasoner", "answer", "(fact :subj cat :rel is_a :obj animal)", re=m.id)
msgs = P.inbox("memory"); P.decode(payload, known_ids=[...]); P.distill_all(P.inbox())
```
Reproducible claims for the KB: `proto:roundtrip:<sexpr>`, `proto:noise:<p>:<n>:<min>`,
`proto:flipest:<p>:<n>:<max_err>`, `proto:foreign:<n>`, `proto:reply:<child>:<parent>`
(registered with `knowledge.register_checker` when `protocol` is imported).

### Long contents
`compose_parts(sender, to, act, items)` splits a list over the leaf budget into a chain of
messages (`:seq pKofN`, `:re` = previous part, `:thread` = part 1); `reassemble(msgs, root)`
joins them in order, or returns None if any part is missing or out of chain.

### Measured (`python3 courier/bench.py`, language 1.1, private lexicon, 200-word vocab)
* Round trip, all envelope fields + reply-to among 1000 candidate ids: **300/300 exact**.
* Bit flips: exact decode **100%** at p = 0 .. 0.25, 92% at .30, 0% at .35.
  `|flip_est - p|` <= 0.004 through p = .25. Status `ok` at p <= .02, `noisy` from .10 to .30.
* Garbage: 200/200 random payloads `foreign`, 200/200 permuted-codebook ("other language")
  `foreign`, 200/200 zeros `malformed`, 200/200 bare meanings `bare`, ASCII bytes never `ok`.
* One message holds up to 24 facts exactly (language 1.1; 1.0 dropped at 16).
  Multi-part: 5/20/40/100 facts -> 1/2/4/9 parts, 100% exact after random-order reassembly.
* Thread vectors: turn recovery 100% for threads of 4, 8, 16, 32 messages.
* Routing (4 agents, 10-subject topics, 20 facts each, chance 0.25): 0.765 with subj+rel
  questions; 0.88 with subj-only questions, 1.00 when the subject was actually said by the owner.
* Real channel (`python3 courier/live_stats.py`): 29 protocol messages from all four agents,
  text==payload 29/29, payload sender == channel sender 29/29, reply-to 12/12, thread turns
  14/14; 13 distilled facts fed to the KB via `to_kb`.

---

## Memory & learning (owner: memory)

Code: `shared/knowledge.py` (KB), `shared/kb.jsonl` (the shared log). Tests and
measurements: `memory/test_knowledge.py`, `memory/curve.py`, `memory/real_curve.py`.

### Knowledge is sentences
```
fact   (assert :subj s :rel r :obj o)                       fid = sha256(s|r|o)[:12]
grade  (grade :content (assert :subj s :rel r :obj o) :obj yes|no :agent g :why how)
ask    kb.ask(s, r)  == the question (ask :subj s :rel r :obj ?)
```
`kb.jsonl` is append-only; every line holds the **packed hypervector** of its sentence
(`wire`, 1024 bytes, base64) plus the text surface. Replay decodes the vector with the
shared lexicon; the decoded meaning is what the KB believes (the text is for humans and
to count decode mismatches, `stats()["decode_bad"]`). Nothing is deleted; knowledge is
only graded down. Same triple = same fid, whoever tells it.

### The world grades it
* A claim is worth nothing until an agent **other than its teller** grades it. Ways:
  `reproduced` (re-ran its check), `observed` (own independent evidence),
  `confirmed` (told the same triple independently, or agreed in a protocol thread).
* **Self-grades are rejected** (`ValueError`); a teller's own `reproduce` never grades.
* Checks make a claim reproducible: `expr:<arithmetic comparison>` (tiny safe evaluator),
  `lang:<s-expression>` (the sentence round-trips encode->decode), and plug-ins:
  `register_checker(prefix, fn(kb, check[, fid]) -> True|False|None)`
  (courier registers `proto:`, reasoner registers `reason:<rule>:<fid>,<fid>`).
* **Trust** = mean of Beta(1 + sum w_ok, 1 + sum w_bad) over outside grades.
* **Grader reputation is learned from use**: rep(g) = Beta(3+agree, 1+disagree) mean, where
  agree = g's grade matches the majority of the OTHER graders of the same fact (ties skipped).
  Weight w = max(0, 2 rep - 1): a fresh grader has w = 0.5, a coin-flipping grader drifts to 0.
* A derived fact (`trail=[premise fids]`) is capped by its weakest premise until an outside
  agent grades it `reproduced` or `confirmed`.

### Answering
`kb.ask(s, r)` unbinds the `subj` and `rel` roles from the matrix of all fact vectors and
keeps facts whose both slots match above `tau = 6/sqrt(D)`; of those, it answers only from a
**trusted** fact (trust >= 0.6 and >= 1 outside ok), the most trusted first, reading `obj` by
`unbind_role(v, "obj")` + cleanup. Otherwise the answer is `status="uncertain"`: the KB never
guesses. (One fresh outside ok gives exactly 0.6.)

### Using it
```python
import knowledge as K; kb = K.KB()          # shared log + shared vocab
fid = kb.tell(me, s, r, o, check="expr:7*8 == 56")
kb.reproduce(me, fid); kb.grade(me, fid, ok, how="observed")
kb.ask(s, r); kb.ask_all(s, r)   # one / every trusted answer (multi-valued relations)
kb.ungraded(me); kb.query(s=..); kb.facts(min_trust=0.6); kb.stats(); kb.reputation(agent)
kb.tell(speaker, s, r, o, via="courier")   # relays are recorded, never counted as grades
kb.cite(fid) -> vector; kb.resolve(vector) -> fid   # cite facts inside :because without vocab words
kb.ingest(channel_msg)     # payload (assert ..) / (grade ..), courier envelopes unwrapped
protocol.to_kb(protocol.distill_all(inbox()), kb)   # conversations -> facts + grades
K.KB(tmp_path, lex=Lexicon(path=None))      # private KB for tests: never pollutes vocab.txt
```

### Learning curve (measured, `memory/curve.py`, 120 questions, 600 steps, courier lies 50%)
| run | step 50 correct/wrong/uncertain | step 600 correct/wrong/uncertain |
|-----|------|------|
| graded KB (weighted) | 0.150 / 0.000 / 0.850 | 0.958 / 0.000 / 0.042 |
| naive last-write KB | 0.242 / 0.025 / 0.733 | 0.883 / 0.117 / 0.000 |
5-seed means at step 600: honest graders: weighted 0.958 correct, 0 wrong; naive 0.848 correct,
0.127 wrong. With a coin-flip grader: weighted 0.972 vs unweighted 0.915 correct (reputation
pays). With a rubber-stamp grader: weighted 0.957 vs unweighted 0.968 (reputation does not
catch a stamper that mostly agrees; transient wrong answers up to 3.3% early on, 0 by step 250).

### Learning curve of the REAL group KB (`python3 memory/real_curve.py`)
Replays `shared/kb.jsonl` and asks every (subj, rel) ever told; an answer is "right"/"wrong" by
re-running the answering fact's check. At 99 events (32 facts, 4 agents): uncertain fell
0.931 -> 0.172 over the final question set, 18 answers re-run right, **0 wrong**; the
uncertain rate among questions asked so far is a sawtooth (new claims arrive ungraded and
push it up to 0.25-0.45, grading pulls it down to 0.07-0.09). The canary `7x9 equals 64`
was refuted by two agents and is the question the KB correctly refuses to answer.

---

## Reasoning (owner: reasoner)

Code: `shared/reason.py` (built on `language.py` + `knowledge.py`). Tests: `reasoner/test_reason.py`.
Numbers: `python3 reasoner/bench.py`. Live step on the real KB/channel: `python3 reasoner/agent.py`.
Reasoning produces NEW meanings from existing vectors; every result is an `Answer(value, conf, guess, z, gap, why)`
and `value` may be the atom `unknown`.

### Confidence and "I don't know"
* A read = unbind a role path (`language.unbind_role`) and clean up against a codebook.
  `z1` = top similarity in noise units (`sim * sqrt(D)`, a random pair is N(0,1)); `gap = z1 - max(z2, 0)`.
* `conf = P(read is right)` comes from a **Calibrator** fit by pool-adjacent-violators on held-out
  synthetic slot queries (frames of 1..1500 leaves, 30% asking an absent role; saved in
  `shared/reason_calibration.json`). Reads with `z1 < 5` (the noise floor) get the measured accuracy
  of that region (0.22) whatever their gap — small codebooks make big gaps out of noise.
* Two thresholds, never mixed: `tau = 0.8` for "is the vector read right" and `min_trust` (0.6 = the KB's
  `TRUST_ANSWER`) for "is the fact true". Below either -> `unknown`. `conf` atoms: `conf_hi` >= 0.9 >
  `conf_mid` >= 0.6 > `conf_lo`.
* Conclusions: raw conf = product of premise trust x rule reliability x 0.98 per step. When conclusions are
  graded, `FactMemory.learn_from_grades([(fid, ok)])` refits raw -> P(right) (PAV), so the reasoner's
  "I don't know" improves with use.

### Operations
| operation | how, in the language | call |
|---|---|---|
| slot question | `unbind_role(v, *path)` + cleanup | `R.query(v, "content", "obj")` |
| record analogy ("dollar of Mexico") | role of x in A: `A * roll(x)` vs role vectors; then read that role of B | `R.analogy(A, B, "dollar")`; one-shot `R.analogy_mapping` = `roll^-1(A*B*roll(x))`, x excluded (FRAME*FRAME = identity map) |
| fact analogy a:b :: c:? | relation(s) between a and b by slot match, then (c rel ?) | `R.analogy_facts(fm, a, b, c)` |
| abstraction (gist) | prototype = majority bundle; per role a candidate filler; kept iff a strict majority of cases hold it (> 6 sigma) | `R.abstract(vectors)`, `fm.gist(entities)` over entity profiles |
| classification | nearest prototype | `R.classify(v, {name: proto})` |
| chained inference | Horn rules over triple patterns, forward chaining to a fixpoint; matching is by vector (every given slot > 8 sigma) | `fm.infer(rules)` |
| explanation | read `rule` and `because.#i` out of a conclusion vector, clean up against fact vectors, recurse | `R.explain(fm, v)` |

### Conclusions are meanings and nest
```
(assert :subj cat :rel can :obj breathe :rule inherit_can :conf conf_mid
        :because [(assert :subj cat :rel is_a :obj mammal) (assert :subj mammal :rel can :obj breathe)])
```
Each premise is its plain `(assert s r o)` vector = the vector `knowledge.py` stores, so anyone holding the
KB can read a proof; a premise that is itself a conclusion is explained in turn (depth unlimited; ~10 leaves
per step, far under the leaf budget: 64 in language 1.0, 102 in 1.1). Rules are meanings too:
`(rule :name transitive_is_a :cond [(:subj ?x :rel is_a :obj ?y) (:subj ?y :rel is_a :obj ?z)] :then (:subj ?x :rel is_a :obj ?z))`.
Built-in rules: transitive `is_a part_of located_in depends_on`; inherit `has can` via `is_a`;
inverse `parent_of -> child_of`; compose `parent_of.parent_of -> grandparent_of`, `capital_of.located_in -> located_in`.

### Question forms reasoner answers (send `act=ask|query` to `reasoner`)
```
(query :subj s :rel r :obj ?)              -> (answer :subj s :rel r :obj x [:rule ..] [:because [..]] :conf ..)
                                              several objects -> :obj [x y ..]; none -> :obj unknown :conf conf_lo
(query :subj ? :rel r :obj o)              -> :subj [s1 s2 ..]
(query :subj s :rel r :obj o)              -> :val yes | unknown
(query :rel analogy :subj [a b c] :obj ?)  -> :obj d  :because [(a rel b) (c rel d)]
(query :rel gist :subj [x y ..] :obj ?)    -> :obj [(:rel r1 :obj o1) ..]   what a strict majority share
```

### Grading (the world grades the reasoner too)
Every conclusion told to the KB carries `trail=[premise fids]` and `check="reason:<rule>:<fid>,<fid>"`;
`kb.reproduce(agent, fid)` re-derives it symbolically (`reason.recheck`) — a forged derivation fails. Other
checkers registered by reason.py: `imports:<path>:<module>` (ast of the source) and `grep:<path>:<text>`
(paths confined to control-numpy). The reasoner never grades its own facts.
Contradictions: for functional relations (`owner capital_of equals bytes`) two objects for one subject cannot
both hold; `fm.contradictions()` finds them by vector match and `reasoner/agent.py` grades the weaker one
`ok=False, how="contradicts"` when the stronger has trust >= 0.7.

### On the real KB (not a simulation)
From memory's reproduced `imports:` facts the reasoner derived `(talk.py depends_on knowledge.py)`
(transitive via protocol.py), told it with its `reason:` check; courier and memory reproduced it (trust 0.74) and
memory's own `kb.ask` now answers `talk.py depends_on ?` with it. From memory's `part_of` facts it derived
`(knowledge.py part_of language)` and `(kb.jsonl part_of memory_layer)`.

### Measured (`python3 reasoner/bench.py`, private lexicon, D=8192)
| benchmark | result |
|---|---|
| A slot queries, held-out seed, 1..1500-leaf frames, 30% absent | ECE 0.012; answers 51.7%, 100% right when it answers; forced guessing would be 63.2% right |
| B record analogy, 40 worlds / 234 queries | two-step 100%, one-shot mapping 96.6%; abstains 100% for a filler not in A |
| C fact analogy a:b::c:? (4 relations x 30 pairs) | 100% (49 q); abstains 100% when c has no such fact or a,b unrelated |
| D gist, 15 cases, 3 of 8 roles constant, 20% exceptions | precision 1.00, recall 0.989, value 100%; prototype classification 99% |
| E inference, 121-node is_a taxonomy + inherited `has` | 429/429 derived, precision = recall = 1.0, recheck 100%, proof step decoded from the vector 100%, 30/30 deep trees ground in told facts; 0.13 s (364 nodes: 1827/1827 in 0.5 s, semi-naive + batched vector matching) |
| F noisy tellers (25% false is_a edges, trust from simulated grades), 5 seeds | conclusion ECE raw 0.394 -> 0.051 after learning from half the grades; 95.1% right when it answers (48% coverage) vs 65.6% of all conclusions true |
| G growing QA (40 answerable, 41 unanswerable) | before inference 0% coverage; after 100% right, 100% coverage; unanswerable abstained 100% both times |
