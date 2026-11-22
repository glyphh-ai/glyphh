"""Create with AI (docs/specs/bots.md, 9): the bot maker's next turn in a conversation about the bot the person wants,
and a mascot drawn from their words. Both ask Claude on the bots' own key (the org's or Glyphh's, metered), so they
sign the caller in on a short transaction of their own and hold none while Claude answers. Neither makes a bot:
POST /v1/bots makes the draft, its mascot with it."""

from typing import Any

from fastapi import APIRouter, Request

from glyphh_server.api.templates import Person
from glyphh_server.ops.bots import maker, mascot
from glyphh_server.ops.bots.maker_views import DraftIn, DraftView, MascotIn, MascotView

router = APIRouter(tags=["bots"])


def _bots(request: Request) -> Any:
    return request.app.state.bots


@router.post("/v1/bots/draft", operation_id="draftBot")
async def draft_bot(body: DraftIn, request: Request, who: Person) -> DraftView:
    """The bot maker's next turn: a short question, or the bot drafted (checked by the SDK, its problems said, its apps
    scoped to the org's connections and the ones not connected named). With neither Anthropic key, 503
    anthropic_off."""
    return await maker.draft(_bots(request), who, body)


@router.post("/v1/bots/mascot", operation_id="drawBotMascot")
async def draw_mascot(body: MascotIn, request: Request, who: Person) -> MascotView:
    """A new mascot drawn from the words given: black-and-white SVG shapes, made safe, for a bot's `mascot`."""
    return MascotView(mascot=await mascot.draw(_bots(request), who, body.prompt))
