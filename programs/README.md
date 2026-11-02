# Programs

Example programs for rrotor, your runtime. Each folder is one program: a `glyphh.json` manifest, `program.py` and its
tests. Copy one, change it, and deploy it to your rrotor. More are on the way.

| Program | What it does | Uses |
|---|---|---|
| [`launch_watch`](launch_watch) | Each morning, takes a project's GitHub stars, forks, new issues and PRs, and its PyPI and npm downloads. Keeps them day by day in its database and emails you the summary through Claude's Gmail connector | A schedule, an approval, SQLite, the built-in `claude` CLI |
| [`app_static`](app_static) | A page published to the organisation (`"kind": "app"`): one `index.html`, served at `/apps/release_notes/` to everyone signed in, once a reviewer approves it | An app with nothing behind it |
| [`app_dashboard`](app_dashboard) | A dashboard (`"type": "dashboard"`) of failed GitHub Actions runs by workflow, for the `sre` group: the page calls its own function, run as the person viewing it | An app with a function, roles, a declared host |
| [`app_react`](app_react) | A React page: one `index.tsx` with a recharts bar chart and Tailwind classes, served by rrotor's React shell with no build | An app of one `.tsx` file |
| [`app_diagram`](app_diagram) | A diagram: one `index.mmd` (a Mermaid sequence diagram of the browser sign-in), rendered by rrotor's diagram shell; the type `diagram` is inferred from the entry | An app of one `.mmd` file |

An **app** is what Claude made (a Claude Code artifact, a React page, a document, a diagram, a deck, a design, a
dashboard) published to the organisation's own rrotor and reviewed before anyone opens it; the plugin's `publish`
skill does it from the session (*"publish this to my org"*). Its manifest is a program's with `"kind": "app"` and an
`app` block (`entry`, `type`, `title`, `roles`, `functions`); the type is one of `page`, `dashboard`, `doc`,
`diagram`, `deck`, `design`, and follows the entry's extension when absent (`dashboard` and `deck` are always said).

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
