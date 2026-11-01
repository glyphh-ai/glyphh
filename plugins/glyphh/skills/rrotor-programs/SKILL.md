---
name: rrotor-programs
description: Write a program or a CLI manifest for rrotor, the local Glyphh runtime: glyphh.json and program.py (functions, inputs, approvals, secrets, schedules, a SQLite database, declared hosts), or a "kind": "cli" manifest that installs a pinned command-line tool. Use when the person wants something to run on their rrotor (a job, an integration, a scheduled task, a sandboxed CLI such as gh), before deploying it with the rrotor skill. Not for Ada models (the ada skill).
---

# Writing a program or a CLI for rrotor

A program is a git repo (a folder with its own `git init` is enough); a version is a commit. Agree with the person
what it does, which hosts it may reach, which steps need their approval and which secrets it reads; write it; test
it; commit; deploy (the rrotor skill: `rrotor.sh deploy <folder>`, or `program_deploy` with a GitHub repo and its
commit). A deploy is refused `E_MANIFEST` with where and why: fix that and deploy again.

| File | What |
|---|---|
| `glyphh.json` | The manifest |
| `program.py` | The functions (`load` and `end` are optional hooks, never functions) |
| `requirements.lock` | Optional: Python dependencies pinned with hashes (`uv pip compile --generate-hashes`), binary wheels only, installed at deploy |
| `files/` | Optional: seed files, copied into the program's folder on its first deploy |
| `tests/` | Its own tests, with `rrotor.testing` (no sandbox needed) |

## The manifest

```json
{
  "name": "daily_sales",
  "description": "A day's sales, added up, converted to euros, and written to its ledger once approved",
  "python": "3.13",
  "functions": {
    "start": {
      "description": "Read a day's export, add it up, write the total to the ledger (asks approval first)",
      "inputs": { "type": "object", "properties": { "day": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" } }, "additionalProperties": false },
      "approvals": ["write"],
      "writes": true
    },
    "summary": { "description": "The ledger", "inputs": { "type": "object", "additionalProperties": false }, "writes": false }
  },
  "hosts": ["api.frankfurter.dev"],
  "secrets": [],
  "databases": [],
  "limits": { "seconds": 60, "memory_mb": 256 },
  "schedules": [{ "function": "start", "cron": "15 6 * * *", "tz": "UTC", "name": "each_morning" }]
}
```

- `name`: `^[a-z][a-z0-9_]{0,62}$`, the program's name on the runtime. `python` is `3.13`. Unknown keys are refused.
- `functions`: at least one, each with `inputs` (a JSON Schema the call is checked against), `approvals` (every step
  that may ask the person; a step not listed fails the run) and `writes`.
- `hosts`: the only hosts a run may reach, HTTPS on 443 (`*.example.com` allowed). Everything else is blocked.
- `secrets`: names (`^[A-Z][A-Z0-9_]{0,63}$`) it reads; the person sets the values on the runtime (`secret_set`),
  never in the repo. A run with one unset fails `E_SECRET_MISSING`, naming it.
- `databases: ["sqlite"]`: a SQLite file in its data folder, `ctx.db`. `"data": true`: a persistent folder,
  `ctx.data`. Either way every call runs on a cluster's head.
- `schedules`: `{function, cron, tz?, input?, name?}`; five-field cron or `@daily` and the like; `input` must fit the
  function's schema. The runtime fires them itself; an approval waits like any other run's.
- `limits`: `seconds` 1 to 3600 (300), `memory_mb` 64 to 8192 (512).

## program.py

```python
from rrotor import Ctx, Result


def start(ctx: Ctx, inputs: dict) -> Result:
    day = inputs.get("day") or ctx.yesterday()
    export = ctx.files / "sales" / f"{day}.csv"
    if not export.is_file():
        return Result.failed("read", f"There is no sales export for {day}.")
    total = add_up(export)
    rate = ctx.checkpoint(f"rate:{day}", lambda: ctx.http.get(RATES, params={"from": "USD", "to": "EUR"}).json()["rates"]["EUR"])
    if not ctx.ask_approval("write", f"Write {day}'s total, ${total}, to the ledger?"):
        return Result.done({"day": day, "total_usd": str(total), "written": False})
    with ctx.db:                                         # "databases": ["sqlite"]; committed at the block's end
        ctx.db.execute("create table if not exists ledger (day text primary key, total_usd text)")
        ctx.db.execute("insert or replace into ledger values (?, ?)", (day, str(total)))
    ctx.log("written", day=day)
    return Result.done({"day": day, "total_usd": str(total), "written": True})
```

- A function is `def name(ctx, inputs) -> Result`: `Result.done(data)`, `Result.failed(step, reason)`,
  `Result.needs_input(prompt, schema=None, options=None)`, `Result.needs_approval(step, prompt)`. A crash is a
  `failed` Result, never an exception to the caller.
- **Re-entrant:** a continue calls the same function again with the same inputs. Wrap anything done once (a fetch,
  a charge) in `ctx.checkpoint(key, fn)`; `ctx.ask_approval(step, prompt)` returns True or False once the person
  answered and waits until then; `ctx.needs_input(...)` likewise.
- `ctx.http` (HTTPS to the declared hosts), `ctx.files` (its folder), `ctx.data`, `ctx.db`, `ctx.secrets["NAME"]`,
  `ctx.log(message, **detail)`, `ctx.today()`, `ctx.yesterday()`, `ctx.caller` (`claude` or `schedule`),
  `ctx.clearance`. `rrotor` is in the sandbox already: never install it or list it in `requirements.lock`.
- Its tests use `rrotor.testing.Harness` (inputs, answers, a folder, an `http` that answers what the test says,
  `secrets={...}`, `database=<a file>`). rrotor's `examples/daily_sales` is the model to follow.

## A CLI

A CLI is a kind of program: no `program.py`, no functions or schedules, a `cli` block instead.

```json
{
  "name": "github",
  "kind": "cli",
  "description": "GitHub's gh",
  "cli": {
    "install": { "url": "https://github.com/cli/cli/releases/download/v2.62.0/gh_2.62.0_linux_amd64.tar.gz", "sha256": "<its 64-hex checksum>" },
    "command": "gh",
    "allow": ["pr *", "issue *", "repo view *", "api repos/*"],
    "approvals": ["pr merge *", "pr close *", "issue close *"],
    "env": { "GH_TOKEN": "secret:GH_TOKEN", "GH_PROMPT_DISABLED": "1" },
    "home": true
  },
  "hosts": ["api.github.com", "github.com"],
  "secrets": ["GH_TOKEN"],
  "limits": { "seconds": 120, "memory_mb": 512 }
}
```

- `install`: one source, pinned, with the `sha256` of what is downloaded: `url` (an https release asset: a tarball,
  a zip or a binary; pick the Linux build for the runtime's architecture), `npm` (`name@1.2.3`, no install scripts,
  dependencies bundled), `pypi` (`name==1.2.3`: a `py3-none-any` wheel, its dependencies in `requirements.lock`), or
  `image` (a binary already in the image, no checksum needed). Get the real checksum from the release's published
  checksums or PyPI's files page; never invent one.
- `command`: what runs (a path or a name in the install, npm's bin, PyPI's console script). There is no shell.
- `allow`: globs over the joined arguments; none means any. `approvals`: arguments that wait for the person.
- `env`: `secret:NAME` takes a declared secret from the vault; `PATH`, `HOME`, `TMPDIR`, proxies and `LD_*` are
  rrotor's. `home: true`: a private HOME kept across calls (a login the tool keeps).
- The glyphh command as a CLI (rrotor's `examples/cli_glyphh`): `"install": {"pypi": "glyphh==<version>", "sha256":
  "<the wheel's>"}`, `"command": "glyphh"`, `"env": {"GLYPHH_API_KEY": "secret:GLYPHH_API_KEY"}`, `"hosts":
  ["ada.glyphh.ai", "platform.glyphh.ai"]`.

Run it with `cli_run {cli, args}`: each call is a run with its exit code, stdout and stderr.
