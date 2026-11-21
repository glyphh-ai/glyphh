"""The org's connections to other services (docs/specs/bots.md, Connections): Pipedream's accounts, signed in on its own
page, for the org's bots to use. Every route answers 503 E_UNAVAILABLE (reason pipedream_off) while Pipedream is not
set up. The routes that call Pipedream sign the caller in on a short transaction of their own, none held while it
answers."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.api.templates import Person
from glyphh_server.errors import Unavailable
from glyphh_server.ops.bots import connections
from glyphh_server.ops.bots.connviews import Apps, Connections, ConnectionView, Link, LinkIn, PermissionsIn, Tools
from glyphh_server.ops.bots.pipedream import OFF, Pipedream

router = APIRouter(tags=["connections"])


def pipedream(request: Request) -> Pipedream:
    pd: Pipedream = request.app.state.bots.pd
    if not pd.on:
        raise Unavailable(OFF, reason="pipedream_off")
    return pd


@router.get("/v1/connections", operation_id="listConnections")
async def list_connections(request: Request, caller: Caller, conn: Conn) -> Connections:
    pipedream(request)
    return Connections(connections=await connections.listing(conn))


@router.get("/v1/connections/apps", operation_id="listConnectionApps")
async def list_apps(
    request: Request,
    caller: Caller,
    q: Annotated[str | None, Query(max_length=200, description="Matches the service's name")] = None,
    cursor: Annotated[str | None, Query(max_length=500, description="next_cursor of the page before")] = None,
) -> Apps:
    """The services a connection can be made to."""
    return await connections.apps(pipedream(request), q, cursor)


@router.post("/v1/connections/link", operation_id="linkConnection")
async def link(body: LinkIn, request: Request, who: Person) -> Link:
    """A page where someone signs in to the service for the org; a sync afterwards adds the connection."""
    return await connections.link(pipedream(request), who, body.app)


@router.post("/v1/connections/sync", operation_id="syncConnections")
async def sync(request: Request, who: Person) -> Connections:
    """The org's connections made to match its accounts at Pipedream: new ones added, gone ones removed."""
    state: Any = request.app.state
    return Connections(connections=await connections.sync(pipedream(request), state.engine, who))


@router.delete("/v1/connections/{connection_id}", operation_id="deleteConnection", status_code=204)
async def delete_connection(connection_id: uuid.UUID, request: Request, who: Person) -> Response:
    """The connection removed, its account at Pipedream too; bots lose its tools."""
    await connections.remove(pipedream(request), request.app.state.engine, who, connection_id)
    return Response(status_code=204)


@router.get("/v1/connections/{connection_id}/tools", operation_id="listConnectionTools")
async def list_tools(connection_id: uuid.UUID, request: Request, who: Person) -> Tools:
    """What a bot may be let do with the connection (PUT /v1/bots/{slug}/connections scopes it), each tool with what
    the org's bots may do with it."""
    found = await connections.tools(pipedream(request), request.app.state.engine, who, connection_id)
    return Tools(tools=found)


@router.put("/v1/connections/{connection_id}/permissions", operation_id="setConnectionPermissions")
async def set_permissions(connection_id: uuid.UUID, body: PermissionsIn, caller: Caller, conn: Conn) -> ConnectionView:
    """Per tool, what the org's bots may do with it: allow, ask (a step using it waits for the person's yes) or deny.
    A tool not named asks."""
    return await connections.set_permissions(conn, connection_id, body)
