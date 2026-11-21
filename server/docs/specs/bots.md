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
| `GET /v1/bot-templates?q=`, `GET /v1/bot-templates/{slug}` | The bots Glyphh ships (`ops/bots/library/*.json`): `{slug, name, summary, description, look, model, instructions, skills, spec, apps, tools, gates}` |
| `POST /v1/bot-templates/{slug}/install` | `{name?}` → 201, the org's own copy, each app's tools scoped to its first connection of that app; an app not connected is 422 `connections` with `apps` |
| `GET /v1/bot-approvals` | `{runs}`: every run waiting on the person, oldest first |
| `GET`/`POST /v1/bots`, `GET`/`PATCH`/`DELETE /v1/bots/{slug}` | A bot: `{id, slug, name, summary, look, mascot, instructions, model, permission_mode, voice, spec, skills, gate_models, connections: [{connection_id, app, app_name, tools}], created_at, updated_at, last_run}`; a slug taken is `E_CONFLICT` |
| `PUT /v1/bots/{slug}/connections` | `{connections: [{connection_id, tools}]}` → the bot (checked again) |
| `GET /v1/bots/models` | `{models: [{id, name, input_cents_per_mtok, output_cents_per_mtok, own_key_input_cents_per_mtok, own_key_output_cents_per_mtok, default}], markup_pct}` |
| `GET /v1/bots/voices` | `{voices: [{id, name, accent, gender, default}], samples}` |
| `POST /v1/bots/draft` | `{messages, draft?}` → `{reply, draft: {name, summary, look, mascot, instructions, model, spec, skills, apps: [{app, tools}], connections} \| null, problems, missing_apps}` |
| `POST /v1/bots/mascot` | `{prompt}` → `{mascot}`, safe SVG |
| `GET /v1/bots/{slug}/gates` | Per gate: its precedents, how often it asked and was right |
| `POST /v1/bots/{slug}/runs` | `{input}` → 202, the run queued; a live run already is `E_CONFLICT` |
| `GET /v1/bots/{slug}/runs`, `GET /v1/bot-runs/{id}` | A run: `{id, bot_slug, status, input, output, error, log, data, question: {question, options, batch, answer_with}, input_tokens, output_tokens, cost_micros, own_key, created_at, started_at, finished_at}` |
| `POST /v1/bot-runs/{id}/answer` | `{answer}` (an option; for a batch `N=option`, `rest=option` or a map) → 202; one that does not fit is 422 |
| `POST /v1/bot-runs/{id}/wrong` | `{outcome, gate?, item?}` → `{gate, said, now}`, learned as a precedent |
| `POST /v1/bot-runs/{id}/cancel` | A waiting run, failed `cancelled` |
| `GET`/`PUT`/`DELETE /v1/bot-key` | `{set, hint, set_at, glyphh_key}`; `PUT` takes `{key}` |

Without Pipedream set up (`GLYPHH_PIPEDREAM_CLIENT_ID`, `_CLIENT_SECRET`, `_PROJECT_ID`) every connections route
answers 503 `E_UNAVAILABLE` `pipedream_off`. The connector's tools: `bot_guide`, `bots`, `bot`, `bot_create`,
`bot_update`, `bot_delete`, `bot_connections_set`, `bot_models`, `bot_run`, `bot_runs`, `bot_run_get`,
`bot_run_answer`, `bot_run_wrong`, `bot_run_cancel`, `bot_gates`, `connections`, `connection_apps`, `connection_link`,
`connection_tools`, `connection_permissions_set`, `bot_approvals`, `bot_templates`, `bot_template`,
`bot_template_install`, `bot_draft`, `bot_mascot`, `bot_voices`.

**Permission mode.** Each tool on a connection is allowed, asked about or denied (a tool never set is unset), and the
bot's `permission_mode` says which of its tool steps wait for the person's yes (`ops/bots/cloud.py`, `asks`): `ask`
(the default, and what bots did before it existed): each, unless its connection allows the tool; `connection`: only
those its connection says to ask about; `auto`: none. A step that waits does so as `use <tool>` (unless the step has
an approval already), so it shows in the approvals queue; a denied tool fails the step that runs it, in every mode,
saying where to allow it. A step's own `approval` in the loop always asks.

**The marketplace** ships, beside Inbox Triage, Support Triage (Gmail to Slack, a three-way gate), Meeting Prep
(Google Calendar to Notion), PR Review Digest (GitHub to Slack), Lead Scoring (`$input` read by Claude into leads, a
gate scoring each, Google Sheets), Weekly Report (GitHub to Notion, a one-case gate before filing) and News Brief (no
connection: `fetch` from a public API). Each installs, checked by the SDK, once its apps are connected.

Not yet: who in the org may use a connection or a bot, schedules, running a cloud bot on a chosen rrotor.
