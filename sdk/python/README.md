# glyphh

Ada for Python: your models in Ada Cloud, `https://ada.glyphh.ai`, called with an API key. Python 3.9 or later, no
dependencies.

```bash
pip install glyphh
```

```python
from glyphh import Ada, LimitError

ada = Ada()                     # GLYPHH_API_KEY from the environment; or Ada(key="glyphh_ak_...")

d = ada.decide("tickets", {"ticket": {"what": {"plan": "pro", "text": "charged twice"}}})
if d.ask:                       # a person should decide: d.outcome is the best guess, for them to see
    send_to_a_person(d)
else:
    act(d.outcome)              # d.probabilities, d.expected_cost, d.receipts: the precedents it stands on

tickets = ada.model("tickets")
tickets.record({"ticket": {...}}, "refund")                     # a confirmed outcome: the next case learns from it
```

The key is made on the platform's API Keys page (https://platform.glyphh.ai), or by Claude through the Glyphh
connector; it acts in your org, with the clearance it was made with. `GLYPHH_ADA_URL` moves the address (a local
server under test); 3.0's `GLYPHH_RUNTIME_URL` and `GLYPHH_RUNTIME_KEY` are still read. With no key given or set,
`Ada()` uses the key `glyphh login` keeps for this machine (below).

## The glyphh command

The package installs `glyphh` (also `python -m glyphh`): Ada Cloud from a terminal, for you, your scripts and CI,
and agents with a shell such as Claude Code.

```bash
pipx install glyphh             # or: uv tool install glyphh, pip install glyphh
glyphh login                    # paste an API key: checked against Ada, then kept in ~/.glyphh/credentials.json
glyphh whoami                   # which key, from where, and the org's plan
```

The key is the same API key the SDK takes. `glyphh login` keeps it 0600 for this machine (`--key-stdin` reads it
from a pipe); `GLYPHH_API_KEY`, when set, wins over it, which is the way for CI. `glyphh logout` forgets it here; the
key stays live until you revoke it on the API Keys page.

From nothing to a decision:

```bash
glyphh create tickets --spec @spec.json
glyphh import tickets history.csv --mapping '{"Plan": "ticket.what.plan", "Result": "outcome"}'
glyphh decide tickets '{"ticket": {"what": {"plan": "pro", "text": "charged twice"}}}'
glyphh record tickets @case.json --outcome refund        # a confirmed outcome: the next case learns from it
glyphh backtest tickets --candidates '[{"settings": {"word_evidence": 0}}]' --holdout '{"newest": 200}'
glyphh export tickets --to tickets.zip
```

| Commands | Do |
|---|---|
| `login`, `logout`, `whoami`, `usage`, `releases` | The key; the plan's use this month; every Ada version |
| `models`, `model`, `spec`, `create`, `delete` | The org's models; one; its spec (`--set` a new one); make one; delete one (`--confirm NAME`) |
| `record`, `record-many`, `grade`, `forget`, `import` | Cases in: one, a JSON Lines file, an outcome later, one out, a whole history file |
| `decide`, `query`, `probabilities`, `facts` | Ask |
| `learn`, `calibrate`, `backtest`, `settings`, `versions`, `activate`, `upgrade` | Tune, compare, roll back, move Ada versions |
| `export`, `job` | Everything out; any job's state (`--wait`) |

Every answer is the API's own JSON on stdout, so it pipes into `jq`; a refusal is `{"error": {code, message}}` on
stderr with exit code 1 (2 for a usage mistake). A JSON argument is the JSON itself, `@file` for a file's, or `-` for
stdin's. Jobs are waited for, with progress on stderr (`-q` hides it, `--no-wait` answers the job at once).
`glyphh <command> --help` says the rest.

## From nothing to a decision

```python
tickets = ada.create_model("tickets", spec)                     # the spec as JSON: layers, segments, roles, output
job = tickets.import_file("history.csv", mapping={"Plan": "ticket.what.plan", "Result": "outcome"},
                          on_progress=lambda j: print(j.state, j.percent))
print(job.result["added"], job.result["refused"], job.result["refusals"][:3])

bt = tickets.backtest([{"settings": {"word_evidence": 0}, "name": "no word evidence"}], holdout={"newest": 200})
print(bt.result["active"]["accuracy"], bt.result["candidates"][0]["change"])
tickets.settings({"word_evidence": 0}, note="cost 8% less on the last 200", backtest=bt.id)   # a new version
tickets.activate(1)                                            # and back
tickets.export(to="tickets.zip")                               # everything, as a zip: never locked in
```

## Typed outputs and unions

On `ada-1-2-beta`, a named output's `kind` says what its answer is: `score`, `noul`, `number`, `many` or `choice`
(the default), and `when` makes an output a branch of a union. Record each in its own terms; read what its kind adds:

```python
tickets = ada.model("tickets")
tickets.record(data, outcomes={"kind": "billing", "refund": 120, "urgent": True, "tags": ["web"]})
d = ada.decide("tickets", data, outputs=["kind", "severity", "refund", "urgent", "tags"])
d.outputs["urgent"].p            # a noul's P(true)
d.outputs["refund"].value        # a number's expected value
d.outputs["severity"].applies    # False: a bug's severity does not arise for a billing case
d.outputs["tags"].outcome        # a many output's list
```

## Ada versions

Every model version runs one Ada version, named `ada-<major>-<minor>` (`-beta` for a beta): `ada-1-0` is the
latest stable today, `ada-1-1-beta` a beta. A model's answers are always computed by its own Ada version; moving
to another is your choice, made with a backtest in front of you.

```python
for v in ada.ada.versions():                                   # newest first: name, status, dates, notes, your models on it
    print(v.name, v.status, v.ends, v.changes_answers, v.models)

tickets = ada.create_model("tickets", spec)                     # the latest stable; ada="ada-1-1-beta" to opt in to a beta
info = tickets.info()
print(info.ada, info.ada_status, info.ada_notice)              # ada-1-0 stable None; each of versions() has .ada too

bt = tickets.backtest(ada="ada-1-1-beta")                       # the active spec, learned and scored on that Ada
print(bt.result["active"]["cost"], "->", bt.result["candidates"][0]["cost"])
before = info.version
moved = tickets.upgrade("ada-1-1-beta", note="2 fewer wrong on the last 200", backtest=bt.id)   # a re-encode, waited for
tickets.activate(before)                                       # and back, on the Ada it ran before
```

`upgrade()` with no `ada` moves to the latest stable; an older version is a downgrade, allowed while it is kept.
A beta is never the default. A deprecated version still answers until its end date, then the model is moved to the
latest stable for you (never left unable to answer); while it runs one, or just after it was moved, the client warns
`AdaDeprecationWarning` (once per client). A name refused is never substituted: `AdaVersionUnknownError`,
`AdaVersionRetiredError`, `AdaVersionDeprecatedError` (for a new model or as an upgrade's target),
`AdaBetaClosedError`, `AdaVersionUnavailableError`, each with `ada` and `latest` (the latest stable, the fix).

The SDK speaks contract `SUPPORTED_CONTRACT` (5) and was made against `SUPPORTED_ADA` (`ada-1-0`, `ada-1-1-beta`);
newer names the server lists work as they are. A server that speaks a newer contract is refused, never read
half-understood: `ClientTooOldError` (`contract`, `supported`), saying to `pip install -U glyphh`.

| | |
|---|---|
| `Ada` | `decide(model, data, output=, outputs=, include=["facts"], clearance=)` (`POST /v1/decide`); `models()`, `model(name)`, `create_model(name, spec, ada=)`, `delete_model(name)`; `ada.versions()`, `ada.latest_stable()`; `job(id)`, `wait(job, timeout=, on_progress=)`, `download(job)`; `usage()` |
| `Model` | `info()` (a `ModelInfo`: `ada`, `ada_status`, `ada_notice`), `spec()`, `set_spec(spec, note=, backtest=)`, `settings()` and `settings(changes, note=, backtest=)`, `versions()` (each with `ada`, `kernel`), `activate(version)`, `upgrade(ada=, note=, backtest=, wait=)`, `delete()`; `record_many(cases)` (a thousand a request, in chunks), `grade(id, value, output=)`, `forget(id)`; `decide(data, ...)`; `learn()`, `learn_job()`, `calibrate()`, `backtest(candidates, ada=, holdout=, output=)`; `import_file(path or bytes, format=, mapping=, partial=, learn=)`, `export(format=, to=)` |
| `Decision` | `outcome`, `probabilities`, `expected_cost`, `ask`, `receipts`, `facts`, `outputs`, `model`, `version`, `ada`; reads as 3.0's `Result` too (`done`, `status`, `data`) |
| `AdaVersions` | `latest_stable`, `contract`, `versions` (each an `AdaVersion`: `name`, `kernel`, `status`, `beta`, `open`, `released`, `deprecated`, `ends`, `changes_answers`, `aliases`, `summary`, `notes`, `models`); iterates over the versions; `get(name)` |
| `Job` | `id`, `model`, `kind`, `state` (`awaiting`, `queued`, `running`, `done`, `failed`), `percent`, `result`, `error`, `download`, `upload`; `done`, `failed`, `ended` |
| `Usage` | `plan`, `month` (YYYY-MM, UTC), `resets_at` (YYYY-MM-DD), `models`, `precedents` (`used`, `max`), `requests` (`used`, `max`, `over`, `overage`: past the month metered on Basic, Pro and Team, refused on Free), `requests_per_second`; `None` is by contract, no cap |
| `AdaError` | `code`, `message`, `status`, `detail`, `retry_after`, `trace_id`; typed by code: `AuthError`, `LimitError` (`reason`, `used`, `max`, `plan`, `upgrade`, `resets_at`), `RateError` (`retry_after` from Retry-After, `max`; waited out while the retry deadline allows), `InvalidError`, `ModelMissingError`, `JobMissingError`, `SpecError`, `SpecLimitError`, `SpecReadingError`, `FewRolesError`, `MappingError`, `BusyError`, `NotReadyError`, `NoChangeError`, `IdempotencyError`, `VersionGoneError`, `AdaTimeoutError`, `UnavailableError`, `JobFailedError` (a job that ended `failed`), `AdaVersionError` and its kinds (above), `ClientTooOldError` |

Every call that runs long is a job, waited for with its progress unless `wait=False`. Every write carries an
`Idempotency-Key`, so the client sends again what is safe to: a read, or a write, while Ada is unreachable for a
moment (`E_UNAVAILABLE`, `E_TIMEOUT`, a 502 to 504), and anything refused with 429, with backoff and `Retry-After`,
for up to `Ada(retry_deadline=)` seconds (default 30; 0: never).

SDK 3.0's calls still work: `Model.record`, `query`, `facts`, `probabilities`, `learn` and `call(function, inputs)`
go through `POST /v1/runs` and answer a `Result` (`run_id`, `status`, `data`, ...). The cloud answers every run at
once, so a decision never waits for input: it says `ask`.

The API and its answers' shapes are in [`contract/contract.json`](https://github.com/glyphh-ai/glyphh/tree/main/contract).
Pin `glyphh>=3`: versions up to 2.6.7 are a different, older library.

## License

MIT (`LICENSE`).
