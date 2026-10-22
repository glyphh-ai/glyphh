# @glyphh-ai/glyphh

Ada for TypeScript and JavaScript: your models in Ada Cloud, `https://ada.glyphh.ai`, called with an API key.
Node 18 or later (or any runtime with `fetch`), no dependencies.

```bash
npm install @glyphh-ai/glyphh
```

```ts
import { Ada, LimitError } from "@glyphh-ai/glyphh";

const ada = new Ada();          // GLYPHH_API_KEY from the environment; or new Ada({ key: "glyphh_ak_..." })

const d = await ada.decide("tickets", { ticket: { what: { plan: "pro", text: "charged twice" } } });
if (d.ask) await sendToAPerson(d);   // a person should decide: d.outcome is the best guess, for them to see
else act(d.outcome);                 // d.probabilities, d.expected_cost, d.receipts: the precedents it stands on

const tickets = ada.model("tickets");
await tickets.record({ ticket: {...} }, "refund");              // a confirmed outcome: the next case learns from it
```

The key is made on the platform's API Keys page (https://platform.glyphh.ai), or by Claude through the Glyphh
connector; it acts in your org, with the clearance it was made with. `GLYPHH_ADA_URL` moves the address (a local
server under test); 3.0's `GLYPHH_RUNTIME_URL` and `GLYPHH_RUNTIME_KEY` are still read.

## From nothing to a decision

```ts
const tickets = await ada.createModel("tickets", spec);       // the spec as JSON: layers, segments, roles, output
const job = await tickets.importFile("history.csv", {          // a path (Node), or the bytes with { format }
  mapping: { Plan: "ticket.what.plan", Result: "outcome" },
  onProgress: (j) => console.log(j.state, j.percent),
});
console.log(job.result.added, job.result.refused, job.result.refusals.slice(0, 3));

const bt = await tickets.backtest([{ settings: { word_evidence: 0 }, name: "no word evidence" }], { holdout: { newest: 200 } });
await tickets.settings({ word_evidence: 0 }, { note: "cost 8% less on the last 200", backtest: bt.id });   // a new version
await tickets.activate(1);                                     // and back
await tickets.export({ to: "tickets.zip" });                   // everything, as a zip: never locked in
```

| | |
|---|---|
| `Ada` | `decide(model, data, { output, outputs, include: ["facts"], clearance })` (`POST /v1/decide`); `models()`, `model(name)`, `createModel(name, spec)`, `deleteModel(name)`; `job(id)`, `wait(job, { timeout, onProgress })`, `download(job)`; `usage()` |
| `AdaModel` | `info()`, `spec()`, `setSpec(spec, { note, backtest })`, `settings()` and `settings(changes, { note, backtest })`, `versions()`, `activate(version)`, `delete()`; `recordMany(cases)` (a thousand a request, in chunks), `grade(id, value, { output })`, `forget(id)`; `decide(data, ...)`; `learn()`, `learnJob()`, `calibrate()`, `backtest(candidates, { holdout, output })`; `importFile(path or bytes, { format, mapping, partial, learn })`, `export({ format, to })` |
| `Decision` | `outcome`, `probabilities`, `expected_cost`, `ask`, `receipts`, `facts`, `outputs`, `model`, `version`; reads as 3.0's `Result` too (`status`, `data`) |
| `Job` | `id`, `model`, `kind`, `state` (`awaiting`, `queued`, `running`, `done`, `failed`), `percent`, `result`, `error`, `download`, `upload` |
| `Usage` | `plan`, `month` (YYYY-MM, UTC), `resets_at` (YYYY-MM-DD), `models`, `precedents` (`used`, `max`), `requests` (`used`, `max`, `over`, `overage`: past the month metered on Basic, Pro and Team, refused on Free), `requests_per_second`; `null` is by contract, no cap |
| `AdaError` | `code`, `message`, `status`, `detail`, `retryAfter`, `traceId`; typed by code: `AuthError`, `LimitError` (`reason`, `used`, `max`, `plan`, `upgrade`, `resetsAt`), `RateError` (`retryAfter` from Retry-After, `max`; waited out while the retry deadline allows), `InvalidError`, `ModelMissingError`, `JobMissingError`, `SpecError`, `SpecLimitError`, `SpecReadingError`, `FewRolesError`, `MappingError`, `BusyError`, `NotReadyError`, `NoChangeError`, `IdempotencyError`, `VersionGoneError`, `AdaTimeoutError`, `UnavailableError`, `JobFailedError` (a job that ended `failed`) |

Every call that runs long is a job, waited for with its progress unless `{ wait: false }`. Every write carries an
`Idempotency-Key`, so the client sends again what is safe to: a read, or a write, while Ada is unreachable for a
moment (`E_UNAVAILABLE`, `E_TIMEOUT`, a 502 to 504), and anything refused with 429, with backoff and `Retry-After`,
for up to `new Ada({ retryDeadline })` seconds (default 30; 0: never).

SDK 3.0's calls still work: `record`, `query`, `facts`, `probabilities`, `learn` and `call(fn, inputs)` go through
`POST /v1/runs` and answer a `Result` (`run_id`, `status`, `data`, ...). The cloud answers every run at once, so a
decision never waits for input: it says `ask`.

The API and its answers' shapes are in [`contract/contract.json`](https://github.com/glyphh-ai/glyphh/tree/main/contract).

## License

MIT (`LICENSE`).
