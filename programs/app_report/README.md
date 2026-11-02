# app_report

A report published to the organisation that runs as the app, with the organisation's key.

- **What it is:** an app of `"type": "dashboard"` whose one function runs **as the app** (`"run_as": "app"` in the
  manifest's `app` block), not as the person viewing it: every viewer gets the same page, and no one signs in.
- **What it shows:** a repository's open issues, newest first, with a link each.
- **Where the data comes from:** the page loads rrotor's own script (`<script src="/apps/_/rrotor.js">`), awaits
  `rrotor.ready()` (it resolves at once: an app that runs as the app shows no sign-in card) and calls
  `rrotor.call("issues")`. The function runs the `gh` CLI on the rrotor (the manifest's `clis`) and hands it the
  organisation's token from the vault for that one command: `ctx.cli("gh", [...], env={"GH_TOKEN":
  ctx.secrets["GH_TOKEN"]})`. The token never reaches the page or a viewer, and is masked in the run's log.
- **Who may open it:** everyone in the organisation (`"roles": []`).

| Function | Inputs | Does |
|---|---|---|
| `issues` | `{"limit": 50}` (1 to 200) | Lists the open issues through `gh issue list --json` |

## What the admin does once

The app declares the secret `GH_TOKEN`; the admin sets it on the rrotor with `secret_set {program: "open_issues",
name: "GH_TOKEN", value: ...}`, before the review (the catalogue's card says "GH_TOKEN not set on the rrotor" until
then, and a run without it fails naming it). That is all: the page is the same for every viewer, and nothing is
signed in. Had `gh` no token, an admin would sign it in once instead, to its shared HOME, with `cli_login {cli:
"gh", shared: true}`.

Compare `app_dashboard`, which runs as the viewer: each person sees what their own account allows.

## Make it yours

1. In `program.py`, set `REPO` to your repository; `gh` needs a token that can read it.
2. In `glyphh.json`, set `app.roles` to the groups that may open it, if not everyone.
3. Ask Claude to *"publish programs/app_report to my org"*; set `GH_TOKEN`; a reviewer approves it; the Open link is
   `https://<host>/apps/open_issues/`.

## The tests

`tests/test_program.py` runs the function through `rrotor.testing` with `gh` answered by `FakeCli` and the secret
given to the harness; it also checks that the manifest runs as the app and that the page goes through `rrotor.js`.
They need rrotor 0.4.0's SDK (`ctx.cli`'s `env`).
