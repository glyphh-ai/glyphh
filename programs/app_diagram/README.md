# app_diagram

A diagram published to the organisation: one `.mmd` file, nothing behind it.

- **What it is:** `index.mmd`, a Mermaid sequence diagram of how a browser signs in to an app on the
  organisation's rrotor. rrotor serves it in its diagram shell (Mermaid rendered; the source as text when the
  library does not load) at `https://<host>/apps/sign_in_flow/` to anyone signed in to Glyphh for that rrotor
  (`"roles": []`), once a reviewer has approved it.
- **The type** is not in the manifest: a `.mmd` entry is a `diagram` when `app.type` is absent, as a `.svg` is.
  Only `dashboard` and `deck` are always said.
- **What it calls:** nothing.

## Publish it

Ask Claude to *"publish programs/app_diagram to my org"* (the plugin's `publish` skill), or from the mod:
`/glyphh publish programs/app_diagram/index.mmd --name sign-in-flow --title "Sign-in flow"`. The app waits for
review in the organisation's catalogue (the platform's Apps page, the `apps` tool in Claude, or `/glyphh apps`).
