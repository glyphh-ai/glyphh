# Cold-test results: glyphh kernel

Evaluator: Claude (cold, spec + source only). Files: `opsbot.py` (the
application), `run_log.json` (full decision log), `wins.db` / `vetoes.db`
(kernel persistence, written by the kernel itself).

## What I built

**opsbot**: an automated incident-remediation agent. The world is a
deterministic simulator: 4 services x 4 symptoms, each pair has one
correct action among 5 (restart / failover / scale_up / rollback /
throttle); `region` and `load` are decision-irrelevant attributes.
Grading is programmatic: action == truth. The fallback consultant is a
noisy oracle (80% correct). At step 200 the world drifts: the correct
action for (payments, latency) changes from `scale_up` to `restart`,
to exercise the veto path. Every decision goes through the grounded
loop copied verbatim from KERNEL.md: wins Space -> confidence >= 0.5
gate -> vetoes Space check -> fallback; the world grades; the outcome
is recorded into wins or vetoes. Both Spaces persist via the kernel's
own SQLite path (`Space(path=...)`). 400 decision steps.

## Metrics

| Quartile | steps | consult rate | success rate |
|---|---|---|---|
| Q1 | 0–99 | 0.900 | 0.760 |
| Q2 | 100–199 | 0.700 | 0.850 |
| Q3 | 200–299 (drift at 200) | 0.640 | 0.850 |
| Q4 | 300–399 | 0.450 | 0.840 |

Overall: 400 steps, consult rate 0.672, success rate 0.825.
Wins space: 330 rows. Vetoes space: 70 rows.

Reflex vs fallback accuracy:

| | n | accuracy |
|---|---|---|
| reflex (overall) | 131 | 0.824 |
| consult (overall) | 269 | 0.825 |
| reflex Q1 | 10 | **0.300** |
| reflex Q2 | 30 | 1.000 |
| reflex Q3 | 36 | 0.806 |
| reflex Q4 | 55 | 0.836 |

The consult rate does fall as promised (0.90 -> 0.45) and mature
reflexes (Q2, pre-drift) are excellent. But overall reflex accuracy is
no better than the 80%-accurate noisy oracle, for two reasons detailed
below: early cross-situation false reflexes, and post-drift veto
leakage.

### Demo A: confidence gate on novelty

- Fully novel situation (`quantumdb`/`bitflip`/`mars-1`/`singularity`):
  `sufficient=False, confidence=0.0, support=0.042, top=None`. The gate
  declines cleanly. PASS.
- **Partially** novel (novel service+symptom, familiar region+load):
  `sufficient=True, confidence=0.404, top="throttle"`. The Space claims
  sufficiency on a (service, symptom) it has never seen, on the
  strength of shared *irrelevant* attributes. The loop still consulted
  only because confidence happened to fall under 0.5 — the `min_sim`
  "insufficient" gate did not protect at all. See gap 2.

### Demo B: veto vs the discredited reflex

Post-drift trace for (payments, latency), old truth `scale_up`, new
truth `restart`:

```
203 consult restart  True     253 consult failover False
208 consult restart  True     263 consult restart  True
213 reflex  scale_up False    ...
223 reflex  scale_up False    313 reflex  restart  True
233 reflex  scale_up False    318 reflex  scale_up False
243 reflex  scale_up False    343 reflex  scale_up False
                              348 reflex  scale_up False
                              383 reflex  restart  True
```

The veto **eventually** works (by ~step 253 the discredited reflex is
mostly suppressed and consults relearn `restart`), and by the end the
reflex fires the *new* correct action. But the discredited reflex
repeated **6 more times after its first graded failure** (steps
223–348). The spec's claim — "a discredited reflex does not fire again
— the entity consults instead of being confidently wrong twice" — is
empirically false under the canonical loop. Root cause: the veto
query's top-15 neighbors include unrelated failures (oracle mistakes
on other situations), diluting `v.confidence` below 0.5; and each
incident's incidental region/load values move the veto's neighborhood,
so blocking is intermittent. One veto row cannot outvote a
similarity-weighted crowd. PARTIAL PASS at best.

## Spec gaps, ambiguities, insufficiencies

1. **"Confidently wrong twice" is overpromised.** KERNEL.md: *"Failures
   become vetoes: a discredited reflex does not fire again."* As shown
   in Demo B, with the canonical loop's `v.confidence >= 0.5` and
   default `k=15`, a single veto is diluted by unrelated failures in
   the veto Space and by incidental-attribute variation. It took ~4
   repeated failures before the veto held, and it relapsed at steps
   318/343/348. The spec should either weaken the claim or prescribe a
   different veto gate (e.g. gate on the veto's *support*/nearest-sim
   for the exact situation+action, or keep per-situation veto spaces).

2. **Two different gates are conflated, and `min_sim` is nearly
   vestigial.** Rule 5 says *"Every query returns confidence, and
   below threshold it says 'insufficient' instead of guessing."*
   In the code, `sufficient` is gated by *similarity* (`min_sim=0.10`),
   while the loop's threshold is on *confidence* (consensus). These are
   different quantities and the spec never says which "threshold"
   rule 5 means. Worse, the default `min_sim=0.10` is far below the
   structural similarity of the encoding: two situations sharing only
   2 of 4 irrelevant attributes measure sim ≈ 0.44, and even a
   *completely different* service+symptom with familiar region/load
   measures ≈ 0.42. So `sufficient=True` for anything sharing a couple
   of attribute values, and "it knows what it doesn't know" is carried
   almost entirely by the confidence consensus, which brings us to:

3. **A singleton neighborhood yields confidence 1.0.** With one (or
   few) precedents in the Space, the top-k is that one row and
   `confidence = 1.0` — maximal confidence from a single example, or
   from a *wrong-situation* example that happens to share incidental
   attributes. This is why Q1 reflex accuracy was 30%: early reflexes
   fired at high confidence off cross-situation bleed (e.g. step 5:
   payments/oom answered `scale_up` because payments/latency had a
   `scale_up` win). The spec's calibration claim (*"answers at
   confidence >= 0.5 were 86% accurate"*) did not transfer to my
   domain in the early regime; nothing in the spec warns that
   confidence is uncalibrated when the Space is sparse, nor suggests a
   minimum support/receipt-count guard. `Answer.support` exists but the
   spec never says what to do with it — the canonical loop ignores it.

4. **No way to weight decision-relevant attributes.** The encoding
   bundles all attr:val pairs equally, so `region` counts as much as
   `symptom`. sim(same pair, different region+load) = 0.435 —
   *identical* to sim(different service+symptom, same region+load) =
   0.438. The spec's "a situation is a flat dict of attributes" gives
   no guidance on attribute selection or weighting; in any domain with
   noise attributes this silently poisons neighborhoods. A sentence
   like "only include decision-relevant attributes" (or a weighting
   mechanism, e.g. repeat-bundling important attributes) is needed.

5. **Events must be replayed identically at query time** for the
   trajectory part to match; the spec never says how sensitive
   matching is to event mismatch (measured: dropping events entirely
   still leaves sim 0.63 to the same situation — so events are a
   minority vote of the bundle, which is not stated).

6. **`decay` is unreachable through Space.** Strand advertises
   `state(decay=0.7)` as tunable, but `Space.encode` hardcodes
   `Strand(events).state()` — no way to use a different decay for
   recorded trajectories without re-implementing `encode`.

## Bugs / API friction in glyphh_kernel.py

- **`bundle` tie-break inconsistency (real bug for non-default dims and
  seeds):** `signs[ties] = symbol("tie-break")[ties] if len(signs) == DIM
  else 1`. (a) For dim != 4096 all ties collapse to +1 — a systematic
  bias, silently different semantics from the default dim. (b)
  `symbol("tie-break")` uses seed 42 regardless of the Space's seed, so
  two agents on a shared non-42 seed still get identical tie-breaks
  from a foreign vocabulary — harmless by luck, but violates the
  "different seeds are mutually random noise" story.
- **`Space.query` weights all top-k rows, even those below `min_sim`**
  (`weights = max(s, 0)` with no min_sim cut). Only the *best* row is
  checked against min_sim; rows at sim 0.05 still vote. This amplifies
  the cross-situation bleed in gaps 2–3.
- **O(n) matrix rebuild on every record→query alternation**: `record`
  sets `_matrix = None`, so the interleaved record/query pattern of the
  grounded loop restacks the full matrix every step. Fine at 400 rows,
  quadratic pain at scale. Incremental append would be trivial.
- **No `close()`** on Space; the sqlite connection is never closed.
  Minor, but "state is handed over" invites copying the file while a
  connection holds it.
- Docstring drift: `Answer.confidence` says "consensus of the k nearest
  precedents" but it is a *similarity-weighted share*, not a count
  consensus; the number is hard to interpret (0.404 in Demo A means
  what, exactly?). Not wrong, but underspecified for a calibration-
  bearing quantity.
- Positive friction, for balance: the persistence Just Worked
  (`Space(path=...)`, zero ceremony, reload-on-open verified), receipts
  are genuinely useful for debugging (they told me exactly which
  cross-situation precedents caused false reflexes), and the grounded
  loop is short enough to copy verbatim, which I did.

## Verdict

**Yes, with caveats** — I could wield the kernel from the spec alone:
the loop ran unmodified, persistence worked first try, consult rate
fell 0.90 -> 0.45 over the run, and the novelty gate declines cleanly
on fully-novel input. But two of the spec's headline promises did not
survive contact: (1) "a discredited reflex does not fire again" — mine
fired six more times; (2) "below threshold it says insufficient" — the
insufficiency gate is effectively decorative once situations share any
attribute values, and early-regime confidence is uncalibrated. A user
who trusts those two sentences literally will ship an agent that is
confidently wrong during exactly the sparse/post-drift regimes where
it matters most. The kernel is usable; the spec oversells its safety
properties and gives no guidance on attribute hygiene, sparse-regime
confidence, or veto strength — all three of which bit me within 400
steps.
