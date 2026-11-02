# app_dashboard

A dashboard published to the organisation, with one function behind it.

- **What it is:** an app of `"type": "dashboard"` (the manifest's `app.type`; a dashboard is always said, never
  inferred from the entry): a page whose numbers come from the app's own functions, one per chart.
- **What it shows:** failed GitHub Actions runs since a date, counted by workflow, with a bar each.
- **Where the data comes from:** the page's own function, `failures`, which the page calls through rrotor's own
  script (`<script src="/apps/_/rrotor.js">`, then `await rrotor.ready()` and `rrotor.call("failures", {since})`)
  each time it loads. The rrotor runs it as the person viewing the page (`"run_as": "viewer"`, said in the
  manifest though it is the default), reaching only `api.github.com` (the manifest's `hosts`). No claude.ai
  connector is in the path: a Claude Code artifact that pulled this through the GitHub connector is rewritten this
  way when it is published (the plugin's `publish` skill).
- **Why the viewer:** this app declares a host, not a CLI, so no one signs in; an app whose function runs a CLI
  (`clis: ["gh"]`) as the viewer has each viewer sign it in once, from the page's sign-in card (`rrotor.ready()`
  shows it). For a page that is the same for everyone, with the organisation's key, see `app_report`.
- **Who may open it:** the `sre` group and admins (`app.roles`). Roles are the organisation's single sign-on
  groups, or `admin` and `member`.

| Function | Inputs | Does |
|---|---|---|
| `failures` | `{"since": "2026-10-25"}` (default: a week ago) | Counts the failed runs by workflow |

## Make it yours

1. In `program.py`, set `REPO` to your repository. A private one needs a token: declare a secret in `glyphh.json`
   (`"secrets": ["GH_TOKEN"]`), read it with `ctx.secrets["GH_TOKEN"]` in the request's headers, and set it on the
   rrotor with `secret_set`.
2. In `glyphh.json`, set `app.roles` to the groups that may open it.
3. Ask Claude to *"publish programs/app_dashboard to my org"*; a reviewer approves it; the Open link is
   `https://<host>/apps/deploy_failures/`.

## The tests

`tests/test_program.py` runs the function through `rrotor.testing` with GitHub answered by `FakeHttp`.
