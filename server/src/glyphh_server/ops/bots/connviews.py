"""What the connections routes and tools take and answer (docs/specs/bots.md, 9)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Permission = Literal["allow", "ask", "deny"]
ASK: str = "ask"  # a tool not named in a connection's permissions: its bots wait for the person's yes


class ConnectionView(BaseModel):
    id: uuid.UUID
    app: str = Field(description="The service, as Pipedream names it (gmail, slack, ...)")
    app_name: str
    app_icon: str
    account_id: str
    label: str = Field(description="The account's own name at the service")
    permissions: dict[str, str] = Field(
        description="Per tool key: allow, ask (a step using it waits for the person's yes) or deny; one not named asks"
    )
    created_at: datetime


class Connections(BaseModel):
    connections: list[ConnectionView]


class AppView(BaseModel):
    slug: str
    name: str
    description: str
    icon: str


class Apps(BaseModel):
    apps: list[AppView]
    next_cursor: str | None


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app: str = Field(min_length=1, max_length=200, description="The service's slug (connection_apps lists them)")


class Link(BaseModel):
    url: str = Field(description="Pipedream's page where the person signs in to the service for the org")
    expires_at: str | None


class ToolView(BaseModel):
    key: str = Field(description="The tool's key, as a bot's scope names it")
    name: str
    description: str
    permission: Permission = Field(description="allow, ask or deny: what the org's bots may do with it")


class Tools(BaseModel):
    tools: list[ToolView]


class PermissionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permissions: dict[str, Permission] = Field(
        max_length=500, description="Per tool key: allow, ask or deny; the keys named are changed, the rest kept"
    )
