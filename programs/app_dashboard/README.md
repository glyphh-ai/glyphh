# app_dashboard

A dashboard published to the organisation, with one function behind it.

- **What it shows:** failed GitHub Actions runs since a date, counted by workflow, with a bar each.
- **Where the data comes from:** the page's own function, `failures`, which the page calls at
  `/apps/deploy_failures/call/failures` each time it loads. The rrotor runs it as the person viewing the page,
  reaching only `api.github.com` (the manifest's `hosts`). No claude.ai connector is in the path: a Claude Code
  artifact that pulled this through the GitHub connector is rewritten this way when it is published (the plugin's
  `publish` skill).
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
