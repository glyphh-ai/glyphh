# Bots: Claude bots a person makes for themselves

A bot is a Claude that does one job for the person who made it, the way they would do it, again and again: watch a
launch each morning, triage an inbox, keep a reading list, chase a PR. It is a package of four things:

| Part | What | Where it comes from |
|---|---|---|
| **Memory** | The bot's own personality, rules and memory, plus the person's glyphh read alongside | A template (`templates.md`), installed per bot |
| **Skills** | `SKILL.md` files: how the bot does its job | Packaged with the bot |
| **CLIs** | The command-line tools it may run, each with `allow` and `approvals` patterns | Packaged with the bot |
| **Program** | The loop it follows: its steps, in order, some code and some Claude | Packaged with the bot |

A bot is the person's alone: nobody else calls it, sees it or shares its memory. It runs in **the person's own Claude
session**, so there is no runtime to host: Claude Code on their computer, a Claude Code cloud session, or Cowork. Its
**routine** (a scheduled task, a webhook or a PR event that wakes a session) starts the program; the session is the
runtime. rrotor stays shelved: none of this needs it.

## 1. The package

A bot is a folder, `~/.glyphh/bots/<slug>/` on a computer, kept in the person's glyphh on the server so that every
session they open can pull it (§4):

```
bot.json        the manifest
program.py      the program's code steps (optional: a bot can be all Claude)
skills/*/SKILL.md
tests/          optional, run by `glyphh bot test`
```

`bot.json` (unknown keys refused, as everywhere):

| Field | What |
|---|---|
| `slug`, `name`, `summary`, `version` | As a template's; `slug` `^[a-z][a-z0-9-]{0,30}$` |
| `seed` | `{personality[], instructions[], memory[]}`: what the bot starts knowing, remembered at install |
| `reads_glyphh` | `true` (the default): the person's own personality and rules are put before the bot too, theirs first |
| `clis` | `{name: {command, allow[globs], approvals[globs], env{"X":"secret:NAME"}}}`, the rrotor CLI block without `install`, `home` or `image`: the CLI is one already on the computer or in the cloud environment |
| `hosts` | The HTTPS hosts the program's code reaches |
| `secrets` | Names only (`^[A-Z][A-Z0-9_]{0,63}$`); values come from the environment (§5), never the package |
| `loop` | The program: `[{id, do, ...}]`, below |
| `routine` | `{cron?, tz?, on?}`: when it runs by itself; `on` is `webhook` or `pr` |
| `limits` | `{seconds, steps}`: a run's bounds |

### The loop

The program is a list of steps run in order, each `run` (code) or `think` (Claude):

```json
"loop": [
  { "id": "numbers", "do": "run", "function": "numbers" },
  { "id": "keep", "do": "run", "function": "keep", "input": "$numbers" },
  { "id": "summary", "do": "think", "skill": "launch-summary",
    "prompt": "Write today's launch summary from $numbers against the last week in $keep." },
  { "id": "email", "do": "think", "approval": "email",
    "prompt": "Email $summary to the person through Gmail." }
]
```

- **`run`** calls a function of `program.py`, `def name(ctx, inputs) -> Result`, the rrotor shape kept (`done`,
  `needs_input`, `needs_approval`, `failed`; `ctx.cli`, `ctx.http`, `ctx.checkpoint`, `ctx.data`, `ctx.secrets`,
  `ctx.log`), so a shelved rrotor program ports with its code unchanged. `ctx.cli` checks the bot's `allow` patterns
  and runs the CLI as a plain process; `ctx.http` reaches only `hosts`.
- **`think`** is Claude's own turn in the session: the prompt, with the named skill, the bot's memory recalled for it
  and the earlier steps' answers (`$id`). Its answer is the step's data.
- **`approval`** on either kind stops before the step for the person's yes. In a session the person is in, Claude asks
  them; in a routine nobody is watching, the run stops there as `needs_approval` and the person is told (§3).
- **`remember`** (`true` on a `think`) lets Claude keep what the step taught it in the bot's memory.

A run is the loop once. Its state (each step's answer, checkpoints, where it stopped) is kept in
`~/.glyphh/bots/<slug>/runs.sqlite`, so a stopped run continues from its step, as a rrotor run did.

## 2. Memory

Installing a bot installs the `bot-memory` template for it: Agentic memory's spec and three kinds (`memory`,
`instructions`, `personality`), its models named `me-<user hex>-bot-<slug>-<key>`, so each bot remembers on its own
and removing a bot deletes only its memory. Its `seed` is remembered at install. Before each `think`, the runner puts
the bot's recall for the step (and, with `reads_glyphh`, the person's rules and personality) before Claude, through the
same `POST /v1/me/glyphh/context`, now taking `bot` (§4).

## 3. Running it

`glyphh bot run <slug>` (the `glyphh` command, SDK) walks the loop: it runs each `run` step itself and hands each
`think` step to the Claude session that called it, as a prompt answered in the same session. The plugin's `bot` skill
is what Claude follows to do that. So a bot runs the same way everywhere Claude Code does:

| Where | Started by | What it gives |
|---|---|---|
| Claude Code on the person's computer | `/bot run <slug>`, or `/loop` | Their own CLIs, files and sign-ins; runs while the computer is on |
| A Claude Code cloud session | The bot's routine, made a scheduled task at install (`create_trigger`, fresh session per run), or a webhook / PR event | Runs with the computer off; cron at most hourly; the cloud environment holds its CLIs and secrets |
| Cowork | Cowork's own scheduled tasks | The same, for people who don't use Claude Code |

A routine run nobody watches ends `done`, `failed` or `needs_approval`; the last two push to the person's phone with
the run's step and why, and `/bot continue <slug>` (or answering the push in that session) carries it on. Every run's
outcome is kept in the bot's memory as `memory` (`when`: the run), so the bot knows what it did last time.

## 4. The server

| Call | Does |
|---|---|
| `GET /v1/me/bots` | `{bots}`: the person's bots, each with its version, routine and last run |
| `PUT /v1/me/bots/{slug}` | Keeps the package (a tar of the folder, at most 1 MB, `bot.json` validated) and installs its memory on first put |
| `GET /v1/me/bots/{slug}` | The package, for `glyphh bot pull` in a fresh session |
| `DELETE /v1/me/bots/{slug}` | Removes it and its memory (`confirm` the slug again) |
| `POST /v1/me/bots/{slug}/runs` | Records a run's outcome (`status`, `step`, `reason`), for the list and the push |
| `POST /v1/me/glyphh/context` | Takes `bot?` and `step?` as well: the bot's recall for the step, then the person's glyphh |

The connector gets `bots`, `bot`, `bot_save` and `bot_remove`, so Cowork and claude.ai can make and keep a bot without a
shell, and the library gains bots Glyphh makes (`category: "bot"`), installed by copying the package into the person's
own. Bots count against the plan's models (each bot's memory is three) and reads, like any template.

## 5. Secrets and safety

- Secrets are names in the package and values in the environment: the computer's `~/.glyphh/bots/<slug>/.env` (mode
  600), or the cloud environment's variables. The server never holds a value.
- `ctx.cli` refuses arguments outside `allow` (`E_CLI_DENIED`) and stops for `approvals`; on the computer the runner
  also writes the bot's CLI patterns into Claude Code's permissions for the run, so Claude's own Bash calls inside a
  `think` step are held to them.
- A bot's `think` steps run with the session's tools, connectors included; `approval` is how a bot that sends, pays or
  deletes asks first. A routine run never approves its own step.

## 6. The tools Glyphh ships

- **The `bot` skill** (plugin): "make me a bot that…" interviews the person for the job, writes `bot.json`, the skills
  and any code, runs it once with them watching, then saves it and sets its routine. The same skill runs and continues
  bots.
- **`glyphh bot`** (SDK 3.8): `new`, `run`, `continue`, `test` (the program with fake CLIs and HTTP, rrotor's Harness
  kept), `pull`, `save`, `list`, `remove`.
- **`/bot`** (plugin): the list with each bot's last run, and run, continue and pause.
- **The platform**: a Bots page listing them, their runs and memory.

## 7. Build order

1. The package format and `glyphh bot run` on the computer, with `launch_watch` ported as the first bot.
2. Bot memory (`bot-memory` template, `context` with `bot`) and the server's `/v1/me/bots`.
3. The `bot` skill and `/bot`; routines as cloud scheduled tasks; the push on `needs_approval`.
4. The connector's bot tools for Cowork and claude.ai, then the library's Glyphh-made bots and the platform page.

## 8. Open

- Whether a bot's memory should be its own (above) or a slice of the person's glyphh.
- Whether `think` steps in a cloud routine run in one session per run (simple, above) or one long-lived session per
  bot woken each time (keeps context, costs more).
