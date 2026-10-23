---
name: ada
description: Build, load, tune and ask Ada models in Ada Cloud through the Glyphh connector's ada_* tools. Use when the user wants software (or Claude) to decide something the way it was decided before (route a ticket, pick the fix for an error, triage a lead, approve or refuse, apply a policy), to load a history of past cases and outcomes so the next case is answered from precedent, to backtest or tune such a model, to read one of its answers, or to call it from their own code with an API key; or asks about Ada, Ada Cloud, a model's spec, which Ada version a model runs or upgrading it (Ada versions, betas, deprecations), or the Glyphh SDKs.
---

# Ada

An Ada model is a spec (what a case looks like, what the outcomes are, what each mistake costs) and its precedents:
past cases with their outcomes. A new case is answered from the precedents closest to it: the outcome of least
expected cost, calibrated probabilities, whether a person should decide instead, and the precedents it stands on. The
same question always gets the same answer, no language model is in the path, and the model says when it does not
know. It learns one confirmed case at a time.

Glyphh runs it: Ada Cloud, at `https://ada.glyphh.ai`. There is nothing to install, deploy or host, no repository and
no code to write for a model: the spec is JSON, and you write it with the user.

## How you reach it

Through the Glyphh connector, `https://api.glyphh.ai/mcp`, added once in Claude (Settings, Connectors) and signed in
with Google or GitHub. Its Ada tools:

| Tool | Does |
|---|---|
| `ada_models`, `ada_model {name}` | The org's models, each with its Ada version; one with its spec, active version, size, settings, its Ada version and any notice about it |
| `ada_model_create {name, spec, ada?}` | A model from its spec: version 1, empty, on the latest stable Ada unless `ada` names another |
| `ada_spec_update {name, spec, note}`, `ada_model_delete {name, confirm}` | A new version of the spec; delete a model (`confirm` repeats its name) |
| `ada_record {name, data, outcome?}`, `ada_record_many {name, cases}` | One case, or up to 1,000 `{data, outcome?, outcomes?, ts?}` |
| `ada_grade {name, id, value, output?}`, `ada_forget {name, id}` | An outcome on a case already in; forget one case |
| `ada_import {name, format, mapping?, content?, rows?}` | An import, as a job: a one-hour upload link for the file, or the file's text or its rows inline (5 MB) |
| `ada_job {id, wait_seconds?}` | Any job's state and progress, waiting up to 50 s for it to end; a done export's download link |
| `ada_learn {name}`, `ada_calibrate {name}` | Weigh the roles from the precedents, then calibrate; calibrate alone. Jobs |
| `ada_decide`, `ada_query`, `ada_probabilities`, `ada_facts` `{name, data, ...}` | Ask |
| `ada_backtest {name, candidates, holdout?, ada?}` | Score the live version and candidates on held-out cases, the live model untouched; `ada` (or a candidate's own `ada`) scores on another Ada version. A job |
| `ada_settings {name, changes?, note?, backtest?}` | Every lever; with changes, a new version |
| `ada_versions {name}`, `ada_activate {name, version}` | A model's versions, who made them and why, and the Ada version each runs; roll back |
| `ada_releases` | Every Ada version: its status (stable, beta, deprecated, retired), dates, release notes and how many of the org's models run it |
| `ada_upgrade {name, ada?, note?, backtest?}` | Move a model to another Ada version (none: the latest stable), re-encoded as a job; the new version is live when it is done |
| `ada_export {name, format?}` | Everything out, as a job whose done state has a one-hour download link |
| `create_api_key {name, expires_in_days?, clearance?}`, `api_keys`, `revoke_api_key` | A key for the user's code, shown once; the keys; revoke one |

No `ada_*` tools: the connector is not added, or not signed in. Ask the user to add `https://api.glyphh.ai/mcp` in
Claude's Connectors and sign in; never ask for a key or a token in the chat.

A model name is lower case letters, digits and `_ . -`, at most 63. A refusal carries a code: `E_LIMIT` (the plan's
cap: `reason`, `used`, `max`), `E_SPEC` (the spec or a case does not fit it; `path` says where), `E_SPEC_LIMIT`,
`E_SPEC_READING`, `E_FEW_ROLES`, `E_MAPPING`, `E_BUSY` (an import or re-encode is running: wait for its job),
`E_MODEL_MISSING`, and the Ada version ones (below: `E_ADA_UNKNOWN`, `E_ADA_RETIRED`, `E_ADA_DEPRECATED`,
`E_ADA_BETA`, `E_ADA_UNAVAILABLE`). Say what it means in plain words and what to do; never retry a refusal unchanged.

This skill speaks contract 5 of Ada Cloud. When `ada_releases` answers a `contract` above 5, the server knows more
than this plugin: tell the person to update it (`/plugin update glyphh@glyphh`, then reload) before relying on
what is new, and do not guess at fields you do not know.

## Building one with the user

1. **Agree the case.** What comes in (the fields; which are exact values, which free text, which numbers on a scale,
   which an id, which only some callers may see), what the outcome is (a short string: the decision), what each
   wrong answer costs them, and when a person should decide instead. Ask; do not guess the business numbers.
2. **Write the spec** (the format: [references/spec.md](references/spec.md)) and show it to the user in plain words
   before you make it. Choose how each role reads its values with care: a role's reading (`numeric_config`,
   `text_encoding`, `key_part`) cannot change once cases are stored (`E_SPEC_READING`); fixing it takes a new model
   and an import. Then `ada_model_create`.
3. **Load the history.** Read the user's file first and map its columns to the spec's roles with them; leave out
   anything that was only known after the outcome (it would leak the answer).
   - Up to a few thousand rows: `ada_record_many` in chunks of 1,000, each `{data, outcome}` in the spec's shape;
     then `ada_learn`.
   - A file: `ada_import {name, format: "csv" | "jsonl", mapping}` answers a job and an upload link; send the file
     to it (in Claude Code: `curl -sS -T <file> "<upload url>"`), then `ada_job {id, wait_seconds: 30}` until it is
     `done`. A small file (5 MB) can go inline instead, as `content` (its text) or `rows` (the cases). CSV: a header
     names a role by its path (`ticket.what.plan`) or `mapping` maps it (`{"Plan": "ticket.what.plan", "Result":
     "outcome", "Notes": null}`; `outcome.<output>` for a named output, null skips a column).
   - Report what went in: rows, added, replaced (an id held already replaces its row), and the refused rows with
     why (the first are named). An import learns and calibrates at its end.
4. **Learn.** `ada_learn` (after `ada_record_many`; an import already did), a job: follow it with `ada_job`. It
   needs ten graded precedents of two outcomes. What it found is what the cases actually turn on: each role's learned weight (0: it tells nothing), the
   pairs of roles that tell more together, the telling words. Tell the user; it is often the first useful thing they
   learn.
5. **Backtest before trusting it.** `ada_backtest {name, candidates: [], holdout: {newest: 200}}` (a job) scores
   the live version on the newest 200 cases, learned on the rest. Read it with them ([references/tuning.md](references/tuning.md)):
   accuracy, cost, how often it asks, and its accuracy where it did not ask.
6. **Ask it.** `ada_decide {name, data}` with new cases; `include: ["facts"]` (or `ada_facts`) to show why.
7. **Tune** if the numbers call for it (below), and **keep learning:** `ada_record` each outcome the user or the
   world confirms. Never record your own guess as a precedent.
8. **Call it from their code:** below.

## Reading an answer

`ada_decide` answers `{outcome, probabilities, expected_cost, ask, receipts, model, version}`:

- `outcome`: the choice of least expected cost under the spec's costs, from the calibrated `probabilities`
  (`expected_cost` is its cost in the spec's units).
- `ask: true`: a person should decide. Nothing close enough is known, every choice costs more than asking
  (`output.ask`), or the top probability is under the spec's bar (`output.ask_below`). The `outcome` is then only
  the best guess, for the person to see. Ask them, and record their answer.
- `receipts`: the precedents it stands on (`id`, `sim`, `outcome`, `hash`, `author`). Cite them.
- `outputs`, when several named outputs were decided at once: one such answer each.

`ada_query` is the raw vote, `{sufficient, confidence, support, count, top, outcomes, receipts}`: trust `top` only
when `sufficient` and `count` is more than one or two; `confidence` is a similarity-weighted vote, not a
probability. A caller with a lower `clearance` sees less: secured roles are cut from what it reads.

What to expect: on a public credit data set (800 cases learned, 200 held out) the learned, calibrated model matched
Claude judging the same cases on accuracy and on the bank's cost, deterministically, at a tiny fraction of the cost
a decision; a classic model was level with it on cost. Ada's edge is the receipts, the clearances, asking when it
should, and learning one confirmed case at a time, not beating a classic model on numbers: say so when the user has
purely numeric data and needs none of those.

## Tuning, with the user

Every lever is a setting or part of the spec, and every change is a new version you can roll back
([references/tuning.md](references/tuning.md) lists them).

1. Read `ada_model` and `ada_settings`.
2. Propose **one** change at a time, with the reason ("the words decide most tickets; weigh them more").
3. `ada_backtest` the live version against the candidate (`{"settings": {...}}`, or a whole `{"spec": {...}}`) on
   held-out cases.
4. Say what changed in plain words: "asks 12% fewer times, costs 8% less on the last 200 cases, the same accuracy".
   Never score on cases the model learned from: the backtest holds out its own, and so do you.
5. Only when the user agrees: `ada_settings {name, changes, note}` (or `ada_spec_update`) with the reason as the
   note. A change that only reads differently is live at once; one that changes what a stored case carries (the
   learning levers, roles added or taken away, the lexicon) re-encodes the model as a job while the old version
   answers: follow it with `ada_job`.
6. If live results fall, `ada_versions` and `ada_activate` the version before.

What needs code is not a lever: a derived field (a ratio, a weekday) is computed by the caller and sent as a role;
a business rule ("never above $50,000") is applied by the caller around the answer.

## Ada versions

Ada itself has versions, named `ada-<major>-<minor>`: `ada-1-0` is the latest stable today, `ada-1-1-beta` a beta.
Every version of a model runs one Ada version and is always answered by it, so a model's answers never change under
it; moving to another Ada version is the person's choice, made with a backtest in front of them.

- **Say which one a model runs.** `ada_model` shows its Ada and a notice when there is something to say (a newer
  stable exists, it runs a beta, its version is deprecated). Mention it when you show a model, in one line.
- **New models take the latest stable.** Leave `ada` out of `ada_model_create` unless the person asks for another
  by name.
- **A beta** is a newer Ada offered to try: opt in, never the default, chosen only by its name, labelled Beta
  wherever it shows. Its answers can differ; it may be promoted to the next stable or withdrawn. Offer it only with
  a backtest, and say it is a beta.
- **When a newer stable exists** (the notice says `upgrade`), offer it, in this order:
  1. Backtest first: `ada_backtest {name, candidates: [], ada: "<the newer one>", holdout: {newest: 200}}` scores
     the live model and the same spec on the newer Ada on the same held-out cases (each result carries its `ada`).
  2. Say the change in plain words, as for tuning: "on your last 200 cases ada-1-1 gets 2 more right and costs 9%
     less, and asks a person about as often". If it is worse, say so and recommend staying.
  3. Only when the person agrees: `ada_upgrade {name, ada, note, backtest: <the backtest's job id>}`. It re-encodes
     the model as a job while the current version keeps answering; follow it with `ada_job`. When it is done the new
     version is live.
  4. Tell them how to go back: `ada_versions {name}` shows the version before (on the old Ada), and
     `ada_activate {name, version}` makes it live again, as it was.
  Any kept version can be chosen, an older one too (a downgrade). The same Ada again is `E_NO_CHANGE`.
- **Deprecated and retired.** When a new stable ships, the one before is deprecated: its models keep answering, with
  a notice and an end date, and it cannot be chosen for a new model or an upgrade (`E_ADA_DEPRECATED`). On that
  date it is retired and every model still on it is moved to the latest stable automatically (a note says so), so a
  model is never left unable to answer. Tell the person the date, and offer the backtest and upgrade sooner so they
  see the change first. A retired version cannot be made live again (`E_ADA_RETIRED`).
- **The refusals** each name the latest stable as the fix (`latest`): `E_ADA_UNKNOWN` (no such name: check
  `ada_releases`, never guess another), `E_ADA_BETA` (a beta closed to new models), `E_ADA_UNAVAILABLE` (that Ada
  is not on this deploy: tell support, with the trace id).
- `ada_releases` lists them all with release notes; the `/glyphh` panel's Plan section shows the org's models by
  Ada version and any deprecation.

## Calling it from code

`create_api_key {name}` makes a key, shown once (`clearance` below 1 for a caller who may not see the secured roles;
`expires_in_days` for one that should lapse): the user keeps it as a secret (`GLYPHH_API_KEY` in their environment or
secret store), never in the chat, a file in the repository, or a commit. Then:

```python
from glyphh import Ada                      # pip install glyphh

d = Ada().decide("tickets", {"ticket": {"what": {"plan": "pro", "text": "charged twice"}}})
if d.ask: send_to_a_person(d)               # d.outcome is the best guess
else: act(d.outcome)
```

```ts
import { Ada } from "@glyphh-ai/glyphh";   // npm i @glyphh-ai/glyphh

const d = await new Ada().decide("tickets", { ticket: { what: { plan: "pro", text: "charged twice" } } });
```

Or `POST https://ada.glyphh.ai/v1/decide {model, data}` with `Authorization: Bearer <key>`. The SDKs also make
models, import files, backtest, tune and export, with typed errors (`LimitError`, `SpecReadingError`, ...), and know
Ada versions (3.3 and later): `ada.ada.versions()`, `create_model(..., ada=)`, `model.info().ada`,
`backtest(ada=)`, `upgrade(ada=)`, a warning when a model runs a deprecated Ada, and `ClientTooOldError` when the
server is newer than the SDK (upgrade it).

## Limits

Precedents are counted across the org's models, against the plan: Free 1,000, Basic 10,000, Pro 100,000, Team 1,000,000. A write
or import past it is refused whole (`E_LIMIT`, `reason: "precedents"`, with `used` and `max`); an import with
`partial` records up to the cap. Tell the user nothing was recorded past it and that a plan with a higher cap lifts
it (`plan` and `upgrade` on the connector). Reads (`decide`, `query`, `probabilities`, `facts`; a decide per output)
count against the plan's month (Free 5,000, refused past it with `E_LIMIT` `reason: "requests"`; Basic
50,000, Pro 1,000,000 and Team 5,000,000 go on past theirs, metered), and calls a second against its rate (`E_RATE`, wait as `Retry-After` says). A model over 100,000 precedents asked with under half its voting roles is
refused (`E_FEW_ROLES`): ask with more of the case. A spec is at most 64 KB, 64 roles, 20 named outputs, 200 values
an output, `k` 200, `dimension` 8,192. `ada_export` gives everything back (precedents, every spec version, what was
learned) as a zip, which `ada_import` takes into a new model of the same spec.
