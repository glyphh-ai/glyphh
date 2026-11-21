"""Who calls the Ada API: an API key (`glyphh_ak_…`, with its clearance), or a Glyphh sign-in (an install's token or an
OAuth access token, as the rest of the API takes them; full clearance). Resolved in a short transaction of its own,
so no database connection is held while a worker answers, and kept KEY_TTL seconds in the process, so a burst of
reads costs one lookup: a revoked key stops working within that. Anything wrong is one answer, 401 E_AUTH."""

import hashlib
import time
import uuid
from dataclasses import dataclass, replace
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada import keys
from glyphh_ada.allowance import Allowance, allowance
from glyphh_ada.errors import NoKey
from glyphh_server.api.auth import Bearer, authenticate
from glyphh_server.errors import Unauthorized
from glyphh_server.obs import context

KEY_TTL: float = 10.0
KEPT_MAX: int = 10_000


@dataclass(frozen=True)
class AdaCaller:
    org_id: uuid.UUID
    user_id: uuid.UUID
    clearance: float
    key_id: uuid.UUID | None = None
    allowance: Allowance | None = None  # what the org's plan allows; None: nothing counted (an upload's own link)

    @property
    def cap(self) -> int | None:
        """The precedents the org's plan allows across its models; None: no cap."""
        return None if self.allowance is None else self.allowance.precedents

    @property
    def author(self) -> str:
        return str(self.user_id)

    def clearance_for(self, asked: float | None) -> float:
        """A request may read with less clearance than its key's, never more."""
        return self.clearance if asked is None else max(0.0, min(float(asked), self.clearance))


async def _found(request: Request, conn: AsyncConnection, creds: HTTPAuthorizationCredentials) -> AdaCaller | None:
    if creds.credentials.startswith(keys.PREFIX):
        found = await keys.holder(conn, creds.credentials)
        return None if found is None else AdaCaller(found.org_id, found.user_id, found.clearance, found.key_id)
    try:
        who = await authenticate(conn, creds, request.app.state.settings.mcp_resource)
    except Unauthorized:
        return None
    return AdaCaller(who.org_id, who.user_id, 1.0)


async def _resolve(request: Request, creds: HTTPAuthorizationCredentials) -> AdaCaller | None:
    """The caller, with what its org's plan allows (its version's cloud limits)."""
    async with request.app.state.engine.begin() as conn:
        found = await _found(request, conn, creds)
        if found is None:
            return None
        return replace(found, allowance=await allowance(conn, found.org_id))


async def ada_caller(request: Request, creds: Bearer) -> AdaCaller:
    if creds is None:
        raise NoKey("Send an API key: Authorization: Bearer <key>.")
    kept: dict[str, tuple[float, AdaCaller]] = request.app.state.ada_callers
    hashed = hashlib.sha256(creds.credentials.encode()).hexdigest()
    hit = kept.get(hashed)
    if hit is None or hit[0] <= time.monotonic():
        found = await _resolve(request, creds)
        if found is None:
            raise NoKey("That key is not a live Glyphh API key or sign-in.")
        if len(kept) >= KEPT_MAX:
            kept.clear()
        hit = kept[hashed] = (time.monotonic() + KEY_TTL, found)
    who = hit[1]
    context.user_id.set(str(who.user_id))
    context.org_id.set(str(who.org_id))
    return who


AdaWho = Annotated[AdaCaller, Depends(ada_caller)]
