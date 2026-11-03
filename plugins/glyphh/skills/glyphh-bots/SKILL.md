---
name: glyphh-bots
description: Make, run and train Glyphh bots with the `glyphh bot` command (pip install glyphh, SDK 3.9) - programs that run a Claude agent behind hard gates in code and learned gates in Ada that learn from the person's answers. Use when the person wants a recurring job done by a bot ("make me a bot that...", "every morning, check..."), to run a bot, answer a bot's questions or approval (one or a batch of items), say a bot got a run or an item wrong, record what really happened, see what a bot's gates learned (gates, report), pause or resume a bot, review how far a bot is trusted or whether to keep it, install a bot's routine, or write or check a bot's package (bot.json, agent.md, program.py, skills).
---

# Glyphh bots

A bot is a program that controls a Claude agent, kept in `~/.glyphh/bots/<slug>/`: `bot.json` (a loop of steps, its
gates, its limits, what it touches), `agent.md` (its Claude agent), `program.py` (its code steps) and
`skills/*/SKILL.md`. The runner walks the loop: `run` steps are code, `gate` steps are Ada models of the bot's own
that learn from the person's answers, `ladder` steps climb ordered options, `agent` steps call Claude lean
(`claude -p`, no tools, no MCP servers), with the bot's memory and the person's glyphh before it. The orchestrator
makes bots from a job, decides how far each is trusted and whether it is kept, and learns from every run. Everything
goes through Bash with `glyphh bot ...`; every answer is JSON on stdout. Read it and tell the person what it means in
plain words; do not paste it whole.

## The rules that never bend

- **Hard gates are code; learned gates are Ada.** A limit that must hold (money, a rate, quiet hours, an allowed
  list, "never more than N", "stop when nothing is new") is code: bot.json's `limits`, a step's `requires`, or a run
  step answering `{"_end": "why"}`. A judgment the person makes (is this worth reading, which way, is it safe) is a
  learned gate. Never put a hard limit in a gate, and never let a gate's guess stand in for code.
- **No bot acts outward without the person's yes until trust allows.** Any step that sends, posts, pays or deletes
  has an `approval`. Trust (`ask_all`, `ask_outward`, `autonomous`) comes only from `review` with the person's
  agreement, or their `verdict`; even `autonomous` never pays or deletes alone unless its `approval_gate` is sure.
- **Gates learn only from the person and the world.** Record what the person answered or what really happened,
  never your own guess. **Never answer a gate, a batch or an approval yourself**: ask the person and pass on exactly
  what they said. A wrong call is corrected with `wrong`, a real outcome recorded with `outcome`, on their word.

## Which gate for which job

When you write or change a bot (or brief the person on what `new` made), use the right gate:

| The job has | Gate | In bot.json |
|---|---|---|
| A list to judge item by item (stories, emails, issues, leads) | per-item gate | `gate` step with `"each": "$fetch.items"`, `label`, `key`; the gate's `max_questions` and `default` |
| One call on the whole run | gate | `gate` step, `on` mapping each outcome |
| Options of rising cost (models, strategies) | ladder | `ladder` step: the gate's outcomes cheapest first, `try`, `check` |
| An outward action | approval, learned | `approval` + `approval_gate` (a yes/no gate) on the step, its `touches` |
| An outcome that arrives later | world-answered gate | `"world": true`; `glyphh bot outcome` when it is known |
| A Claude answer code reads | agent output gate | `schema` (JSON Schema) and `check` on the agent step |
| Money, rate, time, size | hard limits, always | `limits`: `usd_per_run`, `usd_per_day`, `runs_per_day`, `quiet_hours`, `max_items`, `seconds`, `steps` |

A gate's policy sits beside its spec: `ask_below`, `min_precedents` (answers before Ada decides alone), `audit` (a
share of sure calls still asked), `shadow` (always asked, agreement measured), `max_questions` a run, `default`.
The full format is `BUILDING.md` in the SDK (`glyphh/bots/BUILDING.md`), which the builder follows.

## Setup

- `glyphh --version` (3.9 or later); missing or older: `pipx install glyphh` (or `pipx upgrade glyphh`).
- The key: `glyphh whoami`. `{"logged_in": false}`: ask the person to run `! glyphh login` themselves (the glyphh-cli
  skill says how); `GLYPHH_API_KEY` or `GLYPHH_API_KEY=` in `~/.glyphh/bots/.env` also work. Never ask for the key in
  the chat.
- Bots call Claude Code's `claude` on the PATH.

## Make a bot from a job

1. Agree the job in a sentence, how often it comes up (`--recurs`, times a week) and the most outward thing it may do
   (`--touches read_only|drafts|sends|pays|deletes`). Say plainly that a bot that sends, pays or deletes asks before
   each one until it is trusted.
2. `glyphh bot new "<job>" --recurs N --touches T`. The orchestrator's make_bot gate decides when Ada is sure;
   otherwise the answer is `needs_input` with its question: ask the person, then run it again with
   `--answer make|not_yet|no` (their word).
3. On `make`, a builder writes the package from the format, two example bots and what earlier bots taught the
   orchestrator; it is checked, installed and trusted `ask_all`. A package that is not right (or touches more than
   asked) is set aside in `~/.glyphh/bots/.rejected/` with its problems: say them, and offer to fix it by hand.

You may also write a package yourself (examples in the repo's `examples/bots/`; `hn_reader` is the per-item one),
check it with `glyphh bot check <folder>` (every problem at once, malformed limits and gates included), then
`glyphh bot install <folder>`.

## Run it, and answer it

- `glyphh bot run <slug>`. From Claude there is no terminal, so a question stops the run: `status` `needs_input`.
  - One question (`question`, `options`): ask the person in one line with the options, then
    `glyphh bot continue <slug> <their answer>`.
  - A batch (`batch`: items by number, each with Ada's guess and P): show the person the list, numbered, in a few
    lines, and ask for their call on each; then `glyphh bot continue <slug> 1=read 2=skip 3=read` (`rest=skip` for
    the ones they leave; a JSON map works too). Every answer is kept as a precedent, so the batch shrinks run by run.
  - Repeat until `done` (`reason` says why it ended early, when it did), `failed` (say the `reason`) or `skipped` (a
    limit kept it from starting: quiet hours, runs a day).
- `glyphh bot wrong <slug> <run|last> <outcome> [--gate G] [--item N]`: the person says a gate decided that run (or
  item N of it) wrong; their outcome is kept as a precedent and counts against the bot's record.
- `glyphh bot outcome <slug> <run|last> <gate> [item] <outcome>`: what really happened to a case (a world-answered
  gate): kept as a precedent; where Ada had decided otherwise it counts as an overrule.
- `glyphh bot pause <slug> [--why ...]` / `glyphh bot resume <slug>`: the kill switch. A paused bot refuses to run,
  its routine included. Pause at once when the person asks a bot to stop.

## See what it learned

- `glyphh bot gates <slug> [--runs N]`: per gate, its precedents, its policy, decisions by Ada vs the person (and
  defaults), the ask rate over the last N runs and run by run, agreement on audits and shadow calls, overrules
  (corrections, audits, the world), ladders' escalations. Say it in a sentence or two: "it asked you 3 of 30 this
  run, down from 10; you agreed with 9 of 10 audits".
- `glyphh bot report <slug>`: writes `report.html` in the bot's folder and prints its path: the last run's items with
  each decision, who made it and P; asked you N, decided M by itself, you overruled K; the ask rate falling run by
  run; the gates' records; links to what the bot made in `out/`. Offer to open it (`open <path>` on a Mac).
- `glyphh bot status <slug>`: gates, memory, trust and keep, paused, the last runs.

## The demo: a bot that learns what you read

1. `glyphh bot new "each morning, pick the Hacker News front-page stories worth my time and write me a short
   digest" --recurs 7 --touches read_only` (answer make_bot with the person's word). The builder makes a per-item
   gate (read or skip) from the stories' titles, sites, points, comments and age; `examples/bots/hn_reader` is the
   reference (`glyphh bot install examples/bots/hn_reader` installs it as is).
2. `glyphh bot run <slug>`: the first runs stop with a batch of up to 10 stories; show them, take the person's read
   or skip on each, `glyphh bot continue <slug> 1=read 2=skip ...`. The digest is written to `out/digest.md`.
3. Run it again over the days (or `glyphh bot routine <slug>`): Ada starts deciding the stories it is sure of; the
   batch shrinks, audits keep checking it.
4. `glyphh bot report <slug>` and open it: the ask rate falling run by run, and who decided each story.

## Trust and keep

- `glyphh bot review`: trust_bot (`autonomous`, `ask_outward`, `ask_all`) and keep_bot (`keep`, `fix`, `retire`)
  for every bot, from its record (runs, how often it asked, how often it was overruled, how often it finished). Ada's
  call stands when it is sure; the rest come back as questions. Show the person each bot's record and ask; then
  `glyphh bot review --answer <bot>.trust_bot=<theirs> <bot>.keep_bot=<theirs>`.
- `glyphh bot verdict <slug> trust|keep <outcome>`: the person's own call, kept and applied at once. A retired bot
  does not run.
- `glyphh bot status`: the orchestrator's gates and memory, and every bot with its trust, keep and record.

## A routine

`glyphh bot routine <slug>` runs `glyphh bot run <slug> --routine` on the bot's `routine.cron`: a launchd job on a
Mac (`ai.glyphh.bot.<slug>`; `--remove` takes it away), else the cron line for the person to add. In a routine
nobody is watching: a question stops the run, the Mac shows a notification, and `glyphh bot continue <slug>` carries
it on; inside `quiet_hours` the run is skipped. Install a routine only when the person asks for one.
