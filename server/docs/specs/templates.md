# Templates: build your glyphh

A template is a bundle a person installs for themselves: Ada models made from one spec, the tools it adds to that
person's own connector (never their org's), what a hook puts before an AI, and the instructions an AI without hooks
follows. The first, **Agentic memory**, is a person's glyphh: what any AI they use knows about them, the rules they have
given it and the personality it has grown with them, kept as their own Ada models and carried from one AI to the next.
Any AI that speaks MCP attaches to it through the Glyphh connector; Claude Code also gets it through the `glyphh`
plugin's hooks.

## 1. The library

Glyphh ships the templates as JSON in the server (`src/glyphh_server/ops/templates/library/*.json`), seeded into
`templates` at every start (`ops/templates/library.py`): a newer version replaces the row, a template no longer shipped
is retired (`active` false), never deleted, and its installs keep working. A template is:

| Field | What |
|---|---|
| `slug`, `name`, `category`, `version`, `summary` | What the library shows |
| `spec` | The Ada spec every one of its models is made from |
| `models` | `{key, title, about}` each: one Ada model per key, the person's own |
| `tools` | `{name, title, op, description, kinds?}` each: a tool on the person's connector, one of the ops below over the models named by `kinds` (all, when left out); every name starts `glyphh_` |
| `context` | `session` and `prompt`, each `[{kind, top}]`: what a hook puts before an AI at a session's start (a kind's newest) and with each prompt (a kind's closest to it) |
| `instructions` | How an AI uses it, added to the connector's instructions for the person who installed it |

## 2. A person's glyphh

Installing makes each model in Ada Cloud as the person's, named `me-<their user id's first 12 hex>-<slug>-<key>`
(`ops/templates/glyphh.py`), then records the install in `template_installs` (one per person and template, their org's
rows only). A model already there is kept, so an install that failed half way is made again. Removing deletes those
models with every precedent in them, then the install.

A person's glyphh models are theirs alone: the connector's `ada_*` tools refuse anyone else's (`E_NOT_FOUND`) and
`ada_models` lists only their own. (An org's API key on the Ada API still reaches every model of the org.)

Each thing kept is one precedent: its outcome is the thing itself, its situation its words (`cue`: the situation it
applies to, then the text, read as a bag of words) and its `kind` (a light weight); its key part is the text, folded to
lower case, so remembering the same text again replaces it. The ops:

| Op | Arguments | Does |
|---|---|---|
| `remember` | `kind`, `text`, `when?` | Records it |
| `recall` | `about`, `kind?`, `top` | Each kind's closest to `about` by its words alone (`facts`, `min_score` 0.05), best first |
| `list` | `about?`, `top` | Each kind's newest (with `about`, as `recall`) |
| `forget` | `kind`, `id` | Forgets it |

Agentic memory keeps three kinds: `memory` (facts about the person), `instructions` (their rules) and `personality`
(how to be with them), with `glyphh_remember`, `glyphh_recall`, `glyphh_personality`, `glyphh_instructions` and
`glyphh_forget`.

## 3. The connector

With Ada Cloud on, the connector offers `templates` (`q`), `template` (`slug`), `template_install` (`slug`) and
`template_remove` (`slug`, `confirm` the slug again), and `tools/list` adds the tools of every template the person has
installed; `initialize` and `server/discover` add each one's `instructions`. The connector is stateless, so a client
sees new tools when it lists them again (reconnecting). A template's tool waits on a worker, so it runs after the
request's transaction has ended, as the other Ada tools do. Two templates may not add the same tool (`E_CONFLICT`
naming them).

## 4. The API

| Call | Does |
|---|---|
| `GET /v1/templates?q=` | `{templates}`: the library, each with `installed` and `installed_version`, and each model's name for the caller |
| `GET /v1/templates/{slug}` | One |
| `POST /v1/templates/{slug}/install` | Installs it for the caller; `E_UNAVAILABLE` `ada_off` while Ada Cloud is off |
| `DELETE /v1/templates/{slug}/install` | Removes it, its models deleted; `E_NOT_FOUND` when not installed |
| `POST /v1/me/glyphh/context` | `{prompt?}` → `{context}`: the hooks' text, a session's start without a prompt, what bears on it with one; `""` when there is nothing |

## 5. The plugin and the platform

The `glyphh` plugin's `SessionStart` and `UserPromptSubmit` hooks call `POST /v1/me/glyphh/context` with the install's
token and put the answer in Claude's context, so Claude starts each session with the person's personality and rules
and each prompt with what bears on it. The platform's Templates page lists the library and installs and removes one.
