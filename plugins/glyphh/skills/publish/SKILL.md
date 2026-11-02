---
name: publish
description: Publish what Claude made (a Claude Code artifact, a React page, a Markdown document or a Claude Doc, a Mermaid or SVG diagram, a deck or a design exported to PDF or an image, a dashboard) to the person's organisation as an app on its own rrotor, where an admin or a reviewer approves it and the organisation's people open it. Use when the person says "publish this to my org", "put this on our rrotor", "share this dashboard with the team through Glyphh", or runs /glyphh:publish. Not for publishing to claude.ai (Claude Code does that itself) and not for programs without a page (the rrotor-programs skill).
---

# Publish an app to the organisation

What Claude made in this session becomes an **app** on the organisation's rrotor: a program of `"kind": "app"` that
rrotor serves at `https://<host>/apps/<name>/` to people signed in to Glyphh for that rrotor whose roles allow it,
once a reviewer has approved it. The file never goes through Glyphh's server: it goes from this session to the
rrotor, and the server keeps only the catalogue entry (title, description, type, version, roles, who published it,
its review state). "Artifact" is Claude's word for the file in the session; on the rrotor, in the catalogue, in
Claude and on the platform it is an app.

Do it in this order.

## 1. Find the file

| Made as | The file |
|---|---|
| A Claude Code artifact (this session) | The file Claude wrote when it made it: one self-contained `.html` or `.md` in a temporary directory outside the project. Read it back |
| A React page Claude wrote | The one `.jsx` or `.tsx` (section 4) |
| A path the person names | That file |
| A Claude Doc (claude.ai) | Export it to Markdown with the Claude Docs connector's `export` and write the Markdown to a file (`<name>.md`) |
| A Claude Slides deck, or a Claude Design | Neither exports from here: ask the person to export it from claude.ai as PDF (a deck) or as PDF or PNG (a design) and give the path |
| A Claude Dashboard (claude.ai) | It has no export. Each chart on it shows its SQL: ask the person for the charts' queries and the data source (which warehouse, and the CLI they reach it with), and rebuild it as a dashboard app (section 5) |

One file. If there is more than one candidate, ask which, in one line. A page must be self-contained (styles and
scripts inline, libraries from the five CDN hosts cdnjs, jsDelivr, the Tailwind and jQuery CDNs and unpkg, fonts
from Google Fonts): rrotor serves it under those rules, so a page that works as a Claude Code artifact works as an
app.

## 2. The type

By the file's extension, unless the person says otherwise:

| Entry | Served as | Type |
|---|---|---|
| `.html`, `.htm` | as it is | `page` |
| `.jsx`, `.tsx` | rrotor's React shell (section 4) | `page` |
| `.md` | rrotor's document shell: the Markdown rendered | `doc` |
| `.pdf` | the browser's own viewer | `doc` |
| `.mmd`, `.mermaid` | rrotor's diagram shell: Mermaid rendered | `diagram` |
| `.svg` | as it is | `diagram` |
| `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` | rrotor's image shell: the image centred, with the title | `design` |

`dashboard` (a page whose numbers come from the app's own functions) and `deck` (a presentation, usually a PDF) are
never inferred: say them in `type`. Any other file is refused by rrotor (`E_INPUTS`: "entry is a page (.html,
.jsx, .tsx), a document (.md, .pdf), a diagram (.mmd, .svg) or an image"): convert it first (a `.pptx` to PDF, a
`.docx` to Markdown), or say it cannot go.

## 3. Agree the name, the title, the description and the roles

- **name**: kebab-case from the title (`deploy-failures`), `^[a-z][a-z0-9-]{0,62}$`; confirm it with the person
  since it is the address (`/apps/<name>/`) and a new version of the same name replaces the old one.
- **title** (up to 120 characters) and a one-line **description**: what it shows, in the person's words.
- **roles**: which roles may open it. A role is a group name from the organisation's identity provider (what
  single sign-on gives each person) or `admin` or `member`. Default: everyone in the organisation (`[]`). Ask only
  if the person did not say.

## 4. A React page

A `.jsx` or `.tsx` entry is what claude.ai's React artifacts are, and rrotor builds nothing: it serves the file in
its React shell, an HTML page with an import map for `react`, `react-dom` (and `react-dom/client`), `recharts`,
`lucide-react`, `d3`, `three`, `framer-motion`, `date-fns`, `lodash`, `papaparse`, `mathjs` and `@radix-ui/*` (the
React family from esm.sh so the page holds one React, the rest from jsDelivr), the Tailwind CDN, and Babel in the
browser (the automatic JSX runtime, and TypeScript for `.tsx`). So:

- One file, with ES imports of those packages only (`import React from 'react'` is not needed for JSX, hooks are
  imported from `react`); Tailwind classes are fine; `export default` the component, which the shell mounts into
  `#root`.
- A package outside that list fails in the browser as it would on claude.ai: inline what it did, or drop it.
- No build step, no `package.json`, no CSS file: styles as Tailwind classes or a `<style>` element.

## 5. A dashboard, or any page with live data

A Claude Code artifact or a Claude Dashboard pulls live data through claude.ai connectors or claude.ai's own
warehouse links. On rrotor there is no claude.ai in the path: the page may `fetch` only its own origin. So each
chart or table becomes a function of the app, called **as the viewer**:

- **One function per chart** in `program.py` (the rrotor-programs skill: `def failures(ctx, inputs) -> Result`).
  The data comes through `ctx.cli` with a CLI on the rrotor (`bq`, `snowsql`, `databricks`, `psql`,
  `clickhouse-client`, `gh`, any CLI the manifest's `clis` names), which each person signs in to once with
  `cli_login`, so two people opening the same dashboard see what their own accounts allow; or through `ctx.http` to
  the hosts the manifest declares. Name each function in the manifest's `functions` and in `app.functions`.
- **A slow source: cache it.** Keep the last answer in `ctx.db` (the app's SQLite) and add a `schedules` entry that
  refreshes it (a schedule runs as the program with its own secrets, not as a person). Answer the rows with when
  they were refreshed (`{"rows": [...], "refreshed_at": "..."}`).
- **In the page**, replace each connector call with `fetch("/apps/<name>/call/<function>", {method: "POST",
  headers: {"content-type": "application/json"}, body: JSON.stringify(inputs)})`; the answer is the function's
  Result (`{status: "done", data: ...}`). Show each chart's refreshed time from its answer. A `needs_input` or
  `needs_approval` Result carries a `run_id` the page may answer at `POST /apps/<name>/runs/<run_id>/continue`.
- **Or leave the section out**, with a short note in the page where it was ("Live data is not on this copy"), when
  the person prefers a static page or the data has no source the rrotor can reach.

The type is `dashboard`. Say which you did, in one line each.

## 6. Publish

Call the rrotor's `app_publish` tool (on the rrotor the organisation runs; the rrotor skill connects it). The
person can do the same from the mod without Claude: `/glyphh publish <file> [--name n] [--title t] [--description
d] [--type t] [--roles a,b]` sends one file to the local rrotor, and `/glyphh apps` shows the organisation's list
(a type filter; a reviewer's Approve, Reject and Retire) in the panel.

```json
{
  "name": "deploy-failures",
  "title": "Deploy failures",
  "description": "Last week's deploy failures by service.",
  "type": "dashboard",
  "roles": ["sre", "admin"],
  "files": { "index.html": "<the page's text>" },
  "entry": "index.html",
  "functions": { "failures": { "description": "The failures by service", "inputs": { "type": "object" } } },
  "program": "<program.py's text>",
  "hosts": ["api.github.com"],
  "clis": ["gh"]
}
```

`files` is each file's text, or `{"base64": "..."}` for a PDF or an image, up to 64 files and 16 MiB; `entry`
defaults to `index.html` (the one file, when there is one); `type` is the table's word, else the entry's own;
`functions`, `program`, `hosts`, `clis`, `secrets`, `schedules` and `limits` only when the page calls functions.
The tool answers `{program, version, commit_sha, deployed_at, type, url}`. A refusal is `{error: {code, message}}`:
say the message (`E_INPUTS` and `E_MANIFEST` say what to fix; `E_FORBIDDEN` on a self-hosted rrotor means the
session is not signed in to Glyphh for it: publishing is a person's act, never a key's).

A new version of an app already approved is deployed but not served until it is approved in turn: the approved
version stays up.

## 7. Tell the person

- The app is **awaiting review**, and who reviews: the organisation's admin, and the reviewer groups set on the
  platform's Settings → Auth. `whoami` (the Glyphh connector) says whether the person is a reviewer themselves
  (`reviewer: true`): then offer to approve it right away with `app_approve` (the `apps` tool lists it with its id
  under `state: "draft"`).
- The **Open** link: the `url` the tool answered. Viewers sign in to Glyphh there once.
- Where it is listed: the Apps page on the platform, the `apps` tool in Claude (its cards: search, a type filter,
  Open, and for reviewers Approve and Reject), and `/glyphh apps` in the mod.

## Example: a static page

The person: "publish the release notes page to my org". Claude finds `/tmp/claude-artifacts/release-notes.html`,
agrees `release-notes`, "Release notes, 1.7", "What changed in 1.7, for the whole company", roles everyone; the
page has no connector calls; calls `app_publish` with `files: {"index.html": ...}`, `type: "page"` and nothing
else; answers: "Published release-notes v1 (page) to the rrotor, awaiting review by your admin (you are not a
reviewer). Open: https://rrotor.acme.com/apps/release-notes/".

## Example: a deck

The person: "share the Q3 review deck with the leadership group". It is a Claude Slides deck: Claude asks them to
export it as PDF from claude.ai and name the path; reads it as bytes; calls `app_publish` with `files:
{"index.pdf": {"base64": "..."}}`, `type: "deck"`, `roles: ["leadership"]`. Then: "Published q3-review v1 (deck),
leadership only, awaiting review."

## Example: a Claude Dashboard rebuilt

The person: "put my deploy-failures dashboard on our rrotor, SRE only". It is a Claude Dashboard on claude.ai with
one chart whose SQL reads BigQuery. Claude asks for the query and that they use `bq`; writes `program.py`:

```python
import json

from rrotor import Ctx, Result

QUERY = "SELECT workflow, COUNT(*) AS failures FROM ops.deploys WHERE failed AND day >= CURRENT_DATE() - 7 GROUP BY 1"


def failures(ctx: Ctx, inputs: dict) -> Result:
    # Runs as the person viewing the page, with their own bq sign-in (cli_login).
    out = ctx.cli("bq", ["query", "--format=json", "--use_legacy_sql=false", QUERY])
    if out.exit_code != 0:
        return Result.failed("query", out.stderr.strip())
    return Result.done({"rows": json.loads(out.stdout), "refreshed_at": str(ctx.now())})
```

replaces the chart's data with `fetch("/apps/deploy-failures/call/failures", {method: "POST", headers:
{"content-type": "application/json"}, body: "{}"})` and shows `refreshed_at` under the chart, and calls
`app_publish` with `type: "dashboard"`, `roles: ["sre", "admin"]`, `functions`, `program` and `clis: ["bq"]`.
Then: "Published deploy-failures v1 (dashboard), SRE and admins only, awaiting review. Each viewer signs `bq` in
once with cli_login. You are a reviewer: approve it now?"
