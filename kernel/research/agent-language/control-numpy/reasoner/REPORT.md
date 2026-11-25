# reasoner: REPORT

> Saved verbatim by the orchestrator from the agent's hand-back. The harness does not let subagents write report files.

## Summary

I built `shared/reason.py`, the group's reasoning layer. It runs on lexicon's `language.py` and memory's `knowledge.py`, and it makes new knowledge out of existing hypervectors: it answers structured questions, draws analogies, abstracts a gist from many cases, and chains inferences into nested conclusions. Every answer comes with a calibrated confidence and can be the language atom `unknown`. Conclusions go into the shared KB with a check that anyone can rerun, so other agents grade them. The reasoner never grades its own facts.

On the real KB this worked end to end for one conclusion:
1. I derived `(talk.py depends_on knowledge.py)`.
2. Courier and memory reproduced it (trust 0.74).
3. Memory's own `kb.ask` now answers with it.

Two more real conclusions are still ungraded, because the others had finished by the time I told them.

- Tests: `reasoner/test_reason.py`, 19/19 OK.
- Benchmarks: `reasoner/bench.py`.
- Nothing I ran wrote throwaway words into `shared/vocab.txt`: I diffed it before and after the test run.

## What I built

Code:
- `shared/reason.py` (shared).
- `shared/reason_calibration.json`: the fitted calibrator.
- `reasoner/bench.py`: measurements.
- `reasoner/test_reason.py`: tests.
- `reasoner/agent.py`: one live work step on the real KB and channel.

**Confidence and "I don't know"**
- Every read is `language.unbind_role(v, *path)` plus a cleanup against a codebook.
- Two numbers describe a read:
  - `z1` is the top similarity in noise units (sim·√D; a random pair is N(0,1)).
  - `gap` is `z1 − max(z2, 0)`.
- A Calibrator maps the gap to P(correct):
  - It uses pool-adjacent-violators, fit on synthetic slot queries over frames of 1 to 1500 leaves, with 30% of the queries asking for a role that isn't there.
  - An absolute floor applies: a read with `z1 < 5σ` gets that region's measured accuracy (0.22). Small codebooks otherwise produce large gaps out of pure noise. This was a real bug: a told fact decoded a phantom `rule` slot.
- Two thresholds are kept separate:
  - `tau = 0.8` asks whether the vector read is right.
  - `min_trust` (0.6, the KB's `TRUST_ANSWER`) asks whether the fact is true.

**Operations**
- `R.query(v, *path)`: read one slot, or a path of slots, of a meaning.
- `R.analogy(A, B, x)`: "the dollar of Mexico".
  - Two-step version: find x's role in A (`A·roll(x)` against the role vectors), then read that role of B.
  - One-shot version, `R.analogy_mapping`: `roll⁻¹(A·B·roll(x))`. It must exclude x itself, because both frames carry the FRAME marker, so A·B contains an identity map. I found this by measuring.
- `R.analogy_facts(fm, a, b, c)`: a:b :: c:? over facts. It finds the relation from a to b by vector slot match, then asks (c rel ?).
- `R.abstract(cases)` and `fm.gist(entities)`:
  - The prototype is a majority bundle.
  - A filler is in the gist only if a strict majority of cases hold it (>6σ, measured per case).
  - `R.classify` picks the nearest prototype.
- `fm.infer(rules)`: Horn rules over triple patterns, forward-chained to a fixpoint.
  - It is semi-naive: after the first round, a rule only fires if at least one premise came from the previous round.
  - Premises are matched by batched vector matching; every given slot must score above 8σ.
  - This took a 364-node taxonomy from 32 s to 0.5 s.
  - Built-in rules:
    - transitive: `is_a`, `part_of`, `located_in`, `depends_on`
    - inherit via `is_a`: `has`, `can`
    - inverse: `parent_of` → `child_of`
    - two compositions
  - Rules are themselves meanings: `(rule :name … :cond [..] :then (..))`.
- Conclusions are meanings too: `(assert :subj … :rule … :conf … :because [<premise (assert s r o) vectors>])`.
  - Each premise vector is the same vector the KB stores, so anyone holding the KB can decode a proof.
  - `R.explain` recurses through premises that are themselves conclusions, so proofs nest to any depth.
- `fm.learn_from_grades([(fid, ok)])` refits raw conclusion confidence to P(right) from outside grades. The more the reasoner is graded, the better its "I don't know" becomes.
- `fm.contradictions()`: a functional relation (owner, capital_of, equals, bytes) with two different objects for one subject gets flagged. `agent.py` grades the weaker fact `ok=False, how="contradicts"` when the stronger one has trust ≥ 0.7.
- `fm.answer(question_meaning)` → answer meaning. These are the five question forms in LANGUAGE.md:

  | question | answer |
  |---|---|
  | `(query :subj s :rel r :obj ?)` | the object, or a list if several |
  | `(query :subj ? :rel r :obj o)` | every subject s |
  | `(query :subj s :rel r :obj o)` | `yes` or `unknown` |
  | `(query :rel analogy :subj [a b c] :obj ?)` | d, with the two facts as `:because` |
  | `(query :rel gist :subj [x y ..] :obj ?)` | what a strict majority share |

- Checkers registered with `knowledge.register_checker`, so `kb.reproduce` can rerun them:
  - `reason:<rule>:<fid>,<fid>`: re-derives the step symbolically; a forged derivation fails.
  - `imports:<path>:<module>`: reads the source with ast.
  - `grep:<path>:<text>`: paths are confined to control-numpy.

## Measured results (`python3 reasoner/bench.py`, private lexicon, D=8192)

| benchmark | result |
|---|---|
| A: slot queries, held-out seed, 1..1500-leaf frames, 30% absent roles | ECE 0.012; answers 51.7% of queries and is 100% right on those; forced guessing would be 63.2% right |
| B: record analogy, 234 queries | two-step 100%, one-shot mapping 96.6%; abstains 100% when the filler is not in A |
| C: fact analogy (4 relations × 30 pairs) | 100% on 49 queries; abstains 100% when c has no such fact or a and b are unrelated |
| D: gist, 15 cases, 3 of 8 roles constant, 20% exceptions | precision 1.00, recall 0.989, value 100%; classification 99% |
| E: inference, 121-node taxonomy | 429/429 derived, precision = recall = 1.0, recheck 100%, proof steps decoded from the vector 100%, 30/30 deep trees bottom out in told facts; 0.13 s. At 364 nodes: 1827/1827 in 0.5 s |
| F: noisy tellers (25% false edges), 5 seeds | conclusion ECE 0.394 raw → 0.051 after learning from half the grades; 95.1% right when it answers (48% coverage), vs 65.6% of all conclusions being true |
| G: growing QA (40 answerable, 41 unanswerable) | coverage 0% before inference → 100% after, all right; unanswerable questions abstained 100% both times |

## What I said to the others and what came of it

- **Plan and needs.** I posted my plan and asked for roles `because`/`rule`/`conf` and the atom `unknown`. Lexicon added all of them to the inventory.
- **API announcement.** I announced the API, the question forms and the `reason:` check format. Memory made `kb.reproduce` pass the fid to checkers, which my checker uses, and lazily imports `reason` so the checker is found.
- **Graded others' facts.** I reproduced 21 of their facts through their checks, including catching memory's `7x9 equals 64` canary. I also graded `17c2c92f82d7 (self_grade allowed no)` by trying a self-grade in a temp KB and seeing it rejected.
- **Wrong answer, then fixed.**
  - My first answer to courier was `unknown`, because I used my read threshold of 0.8 on KB trust of 0.64.
  - Memory pointed this out. I split the two thresholds, re-answered with `yes conf_mid`, and switched to courier's stateless `P.serve`.
  - Courier noted I had answered one question twice; `P.serve` fixes that.
- **Dependency graph.** I told 8 `depends_on` facts and 6 `owner` facts, each with a source check.
  - Memory and courier reproduced all 14.
  - From them I derived `talk.py depends_on knowledge.py`, sent its proof in the language (`m6dd72c68ffd2`), and courier agreed.
  - When I asked memory in the protocol (`madcf0da53195`), memory's KB answered `[language.py knowledge.py protocol.py]`, which includes my conclusion.
- **Part-of facts.** At my request memory told `part_of` facts. I derived two more conclusions from them: `(knowledge.py part_of language)` and `(kb.jsonl part_of memory_layer)`.
- **Real-KB gist.** `gist [protocol.py reason.py]` → `(depends_on knowledge.py)`, `(depends_on language.py)`.
- **No answer from lexicon.** My question to lexicon (`m843d9f5b07fe`, `language.py part_of ?`) got no answer.

## What doesn't work / limits

- **Two conclusions ungraded.** They sit at trust 0.5 (below the answer threshold) because the other agents finished first. The second-level derivation (kb.jsonl part_of language) waits on them.
- **Real-analogy blocked by low trust.** Analogy over real facts is correctly abstained: two facts at trust 0.66 each are below min_trust after decay. The KB's trust is a conservative Beta mean, not a probability, so multiplying trust values makes long chains fade fast.
- **Grade learning only simulated.** `learn_from_grades` is only measured in simulation; the real KB has 3 graded conclusions, too few to fit.
- **First proof wins.** A conclusion keeps the first (strongest-in-round) proof it was found with; a stronger proof in a later round does not replace it.
- **Gist is limited.** It needs a strict majority. Profiles are single superposed frames, so very many facts about one entity will saturate them (not measured).
- **Calibration domain.** The calibrator was fit on synthetic frames with a 300-word codebook. Transfer to other codebook sizes relies on the 5σ floor rather than being fitted.

## Next steps

1. Fit `learn_from_grades` on real outside grades once enough conclusions have been graded.
2. Learn rules from the KB: propose a composition rule when it holds in more than 90% of cases, and let the world grade the rule as a fact.
3. Add `:time` to facts (memory's and courier's idea), so dependency facts expire when code changes instead of being refuted.
4. Keep the best proof per conclusion across rounds.
