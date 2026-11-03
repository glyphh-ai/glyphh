# Bots: Claude bots a person makes for themselves

A bot is a Claude agent with Glyphh's tooling: a Claude that does one job for the person who made it, the way they
would do it, again and again (watch a launch each morning, triage an inbox, keep a reading list, chase a PR). **Claude
is the bot**: it drives every run, decides each step and calls the tools; Glyphh gives it what makes it that bot and
not any Claude:

| Part | What | Where it comes from |
|---|---|---|
| **Agent** | Who the bot is: its name, its job and its system prompt, the tools it may use, its model | A Claude agent definition, packaged with the bot |
| **Memory** | The bot's own personality, rules and memory, plus the person's glyphh read alongside | A template (`templates.md`), installed per bot |
| **Skills** | `SKILL.md` files: how the bot does each part of its job | Packaged with the bot |
| **CLIs** | The command-line tools it may run, each with `allow` and `approvals` patterns | Packaged with the bot |
| **Program** | The loop it follows each run, and the code it calls for work code does better than Claude | Packaged with the bot |

A bot is the person's alone: nobody else calls it, sees it or shares its memory. It runs in **the person's own Claude
session**, so there is no runtime to host: Claude Code on their computer, a Claude Code cloud session, or Cowork. Its
**routine** (a scheduled task, a webhook or a PR event that wakes a session) starts it; the session is the runtime.
rrotor stays shelved: none of this needs it.

## 1. The package

A bot is a folder, `~/.glyphh/bots/<slug>/` on a computer, kept in the person's glyphh on the server so that every
session they open can pull it (§4):

```
bot.json        the manifest
agent.md        the Claude agent: frontmatter (name, description, tools, model) and its system prompt
program.py      the program's code functions (optional: a bot can be all Claude)
skills/*/SKILL.md
tests/          optional, run by `glyphh bot test`
```

`agent.md` is a Claude Code agent definition (`.claude/agents/*.md`), so Claude Code runs the bot as itself or as a
subagent; Cowork and the Claude Agent SDK read the same file. Its system prompt is the bot's job in the bot's words;
Glyphh adds the loop, the memory and the CLI rules to it when the bot starts (§3).

`bot.json` (unknown keys refused, as everywhere):

| Field | What |
|---|---|
| `slug`, `name`, `summary`, `version` | As a template's; `slug` `^[a-z][a-z0-9-]{0,30}$` |
| `seed` | `{personality[], instructions[], memory[]}`: what the bot starts knowing, remembered at install |
| `reads_glyphh` | `true` (the default): the person's own personality and rules are put before the bot too, theirs first |
| `clis` | `{name: {command, allow[globs], approvals[globs], env{"X":"secret:NAME"}}}`, the rrotor CLI block without `install`, `home` or `image`: the CLI is one already on the computer or in the cloud environment |
| `hosts` | The HTTPS hosts the program's code reaches |
| `secrets` | Names only (`^[A-Z][A-Z0-9_]{0,63}$`); values come from the environment (§5), never the package |
| `loop` | The program's loop: `[{id, does, ...}]`, below |
| `routine` | `{cron?, tz?, on?}`: when it runs by itself; `on` is `webhook` or `pr` |
| `limits` | `{minutes, turns}`: a run's bounds |

### The loop

The loop is what the bot does each run, in order. It is the bot's checklist, not a script that drives Claude: Claude
reads it, works through it with its skills and memory, and may call code for a step.

```json
"loop": [
  { "id": "numbers", "does": "Take today's stars, issues, PRs and downloads", "call": "numbers" },
  { "id": "keep", "does": "Keep them beside the earlier days", "call": "keep" },
  { "id": "summary", "does": "Write today's summary against the last week", "skill": "launch-summary", "remember": true },
  { "id": "email", "does": "Email the summary through Gmail", "approval": "email" }
]
```

- **`call`** names a function of `program.py`, `def name(ctx, inputs) -> Result`, the rrotor shape kept (`done`,
  `needs_input`, `needs_approval`, `failed`; `ctx.cli`, `ctx.http`, `ctx.checkpoint`, `ctx.data`, `ctx.secrets`,
  `ctx.log`), so a shelved rrotor program's code ports unchanged. Claude calls it as a tool, `glyphh bot call <slug>
  <function> [input]`, and reads its `Result`. `ctx.cli` checks the bot's `allow` patterns and runs the CLI as a plain
  process; `ctx.http` reaches only `hosts`.
- A step with no `call` is Claude's own: it does it with the named `skill`, its memory and the session's tools.
- **`approval`** stops before the step for the person's yes. In a session the person is in, Claude asks them; in a
  routine nobody is watching, the run stops there as `needs_approval` and the person is told (§3).
- **`remember`** has Claude keep what the step taught it in the bot's memory.

A run is the loop once. Claude marks each step with `glyphh bot step <slug> <id> done|failed|needs_approval [why]`,
kept in `~/.glyphh/bots/<slug>/runs.sqlite` with each call's checkpoints, so a stopped run continues from its step,
as a rrotor run did.

## 2. Memory

Installing a bot installs the `bot-memory` template for it: Agentic memory's spec and three kinds (`memory`,
`instructions`, `personality`), its models named `me-<user hex>-bot-<slug>-<key>`, so each bot remembers on its own
and removing a bot deletes only its memory. Its `seed` is remembered at install. When the bot starts, and before each
step, its memory for the step (and, with `reads_glyphh`, the person's rules and personality) is put before Claude
through the same `POST /v1/me/glyphh/context`, now taking `bot` and `step` (§4); the bot's own `glyphh_remember`,
`glyphh_recall` and `glyphh_forget` take `bot` so what it keeps lands in its memory, not the person's.

## 3. Running it

`glyphh bot start <slug>` pulls the package if it is not on the computer, then starts Claude as the bot: `claude
--agent <slug>` with the bot's agent installed in `~/.claude/agents/`, its system prompt followed by the loop, its
memory and its CLI rules, and its CLI patterns written into the session's permissions (§5). Claude then drives the run.
The same bot runs everywhere Claude does:

| Where | Started by | What it gives |
|---|---|---|
| Claude Code on the person's computer | `/bot <slug>`, `glyphh bot start <slug>`, or `/loop` | Their own CLIs, files and sign-ins; runs while the computer is on |
| A Claude Code cloud session | The bot's routine, made a scheduled task at install (`create_trigger`, a fresh session per run, its prompt `glyphh bot start <slug>`), or a webhook / PR event | Runs with the computer off; cron at most hourly; the cloud environment holds its CLIs and secrets |
| Cowork | Cowork's own scheduled tasks, with the bot's agent and skills installed as a Cowork plugin | The same, for people who don't use Claude Code |

A routine run nobody watches ends `done`, `failed` or `needs_approval`; the last two push to the person's phone with
the run's step and why, and `/bot continue <slug>` (or answering the push in that session) carries it on. Every run's
outcome is kept in the bot's memory as `memory` (`when`: the run), so the bot knows what it did last time.

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
- The agent's `tools` frontmatter is what the bot may use; its CLIs reach Claude Code's permissions as `Bash(<command>
  <allow>)` rules for the bot's session, approvals as `ask` rules, so Claude's own shell calls are held to the same
  patterns `ctx.cli` checks (`E_CLI_DENIED` outside `allow`).
- `approval` is how a bot that sends, pays or deletes asks first. A routine run never approves its own step.

## 6. The tools Glyphh ships

- **The `bot` skill** (plugin): "make me a bot that…" interviews the person for the job, writes `agent.md`,
  `bot.json`, the skills and any code, runs it once with them watching, then saves it and sets its routine.
- **`glyphh bot`** (SDK 3.8): `new`, `start`, `continue`, `call`, `step`, `test` (the code with fake CLIs and HTTP,
  rrotor's Harness kept), `pull`, `save`, `list`, `remove`.
- **`/bot`** (plugin): the list with each bot's last run; start, continue and pause.
- **The platform**: a Bots page listing them, their runs and memory.

## 7. Build order

1. The package (`agent.md`, `bot.json`), `glyphh bot start`, `call` and `step` on the computer, with `launch_watch`
   ported as the first bot.
2. Bot memory (`bot-memory` template, `context` and the memory tools with `bot`) and the server's `/v1/me/bots`.
3. The `bot` skill and `/bot`; routines as cloud scheduled tasks; the push on `needs_approval`.
4. Cowork (the bot as a Cowork plugin) and the connector's bot tools, then the library's Glyphh-made bots and the
   platform page.

## 8. Open

- Whether a bot's memory should be its own (above) or a slice of the person's glyphh.
- Whether a cloud routine runs one session per run (simple, above) or one long-lived session per bot woken each time
  (keeps context, costs more).
