# memory: REPORT

> Saved verbatim by the orchestrator from the agent's hand-back. The harness does not let subagents write report files.

## What I built

- **`shared/knowledge.py`**: the group's shared, graded knowledge base, written on lexicon's `shared/language.py`.
  - **Facts are sentences in the language.**
    - A fact is `(assert :subj s :rel r :obj o)`.
    - A grade is a nested sentence: `(grade :content (assert ...) :obj yes|no :agent g :why how)`.
  - **The log stores the language itself.** `shared/kb.jsonl` is append-only. Each line holds the packed hypervector of its sentence (`wire`, 1024 bytes, base64) plus its text surface. On replay the KB decodes the vector with the shared lexicon, and the decoded meaning is what it believes. `stats()` counts any decode mismatches.
  - **Fact ids come from content:** `fid = sha256(s|r|o)[:12]`. If a second agent tells the same triple independently, that counts as a confirmation.
  - **API:**
    - reading and writing: `tell`, `grade`, `reproduce`, `ask`, `ask_all`, `query`, `facts`, `ungraded`, `stats`
    - trust and channel: `reputation`, `ingest` (a channel message whose payload is `(assert ...)` or `(grade ...)`; courier's `proto_v1` envelopes are unwrapped), `cite`/`resolve`
    - plug-ins: `register_checker`, `answer_handler` (for `protocol.serve`)
    - alias for reasoner: `add_fact`
  - **Checks make a claim reproducible:**
    - `expr:` is a tiny safe arithmetic evaluator.
    - `lang:` checks that a sentence survives encode→decode.
    - `kbcurve:` re-runs my learning-curve simulation.
    - Other agents plugged in their own checkers: courier `proto:`, reasoner `reason:`, `grep:` and `imports:`. They load lazily, which avoids circular imports.
  - **How `ask` works in the language:**
    1. It unbinds the `subj` and `rel` roles from the matrix of all fact vectors and keeps facts where both slots score above `tau = 6/sqrt(D)`.
    2. It answers only from a trusted fact, reading `obj` back with `unbind_role` plus cleanup.
    3. If no fact qualifies, the answer is `uncertain`. It never guesses.
  - **Citations without new vocabulary:** `cite(fid)` gives an embedded vector `atom("fact:"+fid)`, so facts can be cited inside `:because` without adding words to `vocab.txt`. `resolve(vector)` turns it back into the fid.
- **`shared/LANGUAGE.md`, section "Memory & learning"**: the model, the grading law, the answering rule, the API and the measured numbers.
- **`memory/test_knowledge.py`**: 25 unittest cases, all passing (about 14 s). They use a private `Lexicon(path=None)` and a temporary log, so they never touch shared files.
- **`memory/curve.py`**: the simulated learning curve.
- **`memory/real_curve.py`**: the learning curve of the real shared KB.
- **`memory/demo.py`**: an end-to-end demo on a private KB.

## What "the world grades it" means here

- **Only outside grades count.** A claim is worth nothing until an agent other than its teller grades it, in one of three ways:
  - `reproduced`: re-ran its check;
  - `observed`: has its own independent evidence;
  - `confirmed`: told the same triple on its own, or agreed with it in a protocol thread.
- **Self-grades are refused** with `ValueError`, and a teller's own `reproduce` never records a grade.
- **Trust** is the mean of Beta(1 + Σw_ok, 1 + Σw_bad) over outside grades.
- **Answering rule:** `ask` needs trust ≥ 0.6 and at least one outside "ok".
- **Grader reputation is learned from use.** An agent's reputation is how often its grades agree with the majority of the other graders of the same fact, starting from a Beta(3,1) prior. Each grade is weighted by 2·rep − 1.
- **Derived facts** (with `trail=[premise fids]`) are capped at their weakest premise's trust until someone else reproduces them directly.

## Measured results (all outputs seen)

**Simulated curve** (`python3 memory/curve.py`): 120 questions, 600 steps, 4 agents, courier tells 50% lies, graders grade only what their own evidence covers.

| | step 50 (correct / wrong / uncertain) | step 600 (correct / wrong / uncertain) |
|---|---|---|
| graded KB | 0.150 / 0.000 / 0.850 | 0.958 / 0.000 / 0.042 |
| naive last-write KB | 0.242 / 0.025 / 0.733 | 0.883 / 0.117 / 0.000 |

Averages over 5 seeds at step 600:

| scenario | graded KB (reputation-weighted) | graded KB (unweighted) | naive KB |
|---|---|---|---|
| honest graders | 0.958 correct, 0 wrong | same as weighted | 0.848 correct, 0.127 wrong |
| plus a coin-flip grader | 0.972 correct | 0.915 correct | — |
| plus a rubber-stamp grader | 0.957 correct | 0.968 correct | — |

- Against the rubber-stamp grader, reputation did not help: the stamper mostly agrees with the others, so it keeps its weight.
- In one run with the stamper, up to 3.3% of answers were wrong early on, falling to 0 by step 250.

**Real group KB** (`python3 memory/real_curve.py`):
- **Size:** 153 events, 43 facts told by all four agents (memory 18, reasoner 15, lexicon 5, courier 5).
- **Grading:** every one of the 43 facts has an outside grade. Graders: courier 38, memory 25, reasoner 17, lexicon 7.
- **Decoding:** 153/153 events decode correctly from their vectors.
- **Trust:** 40 facts are trusted and 3 refuted.
- **Uncertainty:** over all 39 questions, the uncertain rate fell from 0.846 to 0.077.
- **Answer quality:** 29 answers were confirmed right by re-running their checks, and **0 were wrong**.
- **Uncertainty over time** is a sawtooth: new claims arrive ungraded and push it up to 0.25–0.45, and grading pulls it back down to about 0.08.
- **Learned reputations:** lexicon 0.91, courier 0.97, memory 0.96, reasoner 0.95.

## What I said to the others and what came of it

- **To everyone:** I posted the plan and the API, seeded 7 facts, and warned that "some may be WRONG ON PURPOSE". The canary `7x9 equals 64` was refuted by both lexicon and courier. Later, when courier asked the question in the protocol, the KB answered `unknown`.
- **To courier:** I confirmed that its `to_kb()` fits my KB exactly. I added a `via=` field so relayed facts are recorded without counting as grades, and courier now passes it. I answered its questions in the protocol with `P.serve`, and its `distill` turned those answers into facts.
- **To reasoner:** I pointed out that its "unknown" answer ignored a fact the KB trusted; it then switched to reading the KB. I reproduced its `reason:` derivation (`talk.py depends_on knowledge.py`), which became trusted at 0.74. My later protocol answer included that derived fact. I also told it `part_of` facts for its transitive rule.
- **To lexicon:** I apologised for filling `vocab.txt` with test words. My first simulation run persisted about 80 synthetic words and 4 uppercase roles into the shared file. The harness blocked me from rewriting lexicon's file, so I asked lexicon to prune it; I don't know whether they did. After that, everyone switched to `Lexicon(path=None)` for tests. For lexicon's idea of a vocabulary word per fact, I proposed `cite`/`resolve` instead, which needs no new words.
- **My own mistakes, logged openly:**
  - My `lang:` checker compared role names case-sensitively and graded lexicon's true claim as false. I fixed it and re-graded.
  - One of my facts carries a mistyped check (`language part_of application`), so it re-runs False. Others graded it down by its check, as the rules require.

## What doesn't work

- **A rubber-stamp grader is not caught.** Reputation only detects graders who disagree with the others.
- **One ally is enough.** A single outside "ok" makes a fact answerable, so two colluding agents can push a claim through.
- **Facts have no time.** A claim about code that was true when told, and is now fixed, gets refuted rather than superseded. Courier's `check_lang fails_on uppercase_roles` went this way.
- **Some things are slow.** Reputation cost grows roughly with facts × graders² and `ask` with facts × D. The full `curve.py` run takes about 95 s.
- **Duplicate events pile up.** Re-running `to_kb` appends duplicate tell/grade events; they are harmless but grow the log.
- **A fact's check is fixed at its first tell**, so a mistyped check cannot be corrected.

## Next steps

1. Add a `:time` slot so a newer fact can supersede an older one instead of refuting it.
2. Require two independent graders for high-stakes facts.
3. Base reputation on check-verified grades only, which would catch rubber-stampers.
4. Allow a revised check through a "reclaim" event.
5. Let reasoner's derived facts answer questions nobody told directly, and measure how much that lowers the uncertain rate.
