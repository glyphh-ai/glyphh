# Glyphh Ada: the decision engine

**A Glyphh Labs project. It's open source under Apache-2.0 and is no longer a hosted service.** Ada Cloud
(`ada.glyphh.ai`, `api.glyphh.ai`, `platform.glyphh.ai`) is being shut down. The code is all here for you to read,
run and build on. More about Glyphh: [glyphh.ai](https://glyphh.ai).

Ada is a classifier that learns from precedent. You describe your cases once as a JSON spec, load past cases with
their outcomes, then ask about a new case. Ada answers from the cases most like it:

- **Precedent, not a language model.** Each case is encoded as a hyperdimensional vector, and an answer is read
  from the precedents nearest to it. No LLM is in the path, it runs on a CPU, and the same case with the same
  precedents gets the same answer.
- **Receipts.** Every answer comes with the precedents it stands on, so each decision can be audited.
- **Typed, calibrated answers.** An answer comes as a choice, a level, a yes or no, a number or a set of labels,
  with probabilities, the expected cost of each choice, and an ask flag when a person should decide instead.
- **Hands off what it's unsure of.** Cases Ada isn't sure about go to an LLM or a person. Their answers become new
  precedents, one confirmed case at a time.

The benchmarks below are experiments, not validated production results.

## What is here

| Folder | What |
|---|---|
| [`kernel`](kernel) | `glyphh_kernel` and `glyphh_spec`: the engine itself, Python whose one dependency is numpy (Postgres/pgvector storage optional), plus its lexicon and tests |
| [`server`](server) | The Ada Cloud server (Python, Postgres + pgvector, Redis): accounts, orgs, API keys, the Ada API, jobs, the MCP connector |
| [`platform`](platform) | The web app in front of it (Hono + React): sign-in, models, keys, the staff view, and the demos that ran on demo.glyphh.ai |
| [`sdk/python`](sdk/python), [`sdk/typescript`](sdk/typescript) | The SDKs (`pip install glyphh`, `npm i @glyphh-ai/glyphh`) and the `glyphh` command |
| [`contract`](contract) | JSON Schema of Ada's answers and the fixtures both SDKs are tested against |
| [`plugins`](plugins) | Claude Code plugins: `glyphh` (the Ada skill, the connector, the command's skill) and `resume-screener` |
| [`benchmarks`](benchmarks) | Ada against Claude on public data (Banking77, German Credit), plus earlier experiments in `benchmarks/research` |
| [`demos/expenses`](demos/expenses) | The expense-approvals demo |

Each folder brought its history with it: `server`, `platform`, `kernel` (from `ada-private`), `benchmarks/research`
(from `benchmarks`), `demos/expenses` (from `ada-expenses-demo`) and `plugins/resume-screener` (from `plugins`). The
old repos are archived and point here.

## Run it yourself

The kernel on its own, with no server:

```bash
cd kernel
python -m pip install -e '.[dev]'
python -m pytest -q
```

```python
from glyphh_spec import Model, Spec
model = Model(Spec.from_json(spec_json), path="tickets.db")
model.record(data, outcomes={"team": "billing"})   # data in the spec's shape
model.decide_all(new_case)                          # every output: outcome, probabilities, receipts
```

`kernel/README.md` covers the spec, typed outputs, calibration, the thread reads and the stores.

The whole service, with Postgres and Redis:

```bash
cd server
docker compose up --build              # the API; --profile ada adds the Ada workers
docker compose --profile test run --rm --build test
```

The server's image installs the kernel from `glyphh-ai/ada-private`, at the commit `server/uv.lock` pins. That repo
is now public and archived. The Dockerfile still reads it over SSH with a deploy key (the build secret
`ada_deploy_key`). To build without a key, remove the `insteadOf` line and the key wrapper from `server/Dockerfile`,
or point the dependency at `../kernel`. [`server/README.md`](server/README.md) has the settings, and
[`platform/README.md`](platform/README.md) covers the web app.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Copyright 2026 Chris Timmerman / Glyphh AI LLC.
