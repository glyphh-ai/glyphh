---
name: glyphh-sign-in
description: Sign this device in to Glyphh. Use when the user asks to sign in, log in or connect to Glyphh, or asks whether they are signed in to Glyphh.
---

# Sign in to Glyphh

Call the `glyphh_sign_in` tool (from this plugin's `glyphh` MCP server). It takes no arguments.

- Signed in already: it answers "Signed in as <email>." Tell the user that and stop.
- Otherwise it shows a sign-in card in the chat with the code, and its answer carries `verification_uri_complete`. **Right away, open that address in the browser pane** (the Claude_Browser `preview_start` tool): the card shows the code, the page beside it signs the user in. Then tell the user, in one line, to approve the code on that page. The card waits and says when they are signed in. Do not poll; the card does.
- Where no card shows, the tool's text holds the code and the link: give them to the user, and once they say they approved it, call `glyphh_sign_in` again to finish.
- If it fails (for example the Glyphh server cannot be reached), say so plainly. `/glyphh signin` is the other way in.

Never ask the user for a password or token, and never call `glyphh_sign_in_status` yourself: it is the card's.

Once signed in, the Glyphh connector's `whoami` says who they are: name, email, organisation and role, and now
their `groups` (from the organisation's single sign-on, if any) and `reviewer` (whether they review the apps
published to the organisation's rrotors: the `publish` skill).
