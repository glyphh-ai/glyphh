"""A bot's plugins (docs/specs/bot-agent-loop.md, 7.2): the know-how a template installed for it, brought to the
version Glyphh ships now when its owner asks."""

from fastapi import APIRouter

from glyphh_server.api.auth import Conn
from glyphh_server.api.key_auth import KeyCaller as Caller
from glyphh_server.ops.bots import installed, store
from glyphh_server.ops.bots.views import BotView

router = APIRouter()


@router.post("/v1/bots/{slug}/plugins/{name}/update", operation_id="updateBotPlugin")
async def update_plugin(slug: str, name: str, who: Caller, conn: Conn) -> BotView:
    """The bot's plugin from a template brought to the version Glyphh ships now: its know-how replaced, the
    decisions the new version adds added. What the person edited, and what a decision learned, is left as it is.
    404 when the bot has no such plugin from a template."""
    await installed.update(conn, await store.row(conn, slug), name)
    return await store.one(conn, slug)
