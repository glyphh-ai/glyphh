# memory: report

> Saved by the orchestrator from memory's hand-back. The harness does not let subagents write report files.

My lens was shared learning: how the group builds up knowledge it can trust.

## What I built

| file | what |
|---|---|
| `shared/knowledge.py` | The group knowledge base (KB). Calls: `tell / grade / verify / ask / ask_glyph / feedback / decide / pending / concept / lineage / suspects / reliability / audit / stats / curve` |
| `shared/kb/` | The live shared files. `claims.db`, `wins.db` and `vetoes.db` are kernel Spaces (WAL mode, `author=` on every row). `ledger.db` holds claims, grades and asks. |
| `shared/LANGUAGE.md` | The "Knowledge: memory & learning" section |
| `memory/world.py` | The world that grades claims: 37 questions about the kernel that anyone can measure (bundle recall, strand recall, nest read, situation overlap). Call it as `measure(q, seed, dim, decay)`. |
| `memory/demo_curve.py` | Learning-curve simulation: 4 workers, 800 asks, the world changes at ask 400, optional hostile grader |
| `memory/run_matrix.py` -> `matrix_output.txt` | 3 veto rules x {world change, hostile grader} x 3 seeds |
| `memory/replay.py` -> `replay_output.txt` | The real curve: replays the group's actual ledger |
| `memory/grade.py` | My grader. It re-runs each peer's `claims.py measure` with my own seed, and checks `part_of` claims by decoding the concept glyph. |
| `memory/claims.py` | My claims, each with a command anyone can re-run (the tie-break finding and KB-curve properties) |
| `memory/canaries.json` | The planted claims used for the canary test |
| `memory/test_knowledge.py` | 20 unittests, all pass |

## How it uses the language

- **A fact is a sentence.** It is `encode({subject, relation, object, **context})` through lexicon's `LX`. The question is the same frame without `object`.
- **The question is the lookup key.** Flat frames are bit-identical to `Space.encode` (lexicon's design; tested in `test_question_is_a_space_situation`). So the question glyph is the Space situation and the answer is the Space outcome. The storage is a Space, not a string table.
- **Questions can arrive as glyphs.** `ask_glyph(g)` answers a question glyph, for example `lx.ask("object", subject=.., relation=..)` inside an envelope. Envelope roles and `?` holes are dropped. Tested.
- **Knowledge about a subject is one glyph.** `concept(subject)` bundles every known fact about a subject. Probing it with `bind(g, role("object"))` reads the known objects back. Facts that are only claimed stay out of it. Tested.
- **Grading follows the kernel contract.** Each (claim, grader) pair is one precedent with `author=grader`, so `count` is the number of independent reproductions. A fact must pass the kernel's trust gates: sufficient, strict majority, and `count >= 3`. It must also pass a veto check through `vetoes.matches()`.
- **"The world grades it" means another agent reproduces the claim.** The grader re-runs the `how` measurement with its own seed (a different draw of words and frames). Or it re-derives the claim from premises, or reads it back from the glyph. Grading your own claim raises `SelfGrade`.

## What I said to the others, and what came of it

- **The KB is in real use.** I posted my plan, then the API, and all four agents used it. The KB ends with 95 claims (courier 15, lexicon 27, memory 14, reasoner 39) and 252 grades (courier 74, lexicon 62, memory 81, reasoner 35). `audit()` finds 0 bad receipts.
- **reasoner.** It asked for `evidence=` and `confidence`, and I added both. It now tells inferences with their premises as evidence. It only reasons from premises that someone other than their author reproduced, and its 6 inferences were reproduced 12/12. I answered its question about which relations are transitive with a glyph message (`derived_from`). I then built `lineage()` and `suspects()` for it.
- **Grading across agents.** reasoner, courier and lexicon graded claims using `memory/world.py` and each other's `claims.py`. I graded 81 peer claims by reproduction and all 81 held.
- **A kernel finding, reproduced by lexicon with its own encoder.** Take two situations that differ in one attribute. If the differing attribute sorts first, similarity is 0.23 / 0.44 / 0.49 at n = 2 / 4 / 6. If it sorts last, it is 0.51 / 0.64 / 0.68. The cause is the even-count tie-break, which is taken from `parts[0]`. So two `{subject, relation}` questions that share only the relation measure about 0.5. That is why I set `MIN_SIM` to 0.70.
- **Canary test.** After 82 claims the KB had 0 vetoes, so there was no evidence that graders ever refute anything. I announced in advance that blind canaries were coming, then planted 7: 4 false and 3 true. courier and lexicon each refuted all 4 false ones and confirmed all 3 true ones. That is 8/8 refutations and 0 false refutations. Their refutations exposed a bug, now fixed and tested: a claim that was refuted but never reproduced still showed as `claimed` instead of `vetoed`.

## Measured results

**Simulated learning curve** (`demo_curve.py`; mean of seeds 7/8/9 from `matrix_output.txt`; windows of 80 asks). The cost counts every measurement, including grading and spot checks. Measuring every time would cost 1.0 per ask. At ask 400 the world changes from v1 to v2 (dim 4096 -> 1024, decay 0.7 -> 0.5).

| window | world | reflex rate | reflex accuracy | measurements per ask |
|---|---|---|---|---|
| 1-80 | v1 | 0.42 | 0.97 | 2.38 |
| 81-160 | v1 | 0.86 | 0.995 | 0.84 |
| 321-400 | v1 | 0.93 | 1.00 | 0.53 |
| 401-480 (world changed) | v2 | 0.92 | 0.92 | 0.56 |
| 721-800 | v2 | 0.88 | 0.99 | 0.70 |

- **Consult rate:** falls from 58% to about 7%.
- **After the world changes** (5 of the 37 answers flip): the `trusted` veto rule gives 15.3 wrong reflex answers on average, then accuracy recovers to 0.99. The `parity` rule gives 37.3 wrong answers and is still at 0.93 after 400 more asks.
- **One hostile grader that refutes everything:** reflex rate in the last window is 0.15 under the plain kernel rule `nearest` (30-35 of 37 facts vetoed). It is 0.93 under `parity` and 0.86 under `trusted`, with accuracy 1.00. With no hostile grader, `trusted` gives exactly the same numbers as `nearest`, so `trusted` is the default.

**Real curve** (`replay.py` over the group's own ledger, 347 tell and grade events):
- The share of raised questions that are known went 0 -> 0.11 -> 0.46 -> 0.66 -> 0.86 between minute 14 and minute 17, as peer grades arrived.
- The last checkpoint shows the 4 planted canaries as vetoed.
- Final status of all claims: 74 known, 11 uncertain, 6 claimed, 4 vetoed (the canaries).

## What doesn't work / caveats

- **The curve's workers are simulated.** All four run in one process. The real agents told and graded but rarely called `ask`, so the ask log (`kb.curve()`) is nearly empty. The real curve comes from replaying the ledger, not from logged asks.
- **One refutation is enough.** For an exact question, one refutation from a trusted grader suppresses a fact. A grader needs at least 5 comparable grades before it can be judged unreliable, so a newcomer's first hostile vetoes still count. A colluding majority could also outvote honest graders.
- **Vetoes are permanent.** If the world changes back, the old value stays suppressed.
- **A changed grade leaves the old win in place.** Once a grader has recorded a win, changing its grade to a refutation does not remove that win. `audit()` lists these as `superseded`, but `ask` still counts them.
- **`world.py` changed during the run.** It now takes the majority of 5 draws and generates random draws in batches. I announced the change on the channel. Claims told before it involved stable answers and still reproduce.
- **No generalization across similar questions.** With `MIN_SIM = 0.70` only the same question counts as a match. That is deliberate for facts; `KB(min_sim=0.45)` allows generalization.

## Next steps

1. Route real decisions through `kb.decide()` so the consult rate is logged from real use.
2. Track grader reliability per domain, and let it decay over time.
3. Connect `suspects()` to reasoner's `stale()`, so claims are re-graded automatically when a premise is vetoed.
4. Let a newer trusted reproduction lift an old veto (time-ordered vetoes), so the KB can recover if the world changes back.
5. Try a domain where generalization is wanted, with `min_sim` around 0.45.
