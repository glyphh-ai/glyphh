# Bots: Claude bots a person makes for themselves

A bot is a Claude agent with Glyphh's tooling: a Claude that does one job for the person who made it, the way they
would do it, again and again (watch a launch each morning, triage an inbox, keep a reading list, chase a PR).

**The program controls the agent.** The usual agent is a model that decides what to do and calls tools; a bot inverts
that. Its program is the loop, and code runs it: which step comes next, what each step is given, when to stop, what
needs the person's yes, what is kept. For each step that needs judgment, the program calls the bot's Claude agent with
that step's job, its skill and its memory, and takes the agent's answer as the step's data. Claude does the work and
makes the bot what it is, and the program keeps it on its job. So a bot does the same job the same way each run: it
doesn't drift, skip a step or approve itself, and every run leaves the same record.

| Part | What | Where it comes from |
|---|---|---|
| **Program** | The loop: its steps in order, code steps run directly and agent steps handed to Claude, approvals, limits | Packaged with the bot |
| **Agent** | Who does each agent step: its name, its system prompt, the tools it may use, its model | A Claude agent definition, packaged with the bot |
| **Memory** | The bot's own personality, rules and memory, plus the person's glyphh read alongside | A template (`templates.md`), installed per bot |
| **Skills** | `SKILL.md` files: how the agent does each kind of step | Packaged with the bot |
| **CLIs** | The command-line tools it may run, each with `allow` and `approvals` patterns | Packaged with the bot |

A bot is the person's alone: nobody else calls it, sees it or shares its memory. It runs on **the person's own
Claude**, so there is no runtime to host: Claude Code on their computer, a Claude Code cloud session, or Cowork. Its
**routine** (a scheduled task, a webhook or a PR event) starts the program. rrotor stays shelved: none of this needs
it.

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
| `loop` | The program's steps, `[{id, run|agent, ...}]`, below |
| `routine` | `{cron?, tz?, on?}`: when it runs by itself; `on` is `webhook` or `pr` |
| `limits` | `{seconds, agent_turns}`: a run's bounds, and each agent step's |

### The loop

```json
"loop": [
  { "id": "numbers", "run": "numbers" },
  { "id": "keep", "run": "keep", "input": "$numbers" },
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
person's own. Bots count against the plan's models (each bot's memory is three) and reads, like any template.

## 5. Secrets and safety

- Secrets are names in the package and values in the environment: the computer's `~/.glyphh/bots/<slug>/.env` (mode
  600), or the cloud environment's variables. The server never holds a value.
- The agent's `tools` frontmatter is all an agent step may use. The bot's CLIs reach the agent's session as
  `Bash(<command> <allow>)` permission rules, approvals as `ask` rules, so its shell calls are held to the same
  patterns `ctx.cli` checks (`E_CLI_DENIED` outside `allow`).
- Approvals live in the program, not the prompt: a step that sends, pays or deletes is marked `approval`, and a
  routine run never approves its own step.

## 6. The tools Glyphh ships

- **The `bot` skill** (plugin): "make me a bot that…" interviews the person for the job, writes the loop, `agent.md`,
  the skills and any code, runs it once with them watching, then saves it and sets its routine.
- **`glyphh bot`** (SDK 3.8): `new`, `run`, `continue`, `test` (the loop with a fake agent, CLIs and HTTP, rrotor's
  Harness kept), `pull`, `save`, `list`, `remove`.
- **`/bot`** (plugin): the list with each bot's last run; run, continue and pause.
- **The platform**: a Bots page listing them, their runs and memory.

## 7. Build order

1. The package, `glyphh bot run` with agent steps through the Agent SDK, on the computer, with `launch_watch` ported as
   the first bot.
2. Bot memory (`bot-memory` template, `context` with `bot` and `step`) and the server's `/v1/me/bots`.
3. The `bot` skill and `/bot`; routines as cloud scheduled tasks; the push on `needs_approval`.
4. Cowork (the bot as a Cowork plugin) and the connector's bot tools, then the library's Glyphh-made bots and the
   platform page.

## 8. Open

- Whether a bot's memory should be its own (above) or a slice of the person's glyphh.
- Whether agent steps in one run share one agent session (context carries from step to step) or each start fresh
  (above: cleaner, each step only what the program gives it).
