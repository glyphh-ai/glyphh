---
name: rrotor-graph
description: Build data pipelines into rrotor's graph, its semantic layer (one knowledge graph of the organisation's data, with search), and build apps and answers on top of it. Use when the person wants to connect a data source to their rrotor (a CRM, a ticket system, a warehouse, files, any API), "build a pipeline", "load this into the graph", "make a knowledge graph" or "a semantic layer", to set a pipeline's API key or other secret, to search or explore what the graph holds, or to build a page, dashboard or answer from the organisation's data on rrotor. Needs rrotor 0.4.0 or later (the rrotor skill installs and updates it). Not for Ada models (the ada skill).
---

# Pipelines and the graph

rrotor keeps **one graph** for the whole runtime, its semantic layer: the organisation's data, shaped once, behind
everything built there.

| Thing | What |
|---|---|
| **node** | A type and a key (`deal`, `d-1042`), with a `title`, `props` (a JSON object) and `text`. `(type, key)` names it: writing it again changes it |
| **edge** | `from` a node, a relation (`belongs_to`), `to` a node, with `props` |
| **search** | Every node's title, props and text are indexed; a search answers the best **passages** with their nodes |

Types and relations are lower-case names (`^[a-z][a-z0-9_]{0,62}$`); a key is the source's own id, as text.

```
a source ──▶ a pipeline (a program on a schedule) ──▶ the graph ──▶ apps, programs, Claude
```

rrotor's tools are `mcp__rrotor__*` (not there: the rrotor skill). Search is by words (ranked, stemmed), not by
meaning: no model runs on rrotor. Say so when it matters, and search with the words the data uses.

## 1. Look first

`graph_schema` says what the graph holds: each type (how many, the props its nodes carry, the pipelines that wrote
them) and each relation between two types. Read it before writing a pipeline or an app, and reuse its types and
relations: a second pipeline that calls a company `account` where the first said `company` makes two graphs.

## 2. A pipeline

A pipeline is an ordinary rrotor program (the rrotor-programs skill: `glyphh.json`, `program.py`, its tests, a
commit, a deploy) whose manifest says `"graph": "write"`. There is no DAG engine: its steps are plain Python
functions that one function calls in order.

Agree with the person, before writing: the source and how it is reached (its API host; the key or token it needs);
which records become which node types, each one's key, title and text; which fields link records to each other;
how often it runs.

```json
{
  "name": "hubspot_pipeline",
  "description": "HubSpot's companies, contacts and deals, written to the graph each hour",
  "python": "3.13",
  "functions": { "sync": { "description": "Read every record and write it to the graph", "inputs": { "type": "object", "additionalProperties": false } } },
  "hosts": ["api.hubapi.com"],
  "secrets": ["HUBSPOT_TOKEN"],
  "graph": "write",
  "limits": { "seconds": 900, "memory_mb": 512 },
  "schedules": [{ "function": "sync", "cron": "5 * * * *", "name": "each_hour" }]
}
```

```python
from rrotor import Ctx, Result

API = "https://api.hubapi.com/crm/v3/objects"


def extract(ctx: Ctx, objects: str, properties: list[str]):
    """Every record, a page at a time."""
    headers = {"Authorization": f"Bearer {ctx.secrets['HUBSPOT_TOKEN']}"}
    after = None
    while True:
        params = {"limit": 100, "properties": ",".join(properties), "associations": "companies"}
        if after:
            params["after"] = after
        page = ctx.http.get(f"{API}/{objects}", params=params, headers=headers).raise_for_status().json()
        yield from page.get("results", [])
        after = ((page.get("paging") or {}).get("next") or {}).get("after")
        if not after:
            return


def transform(record: dict) -> dict:
    """A record as a flat row."""
    linked = ((record.get("associations") or {}).get("companies") or {}).get("results") or []
    return {"id": record["id"], **(record.get("properties") or {}), "companies": sorted({a["id"] for a in linked})}


def store(ctx: Ctx, rows: list[dict]) -> dict:
    """The rows as nodes, with an edge to each company a row names."""
    return ctx.graph.rows(rows, type="deal", key="id", title="dealname", text=["description"],
                          links={"companies": ("belongs_to", "company")})


def sync(ctx: Ctx, inputs: dict) -> Result:
    rows = [transform(r) for r in extract(ctx, "deals", ["dealname", "amount", "dealstage", "description"])]
    return Result.done(store(ctx, rows))
```

- **Never name a step `load` or `end`**: rrotor calls a program's own `load(ctx)` before every run and `end(ctx)`
  after. Call the last step `store`.
- **`ctx.graph.rows(records, type=, key=, title=, text=, props=, links=)`** writes a table of records: each row a
  node of `type` named by its `key` column; `title` a column (or a function of the row); `text` the columns whose
  words are the node's text (notes, a description, a body: what search should read); the other columns its props
  (or only those `props` names). `links={"account_id": ("belongs_to", "account")}` makes an edge from the row to the
  account that column names; `("has_deal", "account", "in")` points it the other way; a list links each; an empty
  value, none. A row without a key is left out.
- **`ctx.graph.upsert(nodes=[{type, key, title?, props?, text?}], edges=[{from: {type, key}, rel, to: {type, key},
  props?}])`** writes them as given: use it for documents (`text` is the whole document, up to a million
  characters; rrotor cuts it into passages) and for edges that are not a column.
- **Run again, it changes nothing it should not:** a node written again keeps what the write does not name, and
  the graph holds one of each `(type, key)`. An edge to a node not written yet makes that node, empty, until its own
  pipeline fills it. So pipelines do not need an order between them.
- **What the source dropped stays** until the pipeline removes it: `ctx.graph.delete(nodes=[{type, key}])` (a node
  takes its edges with it). List what the graph holds with `ctx.graph.nodes(type)` and delete the keys the source
  no longer has, when that matters.
- A write is sent a batch at a time and each batch is kept whole or not at all. Large sources: raise
  `limits.seconds` (3600 at most) and page through the source rather than holding it all.
- **Tests** (`rrotor.testing`): `Harness(program, tmp_path, http=FakeHttp({...}), secrets={"HUBSPOT_TOKEN": "t"},
  graph=FakeGraph("write"))`; after `h.call("sync")`, `h.graph.nodes` (`{(type, key): {title, props, text}}`) and
  `h.graph.edges` (`{(from, rel, to): props}`) hold what it wrote. rrotor's `examples/hubspot_pipeline` is the model
  to follow.

Deploy it (the rrotor skill: `rrotor.sh deploy <folder>` or `program_deploy`), set its secrets (below), call it once
with `program_call` and read `graph_schema` again to see what it wrote, then leave it to its schedule
(`schedules_list`).

**A source that only Claude can reach** (a claude.ai connector with no API key): read it in this session and write
it with `graph_upsert` directly (2,000 nodes and 10,000 edges a call). That loads it once; it does not keep it
fresh, so say so. For a source that must stay fresh without a key, a program can run the Claude CLI on the rrotor
(`"clis": ["claude"]`, `ctx.cli("claude", ["-p", …])`, once the person signed it in with `cli_login`): every pull
then runs through Claude and costs tokens, so prefer a key.

## 3. Secrets: the form, never the chat

A pipeline's key is a secret its manifest declares; the person sets its value on the runtime.

- Call **`secrets_form {program}`**. In Claude it shows a form: each secret, whether it is set, and a field. What the
  person types goes straight to rrotor's vault; it is not in the conversation, and you are told only which names
  were set.
- **Never ask the person to paste a key, token or password into the chat**, and never pass one to `secret_set`
  yourself unless they already put it in the chat and ask you to.
- Where no form shows (Claude Code in a terminal), the tool's answer says how they set it themselves; give them
  that command to run in their own terminal, with the value typed by them.
- A run that fails `E_SECRET_MISSING` names what is missing: show the form, then call again.

## 4. Reading the graph

| Tool | In a program (`"graph": "read"`) | Answers |
|---|---|---|
| `graph_search {query, types?, limit?, expand?}` | `ctx.graph.search(query, types=, limit=, expand=)` | The best nodes for the words, each with the `passage` that matched (the text to answer from), a `snippet` and a `score`; `expand` adds the nodes each is linked to (`out`, `in`) |
| `graph_node {type, key}` | `ctx.graph.node(type, key)` (None when there is none) | One node whole, with its edges each way |
| `graph_nodes {type, where?, limit?, offset?}` | `ctx.graph.nodes(type, where=…)` | The nodes of a type, the newest first, whose props equal `where` |
| `graph_neighbours {type, key, rel?, direction?, depth?}` | `ctx.graph.neighbours(type, key, …)` | The nodes within 1 to 3 edges, with the edges among them |
| `graph_schema` | `ctx.graph.schema()` | Types, props, relations, totals |

To answer a question from the organisation's data: `graph_search` with the question's own words (and `expand`), read
the passages, follow an edge with `graph_node` or `graph_neighbours` when the answer is in what a hit is linked to,
and say which nodes the answer stands on. A count or a list by a property is `graph_nodes` with `where`, not a
search.

## 5. Apps on the graph

An app (the publish skill) whose page shows the organisation's data reads the graph through its own functions:
publish it with `graph: "read"`, and write one function per chart, table or search box.

```python
def won_deals(ctx, inputs):
    deals = ctx.graph.nodes("deal", where={"dealstage": "closedwon"}, limit=200)
    return Result.done({"rows": [{"name": d["title"], "amount": d["props"].get("amount")} for d in deals]})


def ask(ctx, inputs):
    hits = ctx.graph.search(inputs["q"], limit=8, expand=True)
    return Result.done({"hits": [{"title": h["title"], "type": h["type"], "passage": h["passage"]} for h in hits]})
```

The page calls `fetch("/apps/<name>/call/won_deals", {method: "POST", …})` as the viewer. The graph is not divided
by role: whoever may open the app sees what its functions answer, so give an app over sensitive data `roles`.
Prefer the graph to a function that calls the source itself: the pipeline already did that work, once, for every
app.
