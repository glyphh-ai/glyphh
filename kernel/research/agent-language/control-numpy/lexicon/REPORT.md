# lexicon: REPORT

> Saved verbatim by the orchestrator from the agent's hand-back. The harness does not let subagents write report files.

## What I built

My part was the vocabulary and grammar, the layer everything else sits on: how a meaning becomes one numpy vector and how that vector is read back into a meaning. I built it from numpy and the Python standard library only.

| File | What it is |
|------|------------|
| `shared/language.py` (v1.1) | The group language: vectors, grammar, reader, wire form, text surface, vocabulary registry |
| `shared/dictionary.py` | How the language grows: new words defined from old ones (define / compress / expand / mine / sense / recognise) |
| `shared/LANGUAGE.md` | The header table, and the "Lexicon & grammar" and "The language grows" sections |
| `lexicon/test_language.py` | 18 unittests |
| `lexicon/test_dictionary.py` | 9 unittests |
| `lexicon/capacity.py`, `capacity_output.txt`, `capacity.json` | Capacity measurements |
| `lexicon/grow.py` | Mines recurring structures from the real channel and adopts them as words (`--adopt`) |

### The language
- **Vectors.** Each representation is one bipolar hypervector: `int8` with values ±1 and length D = 8192.
- **Words.** `atom(name)` gets its vector from sha256(name) fed into numpy's random generator. All four agents therefore get the same vector for a word without ever exchanging a codebook.
- **Roles.** Roles are a separate set of vectors (`role:<name>`) and are case-insensitive.
- **Operations.**
  - bind = elementwise multiply, which is its own inverse;
  - permute = `np.roll`;
  - bundle = majority vote;
  - sim = cosine similarity.
- **Meanings.** A meaning is one of four things:
  - an atom (a word);
  - a frame `{role: meaning}`;
  - a list `[meaning, …]` of up to 32 items;
  - an embedded vector (courier uses these for message ids, memory for fact citations).
- **Grammar.**
  - `sum(frame) = FRAME + Σ role(r) * roll(sum(filler), 1)`, and the same for lists using `LIST` and `#i` roles.
  - `encode = sign(sum)`, signed only once, at the top.
  - The `roll` marks nesting depth, so `{a:{b:x}}` and `{b:{a:x}}` are different vectors.
  - The FRAME and LIST marker atoms tell the reader whether a slot holds a word or a structure.
- **Reader.** `read_back(v)` returns `Reading(meaning, scores per slot path, kind)`, where kind is frame, list, atom or noise.
  - One matrix product unbinds all roles at once.
  - It keeps words above a threshold of 6/√D, and recurses where it finds a marker.
  - In v1.1 it then "peels": it removes (by least squares) everything already read and reads the remainder again.
  - Finally it "prunes": it drops any slot whose weight is less than half the median weight.
- **Wire form.** `np.packbits` gives 1024 bytes of `uint8`.
- **Text form.** S-expressions, e.g. `(assert :subj cat :rel is_a :obj animal)`; a list is written `[a b]`, and quoted text is one atom. `parse` and `show` are inverses.
- **Role inventory.**
  - Content: act, subj, rel, obj, attr, val, not, quant.
  - Who and where from: agent, src, from, to.
  - Conversation: re, thread, seq, id, check, content, topic.
  - Reasoning: conf, because, rule, cond, then, name, def, time, loc, why.
  - List positions: #0 to #31.
- **Preloaded words.** The speech acts, `?`, `unknown`, `yes` and `no`, the `conf_*` confidence levels, and the agent names.
- **Shared vocabulary.** `shared/vocab.txt` is an append-only file of known words (`:role` lines for roles). Any agent can read words that another agent wrote there.

### How the others build on it
- **courier (`protocol.py`):** every message is one meaning, sent as one 1024-byte payload.
- **memory (`knowledge.py`):** each fact is stored as its wire vector, and replaying the store means decoding those vectors.
- **reasoner (`reason.py`):** proofs are nested `:because` meanings.

All three suites pass unchanged on v1.1: courier 18/18, memory 25/25, reasoner 19/19, and mine 27/27, so 89 tests in total.

## Measured results (`python3 lexicon/capacity.py`, exact match of the whole meaning, D = 8192 unless stated)

**Leaf budget.** "Leaves" are the words, embedded vectors and markers a meaning contains. The budget is D/80 = 102 leaves, and `encode()` warns above it.

**Flat frames (role-filler pairs in one frame).**

| D | One-pass reader | v1.1 reader (with peeling) |
|---|---|---|
| 1024 | 100% at 8 pairs | 100% at 16 pairs |
| 2048 | 97% at 16 pairs | 100% at 32 pairs |
| 4096 | 93% at 32 pairs | 100% at 64 pairs |
| 8192 | 93% at 64 pairs, 0% at 96 | 100% at 160 pairs |

**Nested proofs** `(answer :content f :because [n facts] :rule r)`.

| Premises | Leaves | One-pass reader | v1.1 reader |
|---|---|---|---|
| 8 | 49 | 93% | 100% |
| 12 | 69 | 0% | 100% |
| 20 | 109 | 0% | 100% |
| 24 | 129 | 0% | 0% |

**Depth.**
- Signing once: depth 6 with 4 branches per level (25 leaves) decodes 100%.
- My first draft signed at every level. It fell to 0.35 at depth 3 with 2 branches per level, and to 0.00 at depth 3 with 3 branches.

**Vocabulary size.** 100 to 20,000 words: 100% at 32 slots.

**Bit flips on the wire.** 100% exact up to 20% of bits flipped, 93% at 30%, 0% at 40%.

**False positives.**
- 0 of 200 random payloads were read as meanings.
- 0 spurious slots in 5,650 checks of empty roles.
- Pruning took spurious slots on random nested trees from 3 in 1,500 down to 0 in 1,500.

**Similarity is graded.** Similarity between two meanings follows the fraction of leaves they share: 7/9 shared gives 0.73, 4/9 gives 0.39, and marker only gives 0.07.

**Speed.** Encoding takes 0.1 ms. Decoding takes about 35 ms, or about 20 ms with the one-pass reader.

**Dictionary.**
- A 30-premise proof (159 leaves) does not decode. With its premises defined as words it becomes 39 leaves, decodes exactly over the wire, and expands back to the original.
- Defined concepts built from shared parts are similar to each other: cat_mammal vs dog_mammal > 0.5, while their bare atoms are unrelated (about 0).

**Real channel.**
- All 46 of 46 payloads decode as frames using my reader alone.
- The miner found 2 structures that recur across messages. Adopting them made the traffic 3.1% shorter (510 → 494 leaves), and `expand(compress(m)) == m` held for every message.
- The two definitions were posted as `(define …)` payloads, and a fresh reader decoded and learned both.

## What I said to the others and what came of it
- **Plan and API.** I posted the plan, then v1.0 with its full API and a payload for others to decode. Courier decoded it and replied in the protocol with an `answer` and an `agree`.
- **Uppercase roles.** `knowledge.py` and `reason.py` used uppercase roles (`SUBJ`). I made roles case-insensitive and made decoded frames accept either case, instead of asking them to rewrite. Courier agreed in the protocol, and memory later fixed a case-sensitivity bug in its own `lang:` checker.
- **Shared-vocabulary hygiene.** Test words (thing0…thing39, hue*, …) had leaked into `vocab.txt`. I asked everyone to use `Lexicon(path=None)` for tests.
- **Dictionary.** Memory chose to cite facts with embedded vectors (`kb.cite`) rather than a vocabulary word per fact, to avoid adding decoding noise for everyone. That was right; I documented the split (dictionary words are for recurring structure, `kb.cite` for individual facts).
- **v1.1 reader.** I announced the peeling reader with its numbers and re-ran all three of the others' suites against it.
- **Grading and facts.**
  - I reproduced 30 of the knowledge base's facts plus memory's seed facts. Memory's deliberate test fact "7x9 = 64" came out false, as did its mistyped README check; everything else was true, including reasoner's two derived facts.
  - I answered reasoner's question "language.py part_of ?" in the protocol.
  - I told 5 facts with checks attached: part_of links for the lexicon layer, a 99-leaf proof that round-trips, and the budget of 102.
- I posted a final `done` message on the channel.

## What doesn't work / limits
- **Cliff past the budget.** Past about 110 nested leaves, decoding drops to 0% almost at once. Nested structures hit that cliff earlier than flat ones, because the FRAME markers must be found before the reader can recurse.
- **Unknown words.** A reader can only name words that are in its vocabulary. Anything else is silently left out, and only a lower confidence or a slot that should be there hints at it.
- **Frames have no order.** Role order inside a frame is not stored, and a role can appear only once per frame.
- **Little compression on real traffic (3.1%).** The dictionary only replaces a whole sub-structure with a word, and our messages rarely repeat whole sub-frames. The repeated part is courier's envelope (check, from, to), but it is only part of a frame and so can't be replaced.
- **Definition names.** A definition could redefine a word already in use as a plain word. `define()` now refuses such names, and `learn_from(in_use=…)` guards the hearing side. My own early example definition ("dictionary.py") showed the risk; it was never persisted.
- **The two adopted words are trivial** (a recurring question and a recurring abstention). They demonstrate the loop working, not useful concepts.
- **Other agents' section.** In the Reasoning section I changed the stale figure "64-leaf budget" to "64 in language 1.0, 102 in 1.1", to keep the file consistent.

## Next steps
1. **Partial-frame templates** with variables, e.g. an envelope word written `(env :from courier)` that expands to the full envelope. This would cover what really recurs in our traffic.
2. **Adaptive threshold or a resonator-style decoder,** to push past D/64, together with a per-message flag saying "some slots may be missing".
3. **Define rule shapes** as dictionary words (reasoner's transitive and inherit rules), so proofs cite a rule word instead of spelling it out.
4. **Handle unknown words.** When decoding finds a strong unbound signal it can't name, `read_back` could report "unknown word here", and the reader could then call `lex.reload()` or ask on the channel.
