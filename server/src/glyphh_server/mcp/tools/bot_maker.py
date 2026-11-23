"""Create with AI through the connector (docs/specs/bots.md, 9): Glyphh's bot maker drafts a bot from a conversation
(checked by the SDK, scoped to the org's connections), and draws a bot a mascot of its own. Both ask Claude on the
bots' key, so they run on short transactions of their own (DETACHED). bot_create makes the draft."""

from glyphh_server.mcp.tools.base import Context, Done, Tool, dump
from glyphh_server.ops.bots import maker, mascot
from glyphh_server.ops.bots.maker_views import DraftIn, MascotIn, MascotView


async def draft(ctx: Context, args: DraftIn) -> Done:
    got = await maker.draft(ctx.bots, ctx.who, args)
    notes = [got.reply]
    if got.problems:
        notes.append("Still wrong: " + "; ".join(got.problems))
    if got.missing_apps:
        notes.append("Connect first: " + ", ".join(got.missing_apps) + " (connection_link).")
    return Done("\n".join(notes), dump(got))


async def draw(ctx: Context, args: MascotIn) -> Done:
    drawn = MascotView(mascot=await mascot.draw(ctx.bots, ctx.who, args.prompt))
    return Done("Drawn: bot_create or bot_update takes it as `mascot`.", dump(drawn))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "bot_draft",
        "Draft a bot with Glyphh's bot maker",
        "Glyphh's bot maker's next turn in a conversation about a bot the person wants: a short question, or the bot "
        "drafted (name, summary, cat, instructions, model, the decisions it can ask Ada about, skills, apps), checked "
        "by the SDK and scoped to the org's connections. Pass the whole conversation and the draft so far; "
        "bot_create makes it.",
        DraftIn,
        draft,
        True,
    ),
    Tool(
        "bot_mascot",
        "Draw a bot's mascot",
        "A new black-and-white mascot for a bot, drawn from a description as safe SVG: bot_create or bot_update "
        "takes it as `mascot`, shown in place of the bot's cat.",
        MascotIn,
        draw,
        True,
    ),
)
DETACHED: frozenset[str] = frozenset(t.name for t in TOOLS)
