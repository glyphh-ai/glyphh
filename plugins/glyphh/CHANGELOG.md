# The glyphh plugin's changelog

Newest first. The version is `.claude-plugin/plugin.json`'s and the marketplace's.

## 2.0.0 — 2026-11-24

Glyphh is one thing: Ada. The plugin is now your Glyphh account and sign-in, the Ada skill, the glyphh command's
skill and the file ledger. A major version because skills, commands and a panel section are gone.

- Skills: `ada`, `glyphh-cli` and `glyphh-sign-in` stay. Every other skill is removed.
- `/glyphh`: Sign in, Account, Org, Plan and Billing stay. The Apps section and every `/glyphh` subcommand but
  `signin` and `signout` (`login`, `logout`) and the section names are removed, and the Account section shows your
  name, email, sign-ins and installs only.
- Hooks: the file ledger's three command hooks stay. The hooks that added context from the server at a session's
  start and with each prompt are removed: nothing of a prompt is sent anywhere.
- The mod no longer runs any installer script, reads a file to publish, or talks to `127.0.0.1`: it calls
  `api.glyphh.ai` for sign-in, `/v1/me`, `/v1/installs`, `/v1/org`, `/v1/plans` and `/v1/billing`, and nothing else.
- `.mcp.json` still names one server, the Glyphh connector (`glyphh-cloud` at `https://api.glyphh.ai/mcp`), which
  brings the `ada_*` tools.

Other plugins and skills for Claude are at https://github.com/glyphh-ai/plugins.

## 1.x

What 1.x gave the parts that stay:

- 1.19.0 (2026-11-13): no local MCP server. Sign-in from the chat calls the account mod's own `glyphh_login`.
- 1.18.2 (2026-11-04): `.mcp.json` names the Glyphh connector, so the plugin brings the `ada_*` tools.
- 1.18.0 (2026-11-04): the beam. The Ada skill names `ada_beam`, a chain of models.
- 1.9.1 (2026-11-02): jobs can be stopped. The Ada skill names `ada_job_cancel` and the stage `ada_job` answers.
- 1.7.1 (2026-11-02): the panel's sections drawn from one kit; a member's row says Admin or You; the plan the org is
  on is marked on Plan and Billing alike.
- 1.4.0 (2026-10-29): the glyphh command. The `glyphh-cli` skill does the Ada skill's work through the shell.
- 1.3.0 (2026-10-28): typed outputs and discriminated unions in the Ada skill (on `ada-1-2-beta`).
- 1.2.0 (2026-10-23): Ada versions (contract 5): the skill says which Ada version a model runs and offers a newer
  stable with a backtest first; the panel shows each model's Ada version.
