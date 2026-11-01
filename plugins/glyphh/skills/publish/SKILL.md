---
name: publish
description: Publish a page Claude made (a Claude Code artifact, an HTML or Markdown file) to the person's organisation as an app on its own rrotor, where an admin or a reviewer approves it and the organisation's people open it. Use when the person says "publish this to my org", "put this artifact on our rrotor", "share this dashboard with the team through Glyphh", or runs /glyphh:publish. Not for publishing to claude.ai (Claude Code does that itself) and not for programs without a page (the rrotor-programs skill).
---

# Publish a page to the organisation

A page Claude wrote in this session (an artifact: one self-contained `.html` or `.md` file) becomes an **app** on
the organisation's rrotor: a program of `"kind": "app"` that rrotor serves at `https://<host>/apps/<name>/` to
people signed in to Glyphh for that rrotor whose roles allow it, once a reviewer has approved it. The page never
goes through Glyphh's server: it goes from this session to the rrotor, and the server keeps only the catalogue
entry (title, description, version, roles, who published it, its review state).

Do it in this order.

## 1. Find the page

- The session's latest artifact: the file Claude wrote when it published (an `.html` or `.md` in a temporary
  directory outside the project, or the path the person named when they asked for it). If the person names a path,
  use that. If there is more than one candidate, ask which, in one line.
- Read it. It must be one file: Claude Code's artifacts are self-contained (styles and scripts inline, libraries
  from the five CDN hosts cdnjs, jsDelivr, the Tailwind and jQuery CDNs and unpkg, fonts from Google Fonts). rrotor
  serves it under the same rules, so a page that already works as an artifact works as an app.

## 2. Agree the name, the title, the description and the roles

- **name**: kebab-case from the title (`deploy-failures`), `^[a-z][a-z0-9-]{0,62}$`; confirm it with the person
  since it is the address (`/apps/<name>/`) and a new version of the same name replaces the old one.
- **title** (up to 120 characters) and a one-line **description**: what the page shows, in the person's words.
- **roles**: which roles may open it. A role is a group name from the organisation's identity provider (what
  single sign-on gives each person) or `admin` or `member`. Default: everyone in the organisation (`[]`). Ask only
  if the person did not say.

## 3. Replace what cannot run on rrotor

A Claude Code artifact may pull live data through claude.ai connectors when it is viewed. On rrotor there is no
claude.ai in the path: the page may `fetch` only its own origin. For each such section:

- **Make it a function.** Write `program.py` with one function per data need, as the rrotor-programs skill
  describes (`def failures(ctx, inputs) -> Result`), using `ctx.http` to the hosts the manifest declares, or
  `ctx.cli` with a CLI on the rrotor (`gh`, `claude`, the person's own). Name the function in the manifest's
  `functions` and in `app.functions`. In the page, replace the connector call with
  `fetch("/apps/<name>/call/<function>", {method: "POST", headers: {"content-type": "application/json"}, body:
  JSON.stringify(inputs)})`: the answer is the function's Result (`{status: "done", data: ...}`), run as the person
  viewing the page, with their own CLI sign-ins. A `needs_input` or `needs_approval` Result carries a `run_id` the
  page may answer at `POST /apps/<name>/runs/<run_id>/continue`.
- **Or leave it out**, with a short note in the page where the section was ("Live data is not on this copy"), when
  the person prefers a static page or the data has no source the rrotor can reach.

Say which you did, in one line each.

## 4. Publish

Call the rrotor's `app_publish` tool (on the rrotor the organisation runs; the rrotor skill connects it). The
person can do the same from the mod without Claude: `/glyphh publish <file> [--name n] [--title t] [--description
d] [--roles a,b]` sends the one file to the local rrotor, and `/glyphh artifacts` shows the organisation's list
(with a reviewer's Approve, Reject and Retire) in the panel.

```json
{
  "name": "deploy-failures",
  "title": "Deploy failures",
  "description": "Last week's deploy failures by service.",
  "roles": ["sre", "admin"],
  "files": { "index.html": "<the page's text>" },
  "entry": "index.html",
  "functions": { "failures": { "description": "The failures by service", "inputs": { "type": "object" } } },
  "program": "<program.py's text>",
  "hosts": ["api.github.com"],
  "clis": ["gh"]
}
```

`files` is each file's text (or `{"base64": ...}` for a binary one), up to 64 files and 16 MiB; `entry` defaults to
`index.html`; `functions`, `program`, `hosts`, `clis`, `secrets` and `limits` only when the page calls functions.
The tool answers `{program, version, commit_sha, deployed_at, url}`. A refusal is `{error: {code, message}}`: say
the message (`E_MANIFEST` says what to fix; `E_FORBIDDEN` on a self-hosted rrotor means the session is not signed in
to Glyphh for it: publishing is a person's act, never a key's).

A new version of an app already approved is deployed but not served until it is approved in turn: the approved
version stays up.

## 5. Tell the person

- The app is **awaiting review**, and who reviews: the organisation's admin, and the reviewer groups set on the
  platform's Settings → Auth. `whoami` (the Glyphh connector) says whether the person is a reviewer themselves
  (`reviewer: true`): then offer to approve it right away with `artifact_approve` (the `artifacts` tool lists it
  with its id under `state: "draft"`).
- The **Open** link: the `url` the tool answered. Viewers sign in to Glyphh there once.
- Where it is listed: the Artifacts page on the platform and the `artifacts` tool in Claude (its cards: search,
  Open, and for reviewers Approve and Reject).

## Example: a static page

The person: "publish the release notes page to my org". Claude finds `/tmp/claude-artifacts/release-notes.html`,
agrees `release-notes`, "Release notes, 1.6", "What changed in 1.6, for the whole company", roles everyone; the
page has no connector calls; calls `app_publish` with `files: {"index.html": ...}` and nothing else; answers:
"Published release-notes v1 to the rrotor, awaiting review by your admin (you are not a reviewer). Open:
https://rrotor.acme.com/apps/release-notes/".

## Example: a page with a function

The person: "put the deploy-failures dashboard on our rrotor, SRE only". The page pulled failures through the
GitHub connector. Claude writes `program.py`:

```python
from rrotor import Ctx, Result


def failures(ctx: Ctx, inputs: dict) -> Result:
    runs = ctx.http.get("https://api.github.com/repos/acme/platform/actions/runs", params={"status": "failure", "per_page": 100}).raise_for_status().json()
    by_service: dict[str, int] = {}
    for run in runs["workflow_runs"]:
        by_service[run["name"]] = by_service.get(run["name"], 0) + 1
    return Result.done({"failures": by_service})
```

replaces the connector call in the page with `fetch("/apps/deploy-failures/call/failures", {method: "POST",
headers: {"content-type": "application/json"}, body: "{}"})`, and calls `app_publish` with `roles: ["sre",
"admin"]`, `functions`, `program` and `hosts: ["api.github.com"]`. Then: "Published deploy-failures v1, SRE and
admins only, awaiting review. You are a reviewer: approve it now?"
