# launch_watch

A project's launch numbers each morning, emailed to you.

- **What it takes:** GitHub stars, forks and open issues, new issues and PRs since the last run, and PyPI and npm
  downloads for yesterday and the past week.
- **Where it keeps them:** its SQLite database, one row a day, so each email shows the change since the day before.
- **How it emails:** it asks rrotor's built-in `claude` CLI to send the summary through your claude.ai Gmail
  connector, so there's no email API or key to set up.
- **When it asks first:** called from Claude, it shows you the email and waits for your approval. The 7:37 a.m.
  schedule (America/Chicago) sends on its own, since nobody is there to answer.

| Function | Inputs | Does |
|---|---|---|
| `morning` | `{"to": "you@example.com"}` | Takes today's numbers, keeps them, emails the summary |
| `history` | `{"days": 30}` | The kept numbers, newest first |

## Make it yours

1. In `program.py`, set `REPO`, `PYPI` and `NPM` to your own project.
2. In `glyphh.json`, set the schedule's `input.to` to your address, and change `cron` and `tz` if you want another
   time.
3. Sign the `claude` CLI in once with `cli_login`, using a claude.ai account that has Gmail connected.
4. Deploy it, then ask Claude to call `morning` once to see the first email.

It reaches only `api.github.com`, `pypistats.org` and `api.npmjs.org`, plus whatever the `claude` CLI is allowed.
