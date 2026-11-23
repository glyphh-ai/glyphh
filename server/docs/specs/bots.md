# Bots: Claude bots a person makes for themselves

A bot is a Claude agent with Glyphh's tooling: a Claude that does one job for the person who made it, the way they
would do it, again and again (watch a launch each morning, triage an inbox, keep a reading list, chase a PR).

**The program controls the agent.** The usual agent is a model that decides what to do and calls tools; a bot inverts
that. Its program is the loop, and code runs it: which step comes next, what each step is given, when to stop, what
needs the person's yes, what is kept. For each step that needs judgment, the program calls the bot's Claude agent with
that step's job, its skill and its memory, and takes the agent's answer as the step's data. Claude does the work and
makes the bot what it is, and the program keeps it on its job. So a bot does the same job the same way each run: it
doesn't drift, skip a step or approve itself, and every run leaves the same record.

**Gates make it learn.** Between steps, the program asks **Ada** (Ada Cloud, `ada-cloud.md`): go on, skip, take this
branch, ask the person, or call the agent. Each gate is an Ada model of the bot's own, answering from precedent: every
time the person approves, refuses or corrects, and every time a run's outcome comes back, that is a new precedent.
So a gate that asked the person on day one stops asking once its precedents agree, and a gate in front of an agent
step answers from precedent the cases it has seen and calls Claude only on the new ones. The program stays the same
code; what it does at each gate is learned. That is what no prompt or agent alone gives: a bot that gets surer and
cheaper with every run, the reason for each choice readable as the precedents behind it.

And because a bot is a package of plain files, a Claude agent can make one: the `bot` skill (§6) is Claude as the
orchestrator's builder, writing the loop, its gates, the agent and the skills from what the person says the job is.

| Part | What | Where it comes from |
|---|---|---|
| **Program** | The loop: its steps in order, code steps run directly and agent steps handed to Claude, approvals, limits | Packaged with the bot |
| **Gates** | The program's decisions between steps, each an Ada model that learns from the person's answers and the runs' outcomes | Ada Cloud, made per bot at install |
| **Agent** | Who does each agent step: its name, its system prompt, the tools it may use, its model | A Claude agent definition, packaged with the bot |
| **Memory** | The bot's own personality, rules and memory, plus the person's glyphh read alongside | A template (`templates.md`), installed per bot |
| **Skills** | `SKILL.md` files: how the agent does each kind of step | Packaged with the bot |
| **CLIs** | The command-line tools it may run, each with `allow` and `approvals` patterns | Packaged with the bot |

A bot is the person's alone: nobody else calls it, sees it or shares its memory. It runs on **the person's own
Claude**, so there is no runtime to host: Claude Code on their computer, a Claude Code cloud session, or Cowork. Its
**routine** (a scheduled task, a webhook or a PR event) starts the program. None of this needs rrotor.

## 1. The package

A bot is a folder, `~/.glyphh/bots/<slug>/` on a computer, kept in the person's glyphh on the server so that every
session they open can pull it (§4):

```
bot.json        the manifest, with the loop
program.py      the program's code steps (optional: a loop can be all agent steps)
agent.md        the Claude agent: frontmatter (name, description, tools, model) and its system prompt
skills/*/SKILL.md
tests/          optional, run by `glyphh bot test`
```

`agent.md` is a Claude Code agent definition (`.claude/agents/*.md`), the same file Cowork and the Claude Agent SDK
read. `bot.json` (unknown keys refused, as everywhere):

| Field | What |
|---|---|
| `slug`, `name`, `summary`, `version` | As a template's; `slug` `^[a-z][a-z0-9-]{0,30}$` |
| `seed` | `{personality[], instructions[], memory[]}`: what the bot starts knowing, remembered at install |
| `reads_glyphh` | `true` (the default): the person's own personality and rules are put before the agent too, theirs first |
| `clis` | `{name: {command, allow[globs], approvals[globs], env{"X":"secret:NAME"}}}`, the rrotor CLI block without `install`, `home` or `image`: the CLI is one already on the computer or in the cloud environment |
| `hosts` | The HTTPS hosts the program's code reaches |
| `secrets` | Names only (`^[A-Z][A-Z0-9_]{0,63}$`); values come from the environment (§5), never the package |
| `loop` | The program's steps, `[{id, run|agent|gate, ...}]`, below |
| `gates` | `{name: {spec, outcomes[], ask_below, seed[]}}`: each gate's Ada spec (what it reads of the run), its outcomes, the confidence under which it asks the person, and precedents to start from |
| `routine` | `{cron?, tz?, on?}`: when it runs by itself; `on` is `webhook` or `pr` |
| `limits` | `{seconds, agent_turns}`: a run's bounds, and each agent step's |

### The loop

```json
"loop": [
  { "id": "numbers", "run": "numbers" },
  { "id": "keep", "run": "keep", "input": "$numbers" },
  { "id": "worth", "gate": "worth_sending", "reads": ["$numbers", "$keep"],
    "on": { "send": "summary", "skip": "end" } },
  { "id": "summary", "agent": "Write today's launch summary from $numbers against the last week in $keep.",
    "skill": "launch-summary", "schema": { "type": "string" }, "remember": true },
  { "id": "email", "agent": "Email $summary to the person through Gmail.", "approval": "email" }
]
```


- **`run`** calls a function of `program.py`, `def name(ctx, inputs) -> Result`, the rrotor shape kept (`done`,
  `needs_input`, `needs_approval`, `failed`; `ctx.cli`, `ctx.http`, `ctx.checkpoint`, `ctx.data`, `ctx.secrets`,
  `ctx.log`), so a shelved rrotor program's code ports unchanged. `ctx.cli` checks the bot's `allow` patterns and runs
  the CLI as a plain process; `ctx.http` reaches only `hosts`.
- **`agent`** is the step's job for Claude, with earlier steps' data (`$id`) filled in. The program calls the bot's
  agent with it (§3), the named `skill` loaded, the agent's memory for the step put before it, the bot's CLI rules
  holding its shell, and `agent_turns` bounding it. With `schema`, the answer must match it (one retry, then the step
  fails); without, it is the agent's text. A `run` function can also call the agent itself, `ctx.agent(prompt,
  schema?)`, for judgment inside code.
- **`gate`** asks the bot's Ada model `gates.<name>` to decide from what the step `reads`, and `on` sends the run to
  the step its outcome names (`end` ends the run). Under `ask_below` confidence, or for a case unlike any precedent,
  the person is asked instead, their answer recorded as a precedent, so the gate asks less as it learns. A gate's
  answer carries the precedents behind it, kept with the run.
- **`approval`** stops the program before the step for the person's yes. Someone at the session is asked; a routine
  nobody is watching stops there as `needs_approval` and the person is told (§3). The agent is never the one asked.
- **`remember`** keeps the step's answer in the bot's memory (`when`: the step and the run).

A run is the loop once. Its state (each step's data, checkpoints, where it stopped) is kept in
`~/.glyphh/bots/<slug>/runs.sqlite`, so a stopped run continues from its step, as a rrotor run did.

## 2. Memory

Installing a bot installs the `bot-memory` template for it: Agentic memory's spec and three kinds (`memory`,
`instructions`, `personality`), its models named `me-<user hex>-bot-<slug>-<key>`, so each bot remembers on its own
and removing a bot deletes only its memory. Its `seed` is remembered at install. Before each agent step the program
puts the agent's memory for that step (and, with `reads_glyphh`, the person's rules and personality) in front of it,
through the same `POST /v1/me/glyphh/context`, now taking `bot` and `step` (§4). The program keeps each run's outcome
in that memory too, so the next run's agent knows what the last one did and how it went.

Each gate is an Ada model of its own (`me-<user hex>-bot-<slug>-gate-<name>`), made from its `spec` with its `seed`
at install. The program records a precedent at every gate the person answered, every approval given or refused, and
every run whose outcome the person corrects (`/bot wrong <slug> <step>`), with the outcome that should have been.
`ada_backtest` and `ada_settings` tune a gate as any Ada model, and `glyphh bot gates <slug>` shows each one's
precedents, how often it asked and how often it was overruled.

## 3. Running it

`glyphh bot run <slug>` (the `glyphh` command, SDK) is the program: it pulls the package if it is not on the computer,
walks the loop, runs each `run` step itself and calls the agent for each `agent` step through the Claude Agent SDK,
or `claude -p --agent <slug>` where the CLI is what's signed in, on the person's own Claude sign-in. Where it runs:

| Where | Started by | What it gives |
|---|---|---|
| The person's computer | `/bot run <slug>` in Claude Code, `glyphh bot run <slug>` in a shell, or a local scheduled task | Their own CLIs, files and sign-ins; runs while the computer is on |
| A Claude Code cloud session | The bot's routine, made a scheduled task at install (`create_trigger`, a fresh session per run, its prompt `glyphh bot run <slug>`), or a webhook / PR event | Runs with the computer off; cron at most hourly; the cloud environment holds its CLIs and secrets |
| Cowork | Cowork's own scheduled tasks, with the bot installed as a Cowork plugin | The same, for people who don't use Claude Code |

A run nobody watches ends `done`, `failed` or `needs_approval`; the last two push to the person's phone with the run's
step and why, and `/bot continue <slug>` (or answering the push) carries it on from that step.

## 4. The server

| Call | Does |
|---|---|
| `GET /v1/me/bots` | `{bots}`: the person's bots, each with its version, routine and last run |
| `PUT /v1/me/bots/{slug}` | Keeps the package (a tar of the folder, at most 1 MB, `bot.json` and `agent.md` validated) and installs its memory on first put |
| `GET /v1/me/bots/{slug}` | The package, for a fresh session to pull |
| `DELETE /v1/me/bots/{slug}` | Removes it and its memory (`confirm` the slug again) |
| `POST /v1/me/bots/{slug}/runs` | Records a run's outcome (`status`, `step`, `reason`), for the list and the push |
| `POST /v1/me/glyphh/context` | Takes `bot?` and `step?` as well: the bot's memory for the step, then the person's glyphh |

The connector gets `bots`, `bot`, `bot_save` and `bot_remove`, so Cowork and claude.ai can make and keep a bot without
a shell, and the library gains bots Glyphh makes (`category: "bot"`), installed by copying the package into the
person's own. Bots count against the plan's models (each bot's memory is three, plus one per gate) and reads, like any template.

## 5. Secrets and safety

- Secrets are names in the package and values in the environment: the computer's `~/.glyphh/bots/<slug>/.env` (mode
  600), or the cloud environment's variables. The server never holds a value.
- The agent's `tools` frontmatter is all an agent step may use. The bot's CLIs reach the agent's session as
  `Bash(<command> <allow>)` permission rules, approvals as `ask` rules, so its shell calls are held to the same
  patterns `ctx.cli` checks (`E_CLI_DENIED` outside `allow`).
- Approvals live in the program, not the prompt: a step that sends, pays or deletes is marked `approval`, and a
  routine run never approves its own step.

## 6. The tools Glyphh ships

- **The `bot` skill** (plugin): "make me a bot that…" interviews the person for the job, writes the loop and its gates, `agent.md`,
  the skills and any code, runs it once with them watching, then saves it and sets its routine.
- **`glyphh bot`** (SDK 3.8): `new`, `run`, `continue`, `test` (the loop with a fake agent, CLIs and HTTP, rrotor's
  Harness kept), `pull`, `save`, `list`, `remove`.
- **`/bot`** (plugin): the list with each bot's last run; run, continue and pause.
- **The platform**: a Bots page listing them, their runs and memory.

## 7. Build order

1. The package, `glyphh bot run` with agent steps through the Agent SDK, on the computer, with `launch_watch` ported as
   the first bot.
2. Gates on Ada Cloud (made at install, asked between steps, a precedent from every answer and correction), then bot
   memory (`bot-memory` template, `context` with `bot` and `step`) and the server's `/v1/me/bots`; the benchmark is
   `launch_watch`'s gate asking less, run after run.
3. The `bot` skill and `/bot`; routines as cloud scheduled tasks; the push on `needs_approval`.
4. Cowork (the bot as a Cowork plugin) and the connector's bot tools, then the library's Glyphh-made bots and the
   platform page.

## 8. Open

- Whether a bot's memory should be its own (above) or a slice of the person's glyphh.
- Whether agent steps in one run share one agent session (context carries from step to step) or each start fresh
  (above: cleaner, each step only what the program gives it).

## 9. Hosted bots and connections (built)

The platform's bots: the packaged bots above, run by the SDK's own loop (`glyphh.bots.Runner`, `glyphh[api]`) on
Glyphh's server, with the org's connections to other services. **No code runs in the cloud**: a cloud bot has no
`program.py`; its run steps are `fetch` or one of its scoped tools, and a gate's case is mapped from fields. A bot with
code runs on rrotor. They are first-class on the platform (Bots and Connections pages) and in the connector; for now
anyone in the org may make, change and run them.

**Connections** are Pipedream Connect accounts. The org is one external user of Glyphh's Pipedream project,
`org_<org id>`; someone in the org signs in to a service on Pipedream's own page (a Connect link), and a sync then reads
the org's accounts back as its connections (the new ones added, the gone ones removed). Glyphh keeps no sign-in, only
Pipedream's account id, the app and the account's name. A connection's tools are its app's Pipedream actions.

**A bot** is a name (its slug, the org's own, at most 30 characters, fixed once made), a summary, a look (its cat:
`head`, `tail`, `eye`, `extra`, `accessory`, `pose`, the glyphh-bot mascots' parts) or a **mascot** of its own (below),
instructions (its `agent.md`), the Claude model its agent steps run on (one of those `GET /v1/bots/models` lists, its
default when none is given), its **permission mode** (below), its **voice** (one of `GET /v1/bots/voices`: Kokoro-82M's,
the open TTS model; only the choice is kept, no speech is made yet, so `samples` is false), its
spec (`bot.json`: touches, hosts, seed, gates, loop, limits), its skills (`{name: SKILL.md}`) and **per connection, the
tools it may use** (its scope). It is checked by the SDK when made and when changed, every problem said at once (422,
`problems`); fetch hosts must be public names. It gets its own Ada key, made as the person who made it and revoked when
it is deleted; its gate and memory models are `bot-<slug>-gate-<gate>` and `bot-<slug>-<kind>`. `bot_guide` (and
`ops/bots/guide.py`) says how a cloud bot is written.

**Create with AI.** `POST /v1/bots/draft` is the bot maker's next turn (`ops/bots/maker.py`): given the conversation
(`{messages: [{role, content}], draft?}`), Claude asks a short question or drafts the whole bot (name, summary, cat,
instructions, model, spec, skills, and the apps and tools it needs) from `bot_guide`'s text and the org's connected apps.
The draft is checked by the SDK as a bot being made (every tool it names counted as scoped); one the check finds wrong
is sent back to Claude once with its problems. Its apps are scoped to the org's first connection of each
(`connections`, ready for `POST /v1/bots`), the ones not connected named (`missing_apps`). It answers `{reply, draft,
problems, missing_apps}` and makes nothing. **A mascot**: `POST /v1/bots/mascot` (`{prompt}` → `{mascot}`) has Claude
draw a new black-and-white character in Spike's style as SVG; a bot keeps it as `mascot`, shown in place of its cat.
Whoever drew it, a mascot is made safe before it is kept (`ops/bots/svg.py`): only `g` and the basic shapes, numeric
and path attributes, transforms, and the two colours white and ink survive (no script, style, link, image, text,
entity, event handler or other colour), at most 30 KB; the platform shows it as an image, never as markup. Both ask
Claude on the bots' key (the org's own or Glyphh's), metered as agent steps are; with neither, 503 `anthropic_off`;
Claude failing is 503 `claude`.

**A run** is a background task in the server's own process, at most `GLYPHH_BOT_RUNS_AT_ONCE` (4) a machine, the rest
queued; a bot has one live run at a time (queued, running or waiting on the person). The bot's package is written to a
folder of its own with its runner state (`runs.sqlite`, kept on the bot between goes) and the SDK's runner walks its
loop in a worker thread: tools run as Pipedream actions as the org (the app prop filled with the connection's account),
`fetch` GETs JSON from the bot's hosts only (every address public, no redirects, 5 MB at most), gates ask Ada with the
bot's own key. A run that stops for the person (a gate unsure, an approval) is `needs_input` with its question (a batch
for a gate over many items, answered `1=answer 2=skip`); answered, it carries on; it can be cancelled. A gate's call
said wrong is learned as a precedent. A run records its machine; when that machine starts again, its runs left queued
or running are failed (`interrupted by a restart`); one waiting on the person is left waiting.

**A schedule** is chosen in plain words, never as cron: `schedule: {every, at, weekday, day, timezone, input}`, `every`
one of `off` (the default), `hour` (every hour, on the hour), `day`, `weekdays` (Monday to Friday), `week` (on
`weekday`, 0 Monday to 6 Sunday) or `month` (on `day`, 1 to 31; past a month's end, its last day), at `at` (`HH:MM`,
24 hours) in `timezone` (IANA, the person's, which the platform detects in the browser; anything else is 422), each run
given `input`. It is kept as chosen; the server works out `next_run_at` in that zone (`ops/bots/schedule.py`) when the
bot is made and whenever its schedule is given, and the view says it back (`schedule_summary`: `Every day at 9:00`;
`next_run`: `Mon 9:00`, or `Mon 15 Dec 9:00` past the week; empty when off). The minute tick fires the bots that are due
(`ops/bots/due.py`), every org's, on the ticking process (one process at a time: the tick's lock): each due bot's
`next_run_at` is worked out again from now before its run is queued, so ticks missed (the server down for hours) fire
it once, not once for each run missed; its run is the person's who made it. A bot whose run is still live is skipped
that time, as is one whose rrotor is not linked or that has no Anthropic key to run on; each skip is logged.

**Where it runs**, `runs_on`: none, Glyphh cloud (the default), or one of the org's own rrotors (those its people own;
another's is 422 `runs_on`); `GET /v1/bots/places` lists them with whether each is linked right now (its state, set at
its link's hello and close), and a rrotor deleted puts its bots back on the cloud.

**A run on a rrotor** (`ops/bots/remote.py`, `remote_in.py`, `remote_out.py`): the server keeps the bot, its state
and its runs; the rrotor runs it, as its built-in program `glyphh_bot` (rrotor 0.5, SDK 3.12: an older rrotor's
glyphh_bot answers `E_SDK`). Started by the person or its schedule, the run is refused while the rrotor is not linked
(409 `E_CONFLICT` `rrotor_offline`; its schedule skips it) or the org's tokens are spent; else it is sent down the link
as a `call` (`{run_id, program: "glyphh_bot", version: null, function: "run", inputs}`, version null: the rrotor's
active one) and is `dispatched`, with `rrotor_id` on the run. Its inputs: the bot's package by path (as the cloud
writes it, with the approvals its permission mode adds), its state (base64), `given` or `answer`, its Ada (`ada_base`,
its own Ada key), `model`, `claude: "api"` (the rrotor's `ANTHROPIC_API_KEY`, the org's own) and where its tools are:
`tool_url`, this server's `POST /v1/bots/runs/{id}/tool` (https only: a server or Ada Cloud not on https fails the
run, `not_https`), with `tool_token`, signed for that run alone, six hours. A call bigger than one link message (4 MB,
less a margin) fails the run saying so (`too_big`: run it on Glyphh cloud); a rrotor whose link dropped as the call
went fails it too, saying the rrotor is not linked.

The rrotor's `result` (`{status, data, step, prompt}`, the SDK's `RunResult.to_result`) comes back up the link and is
taken once per run (its `seq` past the last the run took, from the rrotor the run is on, while the run is out there
or waits): the run's end or its question, kept as a run in the cloud keeps its own, and the bot's state from it. The
tokens it reports are the whole call's so far; what is new since the run's last result goes on the meter at the org's
own key's rate (the markup alone: it ran on the org's key). A question waits in the approvals queue as any run's does
(`runs_on` on the run says where). Answered within 14 minutes (the rrotor holds a waiting run 15), the answer goes as
`continue {run_id, answer}`; later, or after the rrotor said its wait `expired`, or when a `continue` finds no run there
(`E_RUN_MISSING`: it restarted), as a fresh `call` carrying the bot's state and the answer. Cancelled, a run out there
is failed `cancelled` here and `cancel {run_id}` goes down; a waiting one is cancelled as the cloud's are and the
rrotor's wait ended too. A result that cannot be kept fails the run, saying why. The server's restart leaves a run on
a rrotor as it is.

**Its tools** (`ops/bots/tool_calls.py`): glyphh_bot's steps that run a tool post `{tool, input, run_id}` to `tool_url`
with `Authorization: Bearer <tool_token>` and are answered `{result}` or `{error}` (the step fails, saying so): `fetch`
(a URL, or `{url, headers}`; https on one of the hosts its bot.json names, a public address, no redirects, at most
5 MB) or one of its connections' tools, run as the org, as the cloud runs them. Any other tool, host or input is an
`error`; another run's token, one past its six hours, or none is 401; a run no longer out on its rrotor is an `error`.
The approvals its permission mode asks for are in the package itself, so they wait on the rrotor as questions; but the
server does not trust the rrotor's guard alone (a rrotor taken over holds the run's token and could call the bot's
tools directly), so it holds the permissions itself (`ops/bots/approvals.py`): a tool its connection denies is
refused, never run; a tool to ask about (by the bot's permission mode and the connection, as `cloud.asks` says) runs
only by taking the person's yes. When the person answers a run on a rrotor that waits at an approval (`question.step`,
`question.approval`) with yes, the yes is kept on the run (`bot_runs.approvals`, by the tool that step runs, who said it
and when; that one alone, replacing any before; any other answer keeps none). The rrotor's call of that tool takes
it, in the same transaction it reads the run: one call, of that tool, for that run. A call with no yes to take is an
`error` (`<tool> asks the person first, and this run has no yes of theirs to it`), and every refused call is logged
(`bot tool call refused`, with the run, the tool and why). A tool to ask about is so called only from the step its
approval guards. Runs on Glyphh cloud are unchanged: the cloud runs the guard itself.

**Claude (BYOK).** Agent steps run on the org's own Anthropic API key when it has set one (`PUT /v1/bot-key`, tried with
Anthropic before it is kept, sealed, shown by its last four characters), else on Glyphh's key; the org chooses. Both
are charged: each step is let in by the hosted models' meter (`tokens.md`: the plan's allowance, then the balance) and
charged after, on Glyphh's key at Anthropic's rate plus Glyphh's markup (20%, `ops/bots/prices.py`), on the org's own
key at the markup alone (it pays Anthropic itself). `GET /v1/bots/models` lists both rates. With neither key, starting
a run answers 503 `anthropic_off`.

| Call | What |
|---|---|
| `GET /v1/connections` | `{connections: [{id, app, app_name, app_icon, account_id, label, permissions, created_at}]}` |
| `GET /v1/connections/apps?q=&cursor=` | `{apps: [{slug, name, description, icon}], next_cursor}` |
| `POST /v1/connections/link` | `{app}` → `{url, expires_at}` |
| `POST /v1/connections/sync` | `{connections}` |
| `DELETE /v1/connections/{id}` | 204; its Pipedream account deleted too |
| `GET /v1/connections/{id}/tools` | `{tools: [{key, name, description, permission}]}` |
| `PUT /v1/connections/{id}/permissions` | `{permissions: {tool: allow\|ask\|deny}}`, merged → the connection |
| `GET /v1/bots?q=` | The org's bots, those whose name, slug or summary have every word when `q` is given |
| `GET /v1/bot-templates?q=`, `GET /v1/bot-templates/{slug}` | The bots Glyphh ships (`ops/bots/library/*.json`): `{slug, name, summary, description, look, model, instructions, skills, spec, apps, tools, connector_tools, gates}` |
| `POST /v1/bot-templates/{slug}/install` | `{name?}` → 201, the org's own copy, each app's tools scoped to its first connection of that app; an app not connected is 422 `connections` with `apps` |
| `GET /v1/bot-approvals` | `{runs}`: every run waiting on the person, oldest first |
| `GET`/`POST /v1/bots`, `GET`/`PATCH`/`DELETE /v1/bots/{slug}` | A bot: `{id, slug, name, summary, look, mascot, instructions, model, permission_mode, voice, spec, skills, gate_models, connections: [{connection_id, app, app_name, tools}], schedule, schedule_summary, next_run_at, next_run, runs_on, folders: [{path, access}], effort, connector_tools, created_at, updated_at, last_run}`; a slug taken is `E_CONFLICT`; `PATCH` with `runs_on: null` puts it back on Glyphh cloud; `folders` and `effort` are section 13's |
| `PUT /v1/bots/{slug}/connections` | `{connections: [{connection_id, tools}]}` → the bot (checked again) |
| `GET /v1/bots/models` | `{models: [{id, name, input_cents_per_mtok, output_cents_per_mtok, own_key_input_cents_per_mtok, own_key_output_cents_per_mtok, default}], markup_pct, efforts, default_effort}` (section 13) |
| `GET /v1/bots/voices` | `{voices: [{id, name, accent, gender, default}], samples}` |
| `GET /v1/bots/places` | `{places: [{id, name, mode, linked, url, version}]}`: Glyphh cloud first (`id` null, `mode` cloud), then the org's rrotors (`local` or `self`) by name; `url` where a browser reads the machine itself, `version` the rrotor's (section 13) |
| `POST /v1/bots/places/{id}/ticket` | `{token, expires_in, url}`: a ticket for the person's browser to read that rrotor itself (section 13); not one of the org's rrotors is 422 `runs_on` |
| `POST /v1/bots/draft` | `{messages, draft?}` → `{reply, draft: {name, summary, look, mascot, instructions, model, spec, skills, apps: [{app, tools}], connections} \| null, problems, missing_apps}` |
| `POST /v1/bots/mascot` | `{prompt}` → `{mascot}`, safe SVG |
| `GET /v1/bots/{slug}/gates` | Per gate: its precedents, how often it asked and was right |
| `POST /v1/bots/{slug}/runs` | `{input}` → 202, the run queued (on a rrotor: `dispatched`); a live run already is `E_CONFLICT`; a bot whose rrotor is not linked is `E_CONFLICT` `rrotor_offline` |
| `GET /v1/bots/{slug}/runs`, `GET /v1/bot-runs/{id}` | A run: `{id, bot_slug, status, input, output, error, log, data, question: {question, options, batch, answer_with, step, approval}, input_tokens, output_tokens, cost_micros, own_key, runs_on, kind, project_slug, created_at, started_at, finished_at}`; `runs_on` the rrotor it ran on (null: Glyphh cloud); `kind` `bot` (a project's pull request in the approvals queue is `project`, section 10). What the run says of itself, worked out when it is read (nothing more is kept; ops/bots/said.py, shown.py): `summary`, what happened in one plain sentence in the bot's own step and decision names (a step that ends the run early may carry `empty`, its own sentence; the runner's line stays in `log`); `hint`, when the text it was given did not fit the bot (its loop is fixed: a step reads that text only where it names `$input`), what the bot does and what to give it (the spec's `takes` and `try`); `links: [{url, title, kind}]`, the pages its steps made or touched; `apps: [{step, uri, title, html, input, result}]`, the MCP App UI resources its tool results carry; `files: [{name, did}]`, on a rrotor, the files of its folders it read and changed, by name (section 14) |
| `GET /v1/mcp-apps/resource?uri=`, `POST /v1/mcp-apps/tools/call` | For the platform as an MCP Apps host (a run's `apps`, shown inline): the page of a UI resource of the server's own (`ui://glyphh/...`, as the connector's `resources/read` answers it), and `{name, arguments}`, a connector tool called for a page as the person signed in, answered as MCP has a tool's result |
| `POST /v1/bots/runs/{id}/tool` | A bot on a rrotor calls a tool: bearer its run's tool token, `{tool, input, run_id?}` → `{result}` or `{error}`; `file_change` asks whether a file of its folders may be changed now (section 14) |
| `POST /v1/bot-runs/{id}/answer` | `{answer}` (an option; for a batch `N=option`, `rest=option` or a map) → 202; one that does not fit is 422 |
| `POST /v1/bot-runs/{id}/wrong` | `{outcome, gate?, item?}` → `{gate, said, now}`, learned as a precedent |
| `POST /v1/bot-runs/{id}/cancel` | A waiting run, failed `cancelled` |
| `GET`/`PUT`/`DELETE /v1/bot-key` | `{set, hint, set_at, glyphh_key}`; `PUT` takes `{key}` |

Without Pipedream set up (`GLYPHH_PIPEDREAM_CLIENT_ID`, `_CLIENT_SECRET`, `_PROJECT_ID`) every connections route
answers 503 `E_UNAVAILABLE` `pipedream_off`. The connector's tools: `bot_guide`, `bots`, `bot`, `bot_create`,
`bot_update`, `bot_delete`, `bot_connections_set`, `bot_models`, `bot_run`, `bot_runs`, `bot_run_get`,
`bot_run_answer`, `bot_run_wrong`, `bot_run_cancel`, `bot_gates`, `connections`, `connection_apps`, `connection_link`,
`connection_tools`, `connection_permissions_set`, `bot_approvals`, `bot_templates`, `bot_template`,
`bot_template_install`, `bot_draft`, `bot_mascot`, `bot_voices`, `bot_places`; `bot_create` and `bot_update` take
`schedule` and `runs_on`, and `bots` and `bot` say each bot's schedule, its next run (`Next run Mon 9:00`) and where it
runs.

**Permission mode.** Each tool on a connection is allowed, asked about or denied (a tool never set is unset), and the
bot's `permission_mode` says which of its tool steps wait for the person's yes (`ops/bots/cloud.py`, `asks`): `ask`
(the default, and what bots did before it existed): each, unless its connection allows the tool; `connection`: only
those its connection says to ask about; `auto`: none. A step that waits does so as `use <tool>` (unless the step has
an approval already), so it shows in the approvals queue; a denied tool fails the step that runs it, in every mode,
saying where to allow it. A step's own `approval` in the loop always asks.

**The marketplace** ships, beside Inbox Triage, Support Triage (Gmail to Slack, a three-way gate), Meeting Prep
(Google Calendar to Notion), PR Review Digest (GitHub to Slack), Lead Scoring (`$input` read by Claude into leads, a
gate scoring each, Google Sheets), Weekly Report (GitHub to Notion, a one-case gate before filing) and News Brief (no
connection: `fetch` from a public API). Each installs, checked by the SDK, once its apps are connected. A template
may carry a `schedule` (the Resume Screener's: every hour), the installed bot's own.

**Built-in tools** (`ops/bots/builtins.py`): steps any bot may run beside `fetch` and its scoped tools, by name, with
no scope. They are Glyphh's own code, not the bot's, so a cloud bot still runs no code of its own; a bot on a rrotor
calls them through its tool endpoint, as it calls `fetch`, so both places run the same code. The Gmail ones reach
Gmail's own API through Pipedream's Connect proxy (`/connect/{project}/proxy/{url, base64url}`, as the account of the
bot's first Gmail connection; `ops/bots/gmail.py`); a bot with none fails that step, saying so.

| Tool | Input | Answers |
|---|---|---|
| `inbox_applications` | `{given?, q?, most?}` | `{applications, rejected, polled}`: the application `given` holds (a resume's text, or `{resume, letter?, sender?, role?}`, the person's own: no sender checks), else the new messages of the Gmail search `q` (at most `most`, 25; 100 at most), each read whole (headers, text, attachments of at most 5 MB as PDF, DOCX or text) |
| `probe_generated` | `{applications, gate}` | `{generated, human, reference}`: the gate asked about each application (on the runner's thread, with the bot's own Ada key; `ops/bots/probe.py`), those whose nearest precedent's similarity is at least the gate's reference p5 sent on as `generated`, the rest `human` (`{id, nearest}`); a gate with no reference (unseeded, or a bot on a rrotor) is sent them all |
| `screen_verdicts` | `{applications, rejected, source, fit, probe, made}` (the gates' `decisions`, the probe's data) | `{verdicts, rejected, summary}`: per applicant its `verdict` (`strong`, `borderline`, `poor`, `spam` or `waiting`), its `fit`, `generated` and `source` each `{outcome, confidence, by}` (confidence Ada's probability, 1 for the person's answer); `generated` is `{outcome: human, by: probe, nearest, reference}` for one the probe found human |
| `inbox_label` | `{verdicts, rejected}` | `{labelled}`: each screened message labelled `Screened` and `Screened/Strong`, `/Borderline`, `/Poor` or `/Spam` (a refused one `/Spam`), the labels made where missing |

An application (`ops/bots/applicants.py`) is one item: the sender (`from`, `domain`, `sender_kind` free, company,
edu or unknown), `auth` (SPF, DKIM and DMARC as the receiving server found them, from `Authentication-Results` and
`Received-SPF`), `bulk` (`List-Unsubscribe`, `Precedence: bulk` or `Auto-Submitted`), `role` (the subject's words),
`opening` (the letter's first 300 characters), the resume's fields (`ops/bots/resumes.py`: `name`, `email`, `years`
from its date spans merged, `skills`, `titles`, `education`) and `signals` (`ops/bots/signals.py`: stock phrases per
thousand words and which, how unevenly long its sentences are, specific numbers per thousand words, long dashes,
links). Code refuses before Ada sees it a message with no sender, one whose SPF failed with no DKIM passing, and one
with nothing to screen. Measuring is code; deciding is Ada's alone.

**Seed sets** (`ops/bots/seeds.py`): a gate's `seed_from` names a set Glyphh ships (`library/seeds/<name>.json`;
another name is 422), whose cases are recorded as the gate's first precedents when its model is made (at the bot's
first run), each item made by the code a run uses and its case filled as the loop fills it; a case of the set's
`train` split is a precedent of each gate its `labels` names, one of its `test` split never is. A gate with `probe`
also gets its reference: its nearest precedent's similarity (the gate's own, on Ada's receipts) over the test split's
cases, its p5, p25, p50, p75 and p95 kept in the runner's state for `probe_generated`. The SDK ignores both keys.

**The Resume Screener** (`library/resume-screener.json`): Gmail in; `inbox_applications`; three gates over the
applicants, each its own Ada model seeded from `resume-screener` (200 past applicants to five roles, one in five held
out as the test split, generated and labelled by `scripts/resume-screener-seed.py`): `source` (`real` or `spam`,
asks under 0.7), `fit` (`strong`, `borderline` or `poor` for the role, from the role, skills, titles, years and
degree; under 0.7) and `made` (how much of it was generated: `some`, `mostly` or `fully`, from the writing's signals;
under 0.55). There is no human class: `made` holds only generated applications, and `probe_generated` before it
answers human for one with no generated precedent as close as its reference's p5, so the gate decides only the
rest. Then `screen_verdicts` and `inbox_label`. A probed-human application has no `made` call to correct. Every hour, and on demand with a resume as `$input`. What a gate is unsure of waits for the person
as one batch; `wrong` on a gate's call is learned. Its connector tools (`connector_tools`): `screen_application`,
`screen_inbox`, `applicants`, `correct` (fit), `correct_generated`, `correct_source` and `screener_answer`.

**Tools by purpose** (`ops/bots/exposed.py`, `mcp/tools/bot_tools.py`). A bot is an agent built around its Ada models,
so it shows in the person's Glyphh connector as the tools its job needs, found by Claude's tool search like any tool
(a resume screener's `screen_application`, `applicants`, `correct`), beside the generic `bot_run`. A template declares
them (`connector_tools` in `library/*.json`), an installed bot keeps its copy, and any bot may declare its own
(`connector_tools` on `POST`/`PATCH /v1/bots`, at most 20, checked with the bot: every problem said at once, 422
`connector_tools`):

```json
{"name": "screen_application", "title": "Screen an application", "description": "Screen one application ...",
 "op": "run", "args": {"resume": "The applicant's email or resume, as text"}, "required": ["resume"],
 "given": "resume", "verdicts": "fit", "wait": 45}
```

`name` is lowercase, `_` between words, at most 48 characters, never `glyphh_` (a template's); `op` is `run` (a run
of the bot: `args` its text arguments, `required` those it needs, `given` the one whose text is the run's `$input`, else
all of them as JSON; it waits up to `wait` seconds, at most 50, for the run to end or ask, and answers
`{run_id, status, input, verdicts, question?, error?}`, `verdicts` the data of the loop step it names), `runs` (its
last 20 runs, each so), `wrong` (`{run_id, outcome, item?}`: a verdict of its `gate` corrected, learned in Ada as a
precedent) or `answer` (`{run_id, answer}`: a run of it waiting on the person, answered). `wrong` and `answer` take
only the bot's own runs. Each is listed for the org (tools/list reads the org's bots); a name the server's own tools
or an earlier bot's already have becomes `<name>__<bot slug>`. Each calls its bot on transactions of its own.

**The SDK's key.** Every bots route (`/v1/bots*`, `/v1/bot-runs*`, `/v1/bot-approvals`, `/v1/bot-templates*`) takes a
person's live Ada API key (`glyphh_ak_`) as its bearer as well as their sign-in (`api/key_auth.py`): the key acts as
the person who made it, in their org, so their own code (the SDK's bots client) uses the key it uses for Ada. An
unknown, revoked or expired key is 401, and so is a bot's own Ada key (named `bot <slug>`, held where the bot runs, a
rrotor too): it is never a person, so a rrotor cannot answer its own run's approvals.

Not yet: who in the org may use a connection or a bot.

## 10. Projects (built)

A project (a swarm, until 2026-11-22) is a crew of the org's bots, in no order, working on one GitHub repo from a set
of instructions, one bot at a time, each turn a pull request. There is no speaking order and there are no rounds: on
its turn a bot reads the repo as it stands and the instructions, and the run goes on until the crew or its
orchestrator says it is done, or a safety cap is reached. It runs headless; nothing is spoken unless someone is
watching and has asked for it. `projects`: `slug` (from its name, kept), `name`, `repo_url`
(`https://github.com/<owner>/<name>`), `base_branch` (`main`), `members` (1 to 8 of the org's bot ids, each once, a
set), `instructions` (the brief given on the project, at most 20,000 characters) and `instructions_path`
(`PROJECT.md`: the file in the repo that holds more, read on every turn when it is there), `turn_mode`, `orchestrator`,
`review`, `runs_on`, `max_turns` (30; 1 to 200), `max_spend_cents` (none: no cap) and `narrate`.

- **Turns** (`turn_mode`). `wait` (wait your turn, the default): one bot at a time; the turn is offered to the bot
  that has waited longest and has not just said it has nothing to do, never the bot that just went while another can
  go; a bot with nothing to do changes nothing and says `PASS`, and the turn moves on. `orchestrator`: before each
  turn the orchestrator (`orchestrator`: a bot of the crew, in its own voice and on its model; none: Claude, on the
  bots' default model) reads the repo and the instructions and answers `{"next": <a bot>, "why": ..., "done": ...}`:
  the bot it names takes the turn and is told why; an answer that names nobody of the crew is taken as wait your turn
  takes it; `done` ends the run.
- **The end.** A run is `done` (`ended` says why) when two bots in a row say `DONE` on a line of its own (a crew of
  one: one), or the whole crew in a row had nothing to do (`ended: done`); when its orchestrator says so
  (`orchestrator`); or at a safety cap: `max_turns` turns taken (`max_turns`), or its turns' tokens at Anthropic's rate
  reaching `max_spend_cents` (`max_spend`).
- **Review** (`review`). `each_turn` (the default): each pull request waits for the person's merge or reject before
  the next turn. `end`: the run has a branch of its own (`project-<slug>-<stamp>`, made off the base through GitHub's
  API as it starts); every turn starts from it and is merged into it as it opens; when the run is over, one pull
  request of it all, into the base, waits for the person (merged: the run is `done`; rejected or not mergeable: it is
  `failed`, saying so). A run that merged nothing opens none. (`auto`, merged as it opens with no review, is gone:
  the migration reads it as `end`.)
- **Narrate when watched** (`narrate`): kept as chosen. The server makes no speech; the platform reads a turn aloud
  only while someone has the project open and this is on.
- **Where it runs** (`runs_on`): none, **Glyphh cloud**, or one of the org's rrotors (a rrotor deleted puts its
  projects on the cloud). Glyphh cloud has fewer tools than a rrotor: bots read and change files and open pull
  requests, but run no commands, tests or browser.

**A run** (`ops/projects/`): `POST /v1/projects/{slug}/runs {task}` (`task` may be empty: the crew works from the
instructions alone) is refused while GitHub is not connected for its repo (404 `github_app_missing` with
`install_url`, 403 `github_not_linked` or `github_no_write`: GitHub, below), with no bot of the crew left (422
`members`), while the project has a run going (409), while its rrotor is not linked (409 `rrotor_offline`), or on
Glyphh cloud with neither the org's Anthropic key nor Glyphh's (503 `anthropic_off`). A run begins with its project's
turn mode, review and caps. Nothing waits on the server: each step's result moves the run on (`engine.py`, `next`).
A step is a bot's `turn` (its branch `turn-<n>-<bot>-<stamp>`) or the orchestrator's `pick`; one step of a run is out
at a time (`project_turns_one_out`). The words every step is told (`turns.py`: the instructions, the file to read,
the task, the crew, the transcript of the last fourteen things said, the persona, the PASS and DONE rules, the
orchestrator's question) are the same module as rrotor's `programs/glyphh_swarm/swarm_turns.py`, with the same tests.
A server bot's card for them: its name, they/them, its summary as its task, its agent's prompt as its personality,
and its cat's parts as its look. The bots are read again at each step, so an edit made while the project runs is
picked up; a bot of the crew deleted since ends the run, `failed`.

**On a rrotor** (`steps.py`, `results.py`): each step is a call of rrotor's built-in `glyphh_swarm` (it keeps its
name: rrotors in the field know it by it). `turn` `{repo, base, branch, prompt, persona, model, bot_id, bot_name,
github_token}`: a fresh branch off the base, Claude Code doing the bot's part in a checkout with the rrotor's
`ANTHROPIC_API_KEY`, committed as the bot and opened as a pull request. `pick` `{repo, base, prompt, persona, model,
github_token}` (rrotor 0.6: an older rrotor fails the run, saying to update it or use wait your turn): Claude Code
reading the checkout, changing nothing, answering who goes next. Each result comes back up the link as a bot run's
does, taken once (`project_turns.remote_seq`, from the run's rrotor alone), with its `usage` (tokens). **Content
stays on the machine:** the server keeps a turn's status, tokens and pointers (branch, pull request, call) and what
the bot said at its end (the next turn's transcript), as it did for swarms; the orchestrator's reasons are used for
the next turn's words and not kept.

**On Glyphh cloud** (`cloud.py`, `claude.py`, `repo.py`): no code runs in the cloud, so there is no shell, no checkout
and no browser. A step is a task of the server's own process: the bot's Claude step (Anthropic's Messages API, on the
org's own key or Glyphh's, let in by the meter and each request charged as a bot's agent steps are) with the repo as
its tools, through GitHub's REST API with the step's own GitHub token: `list_files {under?}`, `read_file {path}`,
`write_file {path, content}` and `delete_file {path}` (a file at most 400 kB, text only; at most 60 files changed a
turn; 60 requests a step). What it wrote is held until the turn ends, then committed once on the turn's branch as
the bot (git's data API: a tree on the base's, a commit, the branch made and moved) and opened as a pull request with
each file's lines added and removed; a turn that changed nothing opens none. The orchestrator's `pick` has the two
reading tools only. Pull requests are merged, closed and their branches deleted by the server through the same API. A
cloud turn does not use the bot's connections or `fetch`, and cannot run or test what it wrote: choose a rrotor for
that. Its turns' content is on Glyphh's side already, so the orchestrator's reasons (`why`) are kept. When the
machine running a cloud step starts again, its runs with a step out are failed (`interrupted by a restart`); one
waiting on the person is left waiting.

**A turn's result.** A turn with changes is `open` (`pr_url`, `number`, `head_sha`, `files`, `said`, `title`): with
`each_turn` the run `needs_input` and the pull request waits in the approvals queue (`GET /v1/bot-approvals`, beside
the bots' runs, `kind: "project"`: "Merge PR #<n> by <bot>?", `merge` or `reject`), answered with `POST
/v1/project-runs/{id}/answer {answer}` (`merged`, or `conflict` left open with its reason; or closed, `rejected`);
with `end`, merged at once into the run's branch, and the run's own pull request waits at the end ("Merge PR #<n>,
the whole run?"). A turn with no changes is `unchanged`. A step that fails (`{status: failed, data.reason}`), or a
call that cannot go (the rrotor not linked, a turn too big), ends the run `failed`, saying why. Cancelled (`POST
/v1/project-runs/{id}/cancel`), the step out is stopped (the rrotor's `cancel`, or the cloud task) and the run
`failed` `cancelled`; an open pull request stays open on GitHub. Each turn keeps its `input_tokens`, `output_tokens`
and `cost_micros` (its tokens at Anthropic's rate for its bot's model: what the spend cap counts); a rrotor's turns
run on the org's own key there and put nothing on the meter.

**GitHub** (`ops/projects/github.py`, `ops/github_app.py`, `ops/github_repos.py`): through the Glyphh GitHub App,
never a token a person pastes, and no GitHub token is kept anywhere. (The org's pasted token, `github_keys` and
`/v1/github-key`, is gone: `0023_projects.sql` drops the table with every token it held.)

- **Connecting a repo.** A project records the installation of the App that covers its repo
  (`projects.github_installation_id`; shown as `github_connected`). It is found when a person connects the repo, which
  happens by itself when the crew's project is made (`PUT /v1/projects/crew`) and when a run starts: the server asks
  GitHub, as the App, which installation covers the repo (`GET /repos/{owner}/{name}/installation`), then, with a token
  of that installation that may only look, whether the GitHub account the person signs in with may push to it (`GET
  /repos/{owner}/{name}/collaborators/{login}/permission`: `admin` or `write`). So nobody connects a repo they could
  not change themselves, and it works the same for a repo of a person's own account and of a GitHub organisation.
  Refused: 404 `github_app_missing` with `install_url` (GitHub's page that installs the App, or adds the repo to it)
  while the App is not on the repo; 403 `github_not_linked` when the person has no GitHub sign-in; 403
  `github_no_write` when they cannot push to it. Every run asks again which installation covers the repo, so an App
  removed and installed again is connected again by the person who starts the next run, and one removed stops the
  run with the install link.
- **A turn's token.** Each step mints its own installation token (`POST /app/installations/{id}/access_tokens`): for
  the project's one repo, one hour, with `contents: write`, `pull_requests: write` and `metadata: read` and nothing
  else. On Glyphh cloud the server uses it for that step's GitHub API calls (and for the review at the end); on a
  rrotor it is sent with that call alone, in git's environment there for the turn's clone and push and for its pull
  request, never written down.
- **The App's permissions on GitHub** (what the published App must have, all on repositories): **Contents: Read and
  write**, **Pull requests: Read and write**, **Metadata: Read-only** (GitHub gives it to every App). No organisation
  or account permission, no webhook events. Its setup URL is the server's `/v1/github/callback`.
- **The picker's reads.** `GET /v1/github/repos`: the repos the person's own installation covers (the one they
  installed on the GitHub account they sign in with, `github_installations`): `{account_login, manage_url, repos:
  [{full_name, url, private, default_branch}]}`, the first 300 by name; no installation: empty, with no account.
  `GET /v1/github/repos/{owner}/{repo}/branches`: `{default_branch, branches}` (the first 100), for any repo the
  person can connect. A repo of a GitHub organisation is not in the list (an organisation's installation is not
  recorded for a person): it is connected by typing `owner/name`.

**The crew's project** (`ops/projects/crew.py`): the Bots screen never shows or names a project. `PUT
/v1/projects/crew {repo, branch, members, runs_on?, turn_mode?, orchestrator?, review?, narrate?, max_turns?,
max_spend_cents?}` finds the project for that workspace (a repo, `owner/name` or its address, and a branch, `main`
unless given), or makes it, sets it to the bots and settings given (one left out is left as it is; a new project
takes the defaults), connects GitHub for the repo, and answers the project. There is one per repo and branch for the
org: its slug is `crew-` and twelve hex digits of the two, its name `<owner>/<name> (<branch>)`.

**A run's model and effort.** `POST /v1/projects/{slug}/runs` also takes `model` (one of `GET /v1/bots/models`; none:
each bot's own, and the bots' default for Claude as orchestrator) and `effort` (`low`, `medium` or `high`; none: the
default), kept on the run (`project_runs.model`, `.effort`) and used for every step of it: the model on a rrotor and
on Glyphh cloud (and for what the spend cap counts), the effort on Glyphh cloud (Anthropic's `output_config.effort`);
a rrotor's Claude Code is not told the effort yet.

| Call | What |
|---|---|
| `GET`/`POST /v1/projects`, `GET`/`PATCH`/`DELETE /v1/projects/{slug}` | A project: `{id, slug, name, repo_url, base_branch, members: [{id, slug, name}], instructions, instructions_path, turn_mode: wait \| orchestrator, orchestrator, review: each_turn \| end, runs_on, max_turns, max_spend_cents, narrate, github_connected, created_at, updated_at}`; a slug taken is `E_CONFLICT`; an orchestrator not of the crew is 422 `orchestrator`; `PATCH` with `runs_on`, `orchestrator` or `max_spend_cents` null clears it; deleting it deletes its runs |
| `POST /v1/projects/{slug}/runs` | `{task, model?, effort?}` (`task` may be empty) → 202, its run: `{id, project_slug, task, status, ended, turn_mode, review, runs_on, max_turns, max_spend_cents, model, effort, work_branch, pr_url, number, error, turns: [{n, bot_id, bot_slug, bot_name, branch, status, picked_by, why, said, title, pr_url, number, head_sha, files, done, error, input_tokens, output_tokens, cost_micros, created_at, finished_at}], input_tokens, output_tokens, cost_micros, created_at, finished_at}`; a turn's `status` is `picking` (the orchestrator choosing; `bot_slug` empty), `running`, `open`, `unchanged`, `merging`, `merged`, `conflict`, `rejecting`, `rejected`, `failed` or `cancelled` |
| `GET /v1/projects/{slug}/runs`, `GET /v1/project-runs/{id}` | Its runs, the newest first (the last 50); one run |
| `POST /v1/project-runs/{id}/answer` | `{answer: merge \| reject}` → 202: the turn's pull request that waits, or with review `end` the whole run's; a run not waiting is `E_CONFLICT` |
| `POST /v1/project-runs/{id}/cancel` | The run ended, its step out stopped; one ended already is `E_CONFLICT` |
| `PUT /v1/projects/crew` | The crew's project for a workspace, found or made and set: `{repo, branch, members, …settings}` → the project |
| `GET /v1/github/repos`, `GET /v1/github/repos/{owner}/{repo}/branches` | The repo picker's reads (above); `POST /v1/github/install` and `GET /v1/github/installations` are the App's install link and the person's installation |

The connector's tools: `projects`, `project`, `project_create`, `project_update`, `project_delete`, `project_run`,
`project_runs`, `project_run_get`, `project_run_answer`, `project_run_cancel` (offered with or without rrotor: a
project runs on Glyphh cloud too); a project's pull request also shows in `bot_approvals`. The GitHub App is
installed in the browser, never through the chat: a run says so, with the link, when it is not on the repo.

**The old names.** Every route also answers at its swarm path (`/v1/swarms…`, `/v1/swarm-runs…`), out of the spec:
the same answers in the project's shape (the list under both `projects` and `swarms`), a body's `rounds` left out and
its review `auto` read as `end`. Each tool is still called by its swarm name (`swarms`, `swarm`, `swarm_create`, …),
never listed. The tables were renamed with their rows (`0023_projects.sql`).

## 11. Recents (built)

The Bots screen has one list of past runs, a bot's own and a crew's alike, and no approvals page: `GET /v1/recents`
(`ops/bots/recents.py`) reads the org's `bot_runs` and `project_runs` together, the newest first.

| Call | What |
|---|---|
| `GET /v1/recents?q=&waiting=&archived=&pinned=&cursor=&limit=` | `{recents: [{id, kind: bot \| crew, title, bot_slug, bot_name, project_slug, workspace, branch, runs_on, status, waiting, pinned, archived, created_at}], next_cursor, needs_you, archived_count}`. `title` is the task's first line (empty when it had none); a crew's run has `bot_name` `Crew`, its `project_slug` and its `workspace` (`owner/name`) and `branch`; `waiting` is `status` `needs_input`. `q` is found in the task, a bot's name or the workspace; `waiting` and `pinned` keep only those; archived runs are left out unless `archived` is given, which lists only them; `limit` 1 to 100 (30), `cursor` the last page's `next_cursor` |
| `POST /v1/recents/{id}/pin` \| `unpin` \| `archive` \| `unarchive` | The person's own mark on a run → the recent; no such run is 404 |
| `DELETE /v1/recents/{id}` | The run deleted for the whole org, with its turns and everyone's marks on it (pull requests stay on GitHub) → 204; 409 `run_live` while it is queued, running or waiting: cancel it first |

`needs_you` is the org's runs waiting on a person now, whatever the filters: the bots' questions and approvals and
the crews' pull requests (what each asks is still `GET /v1/bot-approvals`). Pinned and archived are each person's own
(`run_marks`: `user_id`, `run_id`, `pinned`, `archived`); `archived_count` is the person's.

## 12. Decisions: read them, train the gates (built)

Every decision a bot's gates make, one row per item per gate per run, is copied from the runner's state (its
`runs.sqlite`, the newest 5,000) into `bot_decisions` after each go, on the cloud and back from a rrotor alike
(`ops/bots/decided.py`), so a person (or Claude, through the connector) can read, search, sort and page them and train
the gates from them. The runner's own columns are copied each time (upserted on bot, run, gate, step, item number and
key); what only the server knows (`confirmed`, `precedent`, its precedent's id in the gate's Ada model) is never
overwritten. A state that is not the runner's database copies nothing.

**Readable** (`ops/bots/readable.py`): an item's `fields` are its values flattened to `name: text` (nested names joined
with a dot, a start every name shares left off, lists of plain values joined; at most 40, each at most 2,000
characters), and its `label` is a title drawn from them: the runner's label unless it is JSON (the SDK falls back to a
JSON dump), else its first `title`, `subject`, `summary`, `name`, `headline`, `label`, `snippet`, `text` or `body`,
else its first three fields; never raw JSON. `who` is `ada` (its gate's model, sure enough, or its guess in code),
`you` (the person was asked) or `default`. `now` is what it is: the correction when it was corrected (a relabel, or
what the world said), else the outcome.

**Training** goes through the gate's Ada model the way `wrong` does, as a go of the runner, so the bot must be idle
(409 otherwise): a relabel grades the decision's precedent with the new outcome (or records it, when it was never one)
and marks it corrected; a confirm records it as it is (or as corrected) and marks it `confirmed`; a case added by hand
is recorded with its outcome and kept as a decision of kind `case`; forgetting a precedent forgets it in Ada and drops
it from the decisions (a hand-made case is deleted). Many at once must be of one gate (422 `gate`). Reading one
decision asks its gate for the nearest precedents now (up to 8, nearest first, each with its item's label when it is
one of the bot's); a backtest replays the newest decisions through the gates as they stand now and says which would
change, or be asked, without touching anything.

| Call | What |
|---|---|
| `GET /v1/bots/{slug}/decisions` | `?q=` (each word a prefix, all of them), `gate`, `outcome` (what it is now), `who`, `corrected`, `since`, `until`, `run_id`, `sort` (`time`, the default, `confidence`, `gate`, `outcome`), `order` (`desc`), `cursor`, `limit` (25, at most 100) → `{decisions: [{id, run_id, gate, step, key, kind, label, fields, outcome, now, who, mode, confidence, guess, recorded, corrected, confirmed, outcomes, at}], total, next_cursor, gates}`; a cursor not one of its own is 422 `cursor` |
| `GET /v1/bots/{slug}/decisions/stats` | `?gate=&days=` (30, at most 365) → per gate: decisions, by whom, corrected, confirmed, `ask_rate`, `agreement` (Ada's guess against the person's answer), `accuracy` (Ada's calls the person checked), and the same day by day |
| `GET /v1/bot-decisions/{id}` | One, with its `case` and its nearest `precedents` `[{id, outcome, similarity, label, decision_id}]` |
| `POST /v1/bot-decisions/{id}/relabel`, `/confirm` | `{outcome}` (one of its gate's, else 422 `outcome`); none → `{decisions, precedents, said}` |
| `POST /v1/bots/{slug}/decisions/relabel`, `/confirm` | `{ids, outcome}`, `{ids}`: up to 200 of one gate |
| `POST /v1/bots/{slug}/cases` | `{gate, outcome, item \| case, label}` → 201, the gate's precedents |
| `DELETE /v1/bots/{slug}/gates/{gate}/precedents/{id}` | `{gate, id, precedents}` |
| `POST /v1/bots/{slug}/backtest` | `{gate, limit}` (50, at most 200) → `{replayed, same, changed: [{decision, then, now, ask}], would_ask, right_now}` |

The connector's tools: `bot_decisions` (search, filter, sort, page), `bot_decision` (one, with its precedents),
`bot_gate_stats` and `bot_backtest` read only; `bot_relabel`, `bot_relabel_many` and `bot_forget_case` change what a
gate learned (destructive); `bot_confirm` and `bot_add_case` add to it. Each answers in lines a person reads (`[skip]
Lunch on Friday? (gate worth, by Ada 92%; …)`), never JSON.

**A tool's answer is its list.** The marketplace's templates read a Pipedream action's answer at `$step.ret`, where its
list is: GitHub's Search Issues and Pull Requests and Google Calendar's List Events answer a list, and Gmail's Find
Email a list too, but `{messages, truncated, note}` when cut to fit, which `ops/bots/props.py` (`returned`) turns into
the list (the note kept as `ret_note`). The templates had read `$prs.ret.items`, `$merged.ret.items`,
`$events.ret.items`, `$mail.ret.messages` and `$tickets.ret.messages`: a gate saw no items, `empty:` ended the run and
no agent step ran, so its 0 tokens were right. Migration 0024 rewrites those paths in the bots installed from them.

## 13. A bot's folders and effort (built)

Two settings a bot's owner chooses, on the bot (`bots.folders`, `bots.effort`, migration 0025) and so on `BotView`,
`POST /v1/bots`, `PATCH /v1/bots/{slug}`, and the connector's `bot_create`, `bot_update`, `bot`, `bots`
(`ops/bots/access.py`).

**Folders**, `folders: [{path, access: "read" | "write"}]`, none by default: the folders of its rrotor's machine the
bot may read (`read`) or read and change (`write`). They mean something only when the bot runs on a rrotor
(`runs_on`); on Glyphh cloud, which has no folders, they are kept and ignored. The server knows nothing of the
machine's files, so it checks their shape and nothing more: an absolute path (a trailing `/` dropped), no `..`, at most
1,024 characters, at most 20 folders, none twice; anything else is 422 `folders`, saying which in a plain sentence.
`PATCH` replaces the whole list (`[]`: none). A template's copy has none: a template knows no machine.

- **With each run.** The `call` of `glyphh_bot` carries them beside its inputs (`folders`, null for none: the link's
  `Call`). The rrotor mounts exactly those in the run's sandbox, read-only or writable as chosen, and nothing else
  of the machine (rrotor's docs/architecture.md, 5.11).
- **The machine's owner has the last word.** A rrotor offers only the folders its owner names (`RROTOR_FOLDERS`, none
  by default). A call that asks for one outside them is refused there before anything runs; its plain sentence
  ("/Users/ana/Secret is not in a folder this rrotor's owner shares with bots: it shares /Users/ana/Documents.")
  comes back as the run's `failed` result and is the run's `error`.
- **An older rrotor.** One before 0.6.0 knows no folders: a run of a bot with any is not sent there and fails saying
  to update it (the place's `version` is what it last said it runs).
- **Choosing them.** The platform's picker reads the machine itself, never through this server: `GET
  {url}/v1/folders?under=<path>` on the rrotor, `url` the place's (`GET /v1/bots/places`: a self-hosted rrotor's own
  address; a local one's `http://127.0.0.1:7777`, which answers only a browser on that computer), with a ticket from
  `POST /v1/bots/places/{id}/ticket` as its bearer. The ticket is the rrotor's work ticket (its
  `rrotord/ticket.py`): `{"kind": "work", "runtime_id": <the rrotor's id>, "sub": <the person's id>, "expires_at"}`
  signed as a licence key is (`ops/license_keys.encode`), good ten minutes, for any person of the org and only for
  one of the org's rrotors; the rrotor checks it itself, with the public key it carries. It opens the folder listing
  and the crew's work there, nothing else. What it opens is never carried or kept by this server.

**Effort**, `effort`: `low`, `medium` (the default), `high`, `xhigh` or `max`: how hard Claude works on the bot's
agent steps. It is the Claude API's own `output_config.effort`, and those five are its values (`GET /v1/bots/models`
lists them, `efforts` and `default_effort`: one list, every bot model takes each).

- **In the cloud**, each request of an agent step carries `output_config: {"effort": <the bot's>}`
  (`access.WithEffort`, around the Anthropic client the SDK's `ApiClaude` calls; `goes._claude`). `medium` is said
  too: a model's own default is not always medium (Claude Sonnet 5.5's is `high`).
- **A model that takes none** (one not in `access.EFFORT_MODELS`: today the three bot models take all five) is asked
  without it, as is a level a model does not take. A run never fails over its effort.
- **On a rrotor**, it is `glyphh_bot`'s `effort` input, applied the same way there; a rrotor before 0.6.0, whose
  `glyphh_bot` does not know the input, is sent none. Claude Code signed in on the rrotor (`claude: "cli"`) takes none.
- The bot maker's own steps and the mascot's carry none (the model's default).

## 14. A bot uses the files in its folders (built)

A bot on a rrotor with folders (section 13) uses them: its agent steps there get tools over exactly those folders
(rrotor 0.8.0's `glyphh_bot`, its docs/architecture.md, 5.10): list a folder, read a file (text, Word, PDF), search by
name or text, write a file and move or rename one, the last two only in a folder given to read and change. No
delete, no shell. So a typed task can be done by a bot that has folders ("summarise the invoices in my Invoices
folder"). On Glyphh cloud there are no folders and nothing changes. `ops/bots/files.py`.

- **Which rrotors.** The `call` carries `file_tools: true` when the bot has folders and its rrotor says it runs 0.8.0
  or later (the place's `version`). An older rrotor is not sent the input and keeps the single request a step was
  (its folders mounted and unused, as before). With it, the call also carries the run's text (`given`) each time, a
  fresh call for an answer too: the rrotor puts what the person typed before each agent step, whatever the loop
  names. So the run's `hint` ("it does not read what you type") is not said for a run whose agent steps had files.
- **Reads never ask. A change is made only on this server's word.** Before each write or move the rrotor calls the
  run's tool endpoint with `file_change` and the change's action and names, `{action: write | move, path, name, to?,
  to_name?}` (`name`: the folder's name and the way down, `Notes/Summary.md`). A change outside the folders the bot
  may change is an `error` (the most particular folder that holds the path decides, as on the machine). Otherwise
  `{result: {allowed: true}}` at once when the bot's permission mode is not `ask` (`auto`, Act on its own; and
  `connection`, Follow each app's settings: a folder is no app, and its own setting, read and change, is the say),
  and under `ask` (Ask me first) only by taking the person's yes to that very change: `{allowed: false}` means ask.
- **The question.** The rrotor then stops the step and its result is `needs_input`: "Write Notes/Summary.md?"
  ("Replace what is in …?", "Move … to …?"), `yes` or `no`, an approval; the change it names is kept with the run's question (`file`), not shown. It
  waits in the chat and in `GET /v1/bot-approvals` as any question does. A yes is kept on the run as the yes to
  that change (`bot_runs.approvals.file_change`: its action and paths, who and when; that one alone) and the
  rrotor's next `file_change` for the same action and paths takes it, in one statement: once. Any other change, or
  the same again, is `{allowed: false}` and is asked about in its turn. A no keeps nothing; the rrotor tells Claude
  the person said no, and the step goes on without it. The rrotor is the machine (it could write its own disk), so
  this is the bot's manners held in one place, the server, as its connections' tools are: not a wall.
- **Names here, contents never.** Each result of such a run names the files it read and changed so far
  (`data.files`); the server keeps them with the run as `data._files`, `[{name, did: read | written | moved}]` (the
  200 latest, a fresh call's added to what the run had), and the run's view says them as `files` (what it changed
  first, 12 at most), which the platform shows as the turn's file chips ("Invoices/March.pdf · read"). Anything
  else in what the rrotor names is dropped. What is in a file goes from the machine to Claude and nowhere else: the
  rrotor puts none of it in a step's data, the log or the bot's state, and the conversation a waiting run holds
  stays on the machine. The step's own answer (the bot's words, `output`) is kept as every run's is.
- **Tokens** are the rrotor's count as before (every request of a step's loop added up, cache reads and writes
  counted as input), metered at the org's own key's rate.
