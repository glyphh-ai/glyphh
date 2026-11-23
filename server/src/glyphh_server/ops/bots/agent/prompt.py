"""What a bot's agent is told (docs/specs/bot-agent-loop.md, 2): its system prompt, made of who it is, its own
instructions, the decisions it can ask Ada about, what it may use and how to answer; and the words a waiting run is
carried on with once the person has answered."""

from datetime import UTC, datetime
from typing import Any

from glyphh_server.ops.bots.agent.tools import ASK, DECIDE, Tool

HOW: str = """# How you answer
- The person is talking to you. If they only greet you, or ask what you can do, say in a sentence or two what you \
do and what they can ask for, and use no tool.
- Use a tool only when the person's message, or your task, calls for it. Never search for the person's own words \
unless they asked you to look for exactly that.
- If what they ask is not something you can do with your tools, say so plainly, and say what you can do.
- Answer in clean markdown: short, the result first. Links as links. Never show raw JSON, tool names or ids.
- Never invent a result. If a tool failed or found nothing, say so in one plain sentence.
- When a tool says the person is being asked, stop: you will be told their answer."""
DECIDES: str = """# Ada
Ada knows how the person decided these before: `decide` answers from that, and `ask_person` with a decision's items \
asks the person and teaches Ada their answers. Use them as your instructions say.
{lines}"""
SKILLS: str = "# Know-how\nBefore that kind of work, load its skill: {names}."
STANDING: str = "Do your job now."
YES: str = "The person said yes to that. Do it now, exactly as you asked."
NO: str = "The person said no to that. Do not do it; carry on without it, and say what you did not do."


def _decisions(gates: dict[str, Any]) -> str:
    lines = [
        f"- `{name}`: {g.get('question') or name} One of: {', '.join(map(str, g.get('outcomes') or []))}."
        for name, g in gates.items()
    ]
    return DECIDES.format(lines="\n".join(lines))


def system(bot: Any, tools: dict[str, Tool], skills: list[str]) -> str:
    """The bot's own system prompt."""
    about = f" {bot.summary.strip()}" if bot.summary.strip() else ""
    today = datetime.now(UTC).strftime("%A %-d %B %Y")
    who = f"You are {bot.name}, a bot that works for the person talking to you.{about} Today is {today} (UTC)."
    parts = [who, bot.instructions.strip()]
    gates = bot.spec.get("gates") if isinstance(bot.spec.get("gates"), dict) else {}
    if gates and DECIDE in tools:
        parts.append(_decisions(gates))
    if skills:
        parts.append(SKILLS.format(names=", ".join(s.rsplit(":", 1)[-1] for s in skills)))
    if set(tools) <= {ASK}:
        parts.append("You have no tools: answer from what you know, and say so when a task needs an app.")
    return "\n\n".join(p for p in [*parts, HOW] if p)


def task(bot: Any, given: str) -> str:
    """What a run is given: what the person typed, else the bot's standing task."""
    return given.strip() or bot.task.strip() or STANDING


def approved(question: dict[str, Any], answer: str) -> str:
    return YES if answer == "yes" else NO


def decided(name: str, entries: list[dict[str, Any]]) -> str:
    """The person's answers about a decision's items, said back to the agent (Ada has learned them)."""
    said = "; ".join(f"{e['label']} (id {e['key']}): {e['outcome']}" for e in entries if e["by"] == "person")
    return f"The person answered ({name}): {said}. Carry on with these."


def heard(answer: Any) -> str:
    """The person's answer to the agent's own question, said back to it."""
    return f"The person answered: {answer}. Carry on."
