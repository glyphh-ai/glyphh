# courier: REPORT

> Saved verbatim by the orchestrator from the agent's hand-back. The harness does not let subagents write report files.

## What I built

I owned the protocol, which is how the four agents speak to each other in lexicon's language (`shared/language.py`: D=8192 bipolar hypervectors, sha256-seeded atoms, bind by multiplication, a sum signed once, and 1024-byte packbits on the wire).

- **`shared/protocol.py`** is the application layer.
  - **A message is one meaning, so it is one vector and one 1024-byte payload:**
    `(ACT :from A :to B :check proto_v1 [:conf ..] [:re ^parent] [:thread ^root] :content <any meaning>)`.
    - Speech acts: assert, tell, ask, answer, propose, agree, disagree, ack, grade, define, done, query.
  - **Ids are content-addressed:** `id = "m" + sha256(payload)[:12]`. The `:re` and `:thread` slots hold `atom("msg:"+id)` as an *embedded vector*, so ids never go into `vocab.txt`.
    - A reader recovers the parent by unbinding the slot and cleaning it up against the ids of payloads it has already seen. No registry is needed.
    - A parent the reader has not seen comes back as `None`; the protocol never makes one up.
  - **`decode(payload)` works from the payload alone.** It gives each payload a status: `ok`, `noisy`, `garbled`, `bare` (a meaning without an envelope), `foreign`, or `malformed`.
    - The integrity check is **re-encoding agreement**: re-encode what was read and compare it with what arrived.
    - An intact payload gives 1.0. With bit-flip rate p it gives 1−2p, so `flip_est = (1−agree)/2` measures channel damage directly.
  - **A conversation is a representation.**
    - `Thread.vector()` stores a whole exchange as one vector, and `turn(i)` recovers message i.
    - `distill_all()` turns conversations into established facts with provenance. An ask(s r ?) plus its answer becomes fact (s r x). An assert or propose plus agree/disagree becomes an endorsed or disputed fact. Self-agreement is ignored and abstentions establish nothing.
    - `to_kb()` feeds those facts into memory's KB: the teller tells, endorsers grade ok, disputers grade bad, and each event is recorded with `via="courier"`.
  - **Other pieces:**
    - `pending(me)`, `serve(me, handler)` and `kb_handler(kb)` answer open questions inside the protocol.
    - `profiles()` and `route()` answer "who has talked about this?" by asking each agent's profile vector about the question's role paths.
    - `compose_parts()` and `reassemble()` carry contents longer than one vector can hold (`:seq pKofN`, chained by `:re`).
    - `inbox()` flags a text field that differs from the payload, and a channel sender that differs from the payload's `:from`.
    - A `proto:` checker is registered with knowledge.py (roundtrip, noise, flipest, foreign, reply), so others can re-run my claims.
- **`shared/talk.py`** is the CLI: `send`, `inbox`, `show`, `thread`, `facts`, `route`. Everything it prints is decoded from payloads.
- **`shared/LANGUAGE.md`**: I wrote the "## Protocol" section.
- **Tests and measurements:** `courier/test_protocol.py` (18 tests), `courier/bench.py` (synthetic), `courier/live_stats.py` (the real channel, read-only). All of them use `Lexicon(path=None)`, so they write nothing to the shared vocabulary.

## Measured results

Every number below comes from runs I watched.

**Tests:** `python3 -m unittest courier/test_protocol.py` gives 18/18 OK.

**`courier/bench.py`** (language 1.1, private 200-word lexicon):
- **Round trip:** every envelope field plus reply-to, chosen among 1000 candidate ids, was exact in 300/300.
- **Bit flips:** decode was 100% exact from p=0 to p=0.25, 92% at 0.30 and 0% at 0.35.
  - The flip estimate was off by at most 0.004 on average up to p=0.25.
  - Status was `ok` at p≤0.02 and `noisy` from 0.10 upward.
- **Garbage:** each case below ran 200 times.

  | Input | Status |
  |---|---|
  | Random payloads | 200/200 `foreign` |
  | Permuted codebook (an "other language") | 200/200 `foreign` |
  | All zeros | 200/200 `malformed` |
  | Bare meanings | 200/200 `bare` |
  | ASCII text bytes | never `ok` |

- **Capacity:** one message held up to 24 facts exactly under language 1.1. Under 1.0, 16 facts decoded 67% and 20 decoded 0%.
- **Multi-part:** 100 facts went as 9 parts and came back 10/10 exact after reassembly in random order. A missing part correctly gives `None`.
- **Thread vectors:** turns were recovered 100% for threads of 4, 8, 16 and 32 messages.
- **Routing:** accuracy was 0.765 against a chance level of 0.25. It rose to 0.88 with subject-only questions, and to 1.00 when the owner had actually said that subject.

**The real channel** (`live_stats.py`, before my final messages):
- 37 payloads: 33 protocol messages (courier 21, reasoner 8, memory 3, lexicon 1) plus 4 bare meanings.
- The text field matched the payload in 33/33; the sender matched in 33/33.
- Reply-to was recovered from the payload in 13/13, and thread turns in 16/16.
- `distill_all` produced 13 facts: 4 from question/answer pairs and 5 endorsed. `to_kb` then brought the KB to 39 facts, 30 trusted and 2 refuted.

## What I said to the others and what came of it

- **lexicon:**
  - I asked for protocol roles and acts; they were added to the inventory (from, to, re, thread, content, check, conf, agree, disagree, ack, done, grade).
  - Using the protocol, I answered lexicon's "who decodes this payload?" and agreed to its lowercase-roles proposal.
  - lexicon later sent its own protocol `tell`.
- **memory:**
  - I sent 5 grades as protocol `grade` messages; memory's `kb.ingest` applied all 5.
  - I reproduced or graded all 16 facts in my `kb.ungraded` list. That included catching the 7×9=64 canary as bad, and marking false the one fact whose check was wrong (e9361fc6bf61).
  - I reported 3 bugs in knowledge.py: case-sensitive `_check_lang`, `abs()` rejected by the safe evaluator, and `ingest` trusting the channel's "from" field. memory fixed the lang checker and added `via=` for relays.
  - memory answered my questions through `P.serve` and `kb_handler`. "wire_form bytes ?" came back 1024. "7x9 equals ?" came back `unknown`, which is correct because the canary had been refuted.
- **reasoner:**
  - I reproduced reasoner's 8 `imports:` facts (8/8).
  - I asked "talk.py depends_on ?". Reasoner answered language.py, protocol.py, and knowledge.py (transitive). I agreed with all three, and `to_kb` made them trusted facts (0.74, 0.74, 0.66).
  - Reasoner switched to `P.serve` after I pointed out it had answered one question twice.
  - I answered reasoner's open question "dictionary.py part_of ?" with `unknown` via `kb_handler`, because the KB is uncertain there.

## What doesn't work or is weak

- **Sender identity is not authenticated.** `:from` is only as honest as whoever wrote it. The mismatch flag only catches the case where the payload and the channel line disagree.
- **Random bits and a foreign language look the same.** Without the other language's atoms, both come back as `foreign`.
- **`to_kb` relays for other agents.** It writes KB events under the speaker's name, marked `via="courier"`. That is visible, but it amounts to courier holding the pen for them.
- **Routing is weak when a question includes uninformative leaves.** Accuracy was 0.765; a relation that every agent mentions dilutes the subject signal.
- **Answers are matched to questions only through `:re`.** A free-standing `tell` of a fact does not link to an earlier question about it.
- **Facts about code have no time.** memory's fixed checker turned my true-at-the-time fact "check_lang fails_on uppercase_roles" into a refuted one.

## Next steps

1. Put a `:time` slot on facts so distill can supersede a fact instead of refuting it.
2. Signed senders: a per-agent secret permutation in a signature slot, so a receiver can detect spoofing from the payload.
3. Automatic addressing: fill in `:to` with `route(q, profiles(inbox()))`.
4. Run `dictionary.compress` inside `compose` when content goes over the leaf budget, before falling back to multi-part.

## Files

- `control-numpy/shared/protocol.py`
- `control-numpy/shared/talk.py`
- `control-numpy/shared/LANGUAGE.md` (the "## Protocol" section)
- `control-numpy/courier/test_protocol.py`
- `control-numpy/courier/bench.py`
- `control-numpy/courier/live_stats.py`

My final "done" message is on the channel.
