# reasoner: report

Lens: thinking in the language. Operations that make knowledge the group was never told, and that say "I don't know" when the evidence can't carry an answer.

> Saved by the orchestrator from reasoner's hand-back. The harness does not let subagents write report files.

## What I built

| file | what |
|---|---|
| `shared/reason.py` | the reasoning operations (shared; stdlib + numpy + kernel) |
| `reasoner/agent.py` | the reasoner's turn on the shared KB: infer, tell, grade, answer |
| `reasoner/claims.py` | 20 reasoning properties as seed-reproducible measurements, told to the KB |
| `reasoner/bench.py` | experiments E1-E7; output in `reasoner/bench_output.txt` |
| `reasoner/test_reason.py`, `reasoner/test_agent.py` | 28 unittest tests, all passing |
| `shared/LANGUAGE.md`, section "Reasoning" | the spec section I own |

### shared/reason.py

- **`judge(noisy, candidates)`** is the one decision rule. It cleans up a noisy glyph and gives a confidence. The formula has no fitted parameters:
  - `p_noise = 1 - Phi(top/sigma)^V`: could the best of V random candidates reach this sim?
  - `p_sep = Phi(margin/(sigma*sqrt2))`: is the best really above the runner-up?
  - `conf = (1 - p_noise) * p_sep`. An answer counts as known only when `conf >= 0.90`.
- **`Frames`** holds one frame glyph per subject: `bundle(bind(role r, word o))`. This is bit-identical to `LX.encode(...)` and to `Space.encode(...)` (tested).
  - `ask(s, r)` unbinds the role to answer (s, r, ?).
  - `relation_between(a, b)` unbinds the filler and cleans up against roles to answer (a, ?, b).
- **`analogy(a, b, c)`** answers a:b::c:? in two ways:
  - relational: name the relation, then ask c for it;
  - algebraic: Kanerva's `bind(bind(frame a, b), frame c)`.
- **Chains and closure.**
  - `chain` does multi-hop inference with a cleanup at every hop. Its confidence is the product of the hop confidences.
  - `chain_holistic` is the no-cleanup control.
  - `closure` does transitive inference and emits new facts with their premises and a confidence.
- **`abstract`, `typical`, `classify`**: the gist of many cases is their bundle. Unbinding the gist gives what is typical.
- **`conclude(claim, premises, rule, conf)`** builds a conclusion as a sentence: `{claim, because: [premises], rule, confidence}`.
  - It is bit-identical to lexicon's `LX.encode` of that meaning (tested).
  - A conclusion can therefore be premise #k of the next conclusion.
  - `premise`, `claim_of` and `descend` read it back. `descend` uses cleanup memory and works at any depth.
- **`ordinal_infer(points, grid)`** fills in unmeasured points of a measured family f(param) that forms a monotone step function.
  - Sandwich: if f(lo) == f(hi) and lo < x < hi, then f(x) has the same value.
  - Extrapolate: carry a plateau past the last known point, with confidence decaying per step.
  - Where neighbours disagree, it draws no conclusion.

### reasoner/agent.py (one turn)

1. **Read memory's KB** (`shared/knowledge.py`). It drops questions that are vetoed or contested, and claims the group now answers differently.
2. **Infer.**
   - `closure` runs over transitive relations: is_a, part_of, contains, depends_on, implies. lexicon suggested `contains` in reply to my question on the channel.
   - `ordinal_infer` runs over every measured family with a numeric context parameter. The grids come from `memory/world.py` and each peer's `claims.py`.
   - Each result is told with `evidence=[premise claim ids]`, a confidence, and a `how`.
   - **Premises must already be reproduced by someone other than their author.** A claim-only premise carries 0.5, which can't lift a conclusion over the bar.
3. **Learn rule reliability** from the grades my inferences received: `conf(rule) = (prior*20 + wins) / (20 + graded)`. A veto lowers every later conclusion that rule makes (tested).
4. **`stale()`** flags my inferences whose premise was later vetoed or contested (tested). I can't grade my own claims, so these are flagged for the others.
5. **Grade pending claims I can reproduce.**
   - A peer's measurement is re-run with my own seed, through `<author>/claims.py`, `lexicon/concepts.py` or `memory/world.py`.
   - A derived claim is re-derived from its cited premises.
6. **Answer `act=ask` glyphs** addressed to reasoner or all, using courier's `protocol.inbox`/`send`. When the KB can't answer, it falls back to `infer_one`, which uses the ordinal rule or a transitive chain.

## How it uses the language

Everything that moves between agents is a sentence of lexicon's grammar:
- facts;
- questions, which carry `object: "?"`;
- conclusions;
- confidence words: certain, likely, plausible, doubtful.

All of it is built with `symbol("val:"/"attr:")`, with composite fillers rolled by 1, so the other agents decode my glyphs with `LX.decode`.

I also decoded the others' glyphs:
- lexicon's and memory's API announcements;
- lexicon's reply to my question (`contains`);
- lexicon's typed-reading claim with a nested `because`;
- courier's envelopes, through `protocol.inbox`.

**Reasoning on reasoning, as one glyph.** I posted a 3-level chunked glyph: claim "sandwich reliability high", because of two conclusions, each because of two measured facts. `decode(expand=True)` returned the exact tree.

Reasoning is algebra: unbind to answer questions, bundle to get a gist, unbind-then-bind for analogy, nested slots for conclusions. What the algebra can't do alone is done with cleanup memory: deep structure and long chains. The bench shows why that is required.

## What I said, and what came of it

- **Evidence and confidence on `tell`.** In my plan I asked memory to accept both; memory added them.
- **The roll rule.** I told lexicon its composite-roll rule is load-bearing, which I had measured independently. Without it, unbinding a child's slot lands on the parent (sim .32 vs .23 for the true child). lexicon cites this in LANGUAGE.md.
- **Unknown words.** I reported that `LX.decode` can't read words it has never seen. I added `reason.publish()` to register the roles and words I introduce.
- **Which transitive relations?** I asked this as a question glyph. lexicon answered in glyphs (`contains`), then built `lexicon/concepts.py`, which tells codebook `part_of` facts. I graded its first 3 by expanding definitions; all were ok.
- **Inferring the gaps.**
  - I measured 13 memory-world questions and told them; lexicon reproduced all 13.
  - From those graded premises I inferred 6 gaps. **memory and lexicon reproduced all 6: 12/12 grades ok, 0 vetoes.** Ground truth, used only for scoring, agrees 6/6.
  - The 3 points I abstained on are exactly the boundaries: k=65 (truth "most", a value no neighbour had), age=5 and depth=4.
- **Reasoning claims.** I told 20 reasoning claims from `reasoner/claims.py`; lexicon reproduced 20/20.
- **Grading.** I graded 38 claims by reproduction, all ok, 0 vetoes:
  - memory: 1;
  - lexicon: 22 (13 grammar claims, 2 typed-reading claims, 3 part_of claims, the API claim, and 3 more through `claims.py`);
  - courier: 15 protocol claims (handshake, reply_to, thread recall, fidelity).
- **Lineage.** memory proposed that derived claims resting on a vetoed premise should be re-graded. I implemented `Reasoner.stale()` on my side and suggested a `kb.lineage(cid)` in knowledge.py.
- **Courier.** I asked courier, in glyphs, for the maximum readable envelope depth. There was no answer by the time I finished.

## Measured results

Dimension 4096. Run with `python3 reasoner/bench.py` (85 s).

**E1: calibration of `judge`** (3000 queries, bundles of 1-400 pairs, V=300)
- ECE 0.024.
- Answers marked known were 100% correct, at 80% coverage.
- 0 of 735 questions about an absent role were answered "known".
- Slightly under-confident in the middle band:

| mean conf | accuracy |
|---|---|
| .60 | .73 |
| .82 | .94 |

- Threshold sweep:

| threshold | precision | false "known" on absent roles |
|---|---|---|
| 0.5 | .92 | 19% |
| 0.7 | .98 | 5% |
| 0.9 | 1.00 | 0% |

- Capacity: when accuracy drops, `judge` abstains instead of guessing.

| bundle size (pairs) | raw accuracy | answered "known" |
|---|---|---|
| < 60 | 1.00 | |
| 120-250 | .82 | .23 |
| 250-400 | .53 | .05 |

**E2: analogy** (40 countries). The one-expression (algebraic) analogy only works on small frames.

| attributes per frame | relational | algebraic |
|---|---|---|
| 3 | 1.00 | 1.00 |
| 6 | 1.00 | .995 |
| 12 | 1.00 | .60 |
| 24 | 1.00 | .09 |
| 48 | 1.00 | .01 |

**E3: chains**
- Small frames: cleanup at every hop gives 1.00 to depth 8. Without cleanup (holistic): .97 at depth 1, .01 at depth 2.
- Crowded frames (180 relations):

| depth | 1 | 2 | 3 | 4 | 6 | 8 |
|---|---|---|---|---|---|---|
| accuracy | .90 | .83 | .79 | .69 | .60 | .51 |
| mean chain confidence | .77 | .59 | .45 | .36 | .21 | .12 |

- Answers marked known were 100% correct at every depth. The chain confidence is under-confident: the hop confidences are under-confident, and multiplying them compounds it.

**E4: closure** (is_a tree, depth 5, branching 3). 1278/1278 ancestor facts derived, precision 1.00, with 0, 8 and 40 distractor facts per frame (0.4-3.5 s).

**E5: abstraction** (6 categories, 8 attributes)

| noise | cases | typical | classify |
|---|---|---|---|
| 20% | 9 | 1.00 | 1.00 |
| 50% | 1 | .63 | .85 |
| 50% | 9 | .98 | .99 |
| 50% | 27 | 1.00 | .98 |

**E6: nested conclusions**
- Raw unbinding: sim .127 at depth 1 and .032 at depth 2; accuracy 1.00, then .32, then 0.
- With cleanup memory (`descend`): 1.00 at every depth up to 10, with or without excluding the path. Path exclusion isn't needed thanks to lexicon's roll.

**E7: ordinal inference on memory's world** (unmeasured points of 8 families, 30-70% of points measured)
- It concluded on 29% of points and abstained on 71%.
- Sandwich: 129/129 on draw 7, and 151/151 on held-out draw 8.
- Extrapolation accuracy by steps beyond the last known point:

| steps | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| accuracy | .95 | .82 | .80 | .67 | .40 |

- My first per-step decay (0.97) was over-confident, so I refit it to 0.87 on draw 7. On draw 8, extrapolation scored .91 accuracy vs .87 mean confidence.

**Live KB**
- 6 inferred claims, 12/12 reproductions, 0 vetoes.
- Rule reliability learned from those grades: sandwich 0.988.
- 38 peer claims graded by reproduction, 0 vetoes.

## What doesn't work / limits

- **Pure algebra has about a two-level budget.** Algebraic analogy and holistic chains collapse past about 12 attributes and past depth 1. Everything deep uses cleanup memory, which needs a candidate set: the codebook, the KB, or glyphs already seen.
- **`judge` assumes candidates are random with respect to each other.** Some candidates are correlated: prototypes that share structure, or conclusions that share a rule slot. There the noise model is optimistic. The margin term carries it, but I have not measured calibration in that setting.
- **Chain confidence is under-confident on long chains**, because the product of under-confident hop confidences compounds.
- **Ordinal inference assumes monotone step functions over a numeric parameter.** It correctly refuses non-monotone data. But a family that is monotone on the sampled points and not between them would fool it. Strand recall was the weakest family (.88).
- **`closure` has not yet run on group knowledge.** The live KB has only 1-hop `part_of` facts so far, so closure has been exercised only in tests and the bench.

## Next steps for the group

1. **lexicon:** run `concepts.py tell` on the 3-level glyph I posted. Its chunked concepts form real part_of chains (fact → because-list → conclusion → meta-list). Closure derives the 2-3 hop claims, and grading by re-derivation is ready.
2. **memory:** add `kb.lineage(cid)` and re-grade on veto, so `Reasoner.stale()` becomes a group mechanism. After the dim-1024 drift, my k=17 inference (premise k=33, which flips) is the test case.
3. **Recalibrate `judge` for correlated candidate sets**, fitted per candidate kind from graded outcomes, the same way rule reliabilities are learned.
4. **Rules beyond monotone:** learn a relation's composition table from the KB (r1 then r2 implies r3). Then chains produce new relations, not just new endpoints.
