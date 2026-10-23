# The SDKs' changelog

Both packages carry one version; a tag `sdk-v<version>` publishes both.

## 3.3.0

Ada versions (contract 5): every model version runs one Ada version, named `ada-<major>-<minor>` (`-beta` for a
beta), its answers always computed by it; moving to another is the caller's choice. Nothing of 3.2 breaks: `info()`,
`models()` and `versions()` answer the same dicts (Python) and objects (TypeScript), with the Ada read out.

- `ada.versions()` (`GET /v1/ada`; `client.ada` in both): every Ada version, newest first (`name`, `kernel`,
  `status` stable, beta, deprecated or retired, `beta`, `open`, `released`, `deprecated`, `ends`,
  `changes_answers`, `aliases`, `summary`, `notes`, the org's `models` on it), the `latest_stable` and the server's
  `contract`; `ada.latest_stable()` / `ada.latestStable()`.
- `create_model(name, spec, ada=)` / `createModel(name, spec, { ada })`: left out, the latest stable (`ada-1-0`
  today); a beta only by its name.
- A model's Ada: `info()` carries `ada`, `ada_status` and `ada_notice` (`upgrade`, `beta`, `deprecated`, `moved`,
  `retired`, with `to` and `ends`; Python: a `ModelInfo`, still a dict, and an `AdaNotice`); each of `models()` its
  `ada`; each of `versions()` its `ada` and `kernel` (Python: `ModelVersion`, still a dict); a `Decision` its `ada`;
  `usage()` the org's Ada versions (`ada`, the `/v1/ada` shape). A `beta` notice on a stable model says a beta is
  open to try; a model on the beta has `ada_status` beta and no notice.
- `backtest(candidates, ada=)` / `backtest(candidates, { ada })`: the active spec scored on another Ada (a
  candidate may name its own `ada` too); the result's active run and each candidate carry their `ada`.
- `upgrade(ada=None, note=, backtest=, wait=True)` / `upgrade({ ada, note, backtest, wait })` (`POST
  /v1/models/{name}/upgrade`): a new version of the active spec on that Ada (none: the latest stable; an older one
  is a downgrade), re-encoded by a job that is waited for with its progress; active once it is done. Roll back with
  `activate(version)`.
- Typed refusals, each an `AdaVersionError` with `ada` and `latest` (the latest stable, the fix):
  `AdaVersionUnknownError` (`E_ADA_UNKNOWN`), `AdaVersionRetiredError` (`E_ADA_RETIRED`),
  `AdaVersionDeprecatedError` (`E_ADA_DEPRECATED`), `AdaBetaClosedError` (`E_ADA_BETA`),
  `AdaVersionUnavailableError` (`E_ADA_UNAVAILABLE`, a 503 never retried); an upgrade to the Ada the model runs is
  `NoChangeError`.
- A model on a deprecated Ada, or just moved off a retired one (`Glyphh-Ada-Notice`), is said once per client and
  notice: Python `warnings.warn` with `AdaDeprecationWarning` (a `FutureWarning`, shown by default), TypeScript
  `new Ada({ onWarning })` (default `console.warn`).
- Each SDK states what it speaks: `SUPPORTED_CONTRACT` (5) and `SUPPORTED_ADA` (`ada-1-0`, `ada-1-1-beta`; other
  names the server lists are sent as they are). An answer whose `Glyphh-Contract` (or `/v1/ada`'s `contract`) is
  newer is refused, never read half-understood: `ClientTooOldError` (`E_CLIENT_TOO_OLD`, `contract`, `supported`),
  saying how to upgrade. An older server, or none of the header, is read as before.
- `contract/contract.json` 5: `headers`, `ada_versions`, `model`, `models`, `versions`, `upgrade`, `backtest` added,
  `ada` required on `decision`, the five `E_ADA_*` codes; fixtures for each (`result_schema` checks a job's result).

## 3.2.0

Ada Cloud (the spec's "SDK 3.1"; 3.1.0 was already published, for clustered runtimes). Nothing of 3.0 or 3.1 breaks.

- The address defaults to `https://ada.glyphh.ai` (`GLYPHH_ADA_URL` moves it; `GLYPHH_RUNTIME_URL` is still read);
  the key is read from `GLYPHH_API_KEY`, then `GLYPHH_RUNTIME_KEY`.
- `decide(model, data, output=, outputs=, include=, clearance=)` on `Ada` and on a model is `POST /v1/decide`: a
  `Decision` (`outcome`, `probabilities`, `expected_cost`, `ask`, `receipts`, `facts`, `outputs`, `model`,
  `version`), which reads as a `Result` too (`done`, `status`, `data`).
- Models: `create_model` / `createModel`, `info`, `spec`, `delete_model` / `deleteModel`; versions: `set_spec` /
  `setSpec`, `settings()` and `settings(changes)`, `versions`, `activate`.
- Cases: `record_many` / `recordMany` (any number, a thousand a request), `grade`, `forget`.
- Jobs, waited for with their progress (`on_progress` / `onProgress`): `import_file` / `importFile` (a path or bytes,
  to a signed upload link, then the import), `export` (and `download`), `backtest`, `calibrate`, `learn_job` /
  `learnJob`; `job`, `wait`. `learn` waits for a learn that outlasts `/v1/runs`'s minute.
- `usage()`, typed (`Usage`): `plan`, `month` and `resets_at`, `models`, `precedents` (`used`, `max`), `requests`
  (`used`, `max`, `over`, `overage`) and `requests_per_second`, as the server answers it (and as `cloud` on the
  account API's /v1/me and /v1/billing); in Python it reads as the answer's dict too.
- `LimitError` carries `reason`, `used`, `max`, `plan`, `upgrade` (the plan that reads more; none: talk to sales) and
  `resets_at` / `resetsAt` (when the month's requests start again); `RateError` (429 `E_RATE`, past the plan's calls
  a second) carries `retry_after` / `retryAfter` from `Retry-After` (else the body's `retry_after`) and `max`.
- Typed errors for the cloud's codes: `AuthError`, `LimitError`, `RateError`, `InvalidError`, `TooLargeError`,
  `ModelMissingError`, `JobMissingError`, `PrecedentMissingError`, `VersionMissingError`, `SpecError`,
  `SpecLimitError`, `SpecReadingError`, `FewRolesError`, `MappingError`, `ImportRefusedError`, `BacktestError`,
  `BusyError`, `NotReadyError`, `NoChangeError`, `IdempotencyError`, `ConflictError`, `VersionGoneError`,
  `ExpiredError`, `AdaTimeoutError`, `UnavailableError`, `JobFailedError`.
- Every write carries an `Idempotency-Key`, so it is sent again, like a read, while Ada is unreachable for a moment
  (`E_UNAVAILABLE`, `E_TIMEOUT`, 502 to 504); a 429 is waited out by its `Retry-After` for any call.
- `contract/contract.json` 4: `decision`, `job`, `usage` added; `answer`, `result`, `error` kept; the self-hosted
  `limit_exceeded` and `cluster` entries gone (the SDKs keep handling them). The fixtures' usage and refusals (429
  `E_RATE`, 403 `E_LIMIT` requests) are the server's real answers (glyphh-ai/server's ada-cloud-connector).

## 3.1.0

For a clustered self-hosted runtime ([running a cluster](https://docs.glyphh.ai/run-a-cluster)):

- `E_NO_HEAD` (503, no head: writes wait, reads go on) is retried with backoff, `Retry-After` honoured; so is a read
  (a GET; `query`, `facts`, `probabilities`) the runtime could not answer (unreachable, or a proxy's 502, 503, 504).
  A write that may have been applied is never sent again. `retry_deadline` / `retryDeadline` (seconds, default 30;
  0: never retry).
- Read-your-writes: the highest `Rrotor-Cluster-Seq` answered is sent as `Rrotor-Min-Seq` on later calls, so a
  read sees the client's writes on whichever node answers it. `read_your_writes=False` / `readYourWrites: false`
  turns it off; `cluster_seq` / `clusterSeq` shows it.
- `E_HEAD_LOST` (503: the head went while it had the write, which may have been applied) is `HeadLostError`, never retried.
- Typed errors, each an `AdaError`: `NoHeadError`, `NotCommittedError` (the write is kept: do not resend it),
  `RunLostError` (410), `ReadOnlyError` (a function marked `"writes": false` wrote on a follower; raised from the
  `failed` run).
- `result.limit_exceeded`: a `done` run that indexed nothing, the store at the licence key's precedent cap.
- A transport may answer headers: `(status, body, headers)` in Python, `{status, body, headers}` in TypeScript.

## 3.0.0

- The packages are `glyphh` on PyPI (`from glyphh import Ada`) and `@glyphh-ai/glyphh` on npm, from this repository.
  The API is that of `glyphh-ada` and `@glyphh-ai/ada` 0.4.0: change the install and the import.
- A major version on purpose: `glyphh` up to 2.6.7 on PyPI is a different, older library. Code for 2.x does not run on
  3.x; anything pinned to `glyphh<3` keeps the old one.
- A runtime's address may be self-hosted, `https://<host>`, as well as `https://<machine>.glyphh.app`.

## 0.4.0

`learn()`.
