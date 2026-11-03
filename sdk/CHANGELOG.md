# The SDKs' changelog

Both packages carry one version; a tag `sdk-v<version>` publishes both.

## 3.8.0

Glyphh bots, in the Python package: programs that control a Claude agent, behind gates that learn. Nothing of 3.7
changes; contract 5 still. The TypeScript package changes only its version.

- `glyphh.bots`: a bot is a folder (`bot.json`, `agent.md`, `program.py`, `skills/*/SKILL.md`) in
  `~/.glyphh/bots/<slug>/` (`GLYPHH_BOTS`). `Bot.load` checks a package whole and names every problem
  (`BotError`, `E_BOT`, its `problems`): the loop's steps and targets, the gates' outcomes and specs, the program's
  functions, skills, hosts, a routine's cron, Ada model names within 63 characters, and no bot that sends, pays or
  deletes without an approval step.
- `Runner`: the loop's `run` steps (program functions; `{"_end": why}` ends the run), `gate` steps (an Ada model of
  the bot's own, `bot-<slug>-gate-<gate>`: Ada's call when it is sure, else the person's answer, kept as a
  precedent), `agent` steps (`claude -p` with the bot's agent and nothing else: no tools, no MCP servers, no settings,
  no session; the step's skill and the bot's memory before it: its `bot-<slug>-memory|instructions|personality`
  models and the person's glyphh), and `approval` (the person's yes until the bot is trusted `autonomous`). Runs are
  kept in the bot's `runs.sqlite`; a question in a routine stops the run `needs_input` and `resume` carries it on;
  `wrong` records a gate's correction. Code steps get `ctx`: `http_json` (https, the bot's hosts only, its own
  User-Agent), `db()`, `state`, `gate`, `log`, `today`.
- `Orchestrator`: its own memory and gates (`orch-make-bot`, `orch-trust-bot`, `orch-keep-bot`), learning only from
  the person's verdicts and the bots' records; `install`, `new` (make_bot, then a builder agent with Read and Write in
  the new bot's folder, from `BUILDING.md`, an example bot and what earlier bots taught it; a bot that is not right,
  or touches more than asked, is set aside in `.rejected/`), `review` and `verdict` (trust and keep), `status`, and
  every run kept in its memory. A retired bot does not run.
- The `glyphh` command: `glyphh bot init|check|install|new|run|continue|wrong|status|review|verdict|routine`, JSON on
  stdout as every command; a failed run exits 1. `routine` installs a launchd job on a Mac and prints the cron line
  elsewhere. The key is `GLYPHH_API_KEY`, else `~/.glyphh/bots/.env`, else the one `glyphh login` kept.
- Examples in `examples/bots/`: `launch_watch`, `lab` (the orchestrator as a bot running experiments on how Claude
  codes best, under a hard budget) and `coder` (each task to the cheapest model a learned gate says gets it done).

## 3.7.0

Jobs can be stopped, and say what they are doing. Contract 5 still: both additions are additive.

- `cancel_job(job)` (Python) and `cancelJob(job)` (TypeScript) on `Ada`, by the job or its id
  (`POST /v1/jobs/{id}/cancel`): a job not started ends at once, a running one at its next step, within seconds. It
  ends `failed` with `E_CANCELLED`, its message saying what of its work stays, so `wait` raises (throws)
  `JobFailedError`. Asking again answers the job as it stands; a job that has already ended is refused,
  `E_JOB_ENDED` (409). `cancel(run_id)` is still 3.0's call for a run.
- `Job.stage`: what a running job is doing now, with its counts ("restating 41,000 of 52,000 precedents"), and
  `cancelling` once asked to stop. Python's `Job.cancelled` says a job ended by a cancel.
- The `glyphh` command: `glyphh cancel <job id>`, and progress on stderr shows the stage.
- The contract names the job's `stage` and the codes `E_JOB_ENDED`, `E_CANCELLED`, `E_JOB_STALLED` (a running job
  whose worker stopped and no other took up) and `E_JOB_LOST` (one that stopped its worker three times).

## 3.6.0

`Runtime`, in both packages: a client for your local rrotor, the runtime you install (a Docker image on
`127.0.0.1:7777`) that hosts your programs and CLIs. It sits beside the Ada Cloud client and changes nothing of it:
`Ada`, its contract (5) and every Ada call answer as in 3.5.

- The address is `RROTOR_URL`, else `http://127.0.0.1:7777`; the token is `RROTOR_TOKEN`, else the local token the
  plugin's installer keeps in `~/.glyphh/rrotor/token`. A self-hosted rrotor takes its URL and a runtime key.
- Programs: `programs()`, `program(name)`, `deploy` (a folder at a commit, sent as a git bundle; a GitHub repo and its
  full commit; or a bundle's bytes), `call(program, function, inputs)`, `resume` (MCP's program_continue),
  `approve(run_id, approved)`, `cancel`, `run` (a run's status), `log`, `approvals()`. These are the 3.0 calls for a
  self-hosted runtime (`deploy`, `run`, `log`, `resume`, `cancel`), renamed to programs and pointed at rrotor's
  paths (`/v1/programs/deploy`, `/v1/runs/...`); the `Ada` methods of those names stay as they were.
- Secrets: `secrets(program)` (names, declared, set), `set_secret` / `setSecret`, `delete_secret` / `deleteSecret`.
  No call ever answers a value.
- Schedules: `schedules()`, `pause_schedule` / `pauseSchedule`, `resume_schedule` / `resumeSchedule`.
- CLIs: `clis()`, `run_cli(cli, args, stdin=, files=)` / `runCli(cli, args, { stdin, files })`: exit code, stdout and
  stderr, or `needs_approval`.
- The runtime: `licence()`, `set_licence(key)` / `setLicence(key)` (a local rrotor only), `health()`.
- Typed answers (`Run`, `RunInfo`, `Program`, `ProgramVersion`, `Approval`, `Secret`, `Schedule`, `Cli`, `Licence`;
  TypeScript also `CliOutput`) and typed refusals, each a `RrotorError` and so an `AdaError`: `RrotorAuthError`,
  `RrotorForbiddenError`, `LocalOnlyError`, `ProgramMissingError`, `FunctionMissingError`, `RunMissingError`,
  `ScheduleMissingError`, `ManifestError`, `DeployError`, `InputsError`, `RunStateError`, `NotProgramError`,
  `NotCliError`, `CliDeniedError`, `NotHeadError` (`head`), `LicenceError`, `NotInPlanError`. A cluster's
  `E_NO_HEAD`, `E_RUN_LOST` and the rest keep their 3.1 classes.
- Reads are sent again while rrotor is unreachable for a moment; writes never are (a cluster's `E_NO_HEAD` and a 429
  are waited out). A cluster's `Rrotor-Cluster-Seq` is sent back as `Rrotor-Min-Seq`.
- `contract/runtime.json` and `contract/runtime-fixtures.json`: the runtime's shapes and the cases both SDKs are
  tested against, written from rrotor's code; `contract/contract.json` is Ada Cloud's alone, unchanged.

## 3.5.0

The `glyphh` command (Python): Ada Cloud from a terminal, for people and for agents with a shell. Nothing of 3.4
breaks; the TypeScript package changes only its version.

- `pip install glyphh` installs `glyphh` (and `python -m glyphh`): `login`, `logout`, `whoami`, `models`, `model`,
  `spec`, `create`, `delete`, `record`, `record-many`, `grade`, `forget`, `import`, `learn`, `calibrate`, `decide`,
  `query`, `probabilities`, `facts`, `backtest`, `settings`, `versions`, `activate`, `upgrade`, `export`, `job`,
  `usage`, `releases`. Every answer is the API's JSON on stdout; a refusal is `{"error": {...}}` on stderr, exit 1.
- It runs on an API key, as the SDK does: `glyphh login` checks one against Ada and keeps it 0600 in
  `~/.glyphh/credentials.json` (`--key-stdin` from a pipe); `GLYPHH_API_KEY` wins over it; `glyphh logout` forgets it
  (the key stays live until revoked).
- `Ada()` with no key given or set uses the key `glyphh login` kept.

## 3.4.0

Typed outputs and discriminated unions (Ada kernel 3.15.0, on `ada-1-2-beta`). A spec's named output can say what
its answer is with `kind`: `choice` (the default), `score` (ordered levels), `noul` (yes or no), `number`
(`number: {min, max, step}`) or `many` (any of its values at once); `when: {output, in}` makes it a branch of a
union, asked only when another output's outcome is one of those. Nothing of 3.3 breaks.

- Recording: `record(..., outcomes=)` and `grade(id, value)` take every kind of outcome (`Outcome`, both SDKs): one
  of the output's values, `True`/`False` for a noul, a number, a list of values for a many output.
- A `Decision` (and each of its `outputs`) carries what its kind adds: `p` (a noul's P(true)), `value` (a number's
  expected value), `level` (a score's expected level), and `applies` on a union's branch (`False`: not asked, the
  output it hangs on was decided an outcome that leaves it out). A many output's `outcome` is a list, its
  `probabilities` each value's P(true). Each is absent (None / undefined) where the kind does not give it.

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
