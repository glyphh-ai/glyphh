# A model's spec

The spec is JSON: what a case looks like, what the outcome is, and what each mistake costs. `ada_model_create
{name, spec}` checks it (the kernel's own check, `E_SPEC` with a `path` saying where; then the cloud's bounds,
`E_SPEC_LIMIT`). Every field not marked required has a sound default.

```json
{
  "name": "tickets",
  "layers": [
    {"name": "ticket", "segments": [
      {"name": "what", "roles": [
        {"name": "plan"},
        {"name": "channel"},
        {"name": "age_days", "numeric_config": {"min_value": 0, "max_value": 30, "bin_width": 3}},
        {"name": "text", "text_encoding": "bag_of_words"},
        {"name": "ref", "key_part": true, "similarity_weight": 0}
      ]},
      {"name": "internal", "security_weight": 0.8, "roles": [
        {"name": "owner"}, {"name": "cause"}
      ]}
    ]}
  ],
  "output": {
    "costs": {"refund": {"keep": 3}, "keep": {"refund": 1}},
    "ask_below": 0.6
  },
  "settings": {"refresh_every": 100}
}
```

A case is sent in the same shape, layer by segment by role:
`{"ticket": {"what": {"plan": "pro", "channel": "mail", "age_days": 4, "text": "charged twice", "ref": "T-1009"}}}`.
A role the case leaves out weighs nothing in its answer. Paths name a role as `layer.segment.role`
(`ticket.what.plan`): a CSV header, an import mapping and a refusal's `path` use them.

## Fields

| Field | What |
|---|---|
| `name` (required) | The spec's name: letters, digits, `_`, `-` |
| `layers` (required) | Layers of `segments` of `roles`, each named; layers and segments may carry `similarity_weight` (0 to 1, default 1: their voice) and `security_weight` (0 to 1: the clearance a reader needs to see them) |
| `output` | The default output: `costs`, `ask`, `ask_below`, `report` (below) |
| `outputs` | Named outputs, when one case answers several questions: `{"team": {"values": ["billing", "tech"], "costs": {...}, "ask": 0.5, "ask_below": 0.6}, "urgent": {...}}`. A case's outcomes are then `{"outcomes": {"team": "billing", "urgent": "no"}}`; a CSV names them `outcome.team` |
| `interactions` | Pairs of roles always read together: `[{"name": "plan_x_channel", "roles": ["ticket.what.plan", "ticket.what.channel"]}]` (learning finds the telling pairs by itself; declare one only when the user knows it matters) |
| `temporal_source` | The role that is a case's time (`"ticket.what.opened"`); else when it was recorded |
| `settings` | The levers ([tuning.md](tuning.md)) |
| `seed`, `dimension` | The encoding (default 42 and 4,096; the cloud allows up to 8,192). Leave them unless there is a reason |

## Roles

| A role is | Write | Reads |
|---|---|---|
| An exact value (a plan, a country, an error class) | `{"name": "plan"}` | Equal or not; a list is a set of values |
| Free text | `{"name": "text", "text_encoding": "bag_of_words"}` | Its words, through the lexicon (related words correlate); learning weighs the telling words |
| A number on a scale | `{"name": "amount", "numeric_config": {"min_value": 0, "max_value": 5000, "bin_width": 250}}` | Its bin (at most 1,000 bins): near numbers are near |
| An id (the case's own key) | `{"name": "ref", "key_part": true, "similarity_weight": 0}` | Not compared: it makes the case's id, so the same id sent again replaces its precedent |

A role may also carry `similarity_weight` (its voice, 0 to 1; learning sets the real weights from the precedents),
`security_weight` (the clearance a reader needs to see it: owners, causes, internal notes), `value_weights`
(`{"negative": 1.0}`: how much each value says; usually learned, not written) and `lexicons` (other names the role
goes by in data).

**Choose each role's reading once.** Whether a role is exact, text, a number (and its bins) or a key part cannot be
changed on a model that holds cases: the stored cases keep only how they were read (a number's bin, a text's words),
not the data sent, so they cannot be read again another way (`E_SPEC_READING`). The fix is a new model with the new
spec and an import of the history (the original file, not the export: the export holds cases as they were read).
Adding or taking away roles, the weights, costs and settings can change at any time, as new versions.

## The output: costs and asking

- `costs`: what deciding wrong costs, `{decided: {true outcome: cost}}`. `{"refund": {"keep": 3}, "keep": {"refund":
  1}}`: refunding a ticket that should have been kept costs three of the other mistake. Unset, every mistake costs 1.
  These are the user's business numbers: ask them.
- `ask`: what a person's answer costs, in the same units. `decide` says `ask: true` wherever every choice is dearer.
- `ask_below`: ask whenever the top probability is under it (0.6 is a sound start): the bar for people who think in
  confidence, not costs.
- `report`: the paths a fact tree shows (`["ticket.internal.cause"]`), each still cut by the reader's clearance.

## The cloud's bounds

A spec is at most 64 KB of JSON, 64 roles, 20 named outputs, 200 values an output, `k` 200 and `dimension` 8,192
(`E_SPEC_LIMIT` names the bound). No string may hold the NUL character.
