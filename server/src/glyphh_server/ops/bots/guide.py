"""How a bot is written, for Claude making one through the connector (bot_guide), for the bot maker and for the
platform's help (docs/specs/bot-agent-loop.md): a bot is a Claude agent with its own instructions, the tools of the
apps switched on for it, and Ada deciding what it decides."""

GUIDE: str = """\
A Glyphh bot is a Claude agent a person talks to, built around Ada. Each run is one conversation turn: the bot reads
what the person said (or, when it runs on its own, its standing task), decides what to do, uses its tools and
answers in plain words. It has exactly the tools of the apps switched on for it, `decide` for what Ada decides, and
`fetch` for the hosts it names. It has no shell, no web and no files on Glyphh cloud. A greeting gets a short answer
that says what it can do; nothing runs unless the task calls for it.

A bot is: name, summary (what it is for, a few plain words), look (its cat) or mascot (its own drawing,
bot_mascot), instructions (who it is and how it works, in second person: its job, which tools to use for it and in
what order, when to call decide and what to do with each outcome, what to do with the result, what to say when
there is nothing to do), task (its standing task: what it does when it runs on its own, one or two sentences),
examples (up to 6 short prompts a person might type, shown as suggestions), skills (its notes, {name: SKILL.md
text}: the know-how for one kind of work, such as how its digest is written; each a SKILL.md with name and
description frontmatter), permission_mode (before it acts: ask, each action waits for the person's yes unless its
connection allows the tool; connection, as each connection says; auto, none waits; a tool its connection denies is
always refused; reading never asks unless its connection says to), voice (bot_voices), model (bot_models),
effort ("low", "medium" (the default), "high", "xhigh" or "max"), connections (per connection, the tool keys it may
use, connection_tools lists them), schedule (when it runs on its own, in plain words, never cron: {"every": "off"
| "hour" | "day" | "weekdays" | "week" | "month", "at": "09:00", "weekday": 0 (Monday) to 6, "day": 1 to 31,
"timezone": "America/Chicago"}), runs_on (one of bot_places: a rrotor of the org's, or none for Glyphh cloud),
folders (only on a rrotor: the folders of that machine it may use, [{"path": "/Users/ana/Documents", "access":
"read" | "write"}]; there it can list, read, search, write and move files in them) and spec:

spec = {
  "gates": {<name>: decision},          # what Ada decides for it
  "hosts": ["hn.algolia.com"],          # the public hosts fetch may GET JSON from (https only)
  "limits": {"turns": 25, "seconds": 300, "tokens": 400000, "runs_per_day": 200}
}

A decision: {"outcomes": ["urgent", "normal", "spam"], "question": "How urgent is it?", "case": {<layer>:
{<segment>: {<role>: "$item.subject", ...}}}, "spec": <an Ada spec whose layers, segments and roles match the
case>, "ask_below": 0.75, "min_precedents": 10, "audit": 0.1, "max_questions": 10, "default": "normal"}. The case
is filled from each item the agent hands to decide ($item.x): say in the instructions which fields each item must
carry, and give every item an id. Make one role the key (key_part true, similarity_weight 0) so items stay apart.
Ada answers the items it is sure of; the person is asked about the rest, in the chat, and each answer is a precedent,
so it asks less over time. Never have the instructions decide what a decision decides.

A run that asks waits (needs_input) until bot_run_answer answers it: yes or no for an approval, or for items
"1=urgent 2=spam rest=normal". bot_run_wrong corrects a decision's call; it is learned as a precedent. One live run a
bot at a time. A run is billed by tokens, on the org's own Anthropic key when it has set one in the platform
(Glyphh's markup charged), else on Glyphh's (Anthropic's rate and the markup); bot_models lists both.
"""
