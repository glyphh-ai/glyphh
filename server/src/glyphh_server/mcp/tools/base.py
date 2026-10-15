"""What every tool is: a name, what it does, its arguments as a Pydantic model (their JSON Schema is the tool's input
schema), whether it only reads, whether the account panel shows its result, and its handler. A handler answers a
short text and the same as structured content."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.billing.stripe import StripeClient


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True, slots=True)
class Context:
    conn: AsyncConnection
    who: Principal
    settings: Settings
    http: httpx.AsyncClient

    def stripe(self) -> StripeClient:
        return StripeClient(self.http, self.settings.stripe_secret_key)


@dataclass(frozen=True, slots=True)
class Done:
    text: str
    data: dict[str, Any]


Handler = Callable[[Context, Any], Awaitable[Done]]


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    title: str
    description: str
    args: type[BaseModel]
    handler: Handler
    read_only: bool = False
    panel: bool = False


def dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def amount(value: int | None) -> str:
    return "unlimited" if value is None else str(value)
