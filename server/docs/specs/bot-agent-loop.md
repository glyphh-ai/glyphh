# A bot is a Claude agent you talk to, driven by its instructions

> **Ruling, 2026-11-23.** A bot is the Agent SDK loop driven by its instructions. Ada is not a gate in front of the
> tools: it is two tools the instructions direct (`decide`, `ask_person`, section 4). The permission callback holds
> only allow / ask / deny and the permission mode (section 5). `gates` stays as a storage name (`spec.gates`,
> `bot-<slug>-gate-<name>`, `bot_decisions.gate`, the `/gates` route). A bot may have a program beside it, a
> deterministic workflow: [programs.md](programs.md).

The design for the bots' engine (2026-11-22). It replaces the fixed loop of steps (`spec.loop`, walked by
`glyphh.bots.Runner`) with one Claude Agent SDK conversation turn per run. `bots.md` section 9 and
`architecture.md` say what is built; this file says why, and what each repo owes the others.

## 1. Why

A person typed "Hi there" to the PR Review Digest bot. The loop's first step ran a GitHub search with that text, found
a stranger's issue titled "Hi there" and asked whether to review it. The loop was the fault: the chat text was only
`$input` for whichever step named it, and nothing could answer a person. In the reference app (glyphh-bot,
`src/main/claude.ts`) every bot is a Claude Agent SDK agent: `query({permissionMode, canUseTool, disallowedTools,
mcpServers})`. The platform's bots now work the same way, and stay built around Ada: what a bot decides is still an
Ada model that learns from the person, and what it may do is still held by the server.

## 2. A run

A run is one turn of one Agent SDK session (`claude-agent-sdk`, `ClaudeSDKClient`).

| Part | What it is |
|---|---|
| System prompt | The bot's own: who it is (name, what it is for), its instructions, what it decides (each decision, its outcomes, when to use `decide`), how to answer (short, markdown, say what it can do when greeted, never invent a result). Never Claude Code's preset. |
| User message | What the person typed; for a scheduled run the bot's **standing task** (`bots.task`, "What it does when it runs on its own"); for a connector tool the message the tool makes. |
| Know-how | The bot's plugins (section 7): Claude plugin packages whose skills the SDK loads natively (`plugins`, `skills`). The person's own notes are a personal plugin in the same format. |
| Tools | Exactly section 3's, as one in-process SDK MCP server named `bot`. |
| Model, effort | `bots.model`, `bots.effort` (`ClaudeAgentOptions.model`, `.effort`; a level the model does not take is left out). |
| Limits | `spec.limits`: `turns` (25), `seconds` (300), `tokens` (400,000 a run), `runs_per_day` (200). See 2.2. |

"Hi there" gets a short reply saying what the bot can do. Nothing runs unless the agent chooses a tool.

### 2.1 Statuses, questions, resume

`queued → running → done | failed | needs_input`, as before (`dispatched` on a rrotor, `skipped` by a limit). A run
that must ask the person **stops**: the SDK's permission callback answers `PermissionResultDeny(interrupt=True)`, the
turn ends (`ResultMessage.terminal_reason == "aborted_tools"`), the run is `needs_input` with its `question`, and the
CLI process exits. Nothing waits in memory. The person's answer queues the run again and it **resumes the same
session** (`ClaudeAgentOptions.resume`) with a message that says what they answered.

The session is kept by a `SessionStore` (the SDK's own protocol) in Postgres, `bot_sessions` (`run_id`,
`project_key`, `session_id`, `subpath`, `n`, `entry`), mirrored as the turn runs (`session_store_flush="eager"`). The
SDK materialises it into a fresh folder on resume, so a run answered after a deploy, a restart or on another machine
carries on. Chosen over SDK-local session files (lost with the machine) and over a transcript of our own (we would
re-implement the SDK's resume). A session is deleted when its run ends. The run's folder is
`<tmp>/glyphh-bot-runs/<run id>`, the same path each go (the store's `project_key` is the folder's name), made empty
before and removed after.

A run cut off while `queued` or `running` by its machine's restart is failed as before; one that waits is left
waiting. Cancel: a waiting run is failed `cancelled` and its session dropped; a running one has its task cancelled,
which interrupts the SDK client.

### 2.2 Limits

`turns` is `max_turns`; `seconds` an `asyncio.timeout` around the turn (the client is interrupted; the run fails
saying it ran out of time); `tokens` is checked against what the run has used when each go ends and before a resume
(over: failed, saying so); `runs_per_day` counts the bot's runs made since midnight UTC before one is queued (over:
the run is `skipped`, saying so). Spend is tokens times the bot's rate, so the token cap is the spend cap.

## 3. The tool surface

One SDK MCP server, `bot`. Names are the tool's key with `-` as `_`.

| Tools | From | Asked about? |
|---|---|---|
| The connections' tools | Each tool of `bots.scopes`: a Pipedream action, described by its component (name, description, its configurable props as a JSON schema; the app prop is filled with the connection's account, never offered) | By its permissions (section 5) |
| `decide` | When the bot has decisions (section 4) | Never asks |
| `ask_person` | Always (section 4) | It is the asking: the run stops with the question |
| `fetch` | When `spec.hosts` names hosts: a GET of JSON, https, public addresses, no redirects, 5 MB | No (read-only) |
| Built-ins (`inbox_applications`, `inbox_label`) | The Gmail built-ins a template's sidecar names (`builtins`) | `inbox_label` as an action |
| Orchestrator tools | Only the org's orchestrator (section 8): `list_bots`, `ask_bot`, `crew_start`, `crew_status`, `crew_stop` | `ask_bot`/`crew_*` never ask themselves; the bot handed the work asks by its own mode |
| File tools | Only on a rrotor with folders: `list_folder`, `read_file`, `search_files`, `write_file`, `move_file`, rrotor's own (0.8.0), scoped to the granted folders | `write_file`, `move_file`: the server's `file_change` (bots.md 14) |
| `run_script` | Only on a rrotor, only when a plugin declares scripts (section 7.4) | As an action |

Nothing else. The lock, on Glyphh cloud:

- `tools=[]`, or `["Skill"]` when the bot has a skill: no Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch,
  Agent/Task, notebooks or todo tools exist in the session. `disallowed_tools` names them too.
- `strict_mcp_config=True`, `setting_sources=[]`: no MCP server, settings file, CLAUDE.md, hook or plugin of the
  machine is read. `skills` lists exactly the bot's own.
- A `PreToolUse` hook denies any tool that is not `mcp__bot__*` or `Skill`: a second wall if a new built-in appears.
- `permission_mode="default"` with `can_use_tool`: never `bypassPermissions`.
- The process's environment: every `GLYPHH_*` variable blanked, `CLAUDE_CONFIG_DIR` inside the run's folder,
  telemetry and updates off, `ANTHROPIC_API_KEY` the key the run is billed on.

Tests prove it: the options built for a cloud bot carry no built-in tool, and the live check reads the session's own
tool list from the SDK's `init` message.

## 4. Ada: two tools the instructions direct

A bot's **decisions** are `spec.gates` (a storage name), unchanged: per name its `outcomes`, `question`, Ada `spec`,
`case` mapping (`$item.x`), policy (`ask_below`, `min_precedents`, `audit`, `shadow`, `max_questions`, `default`,
`world`), `seed`/`seed_from`. Their Ada models, names and seeds are untouched. Nothing decides in front of the
agent: its instructions say when to call these two tools, like any other (`ops/bots/agent/desk.py`, `deciding.py`).

- **`decide(decision, items[])`** asks the decision's Ada model about each item (the SDK's own policy,
  `glyphh.bots.Policy.judge`) and answers, per item, `{id, item, outcome, by, confidence, sure}`. It never stops the
  run. What Ada was sure of is kept as the run's decisions (the runner's store, copied to `bot_decisions`).
- **`ask_person`** stops the run with a question (2.1). With `decision` and `items` it is the batch question the
  platform shows (`question`, `options`, `batch: [{n, label, guess, p, why}]`), and each answer (`N=outcome`,
  `rest=outcome`, or a map: `mend.fits`) is recorded as a precedent in that decision's Ada model (unless `world`)
  and kept as a decision by the person; the session resumes with "The person answered (decision): …. Carry on with
  these." With only `question` and `options` it is the bot's own question, and the session resumes with the answer.

So the Decisions panel, Right/Wrong, relabel, confirm, cases, backtest and the nine training tools read the same
tables and the same runner state as before.

## 5. Permission before acting

`can_use_tool(tool, input)` for every tool that is not read-only. A tool is **read-only** when its Pipedream
component says so (`annotations.readOnlyHint`), else when its key's verb is one of `get, list, find, search, read,
retrieve, fetch, check, view, watch, count, lookup, download, export`; `fetch`, `list_bots`, `crew_status`,
`inbox_applications` and the reading file tools are read-only.

| The bot's "Before it acts" | An action tool | A read-only tool |
|---|---|---|
| Ask me first (`ask`) | Asks, unless its connection says allow | Runs, unless its connection says ask |
| Follow each app's settings (`connection`) | The connection's allow / ask / deny; one never set asks | The same; one never set runs |
| Act on its own (`auto`) | Runs | Runs |

A tool its connection denies is refused in every mode (a deny without interrupt: the agent is told and goes on).

Asking: the run stops with an approval question ("Send a message in Slack?", `yes`/`no`, `approval: true`, `tool`,
and `detail`, the call in plain words). A yes is kept on the run as before (`bot_runs.approvals[tool]`), now with the
digest of that very input, and is taken once, in one statement, when the resumed agent calls the same tool with the
same input. Any other input, or a second call, asks again. A no resumes with "The person said no to …".

This is enforced where the tool runs, the server, on the cloud and for a rrotor alike (section 6.2).

## 6. Where it runs

### 6.1 Glyphh cloud: the Agent SDK in the server's container (yes)

Measured in `python:3.13-slim` as uid 1000, 1 GB cap, `claude-agent-sdk` 0.2.187 against the live API:

- The wheel **bundles the Claude Code CLI as a native binary** (`claude_agent_sdk/_bundled/claude`, 2.1.330,
  379 MB on linux/arm64). **No Node.** The image grows by about 410 MB (550 MB to about 960 MB).
- Start: the client connects in 0.3 to 0.5 s; a "Hi there" turn is 1.4 s wall on Haiku.
- Memory: 205 to 230 MB resident for each run's CLI process while its turn runs; none while it waits (2.1).
- Tools: the session's `init` lists exactly the three MCP tools given and nothing else with `tools=[]`. Asked to run
  a shell, read `/etc/passwd` and fetch a URL, the agent said it had no such tools; nothing was written outside
  `CLAUDE_CONFIG_DIR`.
- Deny-with-interrupt, then resume from a `SessionStore` into an emptied folder, worked for a decision and for an
  approval.

So: **in the web process, as today's runs are** (a background task, `GLYPHH_BOT_RUNS_AT_ONCE` at once). The `app` VM
was 1 GB; four runs at once is up to 0.9 GB of CLI processes, so `fly.toml` raises `app` to 2 GB. The `adajobs`
group is the wrong home (single-threaded Ada workers, 8 GB for learns, no HTTP client or link hub). A `bots` process
group of its own is the better home once runs outgrow the web machines; it needs the run queue to leave the web
process (Redis), which is out of scope here.

What the agent can reach there: no file or shell tool exists, so the container's filesystem is unreachable through
it; the CLI itself writes only its config folder in the run's folder. It is not a kernel sandbox: the wall is that
the tools do not exist, proven by test and by `init`.

### 6.2 A rrotor

`glyphh_bot` gains `function: "agent"` (rrotor 0.9.0): the same turn, run in the run's sandbox with the Agent SDK
there. The server sends, in the `call`: `system` (the prompt), `message` (the person's text, or the resume words),
`tools` (`[{name, description, input_schema, read_only}]`: the server-side tools), `plugins` (`[{name, files:
{path: text}}]`), `skills`, `model`, `effort`, `limits`, `resume` (true on an answer), `tool_url`, `tool_token`,
`folders`/`file_tools` as today.

- Every server-side tool (connection tools, `decide`, `fetch`, built-ins, the orchestrator's) is called through
  `POST /v1/bots/runs/{id}/tool` `{tool, input}`, answered `{result}`, `{error}` or **`{ask: true}`**: the server
  has stopped the run with its question (sections 4 and 5 run on the server, with the same code as the cloud). The
  rrotor then ends the turn (`PermissionResultDeny(interrupt=True)`) and its result is `needs_input`.
- The session's transcript stays on the machine (the run's folder in the rrotor's data, kept while the run waits);
  an answer is `continue {run_id, answer}` where `answer` is the resume message, or a fresh `call` with `resume`
  when the rrotor no longer holds the run. A rrotor that lost the transcript starts the turn again from `message`.
- File tools and `run_script` run on the rrotor, in the sandbox; writes ask the server (`file_change`) as today.
- The result: `{status, data: {output, steps: [{tool, ok}], files}, tokens}`. Content stays on the machine as
  today: the server keeps status, tokens, tool names, file names and the bot's final words.
- A rrotor before 0.9.0 cannot run an agent bot: the run fails saying to update it.

As built in rrotor 0.9.0: the run's folder on the machine is keyed by the call's `tool_url` (the same for every call
of one run); the result's tokens are `data.tokens`; a read-only tool the server asks about ends the turn the same
way; `{ask: true}` may carry `question`; `run_script` is allowed by the server first (`{tool: "run_script", input:
{plugin, script, args}}` answers `{result: {allowed: true}}`, or asks) and then runs the declared script as a child
of the sandboxed worker (the interpreter by its extension; 120 s, 64 KB of output); the rrotor's image carries the
Agent SDK without its bundled CLI and uses the image's own `claude`. A PDF in a folder cannot be read by the agent
there yet (the SDK's tool results carry text and images only): a regression from rrotor 0.8.0's loop.

## 7. Templates are plugins

Ruling (2026-11-22): "Templates are skills and plugins with connector requirements, code etc."

### 7.1 The package

A template is a Claude plugin folder, in the server repo at `src/glyphh_server/ops/bots/library/<slug>/`:

```
.claude-plugin/plugin.json     name, version, description (the standard manifest)
skills/<name>/SKILL.md         the bot's know-how (frontmatter: name, description)
skills/<name>/scripts/*        optional code beside a skill
glyphh.json                    Glyphh's sidecar
```

`glyphh.json` (unknown keys refused): `bot` (`name`, `tagline`, `description`, `look`, `instructions`, `model`,
`effort`), `requires` (`[{app, tools: [key]}]`), `decisions` (today's gates, as section 4), `hosts`, `builtins`,
`task` (the standing task), `schedule`, `examples` (the prompts shown as chips), `connector_tools`, `limits`, and
`code` (`[{skill, scripts: [path], why}]`: the skills that need code), `folders` (it needs folders of a machine) and
`runs_on`.

**Where a template can run** (ruling: "Yes on code; telling the customer the template supports cloud is a pill on the
template"). `runs_on` is `["cloud", "rrotor"]`, or `["rrotor"]` for a package with any `code` or with `folders`. It
is derived from the package, and a declaration that does not match is refused (`packages.check`). The template list
and read answer it, the connector's template tools say it in their text ("runs on Glyphh cloud or a rrotor", "a
rrotor only"), and the Marketplace shows it as pills. Installing a rrotor-only template with no rrotor linked is 422
`rrotor`, with a plain sentence and `setup_url`; installed, it runs on the org's first linked rrotor, its view's
`can_run_on` is `["rrotor"]`, and putting it back on Glyphh cloud is 422 `runs_on`.

### 7.2 Installed

`bot_plugins` (`org_id`, `bot_id`, `name`, `version`, `source`: `template:<slug>`, `files`: `{path: text}`, the
manifest and the sidecar among them, `installed_at`), one row per plugin per bot, unique on (`bot_id`, `name`).
Installing a template copies the package's files into the row, so a bot keeps the version it installed. A bot may
have several plugins. Its own notes (`bots.skills`, `{name: SKILL.md}`) are written at run time as the personal
plugin `notes`; the editor's Instructions and the drafting endpoint write there.

`POST /v1/bot-templates/{slug}/install` refuses with the missing connectors until each is connected (422
`connections`, `apps`), makes the bot from the sidecar's `bot`, scopes each required app's tools to the org's first
connection of it, keeps the plugin, and its decisions' Ada models are made at its first run as before.

**A new version.** `plugin.json`'s `version` is the template's. A bot's view says `plugins: [{name, version,
latest, source}]`; `POST /v1/bots/{slug}/plugins/{name}/update` replaces the plugin's files with the library's and
adds decisions and required tools the new version names (to the bot's own connection of the app, else the org's
first; an app the new version needs that is not connected is 422 `connections`, and nothing changes). It never
touches what the person edited (name, cat, instructions, schedule, permission mode), takes no tool away, and leaves
what a decision has learned.

### 7.3 At a run

The bot's plugins are written into the run's folder and given to the SDK (`plugins=[{"type": "local", "path"}]`,
`skills=["<plugin>:<skill>", …]`, `tools=["Skill"]`).

### 7.4 Code

Code runs only where there is a sandbox: a rrotor. There the agent gets `run_script(plugin, script, args, stdin)`:
it runs one of the scripts a plugin's `code` declares, by name, inside the run's sandbox, with the folders the run
has. It is not a shell: no other command exists. On Glyphh cloud the tool does not exist and the prompt says which
skills need a rrotor, so the bot says so plainly rather than pretending.

A template may also carry a **program** (`program.py` beside `glyphh.json`): a deterministic workflow installed with
the bot as the org's program ([programs.md](programs.md)). Its steps are walked by the server, on Glyphh cloud and on
a rrotor; a `code` step of it runs only on a rrotor (`glyphh_bot`'s `code`), so a template whose program has one is
`runs_on: ["rrotor"]`.

No first template needs a script: the Resume Screener's PDF and Word reading is Glyphh's own built-in tool
(`inbox_applications`), Glyphh's code and not a plugin's, as it was.

### 7.5 The marketplace

`GET /v1/bot-templates` and `/{slug}`: `{slug, version, name, summary, description, look, apps: [{app, name,
tools}], decides: [{name, question, outcomes}], examples, task, schedule, runs_on}`. The platform keeps saying
"template" and "bot"; "plugin" and "skill" stay out of the screen (a wording question for Chris).

## 8. The orchestrator

Ruling: "The bots need the default orchestrator bot. It is always there and it should be allowed to be edited like
the others but it can't be deleted."

- `bots.role`: `bot` or `orchestrator`; one orchestrator per org (`bots_one_orchestrator`, unique on `org_id` where
  the role is orchestrator). Made with the org; the conversion (section 9) makes it for every org that has none. It
  can be edited like any bot; `DELETE` (and the connector's `bot_delete`) is 409 `orchestrator`: "The orchestrator
  is always here: you can change it, but not delete it." Its role is not a field of any request.
- Its Ada key is made the first time it needs one (a migration cannot make keys).
- Its tools, beside any app's: `list_bots` (each bot's name and what it is for), `ask_bot(bot, task)` (a run of that
  bot with that task, under that bot's own permission mode; answers the bot's words), `crew_start(task)`,
  `crew_status`, `crew_stop` (the crew's latest workspace).
- **A bot it asked that must ask the person**: the bot's run waits as any run does, and the orchestrator's run
  stops with the same question (`question.child_run`). Answering either answers the bot's run; the orchestrator
  carries on when the bot's run ends, or asks again.
- A crew's "the orchestrator picks who goes next" uses this bot (its instructions and model).
  `projects.orchestrator` is no longer chosen: the API ignores it and the conversion points every project at the
  org's orchestrator.

## 9. Bots that exist

Migration `0026_bot_agent_loop.sql` adds the columns and tables. The conversion (`ops/bots/converted.py`, run by
`python -m glyphh_server.db.schema` after the migrations, once per bot) turns every `spec.loop` bot into the new
shape. Chosen over running old bots on the old engine: two engines would keep the bug alive for exactly the bots
people already have.

- `bots.old_spec` keeps the bot's spec as it was, loop and all. Nothing reads it; it is the way back.
- A bot whose loop is a library template's (matched by its steps' ids and tools) gets that template's plugin,
  standing task and examples. Its instructions are kept when the person changed them, else the template's new ones.
- Any other bot gets a personal skill `how-it-works`, written from its loop in order (each tool step, each
  decision, each Claude step's own words), a standing task (its schedule's input, else "Do your job now."), and no
  examples.
- Kept untouched for all: name, cat, model, effort, permission mode, schedule, where it runs, folders, connections
  and their tools, decisions (`spec.gates`) with their Ada models and everything they learned, `connector_tools`,
  runs and decisions.
- `spec` keeps only what a bot has now (`gates`, `hosts`, `builtins`, `limits`, `seed`): `loop`, `takes`, `try`,
  `touches` and the loop's own limits go. A decision whose case read a loop step (`$report.title`) reads the item
  (`$item.title`). A connector tool whose `verdicts` named a loop step names the decision that step made. The
  person's own notes are kept; a template's old notes, unchanged, give way to its plugin. A template is matched by
  its loop's step ids and tools.
- A run that was waiting on the person, or out on a rrotor, is failed, saying the bot was updated.

## 10. What stays the same

Metering (admit before each go, record after: the SDK's `usage` on the result, cache reads and writes counted as
input; the org's own Anthropic key or Glyphh's; `prices.charged`, the same markup), `connector_tools` (op `run`
starts a run with a message; `verdicts` now reads a decision's results), the approvals queue, recents, schedules,
places, folders, the decisions API and training.

A run's `output` is the agent's final words. `summary` is one plain sentence for a run with no words (failed,
cancelled, skipped, waiting). `hint` is gone (always empty): the bot answers. `steps` is new: `[{tool, title, app,
ok}]`, what it used, in plain words, for the turn's "Ran N steps" fold.

## 11. The SDK

`glyphh bot` (the SDK's local runner of packaged loop bots on a person's own Claude) keeps working, unchanged: it is
a different product surface (bots.md sections 1 to 8), and the server still uses its store, policy and Ada plumbing.
The server no longer walks a loop with it. Nothing is published.

## 12. Out of scope

- Memory across runs (each run is a fresh session; the bot's `bot-memory` Ada models are not read into the prompt).
- Streaming the agent's words to the screen as they are written.
- A `bots` process group, and runs queued in Redis.
- Code on Glyphh cloud.
- Who in the org may use a bot or a connection.
