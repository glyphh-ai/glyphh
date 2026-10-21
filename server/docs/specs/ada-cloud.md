# Ada Cloud: the build plan

**Status:** a plan for Chris to decide on, not built. Written 2026-10-21 from `origin/main` of `ada-private` (kernel
3.11.0), `rrotor`, `server`, `glyphh`, `platform` and `web`. Every claim about today cites the file it comes from.

**The direction (Chris, 2026-10-21):** one multi-tenant, Glyphh-run Ada service behind one URL, so a customer needs
no runtime, no repo and no image. The model is TypeSafe AI's Jev: cloud only, one endpoint, typed answers with
probabilities, billed per request. Why: self-hosting rrotor is too hard to get running, and the public image
`ghcr.io/glyphh-ai/rrotor` carries the Ada kernel's source (the IP). Self-hosted rrotor stays, as the Enterprise
option. Glyphh-hosted per-org Fly machines (`GLYPHH_HOSTING`) stay off.

This reverses two standing rulings, and the plan says so where it matters: "nothing of Glyphh's is on the data path"
and "Glyphh's cloud never keeps a copy of the code or the precedents" (`docs/architecture.md`, Architecture and Ada
models), and "Free is a node you run yourself" (`docs/pricing.md`).

---

## 1. The product

**Ada Cloud is Ada as an API.** A customer signs in, makes a key, describes their cases once as a JSON spec, loads
their history, and asks: every answer is typed (the spec's outcomes), comes with calibrated probabilities, the
expected cost of each choice, whether a person should decide instead, and the precedents it stands on. No language
model is in the path, the same question gets the same answer, and the model learns one confirmed case at a time.
Glyphh runs it at `https://ada.glyphh.ai`; Claude reaches it through the one Glyphh connector; software through the
SDKs with only a key.

**End to end:**

| Step | On the platform | From Claude (the Glyphh connector + the Ada skill) | From code (SDK, key only) |
|---|---|---|---|
| Sign in | Google or GitHub (built: `api/auth.py`, `ops/auth/`) | Add the connector `https://api.glyphh.ai/mcp`, one Allow (built: `api/oauth.py`, `ops/connector/`) | — |
| Make a key | API Keys page: name, expiry, clearance; shown once | `create_api_key` | — |
| Define a model | Models, New: a spec editor with a template per use case, checked as you type | The skill agrees the case with the person and calls `ada_model_create {name, spec}` | `ada.create_model(name, spec)` |
| Load history | Models, Import: a CSV or JSONL file, mapped to the spec, run as a job with progress | The skill reads the person's file and sends `ada_record_many` in chunks, or starts an import | `model.record_many(cases)` or `model.import_file(path)` |
| Learn | Learn button; automatic after an import | `ada_learn` | `model.learn()` |
| Ask | Try it panel | `ada_decide`, `ada_query`, `ada_facts` | `model.decide(data)`: `{outcome, probabilities, expected_cost, ask, receipts}` |
| Tune | Settings with a backtest before going live, versions, rollback | `ada_backtest`, `ada_settings` (section 5) | `model.backtest(...)`, `model.settings(...)` |
| Keep learning | — | `ada_record` each confirmed outcome | `model.record(data, outcome)` |

The headline call, Jev-shaped: `POST https://ada.glyphh.ai/v1/decide {model, data}` with `Authorization: Bearer
glyphh_ak_…` answers `{outcome, probabilities, expected_cost, ask, receipts, model, version}`.

---

## 2. What a model is in the cloud

**A model is a spec Glyphh stores, plus its precedent store. No customer code runs.**

Today an Ada model is a GitHub repo of `glyphh.json`, `spec.json` and `model.py`, deployed by commit and run in
rrotor's sandbox (rrotor `docs/architecture.md` section 8; `examples/ada_incidents/`, `examples/ada_tickets/`). But
the spec already carries almost everything: `glyphh_spec.py` parses layers, segments, roles (`similarity_weight`,
`security_weight`, `key_part`, `numeric_config`, `text_encoding`, `lexicons`), `interactions`, `temporal_source`,
`output` (`report`, `costs`, `ask`), named `outputs` (`values`, `costs`, `ask`) and `settings` (14 levers), and
`glyphh_spec.Model` does `record`, `grade`, `learn`, `refresh`, `calibrate`, `configure`, `query`, `facts`,
`probabilities`, `decide` and `decide_all`. The `model.py` files are thin wrappers.

What today's `model.py` files do that a spec cannot, and how the cloud covers each:

| In code today | Where | In the cloud |
|---|---|---|
| A confidence bar on `decide` (`CONFIDENT = 0.6`) and, below it, `ctx.needs_input` to ask a person, then record the answer | both examples' `decide` | Stateless. The kernel's own `decide` already answers `ask: true` with the best guess when the spec prices asking (`output.ask`) or nothing is known (`glyphh_spec.py` `Model.decide`). The caller asks the person and calls `record`. Add one spec field, `output.ask_below` (ask when the top probability is under it), for people who think in confidence, not costs: a small kernel change |
| The nearest precedent's cause, owner and runbook beside the fix (`_resolution`) | `ada_incidents/model.py` | `decide` takes `include: ["facts"]` and returns the top fact tree, cut by `output.report` and the caller's clearance, which is exactly what `_resolution` reads |
| Shaping `learn`'s answer (roles, word counts, pairs) | both | The service formats it, once, for every model |
| `probabilities` that bypass `Model.probabilities` (no word evidence) | both | Gone: the cloud calls the kernel's `Model` methods only. This is a quiet bug in the examples, not a feature |
| `needs_approval` steps, declared hosts, secrets, files (`daily_sales`) | rrotor base | Not Ada. Not in the cloud; rrotor keeps them |
| Learning weights up front with `Spec.learned(...)` in Python before the first commit | Ada skill, step 3 | Import, then `learn` (section 6) |
| Seeding by one `model_call record` per case, a sandboxed run each | Ada skill, step 5 | `record_many` and imports (section 6) |
| Deriving fields (a ratio, a weekday, a lookup) before recording | nowhere yet, but customers will want it | The caller sends derived fields. Not in the spec at launch (section 5, "What needs code") |

**So a cloud model is a pure spec.** Customers write JSON (or Claude writes it with them), never Python.

---

## 3. Architecture

### 3.1 Where it runs

**A separate Fly app, `glyphh-ada`, at `https://ada.glyphh.ai`, built from this repo as a second package
(`src/glyphh_ada/`) with its own Dockerfile target and `fly.ada.toml`.** It shares the server's Postgres, its
error shapes, tenancy and key hashing; it does not share its process.

| | Inside `glyphh-ai-server` | Separate app `glyphh-ada` (chosen) |
|---|---|---|
| Memory | The server is one `shared-cpu-1x`, 1 GB (`fly.toml`). One Pro org at 50,000 precedents is about 800 MB today (16 KB each, rrotor `docs/architecture.md` section 8) | Sized for stores: `performance` machines, memory as the plan needs |
| CPU | The kernel is numpy plus a lot of pure Python (`_fast_scores`, `_explain`, `encode`); learn and calibrate hold the GIL for seconds to minutes and would stall sign-in, OAuth and Stripe's webhook | Ada's load never touches account traffic |
| Scaling | The server scales by request; Ada scales by where each model's store lives (3.4) | Placement by model, machines added by memory |
| The kernel | Every server image would hold the kernel | Only the Ada image holds it; the server image stays kernel-free |
| Deploys | A kernel bump redeploys sign-in | Independent |

### 3.2 Packaging the kernel privately

- **Never a public image.** The Ada image is pushed only to `registry.fly.io/glyphh-ada` (private to the Fly org),
  built in this repo's CI with a read token for `ada-private`.
- **Install the signed Ada part** that rrotor's CI already builds and signs (`part-ada-<version>`, rrotor
  `parts/ada/`, `scripts/part.py`; releases on the private rrotor repo), verifying its signature at build time.
  Fallback: `pip install git+https://…/ada-private@v3.12.0`, but `ada-private/pyproject.toml` lists
  `py-modules = ["glyphh_kernel", "glyphh_spec", "glyphh_nsm"]` and leaves out `glyphh_lexicon` and `lexicon/`, so
  that needs fixing first (kernel step, section 9).
- **The lexicon stays server-side.** `lexicon/words.jsonl.gz` (WordNet 3.0, 2.5 MB) and `grammar.jsonl.gz` (Moby,
  0.9 MB) ship in the image only, read once per process (`glyphh_lexicon.py`), shared read-only by every model. Their
  licences (`lexicon/LICENSES.md`) allow this; the attribution goes in the service's legal notices.

### 3.3 Tenancy and isolation

- **Ids, not names, on disk.** A store's path is `/data/stores/<org uuid>/<model uuid>/<version encoding>.sqlite`,
  made from database ids, never from anything a caller typed.
- **The key decides the org; nothing in the body does.** Every request resolves its key or sign-in to `(org, user,
  clearance)` before it touches a model; a model is looked up by `(org_id, name)`.
- **RLS on every new table, failing closed.** Today's policies let a connection with no org set see every row
  (`db/schema.sql`: `nullif(current_setting('glyphh.org_id', true), '') IS NULL OR …`; `db/tenancy.py`). That is
  right for sign-in and the webhook; it is wrong for customer data. The Ada tables get a strict policy (`org_id =
  current_setting('glyphh.org_id')::uuid`, no bypass) and the Ada app connects as its own role, which cannot read
  the account tables it does not need.
- **No customer code runs,** so no sandbox is needed: the attack surface is JSON the kernel parses
  (`Spec.from_json` validates exactly and names the path of any fault) and data in the spec's shape.
- **Bounds a spec cannot exceed in the cloud:** `dimension` at most 8,192 (the kernel allows 65,536,
  `_parse_spec`; at 65,536 one precedent is 256 KB of float32), at most 64 roles, 20 named outputs, 200 values per
  output, `k` at most 200.
- **Kernel globals that must become per-model first** (section 9, step 0):
  - `glyphh_lexicon.LEXICON.enabled` is one flag per process, set by `Model._apply()` from the model's `lexicon`
    setting: two models with different settings in one process flip it for each other, and the lexicon's glyph
    cache key `(word, seed, dim)` does not include it.
  - `glyphh_kernel._SYMBOLS` is an unbounded process-wide cache of 4 KB glyphs: across tenants it grows without
    limit. It needs a bound (an LRU).
  - Neither leaks one tenant's data to another (a symbol is a hash of a public key and seed), but both are
    correctness and memory problems in a shared process.

### 3.4 Where a model's precedents live

**Chosen: one SQLite file per model on the Ada machine's Fly volume, replicated continuously to object storage
(Litestream to Tigris, Fly's S3), with each model owned by one machine.** The model registry, spec versions, keys,
usage and audit are in Postgres.

| | Per-model SQLite on volumes (chosen) | Postgres tables |
|---|---|---|
| Kernel | Unchanged: `kernel.Space` opens a SQLite path, WAL, and commits each write (`_open`, `record`); rrotor and every benchmark use exactly this | `Space` touches `self._db` in 60 places (`glyphh_kernel.py`); it needs a storage interface first: 1 to 2 weeks and a new failure mode in the hottest code |
| Serving | The kernel holds the whole store in RAM and serves from there (`Space.__init__` loads every row; `_matrix`, the leaf tables). A model is served by one process whichever store is chosen, so a model has an owner either way | The same owner is needed; Postgres only moves the durable copy |
| Scaling past one machine | Placement: `ada_placements(model_id, machine_id)` in Postgres; any machine that gets a request for a model it does not own answers `fly-replay: instance=<owner>` (the pattern the doorman already uses, `docs/architecture.md`, Reaching a runtime). New machines take new models; a model moves by snapshot and restore | Any machine can load any model, but two must not write it, so placement is still needed |
| Backups | Litestream: every WAL frame shipped within a second; point-in-time restore; daily snapshots kept 7 days | Managed Postgres backups |
| Size | About 4 KB of glyph plus the situation's JSON per precedent on disk | The same 4 KB per row as `bytea`, on the managed database, at its price |
| Export and delete | A model is a file: export is that file (or JSONL from it), delete is the file and its replica prefix | Rows |
| Failover | A dead machine's models are restored from Tigris onto another machine: minutes, not seconds (stated in the SLA) | Faster restore, same reload time |

Postgres is the better long-run answer only if the kernel gets a storage interface anyway; revisit when a single
model outgrows one machine's RAM.

### 3.5 Models in memory, concurrency, cold start

- **One worker process per machine at launch,** a `glyphh_spec.Model` per open model held in an LRU by memory, not
  count. A model is evicted (closed; its file stays) when the machine passes its budget; the largest paid stores are
  pinned.
- **One thread per open model.** Python's `sqlite3.connect` defaults to `check_same_thread=True`, and the kernel
  opens its connection in `Space._open`, so each model's calls run on its own single-thread executor: writes to a
  model are serialised (as the kernel needs), different models run side by side, numpy matrix products release the
  GIL. More cores later means more worker processes, each owning a share of the machine's models.
- **Memory today:** about 16 KB of RAM per precedent: the float32 `_matrix` (16 KB at 4,096), the int8 glyph (4
  KB) and the leaf tables. A spec model always queries with weights, which takes `_fast_scores` and never touches
  `_matrix` (`Space._scores`), so making `_matrix` lazy should bring it to about 5 KB. Kernel step 0 measures it; the
  plan caps in section 7 assume it.
- **Named outputs cost more:** each output whose learned word weights differ reads through its own in-memory view
  of the store (`Model._space_for`, `Space.view`), a second copy of the glyphs. Count it in the memory budget.
- **Cold start:** opening a store reads every row and rebuilds the leaf tables (`Space.refresh`, `_leaf_add`). 10,003
  precedents recorded from scratch take about 4 s in memory (rrotor `benchmarks/banking77/README.md`, Cost and
  time); a load from SQLite skips the encoding of whole cases but not of leaves. Estimate 1 to 2 s per 10,000, so
  500,000 is about a minute: measure in step 0, keep big stores resident, and answer `503 E_WARMING` with
  `Retry-After` while one loads.
- **Limits per request:**

| | Limit |
|---|---|
| Body | 1 MB (`record_many`: 5 MB) |
| `record_many` | 1,000 cases |
| `facts` `top` | 50 |
| A read (`query`, `probabilities`, `decide`, `facts`) | 10 s, then `504 E_TIMEOUT` |
| `learn`, `calibrate`, `backtest` | Inline up to 20,000 graded precedents; above, a job (`202` and a job id) |
| Rate | Per org per plan (section 7), `429 E_RATE` with `Retry-After` |
| Imports | 200 MB a file, one running per model |

---

## 4. The API

### 4.1 Auth

- **API keys** (`glyphh_ak_…`), made on the API Keys page or the connector, shown once, kept as SHA-256: the
  `runtime_keys` table and `ops/runtime_keys.py` as they are, with a `scope` column (`cloud`, `runtime`) and a
  `clearance` column (0 to 1; default 1). A key belongs to its maker and acts in their org. Today's
  `glyphh_rk_` keys keep working on self-hosted rrotor only.
- **A Glyphh sign-in** (an OAuth access token from `/oauth/token`) works on the REST API too, for the platform and
  for the connector's forwarded calls.
- **Clearance** comes from the key (or, signed in, from the person's org role: admin 1, member the org's default),
  never from the body. A request may send `clearance` lower than that, never higher, which is rrotor's rule today
  (rrotor `docs/architecture.md` section 8).
- The Ada app checks keys against Postgres and keeps each answer a minute, good or bad, as rrotor does with
  introspection.

### 4.2 Endpoints

All under `https://ada.glyphh.ai/v1`, JSON, refusals `{"error": {"code", "message", "trace_id"}}` with the server's
codes (`E_LIMIT` with `reason`, `used`, `max`, `plan`).

| Call | Does |
|---|---|
| `POST /decide` `{model, data, output?, outputs?, clearance?, include?}` | The headline: the kernel's `decide` (or `decide_all` for `outputs`): `{outcome, expected_cost, probabilities, ask, receipts, model, version}`; `include: ["facts"]` adds the nearest fact tree |
| `GET /models`, `POST /models` `{name, spec}`, `GET /models/{name}`, `DELETE /models/{name}?confirm=<name>` | The org's models; make one (version 1); one with its active version, size and settings; delete it and its store |
| `PUT /models/{name}/spec` `{spec, note?}` | A new spec version, made active (3.6) |
| `GET /models/{name}/versions`, `POST /models/{name}/versions/{n}/activate` | Every version, who made it and why; roll back |
| `GET /models/{name}/settings`, `PATCH /models/{name}/settings` `{changes, note?}` | Every lever as it stands; a change is a new version (section 5) |
| `POST /models/{name}/record` `{data, outcome?, outcomes?, ts?}` | One case: `{id, precedents}` |
| `POST /models/{name}/record_many` `{cases: [{data, outcome?, outcomes?, ts?}]}`, `Idempotency-Key` | Up to 1,000, in one transaction: `{ids, added, replaced, precedents}` |
| `POST /models/{name}/grade` `{id, output?, value}` | One output's outcome on a case already recorded (`Model.grade`) |
| `DELETE /models/{name}/precedents/{id}` | Forget one case (needs the kernel's `forget`, section 9) |
| `POST /models/{name}/query`, `/probabilities`, `/facts`, `/decide` | The kernel's own, with `{data, output?, clearance?}` (`facts`: `top`, `min_score`): the `Answer` shape of `contract/contract.json` unchanged |
| `POST /models/{name}/learn` `{output?}`, `/calibrate` `{output?, sample?, by?}`, `/refresh` | Weights and temperature from the store (`Model.learn`, `calibrate`, `refresh`) |
| `POST /models/{name}/backtest` | Score a candidate before it goes live (section 5) |
| `POST /models/{name}/imports`, `GET /models/{name}/imports/{id}` | Bulk load (section 6) |
| `GET /models/{name}/export` | Everything back out (section 6) |
| `GET /jobs/{id}` | A long `learn`, `calibrate`, `backtest`, import or export |
| `GET /usage` | Precedents, requests this period, against the plan |
| `POST /runs` `{model, function, inputs, clearance?}` | **Compatibility:** today's rrotor call shape (`contract/contract.json` `result`), for `function` in `record`, `query`, `facts`, `probabilities`, `decide`, `learn`, `settings`, answered at once as a `done` Result (`run_id` a fresh id, `seconds` the time taken). The SDKs 3.0 work against the cloud with only the URL and key changed |

`decide` never answers `needs_input`: the cloud has no runs to continue. `ask: true` is the signal.

### 4.3 The connector: one URL

The Ada tools join the existing Glyphh connector at `https://api.glyphh.ai/mcp` (`mcp/tools/registry.py`), as a new
module `mcp/tools/ada.py`, so a person adds one connector for the account and for Ada. Each tool forwards to the Ada
app over Fly's private network with the person's identity; the server stores nothing of the call.

| Tool | Does |
|---|---|
| `ada_models`, `ada_model` | The org's models; one with its spec, active version, size, settings |
| `ada_model_create` `{name, spec}`, `ada_spec_update` `{name, spec, note}`, `ada_model_delete` `{name, confirm}` | Make, change, delete |
| `ada_versions`, `ada_activate` `{name, version}` | Versions; roll back |
| `ada_record` `{name, data, outcome?}`, `ada_record_many` `{name, cases}` | Record one, or up to 1,000 |
| `ada_import` `{name, format, mapping?}` | Starts an import and answers a one-hour upload URL (Claude Code can `curl` the file to it); `ada_job` shows progress |
| `ada_decide`, `ada_query`, `ada_probabilities`, `ada_facts` | Ask |
| `ada_learn`, `ada_settings` `{name, changes?}`, `ada_backtest` | Learn and tune (section 5) |
| `ada_export` `{name}` | A one-hour download link |
| `ada_forget` `{name, id}` | Forget one case |
| `create_api_key` | As `create_runtime_key` today, `scope: cloud` |

Today's `runtime*` tools stay for self-hosted (Enterprise) orgs and are hidden for the rest.

---

## 5. Tuning in the cloud

Every lever the kernel has becomes an API call and a connector tool, versioned per model, with a backtest before a
change goes live. Claude does the tuning conversationally through the connector and the Ada skill.

### 5.1 The levers

From `glyphh_spec.py` (`Settings.RANGES`, `Role`, `Output`, `_parse_spec`):

| Lever | Where | Range or kind | What it changes | Relearns |
|---|---|---|---|---|
| `k` | `settings` | 1 to 1,000 | Nearest precedents a query votes over | No |
| `min_sim` | `settings` | 0 to 1 | The weighted similarity a precedent needs to vote: higher, "say nothing rather than guess" | No |
| `word_weights` | `settings` | bool | Learn a weight per word of a text role | Yes |
| `word_floor` | `settings` | 0 to 1 | The least a learned word weighs | Yes |
| `interactions`, `max_interactions` | `settings` | bool; 0 to 50 | Learn pairs of roles that tell more together | Yes |
| `rare` | `settings` | 1 to 100,000 | Values, words and pairs seen fewer times are not learned from | Yes |
| `word_pairs`, `max_word_pairs` | `settings` | bool; 0 to 200 | Learn pairs of words (phrase intents) | Yes |
| `word_evidence` | `settings` | 0 to 5 | How much a case's words, by what each says of each outcome, weigh on the vote | No |
| `lexicon` | `settings` | bool | Read words through WordNet and Moby | No (but it changes how text is read; the service re-reads the store) |
| `calibrate_by`, `calibrate_sample` | `settings` | `loss` or `cost`; 10 to 1,000,000 | Probabilities that mean what they say, or that decide best by `costs` | Recalibrates |
| `refresh_every` | `settings` | 10 to 1,000,000, or none | Learn and calibrate again every so many graded records | — |
| Role `similarity_weight`, `security_weight` | spec | 0 to 1 | A role's voice; the clearance needed to see it | Yes (learned weights override similarity) |
| `numeric_config` (`min_value`, `max_value`, `bin_width`), `text_encoding`, `lexicons`, `key_part` | spec | per role | How a value is read | Re-reads the store |
| Declared `interactions` | spec | role pairs | Pairs always read together | Yes |
| `output.costs`, `output.ask`; each named output's `values`, `costs`, `ask` | spec | numbers | What each mistake costs; when to ask a person | No (`calibrate_by: cost` recalibrates) |
| `output.report` | spec | paths | What a fact tree shows | No |
| Layer and segment weights, `seed`, `dimension` | spec | 0 to 1; ints | Voices; the encoding (`seed`, `dimension` re-encode the store: `reencode_store`) | Re-encode |
| `clearance` | per key and request | 0 to 1 | What a reader may see and what votes for them | — |
| Learned weights (`value_weights`, `~interactions`, `~evidence`) | the store's `meta` (`learned`, `learned:<output>`) | learned, not set | What the precedents say each role, value, word and pair is worth | — |

### 5.2 Versions and rollback

- Today `Model.configure()` keeps changed levers in the store's `meta` (`settings`), over the spec's, unversioned
  (`glyphh_spec.py`); rrotor's `settings` function exposes that (`examples/*/model.py`). In the cloud **the spec is
  the only truth:** a settings change writes a new spec version with those `settings`; the model reopens on it with no
  `meta` overrides.
- `ada_spec_versions(model_id, version, spec jsonb, note, made_by, made_at, encoding, learned jsonb, tau jsonb)`:
  each version also keeps the learned weights and temperatures it went live with, copied from the store's `meta`, so
  a rollback restores them without relearning. Active version per model in `ada_models`.
- A change of `seed` or `dimension` (the encoding) is a job: the store is re-encoded into a new file beside the old
  (`reencode_store`), switched at the end; rollback switches back while the old file is kept (7 days).

### 5.3 Backtest: before it goes live

`POST /models/{name}/backtest`:

```jsonc
{"candidates": [{"settings": {"word_evidence": 1.0}}, {"spec_version": 4}, {"spec": {…}}],
 "holdout": {"newest": 200},            // or {"fraction": 0.2, "seed": 7}
 "output": "default",
 "clearance": 1.0}
```

- For the active version and each candidate (up to 10): build an in-memory `Model` (`path=None`) from the store's
  graded precedents minus the held-out ones, `learn` and `calibrate` on that training part only, then score every
  held-out case. The live model is never touched. This is what the benchmarks' `tune_*.py` scripts do by hand
  (rrotor `benchmarks/banking77/tune_evidence.py`), and what the Ada skill's Tuning section asks of Claude ("hold
  some cases out, change one lever, learn, score the held-out cases").
- Answers per candidate: accuracy, log-loss, total and mean cost by the output's `costs`, ask rate (and accuracy on
  the cases it did not ask about), coverage (`sufficient`), a confusion table, and the change against the active
  version. A job above 20,000 precedents.
- `PATCH settings` and `PUT spec` take `"backtest": <job id>` to say what the change was checked against, kept on the
  version.

### 5.4 Claude, tuning

The rewritten Ada skill (section 8) tells Claude to: read `ada_model` and `ada_settings`; propose one change at a
time with the reason; run `ada_backtest` with the current and candidate; show the person the numbers in plain words
("asks 12% fewer times, costs 8% less on the last 200 cases"); apply with `ada_settings` and a note only when the
person agrees; and roll back with `ada_activate` if live results fall. It never scores on cases the model learned
from.

### 5.5 What tuning needs code, and so does not fit the cloud

| Needs code | Cloud answer |
|---|---|
| Derived features (a ratio of two numbers, a weekday from a date, a lookup in the customer's systems) | The caller computes them and sends them as roles. Later, a small declarative `derive` block (ratio, difference, date part) if customers ask |
| Business rules on top of the vote ("always refuse above $50,000") | The caller applies them. Not in the spec |
| A custom similarity or a custom scoring metric for backtests | Not offered; the built-in metrics are accuracy, log-loss, cost and ask rate |
| Sequences of events (`Space` `events`, `Strand`) | The spec path does not use them today; not offered |
| Anything with network, files or secrets (rrotor's base) | rrotor, Enterprise |

---

## 6. Getting history in, and out

### 6.1 Seeding today needs code

On rrotor, seeding is one `model_call record` per case, each a sandboxed run (Ada skill step 5), or Python run by
hand (`Spec.learned`, the benchmarks' `run.py`). There is no bulk route in rrotor (`src/rrotord/api/routes.py`); the
kernel's `Space.merge(path)` unions another SQLite store, which rrotor caps all or nothing (`rrotor/ada.py`
`_cap`). A pure-cloud model replaces all of this with three ways in, none of them code.

### 6.2 Three ways in

| Way | Shape | Good for |
|---|---|---|
| `record_many` | Up to 1,000 cases, 5 MB, one SQLite transaction; `Idempotency-Key` (kept 24 h: the same key and body answer the first answer; another body, `409 E_IDEMPOTENCY`). A spec with `key_part` roles is idempotent by itself: the same case id replaces its row (`Space.record`) | Code and Claude, up to tens of thousands |
| An import | `POST /imports {format: jsonl \| csv \| ada_sqlite, mapping?}` answers an upload URL; the file (up to 200 MB) is read as a job: validated row by row against the spec, recorded in batches of 1,000, `GET /imports/{id}` shows `{state, rows, recorded, refused: [{row, path, message}] (first 100), percent}`; `learn` and `calibrate` run once at the end | The platform's Import page; Claude Code with a large file |
| From Claude | The skill reads the person's file, maps its columns to the spec with them, and sends `ada_record_many` in chunks of 1,000, or for big files `ada_import` and `curl` to the upload URL | Conversational onboarding |

- **CSV mapping:** a header names a role by path (`error.what.message`) or the mapping maps a header to one;
  `outcome` (or `outcome.<output>`) names the outcome columns; a cell is parsed by its role's kind (a number for
  `numeric_config`, text for `bag_of_words`, a list for `;`-separated values).
- **`ada_sqlite`:** a self-hosted rrotor's `precedents.sqlite`, merged with the kernel's `Space.merge` after a check
  of its encoding. This is how an Enterprise or former self-hosted customer moves to the cloud.
- **During an import `refresh_every` is off** (the kernel would otherwise learn and calibrate every `refresh_every`
  graded records, `Model.record`), and back on after the final `learn`.
- **Cost at scale:** 10,003 Banking77 cases recorded in about 4 s, 7 s with `learn` (rrotor
  `benchmarks/banking77/README.md`), but in memory (`run.py` opens `Model` with no path). On a file the kernel
  commits every record (`Space.record`), and checks a replaced id with a list search (`rid in self._ids`), so 500,000
  rows would slow quadratically. Kernel step 0 adds `record_many` (one transaction, an id index); target 10,000
  cases in under 10 s on disk.

### 6.3 The precedent cap

- An import or `record_many` counts the new ids it would add (ids the store holds replace their rows and add
  nothing), as rrotor's `_cap` does for `merge`, and is refused whole with `E_LIMIT` `precedents` if the org would
  pass its plan's cap, unless sent with `"partial": true`, which records up to the cap and reports the rest refused.
- The count is the org's total across its models (Postgres `ada_models.precedents`, updated on each write), not per
  node.

### 6.4 Export: never locked in

`GET /models/{name}/export?format=jsonl|ada_sqlite` (a job for large stores; a one-hour download link):

- `jsonl`: one line per precedent `{id, data, outcome, outcomes, ts, author}`, plus `spec.json` (every version) and
  `learned.json` (the active learned weights and temperatures), zipped.
- `ada_sqlite`: the store file itself, which a self-hosted rrotor opens as `precedents.sqlite` unchanged.
- Org-wide export on the platform's Settings page: every model, one archive.

### 6.5 Deletion

- **One case:** `DELETE …/precedents/{id}`. The kernel has no public delete (only the private `_drop`, used when an
  id is replaced), so kernel step 0 adds `Space.forget(rid)` and `Model.forget`; learned weights still reflect the
  case until the next `learn`, which the service schedules.
- **A model:** its store file, its spec versions and its replica prefix in Tigris. Litestream's snapshots age out
  within 7 days: the privacy policy states "deleted within 7 days from backups".
- **An org:** every model, then the org (today's org deletion, plus the above).

---

## 7. Plans and metering

**Nodes mean nothing in the cloud.** What costs Glyphh money is RAM (precedents held), CPU (reads, learns) and disk.
So a cloud plan sells **precedents per org** and **requests per month**; never seats, models or installs (`docs/pricing.md`,
the 2026-10-18 ruling).

**What counts:** a request is one read (`decide`, `query`, `probabilities`, `facts`; `POST /decide`; `/runs` with a
read function). Writes, learns, backtests, imports and exports are not counted as requests: they are bounded by the
precedent cap and the rate limit. A `decide` with `outputs` counts once per output.

| | Free | Pro | Team | Enterprise |
|---|---|---|---|---|
| Price | $0 | $99 a month | $299 a month | By contract, from $10k a year |
| Precedents, the org's total | 5,000 | 100,000 | 1,000,000 | By contract, or self-hosted rrotor |
| Requests a month | 10,000 | 1,000,000 | 5,000,000 | By contract |
| Over the requests | Refused until the month turns (`E_LIMIT` `requests`) | $1 per 10,000 more (metered) | $1 per 10,000 more | By contract |
| Rate | 5 a second | 50 a second | 200 a second | By contract |
| Models, members, keys | Unlimited | Unlimited | Unlimited | Unlimited |
| Backtests, versions, export, audit log | Yes | Yes | Yes | Yes, plus a dedicated cell and SSO when built |
| Self-hosted rrotor | No | No | No | Yes (registry credentials, licence key) |

Why these numbers: at about 5 KB a precedent after kernel step 0, Team's million is about 5 GB of RAM held for one
org, which $299 covers on Fly's list prices with room; at today's 16 KB it would be 16 GB and would not. **If step 0
does not bring memory down, Team's cap must be 300,000.** Requests cost almost nothing (5.9 ms a read on a $0.019/h
machine, Banking77): the request caps are there to bound abuse and to make the step from Free to Pro natural, not to
recover cost.

**What changes in the code:**

- `plan_versions` (`db/schema.sql`) gains `cloud_precedents`, `cloud_requests`, `cloud_rps`; `db/seed.py` seeds them.
  `max_machines`, `precedents` (per node) and `sync` stay for Enterprise's self-hosted licence keys.
- Usage: each Ada machine counts requests per org in Redis (`INCR`, keyed by org and period) and flushes to a new
  `ada_usage(org_id, period, requests, precedents_max)` every minute; the rate limit is a Redis token bucket.
- Stripe: the flat Pro and Team prices stay. One new Billing Meter, `ada_requests`, and a metered price ($1 per
  10,000) on Pro and Team subscriptions, reported daily by the same pattern as `ops/billing/meter.py` (each report
  written before it is sent, its id the identifier Stripe counts once). `scripts/stripe-setup.py` makes them. The
  hosting meter stays unused.
- The connector's `plan`, `plans` and `usage` show the cloud numbers; the licence key is shown only to Enterprise.

---

## 8. Security, data and terms

| | |
|---|---|
| Isolation | Org from the key, never the body; stores by database ids; strict RLS on Ada tables and a separate database role; no customer code; spec bounds (3.3) |
| In transit | TLS to `ada.glyphh.ai`; the connector's forward over Fly's private WireGuard network |
| At rest | Fly volumes are encrypted at rest; Litestream replicas on Tigris encrypted, with an age key per org held in the server's vault (`ops/vault.py`), so a leaked bucket reads nothing |
| Logs | Never a request's data or answer: model, function, org, status, latency, size. The same rule the server keeps for runtimes (`docs/pricing.md`, Telemetry) |
| Audit | Every write that is not a record (spec, settings, activate, import, export, forget, delete, keys) and every refusal, in `ada_audit` per org, kept a year, shown on the platform and by the connector's `logs` |
| Deletion | 6.5: immediate in the live store, 7 days from backups |
| Export | 6.4, on every plan |
| Learning across customers | None: a model learns only from its own store. The lexicon is a fixed public resource, shared read-only |

**The privacy policy and terms change** (a list; the words are a lawyer's):

1. Glyphh now stores and processes customer data (cases, outcomes, specs) as a processor: say what, where (Fly
   `iad`, Tigris), how long, and for what (only to answer that customer).
2. A Data Processing Agreement, offered on Pro and Team, signed on Enterprise; standard contractual clauses for EU
   customers while data is in the US.
3. Sub-processors: Fly.io, Tigris, Stripe, the sign-in providers; a page that lists them and a notice period for
   changes.
4. Retention and deletion: live deletion, 7 days from backups, org closure.
5. Security: encryption, access by Glyphh staff only for support and with the customer's consent, breach notice
   (72 hours).
6. No training on customer data; no use across customers.
7. Acceptable use: no special-category or regulated data (health, card numbers) without an agreement; no use for
   decisions with legal effect on people without a person able to review (the `ask` path), which the EU AI Act and
   GDPR article 22 care about.
8. Service levels: none on Free; Pro and Team best effort with a stated restore time (minutes, 3.4); Enterprise by
   contract.
9. Export and portability rights.
10. The lexicon's attribution (WordNet 3.0, Moby).

---

## 9. What happens to everything else

| Thing | What happens |
|---|---|
| **rrotor** | Stays, as Enterprise's self-hosted option: unchanged code, its licence keys, clusters and audit log. Its examples and the skill's rrotor half stay in its repo |
| **The public image** `ghcr.io/glyphh-ai/rrotor` | Made private now (GHCR package visibility). Enterprise pulls with per-customer credentials: a GHCR token per contract at first, later a token-auth registry fronted by the server. Versions already pulled are out: say so honestly, and consider compiling the kernel (Cython) in the Enterprise image from now on. rrotor's repo and its `part-ada-*` releases are already private |
| **Free self-hosting** | Ends with the image going private: Free moves to the cloud. This reverses the 2026-10-18/19 "Free local unlimited" PLG ruling (decision 7) |
| **The self-hosting docs** (rrotor `docs/self-hosting/`, the platform's Add a runtime dialog, `glyphh.ai/install.sh`) | Kept, marked Enterprise, reached from the Enterprise page and the contract; `install.sh` asks for registry credentials |
| **The platform** | Home becomes Ada: the org's models, usage and the connector URL. New Models pages (list; a model's spec editor, versions and rollback, settings, Import, Try it, Backtest, Export). API Keys makes `cloud` keys with a clearance. Runtimes and Add a runtime show only for orgs with an Enterprise grant |
| **The `glyphh` plugin's Ada skill** | Rewritten for the cloud: no repo, `model.py`, deploy or runtime; the connector's `ada_*` tools; agreeing the case and writing the spec, importing history, learning, backtesting and tuning (5.4), reading an answer. The rrotor way moves to a short "Enterprise: self-hosted" section |
| **The SDKs** (`glyphh` on PyPI, `@glyphh-ai/glyphh` on npm) | 3.0 works against the cloud through `POST /v1/runs` with `GLYPHH_RUNTIME_URL=https://ada.glyphh.ai`. 3.1: the URL defaults to `https://ada.glyphh.ai`; the key reads `GLYPHH_API_KEY` (and `GLYPHH_RUNTIME_KEY`); new `decide` shape, `record_many`, `import_file`, `backtest`, `settings`, `versions`, `export`, `create_model`. Cluster handling stays for rrotor. `contract/contract.json` goes to 4: adds `decision`, `usage`, `job`; keeps `answer`, `result`, `error` |
| **The server's docs** | `docs/architecture.md` and `docs/pricing.md` rewritten when this is built: Ada Cloud is the product; "nothing of Glyphh's on the data path" holds only for Enterprise's self-hosted rrotor |
| **The website** | One story: "Decisions from your own precedents, at one endpoint." The hero shows `POST /v1/decide` and its typed answer; the benchmarks stay; Pricing cards say precedents and requests, not nodes; Enterprise is "self-hosted or a dedicated cell" |
| **Glyphh-hosted machines** (`GLYPHH_HOSTING`) | Stay off. Once Ada Cloud ships, remove them (hosted mode, the doorman, `machine_months`, the Machines page): Ada Cloud replaces their purpose |

---

## 10. Build steps

In order; each ships behind `GLYPHH_ADA_CLOUD` (off) until step 9. Estimates are working days for one engineer
with Claude, honest rather than hopeful.

| # | Step | What ships | Tested by | Days |
|---|---|---|---|---|
| 0 | **Kernel 3.12** (`ada-private`) | `lexicon` per model, not per process; a bounded `_SYMBOLS`; lazy float32 `_matrix` for weighted reads; `Space.forget` and `Model.forget`; `record_many` in one transaction with an id index; `output.ask_below`; packaging of `glyphh_lexicon` and `lexicon/`; a memory and cold-load benchmark at 10k, 100k, 1M | The kernel's tests; the new benchmark's numbers written to its README; the Banking77 and credit results unchanged | 4 to 6 |
| 1 | **The service, one machine** (`src/glyphh_ada/`, `fly.ada.toml`) | Schema (`ada_models`, `ada_spec_versions`, `ada_usage`, `ada_audit`, `ada_jobs`, `ada_placements`) with strict RLS; `cloud` keys with clearance; the model manager (LRU by memory, one thread per model); create, spec, record, record_many, grade, query, probabilities, facts, decide, learn, calibrate, `/runs` compatibility; the private image | 100% coverage as the server keeps; a tenant test that two orgs' keys never reach each other's models; the SDK 3.0 test suite run against it | 8 to 10 |
| 2 | **Durability and scale** | Litestream to Tigris with per-org encryption; restore on start; placement and `fly-replay`; a second machine; moving a model; `E_WARMING` | A restore drill (kill a machine, time the restore); load test: 200 req/s on 100 models, p99 under 100 ms for reads | 5 to 7 |
| 3 | **In and out** | Imports (JSONL, CSV with mapping, `ada_sqlite`) as jobs with progress; the cap at import; export (JSONL, SQLite); forget; model and org deletion with replica purge | A 500,000-row import end to end; an export re-imported gives the same answers; a deleted model's prefix is gone from Tigris | 4 to 6 |
| 4 | **Tuning** | Settings as versions; activate and rollback with learned weights kept per version; re-encode jobs; backtest with candidates | Backtest on credit and Banking77 reproduces the benchmarks' held-out numbers | 4 to 5 |
| 5 | **The connector** | `mcp/tools/ada.py` forwarding over 6PN; `create_api_key`; upload and download links | The MCP test suite; a Claude session that builds a model from a CSV, tunes one lever and decides | 2 to 3 |
| 6 | **Plans and metering** | Cloud caps in `plan_versions`; Redis counting and rate limits; `ada_requests` meter and price; `plan`, `plans`, `usage` updated | Stripe test mode: a Pro org over its requests is invoiced the overage; Free is refused at its cap | 3 to 4 |
| 7 | **SDKs, contract, skill** | SDK 3.1 (Python, TypeScript), contract 4 with fixtures, the rewritten Ada skill | The SDKs' suites against a local Ada app; the skill tried end to end in Claude Code | 3 to 4 |
| 8 | **The platform** | Home, Models (spec editor, versions, settings, Import, Try it, Backtest, Export), API Keys with clearance, Usage; Runtimes behind Enterprise | The platform's tests; a person who has never seen Glyphh gets from sign-in to a first decision in under ten minutes | 6 to 8 |
| 9 | **Launch** | Image private; self-hosting docs marked Enterprise; website and pricing; privacy policy and terms (with a lawyer); `docs/architecture.md` and `pricing.md` rewritten; the flag on | A security review of the Ada app (keys, RLS, spec bounds, upload links); a week's beta with three design partners | 4 to 6 + legal |

**Total: about 43 to 59 working days: 9 to 12 weeks for one engineer, 6 to 8 with two** (steps 3, 5 and 8 run
beside 2 and 4). A usable private beta (steps 0, 1, the record_many part of 3, 5 and the skill from 7) is about
4 weeks.

### Risks and unknowns

| Risk | What would show it | Answer |
|---|---|---|
| Memory per precedent stays near 16 KB | Step 0's benchmark | Team's cap drops to 300,000; bigger stores are Enterprise |
| Cold load of a large store is slow | Step 0 (load at 1M) | Pin big stores; `E_WARMING`; later a snapshot of the in-memory tables beside the SQLite file |
| The GIL: one hot model's learn stalls others on its process | Step 2's load test | Learns and backtests in a separate job process that opens the store read-only (kernel 3.10's `readonly`) and hands back the learned `meta` |
| Failover takes minutes, not seconds | Step 2's restore drill | Say so in the terms; a warm standby (a read-only follower from the Litestream replica) for Team later |
| Glyphh now holds customer data | — | Section 8's list, a DPA, and an honest privacy policy before launch, not after |
| Kernel versions already public in the image | — | Cannot be undone; the advantage moves to the service and the newer kernel |
| Ending Free self-hosting loses developers who want it local | Signups, feedback | A Free cloud with a card-free start; Enterprise trials of rrotor on request |
| Per-request billing through Vercel's AI Gateway (the Jev model) is unverified here | — | Decision 6 |

---

## 11. Open decisions for Chris

| # | Decision | Recommendation |
|---|---|---|
| 1 | Ada in the server's process, or its own Fly app | **Its own app (`glyphh-ada`), in this repo** (3.1) |
| 2 | One connector, or a second at `ada.glyphh.ai/mcp` | **One:** the Ada tools on `api.glyphh.ai/mcp`, forwarded (4.3) |
| 3 | Store: per-model SQLite on volumes, or Postgres | **SQLite with Litestream to Tigris** now; Postgres only if a model outgrows a machine (3.4) |
| 4 | The cloud caps (section 7) | **Free 5k / 10k requests, Pro 100k / 1M, Team 1M / 5M**, Team at 300k if step 0 misses its memory target |
| 5 | What a billable request is | **Reads only;** writes bounded by the precedent cap |
| 6 | Bill through Stripe (built) or through Vercel's AI Gateway like Jev | **Stripe first** (the meter pattern exists, `ops/billing/meter.py`); list on Vercel's marketplace later if it brings customers |
| 7 | Make `ghcr.io/glyphh-ai/rrotor` private, ending Free self-hosting | **Yes, now;** Free moves to the cloud; this reverses the 2026-10-18/19 Free-local ruling |
| 8 | The URL | **`https://ada.glyphh.ai`** for the API; the connector stays at `api.glyphh.ai/mcp` |
| 9 | Region | **`iad` only at launch;** an EU cell (`ams`) when the first EU customer asks, data kept in-region |
| 10 | The audit log on every plan (it is Enterprise-only on rrotor) | **Every plan:** in the cloud it costs almost nothing and buyers ask for it |
| 11 | A confidence bar (`output.ask_below`) beside cost-based `ask` | **Yes:** it is how people think before they think in costs (both examples use 0.6) |
| 12 | Retire Glyphh-hosted machines once Ada Cloud ships | **Yes:** remove the code, not just the flag, a month after launch |
| 13 | Existing paid self-hosted customers, if any | Keep their keys to the end of their period; offer `ada_sqlite` import to the cloud or an Enterprise contract |
