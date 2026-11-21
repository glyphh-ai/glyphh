"""How a bot is written, for Claude making one through the connector (bot_guide) and for the platform's help: the
SDK's bot package as Glyphh's cloud runs it. Kept to what the cloud runs: no program.py, so a run step is `fetch` or
one of the bot's scoped tools, and a gate's case is its fields."""

GUIDE: str = """\
A Glyphh bot is a loop of steps that a program walks, not an agent that roams. Code-like steps fetch and act; gates
decide, each its own Ada model that learns from the person's answers and asks less run after run; Claude is called
only for the steps that need judgment. Hard limits in the loop hold whatever Claude says.

A bot is: name, summary, look (its cat), instructions (its agent's prompt: who it is, how it writes), model (the
Claude model its agent steps run on, bot_models), connections (per connection, the tool keys it may use,
connection_tools lists them), skills ({name: SKILL.md text}, how its agent does one kind of step) and spec:

spec = {
  "touches": "read_only" | "drafts" | "sends" | "pays" | "deletes",   # how far out it reaches; sends and beyond
                                                                       # need an approval step
  "hosts": ["hn.algolia.com"],          # the public hosts fetch may GET JSON from (https only)
  "seed": {"personality": [...], "instructions": [...], "memory": []},  # lines its memory starts with
  "gates": {<name>: gate},
  "loop": [step, ...],                  # walked in order; a gate's `on` jumps to a step id or "end"
  "limits": {"seconds": 300, "agent_turns": 3, "usd_per_run": 0.5, "usd_per_day": 2, "runs_per_day": 8,
             "quiet_hours": "22:00-07:00", "max_items": 30, "steps": 200}
}

Steps (each has an id; none may be called input):
- {"id": "mail", "run": "gmail-find-email", "input": {"q": "is:unread"}}  run one of its scoped tools, input its
  props; or {"id": "page", "run": "fetch", "input": "https://hn.algolia.com/api/v1/search?tags=front_page"}
- {"id": "worth", "gate": "worth", "on": {"yes": "reply", "no": "end"}}  one case, decided or asked
- {"id": "worth", "gate": "worth", "each": "$mail.messages", "label": "subject", "key": "id",
   "on": {"empty:keep": "end"}}  every item of a list: Ada decides the sure ones, the unsure are asked as one batch;
   its data is {<outcome>: [items], "decisions": [...]}; on rules: empty:<outcome>, any:<outcome>, all:<outcome>, else
- {"id": "draft", "agent": "Write a short reply to: $worth.keep", "skill": "replies", "schema": {JSON Schema},
   "remember": true}  Claude, with the step's skill and the bot's memory before it; schema makes it answer JSON
- {"id": "send", "run": "gmail-send-email", "input": {"to": "$draft.to", "body": "$draft.body"},
   "approval": "send this reply"}  an approval asks the person yes or no before the step runs
- any step: "requires": "$mail.count > 0" (a small expression over earlier data), "otherwise": "skip" | "end"

$id.path reads an earlier step's data (inside objects and lists too); $input is what the run was given.

A gate: {"outcomes": ["keep", "drop"], "question": "Worth answering?", "case": {<layer>: {<segment>: {<role>:
"$item.subject", ...}}}, "spec": <an Ada spec whose layers, segments and roles match the case>, "ask_below": 0.75,
"min_precedents": 10, "audit": 0.1, "max_questions": 10, "default": "drop"}. The case is its fields: $item.x for a
gate over items, $step.x for one case. Make one role the key (key_part true, similarity_weight 0) so items stay apart.

A run that asks waits (needs_input) until bot_run_answer answers it: one option, or for a batch "1=keep 2=drop
rest=drop". bot_run_wrong corrects a gate's call; it is learned as a precedent. One live run a bot at a time.
The agent steps run on the org's own Anthropic key when it has set one in the platform (Glyphh's markup charged),
else on Glyphh's (Anthropic's rate and the markup); bot_models lists both.
"""
