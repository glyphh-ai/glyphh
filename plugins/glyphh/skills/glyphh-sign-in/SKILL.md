---
name: glyphh-sign-in
description: Sign this device in to Glyphh. Use when the user asks to sign in, log in or connect to Glyphh, or asks whether they are signed in to Glyphh.
---

# Sign in to Glyphh

Call the `glyphh_login` tool (this plugin's account mod answers it). It takes no arguments and answers a `state`.

- `signed_in`: it carries the `email`. Tell the user they are signed in as that and stop.
- `pending`: it carries `user_code` and `url`, and the sign-in shows in the chat with the code. **Right away, open
  `url` in the browser pane** (the Claude_Browser `preview_start` tool) if it is not open already, then tell the user,
  in one line, to approve the code there. Do not poll; the sign-in in the chat says when they are signed in.
- `signed_out` with an `error` (for example the Glyphh server cannot be reached): say so plainly. `/glyphh signin` is
  the other way in.
- No `glyphh_login` tool (the mod is off, it needs `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`): tell the user to sign in
  with `/glyphh signin`, or to sign in to the `glyphh-cloud` connector through `/mcp`.

Never ask the user for a password or token.

Once signed in, the Glyphh connector's `whoami` says who they are: name, email, organisation and role, and now
their `groups` (from the organisation's single sign-on, if any) and `reviewer` (whether they review the apps
published to the organisation's rrotors: the `publish` skill).
