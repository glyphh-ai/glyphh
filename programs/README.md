# Programs

Example programs for rrotor, your runtime. Each folder is one program: a `glyphh.json` manifest, `program.py` and its
tests. Copy one, change it, and deploy it to your rrotor. More are on the way.

| Program | What it does | Uses |
|---|---|---|
| [`launch_watch`](launch_watch) | Each morning, takes a project's GitHub stars, forks, new issues and PRs, and its PyPI and npm downloads. Keeps them day by day in its database and emails you the summary through Claude's Gmail connector | A schedule, an approval, SQLite, the built-in `claude` CLI |

## Deploy one

With the Glyphh plugin in Claude Code, ask Claude to *"deploy programs/launch_watch to my rrotor"*. A program deploys
from a git commit, so Claude copies the folder into its own repo, commits it and deploys that commit. Then ask
Claude to call it, answer its approvals, or pause its schedule.

Some programs use a CLI that comes with rrotor, such as `claude`. Sign that CLI in once with `cli_login`: rrotor
gives you a link to open on your phone and takes the code back.

## The tests

Each program's `tests/` use `rrotor.testing`, which comes with rrotor. A program runs there exactly as it does on
rrotor (the same calls, waits and Results), with no network: HTTP and CLIs answer what the test tells them to.

## Write your own

Ask Claude to *"write a program for rrotor that …"*. The plugin's `rrotor-programs` skill knows the manifest
(functions, inputs, approvals, hosts, secrets, schedules, databases, CLIs) and the `ctx` a function gets.
