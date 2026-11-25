# Four agents, one language: combined report

Four Claude agents (lexicon, courier, memory, reasoner) were each given the Ada kernel and asked to use it **as a language** to build an application they could communicate through and use to build intelligence. They ran in parallel for about 25–35 minutes and talked only through the shared channel and shared files.

Everything below that the orchestrator re-checked is marked ✔ with the result.

## What they built

One stack, four layers. Each layer is a file in `shared/` that the others import.

| layer | file | owner | what it does |
|---|---|---|---|
| language | `shared/language.py` | lexicon | Words and roles are kernel symbols; a meaning (word, frame, list, nested frame) becomes one 4096-dimension glyph and is read back through a shared, append-only codebook (`shared/codebook.jsonl`) |
| protocol | `shared/protocol.py`, `shared/say.py` | courier | A message is one sentence: `{proto, from, to, act, content, reply_to, thread}`. Replies and threads link by glyph, not id; a receiver decodes everything from the glyph alone and scores its own fidelity |
| knowledge | `shared/knowledge.py`, `shared/kb/` | memory | A fact is a sentence; a question is the same sentence minus its object (bit-identical to a kernel `Space` situation). Claims become **known** only after 3 other agents reproduce them with their own seeds |
| reasoning | `shared/reason.py` | reasoner | Asking by unbinding, analogy, abstraction, chains and closure, nested conclusions, and `judge`, a calibrated "I don't know" |

The full spec is [`shared/LANGUAGE.md`](shared/LANGUAGE.md) (485 lines, one section per owner). The conversation, decoded from the glyphs, is in [`TRANSCRIPT.md`](TRANSCRIPT.md). Per-agent detail is in each `REPORT.md`.

## The language on one card

```
word(w)   = symbol("val:"  + w)          seed 42, dim 4096
role(r)   = symbol("attr:" + r)

"sea"                       -> word("sea")
{subject: sea, relation: is, object: cold}
                            -> bundle( bind(role(k), filler(v)) for k in sorted )
[a, b, c]                   -> the frame {#1: a, #2: b, #3: c}
nested frame as a filler    -> bind(role, roll(inner, 1))    # roll keeps A.B != B.A
question                    -> the frame with a hole: {..., object: "?", want: object}
concept                     -> define(name, meaning) / chunk(m): names a sub-frame in the
                               codebook without changing the glyph, so deep nesting reads back

reading   = unbind every role in one matmul, clean up against the codebook,
            accept a slot only above an adaptive bar ((sqrt(2 ln N)+1.25)·σ)

message   = {proto: proto_v1, from, to, act: tell|ask|answer|propose|agree|...,
             content, reply_to: <parent glyph>, thread: <Strand state>}

fact      = {subject, relation, object, **context}
question  = the same frame minus object  ==  Space.encode(situation)
known     = sufficient ∧ strict majority ∧ ≥ 3 independent reproductions ∧ no trusted veto

conclusion = {claim, because: [premises...], rule, confidence}   # nests: a conclusion
                                                                 # can be a premise
```

A flat frame in this language is **bit-identical** to the kernel's own `Space.encode`, so every sentence is also a precedent situation. That is the design choice that let the four layers join up.

## Did they really communicate?

Yes, in the language itself, not just in English.

- ✔ **38 channel messages, 32 of them carrying a glyph.** Messages per agent: lexicon 11, courier 10, reasoner 9, memory 7, plus the orchestrator's opening line.
- ✔ **Everything decodes from the glyph alone.** Re-running `protocol.audit()`: 28 envelopes decoded, sender/addressee/act 28/28, content 27/27, reply links 9/9, 4 bare glyphs correctly rejected.
- **Real exchanges in glyphs:**
  - reasoner asked "which relations are transitive?" as a question glyph, and lexicon answered `contains` in a reply glyph that linked back to the question;
  - courier answered reasoner's nesting-depth question the same way;
  - reasoner posted a 3-level "reasoning about reasoning" glyph, and lexicon decoded it exactly.
- **They fixed each other's work:**
  - lexicon's prefix choice made courier drop its own scheme;
  - courier's live audit found a decoding bug (a look-alike concept stole the content, 5 of 17 messages misread). courier fixed it in the protocol, and lexicon ported the fix into the language (20/20 misreads → 0/20);
  - reasoner and lexicon independently found that the nesting `roll` is load-bearing;
  - memory added `evidence=` and `lineage()` because reasoner asked for them.

## Did they build intelligence?

A small, honest version of it: a **shared knowledge base that grows only through independent verification**.

- ✔ **The KB now:** 95 claims, 258 grades, 0 bad receipts.
  - Claims by author: reasoner 39, lexicon 27, courier 15, memory 14.
  - Status: 74 **known**, 16 uncertain, 5 vetoed.
- ✔ **The canary test worked.** memory announced it would plant blind claims, then planted 7: 4 false, 3 true.
  - All 4 false claims are **vetoed**: courier and lexicon each refuted them by re-measuring.
  - The 3 true claims were confirmed but are still "uncertain": only 2 of the 3 required reproductions.
  - The fifth veto is courier refuting a borderline claim of memory's.
- **New knowledge by reasoning.** reasoner inferred 6 facts no one had told it, from premises others had verified. The other agents reproduced all 6 (12/12 grades), and it correctly abstained at the 3 boundary points.
- **A learning curve.** On a replay of the group's real ledger, the share of questions the group could answer rose from 0 to 0.86 over 17 minutes. In memory's simulation, the consult rate fell from 58% to about 7% at 0.97–1.00 accuracy.

## Tests

✔ Run by the orchestrator after all four finished:

| suite | tests | result |
|---|---|---|
| `lexicon/test_language.py` | 28 | OK |
| `courier/test_protocol.py` | 17 | OK |
| `memory/test_knowledge.py` | 20 | OK |
| `reasoner/test_reason.py` + `test_agent.py` | 28 | OK |
| **total** | **93** | **all pass** |

## Honest limits

- **The only subject they know is themselves.** Every fact in the KB is a measurement of the kernel or their own language, such as capacity limits and decode rates. That made every claim checkable, but it isn't knowledge about the outside world.
- **Words are atoms.** "bundle" and "bundles" are unrelated symbols; meaning comes only from structure. Nothing yet learns a word's sense from how it is used.
- **Capacity is real and small.**
  - A flat frame reads back exactly up to about 24 slots.
  - Anonymous nesting lasts only 2–3 levels.
  - Envelope content is limited to 4 plain fields.
  - A conversation Strand remembers individual turns only about 5 steps back.
  - Deeper structure needs `chunk`, which leans on the shared codebook.
- **Part of the learning curve is simulated.** The real agents mostly told and graded rather than asked, so the real curve comes from replaying the ledger.
- **Trust is statistical.** Anyone who knows the words can forge a sender, vetoes are permanent, and the codebook only grows (86% of it is slot-type entries).
- **The harness wouldn't let subagents write their REPORT.md files.** Each one sent its report as text, and the orchestrator saved it verbatim with a note.
- **One slip by the orchestrator.** While verifying, it called `kb.ask()` on every claim, which added 95 "anon" entries to `ledger.db`'s asks table. They don't touch any claim or grade.

## What they suggest next

1. **Grounded word senses** (lexicon): a word's meaning as the bundle of the contexts it appears in.
2. **A secret handshake word** (courier) to stop forged senders, plus an incremental decoder.
3. **Time-ordered vetoes and per-domain grader reliability** (memory), so the KB can recover when the world changes back.
4. **Automatic re-grading** when a premise is vetoed (reasoner and memory: `stale()` + `lineage()`), and learned rules beyond monotone ones.
5. **Give them a real domain.** Point the same stack at facts from outside itself, such as a codebase, a dataset or a product, and see whether it still verifies what it learns.
