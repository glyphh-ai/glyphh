# The SDKs' changelog

Both packages carry one version; a tag `sdk-v<version>` publishes both.

## 4.0.0 — 2026-11-24

Glyphh is one thing: Ada. Both packages are now the Ada Cloud client alone (and, in Python, the `glyphh` command for
it). A major version because public modules are gone; everything of Ada answers as in 3.16. Contract 5 still.

Removed, with no replacement in these packages:

- Everything that was not Ada: the modules, classes, errors and commands for anything but Ada Cloud models (in
  Python, every submodule but `glyphh.client`, `glyphh.errors`, `glyphh.credentials` and `glyphh.cli`; in
  TypeScript, every export that was not part of the Ada client), their contracts and fixtures, their examples and
  deploy files. Code that imports one of them keeps working on `glyphh<4` / `@glyphh-ai/glyphh@3` only as long as
  the server still answers it: the server is removing those APIs too.
- The `glyphh` command keeps every Ada command and loses the rest.
- Python's `api` extra (`pip install glyphh[api]`): the package has no optional dependency again.
- What SDK 3.0 and 3.1 kept for a server you ran yourself: `Ada.deploy`, `Ada.run`, `Ada.log`, `Ada.resume`,
  `Ada.cancel` (a job is still stopped with `cancel_job` / `cancelJob`), `Model.resume`, `read_your_writes` /
  `readYourWrites`, `cluster_seq` / `clusterSeq`, `Result.limit_exceeded`, the errors `NoHeadError`,
  `HeadLostError`, `NotCommittedError`, `RunLostError` and `ReadOnlyError`, and the 3.0 environment names
  `GLYPHH_RUNTIME_URL` and `GLYPHH_RUNTIME_KEY`: set `GLYPHH_ADA_URL` and `GLYPHH_API_KEY`.

Unchanged: `Ada`, `Model` (TypeScript `AdaModel`), `decide`, `beam`, models and their versions, cases, jobs, imports
and exports, backtests, Ada versions and upgrades, `usage`, every typed Ada refusal, retries and idempotency, and
3.0's `record`, `query`, `facts`, `probabilities`, `learn` and `call` through `POST /v1/runs`.

Other plugins and skills for Claude live at https://github.com/glyphh-ai/plugins.

## 3.x

What 3.x added to Ada, all of it in 4.0:

- 3.10.0 (2026-11-04): the beam. `beam(start, hops, width, values, miss, clearance)` on `Ada`, `POST /v1/beam`: a
  chain of models, one model's outcome the next model's question, one read per hop; the answer is a `Beam`
  (`outcome`, `p`, `ends`, `paths`, `lost`, `hops`, `ada`). `glyphh beam` in the command.
- 3.7.0: jobs can be stopped and say what they are doing. `cancel_job(job)` / `cancelJob(job)` (`POST
  /v1/jobs/{id}/cancel`; the job ends `failed` with `E_CANCELLED`), `Job.stage`, `glyphh cancel`.
- 3.5.0: the `glyphh` command (Python): Ada Cloud from a terminal, on an API key that `glyphh login` checks and
  keeps 0600 in `~/.glyphh/credentials.json`; `Ada()` with no key given or set uses it.
- 3.4.0: typed outputs and discriminated unions (on `ada-1-2-beta`): a named output's `kind` (`choice`, `score`,
  `noul`, `number`, `many`) and `when`; a `Decision` carries `p`, `value`, `level` and `applies`.
- 3.3.0: Ada versions (contract 5): `ada.versions()`, `create_model(..., ada=)`, `backtest(..., ada=)`,
  `upgrade()`, the `AdaVersionError` family, `AdaDeprecationWarning` / `onWarning`, `SUPPORTED_CONTRACT`,
  `SUPPORTED_ADA` and `ClientTooOldError`.
- 3.2.0: Ada Cloud. The address defaults to `https://ada.glyphh.ai`; `decide` and its `Decision`; models, versions,
  cases (`record_many`, `grade`, `forget`), jobs (`import_file`, `export`, `backtest`, `calibrate`, `learn_job`),
  `usage()`, `LimitError` and `RateError`, the typed errors for the cloud's codes, an `Idempotency-Key` on every
  write.
- 3.0.0: the packages became `glyphh` on PyPI (`from glyphh import Ada`) and `@glyphh-ai/glyphh` on npm. `glyphh`
  up to 2.6.7 on PyPI is a different, older library.
