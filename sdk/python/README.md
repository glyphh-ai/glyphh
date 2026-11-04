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
| `beam` | A chain of models: one model's outcome is the next model's question (`--hops JSON`, `--width`, `--values`, `--miss`) |
| `learn`, `calibrate`, `backtest`, `settings`, `versions`, `activate`, `upgrade` | Tune, compare, roll back, move Ada versions |
| `export`, `job`, `cancel` | Everything out; any job's state and stage (`--wait`); stop a job |
| `bot ...` | Bots: make one from a job, run it, answer and correct its gates, trust and keep it ([below](#bots)) |

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
| `Ada` | `decide(model, data, output=, outputs=, include=["facts"], clearance=)` (`POST /v1/decide`); `beam(start, hops, width=, values=, miss=, clearance=)` (`POST /v1/beam`: a chain of models, one's outcome the next's question, one read per hop); `models()`, `model(name)`, `create_model(name, spec, ada=)`, `delete_model(name)`; `ada.versions()`, `ada.latest_stable()`; `job(id)` (its `stage`: what it is doing now), `wait(job, timeout=, on_progress=)`, `cancel_job(job)` (ends `failed`, `E_CANCELLED`; `job.cancelled`), `download(job)`; `usage()` |
| `Model` | `info()` (a `ModelInfo`: `ada`, `ada_status`, `ada_notice`), `spec()`, `set_spec(spec, note=, backtest=)`, `settings()` and `settings(changes, note=, backtest=)`, `versions()` (each with `ada`, `kernel`), `activate(version)`, `upgrade(ada=, note=, backtest=, wait=)`, `delete()`; `record_many(cases)` (a thousand a request, in chunks), `grade(id, value, output=)`, `forget(id)`; `decide(data, ...)`; `learn()`, `learn_job()`, `calibrate()`, `backtest(candidates, ada=, holdout=, output=)`; `import_file(path or bytes, format=, mapping=, partial=, learn=)`, `export(format=, to=)` |
| `Decision` | `outcome`, `probabilities`, `expected_cost`, `ask`, `receipts`, `facts`, `outputs`, `model`, `version`, `ada`; reads as 3.0's `Result` too (`done`, `status`, `data`) |
| `Beam` | `outcome` (the heaviest end), `p` (its share of the mass that arrived), `ends`, `paths` (each end's likeliest path: `value`, `p`, `trail_p`, `steps`), `lost`, `hops` (each `model`, `version`), `ada`, `data` |
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

## Bots

A bot is a program that controls a Claude agent: a folder in `~/.glyphh/bots/<slug>/` (`GLYPHH_BOTS` moves it)
holding `bot.json` (a loop of steps, its gates, what it touches), `agent.md` (its Claude agent), `program.py` (its
code steps) and `skills/*/SKILL.md`. The runner walks the loop: a `run` step is a `program.py` function; a `gate` is
an Ada model of the bot's own that learns from your answers (under its confidence, or with no precedent yet, you are
asked, and your answer is kept as a precedent, so it asks less run after run); an `agent` step is Claude, called lean
(`claude -p` with the bot's agent, no tools, no MCP servers, no settings, no session kept), with the step's skill and
the bot's memory before it: its own memory, instructions and personality models, and your glyphh
(`me-*-agentic-memory-*`) when you have one. Hard gates are code: a run step answering `{"_end": "why"}` ends the run,
and a step with an `approval` waits for your yes until the bot is trusted to act alone. Claude Code's `claude` must
be on the PATH (`GLYPHH_CLAUDE` names another).

The orchestrator makes bots and learns to make them, with its own memory and three gates (`orch-make-bot`,
`orch-trust-bot`, `orch-keep-bot`), each learning only from your verdicts and the bots' records: `glyphh bot new`
asks make_bot, then a builder (`claude -p` with Read and Write, in the new bot's folder only) writes the package from
[`BUILDING.md`](src/glyphh/bots/BUILDING.md), an example bot and what earlier bots taught it; the package is checked
(a bot that may send, pay or delete with no approval step, or touches more than you said, is set aside), installed
and trusted `ask_all`. Every run is kept in the orchestrator's memory.

The gates (3.9), each declared in bot.json and enforced by the runner:

- **Per-item gates**: a `gate` step with `"each": "$fetch.items"` decides every item of a list; the items Ada is sure
  of at once, the unsure ones asked as one batch a run (one by one at a terminal; in a routine the run stops with the
  list and `glyphh bot continue SLUG 1=read 2=skip rest=skip` answers them all). The step's data is a list per
  outcome (`$worth.read`) and each item's decision, who made it and P.
- **Asking policy per gate**: `ask_below`, `min_precedents`, `audit` (a share of sure calls still asked), `shadow`
  (always asked, agreement measured), `max_questions` a run and a `default` for the rest.
- **World-answered gates** (`"world": true`): the case is kept until `glyphh bot outcome` (or
  `ctx.gate(g).record_outcome`) records what really happened. **Ladders** (a `ladder` step): the cheapest of ordered
  options a gate predicts will work, up a rung on a failed `check`, what it took recorded. **Learned approvals**
  (`approval_gate`): a yes/no gate that stands in for the person only when it is sure and trust allows; trust
  `ask_outward` asks only for steps that send, pay or delete, and nothing pays or deletes alone. **Agent output
  gates**: an agent step's `schema` (JSON Schema) and `check`, one retry, then the run fails.
- **Hard gates**: `limits` (`usd_per_run`, `usd_per_day` from Claude's reported cost and `ctx.spend`;
  `runs_per_day`; `quiet_hours`; `max_items`; `seconds`, `agent_turns`, `steps`), `requires` (a small safe
  expression over earlier data: skip the step or end the run), `glyphh bot pause`; all refused at load if malformed.

```bash
glyphh bot install examples/bots/hn_reader        # the demo: a per-item gate on Hacker News's front page
glyphh bot run hn_reader                          # asks you about the stories it is unsure of, one batch a run
glyphh bot report hn_reader                       # report.html: who decided each story, the ask rate falling
glyphh bot install examples/bots/launch_watch     # its gate and memory models in Ada, its seed lines
glyphh bot run launch_watch                       # asks you at the gate until it has learned your days
glyphh bot wrong launch_watch <run> skip          # the gate got that run wrong: what it should have been
glyphh bot routine launch_watch                   # launchd on a Mac (elsewhere, the cron line to add)
glyphh bot new "each morning, sum up my repo's new issues" --recurs 7 --touches read_only
glyphh bot review                                 # trust_bot and keep_bot for every bot, from its record
glyphh bot verdict launch_watch trust ask_outward
```

| Command | Does |
|---|---|
| `glyphh bot init`, `check FOLDER`, `install FOLDER\|SLUG [--job J]` | The orchestrator's models; a package checked (every problem at once); a bot installed |
| `glyphh bot new JOB [--recurs N] [--touches T] [--answer make\|not_yet\|no]` | make_bot, then the builder; `needs_input` until Ada or you decide |
| `glyphh bot run SLUG [--routine]`, `continue SLUG [ANSWER ...]` | One run; a question at the terminal is asked there, in a routine (or with no terminal) the run stops `needs_input` until `continue` (a batch: `1=read 2=skip rest=skip`, or a JSON map) |
| `glyphh bot wrong SLUG RUN\|last OUTCOME [--gate G] [--item N]` | A gate's call (or one item's) corrected, kept as a precedent and counted against the bot's record |
| `glyphh bot outcome SLUG RUN\|last GATE [ITEM] OUTCOME` | What really happened to a case a gate decided, kept as a precedent |
| `glyphh bot gates SLUG [--runs N]`, `report SLUG` | Each gate's record (precedents, Ada vs you, ask rate, audits, shadow, overrules); `report.html` in the bot's folder |
| `glyphh bot pause SLUG [--why W]`, `resume SLUG` | The kill switch: a paused bot refuses to run, its routine included |
| `glyphh bot status [SLUG]`, `review [--answer BOT.GATE=OUTCOME ...]`, `verdict SLUG trust\|keep OUTCOME` | The orchestrator and its bots, or one bot's gates, memory and runs; trust and keep from records; your call |
| `glyphh bot routine SLUG [--remove]` | `glyphh bot run SLUG --routine` on the bot's cron: `~/Library/LaunchAgents/ai.glyphh.bot.<slug>.plist` on a Mac, else the cron line |

The API key is `GLYPHH_API_KEY`, else `GLYPHH_API_KEY=` in `~/.glyphh/bots/.env` (keep it mode 600), else the key
`glyphh login` kept. Ada model names: `bot-<slug>-gate-<gate>`, `bot-<slug>-<memory|instructions|personality>` and
`orch-<...>`, at most 63 characters (a slug is at most 46). From Python, `glyphh.bots`: `Orchestrator(ada)`
(`install`, `new`, `runner(slug)`, `review`, `verdict`, `status`), `Runner` (`run`, `resume`, `wrong`, `outcome`, `pause`, `unpause`, `gates`, `report`, `status`),
`Bot.load(folder)`. Examples: [`examples/bots`](https://github.com/glyphh-ai/glyphh/tree/main/examples/bots).

## Your local runtime: programs and CLIs

`Runtime` is a client for rrotor, the runtime you install on your own machine (a Docker image, bound to
`127.0.0.1:7777`; the glyphh plugin's `rrotor` skill installs it from Claude). It is not Ada Cloud and shares nothing
with it but this package: it hosts your **programs** (a `glyphh.json` manifest and `program.py`, run in a sandbox,
with a local secrets vault, cron schedules, a SQLite database and approvals) and your **CLIs** (a kind of program,
`"kind": "cli"`, run one command at a time in the same sandbox). Glyphh only grants it a licence; with none it runs
as Community.

```python
from glyphh import Runtime

rt = Runtime()                                    # RROTOR_URL or http://127.0.0.1:7777; RROTOR_TOKEN or ~/.glyphh/rrotor/token
rt.deploy("./daily_sales")                        # the folder's HEAD commit, as a git bundle (or repo=, commit=)
run = rt.call("daily_sales", "start", {"day": "2026-10-30"})
if run.needs_approval:                            # show the person run.prompt; only on their yes:
    run = rt.approve(run.run_id)                  # or rt.approve(run.run_id, False)
print(run.status, run.data)

rt.set_secret("github", "GH_TOKEN", token)       # kept encrypted on the runtime; never read back
out = rt.run_cli("github", ["pr", "list"])        # out.exit_code, out.stdout, out.stderr
```

| | |
|---|---|
| `Runtime` | `programs()`, `program(name)`, `deploy(path, commit=)` / `deploy(repo=, commit=, token=)` / `deploy(bundle=, commit=)`; `call(program, function, inputs, version=, clearance=)`, `resume(run_id, answer)`, `approve(run_id, approved=True)`, `cancel(run_id)`, `run(run_id)`, `log(run_id)`, `approvals()`; `secrets(program)`, `set_secret`, `delete_secret`; `schedules()`, `pause_schedule`, `resume_schedule`; `clis()`, `run_cli(cli, args, stdin=, files=)`; `licence()`, `set_licence(key)`, `health()` |
| `Run` | `run_id`, `program`, `version`, `function`, `status`, `data`, `step`, `prompt`, `seconds`; `done`, `waiting`, `needs_approval`, `needs_input`, `failed`, `ended`; a CLI command's `exit_code`, `stdout`, `stderr`, `files` |
| `Program`, `ProgramVersion`, `RunInfo`, `Approval`, `Secret` (`name`, `declared`, `set`: never a value), `Schedule`, `Cli`, `Licence` | The API's answers, typed (`body` keeps each one's JSON) |
| `RrotorError` | An `AdaError` too; typed by code: `RrotorAuthError`, `RrotorForbiddenError`, `LocalOnlyError`, `ProgramMissingError`, `FunctionMissingError`, `RunMissingError`, `ScheduleMissingError`, `ManifestError`, `DeployError`, `InputsError`, `RunStateError`, `NotProgramError`, `NotCliError`, `CliDeniedError`, `NotHeadError`, `LicenceError`, `NotInPlanError`; `E_UNREACHABLE` when rrotor is not running |

Reads are sent again while rrotor is unreachable for a moment; a write never is. A self-hosted rrotor is
`Runtime("https://rrotor.example.com", "<a runtime key>")`. Its shapes are in
[`contract/runtime.json`](https://github.com/glyphh-ai/glyphh/tree/main/contract), apart from Ada's contract.

## License

MIT (`LICENSE`).
