# Tuning a model

Every lever is a setting (`ada_settings {name, changes, note}`) or part of the spec (`ada_spec_update`). Each change
is a new version, kept with who made it, why (the note) and the backtest that chose it; `ada_versions` lists them and
`ada_activate` makes an earlier one active again, with what it had learned.

## The settings

| Setting | Default | What it does | A change is |
|---|---|---|---|
| `k` | 15 | How many nearest precedents a case's vote is over (cloud: at most 200) | Live |
| `min_sim` | 0.10 | The similarity a precedent needs to vote: higher means "say nothing rather than guess" | Live |
| `word_evidence` | 2 | How much a case's words, by what each says of each outcome, weigh on the vote (0: not at all) | Live |
| `word_weights` | true | Learn a weight per word of a text role (which words matter) | Re-encoded |
| `word_floor` | 0.35 | The least a learned word weighs: lower lets the telling words dominate | Re-encoded |
| `interactions` | true | Learn pairs of roles that tell more together than apart | Re-encoded |
| `max_interactions` | 5 | How many such pairs at most (0 to 50) | Re-encoded |
| `rare` | 5 | A value, word or pair seen fewer times is not learned from | Re-encoded |
| `word_pairs` | false | Learn pairs of words ("top" + "up"), for intents that are phrases | Re-encoded |
| `max_word_pairs` | 20 | How many word pairs at most (0 to 200) | Re-encoded |
| `lexicon` | true | Read words through WordNet and Moby, so related words correlate | Re-encoded |
| `calibrate_by` | loss | `loss`: probabilities that mean what they say; `cost`: that decide best by the costs | Live, then recalibrated |
| `calibrate_sample` | 200 | The newest precedents a calibration holds out | Live |
| `refresh_every` | none | Learn and calibrate again every so many precedents, as a job | Live |
| `shortlist` | 1,000 | How many candidates a big model's read re-ranks exactly (0: read every precedent) | Live |

In the spec: a role's or layer's `similarity_weight` and `security_weight`, the `costs`, `ask` and `ask_below` of
each output, and `report` are live; roles added or taken away, declared `interactions`, `seed` and `dimension` are
re-encoded; a role's reading cannot change (`E_SPEC_READING`: a new model and an import).

"Live" is active at once on the same precedents. "Re-encoded" is a job (`ada_job`): the precedents are restated for
the new version into a store of its own, which learns before it goes live, while the old version answers; a rollback
to it is at once. One import or re-encode runs at a time on a model (`E_BUSY`).

## The backtest

`ada_backtest {name, candidates, holdout?, output?}`:

- `candidates`: up to ten, each `{"settings": {...}}` (the live version with those changed), `{"spec_version": n}`,
  or `{"spec": {...}}`, with an optional `name`. The live version is always scored too, as `active`.
- `holdout`: `{"newest": 200}` (the default: the newest 200 graded cases) or `{"fraction": 0.2, "seed": 7}`. Each
  candidate learns and calibrates on the rest, then decides every held-out case. The live model is never touched.
- The answer, for `active` and each candidate: `accuracy` (decide's), `top_accuracy` (the plain vote's),
  `log_loss`, `cost` and `cost_mean` (by the output's costs), `ask_rate` and `accuracy_answered` (its accuracy where
  it did not ask), `coverage`, `calibration_error`, `mistakes` (`{truth: {decided: count}}`), and for a candidate
  `change` against `active`.

Read it to the user as plain differences, on the held-out cases: "asks 12% fewer times, costs 8% less, the same
accuracy on the last 200". A candidate with too few cases to learn from is scored unlearned and says so; a spec that
reads a role differently is answered with its refusal.

## What usually helps

- Text decides the case (tickets, intents): `word_evidence` up (2 to 3), `word_pairs` on for phrase-like intents.
- Few, noisy precedents: `rare` up, `k` up.
- It guesses where it should not: `min_sim` up, or `ask_below` up in the spec.
- The costs matter more than being right: `calibrate_by: cost`.
- A role learned to near 0 tells nothing: leaving it in costs nothing, and taking it away is a re-encode.

One change at a time, each backtested, each applied only when the user agrees, with the reason as its note.
