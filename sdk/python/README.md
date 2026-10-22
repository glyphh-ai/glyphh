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
server under test); 3.0's `GLYPHH_RUNTIME_URL` and `GLYPHH_RUNTIME_KEY` are still read.

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

| | |
|---|---|
| `Ada` | `decide(model, data, output=, outputs=, include=["facts"], clearance=)` (`POST /v1/decide`); `models()`, `model(name)`, `create_model(name, spec)`, `delete_model(name)`; `job(id)`, `wait(job, timeout=, on_progress=)`, `download(job)`; `usage()` |
| `Model` | `info()`, `spec()`, `set_spec(spec, note=, backtest=)`, `settings()` and `settings(changes, note=, backtest=)`, `versions()`, `activate(version)`, `delete()`; `record_many(cases)` (a thousand a request, in chunks), `grade(id, value, output=)`, `forget(id)`; `decide(data, ...)`; `learn()`, `learn_job()`, `calibrate()`, `backtest(candidates, holdout=, output=)`; `import_file(path or bytes, format=, mapping=, partial=, learn=)`, `export(format=, to=)` |
| `Decision` | `outcome`, `probabilities`, `expected_cost`, `ask`, `receipts`, `facts`, `outputs`, `model`, `version`; reads as 3.0's `Result` too (`done`, `status`, `data`) |
| `Job` | `id`, `model`, `kind`, `state` (`awaiting`, `queued`, `running`, `done`, `failed`), `percent`, `result`, `error`, `download`, `upload`; `done`, `failed`, `ended` |
| `Usage` | `plan`, `month` (YYYY-MM, UTC), `resets_at` (YYYY-MM-DD), `models`, `precedents` (`used`, `max`), `requests` (`used`, `max`, `over`, `overage`: past the month metered on Basic, Pro and Team, refused on Free), `requests_per_second`; `None` is by contract, no cap |
| `AdaError` | `code`, `message`, `status`, `detail`, `retry_after`, `trace_id`; typed by code: `AuthError`, `LimitError` (`reason`, `used`, `max`, `plan`, `upgrade`, `resets_at`), `RateError` (`retry_after` from Retry-After, `max`; waited out while the retry deadline allows), `InvalidError`, `ModelMissingError`, `JobMissingError`, `SpecError`, `SpecLimitError`, `SpecReadingError`, `FewRolesError`, `MappingError`, `BusyError`, `NotReadyError`, `NoChangeError`, `IdempotencyError`, `VersionGoneError`, `AdaTimeoutError`, `UnavailableError`, `JobFailedError` (a job that ended `failed`) |

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
