# lexicon: report

> Saved by the orchestrator from lexicon's hand-back. The harness does not let subagents write report files.

My lens was vocabulary and grammar: how a meaning becomes a glyph and how a glyph is read back. I shipped `shared/language.py` first. The other three layers are built on it: courier's envelopes, memory's facts and questions, and reasoner's conclusions are all sentences of this language.

## What I built

| file | what |
|---|---|
| `shared/language.py` | the language: `Lexicon` (vocabulary, grammar, reader) plus the shared codebook |
| `shared/codebook.jsonl` | the shared dictionary, append-only, about 1000 lines written by all four agents |
| `shared/LANGUAGE.md` | the group spec; I wrote the frame and the "Lexicon & grammar" section |
| `lexicon/test_language.py` | 28 unittests, all passing |
| `lexicon/capacity.py` → `lexicon/capacity_results.txt` | the capacity measurements behind the tables below |
| `lexicon/claims.py` | 15 grammar claims; each is a measurement anyone can reproduce with their own seed |
| `lexicon/concepts.py` | turns the codebook's concept structure into `part_of` facts and grades other agents' `part_of` claims |
| `lexicon/demo_closure.py` | runs part_of facts through reasoner's closure and checks the derived facts against the definitions |

## How it uses the language

- **Words and roles are kernel symbols.** `word(w) = symbol("val:"+w)` and `role(r) = symbol("attr:"+r)`, with seed 42 and dim 4096.
  - I chose Space's own prefixes on purpose; courier had proposed `role:` and `w:`.
  - As a result, a flat frame is bit-identical to `Space.encode(frame)`, so every sentence is a Space situation (tested).
  - Memory's KB relies on this: a question is the same frame with the object removed.
- **Grammar.** Four kinds of meaning, built with bind and bundle:
  - a `str` is a word, or a named concept;
  - a `dict` is a frame: `bundle(bind(role, filler))` over the roles in sorted order (sorting makes the kernel's tie-break deterministic);
  - a `list` is a frame of positional roles `#1`, `#2`, and so on;
  - an `ndarray` is a raw glyph, passed through.
- **Rolled nesting.** A composite filler is rolled by 1 when it goes into a slot: `bind(role, roll(inner, 1))`.
  - `bind` is commutative, so without the roll, path A.B and path B.A are the same glyph (sim 1.0, measured).
  - With the roll their sim is about 0.
  - Word fillers are not rolled, so flat frames stay Space-identical.
  - Reasoner found the same failure on its own: an unrolled child's slot read back as the parent (.32 vs .23).
- **Reading.**
  - One matmul unbinds every known role and scores the result against every filler.
  - A slot counts if its best filler clears an adaptive bar, `thr() = (sqrt(2 ln N) + 1.25)·σ` with `N = roles × fillers` and a floor of 0.08. That is 0.095 at 128 × 1000.
  - Nested frames are searched for only under `nest_roles`: roles that have ever held a composite. This set is learned by the whole group through the codebook. It keeps decoding a nested message at about 18 ms.
  - A hit on a named concept reads as its name; `expand=True` replaces it with its definition, recursively.
- **Fidelity check.** A structural concept that merely shares slots with the real filler can win the cleanup; courier's live audit caught this. When a slot reads as a structural concept, the reader also reads the slot anonymously and keeps the reading whose re-encoding explains the slot better.
- **Concepts and chunking.**
  - `define(name, m)` names a meaning. Concepts are immutable.
  - `chunk(m)` names every sub-frame with a content hash (`c:<10 hex>`). It **does not change the glyph**; it only teaches the codebook. After that, any agent that has refreshed can read the glyph at any depth.
  - `chunk(m, whole=True)` also names the top frame. That is what makes big content readable inside an envelope.
- **Learned slot types (selectional preferences).**
  - Every encode records which fillers each role has taken (`sel` lines in the codebook, shared by all four agents).
  - When a slot misses the global bar, the reader tries the role's own vocabulary at a lower bar, `type_thr(role)`. It accepts the result only if it is also the global best match.
  - The more we talk, the better we read each other.
  - `novel(m)` flags (role, filler) pairs the group has never used together.
- **Questions.** `ask(want, **known)` builds a frame with the hole `"?"` and `want=<role>`; `holes(m)` finds the holes.
- **Codebook.** `shared/codebook.jsonl` is append-only, with line kinds `word | role | concept | nest | sel`. `decode()` calls `refresh()`, so a receiver learns the sender's words.

## What I said to the others and what came of it

- **Courier.**
  - I announced the prefix choice and told courier to use `lx.encode` for envelopes.
  - Courier dropped its own `role:`/`w:` scheme. Its envelope is now a lexicon frame, so `LX.decode` reads every envelope directly.
  - Courier measured a content budget inside the envelope: exact at 4 or fewer flat slots, 0.31 at 8.
  - I measured a fix: `chunk(content, whole=True)` takes 6–24-slot content from 0.00 to 1.00. I proposed it in a glyph whose content was a concept name.
  - Courier adopted it: `protocol.send` now auto-chunks nested or over-budget content.
  - Courier's live audit found that a look-alike concept could steal the content reading (5/17 messages). I reproduced the bug in `LX.decode` (the look-alike wins cleanup 20/20) and fixed it with the fidelity check (0/20 misreads, test added).
- **Memory.**
  - Memory's facts are `LX.encode` frames, and its KB questions are Space situations because of the prefix choice.
  - Memory reported that the kernel tie-break comes from the first sorted part. I reproduced this with my own encoder: 6 slots differing in the first role measure .53, differing in the last .69. I added it to the spec's rules of thumb.
  - Memory planted blind canary claims. I refuted 4 by my own measurement:
    - bundle recall k=65 (claimed "all");
    - nest read depth=4 (claimed "readable");
    - overlap_sim n=4 m=2 (claimed 0.7);
    - last_attr_differs n=3 (claimed "yes"; odd n has no ties, gap 0.002).
  - I reproduced the other 3. Courier independently refuted the same 4.
- **Reasoner.**
  - Reasoner asked which transitive relations to close over. I answered in the language (act=answer, reply_to its ask) with `contains`, and reasoner added it to its transitive set.
  - Reasoner used `chunk` for nested conclusions (1.00 to depth 10) and posted a 3-level "reasoning on reasoning" glyph. It decoded exactly with `expand=True`.
  - That glyph gave the codebook real concept chains. `concepts.py` told 11 `part_of` facts.
  - Reasoner's `closure` over them derived 12 facts at depths 2–3 (`demo_closure.py`). All 12 reproduced from the definitions.
  - I deliberately did not `tell()` the 12 derived facts; they are reasoner's inferences to claim.
- **Grading.**
  - I filed 15 grammar claims and 11 `part_of` claims.
  - Every grammar claim takes the grader's own seed, and the seed changes both the vocabulary and the frames. Agreement therefore means the property belongs to the grammar, not to one draw.
  - 14 of my claims are **known** (3 independent reproductions each), and 0 have been vetoed.
  - I graded about 45 claims by others, all by reproduction and never from the text: reasoner's 26 (including 13 measured on memory's world), courier's 15, memory's KB smoke claim, and the 7 canaries (4 refuted).
- **On the channel.** I decoded every glyph with `LX.decode`, and each matched its text. Most of my own messages went through `protocol.send` with a content frame in the language.

## Measured results

Setup: dim 4096, 1000 words, 128 roles, 50 trials; full tables in `lexicon/capacity_results.txt`.

**Flat frame, blind decode (every role probed, untyped).**

| slots | 1–24 | 32 | 40 | 48 | 64 |
|---|---|---|---|---|---|
| exact | 1.00 | 0.94 | 0.38 | 0.00 | 0.00 |
| slot recall | 1.000 | 0.998 | 0.974 | 0.897 | 0.608 |

Slot sim is about `sqrt(2/πn)`: .50 at 2–3 slots, .31 at 6, .20 at 16, .14 at 32.

**Probe one known slot** (no threshold): top-1 is 1.00 up to 64 slots, 0.985 at 80.

**Nesting, exact decode of the whole tree.**

| slots per frame | depth 1 | depth 2 | depth 3 | depth 4 | chunked (all depths measured) |
|---|---|---|---|---|---|
| 3 | 1.00 | 1.00 | 0.84 | 0.00 | 1.00 |
| 4 | 1.00 | 1.00 | 0.00 | 0.00 | 1.00 |
| 6 | 1.00 | 0.00 | 0.00 | 0.00 | 1.00 |

Innermost slot sim for 3-slot frames: .50 .24 .13 .06 at depths 1–4.

**Lists.** Exact up to 16 items.

**Noise.**
- Max noise over the 128 × 1016 table: mean 0.070, worst 0.081. The adaptive bar is 0.095.
- 0 false slots on 1000 real 6-slot frames and on random glyphs. A fixed 0.08 bar gave about 5% false slots per frame at 1000 words.
- Glyphs from a foreign seed read as nothing.

**Similarity.** Two 6-slot frames sharing k slots, for k = 0 to 6: .00 .11 .23 .36 .51 .64 1.00.

**Learned slot types.** 3000 words, 80 roles, each with a 25-word vocabulary; speaker and reader are separate.

| slots | frames seen | untyped exact | typed exact | typed slot recall |
|---|---|---|---|---|
| 32 | 400 | 0.76 | 0.94 | 0.998 |
| 40 | 400 | 0.14 | 0.62 | 0.991 |
| 48 | 400 | 0.00 | 0.10 | 0.960 |
| 56 | 400 | 0.00 | 0.00 | 0.902 |

No gain at 16 slots, where untyped reading is already exact (claimed and reproduced).

**Envelope content** (7-part envelope, 20 trials each). Anonymous content is 1.00 exact at 4 slots and 0.00 at 6–24. As a concept (`chunk(whole=True)`) it is 1.00 at 4, 6, 8, 12, 16 and 24 slots.

**Concept misread fix.** A look-alike concept (sharing 2 of 3 slots) wins probe cleanup 20/20. `decode` now returns the true content 20/20.

**Closure demo.** 11 told part_of facts gave 12 derived facts, 12/12 reproduced.

**Speed.** Decoding a nested message takes about 18 ms (129 roles × 1021 fillers).

**Tests.** `lexicon/test_language.py` has 28 tests, all passing. The other suites also pass on the final `language.py`: courier 17, memory 19, reasoner 19 + 7.

## What doesn't work

- **Words are atoms.** Symbols are random, so "bundle" and "bundles" are unrelated. Similarity of meaning comes only from shared structure; nothing derives a word's meaning from its usage.
- **A reader can't clean up a word it has never seen.** If a sender encodes with a private (`path=None`) lexicon, receivers lose those slots.
- **Anonymous nesting is physically limited** (table above). Depth 3 and beyond need `chunk`.
- **Typed reading is inflated when speaker and reader are the same.** A reader that just encoded a frame already has its pairs. `claims.py` therefore pins `typed=False` for the plain-grammar claims; before that, "48 slots lossy" flipped on one seed.
- **The codebook only grows.** 86% of its lines are `sel` entries, there is no compaction, and every chunk adds fillers, which raises `thr()` for everyone. Courier avoids chunking small flat content for this reason.
- **The even-count tie-break bias stays.** Fixing it would break bit-identity with Space.
- **`part_of` coverage is partial.** It is told only for concepts with exactly one parent, because the KB answers one object per (subject, relation).

## Next steps

1. **Grounded word senses.** A word's sense would be the bundle of the (role, co-filler) contexts it appears in, so unknown-word readings and synonym discovery come from group usage.
2. **Codebook compaction.** A snapshot plus offset, with deduplicated `sel` lines.
3. **Automatic chunking from a budget.** Predict read-back accuracy from slot counts and depth using the tables above, and `chunk` automatically when the prediction falls below 0.99.
4. **Finish the grading.** Get the remaining `part_of` and `typed_reading` claims to known, and have reasoner tell the 12 closure facts so they get graded.
