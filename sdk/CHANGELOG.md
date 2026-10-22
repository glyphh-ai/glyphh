# The SDKs' changelog

Both packages carry one version; a tag `sdk-v<version>` publishes both.

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
