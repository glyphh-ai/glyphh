---
name: glyphh-sign-in
description: Sign this machine in to Glyphh. Use when the user asks to sign in, log in or connect to Glyphh, or asks whether they are signed in to Glyphh.
---

# Sign in to Glyphh

Call the `glyphh_sign_in` tool (from this plugin's `glyphh` MCP server). It takes no arguments.

- Signed in already: it answers "Signed in as <email>." Tell the user that and stop.
- Otherwise it shows a sign-in card in the chat with a code and a **Sign in** button, and its answer carries `verification_uri_complete`. Tell the user, in one line, to press **Sign in** on the card. Pressing it sends a chat message asking to open the sign-in page: when that message comes, open its address in the browser pane (the Claude_Browser `preview_start` tool) and say to approve it there. The card waits for approval and says when the user is signed in. Do not poll; the card does.
- Where no card shows, the tool's text holds the code and the link: give them to the user, and once they say they approved it, call `glyphh_sign_in` again to finish.
- If it fails (for example the Glyphh server cannot be reached), say so plainly. `/glyphh signin` is the other way in.

Never ask the user for a password or token, and never call `glyphh_sign_in_status` yourself: it is the card's.
