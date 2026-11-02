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
warehouse links. On rrotor there is no claude.ai in the path: the page may reach only its own origin. So each
chart or table becomes a function of the app, called from the page through `rrotor.js`, **as the viewer** or **as
the app** (`run_as`, below):

- **One function per chart** in `program.py` (the rrotor-programs skill: `def failures(ctx, inputs) -> Result`).
  The data comes through `ctx.cli` with a CLI on the rrotor (`bq`, `snowsql`, `databricks`, `psql`,
  `clickhouse-client`, `gh`, any CLI the manifest's `clis` names), or through `ctx.http` to the hosts the manifest
  declares. Name each function in the manifest's `functions` and in `app.functions`.
- **A slow source: cache it.** Keep the last answer in `ctx.db` (the app's SQLite) and add a `schedules` entry that
  refreshes it (a schedule runs as the app itself, with its own secrets, never as a person). Answer the rows with
  when they were refreshed (`{"rows": [...], "refreshed_at": "..."}`).
- **Or leave the section out**, with a short note in the page where it was ("Live data is not on this copy"), when
  the person prefers a static page or the data has no source the rrotor can reach.

The type is `dashboard`. Say which you did, in one line each.

### Who the functions run as: `run_as`

Decide it with the person; it is one word in the manifest's `app` block (and `app_publish`'s `run_as`), and the
catalogue shows it on the app's card.

| `run_as` | When | What happens |
|---|---|---|
| `viewer` (the default) | Each person should see **their own** data: a dashboard over their warehouse, their GitHub, their tickets. The tell: two people opening it should see different things, or the page says "your" | A call runs as the person viewing the page, in their own HOME on the rrotor, with their own CLI sign-ins. Each viewer signs each CLI in once, from the page (rrotor's sign-in card, below) or with `cli_login` from Claude |
| `app` | The page is **the same for everyone**, and the organisation holds a key or signs the CLI in once: a report, a status board, anything a schedule could make. The tell: "everyone sees the same numbers", or the data comes from a service account | A call runs as the app itself: no viewer in it, the CLI's shared HOME and the app's own vault, exactly as a schedule's run or a runtime key's call. An admin signs its CLIs in once (`cli_login` with `shared: true`), or sets its keys once (`secret_set`); a viewer never signs in |

Not sure: `viewer`. A `run_as: app` page with a CLI that needs a person's account is a mistake (the admin's account
would answer for everyone): use a key, or make it `viewer`.

### In the page: `rrotor.js`

The page loads rrotor's own script and calls its functions through it; no client code of its own, no `fetch`:

```html
<script src="/apps/_/rrotor.js"></script>
<script>
  (async () => {
    await rrotor.ready();                                  // the sign-in card, if a CLI needs one
    const data = await rrotor.call("failures", { since });  // the function's data
  })();
</script>
```

- `rrotor.call(fn, inputs = {})` → the function's `data` when the Result is `done`; a `needs_input` or
  `needs_approval` Result throws an error carrying the run id, and `rrotor.continue(runId, answer)` carries the
  answer back; a `failed` Result throws an error with the code and the reason.
- `rrotor.ready(names = every CLI of the app)` → resolves once each named CLI is signed in for this viewer. For each
  that is not, it shows rrotor's **sign-in card** (a small fixed panel over the page, its own styles in a shadow
  root): "Sign in to <title> to continue", the address as a link that opens in a new tab, the device code in large
  type with Copy, "Waiting…", then "Signed in" and gone; it polls the sign-in and types a code back when the CLI
  asks for one. A `run_as: app` page's `ready()` resolves at once. **Always await it before the first `call`**, so
  a viewer who is not signed in gets the card and not an error.
- `rrotor.clis()` → `[{name, title, signed_in, login}]` for the app's CLIs, as this viewer stands.
- `rrotor.app` → `{name, title, type, run_as, viewer: {sub, role, groups} | null}` (a local rrotor: `viewer: null`).

It is the same origin as the page (rrotor's CSP allows it), served fresh each time (`no-store`), and needs rrotor
0.4.0: on an older rrotor the script is Not Found (the rrotor skill's `rrotor.sh update`).

### A key from the vault into a CLI

A CLI that takes a token in its environment needs no sign-in: the app declares the secret, and the function hands
it to the command for that one call:

```python
out = ctx.cli("gh", ["issue", "list", "--repo", REPO, "--json", "number,title"], env={"GH_TOKEN": ctx.secrets["GH_TOKEN"]})
```

`env` maps names (`[A-Z_][A-Z0-9_]*`, at most 32) to values the command gets beside the CLI's own; a value of four
characters or more is masked in the run's log. With `run_as: app` and `secrets: ["GH_TOKEN"]`, `gh` runs as the key
for every viewer. Tell the person which secrets to set (`secret_set {program: <name>, name: "GH_TOKEN", value}`
on the rrotor, before the review: the card says "GH_TOKEN not set on the rrotor" until then; a missing one fails
the run by name), and never ask for a value you do not need.

## 6. Publish

Call the rrotor's `app_publish` tool (on the rrotor the organisation runs; the rrotor skill connects it). The
person can do the same from the mod without Claude: `/glyphh publish <file> [--name n] [--title t] [--description
d] [--type t] [--roles a,b]` sends one file to the local rrotor, and `/glyphh apps` shows the organisation's list
(a type filter; a reviewer's Approve, Reject and Retire) in the panel.

**No `app_publish` among `mcp__rrotor__*`** while `programs_list` is there: the rrotor is older than this plugin
(before 0.2.0 it had no apps; before 0.3.0 only HTML and Markdown; before 0.4.0 no `rrotor.js`, no sign-in from the
page and no `run_as`). Never write the page to a file and hand it to the
person instead: run the rrotor skill's `rrotor.sh update` (it keeps everything on the volume), tell them Claude Code
loads the tools again at `/mcp` or its next start, and publish from there; or publish now with `/glyphh publish
<file>`, which the mod sends to the updated rrotor without the tools.

```json
{
  "name": "deploy-failures",
  "title": "Deploy failures",
  "description": "Last week's deploy failures by service.",
  "type": "dashboard",
  "roles": ["sre", "admin"],
  "run_as": "viewer",
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
`run_as` is `viewer` (the default) or `app` (section 5); `functions`, `program`, `hosts`, `clis`, `secrets`,
`schedules` and `limits` only when the page calls functions. The name `_` is refused (it is `rrotor.js`'s).
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
- **What it needs, when it needs anything.** A `run_as: viewer` app with CLIs: each viewer signs them in once, from
  the page's sign-in card or with `cli_login`. A `run_as: app` app: the secrets to set (`secret_set`, each by name)
  and, for a CLI without a key, that an admin signs it in once with `cli_login {cli, shared: true}` (an admin's
  act: a member is refused). Say it before the review, since the card shows a missing secret.
- Where it is listed: the Apps page on the platform, the `apps` tool in Claude (its cards: search, a type filter,
  Open, and for reviewers Approve and Reject), and `/glyphh apps` in the mod.

**People without Claude Code** see the same catalogue: in claude.ai (and the desktop and mobile apps) the Glyphh
connector's `apps` tool draws it inline in the chat ("show me our apps", "what is awaiting my review": the cards,
search, the type filter, Open, and a reviewer's Approve, Reject and Retire, nothing leaving the chat), and in a
browser the rrotor's own `/apps/` page lists its apps to anyone signed in to Glyphh for it (a reviewer sees the
drafts too, with **Review on Glyphh** to the platform). So a viewer needs neither the plugin nor Claude Code.

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
one chart whose SQL reads BigQuery. Claude asks for the query and that they use `bq`; each SRE should see what
their own BigQuery account allows, so `run_as` is `viewer`; writes `program.py`:

```python
import json

from rrotor import Ctx, Result

QUERY = "SELECT workflow, COUNT(*) AS failures FROM ops.deploys WHERE failed AND day >= CURRENT_DATE() - 7 GROUP BY 1"


def failures(ctx: Ctx, inputs: dict) -> Result:
    # Runs as the person viewing the page, with their own bq sign-in.
    out = ctx.cli("bq", ["query", "--format=json", "--use_legacy_sql=false", QUERY])
    if out.exit_code != 0:
        return Result.failed("query", out.stderr.strip())
    return Result.done({"rows": json.loads(out.stdout), "refreshed_at": str(ctx.today())})
```

replaces the chart's data in the page with

```html
<script src="/apps/_/rrotor.js"></script>
<script>
  (async () => {
    await rrotor.ready(["bq"]);                 // the sign-in card for a viewer not yet signed in to bq
    const { rows, refreshed_at } = await rrotor.call("failures");
    draw(rows); note(`Refreshed ${refreshed_at}`);
  })();
</script>
```

and calls `app_publish` with `type: "dashboard"`, `roles: ["sre", "admin"]`, `run_as: "viewer"`, `functions`,
`program` and `clis: ["bq"]`. Then: "Published deploy-failures v1 (dashboard), SRE and admins only, awaiting
review. Each viewer signs `bq` in once, from the page. You are a reviewer: approve it now?"

## Example: a report run as the app, with a key

The person: "publish the open-issues report to the whole company". The page lists the open issues of one
repository, the same for everyone, and the organisation has a GitHub token for it: `run_as` is `app` and the token
is a secret. Claude writes `program.py`:

```python
import json

from rrotor import Ctx, Result

REPO = "acme/platform"


def issues(ctx: Ctx, inputs: dict) -> Result:
    # Runs as the app, for every viewer alike: gh as the organisation's key, no sign-in.
    out = ctx.cli("gh", ["issue", "list", "--repo", REPO, "--state", "open", "--json", "number,title,createdAt"], env={"GH_TOKEN": ctx.secrets["GH_TOKEN"]})
    if out.exit_code != 0:
        return Result.failed("list", out.stderr.strip())
    return Result.done({"issues": json.loads(out.stdout), "refreshed_at": str(ctx.today())})
```

the page loads `rrotor.js`, awaits `rrotor.ready()` (it resolves at once: no viewer signs in) and calls
`rrotor.call("issues")`; and `app_publish` gets `type: "dashboard"`, `run_as: "app"`, `clis: ["gh"]`, `secrets:
["GH_TOKEN"]`, `functions` and `program`. Then: "Published open-issues v1 (dashboard) to everyone, awaiting review.
It runs as the app: set GH_TOKEN on the rrotor with secret_set before it is approved (the card says it is not set
until then). Shall I set it now, if you paste the token?" Had `gh` no key, Claude would say instead that an admin
signs it in once with `cli_login {cli: "gh", shared: true}`.
