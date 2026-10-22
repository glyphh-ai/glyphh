# Glyphh

Glyphh's developer surface for Ada Cloud: the Claude Code plugin, the SDKs and the contract they share.

| Folder | Install | What |
|---|---|---|
| [`plugins/glyphh`](plugins/glyphh) | `/plugin marketplace add glyphh-ai/glyphh`, then `/plugin install glyphh@glyphh` | The plugin: your Glyphh account in Claude Code, the Ada skill, the file ledger |
| [`sdk/python`](sdk/python) | `pip install glyphh` | Ada for Python, `from glyphh import Ada` |
| [`sdk/typescript`](sdk/typescript) | `npm i @glyphh-ai/glyphh` | Ada for TypeScript and JavaScript, `import { Ada } from "@glyphh-ai/glyphh"` |
| [`contract`](contract) | | JSON Schema of Ada's answers (a decision, a job, usage, a query's answer, SDK 3.0's run result, a refusal) and the fixtures both SDKs are tested against, recorded from a real server |
| [`benchmarks`](benchmarks) | | Ada against Claude and classic models on public data (Banking77, German Credit), with the results, the judges' prompts and the scripts |

**Ada Cloud is Ada as an API.** You describe your cases once as a JSON spec, load your history, and ask: every
answer is typed (the spec's outcomes), with calibrated probabilities, the expected cost of each choice, whether a
person should decide instead, and the precedents it stands on. No language model is in the path, the same question
gets the same answer, and a model learns one confirmed case at a time. Glyphh runs it at `https://ada.glyphh.ai`:
there is nothing to install or host. Claude reaches it through the Glyphh connector (`https://api.glyphh.ai/mcp`)
and the Ada skill; your software through the SDKs with an API key.

- Platform (sign in, models, API keys, usage): https://platform.glyphh.ai
- Pricing: https://glyphh.ai/pricing. Plans sell precedents held and reads a month; members, keys and models are
  unlimited on each.

| Plan | Price | Precedents | Reads a month | Calls a second | Reads past the month |
|---|---|---|---|---|---|
| Free | $0 | 1,000 | 5,000 | 5 | Refused until the month turns |
| Basic | $20/month | 10,000 | 50,000 | 10 | $1 per 10,000 |
| Pro | $99/month | 100,000 | 1,000,000 | 50 | $1 per 10,000 |
| Team | $299/month | 1,000,000 | 5,000,000 | 200 | $1 per 10,000 |
| Enterprise | By contract | By contract | By contract | By contract | By contract |

## The API

At `https://ada.glyphh.ai`, with `Authorization: Bearer glyphh_ak_…` (an API key: the platform's API Keys page, or
Claude through the connector). A refusal is `{"error": {code, message, trace_id, ...}}`.

| Route | Does |
|---|---|
| `POST /v1/decide` `{model, data, output?, outputs?, include?, clearance?}` | The headline: `{outcome, probabilities, expected_cost, ask, receipts, model, version}` |
| `GET`, `POST /v1/models` `{name, spec}`; `GET`, `DELETE /v1/models/{name}?confirm={name}` | The org's models; make one from its spec; one; delete one |
| `PUT /v1/models/{name}/spec`; `GET`, `PATCH …/settings` `{changes, note?, backtest?}` | A new version (`{version, active, job}`; a job when it re-encodes the stored cases); every lever |
| `GET …/versions`; `POST …/versions/{n}/activate` | Every version, who made it and why; roll back |
| `POST …/record`, `…/record_many` `{cases}` (1,000), `…/grade`; `DELETE …/precedents/{id}` | Cases in, one or many (`Idempotency-Key`); an outcome on one already in; forget one |
| `POST …/query`, `…/probabilities`, `…/facts`, `…/decide` | The kernel's own answers |
| `POST …/learn`, `…/calibrate`, `…/backtest` `{candidates, holdout?}` | Jobs: weights and temperature from the precedents; candidates scored on held-out cases |
| `POST …/imports` `{format, mapping?, partial?, learn?}`; `PUT /v1/uploads/{link}` | An import (JSON Lines, CSV, a kernel SQLite store, a model's own export): the job and a one-hour upload link |
| `POST …/export` `{format}`; `GET /v1/downloads/{link}` | Everything of a model, as a job whose done state carries a one-hour download link |
| `GET /v1/jobs/{id}` | A job's state, percent, result or error |
| `GET /v1/usage` | The plan, the month (UTC) and when it starts again, the models, the precedents held and the month's requests against the plan's (`over` past it on Basic, Pro and Team, metered), and the calls a second |
| `POST /v1/runs` `{model, function, inputs, clearance?}` | SDK 3.0's call shape, answered at once as a `done` Result |

The shapes are in [`contract/contract.json`](contract/contract.json) (version 4), with
[`contract/fixtures.json`](contract/fixtures.json).

## Develop

```bash
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin validate --strict plugins/glyphh
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/glyphh
(cd plugins/glyphh && node --test mcp/test/*.test.*)
(cd sdk/typescript && npm ci && npm test)
(cd sdk/python && python -m pip install '.[dev]' && python -m pytest -q)
ADA_SERVER_IMAGE=<an image of glyphh-ai/server> sh sdk/integration/run.sh   # both SDKs against a real server, in Docker
```

CI (`.github/workflows`): `plugins.yml` and `sdks.yml` check every pull request. Changes come in only by pull request,
and only Glyphh maintainers release (the SDKs and the plugin): see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

By folder (`LICENSE`): `plugins/` under Glyphh's terms; `sdk/`, `contract/` and `benchmarks/` MIT. The benchmarks'
data sets keep their own licences (CC BY 4.0).
