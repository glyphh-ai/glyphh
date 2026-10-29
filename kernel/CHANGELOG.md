# Changelog

Every release of Ada's kernel, newest first. Each says whether it **changes answers**.

## The rule

A release is **answer-changing** when the same spec, the same precedents and the same learned state can give a
different answer after it than before: another outcome, other probabilities or expected costs, another `ask`, other
receipts or fact trees, other glyphs (the encoding), or other weights and temperatures from `learn` and `calibrate`.
Anything in the maths, the encoding, learning or calibration that moves even one answer counts, bug fixes included.

A release is **compatible** when no answer can change: speed, memory, storage, packaging, a crash fixed (no answer
was given before), and new things a spec must ask for (a new setting whose default keeps today's answers).

The version says which:

- **PATCH** (3.12.1 → 3.12.2): always compatible. A model made on 3.12.1 can be served by 3.12.2.
- **MINOR** (3.12 → 3.13): every answer-changing release is at least a minor. A minor that changes no answer says
  "compatible" here.
- **MAJOR** (3 → 4): the store's layout changed (`glyphh_postgres.STORE_FORMAT`) or a spec stops parsing. A major
  reads the stores of the major before it.

`glyphh_kernel.__version__`, `pyproject.toml` and the newest heading here always agree (`test_versions.py`). Every
release is tagged `v<version>` on `main`.

Ada Cloud shows these releases to customers under names of its own (`ada-1-0`, `ada-1-1-beta`, ...); each name maps
to one release here. The server's `src/glyphh_ada/ada_versions.json` holds that map and these notes in prose.

## 3.15.0 — 2026-10-28 — compatible

**Typed outputs and discriminated unions.** A named output's `kind` says what its answer is: `choice` (the
default, as before), `score` (ordered `values`: a mistake costs the levels it is off, `decide` adds the expected
`level`), `noul` (yes or no: recorded `true`/`false`, `decide` adds `p`, P(true)), `number` (`number: {min, max,
step}`: recorded as a number and learned by its bin, `decide` adds the expected `value`) and `many` (any of its
`values` at once: recorded as a list, each value a noul of its own stored as `<name>--<i>`, `decide` answers the
list and each value's P(true)). `when: {"output", "in"}` makes an output a union's branch: `decide_all` decides the
output it hangs on first and answers a branch not taken `{"outcome": null, "applies": false}`, and a record that
grades a branch its own outcome leaves out is refused (`E_OUTPUT_WHEN`). docs/multi-output.md, Typed outputs.

- Compatible: a spec that names no `kind` or `when` parses, stores and answers exactly as on 3.14.0. Nothing stored
  changes: the encoding (3) and the store's layout (`STORE_FORMAT` 1) are 3.14.0's. A spec that uses them does not
  parse on 3.14.0 or before.
- TypeSafe's Security Incidents workflow (benchmarks `typesafe-workflows/typed_outputs.py`, the consensus action;
  Jev 59.4% on dev, five folds, and 54.0% on test): flat choices 49.8% / 56.0%; nouls and scores as `score` 49.4% /
  56.0%; nouls as `number`, learned from the consensus's own P(true), 50.6% / 52.0% (the expected `value` 45.2% /
  56.0%); the containment questions as `when` branches of triage 49.8% / 56.0%. The kinds give each question its
  true type and the union skips what the workflow never asks; none moves the score here.

## 3.14.0 — 2026-10-25 — answer-changing

**Time can weigh: calibrate fits a recency half-life.** With `settings.recency` (on by default), `calibrate` also
tries half-lives of 1/16 to 2 times the span of the model's graded precedents, each held-out precedent asked at
its own time. It keeps the half-life that best beats none, by at least 1% of the log-loss (or by cost with
`calibrate_by: "cost"`), and keeps none otherwise. A read is then asked at the case's own time (`temporal_source`)
or now, and each precedent's voice in the vote and the probabilities is halved per half-life of age. The
half-life is kept in the store (`meta.half_lives`, per output; `Space.half_life()`). A model whose precedents span
under a day never gets one. With `recency: false` every voice stays whole.

**A lever, off by default: `settings.level_weights: "roles"`.** A segment then weighs its roles' weights summed,
and a layer its segments' summed, so learned weights can quiet a whole segment of uninformative roles. The default
stays `"spec"`, the weights as before. On German Credit `"roles"` decided worse (cost 125 against 99; learned from
its own store, 115 against 102), so it is for a backtest on a model whose segments hold many quiet roles.

- Changes answers only where `calibrate` fits a half-life: models whose graded precedents span at least a day and
  whose answers drift with time. Nothing stored changes: the glyphs, the encoding (3) and the store's layout
  (`STORE_FORMAT` 1) are 3.13.0's.
- German Credit (the benchmark's `calibrate.py`): every answer is the same as 3.13.0's (`decide` with costs 70.5%,
  cost 99; learned from its own store 69.0%, cost 102). Its cases carry no time, so no half-life is fitted.
  Banking77 is the same too. Neither benchmark has time in it: recency is checked on a drifting store in
  `test_versions.py`, not on a public benchmark.
- New: `Space.half_life`, `Space.set_half_life`, `query(now=)`, `probabilities(now=)`, `calibrate(recency=)`.

## 3.13.0 — 2026-10-23 — answer-changing

**A pair value the model never learned no longer votes.** Once `learn` has found a pair of roles that tell more
together than apart (`interactions`), a query whose pair value it never learned (never seen, or seen fewer than
`rare` times) used to weigh that pair at its full weight, and the value matched nothing; now the pair weighs 0 for
that query, so the two roles' own weights decide. On the compiled-reasoner experiment's held-out combinations of AND
rules a learned model had fallen to 56.5% against plain kNN's 75.9% for this reason (research/compile, REPORT.md).

- Changes answers only for models that learned pairs (`settings.interactions`, on by default), and only for queries
  whose pair value is new to the model. Nothing stored changes: the glyphs, the encoding (3) and the store's layout
  (`STORE_FORMAT` 1) are 3.12.2's.
- German Credit (800 learned, 200 held out, the benchmark's `calibrate.py`): the learned vote 78.0% (3.12.2: 77.5%);
  `decide` with costs 70.5%, cost 99 (70.0%, 100); asking where every answer costs over 0.5, 113 decided at 80.5%
  (111 at 81.1%); learned from its own store as it filled 69.0%, cost 102 (69.5%, 101). Within noise either way.
- New: `glyphh_kernel.__version__`, `glyphh_postgres.STORE_FORMAT`, this file.

## 3.12.2 — 2026-10-22 — compatible

A Postgres store already made opens with no DDL and no lock, so opening a model no longer waits out every write to
it. Ada Cloud launched on this release.

## 3.12.1 — 2026-10-21 — compatible

`PostgresStore` indexes each partition's ids itself: looking a precedent up by id no longer scans the whole index.

## 3.12.0 — 2026-10-21 — compatible

The storage interface (`Store`, `SqliteStore`, `glyphh_postgres.PostgresStore`) with shortlisted reads on Postgres;
on SQLite every answer is the same, guess for guess, on Banking77 and credit. Also: the lexicon setting is each
model's own; LRU symbol caches; `forget`; `record_many`; `output.ask_below` (asked for by the spec); the lexicon and
the Postgres store install with the kernel.

## 3.11.0 — 2026-10-20 — compatible

Named outputs: one model answers several questions about one case (`outputs`, `record(outcomes=)`, `grade`,
`decide_all`). A spec without outputs reads exactly as before.

## 3.10.1 — 2026-10-20 — compatible

`learn` leaves roles that carry sets alone instead of crashing on them.

## 3.10.0 — 2026-10-19 — compatible

A store opened read-only: every read works, every write is refused before the file is touched.

## 3.9.0 — 2026-10-17 — answer-changing

Word evidence: what each word says of each outcome weighs on the vote (`word_evidence`, default 2; Banking77 83.4%
to 88.0% inside its training set).

## 3.8.0 — 2026-10-17 — answer-changing

The lexicon (WordNet 3.0, Moby) ships with the kernel and every text role reads through it; learned word pairs (off
by default); a store restated on open when the settings changed what a bag of words carries.

## 3.7.0 — 2026-10-17 — answer-changing

The levers are settings in the spec, changeable live; the learning constants become settings with the same defaults,
and a change of a learning lever relearns.

## 3.6.0 — 2026-10-17 — answer-changing

Learned word weights; a weighted set.

## 3.5.0 — 2026-10-17 — answer-changing

Learned pairs of roles (interactions); the temperature fitted on cost; a store rewrite.

## 3.4.0 — 2026-10-17 — answer-changing

A subtree that weighs nothing is out of the mean, in the fact tree and the fast path.

## 3.3.0 — 2026-10-17 — answer-changing

A priced `ask` in `decide`; a model learns from its own store and refreshes as cases arrive.

## 3.2.0 — 2026-10-17 — answer-changing

Learned role and value weights, costs and `decide`; exact weighted scores in one pass.

## Before 3.2.0

The Glyphh spec, fact trees and calibrated probability (encoding 3), and the kernel as one file. Not released as
versions.
