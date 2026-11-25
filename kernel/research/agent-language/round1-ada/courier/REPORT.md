# courier: the protocol

> Saved by the orchestrator from courier's hand-back. The harness does not let subagents write report files.

## Built

| file | what |
|---|---|
| `shared/protocol.py` | the envelope (`Message`), the reader (`decode`), `Conversation`, and the channel layer: `send`, `resolve`, `inbox`, `threads`, `conversation_of`, `conversations`, `which_conversation`, `audit`, `chunked`, `expand` |
| `shared/say.py` | CLI: `send FROM TO ACT CONTENT [--reply TS]`, `inbox ME`, `read`, `threads`, `audit` |
| `shared/LANGUAGE.md` § Protocol | the spec |
| `courier/test_protocol.py` | 17 unittests (private Lexicon and temp channel) |
| `courier/measure.py` | measurement suite; output in `measure_output.txt` (sections 2–6) and `measure_output_1.txt` (section 1) |
| `courier/claims.py` | 15 reproducible protocol claims, told to the KB |
| `courier/grade.py` | grades other agents' pending claims by re-measuring with my own seed |

## How it uses the language

The envelope is `lx.encode({proto:"proto_v1", from, to, act, content, reply_to:<parent glyph>, thread:<Strand state>})`, so it is a lexicon sentence and `LX.decode` reads it too. Words and roles are glyphs, bind attaches a filler to its role, bundle makes the sentence, the grammar's roll marks composite fillers, and Strand is the conversation. Links are glyphs, not ids. The receiver reads in five steps:
1. Handshake: the proto slot must reach at least 0.12, about 7σ.
2. Header: from, to and act, each against its closed set of words.
3. Links: `reply_to` and `thread`, matched to the nearest glyph seen on the channel.
4. Content: a codebook concept (only if it reaches 0.6 × the handshake similarity) or the anonymous decode; the reading whose re-encoding best explains the glyph wins.
5. Fidelity: sim(re-encoding, received glyph).

## Dialogue and outcomes

- I ported from `role:`/`w:` to lexicon's `attr:`/`val:` and made the envelope a lexicon frame.
- All four agents post through `protocol.send`.
- Reasoner asked, in glyphs, how deep content can nest in an envelope. I measured it and answered in the same thread: 1 level anonymous, 8 or more chunked.
- Lexicon proposed `chunk(whole=True)`. I adopted it; `send()` auto-chunks only content that is nested or over budget, so the codebook doesn't grow by one concept per message.
- The live audit found a bug: a known concept sharing 1–2 fields with the real content hijacked the content slot, misreading 5 of 17 messages. I fixed it with the concept threshold plus the best-fidelity choice (regression test added). Lexicon ported the same fix into `LX.decode`.
- My 15 claims are all known (reproduced by lexicon, memory and reasoner).
- I graded 81 peer claims by reproduction: 76 reproduced, 5 refuted. Memory's canary test: I refuted 4 of 4 planted false claims and reproduced 3 of 3 true controls. I also refuted kb_curve wrong_after_drift (trusted) le_25; it is likely seed-sensitive near the boundary.
- I sent a conversation glyph as a message's content; `which_conversation` found it on the live channel (sim 0.39, margin 0.22).

## Measured

**Header and content decode** (vocabulary 200 words, 12 roles):
- Header fields (from, to, act): 1.00 in every condition.
- Content exact, bare envelope: 1.00 at 1–4 fields, 0.89 at 6, 0.31 at 8.
- Content exact, with reply_to and thread bound in: 1.00 at 1–3 fields, 0.91 at 4, 0.12 at 6, 0.00 at 8.
- Chunked content: 12 fields exact; nesting exact to depth 8 or more. Unchunked nesting in a linked envelope: 1 level.

**Handshake acceptance under corruption:**

| bits flipped | accepted |
|---|---|
| 0–20% | 1.00 |
| 30% | 0.96–0.98 |
| 35% | 0.27–0.32 |
| 40% and above | 0 |

Foreign seeds, random glyphs and bare frames: 0 accepted. At 15% flips the message still passes, but fidelity drops below 0.9 and flags it.

**Reply resolution:** 1.00 among 10, 100 and 1000 seen messages. Similarity to the true parent is about 0.32; the best wrong candidate is 0.12, 0.17 and 0.21 respectively.

**Thread memory** (24-turn thread; identify the turn at a given age among the thread plus 100 other messages):

| age | top-1 accuracy |
|---|---|
| 0–4 | 1.00 |
| 5 | 0.97 |
| 6 | 0.77 |
| 7 | 0.42 |
| 8 | 0.22 |
| 9 | 0.10 |
| 12 and above | about 0 |

**Recognition:** which conversation a message belongs to, 1.00 among 100. A conversation sent as content, 1.00 among 20.

**Live channel audit:** 28 envelopes; from/to/act 28/28; content 27/27; reply_to 9/9; 4 bare glyphs rejected. Reading the whole channel takes 0.38 s.

## Limits

- Unchunked content budget is small (4 fields, or 3 with links).
- Chunked content and new words need the shared codebook.
- A Strand keeps individual turns for only about 5 steps; the reply chain is the exact record.
- Envelopes resemble each other (shared proto slot, often shared from/to/act), and order within a same-sender thread is weak (abc vs cba: 0.67).
- Validity is statistical, not authenticated: anyone who knows the words can forge a sender.
- `resolve()` re-decodes the whole log on every call.

## Next

1. Incremental resolver with cached decodes.
2. A group-secret handshake word to stop forged senders.
3. Record closed-conversation glyphs as Space events, so conversations become precedent.
4. An auto-chunk budget planner built from lexicon's capacity tables.
