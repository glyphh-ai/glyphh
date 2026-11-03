# Glyphh

Glyphh's developer surface for **Ada Cloud** (Ada as an API that Glyphh runs): the Claude Code plugin, the SDKs and
the contracts they share. **rrotor**, the runtime you run yourself, is shelved (2026-11-02): it is not offered or
supported now, and its files below (`programs`, `deploy`, the SDKs' `Runtime` client, the plugin's `shelved/skills`)
stay as they are.

| Folder | Install | What |
|---|---|---|
| [`plugins/glyphh`](plugins/glyphh) | `/plugin marketplace add glyphh-ai/glyphh`, then `/plugin install glyphh@glyphh` | The plugin: your Glyphh account in Claude Code, the Ada skill, rrotor installed and connected from Claude, pages published to your organisation's rrotor for review, the file ledger |
| [`sdk/python`](sdk/python) | `pip install glyphh` | Ada for Python, `from glyphh import Ada`, and the `glyphh` command; Glyphh bots (`glyphh bot`, `glyphh.bots`): programs that run a Claude agent behind gates that learn in Ada; `Runtime`, a client for your rrotor |
| [`sdk/typescript`](sdk/typescript) | `npm i @glyphh-ai/glyphh` | Ada for TypeScript and JavaScript, `import { Ada } from "@glyphh-ai/glyphh"`; `Runtime`, a client for your rrotor |
| [`contract`](contract) | | JSON Schema of Ada's answers (a decision, a job, usage, a query's answer, SDK 3.0's run result, a refusal) and the fixtures both SDKs are tested against, recorded from a real server; `runtime.json` and `runtime-fixtures.json`, rrotor's answers, apart |
| [`programs`](programs) | | Example programs and apps for rrotor (a manifest, `program.py` or a page, and tests), to copy, change and deploy |
| [`examples/bots`](examples/bots) | `glyphh bot install examples/bots/<bot>` | Example bots: `hn_reader` (the demo: Hacker News's front page behind a per-item gate that learns which stories you read, asking only about the unsure ones), `launch_watch` (a morning summary behind a gate that learns which days matter), `lab` (the orchestrator as a bot, running experiments on how Claude codes best) and `coder` (each task to the cheapest model a learned gate says gets it done) |
| [`deploy`](deploy) | | rrotor with Docker Compose (on your own computer, or self-hosted with HTTPS, air-gapped or as a cluster), Helm and Terraform |
| [`benchmarks`](benchmarks) | | Ada against Claude on public data (Banking77, German Credit), with the results, the judges' prompts and the scripts |

**Ada Cloud is Ada as an API.** You describe your cases once as a JSON spec, load your history, and ask: every
answer is typed (the spec's outcomes), with calibrated probabilities, the expected cost of each choice, whether a
person should decide instead, and the precedents it stands on. No language model is in the path, the same question
gets the same answer, and a model learns one confirmed case at a time. Glyphh runs it at `https://ada.glyphh.ai`:
there is nothing to install or host. Claude reaches it through the Glyphh connector (`https://api.glyphh.ai/mcp`)
and the Ada skill; your software through the SDKs with an API key; your terminal, scripts, CI and agents with a shell
through the `glyphh` command.

## The command

```bash
pipx install glyphh             # the Python package installs `glyphh`
glyphh login                    # paste an API key (the platform's API Keys page): checked, then kept for this machine
glyphh create tickets --spec @spec.json
glyphh import tickets history.csv --mapping '{"Plan": "ticket.what.plan", "Result": "outcome"}'
glyphh decide tickets '{"ticket": {"what": {"plan": "pro", "text": "charged twice"}}}'
```

Every Ada call is a command; every answer is the API's JSON on stdout, a refusal JSON on stderr with exit code 1.
`GLYPHH_API_KEY` wins over the kept key, for CI. The full guide: [`sdk/python`](sdk/python#the-glyphh-command).

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

The shapes are in [`contract/contract.json`](contract/contract.json) (version 5), with
[`contract/fixtures.json`](contract/fixtures.json).

## rrotor, your runtime (shelved)

**Shelved (2026-11-02):** not offered or supported now, and the plugin no longer installs or drives it. What follows
describes it as it was built, kept for reference.

**rrotor is a runtime you run yourself**, a container on your machine (or your servers), driven from Claude. It hosts
two things, each sandboxed (bubblewrap, seccomp, Landlock, and an egress proxy that lets a run reach only the hosts
its manifest names):

- **Programs**: a folder with a `glyphh.json` manifest and `program.py`, deployed by commit. Its functions run with
  a local secrets vault (values encrypted on the runtime, never shown back), cron schedules the runtime fires itself,
  a SQLite database (`ctx.db`), and approvals that wait for a person before a step acts.
- **CLIs**: a kind of program (`"kind": "cli"`): a pinned command-line tool (gh, the `glyphh` command, your own)
  installed into the runtime and run one command at a time, its arguments checked against allow and approval
  patterns.

Programs are not Ada models, and rrotor runs no Ada. Glyphh's server only grants rrotor its licence; with none it runs
as Community (one node), and nothing a licence does refuses a run. Nothing of a run goes through Glyphh.

- **From Claude:** with the plugin, ask *"install rrotor"*. It finds Apple's `container`, OrbStack or Docker, runs
  `ghcr.io/glyphh-ai/rrotor` on `127.0.0.1:7777` only with a local token (kept in `~/.glyphh/rrotor/token`), and adds
  rrotor's MCP server to Claude Code: `claude mcp add --transport http --scope user rrotor http://127.0.0.1:7777/mcp
  --header "Authorization: Bearer $(cat ~/.glyphh/rrotor/token)"`. Claude then writes, deploys, calls and schedules
  programs and runs CLIs with rrotor's tools (`programs_list`, `program_call`, `program_continue`, `approvals`,
  `secret_set`, `schedules_list`, `cli_run`, ...).
- **From code:** `Runtime` in both SDKs (`from glyphh import Runtime`; `import { Runtime } from "@glyphh-ai/glyphh"`).
- **By hand, or on your servers:** [`deploy/`](deploy): Docker Compose on your own computer
  (`docker-compose.local.yml`) or self-hosted with HTTPS, air-gapped or as a cluster, Helm, Terraform.

The image is published as `ghcr.io/glyphh-ai/rrotor`; until a glyphh-ai organisation admin makes the package public
(GitHub, the organisation's Packages, `rrotor`, Package settings, Change visibility), pulling it needs a `docker
login ghcr.io` with access.

| Route (with `Authorization: Bearer <the local token>`, or a self-hosted rrotor's runtime key) | Does |
|---|---|
| `GET /v1/programs`; `POST /v1/programs/deploy` `{bundle, commit}` or `{repo, commit, token?}` | Programs and CLIs; a commit as the next version |
| `POST /v1/runs` `{program, function?, inputs?}`; `POST /v1/runs/{id}/continue` `{answer}`, `…/cancel`; `GET /v1/runs/{id}`, `…/log` | A run and its Result (`done`, `needs_input`, `needs_approval`, `failed`); answer it, stop it, read it |
| `GET /v1/approvals` | Runs waiting for a person |
| `GET /v1/programs/{name}/secrets`; `PUT`, `DELETE …/secrets/{secret}` | A program's secrets: names only back |
| `GET /v1/schedules`; `POST /v1/schedules/{program}/{name}/pause`, `…/resume` | The schedules rrotor fires |
| `GET /v1/clis`; `POST /v1/clis/{name}/run` `{args, stdin?, files?}` | The CLIs; one command: exit code, stdout, stderr |
| `GET`, `PUT /v1/licence` | The licence held and its limits; a key handed in (a local rrotor) |
| `POST /mcp` | The same, as MCP tools |

The shapes are in [`contract/runtime.json`](contract/runtime.json), with
[`contract/runtime-fixtures.json`](contract/runtime-fixtures.json) (written from rrotor's code).

## Develop

```bash
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin validate --strict plugins/glyphh
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/glyphh
(cd plugins/glyphh && node --test mcp/test/*.test.*)
(cd sdk/typescript && npm ci && npm test)
(cd sdk/python && python -m pip install '.[dev]' && python -m pytest -q)
ADA_SERVER_IMAGE=<an image of glyphh-ai/server> sh sdk/integration/run.sh   # both SDKs against a real server, in Docker
sh -n plugins/glyphh/skills/rrotor/scripts/rrotor.sh                         # the rrotor installer parses
helm lint --strict deploy/helm/rrotor && terraform fmt -check -recursive deploy/terraform
```

CI (`.github/workflows`): `plugins.yml` and `sdks.yml` check every pull request. Changes come in only by pull request,
and only Glyphh maintainers release (the SDKs and the plugin): see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

By folder (`LICENSE`): `plugins/` under Glyphh's terms; `sdk/`, `contract/`, `deploy/`, `benchmarks/` and `examples/` MIT (the
rrotor image the deploy files run is not covered by it). The benchmarks' data sets keep their own licences (CC BY
4.0).
