# Programs: a deterministic workflow one bot or several follow

Rulings (2026-11-23): a bot is the Agent SDK loop and its instructions; it "can have a program.py beside its skill",
a deterministic workflow one bot or a swarm follows, part of a template, able to use connections, tools, the file
system and a browser. Programs run on Glyphh cloud, on a rrotor or both; anything that runs on the cloud also runs
on a rrotor. Each program has logs and an audit trail, a bot keeps its identity in it, it can be scheduled with the
bots' own scheduler, and it is edited on a canvas (the Programs tab under Bots) that is the same program as its
`program.py`.

## 1. One source of truth: `program.py`

A program is one Python file. Its steps are the module-level list `FLOW`, a literal (Python's `ast.literal_eval`
reads it; nothing in the file is run to read it). Everything else in the file (its docstring, imports, functions) is
the program's code.

```python
"""PR review digest: the pull requests waiting on my review, the ones for today posted to Slack."""

FLOW = [
    {
        "id": "find",
        "kind": "tool",
        "tool": "github-search-issues-and-pull-requests",
        "input": {"q": "is:pr is:open review-requested:@me"},
        "next": "pick",
        "at": [0, 0],
    },
    {"id": "pick", "kind": "bot", "task": "Which of these need my review today?\n\n{find}", "next": "ok"},
    {
        "id": "ok",
        "kind": "ask",
        "question": "Post the digest?",
        "options": ["yes", "no"],
        "next": {"yes": "post", "no": None},
    },
    {"id": "post", "kind": "tool", "tool": "slack-send-message", "input": {"channel": "@me", "text": "{pick}"}},
]
```

A step is a dict with these keys (no others):

| Key | Steps | What it is |
|---|---|---|
| `id` | all | A lowercase name, unique in the program |
| `kind` | all | `tool`, `bot`, `ask`, `branch` or `code` |
| `title` | all | Its name on the canvas (else made from the step) |
| `bot` | all | The bot that does it, by slug; none: the program's own bot |
| `tool` | tool | A tool key of that bot (a connection's, `fetch`, a built-in) |
| `input` | tool, code | Its input; any string in it may name earlier results (below) |
| `task` | bot | What the bot is told: a run of that bot, its answer the step's result |
| `question`, `options` | ask | What the person is asked; their answer is the result |
| `on` | branch | A value made of earlier results; the result |
| `function` | code | A function of `program.py`, `def name(given)`, run in a sandbox |
| `next` | all | The next step's id; none: the program ends. For `ask` and `branch`, a map from the result to the next step (`else` for any other) |
| `at` | all | `[x, y]` on the canvas |

`{find}` in a string is step `find`'s result (JSON when it is not text); `{find.items}` a key of it; `{input}` what
the run was given. The first step of `FLOW` runs first. A program whose `FLOW` is not a literal list of such steps,
names a step, a tool, a bot or a function that is not there, or has a loop the walk could follow forever without an
`ask` in it, is refused with each problem in plain words (`problems`).

**The canvas and the file are one program.** The canvas reads `flow` (the parsed `FLOW`) and saves `flow`: the
server writes it back into `program.py` as the `FLOW = [...]` literal, in place, and leaves every other byte of the
file as it was. Saving the file's text replaces the file. Either way the program is the file, and reading the file
back gives the canvas exactly what it saved (the round trip is tested both ways).

## 2. A run

The server walks the steps (`ops/programs/walk.py`), on the cloud and for a rrotor alike; only a `code` step's
function runs elsewhere (section 3). Each step's result is kept on the run (`outputs`), so an answer or a restart
carries on from the step it stopped at (`at`), never doing a finished step twice.

| Step | What happens |
|---|---|
| `tool` | The bot's tool, as that bot: its connection, its permission mode and the connection's allow / ask / deny (bot-agent-loop.md, 5). An action that asks stops the run with the approval question; a yes runs that very call once. |
| `bot` | A run of that bot with the task (its own agent, instructions, tools and permissions). A question it asks is the program's question; the program carries on when that run ends. |
| `ask` | The run waits with the question; the person's words (or one of the options) are the result. |
| `branch` | `on` made of earlier results; `next[on]`, else `next.else`. |
| `code` | The function, given its `input`, in a sandbox: its return value (JSON) is the result. |

Statuses are the bots' (`queued`, `running`, `dispatched`, `needs_input`, `done`, `failed`); a run waiting on the
person is in the org's approvals queue. A program has one live run at a time. Cancel stops it where it is.

## 3. Where it runs

`programs.runs_on`: Glyphh cloud (none) or one of the org's rrotors. A template says where it can run with the
bots' `runs_on` pills.

- **Glyphh cloud** runs `tool`, `bot`, `ask` and `branch` steps. These are the "fewer tools": the bots' own,
  through the server.
- **A rrotor** runs the same steps the same way, and runs each `code` step in the rrotor's own programs runtime:
  `glyphh_bot`'s function `code` (rrotor 0.10.0) runs `program.py`'s function in the run's sandbox (bubblewrap and
  Landlock, rrotor's), with the folders the program's bot was given there. This is how the rrotor programs runtime
  and Glyphh programs meet: a Glyphh program is not a second runtime on the rrotor; its code is a call of the
  rrotor's own.
- **A `code` step on Glyphh cloud** does not run. A program with `code` steps is `can_run_on: ["rrotor"]`; while it
  is set to Glyphh cloud its `problems` say, per step, "code does not run on Glyphh cloud yet: choose one of your
  rrotors for this program, and its code runs there", and running it is refused with those words (422). Nothing is
  improvised in its place: how cloud code could run safely is the open ruling of section 7.
- On a rrotor the step is refused in plain words too when the rrotor is older than 0.10.0 (update it) or is not
  linked right now.

## 4. Logs and the audit trail

Every run writes `program_events`, append only, in order: `started` (who or what started it: a person, the
schedule, the connector), each step's `step` (its id, kind, title, the bot that did it, whether it worked, a short
plain detail), `asked`, `answered` (by whom), `done`, `failed`, `cancelled`. The bot that did a step is named on its
event (`bot_id`): a `tool` step is that bot's call, made as that bot; a `bot` step is that bot's own run
(`child_run`). Nothing a tool answered is kept on an event; the result is on the run.

`GET /v1/program-runs/{id}/events?after=<n>` reads them in order (the canvas follows a run with it), and the
connector's `run_program` streams them (section 6).

## 5. Schedules

A program has a schedule like a bot (`schedule`, `next_run_at`, ops/bots/schedule.py's plain choices: off, every
hour, every day at, every weekday at, every week on). The bots' scheduler (`ops/bots/due.py`) starts due programs
as it starts due bots, on the cloud and for a rrotor alike, each as a run with `trigger: schedule` (logged and
audited as any run). A run still live when the next is due is skipped, saying so.

## 6. The API and the connector

| Route | What |
|---|---|
| `GET /v1/programs?q=` | The org's programs |
| `POST /v1/programs` | Make one: `name`, `summary`, `source` or `flow`, `bot`, `runs_on`, `schedule` |
| `GET /v1/programs/{slug}` | `{slug, name, summary, bot, source, flow, functions, problems, runs_on, can_run_on, schedule, schedule_summary, next_run_at, last_run, template, created_at, updated_at}` |
| `PATCH /v1/programs/{slug}` | Any of those; `flow` rewrites `FLOW` in place, `source` replaces the file (not both) |
| `DELETE /v1/programs/{slug}` | Gone, with its runs |
| `POST /v1/programs/{slug}/runs` | Run it: `{input}`; 202 with the run |
| `GET /v1/programs/{slug}/runs` | Its runs, newest first |
| `GET /v1/program-runs/{id}` | `{id, program, status, input, at, outputs, question, error, trigger, created_at, started_at, finished_at}` |
| `GET /v1/program-runs/{id}/events?after=` | Its events from `after` on: `{events: [{n, at, kind, step, title, bot, ok, detail, by}]}` |
| `POST /v1/program-runs/{id}/answer` | `{answer}` |
| `POST /v1/program-runs/{id}/cancel` | |
| `GET /v1/tools/search?q=&bot=` | `search_tool`: tools of the org's connected apps and the built-ins, `{tools: [{key, title, app, description, read_only, connection_id, added}]}` (`connection_id` null for a built-in; `added` whether the bot named has it) |
| `POST /v1/bots/{slug}/tools` | Add a found tool to a bot: `{connection_id, tool}` (no `connection_id`: a built-in); 204 |

A program's `bot` is its own bot's slug (or null); `last_run` is `{id, status, created_at}` (or null); a run's
`outputs` leave out the walk's own bookkeeping.

Connector tools: `programs`, `program_get`, `program_save` (make or change: `source` or `flow`), `program_delete`,
`program_schedule`, `run_program`, `program_runs`, `program_run_get` (with its audit trail), `program_run_answer`,
`program_run_cancel`, and `search_tool` (find tools to use, and with `add_to` give the one found to a bot). Bots get
tools the same way: `search_tool` then `add_to`.

`run_program` starts a run and follows it for up to two minutes, then answers the run as it stands: done with its
results, waiting with its question, or still going with how to follow it; every line of the trail so far is in its
answer. It **streams**: when the client's request accepts `text/event-stream` and carries a `progressToken`
(`params._meta`), the response is an SSE stream (Streamable HTTP), each line of the trail sent as a
`notifications/progress` message the moment it is written, the call's own answer last (`api/mcp_stream.py`). A
client that asks for neither gets the one JSON answer.

## 7. Open

- **Code on Glyphh cloud: a ruling is needed.** Today it is refused (section 3). The ways it could run, none built:
  1. **A Glyphh-run rrotor per org, on demand** (recommended). The code step goes down the same link to a rrotor
     Glyphh starts for the org (a Fly machine, per second, stopped when idle): rrotor's own sandbox (bubblewrap and
     Landlock), egress proxy and limits, already built and tested, and exactly one code path for cloud and rrotor
     ("anything that runs on cloud runs on a rrotor" holds by construction). Cost: it turns Glyphh-run hosting back
     on for this one use (flagged off 2026-10-19), a cold start of some seconds, and per-second machine cost to
     meter.
  2. **CPython built for WASI under `wasmtime`, in the server's process tree.** No kernel features, runs in the
     server's container and in CI, memory and time capped by the runtime, no network and no files unless given.
     Cost: only pure-Python code (no C extensions, no sockets, so no `requests`), a second runtime to keep beside
     rrotor's, and untrusted code beside the server's secrets with one wall between them.
  3. **bubblewrap in the server's container**, as on a rrotor. Needs user namespaces, which the server's Fly
     container and CI's Docker do not allow by default; a privileged container to host other orgs' code is the
     wrong trade.
  4. **A vendor's sandbox** (E2B, Modal, Fly Machines called per step). Fast to ship, good isolation; code and its
     inputs leave Glyphh for a third party, and a per-run price.
  5. **Never**: code stays a rrotor's, and the pills say so. Nothing to build or secure.
- A browser for programs: a rrotor's, when rrotor has one.
