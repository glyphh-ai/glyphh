from fastapi import APIRouter, WebSocket

from glyphh_server.link.serve import serve

router = APIRouter()


@router.websocket("/v1/machine/link")
async def link(ws: WebSocket) -> None:
    """A machine's one outbound connection: protocol 1 (the architecture, The machine link)."""
    await serve(ws)
