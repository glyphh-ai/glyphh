# app_static

A page published to the organisation, with nothing behind it.

- **What it is:** one `index.html`, served by the organisation's rrotor at `https://<host>/apps/release_notes/` to
  anyone signed in to Glyphh for that rrotor (`"roles": []`: everyone in the organisation), once a reviewer has
  approved it.
- **What it calls:** nothing. A static page needs no `program.py`.

The manifest is a program's with `"kind": "app"` and an `app` block: `entry` (the page), `title` (what the
catalogue shows) and `roles` (who may open it: group names from the organisation's single sign-on, or `admin`,
`member`; empty is everyone).

## Publish it

Ask Claude to *"publish programs/app_static to my org"* (the plugin's `publish` skill): it calls the rrotor's
`app_publish` with the page, and the app waits for review in the organisation's catalogue (the platform's Apps
page, the `apps` tool in Claude, or `/glyphh apps`). Deploying the folder as a program (`rrotor.sh deploy
programs/app_static`) does the same.
