# Bots

Example bots for `glyphh bot` (`pip install glyphh`, SDK 3.8). A bot is a folder: `bot.json` (its loop of steps,
its gates, what it touches), `agent.md` (its Claude agent), `program.py` (its code steps) and `skills/*/SKILL.md`.
Its program controls its agent: the runner walks the loop, runs the code steps itself, asks Ada at the gates (Ada
models that learn from your answers, so they ask less run after run), and calls Claude (`claude -p`, lean: no tools,
no MCP servers, no settings) only for the steps that need judgment. The format is
[`BUILDING.md`](../../sdk/python/src/glyphh/bots/BUILDING.md), the same file the orchestrator's builder follows.

| Bot | What it does | Shows |
|---|---|---|
| [`launch_watch`](launch_watch) | Each morning: a project's GitHub stars, new issues and PRs, PyPI and npm downloads, kept day by day; a gate learns which days are worth a summary, and the agent writes it into `out/` | A routine, a learned gate that ends the run, an agent step with a skill and memory, declared hosts |
| [`lab`](lab) | The orchestrator as a bot: it has Claude propose experiments on how Claude does coding work best, keeps the ones its hard rules allow and its `promising` gate rates best, makes each an experiment bot beside it, runs them on the tasks in `tasks/` judged by hidden tests, and writes the playbook | A bot that makes and runs bots (`ctx.orchestrator`), hard gates in code (a $20 budget in `trials.py`, allowed arms), a gate recorded from what the world answered |
| [`coder`](coder) | Does the lab's held-out tasks (`lab/heldout/`), choosing for each the cheapest model its `route` gate learned gets it done, up the ladder on a failure, learning from every task | Knowledge handed from one bot to another; a gate the program asks and records itself (`ctx.gate`) |

```bash
pipx install glyphh && glyphh login          # an Ada Cloud API key (or GLYPHH_API_KEY, or ~/.glyphh/bots/.env)
glyphh bot install examples/bots/launch_watch
glyphh bot run launch_watch                  # the gate asks you until it has learned your days
glyphh bot routine launch_watch              # each morning at 8:47 (launchd on a Mac; elsewhere the cron line)
glyphh bot new "each morning, sum up the new issues in my repo" --touches read_only
```

`lab` and `coder` run real Claude Code trials, each capped at $0.60, the lab's whole spend at $20 (`lab/trials.py`):
install `lab` before `coder`, which reads the lab's ledger. Bots are installed into `~/.glyphh/bots/<slug>/`
(`GLYPHH_BOTS` moves it); each keeps its runs in `runs.sqlite` there.
