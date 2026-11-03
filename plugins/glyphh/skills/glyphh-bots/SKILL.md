---
name: glyphh-bots
description: Make, run and train Glyphh bots with the `glyphh bot` command (pip install glyphh, SDK 3.8) - programs that run a Claude agent behind gates that learn from the person's answers in Ada. Use when the person wants a recurring job done by a bot ("make me a bot that...", "every morning, check..."), to run a bot, answer a bot's gate or approval, say a bot got a run wrong, review how far a bot is trusted or whether to keep it, install a bot's routine, or write or check a bot's package (bot.json, agent.md, program.py, skills).
---

# Glyphh bots

A bot is a program that controls a Claude agent, kept in `~/.glyphh/bots/<slug>/`: `bot.json` (a loop of steps, its
gates, what it touches), `agent.md` (its Claude agent), `program.py` (its code steps) and `skills/*/SKILL.md`. The
runner walks the loop: `run` steps are code, `gate` steps are Ada models of the bot's own that learn from the
person's answers, `agent` steps call Claude lean (`claude -p`, no tools, no MCP servers), with the bot's memory and
the person's glyphh before it. The orchestrator makes bots from a job, decides how far each is trusted and whether
it is kept, and learns from every run. Everything goes through Bash with `glyphh bot ...`; every answer is JSON on
stdout. Read it and tell the person what it means in plain words; do not paste it whole.

## The rules that never bend

- **Hard gates are program code; learned gates are Ada.** A limit that must hold (a budget, an allowed list, "never
  more than N", "stop when nothing is new") is code in `program.py`: a run step answering `{"_end": "why"}` ends the
  run. A judgment the person makes (is this worth sending, which way, is it safe) is a gate, an Ada model that learns
  from their calls. Never put a hard limit in a gate, and never let a gate's guess stand in for code.
- **No bot acts outward without the person's yes until trust allows.** Any step that sends, posts, pays or deletes
  has an `approval`; a bot whose `touches` is `sends`, `pays` or `deletes` is refused without one. Until the
  orchestrator's trust for the bot is `autonomous` (only from `review` with the person's agreement, or their
  `verdict`), every approval waits for the person. Never answer an approval or a gate yourself: ask the person, in
  one line, and pass on exactly what they said.
- **Gates learn only from the person and the world.** Record what the person answered or what really happened, never
  your own guess. A run a gate got wrong is corrected with `wrong`, on the person's word.

## Setup

- `glyphh --version` (3.8 or later); missing or older: `pipx install glyphh` (or `pipx upgrade glyphh`).
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
3. On `make`, a builder writes the package from the format and what earlier bots taught the orchestrator; it is
   checked, installed and trusted `ask_all`. A package that is not right (or touches more than asked) is set aside in
   `~/.glyphh/bots/.rejected/` with its problems: say them, and offer to fix the package by hand (below).

You may also write a package yourself (the format is `BUILDING.md` in the SDK, `glyphh/bots/BUILDING.md`; examples in
the repo's `examples/bots/`), check it with `glyphh bot check <folder>` (every problem at once), then
`glyphh bot install <folder>`. One to three gates; each gate's case is computed by code from the run's data.

## Run it, and answer it

- `glyphh bot run <slug>`. From Claude there is no terminal, so a gate under its confidence or an approval stops the
  run: `status` `needs_input`, with `question` and `options`. Ask the person that question in one line with the
  options, then `glyphh bot continue <slug> <their answer>`. Repeat until `done` (its `reason` says why it ended
  early, when it did) or `failed` (say the `reason`).
- `glyphh bot wrong <slug> <run> <outcome> [--gate G]`: the person says a gate decided that run wrong; their outcome
  is kept as a precedent and counts against the bot's record.
- `glyphh bot status <slug>`: each gate's precedents, the memory, trust and keep, and the last runs.

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
it on. Install a routine only when the person asks for one.
