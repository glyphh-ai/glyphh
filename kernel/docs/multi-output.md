# Multi-output models

Status: kernel and spec built in glyphh-kernel 3.11.0 (order of work steps 1–3); rrotor, the SDKs and the
contract follow.

## The problem

A model today has one spec, one store and **one outcome per precedent**. A decision that needs several answers
about the same case — TypeSafe's security workflow asks 14 questions of one alert; an incident needs a fix, an owner
and a severity — needs one model per answer: 14 specs, 14 stores, 14 deploys, each case recorded 14 times. Jev answers
any number of questions about one state in one request. Ada should answer any number of decisions about one case
from one model.

## The shape

One model, one spec, one store. A precedent is recorded **once**, with its situation, and carries **named outcomes**:
`{"is_true_positive": "z4", "attack_type": "account_takeover"}`. Each output learns, calibrates and decides on its own;
the situation, its glyph and its encoding are shared.

```json
{"name": "security", "layers": [...],
 "outputs": {
   "is_true_positive": {"values": ["z0", "z1", "z2", "z3", "z4"]},
   "attack_type":      {"values": ["host_compromise", "account_takeover", "mail_campaign", "exfiltration"]},
   "action":           {"costs": {"AUTO CLOSE": {"ACT": 5}}, "ask": 0.6}
 }}
```

- `outputs` names each output. `values` (optional) is its closed set: a record outside it is refused (E_OUTPUT_VALUE).
  `costs` and `ask` are today's `output.costs` and `output.ask`, per output.
- A spec without `outputs` is today's model: one unnamed output, `"default"`. Every existing call, store and spec
  works unchanged.

## The store

- New table `outcomes (id TEXT, output TEXT, value TEXT, ts REAL, PRIMARY KEY (id, output))`. The precedent row keeps
  its situation and glyph once.
- `precedents.outcome` stays, as the `default` output, so older files open with no migration and older kernels can
  still read a file written without named outputs.
- A precedent may carry **some** outputs and not others: graded for those, ungraded for the rest. (The security
  workflow's containment questions are answered only on the cases that act.)

## The API (kernel, spec and SDKs alike)

| Call | Today | Multi-output |
|---|---|---|
| Record | `record(data, outcome)` | `record(data, outcomes={name: value, ...})`; `outcome=` still means `default` |
| Grade later | re-record | `grade(id, output, value)`: add or replace one output's outcome on a held precedent |
| Read | `query(data)`, `probabilities(data)`, `decide(data)` | the same, with `output=` (default `default`) |
| Many at once | — | `decide_all(data, outputs=None)`: every output (or the named ones) in one call, one glyph comparison |
| Learn | `learn()`, `refresh()`, `calibrate()` | per output by default, `output=` for one |

`decide_all` is the Jev-shaped call: one case, every answer, one pass over the store.

## Learning, per output

Everything learned today is learned against the outcome, so it is kept **per output**, in `meta` under
`learned:<output>`, `tau:<output>`, `evidence:<output>`:

- **role weights and value weights** — applied at query time (`Spec.weights`), so one store serves every output's
  table.
- **calibration** — one temperature per output, fitted on that output's graded precedents.
- **word evidence** (PMI) — per output, as now per store.
- **interactions** — per output, added as query-time layers, not written into stored situations.

Word weights and interactions are part of a situation's glyph (a weighted bag, a pairs layer), so the stored
situations can carry only one table. As built: **a named output never rewrites the store.** The store holds each
case as recorded (the `default` output still rewrites it, as before, so a spec without `outputs` is unchanged). A
named output whose learned word weights or interactions differ from the store's reads it through a **view**
(`Space.view(fn)`): the same precedents, ids, outcomes, events and temperatures in memory, each situation passed
through the output's `restate` and its glyph made again. A view is kept current: cases added since are appended,
outcomes and temperatures copied on every read; a precedent changed or replaced rebuilds it, as does relearning.
Calibration runs on the view and the store keeps the temperature (`Space.set_tau`). An output whose tables are the
store's reads the store itself.

## Precedents and limits

A precedent counts once against a plan's `max_precedents`, however many outputs it carries: 239 security cases are
239 precedents, not 3,346.

## rrotor and the SDKs

- `rrotor.ada` passes `outcomes=`, `output=` and `decide_all` through; a model's `glyphh.json` functions name them.
- `glyphh` (PyPI) and `@glyphh-ai/glyphh` (npm): `Model.record(data, outcomes=...)`, `Model.grade(id, output, value)`,
  `Model.decide(data, output=...)`, `Model.decide_all(data, outputs=...)`.
- The runtime's REST contract (`glyphh-ai/glyphh/contract`) gains the same fields.

## Order of work

1. Kernel: the `outcomes` table, `record(outcomes=)`, `grade`, `output=` on reads, per-output `meta`; `default`
   keeps every existing test green.
2. Spec: `outputs` parsed and validated; per-output weights, calibration, evidence, interactions; word weights read
   at query time.
3. `decide_all`.
4. rrotor's `rrotor.ada` and an example model; the Ada part (version bump).
5. SDKs and the contract; then the security benchmark's Ada as one model.

## Typed outputs (kernel 3.15.0)

An output's `kind` says what its answer is. A spec that names no kind is a choice, and decides as before.

| kind | the spec | recorded as | `decide` adds |
| --- | --- | --- | --- |
| `choice` | `values` (optional) | one of them | — |
| `score` | `values`, two or more, in order | one of them | `level`: the expected level (0 = the first) |
| `noul` | nothing (its outcomes are `"false"`, `"true"`) | `true`/`false` or the strings | `p`: P(true) |
| `number` | `number: {min, max, step}` | a number (kept as its bin) | `value`: the expected number |
| `many` | `values`, two or more | a list of them | `outcome` is a list; `probabilities` each value's P(true) |

- **Ordered mistakes.** A score's or a number's mistake costs how many levels (bins) it is off, where `costs` names
  no price for the pair, so the least-cost outcome is the median, not the mode. A choice's mistakes still all cost 1.
- **A number** is learned by its bins (at most 1,000); each outcome is a bin's midpoint as printed (`"45"`).
- **A many output** is its values' nouls: member outputs `<name>--0`, `<name>--1`, ... in the store, each learning
  and calibrating on its own. `outputs()` and `to_json()` name only the many output; it takes no costs or ask.
- **A discriminated union.** `when: {"output": "kind", "in": ["bug"]}` asks an output only when another's outcome
  is one of those. `decide_all` decides the one it hangs on first (asked for or not) and answers the branch not
  taken `{"outcome": null, "applies": false}`; a branch taken says `"applies": true`. A record that grades a branch
  its own outcome of the other leaves out is refused (E_OUTPUT_WHEN). The output hung on is a choice, a score or a
  noul; whens may chain and may not go round. `decide` alone does not check the branch.

## Open questions

1. ~~Should an output be able to name the outputs it depends on?~~ Yes, since 3.15.0: `when` (Typed outputs).
2. Should `values` be required? Proposed: optional; an open set is today's behaviour.
